"""20260531_0210 — TANI: run-bazli MASKELI (yazi) dy vs FULL-FRAME dy olc.
Amac (madde 1 guvenlik kaniti): sahte-S (scroll icinde donmus kart) ile
gercek-kart S'yi maskeli-dy AYIRT EDEBILIYOR mu? Kod yazmadan ONCE dogrula.
Beklenti: SENIN_HIKAYEN sahte-S ~ R (yuksek masked-dy) ; SON METRO kart-S << SCROLL_DY (dusuk).
"""
import sys, glob, importlib.util
from pathlib import Path
import cv2, numpy as np
FP=r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py"
spec=importlib.util.spec_from_file_location("fp",FP); fp=importlib.util.module_from_spec(spec)
sys.modules["fp"]=fp; spec.loader.exec_module(fp)
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
V1=Path(r"E:\MITAS\OCR-worktree\tester")

def masked_dy_series(frames):
    """slitscan ile AYNI maskeli-dy: tophat->dilate->mask->phaseCorrelate."""
    H=W=hann=prev=None; pa=False; out=[]
    for f in frames:
        img=fp.rd(f)
        if img is None: continue
        if H is None: H,W=img.shape[:2]; hann=cv2.createHanningWindow((W,H),cv2.CV_32F)
        g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY).astype(np.float32)
        m=fp.tophat(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)); md=cv2.dilate(m,np.ones((11,11),np.uint8))
        mg=g.copy(); mg[md==0]=0.0
        dy=0.0
        if prev is not None and bool(md.any()) and pa:
            (_,dy),_=cv2.phaseCorrelate(prev*hann,mg*hann)
        prev=mg; pa=bool(md.any()); out.append(abs(dy))
    return np.array(out) if out else np.array([0.0])

def full_dy_series(frames):
    H=W=hann=prev=None; out=[]
    for f in frames:
        g=cv2.cvtColor(fp.rd(f),cv2.COLOR_BGR2GRAY).astype(np.float32)
        if H is None: H,W=g.shape; hann=cv2.createHanningWindow((W,H),cv2.CV_32F)
        dy=0.0
        if prev is not None: (_,dy),_=cv2.phaseCorrelate(prev*hann,g*hann)
        prev=g; out.append(abs(dy))
    return np.array(out) if out else np.array([0.0])

def report(film, seg, runs, note=""):
    fdir=V1/film/seg/"frames"; frames=sorted(glob.glob(str(fdir/"f_*.png")))
    if not frames: print(f"[frames yok] {film}/{seg}"); return
    print(f"\n=== {film[:40]}/{seg} {note} ===  (toplam {len(frames)} kare)")
    print(f"  {'run':>14} {'lab':>3} {'n':>4} {'masked-dy med':>14} {'p75':>6} {'full-dy med':>12}")
    for a,b,lab in runs:
        rf=frames[a:b+1]
        md=masked_dy_series(rf); fd=full_dy_series(rf)
        print(f"  [{a:>4},{b:>4}] {lab:>3} {len(rf):>4} {np.median(md):>14.2f} {np.percentile(md,75):>6.2f} {np.median(fd):>12.2f}")

# --- SENIN HIKAYEN cikis: sahte-S (scroll icinde) ile R'leri kiyasla ---
SH="evoArcadmin_SİNEMA_FİLM_2024-1315-1-0000-90-1-SENİN_HİKAYEN"
report(SH,"cikis",[
    (42,69,"S?"),(269,289,"S?"),(319,339,"S?"),        # erken kartlar (gercek mi scroll mu?)
    (372,455,"R"),(456,484,"S*"),(485,558,"R"),(559,585,"S*"),  # R, sahte-S, R, sahte-S
    (666,685,"S*"),(686,764,"R"),(978,1135,"R")],
    "sahte-S(*) vs R bekleniyor: ikisi de YUKSEK")

# --- SON METRO cikis: gercek 22-kart S'i kiyasla ---
SM="evoArcadmin_COZUMLEMEV2S27_1980-0186-1-0000-00-1-SON_METRO"
report(SM,"cikis",[(16,356,"S")], "gercek 22-kart: DUSUK bekleniyor")

# --- DRAKULA giris: gercek statik kart (kontrol) ---
DR="evoArcadmin_COZUMLEMEV2S17_1960-0046-1-0000-00-1-DRAKULA_NIN_GELİNLERİ"
report(DR,"giris",[(0,40,"S")], "gercek statik kart: DUSUK bekleniyor")

print("\nSCROLL_DY=2.5  STATIC_DY=1.5  (esik referansi)")
