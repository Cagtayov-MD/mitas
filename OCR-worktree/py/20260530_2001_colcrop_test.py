"""20260530_2001 — FIX TESTİ: yazı-sütununa kısıtlı slit-scan (split/footage-leak çözümü).
bizim_evin çıkışında: top-hat maskesini biriktir -> yazının x-sütununu [x0,x1] bul ->
şeritleri SADECE o sütundan al. Footage yarısı (sağdaki smear) düşmeli.
Eski master (tam-genişlik) ile yeni master (sütun-kısıtlı) yan yana karşılaştır.
"""
import glob
from pathlib import Path
import cv2, numpy as np

FR = r"E:\MITAS\OCR-worktree\tester\web_client_dizicag_2000-0111-0-0617-00-1-BİZİM_EVİN_HALLERİ\cikis\frames"
OUT= Path(r"E:\MITAS\OCR-worktree\out\colcrop_20260530_2001"); OUT.mkdir(parents=True, exist_ok=True)
SLIT_FRAC=0.55; VMIN=1; VMAX=40; THK=15; THT=22; STATIC_DY=1.5; SCROLL_DY=2.5; CUT=40.0; MIN_HOLD=5

def rd(p): return cv2.imdecode(np.fromfile(str(p),np.uint8),cv2.IMREAD_COLOR)
def wr(p,i):
    ok,b=cv2.imencode(".png",i)
    if ok: b.tofile(str(p))
def tophat(g):
    k=cv2.getStructuringElement(cv2.MORPH_RECT,(THK,5)); th=cv2.morphologyEx(g,cv2.MORPH_TOPHAT,k)
    _,m=cv2.threshold(th,THT,255,cv2.THRESH_BINARY); return m

def text_column(frames):
    """top-hat maskesini biriktir -> kolon profili -> yazının [x0,x1] x-aralığı."""
    acc=None
    for f in frames:
        g=cv2.cvtColor(rd(f),cv2.COLOR_BGR2GRAY); m=tophat(g).astype(np.float32)
        acc=m if acc is None else acc+m
    col=acc.sum(axis=0); k=max(5,len(col)//40)
    col=np.convolve(col,np.ones(k)/k,mode="same")
    peak=int(np.argmax(col)); thr=0.30*col[peak]
    x0=peak
    while x0>0 and col[x0]>thr: x0-=1
    x1=peak
    while x1<len(col)-1 and col[x1]>thr: x1+=1
    W=len(col); pad=int(0.02*W)
    return max(0,x0-pad), min(W, x1+pad), W

def split_runs(frames):
    H=W=hann=prev=None; ady=[]
    for f in frames:
        g=cv2.cvtColor(rd(f),cv2.COLOR_BGR2GRAY).astype(np.float32)
        if H is None: H,W=g.shape; hann=cv2.createHanningWindow((W,H),cv2.CV_32F)
        dy=0.0
        if prev is not None:(_,dy),_=cv2.phaseCorrelate(prev*hann,g*hann)
        prev=g; ady.append(abs(dy))
    ady=np.array(ady); iscut=ady>CUT
    sm=np.array([np.median(np.clip(ady,0,CUT)[max(0,i-2):i+3]) for i in range(len(ady))])
    lab=[];st="S"
    for i,v in enumerate(sm):
        if iscut[i]: lab.append("C"); continue
        if v<STATIC_DY:st="S"
        elif v>SCROLL_DY:st="R"
        lab.append(st)
    runs=[];s=0
    for i in range(1,len(lab)+1):
        if i==len(lab) or lab[i]!=lab[s]: runs.append([s,i-1,lab[s]]); s=i
    return [r for r in runs if r[2]!="C" and (r[1]-r[0]+1)>=MIN_HOLD]

def slit(frames, x0, x1):
    """sütun-kısıtlı maskeli-hız slit-scan."""
    H=W=hann=prev=None;pa=False;strips=[]
    for f in frames:
        img=rd(f);
        if H is None: H,W=img.shape[:2]; hann=cv2.createHanningWindow((W,H),cv2.CV_32F); ref=round(SLIT_FRAC*H)
        g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY); gf=g.astype(np.float32)
        m=tophat(g); md=cv2.dilate(m,np.ones((11,11),np.uint8)); mg=gf.copy(); mg[md==0]=0.0
        dy=0.0
        if prev is not None and bool(md.any()) and pa:(_,dy),_=cv2.phaseCorrelate(prev*hann,mg*hann)
        prev=mg; pa=bool(md.any()); v=int(round(abs(dy)))
        if v<VMIN or v>VMAX: continue
        s=img[ref:ref+v, x0:x1].copy()
        if s.shape[0]>0: strips.append(s)
    return np.vstack(strips) if strips else None

def build(frames, colcrop):
    runs=split_runs(frames)
    if colcrop: x0,x1,W=text_column(frames)
    else: x0,x1,W=0,rd(frames[0]).shape[1],rd(frames[0]).shape[1]
    blocks=[]
    for a,b,lab in runs:
        rf=frames[a:b+1]
        if lab=="R":
            blk=slit(rf,x0,x1)
        else:
            sh=[(cv2.Laplacian(cv2.cvtColor(rd(f),cv2.COLOR_BGR2GRAY),cv2.CV_64F).var(),f) for f in rf]
            _,bf=max(sh,key=lambda t:t[0]); img=rd(bf); m=tophat(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY))
            r=np.where(m.sum(axis=1)>0)[0]
            blk=img[max(0,r.min()-8):r.max()+8, x0:x1] if r.size else None
        if blk is not None and blk.size: blocks.append(blk)
    if not blocks: return None,(x0,x1,W)
    Wm=max(b.shape[1] for b in blocks)
    norm=[cv2.copyMakeBorder(b,0,0,0,Wm-b.shape[1],cv2.BORDER_CONSTANT,value=(0,0,0)) if b.shape[1]<Wm else b for b in blocks]
    sep=[]
    for b in norm: sep.append(b); sep.append(np.zeros((12,Wm,3),np.uint8))
    return np.vstack(sep[:-1]),(x0,x1,W)

frames=sorted(glob.glob(FR+r"\f_*.png"))
print(f"frames={len(frames)}")
old,_=build(frames, False)
new,(x0,x1,W)=build(frames, True)
if old is not None: wr(OUT/"OLD_fullwidth.png", old); print(f"OLD full-width: {old.shape[1]}x{old.shape[0]}")
if new is not None: wr(OUT/"NEW_colcrop.png", new); print(f"NEW col-crop [{x0}:{x1}] / W={W}: {new.shape[1]}x{new.shape[0]}")
print("OUT ->", OUT)
