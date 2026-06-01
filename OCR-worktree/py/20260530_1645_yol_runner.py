"""20260530_1645 — YOL 1 vs YOL 2 koşturucu (yeni 11-film test seti).

Her iş için: ffmpeg ile jenerik TC penceresinden kare çıkar -> AYNI karelerde
  YOL 1 = pipeline run_text_layer_row_reconstruct (metin-farkında photo-finish)
  YOL 2 = ham-kare MASKELİ-hız slit-scan (yazı strokelarından hız)
Çıktı: OCR-worktree/out/yol_test_<tag>/<job>/{yol1/row_composite.png, yol2_master.png}
       + _compare/ (yan yana için) + _summary.json
"""
from __future__ import annotations
import sys, json, glob, subprocess, argparse, importlib.util
from pathlib import Path
import cv2, numpy as np

FFMPEG = r"E:\MITAS\tools\ffmpeg-shared\ffmpeg-8.1.1-full_build-shared\bin\ffmpeg.exe"
META   = r"E:\MITAS\_jenerik_analysis\dense5_metadata.json"
TLRR   = r"E:\MITAS\core\pipelines\ocr\text_layer_row_reconstruct.py"
FPS    = 5
SLIT_FRAC, VMIN, VMAX, TOPHAT_K, TOPHAT_THR = 0.55, 1, 40, 15, 22

# (idx, kısa ad, segment, start_s, end_s)  — TC'ler make_v2_contact_sheets segments'ından
JOBS = [
    (39, "robinson_crusoe", "cikis", 4995, 5205),
    (38, "sansimi_seveyim",  "giris", 0,    235),
    (36, "mumya",            "cikis", 6795, 7235),
    (34, "barbarlar",        "cikis", 6155, 6410),
    (32, "ozgurluk",         "cikis", 6985, 7300),
    (30, "dert_bende",       "giris", 0,    120),
    (28, "altin_yumruk",     "giris", 0,    225),
    (42, "senin_hikayen",    "cikis", 5805, 6035),
    (22, "yabandan",         "giris", 0,    210),
    (18, "ciplak_agaclar",   "cikis", 5610, 5750),
    (15, "pilkington",       "giris", 0,    65),
    (15, "pilkington",       "cikis", 5815, 5888),
]

def rd(p): return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
def wr(p, i):
    ok, b = cv2.imencode(".png", i)
    if ok: b.tofile(str(p))

def load_yol1():
    spec = importlib.util.spec_from_file_location("tlrr", TLRR)
    m = importlib.util.module_from_spec(spec)
    sys.modules["tlrr"] = m            # dataclass __module__ çözümü için şart
    spec.loader.exec_module(m)
    return m.run_text_layer_row_reconstruct

def tophat(g):
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (TOPHAT_K, 5))
    th = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, k)
    _, m = cv2.threshold(th, TOPHAT_THR, 255, cv2.THRESH_BINARY)
    return m

def yol2_slitscan(frame_paths):
    """Maskeli-hız slit-scan: hız YAZI strokelarından, şerit tam-genişlik v-yükseklik."""
    H=W=hann=prev_mg=None; prev_any=False; strips=[]; vs=[]
    for f in frame_paths:
        img = rd(f)
        if img is None: continue
        if H is None:
            H, W = img.shape[:2]; hann = cv2.createHanningWindow((W, H), cv2.CV_32F); ref = round(SLIT_FRAC*H)
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); gf = g.astype(np.float32)
        m = tophat(g); mdil = cv2.dilate(m, np.ones((11,11), np.uint8))
        mg = gf.copy(); mg[mdil==0] = 0.0
        dy = 0.0
        if prev_mg is not None and bool(mdil.any()) and prev_any:
            (_, dy), _ = cv2.phaseCorrelate(prev_mg*hann, mg*hann)
        prev_mg = mg; prev_any = bool(mdil.any())
        v = int(round(abs(dy)))
        if v < VMIN or v > VMAX: continue
        strip = img[ref:ref+v, :].copy()
        if strip.shape[0] > 0: strips.append(strip); vs.append(v)
    if not strips: return None, 0, 0
    return np.vstack(strips), len(strips), int(np.median(vs))

def extract_frames(video, start_s, end_s, fdir):
    fdir.mkdir(parents=True, exist_ok=True)
    existing = sorted(glob.glob(str(fdir/"f_*.png")))
    if existing: return existing
    cmd = [FFMPEG, "-y", "-ss", str(start_s), "-t", str(end_s-start_s), "-i", video,
           "-vf", f"fps={FPS},scale=-2:480", "-q:v", "2", str(fdir/"f_%05d.png")]
    subprocess.run(cmd, check=True, capture_output=True)
    return sorted(glob.glob(str(fdir/"f_*.png")))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="run")
    ap.add_argument("--only", type=int, default=None, help="sadece bu idx")
    a = ap.parse_args()
    meta = {int(it["idx"]): it["path"] for it in json.loads(Path(META).read_text(encoding="utf-8"))}
    run_yol1 = load_yol1()
    base = Path(r"E:\MITAS\OCR-worktree\out") / f"yol_test_{a.tag}"
    cmp = base / "_compare"; cmp.mkdir(parents=True, exist_ok=True)
    summary = []
    jobs = [j for j in JOBS if (a.only is None or j[0] == a.only)]
    for idx, short, seg, s0, s1 in jobs:
        video = meta[idx]; tag = f"{idx}_{short}_{seg}"; jd = base / tag
        rec = {"idx": idx, "film": short, "seg": seg, "tc": f"{s0}-{s1}s", "video_ok": Path(video).exists()}
        try:
            frames = extract_frames(video, s0, s1, jd/"frames")
            rec["frames"] = len(frames)
            # YOL 2
            m2, n2, v2 = yol2_slitscan(frames)
            if m2 is not None:
                wr(jd/"yol2_master.png", m2); wr(cmp/f"{tag}_YOL2.png", m2)
                rec["yol2"] = {"w": int(m2.shape[1]), "h": int(m2.shape[0]), "strips": n2, "median_v": v2}
            else:
                rec["yol2"] = {"empty": True}
            # YOL 1
            res = run_yol1(frame_paths=frames, output_dir=str(jd/"yol1"), max_frames=1500)
            comp = rd(res.composite_path)
            if comp is not None:
                wr(cmp/f"{tag}_YOL1.png", comp)
                rec["yol1"] = {"w": int(comp.shape[1]), "h": int(comp.shape[0]),
                               "composite": str(res.composite_path)}
            print(f"[OK] {tag}: frames={rec['frames']} yol2={rec.get('yol2')} yol1={rec.get('yol1')}", flush=True)
        except Exception as e:
            rec["error"] = repr(e)
            print(f"[ERR] {tag}: {e!r}", flush=True)
        summary.append(rec)
    (base/"_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsummary -> {base/'_summary.json'}  ({len(summary)} iş)")

if __name__ == "__main__":
    main()
