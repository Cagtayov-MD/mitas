"""20260530_1622 — Timeline splitter VIZ (matplotlib sürümü).
16:18 cv2 sürümünün temiz hali: düzgün eksenler, üst üste binmeyen etiketler, Türkçe karakter.
"""
import glob
from pathlib import Path
import numpy as np, cv2
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

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
ady=np.array(ady); is_cut=ady>CUT; sm=med(np.clip(ady,0,CUT),5); n=len(ady)

labels=[]; st="S"
for i,v in enumerate(sm):
    if is_cut[i]: labels.append("C"); continue
    if v<STATIC_TH: st="S"
    elif v>SCROLL_TH: st="R"
    labels.append(st)
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

# ---- çizim ----
col={"S":"#3fae3f","R":"#2878c8","C":"#d63030"}; nm={"S":"STATİK","R":"SCROLL","C":"CUT"}
fig,(ax1,ax2)=plt.subplots(2,1,figsize=(15,6.2),height_ratios=[3,1],sharex=True,
                           gridspec_kw={"hspace":0.12})
fig.suptitle("ANJELIK end_credits — zaman çizgisi blok ayırıcı (dy durum makinesi)",
             fontsize=13,fontweight="bold",y=0.97)
# üst: |dy|
ax1.plot(idxs, np.clip(sm,0,30), color="#444", lw=0.9)
ax1.axhline(SCROLL_TH, ls="--", c="#888", lw=0.8); ax1.text(idxs[-1],SCROLL_TH+0.3,"scroll > 2.5",ha="right",fontsize=8,color="#666")
ax1.axhline(STATIC_TH, ls="--", c="#bbb", lw=0.8); ax1.text(idxs[-1],STATIC_TH+0.3,"static < 1.3",ha="right",fontsize=8,color="#999")
cutx=[idxs[i] for i in range(n) if is_cut[i]]
ax1.plot(cutx,[29.2]*len(cutx),"v",color="#d63030",ms=6,label="cut")
ax1.set_ylim(0,30); ax1.set_ylabel("|dy|  (px/kare, clip 30)"); ax1.grid(alpha=0.25)
# gerçek scroll oku
for r in merged:
    if r[2]=="R" and (r[1]-r[0]+1)>=200:
        cx=(idxs[r[0]]+idxs[r[1]])//2
        ax1.annotate("GERÇEK SCROLL\n566–894 · 329 kare · |dy|≈9",
                     xy=(cx,9), xytext=(cx-30,21), ha="center", color="#c01010", fontsize=9,
                     arrowprops=dict(arrowstyle="->",color="#c01010",lw=1.5))
# alt: blok şeridi
for r in merged:
    ax2.barh(0, idxs[r[1]]-idxs[r[0]]+1, left=idxs[r[0]], height=1.0,
             color=col[r[2]], edgecolor="white", linewidth=0.6)
for r in merged:
    if (r[1]-r[0]+1)>=22:
        cx=(idxs[r[0]]+idxs[r[1]])/2
        ax2.text(cx,0,f"{nm[r[2]]}\n{idxs[r[0]]}-{idxs[r[1]]}",ha="center",va="center",
                 fontsize=7,color="white",fontweight="bold")
ax2.set_xlim(idxs[0],idxs[-1]); ax2.set_ylim(-0.5,0.5); ax2.set_yticks([])
ax2.set_xlabel("frame"); ax2.set_ylabel("bloklar",rotation=0,ha="right",va="center")
ax2.legend(handles=[Patch(color=col["S"],label="STATİK"),Patch(color=col["R"],label="SCROLL"),
                    Patch(color=col["C"],label="CUT")],
           ncol=3, loc="upper center", bbox_to_anchor=(0.5,-0.45), frameon=False, fontsize=9)
p=str(OUT/"20260530_1622_anjelik_timeline_mpl.png")
plt.savefig(p, dpi=150, bbox_inches="tight"); plt.close()
print(f"{len(merged)} blok -> {p}")
