"""db_compose_master.py'yi HAVUZ filmlerine (düz frame klasörü) uygula — smart 'master' mod.
Çıktı: db_masters_master/<safe>/cikis/master.png + master_slit.png + master_mosaic.png + manifest.json"""
import sys, glob, json, time, importlib.util
from pathlib import Path
from types import SimpleNamespace
import cv2, numpy as np

spec = importlib.util.spec_from_file_location("dcm", r"E:\MITAS\OCR-worktree\db_compose_master.py")
M = importlib.util.module_from_spec(spec); sys.modules["dcm"] = M; spec.loader.exec_module(M)

POOL = Path(r"C:\Users\TRT03\Desktop\test")
OUT = Path(r"E:\MITAS\OCR-worktree\db_masters_master"); OUT.mkdir(parents=True, exist_ok=True)
args = SimpleNamespace(deinterlace=False, polarity="auto", luma_key=False, no_dedup=False,
                       text_only=False, debug=False, flip=False, cut_resp=0.05, min_hold=5, tht=22,
                       no_card_split=False, card_same_thr=6, card_min_hold=5)


def wr(path, img):
    ok, b = cv2.imencode(".png", img); b.tofile(str(path))


needles = sys.argv[1:]
dirs = sorted([d for d in POOL.iterdir() if d.is_dir()], key=lambda p: p.name.lower())
sel = []
if needles:
    for n in needles:
        sel += [d for d in dirs if n.lower() in d.name.lower()]
else:
    sel = dirs

for fd in sel:
    frames = sorted(glob.glob(str(fd / "*.png")), key=M.nat_sort_key)
    if not frames:
        print("kare yok:", fd.name); continue
    M.clear_cache()
    first = M.first_readable(frames)
    if first is None:
        print("okunmaz:", fd.name); continue
    h, w = first.shape[:2]
    p = M.derive_params(h, w, args)
    safe = "".join(c if c.isalnum() else "_" for c in fd.name)[:50]
    od = OUT / safe / "cikis"; od.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        runs = M.split_runs(frames, p, args)
        sF = sum(int(r[1]) - int(r[0]) + 1 for r in runs if r[2] == "S")
        rF = sum(int(r[1]) - int(r[0]) + 1 for r in runs if r[2] == "R")
        scroll_frac = rF / max(1, sF + rF)

        slit_master, slit_manifest, _ = M.compose_slit(frames, p, args)
        kept = [m for m in slit_manifest if isinstance(m, dict) and "h" in m and "skip" not in m]
        nb = len(kept)
        n_card = sum(1 for m in kept if m.get("kind") == "card")
        n_scroll = sum(1 for m in kept if m.get("kind") == "scroll")
        if slit_master is not None:
            wr(od / "master_slit.png", slit_master)

        mosaic_master, mos_meta = None, {}
        if scroll_frac < 0.5:
            mosaic_master, mos_meta, _ = M.compose_mosaic(frames, p, args)
            if mosaic_master is not None:
                wr(od / "master_mosaic.png", mosaic_master)

        canonical, sel_mode = M.select_master(slit_master, mosaic_master, scroll_frac, h)
        flags = []
        if isinstance(mos_meta, dict) and mos_meta.get("reject"):
            flags.append("bloat" if mos_meta.get("bloat", 0) > 3 else "cut_storm")
        if canonical is not None:
            wr(od / "master.png", canonical)
            if canonical.shape[0] < int(1.6 * h):
                flags.append("very_short")
            if n_card <= 1 and n_scroll == 0:
                flags.append("single_card")
        size = None if canonical is None else f"{canonical.shape[1]}x{canonical.shape[0]}"
        json.dump({"runs": len(runs), "scroll_frac": round(scroll_frac, 3), "blocks": nb,
                   "selected_mode": sel_mode, "flags": flags, "mosaic_reject": mos_meta.get("err") if mos_meta else None,
                   "manifest": slit_manifest},
                  open(od / "manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{fd.name[:30]:32} runs={len(runs):3} scroll={scroll_frac:.2f} kart-blok={nb:3} "
              f"sel={sel_mode} master={size} flags={flags} ({time.time()-t0:.1f}s)", flush=True)
    except Exception as e:
        import traceback
        print(f"{fd.name[:30]:32} ERR {repr(e)[:120]}", flush=True)
        traceback.print_exc()
print("-> ", OUT, flush=True)
