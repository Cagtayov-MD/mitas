"""20260531_0245 — MASKELI-DY yeniden-siniflandirma + scroll-span birlestirme (madde 1+9).
KONTROLLU: ayri cikti tester_mdy/ (Sonnet'in tester_v3/'une DOKUNMA). v2'yi import eder.
v1/v2 frame'lerini (tester/) reuse. Sadece 3 test filmi.

ALGORITMA (olculmus ayrim: gercek scroll masked-dy>=2.5 ; her-sabit <=0.2):
  1) fp.split_runs (full-frame, AYNEN) -> runs.
  2) her run icin medyan MASKELI-dy hesapla -> eff='R' if med>=SCROLL_DY else 'S'.
     (footage-ustu-duran-yazi 'R' iken dusuk masked-dy -> 'S'e DEMOTE = madde 9.)
  3) her eff-S run: kart-sayisi (v2.split_cards). kind='pause' if (kisa & <=1 kart) else 'cards'.
  4) blok kur: ardisik R + ARADAKI pause'lari KOPRULE -> span'i TEK fp.slitscan (kesintisiz).
     'cards' (gercek kart dizisi) span'i KIRAR -> ayri tutulur (SON METRO 22 kart KORUNUR).
"""
import sys, json, glob, importlib.util
from pathlib import Path
import cv2, numpy as np
FP=r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py"
V2P=r"E:\MITAS\OCR-worktree\py\20260530_2350_full_pipeline_v2.py"
spec=importlib.util.spec_from_file_location("fp",FP); fp=importlib.util.module_from_spec(spec); sys.modules["fp"]=fp; spec.loader.exec_module(fp)
s2=importlib.util.spec_from_file_location("v2",V2P); v2=importlib.util.module_from_spec(s2); sys.modules["v2"]=v2; s2.loader.exec_module(v2)
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

V1BASE=Path(r"E:\MITAS\OCR-worktree\tester")
V2BASE=Path(r"E:\MITAS\OCR-worktree\tester_v2")
OUT=Path(r"E:\MITAS\OCR-worktree\tester_mdy")
PAUSE_MAX=45   # kare; bu kadar kisa + <=1 kart = 'pause' (koprulenebilir)

def masked_dy_full(frames):
    """slitscan ile AYNI maskeli-dy; dy[i] = i-1->i hareketi (dy[0]=0)."""
    H=W=hann=prev=None; pa=False; out=[]
    for f in frames:
        img=fp.rd(f)
        if H is None: H,W=img.shape[:2]; hann=cv2.createHanningWindow((W,H),cv2.CV_32F)
        g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY).astype(np.float32)
        m=fp.tophat(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)); md=cv2.dilate(m,np.ones((11,11),np.uint8)); mg=g.copy(); mg[md==0]=0.0
        dy=0.0
        if prev is not None and bool(md.any()) and pa: (_,dy),_=cv2.phaseCorrelate(prev*hann,mg*hann)
        prev=mg; pa=bool(md.any()); out.append(abs(dy))
    return np.array(out) if out else np.array([0.0])

def card_band(frames_sub):
    """tek-en-keskin kart text-band (v1 statik mantigi) -> 1 blok."""
    sh=[(fp.sharpv(cv2.cvtColor(fp.rd(f),cv2.COLOR_BGR2GRAY)),f) for f in frames_sub]
    _,bestf=max(sh,key=lambda t:t[0]); bimg=fp.rd(bestf); bm=fp.tophat(cv2.cvtColor(bimg,cv2.COLOR_BGR2GRAY))
    tb=fp.text_band(bm)
    if tb is None: return None
    return bimg[max(0,tb[0]-fp.PAD):min(bimg.shape[0],tb[1]+fp.PAD),:]

def process_mdy(framedir, outdir):
    frames=sorted(glob.glob(str(framedir/"f_*.png")))
    if not frames: return {"err":"no frames"}
    outdir.mkdir(parents=True, exist_ok=True)
    runs=fp.split_runs(frames)
    mdy=masked_dy_full(frames)
    R=[]
    for (a,b,lab) in runs:
        med=float(np.median(mdy[a:b+1])) if b>=a else 0.0
        eff="R" if med>=fp.SCROLL_DY else "S"
        rec={"a":a,"b":b,"lab":lab,"eff":eff,"mdy":round(med,2)}
        if eff=="S":
            sub=frames[a:b+1]; nf=b-a+1
            nc=len(v2.split_cards(sub))
            rec["nc"]=nc; rec["kind"]="pause" if (nf<=PAUSE_MAX and nc<=1) else "cards"
        R.append(rec)
    # bekci/no-text filtresi: her R icin en-keskin karede qwen (v1/v2 ile ayni kapi)
    def keep(rec):
        sub=frames[rec["a"]:rec["b"]+1]
        sh=[(fp.sharpv(cv2.cvtColor(fp.rd(f),cv2.COLOR_BGR2GRAY)),f) for f in sub]
        _,bestf=max(sh,key=lambda t:t[0]); bm=fp.tophat(cv2.cvtColor(fp.rd(bestf),cv2.COLOR_BGR2GRAY))
        if not fp.has_text(bm): return False,{"skip":"no-text"}
        try: pred=fp.qwen(bestf)
        except Exception as e: pred={"err":str(e)[:30]}
        if str(pred.get("is_credit")).lower()!="true": return False,{"skip":"bekci-footage","pred":pred}
        return True,{"pred":pred}
    blocks=[]; man=[]; i=0; n=len(R)
    while i<n:
        rec=R[i]
        if rec["eff"]=="R":
            # scroll span: ardisik R + aradaki 'pause'lari koprule (sonra R geliyorsa)
            end=i; k=i
            while k<n:
                if R[k]["eff"]=="R": end=k; k+=1
                elif R[k].get("kind")=="pause":
                    m=k
                    while m<n and R[m]["eff"]=="S" and R[m].get("kind")=="pause": m+=1
                    if m<n and R[m]["eff"]=="R": k=m   # koprule
                    else: break
                else: break
            a0=R[i]["a"]; b0=R[end]["b"]
            ok,info=keep({"a":a0,"b":b0})
            if ok:
                blk=fp.slitscan(frames[a0:b0+1], False)
                if blk is not None and blk.size:
                    blocks.append(blk); man.append({"span":[a0,b0],"kind":"scroll-merged","runs":end-i+1,"h":int(blk.shape[0]),**info})
                else: man.append({"span":[a0,b0],"skip":"empty-recon",**info})
            else: man.append({"span":[a0,b0],**info})
            i=end+1
        else:
            sub=frames[rec["a"]:rec["b"]+1]
            ok,info=keep(rec)
            if not ok: man.append({"run":[rec["a"],rec["b"]],**info}); i+=1; continue
            if rec.get("kind")=="cards":
                cards=v2.split_cards(sub)
                if not cards:
                    cb=card_band(sub)
                    if cb is not None: cards=[cb]
                for cb in cards:
                    if cb is not None and cb.size: blocks.append(cb)
                man.append({"run":[rec["a"],rec["b"]],"kind":"cards","n":len(cards),**info})
            else:  # pause ama KOPRULENMEDI -> v2.split_cards (v2 ile OZDES kalsin)
                cards=v2.split_cards(sub)
                if not cards:
                    cb=card_band(sub)
                    if cb is not None: cards=[cb]
                for cb in cards:
                    if cb is not None and cb.size: blocks.append(cb)
                man.append({"run":[rec["a"],rec["b"]],"kind":"pause-card","n":len(cards),"mdy":rec["mdy"],**info})
        # i zaten artti (R dalinda end+1, S dalinda asagida)
        if rec["eff"]!="R": i+=1
    if blocks:
        W=max(b.shape[1] for b in blocks)
        norm=[cv2.copyMakeBorder(b,0,0,0,W-b.shape[1],cv2.BORDER_CONSTANT,value=(0,0,0)) if b.shape[1]<W else b for b in blocks]
        sep=[]
        for b in norm: sep.append(b); sep.append(np.zeros((12,W,3),np.uint8))
        master=np.vstack(sep[:-1]); fp.wr(outdir/"master.png",master); ms=[int(master.shape[1]),int(master.shape[0])]
    else: ms=None
    (outdir/"manifest.json").write_text(json.dumps({"blocks":len(blocks),"master":ms,"runs":man,"classify":R},ensure_ascii=False,indent=2),encoding="utf-8")
    return {"blocks":len(blocks),"master":ms}

TESTS=[("evoArcadmin_SİNEMA_FİLM_2024-1315-1-0000-90-1-SENİN_HİKAYEN","cikis"),
       ("evoArcadmin_COZUMLEMEV2S27_1980-0186-1-0000-00-1-SON_METRO","cikis"),
       ("evoArcadmin_COZUMLEMEV2S27_2000-0433-1-0000-90-1-X-MEN","cikis")]

def main():
    try: urllib_warm()
    except Exception: pass
    for film,seg in TESTS:
        fdir=V1BASE/film/seg/"frames"
        if not fdir.exists(): print(f"[frames yok] {film}/{seg}"); continue
        r=process_mdy(fdir, OUT/film/seg)
        # v2 ile kiyas
        v2m=V2BASE/film/seg/"manifest.json"; v2b=v2h=None
        if v2m.exists():
            d=json.loads(v2m.read_text(encoding="utf-8")); v2b=d.get("blocks"); v2h=(d.get("master") or [None,None])[1]
        print(f"[mdy] {film[:34]:34}/{seg}: blocks={r.get('blocks')} master={r.get('master')}  | v2: blocks={v2b} H={v2h}",flush=True)

def urllib_warm():
    import urllib.request
    urllib.request.urlopen(urllib.request.Request(fp.OLLAMA,json.dumps({"model":fp.MODEL,"prompt":"ok","stream":False,"keep_alive":"15m"}).encode(),{"Content-Type":"application/json"}),timeout=600).read()

if __name__=="__main__": main()
