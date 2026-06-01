"""20260530_1618 — Timeline splitter VIZ: dy egrisi + renkli blok seridi -> PNG.
16:10 splitter testinin gorsel ciktisi (matplotlib yok -> cv2 ile cizim).
Etiketler ASCII (cv2.putText Turkce harf basamaz).
"""
import glob
from pathlib import Path
import cv2, numpy as np

D = r"E:\MITAS\outputs\ocr_4films_boxtrack_20260523\items\anjelik_ve_sultan_1968_end_credits\frames"
OUT = Path(r"E:\MITAS\OCR-worktree\out"); OUT.mkdir(parents=True, exist_ok=True)
STATIC_TH, SCROLL_TH, CUT, MIN_BLOCK = 1.3, 2.5, 40.0, 8

def rd(p): return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
def med(a, k=5):
    h = k//2; return np.array([np.median(a[max(0,i-h):i+h+1]) for i in range(len(a))])

frames = sorted(glob.glob(D+r"\frame_*.png"), key=lambda p:int(Path(p).stem.split("_")[-1]))
idxs = [int(Path(p).stem.split("_")[-1]) for p in frames]
H=Wd=hann=prev=None; ady=[]
for f in frames:
    g = cv2.cvtColor(rd(f), cv2.COLOR_BGR2GRAY).astype(np.float32)
    if H is None: H,Wd=g.shape; hann=cv2.createHanningWindow((Wd,H),cv2.CV_32F)
    dy=0.0
    if prev is not None: (_,dy),_=cv2.phaseCorrelate(prev*hann, g*hann)
    prev=g; ady.append(abs(dy))
ady=np.array(ady); is_cut=ady>CUT; sm=med(np.clip(ady,0,CUT),5)

labels=[]; st="S"
for i,v in enumerate(sm):
    if is_cut[i]: labels.append("C"); continue
    if v<STATIC_TH: st="S"
    elif v>SCROLL_TH: st="R"
    labels.append(st)
# runs + kisa blok yutma + birlestir
runs=[]; s=0
for i in range(1,len(labels)+1):
    if i==len(labels) or labels[i]!=labels[s]: runs.append([s,i-1,labels[s]]); s=i
ch=True
while ch and len(runs)>1:
    ch=False
    for j,r in enumerate(runs):
        if r[2]=="C": continue
        if (r[1]-r[0]+1)<MIN_BLOCK:
            nb=runs[j-1] if j>0 else runs[j+1]; nb[0]=min(nb[0],r[0]); nb[1]=max(nb[1],r[1])
            runs.pop(j); ch=True; break
merged=[runs[0]]
for r in runs[1:]:
    if r[2]==merged[-1][2]: merged[-1][1]=r[1]
    else: merged.append(r)

# ---- cizim ----
W,Hc=1500,560; img=np.full((Hc,W,3),255,np.uint8)
mL=70; pw=W-mL-30; n=len(labels)
def fx(i): return int(mL+i*pw/max(1,n-1))
top,bot=70,300; clip=30.0
def fy(v): return int(bot-min(v,clip)/clip*(bot-top))
F=cv2.FONT_HERSHEY_SIMPLEX
col={"S":(70,175,70),"R":(205,120,40),"C":(45,45,215)}   # BGR: green / blue / red
# baslik
cv2.putText(img,"ANJELIK end_credits - timeline block splitter (dy state machine)",(mL,32),F,0.6,(0,0,0),1,cv2.LINE_AA)
# dy paneli cerceve + esikler
cv2.rectangle(img,(mL,top),(mL+pw,bot),(210,210,210),1)
for thv,txt in [(STATIC_TH,"static<1.3"),(SCROLL_TH,"scroll>2.5")]:
    y=fy(thv); cv2.line(img,(mL,y),(mL+pw,y),(180,180,180),1,cv2.LINE_AA)
    cv2.putText(img,txt,(mL+pw-90,y-3),F,0.4,(120,120,120),1,cv2.LINE_AA)
cv2.putText(img,"|dy| (px/frame, clip 30)",(mL,top-6),F,0.45,(0,0,0),1,cv2.LINE_AA)
# dy egrisi
pts=np.array([(fx(i),fy(sm[i])) for i in range(n)],np.int32)
cv2.polylines(img,[pts],False,(90,90,90),1,cv2.LINE_AA)
# cut tikleri
for i in range(n):
    if is_cut[i]: cv2.line(img,(fx(i),top),(fx(i),top+10),(45,45,215),1)
# blok seridi
ry0,ry1=340,405
for r in merged:
    cv2.rectangle(img,(fx(r[0]),ry0),(fx(r[1]),ry1),col[r[2]],-1)
cv2.rectangle(img,(mL,ry0),(mL+pw,ry1),(150,150,150),1)
cv2.putText(img,"bloklar",(mL,ry0-6),F,0.45,(0,0,0),1,cv2.LINE_AA)
# buyuk bloklara etiket
nm={"S":"STATIC","R":"SCROLL","C":"CUT"}
for r in merged:
    if (r[1]-r[0]+1)>=22:
        x=fx(r[0])+3; cv2.putText(img,f"{nm[r[2]]} {idxs[r[0]]}-{idxs[r[1]]}",(x,ry1+16),F,0.36,(0,0,0),1,cv2.LINE_AA)
# gercek scroll oku
for r in merged:
    if r[2]=="R" and (r[1]-r[0]+1)>=200:
        xc=fx((r[0]+r[1])//2); cv2.arrowedLine(img,(xc,ry1+60),(xc,ry1+8),(0,0,180),2,tipLength=0.3)
        cv2.putText(img,"GERCEK SCROLL (566-894, 329 kare, |dy|~9)",(xc-260,ry1+78),F,0.5,(0,0,180),1,cv2.LINE_AA)
# x ekseni frame tickleri
for fr in [1,200,400,600,800,idxs[-1]]:
    i=min(range(n),key=lambda k:abs(idxs[k]-fr)); x=fx(i)
    cv2.line(img,(x,bot),(x,bot+5),(0,0,0),1); cv2.putText(img,str(fr),(x-10,bot+18),F,0.4,(0,0,0),1,cv2.LINE_AA)
# legend
lx=mL; ly=Hc-22
for k,t in [("S","STATIC"),("R","SCROLL"),("C","CUT")]:
    cv2.rectangle(img,(lx,ly-10),(lx+16,ly+2),col[k],-1); cv2.putText(img,t,(lx+22,ly),F,0.45,(0,0,0),1,cv2.LINE_AA); lx+=130

p=str(OUT/"20260530_1618_anjelik_timeline.png")
ok,b=cv2.imencode(".png",img)
if ok: b.tofile(p)
print(f"{len(merged)} blok -> {p}")
