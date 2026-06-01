"""20260531_0300 -- PIPELINE v3: native-resolution two-hat architecture.
480-hat (karar): v1 extract (scale=-2:480) + TUM v2 kararlari (split_runs, qwen, split_cards, text_band).
NATIVE-hat (piksel): ffmpeg fps=5, scale YOK -> native kareler.
SF = Hnative / 480.  Final kesim: SCROLL->slitscan_native, KART->text_band*SF native'den.
480p kaynaklarda SF=1.0 -> cikti v2 ile ozdes olacak (regresyon kaniti).
Cikti: tester_v3/ (tester/ ve tester_v2/ DOKUNULMAZ).
"""
import sys, json, glob, importlib.util, subprocess, argparse, urllib.request
from pathlib import Path
import cv2, numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---- importlib: sys.modules ONCE BEFORE exec_module (dataclass tuzagi) ----
FP_PATH = r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py"
V2_PATH = r"E:\MITAS\OCR-worktree\py\20260530_2350_full_pipeline_v2.py"

spec_fp = importlib.util.spec_from_file_location("fp", FP_PATH)
fp = importlib.util.module_from_spec(spec_fp)
sys.modules["fp"] = fp
spec_fp.loader.exec_module(fp)

spec_v2 = importlib.util.spec_from_file_location("v2", V2_PATH)
v2mod = importlib.util.module_from_spec(spec_v2)
sys.modules["v2"] = v2mod
spec_v2.loader.exec_module(v2mod)

V1BASE  = Path(r"E:\MITAS\OCR-worktree\tester")
OUTBASE = Path(r"E:\MITAS\OCR-worktree\tester_v3")


# ============================================================
# NATIVE-HAT: frame extraction (no scale)
# ============================================================
def _src_height(video):
    """ffprobe ile kaynak yuksekligi (cp1254 stderr cokmesini onlemek icin bayt-decode)."""
    ffprobe = fp.FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")
    try:
        r = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=height", "-of", "csv=p=0", video],
            capture_output=True, timeout=30)
        out = r.stdout.decode("utf-8", "ignore").strip().splitlines()
        return int(out[0]) if out else 0
    except Exception:
        return 0

def extract_native(video, s0, s1, fdir):
    fdir.mkdir(parents=True, exist_ok=True)
    ex = sorted(glob.glob(str(fdir / "f_*.png")))
    if ex:
        return ex
    # 288p-GUVENLI: kaynak >=480 ise NATIVE (downscale yok); <480 ise 480'e cikar
    # -> 720p keskinlesir, 480p birebir, 288p KUCULMEZ (v2 ile ayni, regresyon yok).
    h = _src_height(video)
    vf = f"fps={fp.FPS}" if h >= 480 else f"fps={fp.FPS},scale=-2:480"
    subprocess.run(
        [fp.FFMPEG, "-y", "-ss", str(s0), "-t", str(s1 - s0), "-i", video,
         "-vf", vf, "-q:v", "2", str(fdir / "f_%05d.png")],
        capture_output=True
    )
    return sorted(glob.glob(str(fdir / "f_*.png")))


# ============================================================
# SCROLL BRANCH: slitscan_native
# velocity measured on 480-proxy, strip cut from native frame
# Directly from brief reference code (kaniti var, degistirme)
# ============================================================
def slitscan_native(frames_native):
    """480-proxy'de hiz ol, serit native'den kes. Brifteki referans kod aynen."""
    H = W = hann = prev = None
    pa = False
    strips = []
    SF = refN = None
    dropped_vmax = 0
    for f in frames_native:
        img = fp.rd(f)
        if img is None:
            continue
        Hn, Wn = img.shape[:2]
        proxy = cv2.resize(
            img,
            (max(1, int(round(Wn * 480.0 / Hn))), 480),
            interpolation=cv2.INTER_AREA
        )
        if H is None:
            H, W = proxy.shape[:2]
            hann = cv2.createHanningWindow((W, H), cv2.CV_32F)
            SF = Hn / 480.0
            refN = int(round(fp.SLIT_FRAC * Hn))
        g = cv2.cvtColor(proxy, cv2.COLOR_BGR2GRAY)
        gf = g.astype(np.float32)
        m = fp.tophat(g)
        md = cv2.dilate(m, np.ones((11, 11), np.uint8))
        mg = gf.copy()
        mg[md == 0] = 0.0
        dy = 0.0
        if prev is not None and bool(md.any()) and pa:
            (_, dy), _ = cv2.phaseCorrelate(prev * hann, mg * hann)
        prev = mg
        pa = bool(md.any())
        v = int(round(abs(dy)))
        if v < fp.VMIN or v > fp.VMAX:
            if v > fp.VMAX:
                dropped_vmax += 1
            continue
        vN = int(round(v * SF))
        s = img[refN:refN + vN, :].copy()
        if s.shape[0] > 0:
            strips.append(s)
    result = np.vstack(strips) if strips else None
    return result, dropped_vmax


# ============================================================
# CARD BRANCH: native_split_cards
# Mirrors v2.split_cards logic on 480 frames but yields
# (y0_480, y1_480, frame_idx_in_run) so we can cut native.
# ============================================================
def native_split_cards(frames_480, frames_native, SF):
    """v2.split_cards mantigini 480 uzayinda calistir, koordinatlari
    SF ile olcekleyip native kareden kes. v2 ile ayni karar -> v2 ile
    ozdes blok sayisi (480p kaynaklarda piksel de ozdes)."""
    TB_SWAP = v2mod.TB_SWAP
    MIN_CARD = v2mod.MIN_CARD
    PAD = fp.PAD

    # -- split_cards phase: collect sub-runs with (sharpness, frame_idx, img480, mask) --
    sub = []
    cur = []
    pg = pm = None
    for i, f in enumerate(frames_480):
        img = fp.rd(f)
        if img is None:
            continue
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        m = fp.tophat(g)
        txt = fp.has_text(m)
        tb_val = 0.0
        if pg is not None and pm is not None:
            reg = (m > 0) | (pm > 0)
            if reg.any():
                tb_val = float(np.mean(np.abs(g[reg].astype(np.float32) - pg[reg].astype(np.float32))))
        pg = g
        pm = m
        if cur and ((not txt) or tb_val > TB_SWAP):
            sub.append(cur)
            cur = []
        if txt:
            cur.append((fp.sharpv(g), i, img, m))
    if cur:
        sub.append(cur)
    sub = [c for c in sub if len(c) >= MIN_CARD]

    # -- text_band per sub-run, collect (y0, y1, fidx, crop480) for dedup --
    bands = []
    for c in sub:
        _, fidx, bimg480, bm = max(c, key=lambda t: t[0])
        tbnd = fp.text_band(bm)
        if tbnd is None:
            continue
        y0 = max(0, tbnd[0] - PAD)
        y1 = min(bimg480.shape[0], tbnd[1] + PAD)
        crop480 = bimg480[y0:y1, :]
        bands.append((y0, y1, fidx, crop480))

    # -- NCC dedup (same threshold as v2: 0.95) --
    deduped = []
    for item in bands:
        y0, y1, fidx, crop480 = item
        if deduped:
            prev_crop = deduped[-1][3]
            ag = cv2.cvtColor(prev_crop, cv2.COLOR_BGR2GRAY).astype(np.float32)
            bg = cv2.cvtColor(crop480, cv2.COLOR_BGR2GRAY).astype(np.float32)
            if abs(ag.shape[0] - bg.shape[0]) <= 6:
                hh = min(ag.shape[0], bg.shape[0])
                ww = min(ag.shape[1], bg.shape[1])
                score = float(cv2.matchTemplate(ag[:hh, :ww], bg[:hh, :ww], cv2.TM_CCOEFF_NORMED).max())
                if score >= 0.95:
                    continue
        deduped.append(item)

    # -- cut from native frames using SF --
    native_cards = []
    for y0_480, y1_480, fidx_in_run, _ in deduped:
        nat_idx = min(fidx_in_run, len(frames_native) - 1)
        nat_img = fp.rd(frames_native[nat_idx])
        if nat_img is None:
            continue
        Hn = nat_img.shape[0]
        sf_local = Hn / 480.0  # per-frame SF (robust to edge case)
        y0n = max(0, int(round(y0_480 * sf_local)))
        y1n = min(Hn, int(round(y1_480 * sf_local)))
        if y0n >= y1n:
            continue
        nc = nat_img[y0n:y1n, :].copy()
        if nc.size:
            native_cards.append(nc)

    return native_cards


# ============================================================
# PROCESS: two-hat pipeline for one (film, seg)
# ============================================================
def process_v3(video, s0, s1, outdir):
    film_name = outdir.parent.name
    seg_name  = outdir.name

    # 480-HAT: reuse existing v1 frames (already extracted to tester/)
    frames_480_dir = V1BASE / film_name / seg_name / "frames"
    if not frames_480_dir.exists():
        # fallback: extract 480 frames ourselves
        frames_480_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [fp.FFMPEG, "-y", "-ss", str(s0), "-t", str(s1 - s0), "-i", video,
             "-vf", f"fps={fp.FPS},scale=-2:480", "-q:v", "2",
             str(frames_480_dir / "f_%05d.png")],
            capture_output=True
        )
    frames_480 = sorted(glob.glob(str(frames_480_dir / "f_*.png")))
    if not frames_480:
        return {"err": "no 480 frames"}

    # NATIVE-HAT: extract native frames (no scale)
    native_dir = outdir / "frames_native"
    frames_native = extract_native(video, s0, s1, native_dir)
    if not frames_native:
        return {"err": "no native frames"}

    # SF from first native frame
    first_nat = fp.rd(frames_native[0])
    Hn_first = first_nat.shape[0]
    SF = Hn_first / 480.0

    print(f"  SF={SF:.4f}  native={first_nat.shape[:2]}  n480={len(frames_480)}  nnative={len(frames_native)}")

    # --- 480-hat decisions (AYNEN v2 kararlari) ---
    runs = fp.split_runs(frames_480)
    blocks = []
    man = []
    total_dropped_vmax = 0

    for (a, b, lab) in runs:
        rf480 = frames_480[a:b + 1]

        # Best 480 frame for qwen/text check
        sh = [(fp.sharpv(cv2.cvtColor(fp.rd(f), cv2.COLOR_BGR2GRAY)), f) for f in rf480]
        _, bestf = max(sh, key=lambda t: t[0])
        bimg_480 = fp.rd(bestf)
        bm_480 = fp.tophat(cv2.cvtColor(bimg_480, cv2.COLOR_BGR2GRAY))

        if not fp.has_text(bm_480):
            man.append({"run": [a, b], "lab": lab, "skip": "no-text"})
            continue

        try:
            pred = fp.qwen(bestf)
        except Exception as e:
            pred = {"err": str(e)[:30]}

        if str(pred.get("is_credit")).lower() != "true":
            man.append({"run": [a, b], "lab": lab, "skip": "bekci-footage", "pred": pred})
            continue

        # Align native run indices (480 and native same fps, same window -> same count)
        a_nat = min(a, len(frames_native) - 1)
        b_nat = min(b, len(frames_native) - 1)
        rf_native = frames_native[a_nat:b_nat + 1]

        if lab == "R":
            # SCROLL: slitscan_native (proxy velocity, native strip)
            if not rf_native:
                man.append({"run": [a, b], "lab": lab, "skip": "no-native-frames", "pred": pred})
                continue
            blk, dropped = slitscan_native(rf_native)
            total_dropped_vmax += dropped
            if blk is not None and blk.size:
                blocks.append(blk)
                man.append({"run": [a, b], "lab": lab, "kind": "scroll",
                            "h": int(blk.shape[0]), "dropped_vmax": dropped, "pred": pred})
            else:
                man.append({"run": [a, b], "lab": lab, "skip": "empty-scroll",
                            "dropped_vmax": dropped, "pred": pred})

        else:
            # STATIC: native_split_cards (v2 logic, native cuts)
            native_cards = native_split_cards(rf480, rf_native, SF)
            fb = False
            if not native_cards:
                # FALLBACK: single best card (v1-style) from native frame
                tb480 = fp.text_band(bm_480)
                if tb480 is not None:
                    # Use best-sharp native frame from run
                    if rf_native:
                        sh_nat = [(fp.sharpv(cv2.cvtColor(fp.rd(f), cv2.COLOR_BGR2GRAY)), f) for f in rf_native]
                        _, best_nat_f = max(sh_nat, key=lambda t: t[0])
                        nat_img = fp.rd(best_nat_f)
                    else:
                        nat_img = fp.rd(frames_native[a_nat])
                    if nat_img is not None:
                        Hn = nat_img.shape[0]
                        sf_l = Hn / 480.0
                        y0n = max(0, int(round(max(0, tb480[0] - fp.PAD) * sf_l)))
                        y1n = min(Hn, int(round(min(480, tb480[1] + fp.PAD) * sf_l)))
                        if y0n < y1n:
                            nc = nat_img[y0n:y1n, :].copy()
                            if nc.size:
                                native_cards = [nc]
                                fb = True

            for nc in native_cards:
                if nc is not None and nc.size:
                    blocks.append(nc)

            man.append({"run": [a, b], "lab": lab, "kind": "cards",
                        "n_cards": len(native_cards), "fallback": fb, "pred": pred})

    # Build master (v2 layout: vstack + 12px separators + W-padding)
    if blocks:
        W = max(b.shape[1] for b in blocks)
        norm = [
            cv2.copyMakeBorder(b, 0, 0, 0, W - b.shape[1], cv2.BORDER_CONSTANT, value=(0, 0, 0))
            if b.shape[1] < W else b
            for b in blocks
        ]
        sep = []
        for b in norm:
            sep.append(b)
            sep.append(np.zeros((12, W, 3), np.uint8))
        master = np.vstack(sep[:-1])
        outdir.mkdir(parents=True, exist_ok=True)
        fp.wr(outdir / "master.png", master)
        ms = [int(master.shape[1]), int(master.shape[0])]
    else:
        ms = None

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "manifest.json").write_text(
        json.dumps({"blocks": len(blocks), "master": ms, "SF": SF,
                    "dropped_vmax": total_dropped_vmax, "runs": man},
                   ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return {"blocks": len(blocks), "master": ms, "SF": SF, "dropped_vmax": total_dropped_vmax}


# ============================================================
# MAIN
# ============================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idxs", default="")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    meta = json.loads(Path(fp.META).read_text(encoding="utf-8"))
    idx2item = {int(it["idx"]): it for it in meta}

    # Default: only the 4 test films mandated by brief (no batch)
    # idx50=DIRILIS-9132 (720p), idx21=X-MEN (480p), idx13=SON_METRO (480p), idx51=BIZIM_EVIN (720p)
    DEFAULT_IDXS = [50, 21, 13, 51]
    want = [int(x) for x in a.idxs.split(",") if x.strip()] or DEFAULT_IDXS

    # warmup qwen
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                fp.OLLAMA,
                json.dumps({"model": fp.MODEL, "prompt": "ok", "stream": False, "keep_alive": "15m"}).encode(),
                {"Content-Type": "application/json"}
            ), timeout=600
        ).read()
        print("qwen warmup OK")
    except Exception as e:
        print(f"warmup: {e}")

    summary = []
    for idx in want:
        item = idx2item.get(idx)
        if not item:
            print(f"[idx yok] {idx}")
            continue
        video = item["path"]
        if not Path(video).exists():
            print(f"[video yok] {video}")
            continue
        film = fp.safe(Path(video).stem)
        if idx not in fp.WIN:
            print(f"[WIN yok] idx={idx}")
            continue
        gs, ge, cs, ce = fp.WIN[idx]
        for seg, (s0, s1) in [("giris", (gs, ge)), ("cikis", (cs, ce))]:
            od = OUTBASE / film / seg
            print(f"\n[v3] idx={idx} {film}/{seg} ({s0}-{s1}s)", flush=True)
            try:
                r = process_v3(video, s0, s1, od)
                r.update(idx=idx, film=film, seg=seg, tc=f"{s0}-{s1}")
                print(
                    f"[OK] {film}/{seg}: blocks={r.get('blocks')} "
                    f"master={r.get('master')} SF={r.get('SF'):.3f} "
                    f"dropped_vmax={r.get('dropped_vmax')}",
                    flush=True
                )
            except Exception as e:
                import traceback
                r = {"idx": idx, "film": film, "seg": seg, "err": repr(e)}
                print(f"[ERR] {film}/{seg}: {e!r}", flush=True)
                traceback.print_exc()
            summary.append(r)

    OUTBASE.mkdir(parents=True, exist_ok=True)
    (OUTBASE / "_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nv3 SUMMARY -> {OUTBASE / '_SUMMARY.json'} ({len(summary)} is)")


if __name__ == "__main__":
    main()
