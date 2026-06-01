"""slitscan3 — ALIASING'i öldüren zaman-tutarlı hizalama.
Sorun: kredi satırları eşit aralıklı -> row-korelasyon yanlış KAT'a kilitlenir (1 satır kayma) -> yırtık bant.
Çözüm: kaymayı scroll hızının MEDYANINA yakın aralıkta ara (med*0.6 .. med*1.5). Aliasing imkansız.
Test: ACI ÇİKOLATA çıkış (cache idx) -> eski slitscan2 vs yeni slitscan3.
"""
import sys, glob, json, importlib.util
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
fp = importlib.util.module_from_spec(importlib.util.spec_from_file_location("fp", r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py"))
sys.modules["fp"] = fp; fp.__spec__.loader.exec_module(fp)
sl = importlib.util.module_from_spec(importlib.util.spec_from_file_location("sl", r"E:\MITAS\OCR-worktree\py\20260601_slitscan2.py"))
sys.modules["sl"] = sl; sl.__spec__.loader.exec_module(sl)

def shift_in_range(sa, sb, lo, hi):
    n = len(sa); best, bv = lo, -1.0
    for s in range(max(1, lo), min(hi, n-40)):
        a, b = sa[s:], sb[:n-s]
        v = float(np.dot(a, b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-6))
        if v > bv: bv, best = v, s
    return best, bv

def slitscan3(paths):
    imgs = [fp.rd(p) for p in paths]; H, W = imgs[0].shape[:2]
    sigs = [sl.row_sig(im) for im in imgs]
    # pass 1: serbest kayma -> hız medyanı
    raw = [sl.best_shift(sigs[k-1], sigs[k]) for k in range(1, len(imgs))]
    speeds = sorted(s for s, c in raw if c > 0.4 and s > 2)
    med = speeds[len(speeds)//2] if speeds else 0
    # pass 2: kaymayı medyana yakın zorla (aliasing yok)
    canvas = imgs[0].copy()
    for k in range(1, len(imgs)):
        if med >= 2:
            lo, hi = int(med*0.6), int(med*1.5)+1
            s, conf = shift_in_range(sigs[k-1], sigs[k], lo, hi)
            if conf < 0.30: s = int(round(med))     # güven düşükse beklenen hızı kullan
        else:
            s, conf = sl.best_shift(sigs[k-1], sigs[k])
            if s <= 1 or conf < 0.30: continue
        s = min(max(s, 1), H)
        canvas = np.vstack([canvas, imgs[k][H-s:H, :]])
    return canvas, med

if __name__ == "__main__":
    film = "ACI_ÇİKOLATA_1992_0478_1_0000_00_1"
    cache = json.loads(Path(rf"E:\MITAS\OCR-worktree\clip_pipeline50\_CACHE\{film}__cikis.json").read_text(encoding="utf-8"))
    idx = cache["idx"]
    D = r"F:\REPO_GitHub\DATABASE\ACI ÇİKOLATA 1992-0478-1-0000-00-1\exit_frames"
    frames = sorted(glob.glob(D+r"\*.png"))
    # en büyük bitişik run = scroll
    runs = [[idx[0]]]
    for j in idx[1:]:
        (runs[-1].append(j) if j-runs[-1][-1] <= 3 else runs.append([j]))
    run = max(runs, key=len)
    print(f"ACI ÇİKOLATA çıkış: {len(idx)} kredi, en büyük run {run[0]}-{run[-1]} ({len(run)} kare)")
    rf = [frames[i] for i in run]
    old = sl.slitscan2(rf)
    new, med = slitscan3(rf)
    out = Path(r"E:\MITAS\OCR-worktree\clip_probe\_slitscan_test"); out.mkdir(parents=True, exist_ok=True)
    if old is not None: fp.wr(out/"ACI_ESKI.png", old); print(f"ESKİ(slitscan2): {old.shape[1]}x{old.shape[0]}")
    if new is not None: fp.wr(out/"ACI_YENI.png", new); print(f"YENİ(slitscan3): {new.shape[1]}x{new.shape[0]}  (hız medyanı={med}px)")
    print(f"-> {out}")
