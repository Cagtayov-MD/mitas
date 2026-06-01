"""CLIP-seçili kredi karelerinden TEMİZ MASTER PNG (footage YOK).
Statik kart: tophat(yazı-maskesi) farkıyla AYNI kart tekrarını grupla -> kart başına EN-YAZILI kareyi seç -> dikey diz.
Çıktı: clip_probe/<film>/<seg>/MASTER_clip.png
"""
import sys, glob, importlib.util, argparse
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
spec = importlib.util.spec_from_file_location("fp", r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py")
fp = importlib.util.module_from_spec(spec); sys.modules["fp"] = fp; spec.loader.exec_module(fp)

DB = Path(r"F:\REPO_GitHub\DATABASE"); PROBE = Path(r"E:\MITAS\OCR-worktree\clip_probe")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", default="ACEMİLER"); ap.add_argument("--seg", default="giris")
    ap.add_argument("--sub", default="entry_frames"); ap.add_argument("--thr", type=float, default=0.4)
    ap.add_argument("--T", type=float, default=0.012); ap.add_argument("--W", type=int, default=720)
    a = ap.parse_args()
    fd = [d for d in DB.iterdir() if a.film.lower() in d.name.lower()][0]
    safe = "".join(c if c.isalnum() else "_" for c in fd.name)[:40]
    frames = sorted(glob.glob(str(fd/a.sub/"*.png")))
    probs = np.load(PROBE/safe/a.seg/"credit_prob.npy")
    idx = [int(i) for i in np.where(probs >= a.thr)[0]]
    if not idx: print("kredi-karesi yok"); return

    sigs = {}
    for i in idx:
        g = cv2.cvtColor(fp.rd(frames[i]), cv2.COLOR_BGR2GRAY)
        m = fp.tophat(g).astype(np.float32)/255.
        sigs[i] = (cv2.resize(m, (128, 72)), float(m.sum()))
    # grupla: ardışık (gap<=3) + tophat benzer (yazı değişmedi) => aynı kart
    groups = [[idx[0]]]
    for x, y in zip(idx, idx[1:]):
        d = float(np.abs(sigs[x][0]-sigs[y][0]).mean())
        if y-x <= 3 and d < a.T: groups[-1].append(y)
        else: groups.append([y])
    reps = [max(g, key=lambda i: sigs[i][1]) for g in groups]   # kart başına en-yazılı kare
    print(f"{fd.name}/{a.seg}: {len(idx)} kredi-karesi -> {len(reps)} ayrı kart")
    for g, r in zip(groups, reps):
        print(f"   kart {g[0]:>3}-{g[-1]:<3} (rep #{r}, p={probs[r]:.2f})")
    # dikey diz (tam kare, sabit genişlik)
    rows = []
    for r in reps:
        im = fp.rd(frames[r]); h = int(im.shape[0]*a.W/im.shape[1])
        rows.append(cv2.resize(im, (a.W, h)))
    sep = np.full((6, a.W, 3), 40, np.uint8)
    stack = []
    for rw in rows: stack.append(rw); stack.append(sep)
    master = np.vstack(stack[:-1])
    out = PROBE/safe/a.seg/"MASTER_clip.png"
    fp.wr(out, master)
    print(f"-> MASTER {master.shape[1]}x{master.shape[0]}  {out}")

if __name__ == "__main__":
    main()
