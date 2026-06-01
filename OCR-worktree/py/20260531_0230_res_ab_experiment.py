"""20260531_0230 — A/B DENEY: 480-slit vs NATIVE-slit (DİRİLİŞ çıkış, 1280x720 kaynak, solid-bg scroll).
TASARIM (guvenli iyilestirme):  HIZ/SINIFLANDIRMA 480-proxy'de (esikler AYNEN gecerli=regresyon yok),
ama SERIT native kareden kesilir (detay korunur). Downscale YOK -> master native genislikte, daha keskin.
Cikti: iki kirpma (ayni yazi) -> gozle kiyas.
"""
import sys, glob, json, subprocess, importlib.util
from pathlib import Path
import cv2, numpy as np
FP=r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py"
spec=importlib.util.spec_from_file_location("fp",FP); fp=importlib.util.module_from_spec(spec)
sys.modules["fp"]=fp; spec.loader.exec_module(fp)
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

meta=json.loads(Path(fp.META).read_text(encoding="utf-8")); idx2path={int(it["idx"]):it["path"] for it in meta}
IDX=50; path=idx2path[IDX]; s0,s1=8310,8387   # cikis scroll penceresi
exp=Path(r"E:\MITAS\OCR-worktree\tester_v2\_previews\diri_exp"); exp.mkdir(parents=True,exist_ok=True)

def extract(native, sub):
    d=exp/sub; d.mkdir(exist_ok=True)
    ex=sorted(glob.glob(str(d/"f_*.png")))
    if ex: return ex
    vf="fps=5" if native else "fps=5,scale=-2:480"
    subprocess.run([fp.FFMPEG,"-y","-ss",str(s0),"-t",str(s1-s0),"-i",path,"-vf",vf,"-q:v","2",str(d/"f_%05d.png")],capture_output=True)
    return sorted(glob.glob(str(d/"f_*.png")))

fr480=extract(False,"p480"); frN=extract(True,"native")
print(f"480 kare: {len(fr480)} | native kare: {len(frN)}")
if frN: print("native kare boyutu:", fp.rd(frN[0]).shape)
if fr480: print("480 kare boyutu:", fp.rd(fr480[0]).shape)

m480=fp.slitscan(fr480,False)   # MEVCUT yontem

def slitscan_native(frames):
    """v'yi 480-proxy'de olc (esikler ayni), serit native'den kes (SF ile olcekle)."""
    H=W=hann=prev=None; pa=False; strips=[]; SF=refN=None
    for f in frames:
        img=fp.rd(f); Hn,Wn=img.shape[:2]
        proxy=cv2.resize(img,(max(1,int(round(Wn*480.0/Hn))),480),interpolation=cv2.INTER_AREA)
        if H is None:
            H,W=proxy.shape[:2]; hann=cv2.createHanningWindow((W,H),cv2.CV_32F)
            SF=Hn/480.0; refN=int(round(fp.SLIT_FRAC*Hn))
        g=cv2.cvtColor(proxy,cv2.COLOR_BGR2GRAY); gf=g.astype(np.float32)
        m=fp.tophat(g); md=cv2.dilate(m,np.ones((11,11),np.uint8)); mg=gf.copy(); mg[md==0]=0.0
        dy=0.0
        if prev is not None and bool(md.any()) and pa: (_,dy),_=cv2.phaseCorrelate(prev*hann,mg*hann)
        prev=mg; pa=bool(md.any()); v=int(round(abs(dy)))
        if v<fp.VMIN or v>fp.VMAX: continue        # AYNI esikler (480 uzayinda)
        vN=int(round(v*SF))
        s=img[refN:refN+vN,:].copy()
        if s.shape[0]>0: strips.append(s)
    return np.vstack(strips) if strips else None

mN=slitscan_native(frN)
print(f"480-master: {None if m480 is None else m480.shape} | NATIVE-master: {None if mN is None else mN.shape}")

def wr(p,im): cv2.imencode(".png",im)[1].tofile(str(p))
if m480 is not None and mN is not None:
    ratio=mN.shape[0]/m480.shape[0]
    y0,y1=1200,2600
    c480=m480[y0:y1,:]                                   # 480: tam-cozunurluk kirpma (downscale YOK)
    cN=mN[int(y0*ratio):int(y1*ratio),:]                  # native: ayni icerik, daha cok piksel
    wr(exp/"A_480_crop.png",c480); wr(exp/"B_native_crop.png",cN)
    print(f"A_480_crop: {c480.shape}  | B_native_crop: {cN.shape}  (ayni yazi, B daha fazla piksel)")
    print(f"-> {exp/'A_480_crop.png'}")
    print(f"-> {exp/'B_native_crop.png'}")
