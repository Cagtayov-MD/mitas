"""db_compose v2 — FOOTAGE-GATE'li. KANITLANDI: credit = (ultra_flat>0.5 üniform-zemin) VE (text_rows>=1 yazı).
Footage (dokulu, düşük ultra_flat) REDDEDİLİR. Kredi kareleri grupla -> scroll=slitscan / static=kart.
text-over-footage (üniform zemin yok) bu kapıdan geçmez (o ayrı=fiso işi) — ama clean-bg krediler kurtulur.
Çıktı: db_masters_v2/<film>/<seg>/master.png
"""
import sys, glob, json, argparse, importlib.util
from pathlib import Path
import numpy as np, cv2
spec=importlib.util.spec_from_file_location("fp",r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py")
fp=importlib.util.module_from_spec(spec); sys.modules["fp"]=fp; spec.loader.exec_module(fp)
sys.stdout.reconfigure(encoding="utf-8")
DB=Path(r"F:\REPO_GitHub\DATABASE"); OUT=Path(r"E:\MITAS\OCR-worktree\db_masters_v2")
SEGS=[("giris","entry_frames"),("cikis","exit_frames")]

def ultra_flat(g):
    s=cv2.resize(g,(256,144)).astype(np.float32); m=cv2.boxFilter(s,-1,(5,5))
    v=np.clip(cv2.boxFilter(s*s,-1,(5,5))-m*m,0,None); return float((v<6).mean())
def text_rows(g):
    md=cv2.dilate(fp.tophat(g),np.ones((3,3),np.uint8)); n,_,st,_=cv2.connectedComponentsWithStats(md,8); H,W=g.shape; comps=[]
    for i in range(1,n):
        x,y,w,h,a=st[i]
        if 7<=h<=60 and w>=16 and 1.2<=w/max(h,1)<=30 and a>=35: comps.append((y+h/2.,h,w))
    if not comps: return 0
    comps.sort(); rows=[[comps[0]]]
    for c in comps[1:]:
        if abs(c[0]-rows[-1][-1][0])<=max(9,rows[-1][-1][1]*0.8): rows[-1].append(c)
        else: rows.append([c])
    return sum(1 for r in rows if len(r)>=2 or any(c[2]>=W*0.14 for c in r))
def gate(g):
    uf=ultra_flat(g);
    if not (0.5<uf<0.99): return False,uf,0
    tr=text_rows(g); return (tr>=2),uf,tr

def compose2(frames):
    keep=[]; tr_of={}
    for i,f in enumerate(frames):
        g=cv2.cvtColor(fp.rd(f),cv2.COLOR_BGR2GRAY); ok,uf,tr=gate(g)
        if ok: keep.append(i); tr_of[i]=tr
    if not keep: return None,{"kept":0,"runs":0}
    runs=[]; cur=[keep[0]]
    for i in keep[1:]:
        if i-cur[-1]<=3: cur.append(i)
        else: runs.append((cur[0],cur[-1])); cur=[i]
    runs.append((cur[0],cur[-1]))
    blocks=[]; man=[]
    for a,b in runs:
        rf=frames[a:b+1]
        blk=fp.slitscan(rf,False) if len(rf)>=3 else None     # scroll dene
        if blk is not None and blk.size and blk.shape[0]>=60:
            blocks.append(blk); man.append({"run":[a,b],"kind":"scroll","h":int(blk.shape[0])}); continue
        # static / kısa -> en-yazılı karenin text-band'i (kart)
        bf=max(rf,key=lambda f:text_rows(cv2.cvtColor(fp.rd(f),cv2.COLOR_BGR2GRAY)))
        bimg=fp.rd(bf); bm=fp.tophat(cv2.cvtColor(bimg,cv2.COLOR_BGR2GRAY)); tb=fp.text_band(bm)
        if tb: c=bimg[max(0,tb[0]-fp.PAD):min(bimg.shape[0],tb[1]+fp.PAD),:]; blocks.append(c); man.append({"run":[a,b],"kind":"card","h":int(c.shape[0])})
    if not blocks: return None,{"kept":len(keep),"runs":len(runs),"blocks":0}
    W=max(b.shape[1] for b in blocks)
    norm=[cv2.copyMakeBorder(b,0,0,0,W-b.shape[1],cv2.BORDER_CONSTANT,value=(0,0,0)) if b.shape[1]<W else b for b in blocks]
    sep=[];
    for b in norm: sep.append(b); sep.append(np.zeros((12,W,3),np.uint8))
    return np.vstack(sep[:-1]),{"kept":len(keep),"runs":len(runs),"blocks":len(blocks),"man":man}

def run_film(film_sub):
    fd=[d for d in DB.iterdir() if film_sub.lower() in d.name.lower()]
    if not fd: print("film yok:",film_sub); return
    fd=fd[0]; print(f"\n### {fd.name}")
    for seg,sub in SEGS:
        frames=sorted(glob.glob(str(fd/sub/"*.png")))
        if not frames: continue
        master,info=compose2(frames)
        od=OUT/fp.safe(fd.name)/seg; od.mkdir(parents=True,exist_ok=True)
        if master is not None:
            fp.wr(od/"master.png",master); print(f"  {seg}: {len(frames)} kare -> kept={info['kept']} runs={info['runs']} blocks={info.get('blocks')} master={[int(master.shape[1]),int(master.shape[0])]}")
        else: print(f"  {seg}: {len(frames)} kare -> kredi-kare yok / boş ({info})")
        (od/"manifest.json").write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--films",default="ACEMİLER,ACI ÇİKOLATA"); a=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    for f in a.films.split(","): run_film(f.strip())
