"""KANIT: CLIP-seçili giriş kredi karelerini OneOCR ile oku -> gerçekten kadro çıkıyor mu?
credit_prob.npy'den kredi-koşularını al, her koşuda en yüksek skorlu kareyi OneOCR'la oku, satırları topla.
EĞİTİM YOK. Sadece CLIP-tespit + OneOCR-oku zincirinin sonu görülsün.
"""
import sys, glob, importlib.util
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
spec = importlib.util.spec_from_file_location("rw", r"E:\MITAS\OCR-worktree\py\20260531_2330_read_3way.py")
rw = importlib.util.module_from_spec(spec); sys.modules["rw"] = rw; spec.loader.exec_module(rw)
fp = rw.fp; fold = rw.fold; read_oneocr = rw.read_oneocr
def tr_upper(s): return s.replace("i", "İ").upper()

DB = Path(r"F:\REPO_GitHub\DATABASE")
PROBE = Path(r"E:\MITAS\OCR-worktree\clip_probe")
film, seg, sub, thr = "ACEMİLER", "giris", "entry_frames", 0.4
fd = [d for d in DB.iterdir() if film.lower() in d.name.lower()][0]
safe = "".join(c if c.isalnum() else "_" for c in fd.name)[:40]
frames = sorted(glob.glob(str(fd/sub/"*.png")))
probs = np.load(PROBE/safe/seg/"credit_prob.npy")
idx = np.where(probs >= thr)[0]
runs = []; cur = [int(idx[0])]
for j in idx[1:]:
    j = int(j)
    if j - cur[-1] <= 3: cur.append(j)
    else: runs.append(cur); cur = [j]
runs.append(cur)
runs = [r for r in runs if len(r) >= 2]
read_idx = [int(i) for i in idx]   # koşu başına tek kare DEĞİL -> TÜM kredi kareleri (kart-içi çeşitlilik kaybolmasın)
print(f"{fd.name} / {seg}: {len(runs)} koşu, {len(read_idx)} kredi-karesi (thr={thr}) OneOCR okuyor...\n")
seen = {}; order = []
for i in read_idx:
    lines = read_oneocr(fp.rd(frames[i]))
    new = []
    for ln in lines:
        fk = fold(ln)
        if fk and fk not in seen: seen[fk] = ln; order.append(fk); new.append(ln)
    if new: print(f"  #{i:>3} (p={probs[i]:.2f}) YENİ: {new}")
print("\n=== GİRİŞ JENERİĞİ — CLIP-tespit + OneOCR-oku (Türkçe-BÜYÜK) ===")
out = [tr_upper(seen[fk]) for fk in order]
for t in out: print("  ", t)
od = PROBE/safe/seg; (od/"giris_okundu_UPPER.txt").write_text("\n".join(out), encoding="utf-8")
print(f"\n-> {od/'giris_okundu_UPPER.txt'}")
