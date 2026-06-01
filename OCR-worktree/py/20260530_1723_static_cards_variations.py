"""20260530_1723 — STATİK KART yakalama, TÜM VARYASYONLAR (KARAR 2 / açılışlar).
YOL 2 (scroll) açılışlarda çöp veriyordu çünkü bunlar statik kart. Doğru yöntem:
held-run (metin var + dy≈0) → kart. Kart görüntüsü 3 varyasyon:
  V1 sharpest    = run'ın en keskin tek karesi
  V2 median      = run boyunca per-piksel median (sahne/insan hareketi siler, statik yazı kalır)
  V3 med+unsharp = median + keskinleştirme
Her film için 3 master + sayılar. "max verim" = en çok+temiz kart hangi varyasyonda.
"""
import sys, glob, json
from pathlib import Path
import cv2, numpy as np

BASE = r"E:\MITAS\OCR-worktree\out\yol_test_20260530_1645"
OUT  = Path(r"E:\MITAS\OCR-worktree\out\static_cards_var_20260530_1723")
JOBS = ["22_yabandan_giris","15_pilkington_giris","28_altin_yumruk_giris",
        "38_sansimi_seveyim_giris","30_dert_bende_giris"]
STATIC_DY, TB_SWAP, MIN_HOLD, THK, THT, PAD = 1.5, 20.0, 5, 15, 22, 8

def rd(p): return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
def wr(p, i):
    ok, b = cv2.imencode(".png", i)
    if ok: b.tofile(str(p))
def tophat(g):
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (THK, 5))
    th = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, k)
    _, m = cv2.threshold(th, THT, 255, cv2.THRESH_BINARY); return m
def has_text(m):
    n,_,st,_ = cv2.connectedComponentsWithStats(cv2.dilate(m,np.ones((3,3),np.uint8)),8); c=0
    for l in range(1,n):
        h=st[l,cv2.CC_STAT_HEIGHT]; w=st[l,cv2.CC_STAT_WIDTH]
        if 5<=h<=52 and w>=40 and w/max(1,h)>=1.5: c+=1
    return c>=1
def sharp(g): return float(cv2.Laplacian(g, cv2.CV_64F).var())
def text_band(m):
    rows = np.where(m.sum(axis=1) > 0)[0]
    return (int(rows.min()), int(rows.max())) if rows.size else None
def unsharp(img):
    blur = cv2.GaussianBlur(img,(0,0),1.0)
    return cv2.addWeighted(img,1.6,blur,-0.6,0)

def extract(frames):
    H=W=hann=prev_mg=None; prev_any=False; prev_g=prev_m=None; runs=[]; cur=None
    for i,f in enumerate(frames):
        img=rd(f)
        if img is None: continue
        if H is None: H,W=img.shape[:2]; hann=cv2.createHanningWindow((W,H),cv2.CV_32F)
        g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY); gf=g.astype(np.float32)
        m=tophat(g); text=has_text(m)
        md=cv2.dilate(m,np.ones((11,11),np.uint8)); mg=gf.copy(); mg[md==0]=0.0
        dy=0.0
        if prev_mg is not None and bool(md.any()) and prev_any:
            (_,dy),_=cv2.phaseCorrelate(prev_mg*hann, mg*hann)
        tb=0.0
        if prev_g is not None and prev_m is not None:
            reg=(m>0)|(prev_m>0)
            if reg.any(): tb=float(np.mean(np.abs(g[reg].astype(np.float32)-prev_g[reg].astype(np.float32))))
        prev_mg=mg; prev_any=bool(md.any()); prev_g=g; prev_m=m
        held=text and abs(dy)<STATIC_DY; swap=tb>TB_SWAP
        if cur is not None and (not held or swap): runs.append(cur); cur=None
        if held:
            if cur is None: cur=[]
            cur.append((i,sharp(g),img,m))
    if cur is not None: runs.append(cur)
    return [r for r in runs if len(r)>=MIN_HOLD]

def card_band(img, m):
    tb=text_band(m)
    if tb is None: return None
    y0=max(0,tb[0]-PAD); y1=min(img.shape[0],tb[1]+PAD)
    return img[y0:y1,:]

def dedup(cards):
    out=[]
    for c in cards:
        if out:
            a=cv2.cvtColor(out[-1]["band"],cv2.COLOR_BGR2GRAY).astype(np.float32)
            b=cv2.cvtColor(c["band"],cv2.COLOR_BGR2GRAY).astype(np.float32)
            if abs(a.shape[0]-b.shape[0])<=6:
                hh=min(a.shape[0],b.shape[0]); ww=min(a.shape[1],b.shape[1])
                r=cv2.matchTemplate(a[:hh,:ww],b[:hh,:ww],cv2.TM_CCOEFF_NORMED)
                if float(r.max())>=0.95: continue
        out.append(c)
    return out

def stack(bands, W):
    if not bands: return np.zeros((10,W,3),np.uint8)
    out=[]
    for b in bands: out.append(b); out.append(np.zeros((10,b.shape[1],3),np.uint8))
    return np.vstack(out[:-1])

def main():
    OUT.mkdir(parents=True, exist_ok=True); summary=[]
    for job in JOBS:
        fd=Path(BASE)/job/"frames"; frames=sorted(glob.glob(str(fd/"f_*.png")))
        if not frames: summary.append({"job":job,"err":"no frames"}); continue
        runs=extract(frames)
        # her run icin 3 varyasyon kart
        v1=[]; v2=[]; v3=[]
        for r in runs:
            idx,_,bestimg,bestm=max(r,key=lambda t:t[1])           # en keskin
            b1=card_band(bestimg,bestm)
            stackimgs=np.stack([t[2] for t in r],0)
            med=np.median(stackimgs,0).astype(np.uint8)             # temporal median
            b2=card_band(med,bestm); b3=card_band(unsharp(med),bestm)
            if b1 is not None: v1.append({"band":b1})
            if b2 is not None: v2.append({"band":b2})
            if b3 is not None: v3.append({"band":b3})
        W=rd(frames[0]).shape[1]
        d1,d2,d3=dedup(v1),dedup(v2),dedup(v3)
        wr(OUT/f"{job}__V1_sharpest.png", stack([c["band"] for c in d1],W))
        wr(OUT/f"{job}__V2_median.png",   stack([c["band"] for c in d2],W))
        wr(OUT/f"{job}__V3_med_unsharp.png", stack([c["band"] for c in d3],W))
        rec={"job":job,"frames":len(frames),"held_runs":len(runs),
             "cards_V1":len(d1),"cards_V2":len(d2),"cards_V3":len(d3)}
        summary.append(rec); print(f"[OK] {job}: runs={len(runs)} cards V1/V2/V3={len(d1)}/{len(d2)}/{len(d3)}", flush=True)
    (OUT/"_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("OUT ->", OUT)

if __name__=="__main__":
    main()
