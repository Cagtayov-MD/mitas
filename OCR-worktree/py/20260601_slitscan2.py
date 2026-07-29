"""slitscan2 — dikiş glitch'ini (yırtık/çift satır) azaltan gelişmiş slit-scan.
Eski: v=int(round(abs(dy))) -> tek-kare sapması + yuvarlama kayması -> satır yırtılır/tekrarlanır.
Yeni: İŞARETLİ dy + MEDYAN-FİLTRE (tek-kare sapmasını siler) + FLOAT-biriktirme (kayma yok).
Test: ACEMİLER çıkış crawl'ında eski vs yeni master.
"""
import sys, glob, importlib.util
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
fp = importlib.util.module_from_spec(importlib.util.spec_from_file_location("fp", str(__import__("pathlib").Path(__import__("os").environ.get("MITAS_PROJECT_ROOT") or r"E:\MITAS") / "OCR-worktree" / "py" / "20260530_1744_full_pipeline.py")))
sys.modules["fp"] = fp; fp.__spec__.loader.exec_module(fp)

def row_sig(img):
    """satır-başı yazı yoğunluğu (tophat) — büyük dikey kaymayı hizalamak için."""
    return fp.tophat(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)).sum(axis=1).astype(np.float32)

def best_shift(sa, sb, maxs=160):
    """B, A'nın 's' px YUKARI kaymış hali: sb[y]~sa[y+s]. En iyi s>=0 ve güveni döndür."""
    n = len(sa); best, bv = 0, -1.0
    for s in range(0, min(maxs, n-40)):
        a, b = sa[s:], sb[:n-s]
        v = float(np.dot(a, b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-6))
        if v > bv: bv, best = v, s
    return best, bv

def shift_in_range(sa, sb, lo, hi):
    """kaymayı [lo,hi] aralığında ara — aliasing (yanlış satır-katına kilitlenme) engellenir."""
    n = len(sa); best, bv = lo, -1.0
    for s in range(max(1, lo), min(hi, n-40)):
        a, b = sa[s:], sb[:n-s]
        v = float(np.dot(a, b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-6))
        if v > bv: bv, best = v, s
    return best, bv

def textbot(im, H):
    """yazı bölgesinin en alt satırını döndür (tophat → renk-bağımsız).
    Karenin altındaki siyah margin'i atlamak için slitscan2'de kullanılır."""
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) if im.ndim == 3 else im
    th = fp.tophat(g)
    rows = (th > 0).sum(axis=1)
    br = np.where(rows > 3)[0]
    return int(br[-1]) + 1 if len(br) else H

def slitscan2(paths):
    """HİZALAMA-MOZAİĞİ + ZAMAN-TUTARLILIĞI: ardışık kareleri hizala, sadece YENİ giren alt-şeridi ekle.
    Kayma scroll hızının MEDYANINA yakın zorlanır -> periyodik kredi satırlarında aliasing yırtığı OLMAZ.
    FIX-B: şerit frame-altından değil YAZI-BÖLGESİNİN altından alınır (siyah margin atlanır)."""
    imgs = [fp.rd(p) for p in paths]
    H, W = imgs[0].shape[:2]
    sigs = [row_sig(im) for im in imgs]
    # pass 1: serbest kayma -> scroll hızı medyanı
    raw = [best_shift(sigs[k-1], sigs[k]) for k in range(1, len(imgs))]
    speeds = sorted(s for s, c in raw if c > 0.4 and s > 2)
    med = speeds[len(speeds)//2] if speeds else 0
    # pass 2: kaymayı medyana yakın zorla
    canvas = imgs[0][:textbot(imgs[0], H)].copy()
    for k in range(1, len(imgs)):
        if med >= 2:
            s, conf = shift_in_range(sigs[k-1], sigs[k], int(med*0.6), int(med*1.5)+1)
            if conf < 0.30: s = int(round(med))          # güven düşükse beklenen hızı kullan
        else:
            s, conf = best_shift(sigs[k-1], sigs[k])
            if s <= 1 or conf < 0.30: continue
        s = min(max(s, 1), H)
        yb = textbot(imgs[k], H); y0 = max(0, yb - s)
        strip = imgs[k][y0:yb, :]
        if strip.shape[0] > 0: canvas = np.vstack([canvas, strip])
    return canvas

if __name__ == "__main__":
    DB = r"F:\REPO_GitHub\DATABASE\ACEMİLER ÇETESİ 1974-0205-1-0000-90-1\exit_frames"
    frames = sorted(glob.glob(DB+r"\*.png"))
    ps = np.load(r"E:\MITAS\OCR-worktree\clip_probe\_REVIEW15\ACEMİLER_ÇETESİ_1974_0205_1_0000_90_1__cikis.npy")
    idx = [i for i in range(len(ps)) if ps[i] >= 0.5]
    runf = [frames[i] for i in idx]
    print(f"ACEMİLER çıkış crawl: {len(runf)} kare ({idx[0]}-{idx[-1]})")
    old = fp.slitscan(runf, False); new = slitscan2(runf)
    out = Path(r"E:\MITAS\OCR-worktree\clip_probe\_slitscan_test"); out.mkdir(parents=True, exist_ok=True)
    if old is not None: fp.wr(out/"ESKI.png", old); print(f"ESKİ : {old.shape[1]}x{old.shape[0]}")
    if new is not None: fp.wr(out/"YENI.png", new); print(f"YENİ : {new.shape[1]}x{new.shape[0]}")
    print(f"-> {out}")
