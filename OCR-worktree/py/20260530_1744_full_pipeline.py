"""20260530_1744 — FINAL PIPELINE (ilk büyük test). E:\\filmtest\\aaaa tüm videolar.
Her (film, segment) için:
  ffmpeg kare -> dy timeline-split (STATIC/SCROLL/CUT bloklar)
  -> her blokta: text-gate (top-hat) -> BEKÇİ (qwen2.5vl: jenerik mi/footage mı)
     -> credit ise: SCROLL->maskeli-hız slit-scan (footage+bright ise lumakey-pre) ; STATIC->en keskin kart
     -> footage/credit-değil bloklar ATLANIR
  -> credit bloklarını sırayla DİZ -> segment master.
Giriş master'ı sadece credit varsa üretilir (yoksa girişsiz, sadece çıkış) -> kurala uyar.
Çıktı: OCR-worktree/tester/<film>/<seg>/master.png + manifest.json
"""
import sys, json, glob, base64, time, subprocess, argparse, urllib.request, re
from pathlib import Path
import cv2, numpy as np

FFMPEG = r"E:\MITAS\tools\ffmpeg-shared\ffmpeg-8.1.1-full_build-shared\bin\ffmpeg.exe"
META   = r"E:\MITAS\_jenerik_analysis\dense5_metadata.json"
VIDDIR = r"E:\filmtest\aaaa"
OUTBASE= Path(r"E:\MITAS\OCR-worktree\tester")
OLLAMA = "http://localhost:11434/api/generate"; MODEL="qwen2.5vl:7b"
FPS=5; SLIT_FRAC=0.55; VMIN=1; VMAX=40; THK=15; THT=22
STATIC_DY=1.5; SCROLL_DY=2.5; CUT=40.0; MIN_HOLD=5; PAD=8; LUMA_THR=150

# idx -> (giris_start, giris_end, cikis_start, cikis_end) saniye  (make_v2 segments'tan; giriş=en uzun start*, çıkış=end* birliği)
WIN={1:(0,100,5270,5325),2:(0,195,5490,5600),3:(0,130,4800,4850),4:(20,95,675,715),5:(0,100,4865,4910),
6:(0,85,5580,5909),7:(0,80,4690,4725),8:(0,130,5440,5475),9:(0,125,6100,6230),10:(70,230,5520,5710),
11:(0,110,5575,5610),12:(0,125,5460,5605),13:(0,110,7415,7510),14:(65,150,2945,3010),15:(0,65,5815,5888),
16:(0,115,6365,6412),17:(0,120,5360,5455),18:(265,325,5610,5750),19:(0,60,7000,7390),20:(0,115,5035,5155),
21:(20,85,5445,5975),22:(0,210,8015,8140),23:(0,65,4585,4615),24:(0,100,4930,4950),25:(30,135,5210,5240),
26:(0,70,4820,4878),27:(0,90,5460,5520),28:(0,225,4685,4800),29:(0,255,6960,7320),30:(0,120,4830,4845),
31:(0,115,5745,5970),32:(0,45,6985,7300),33:(20,310,7225,7440),34:(0,150,6155,6410),35:(0,40,8640,8745),
36:(0,45,6795,7235),37:(0,90,5785,6060),38:(0,235,5110,5260),39:(0,55,4995,5205),40:(50,155,5315,5570),
41:(0,100,6455,6590),42:(80,215,5805,6035),43:(0,165,5435,5580),44:(0,90,5055,5142),45:(20,110,5330,5430),
46:(0,30,6355,6465),47:(0,90,2930,2980),48:(0,130,6925,6995),49:(605,735,8050,8120),50:(620,755,8300,8390),
51:(0,85,1430,1495),52:(0,85,6410,6500),53:(0,95,8535,8820),54:(0,45,6080,6290)}

PROMPT=("You see ONE still frame from a film/TV. Reply ONE JSON: "
 '"is_credit": true/false (true if it is part of a credits/title/caption sequence; false if plain footage with no overlaid text), '
 '"background":"solid"|"footage", "text_color":"bright"|"dark"|"none". JSON only.')

def rd(p): return cv2.imdecode(np.fromfile(str(p),np.uint8),cv2.IMREAD_COLOR)
def wr(p,i):
    ok,b=cv2.imencode(".png",i)
    if ok: b.tofile(str(p))
def safe(s): return re.sub(r"[^\w\-]+","_",s)[:70].strip("_")
def tophat(g):
    k=cv2.getStructuringElement(cv2.MORPH_RECT,(THK,5)); th=cv2.morphologyEx(g,cv2.MORPH_TOPHAT,k)
    _,m=cv2.threshold(th,THT,255,cv2.THRESH_BINARY); return m
def has_text(m):
    n,_,st,_=cv2.connectedComponentsWithStats(cv2.dilate(m,np.ones((3,3),np.uint8)),8); c=0
    for l in range(1,n):
        h=st[l,cv2.CC_STAT_HEIGHT]; w=st[l,cv2.CC_STAT_WIDTH]
        if 5<=h<=52 and w>=40 and w/max(1,h)>=1.5: c+=1
    return c>=1
def sharpv(g): return float(cv2.Laplacian(g,cv2.CV_64F).var())
def text_band(m):
    r=np.where(m.sum(axis=1)>0)[0]; return (int(r.min()),int(r.max())) if r.size else None
def luma_key(img):
    g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY); o=np.zeros_like(img); o[g>LUMA_THR]=img[g>LUMA_THR]; return o
def qwen(path):
    pl={"model":MODEL,"prompt":PROMPT,"stream":False,"format":"json","keep_alive":"15m",
        "options":{"temperature":0},"images":[base64.b64encode(Path(path).read_bytes()).decode()]}
    req=urllib.request.Request(OLLAMA,json.dumps(pl).encode(),{"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=600) as r: return json.loads(json.loads(r.read()).get("response","{}"))

def extract(video,s0,s1,fdir):
    fdir.mkdir(parents=True,exist_ok=True)
    ex=sorted(glob.glob(str(fdir/"f_*.png")))
    if ex: return ex
    subprocess.run([FFMPEG,"-y","-ss",str(s0),"-t",str(s1-s0),"-i",video,
        "-vf",f"fps={FPS},scale=-2:480","-q:v","2",str(fdir/"f_%05d.png")],capture_output=True)
    return sorted(glob.glob(str(fdir/"f_*.png")))

def split_runs(frames):
    """full-frame dy -> STATIC/SCROLL/CUT runs."""
    H=W=hann=prev=None; ady=[]
    for f in frames:
        g=cv2.cvtColor(rd(f),cv2.COLOR_BGR2GRAY).astype(np.float32)
        if H is None: H,W=g.shape; hann=cv2.createHanningWindow((W,H),cv2.CV_32F)
        dy=0.0
        if prev is not None: (_,dy),_=cv2.phaseCorrelate(prev*hann,g*hann)
        prev=g; ady.append(abs(dy))
    ady=np.array(ady); iscut=ady>CUT
    sm=np.array([np.median(np.clip(ady,0,CUT)[max(0,i-2):i+3]) for i in range(len(ady))])
    lab=[]; st="S"
    for i,v in enumerate(sm):
        if iscut[i]: lab.append("C"); continue
        if v<STATIC_DY: st="S"
        elif v>SCROLL_DY: st="R"
        lab.append(st)
    runs=[];s=0
    for i in range(1,len(lab)+1):
        if i==len(lab) or lab[i]!=lab[s]: runs.append([s,i-1,lab[s]]); s=i
    return [r for r in runs if r[2]!="C" and (r[1]-r[0]+1)>=MIN_HOLD]

def slitscan(frames, keyed):
    H=W=hann=prev=None;pa=False;strips=[]
    for f in frames:
        img=rd(f)
        if keyed: img=luma_key(img)
        if H is None: H,W=img.shape[:2]; hann=cv2.createHanningWindow((W,H),cv2.CV_32F); ref=round(SLIT_FRAC*H)
        g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY); gf=g.astype(np.float32)
        m=tophat(g); md=cv2.dilate(m,np.ones((11,11),np.uint8)); mg=gf.copy(); mg[md==0]=0.0
        dy=0.0
        if prev is not None and bool(md.any()) and pa: (_,dy),_=cv2.phaseCorrelate(prev*hann,mg*hann)
        prev=mg; pa=bool(md.any()); v=int(round(abs(dy)))
        if v<VMIN or v>VMAX: continue
        s=img[ref:ref+v,:].copy()
        if s.shape[0]>0: strips.append(s)
    return np.vstack(strips) if strips else None

def process(video, s0, s1, outdir):
    frames=extract(video,s0,s1,outdir/"frames")
    if not frames: return {"err":"no frames"}
    runs=split_runs(frames)
    blocks=[]; man=[]
    for (a,b,lab) in runs:
        rf=frames[a:b+1]
        sh=[(sharpv(cv2.cvtColor(rd(f),cv2.COLOR_BGR2GRAY)),f) for f in rf]
        _,bestf=max(sh,key=lambda t:t[0]); bimg=rd(bestf); bg=cv2.cvtColor(bimg,cv2.COLOR_BGR2GRAY); bm=tophat(bg)
        if not has_text(bm): man.append({"run":[a,b],"lab":lab,"skip":"no-text"}); continue
        try: pred=qwen(bestf)
        except Exception as e: pred={"err":str(e)[:30]}
        if str(pred.get("is_credit")).lower()!="true":
            man.append({"run":[a,b],"lab":lab,"skip":"bekci-footage","pred":pred}); continue
        if lab=="R":
            keyed = False   # LUMAKEY-PRE KAPATILDI (2026-05-30): göz text_color GÜVENİLMEZ (kendi kuralım) +
                            # renkli/mid-luma yazıyı soluyor (bizim_evin mor yazı faded oldu). Düz slit okunur.
            blk=slitscan(rf,keyed); kind="scroll"
        else:
            tb=text_band(bm); blk=bimg[max(0,tb[0]-PAD):min(bimg.shape[0],tb[1]+PAD),:] if tb else None; kind="card"
        if blk is not None and blk.size:
            blocks.append(blk); man.append({"run":[a,b],"lab":lab,"kind":kind,"pred":pred,"h":int(blk.shape[0])})
        else:
            man.append({"run":[a,b],"lab":lab,"skip":"empty-recon","pred":pred})
    if blocks:
        W=max(b.shape[1] for b in blocks)
        norm=[cv2.copyMakeBorder(b,0,0,0,W-b.shape[1],cv2.BORDER_CONSTANT,value=(0,0,0)) if b.shape[1]<W else b for b in blocks]
        sep=[];
        for b in norm: sep.append(b); sep.append(np.zeros((12,W,3),np.uint8))
        master=np.vstack(sep[:-1]); wr(outdir/"master.png",master)
        msize=[int(master.shape[1]),int(master.shape[0])]
    else:
        msize=None
    (outdir/"manifest.json").write_text(json.dumps({"blocks":len(blocks),"master":msize,"runs":man},ensure_ascii=False,indent=2),encoding="utf-8")
    return {"blocks":len(blocks),"master":msize}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--only",type=int); ap.add_argument("--seg",choices=["giris","cikis"])
    a=ap.parse_args()
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    meta=json.loads(Path(META).read_text(encoding="utf-8")); bystem={Path(it["path"]).name:int(it["idx"]) for it in meta}
    # warmup qwen
    try:
        urllib.request.urlopen(urllib.request.Request(OLLAMA,json.dumps({"model":MODEL,"prompt":"ok","stream":False,"keep_alive":"15m"}).encode(),{"Content-Type":"application/json"}),timeout=600).read()
    except Exception as e: print("warmup:",e)
    vids=sorted(Path(VIDDIR).glob("*"))
    summary=[]
    for v in vids:
        if v.name=="tester.mp4" or v.suffix.lower() not in (".mp4",".mxf",".mkv",".avi",".mov",".ts"): continue
        idx=bystem.get(v.name)
        if idx is None or idx not in WIN: continue
        if a.only and idx!=a.only: continue
        gs,ge,cs,ce=WIN[idx]; film=safe(v.stem)
        for seg,(s0,s1) in [("giris",(gs,ge)),("cikis",(cs,ce))]:
            if a.seg and seg!=a.seg: continue
            od=OUTBASE/film/seg
            try:
                r=process(str(v),s0,s1,od); r.update(idx=idx,film=film,seg=seg,tc=f"{s0}-{s1}")
                print(f"[OK] {film}/{seg}: blocks={r.get('blocks')} master={r.get('master')}",flush=True)
            except Exception as e:
                r={"idx":idx,"film":film,"seg":seg,"err":repr(e)}; print(f"[ERR] {film}/{seg}: {e!r}",flush=True)
            summary.append(r)
    OUTBASE.mkdir(parents=True,exist_ok=True)
    (OUTBASE/"_SUMMARY.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"\nSUMMARY -> {OUTBASE/'_SUMMARY.json'} ({len(summary)} iş)")

if __name__=="__main__":
    main()
