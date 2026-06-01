"""20260531_0410 — FISO: footage'tan yazi izolasyonu KATMANI (madde 3, Katman 2).
qwen YOK: bekci kararini tester_v2 manifestinden okur. tester/ frame'lerini (480) reuse.
  - bg=solid run  -> v2 ile BIREBIR (fp.slitscan / v2.split_cards aynen) = regresyon yok.
  - bg=footage run -> IZOLASYON:
       scroll -> slit-scan + her-serit (top-hat yazi-maske AND median-sabit-grafik HARIC)
       cards  -> v2.split_cards + her karta top-hat yazi-maske
Cikti: tester_fiso/ (v2/v3 DOKUNULMAZ). Sadece secilen film listesi.
"""
import sys, json, glob, argparse, importlib.util
from pathlib import Path
import cv2, numpy as np
spec=importlib.util.spec_from_file_location("fp",r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py"); fp=importlib.util.module_from_spec(spec); sys.modules["fp"]=fp; spec.loader.exec_module(fp)
s2=importlib.util.spec_from_file_location("v2",r"E:\MITAS\OCR-worktree\py\20260530_2350_full_pipeline_v2.py"); v2=importlib.util.module_from_spec(s2); sys.modules["v2"]=v2; s2.loader.exec_module(v2)
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

V1=Path(r"E:\MITAS\OCR-worktree\tester"); V2=Path(r"E:\MITAS\OCR-worktree\tester_v2"); OUT=Path(r"E:\MITAS\OCR-worktree\tester_fiso")
FIXED_THR=22; TH_ISO=18; MIN_COV=0.010   # izolasyon yazi-kapsamasi bunun altinda -> RAW slit'e fallback (icerik kaybetme)

def median_fixed(rf):
    """run boyu temporal median -> parlak SABIT grafik (foto/logo). scroll'da yazi yikanir, median=grafik.
    Sadece BUYUK bilesenleri tut (foto kutusu/logo); kucuk benekleri eleme. Yoksa None."""
    if len(rf)<5: return None
    gr=np.median(np.stack([cv2.cvtColor(fp.rd(f),cv2.COLOR_BGR2GRAY).astype(np.float32) for f in rf]),axis=0)
    if float(gr.mean())>=130: return None   # ACIK zemin -> 'parlak=sabit-grafik' mantigi tum bg'yi yakalar -> iptal
    fx=(gr>FIXED_THR).astype(np.uint8)
    fx=cv2.morphologyEx(fx,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8)); fx=cv2.dilate(fx,np.ones((5,5),np.uint8),1)
    n,lab,stats,_=cv2.connectedComponentsWithStats(fx,8)
    H,W=fx.shape; out=np.zeros_like(fx); big=0
    for i in range(1,n):
        if stats[i,cv2.CC_STAT_AREA] > 0.01*H*W:   # >%1 alan = sabit grafik blogu
            out[lab==i]=1; big+=1
    return out if big>0 else None

def isolate_mask(g, fixedrows):
    """top-hat parlak yazi-maskesi (- sabit-grafik bolgesi)."""
    m=(fp.tophat(g)>TH_ISO).astype(np.uint8)
    if fixedrows is not None: m[fixedrows>0]=0
    m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8)); m=cv2.dilate(m,np.ones((2,2),np.uint8),1)
    return m

def slitscan_iso(rf):
    """footage scroll: slit-scan + her serit izole (yazi tut, footage+sabit-grafik at)."""
    fixed=median_fixed(rf)
    H=W=hann=prev=None; pa=False; strips=[]; ref=None; txt=0; tot=0
    for f in rf:
        img=fp.rd(f)
        if H is None: H,W=img.shape[:2]; hann=cv2.createHanningWindow((W,H),cv2.CV_32F); ref=round(fp.SLIT_FRAC*H)
        g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY); gf=g.astype(np.float32)
        mt=fp.tophat(g); md=cv2.dilate(mt,np.ones((11,11),np.uint8)); mg=gf.copy(); mg[md==0]=0.0
        dy=0.0
        if prev is not None and bool(md.any()) and pa: (_,dy),_=cv2.phaseCorrelate(prev*hann,mg*hann)
        prev=mg; pa=bool(md.any()); v=int(round(abs(dy)))
        if v<fp.VMIN or v>fp.VMAX: continue
        s=img[ref:ref+v,:].copy()
        if s.shape[0]<=0: continue
        sg=cv2.cvtColor(s,cv2.COLOR_BGR2GRAY)
        fr=fixed[ref:ref+v,:] if fixed is not None else None
        m=isolate_mask(sg,fr)
        txt+=int((m>0).sum()); tot+=int(m.size)
        s[m==0]=0; strips.append(s)
    cov=(txt/tot) if tot else 0.0
    return (np.vstack(strips) if strips else None), cov

def cards_iso(rf):
    """footage cards: v2.split_cards + her karta top-hat izolasyon."""
    out=[]
    for c in v2.split_cards(rf):
        if c is None or not c.size: continue
        g=cv2.cvtColor(c,cv2.COLOR_BGR2GRAY); m=isolate_mask(g,None)
        ci=np.zeros_like(c); ci[m>0]=c[m>0]; out.append(ci)
    return out

def process_fiso(film, seg):
    man=V2/film/seg/"manifest.json"; fdir=V1/film/seg/"frames"
    if not man.exists() or not fdir.exists(): return {"err":"v2-manifest/frames yok"}
    d=json.loads(man.read_text(encoding="utf-8")); frames=sorted(glob.glob(str(fdir/"f_*.png")))
    blocks=[]; mani=[]
    for r in d["runs"]:
        if "kind" not in r: continue   # skip (bekci-footage/no-text/empty) -> v2 ile ayni, atla
        a,b=r["run"]; rf=frames[a:b+1]; bg=(r.get("pred") or {}).get("background"); kind=r["kind"]
        if bg=="footage":
            if kind=="scroll":
                blk,cov=slitscan_iso(rf)
                if blk is None or cov<MIN_COV:   # izolasyon yazi bulamadi (koyu-yazi/zayif) -> RAW slit (icerik KAYBETME)
                    blk=fp.slitscan(rf,False); tag="footage-scroll-RAWfallback"
                else: tag="footage-scroll-iso"
                if blk is not None and blk.size: blocks.append(blk); mani.append({"run":[a,b],"path":tag,"cov":round(cov,4),"h":int(blk.shape[0])})
            else:   # footage STATIC -> v2.split_cards (IZOLE ETME; orijinal kart okunur kalir) + v2 fallback
                cards=v2.split_cards(rf)
                if not cards:
                    sh=[(fp.sharpv(cv2.cvtColor(fp.rd(x),cv2.COLOR_BGR2GRAY)),x) for x in rf]
                    _,bestf=max(sh,key=lambda t:t[0]); bimg=fp.rd(bestf); bm=fp.tophat(cv2.cvtColor(bimg,cv2.COLOR_BGR2GRAY)); tb=fp.text_band(bm)
                    if tb is not None: cards=[bimg[max(0,tb[0]-fp.PAD):min(bimg.shape[0],tb[1]+fp.PAD),:]]
                for c in cards:
                    if c is not None and c.size: blocks.append(c)
                mani.append({"run":[a,b],"path":"footage-cards-v2","n":len(cards)})
        else:   # solid (veya bg yok) -> v2 BIREBIR
            if kind=="scroll":
                blk=fp.slitscan(rf,False)
                if blk is not None and blk.size: blocks.append(blk); mani.append({"run":[a,b],"path":"solid-v2-scroll","h":int(blk.shape[0])})
            else:
                cards=v2.split_cards(rf)
                if not cards:   # v2 FALLBACK (madde 8): 0 kart -> tek en-keskin kart (yoksa fiso v2'den AZ verir = regresyon)
                    sh=[(fp.sharpv(cv2.cvtColor(fp.rd(x),cv2.COLOR_BGR2GRAY)),x) for x in rf]
                    _,bestf=max(sh,key=lambda t:t[0]); bimg=fp.rd(bestf); bm=fp.tophat(cv2.cvtColor(bimg,cv2.COLOR_BGR2GRAY)); tb=fp.text_band(bm)
                    if tb is not None: cards=[bimg[max(0,tb[0]-fp.PAD):min(bimg.shape[0],tb[1]+fp.PAD),:]]
                for c in cards:
                    if c is not None and c.size: blocks.append(c)
                mani.append({"run":[a,b],"path":"solid-v2-cards","n":len(cards)})
    od=OUT/film/seg; od.mkdir(parents=True,exist_ok=True)
    if blocks:
        W=max(x.shape[1] for x in blocks)
        norm=[cv2.copyMakeBorder(x,0,0,0,W-x.shape[1],cv2.BORDER_CONSTANT,value=(0,0,0)) if x.shape[1]<W else x for x in blocks]
        sep=[]
        for x in norm: sep.append(x); sep.append(np.zeros((12,W,3),np.uint8))
        master=np.vstack(sep[:-1]); fp.wr(od/"master.png",master); ms=[int(master.shape[1]),int(master.shape[0])]
    else: ms=None
    (od/"manifest.json").write_text(json.dumps({"blocks":len(blocks),"master":ms,"runs":mani},ensure_ascii=False,indent=2),encoding="utf-8")
    return {"blocks":len(blocks),"master":ms}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--idxs",default=""); a=ap.parse_args()
    meta=json.loads(Path(fp.META).read_text(encoding="utf-8")); idx2name={int(it["idx"]):Path(it["path"]).name for it in meta}
    want=[int(x) for x in a.idxs.split(",") if x.strip()]
    summ=[]
    for idx in want:
        nm=idx2name.get(idx)
        if not nm: print(f"[idx yok] {idx}"); continue
        film=fp.safe(Path(nm).stem)
        for seg in ["giris","cikis"]:
            try:
                r=process_fiso(film,seg); r.update(idx=idx,film=film,seg=seg)
                print(f"[OK] idx{idx} {film[:36]}/{seg}: blocks={r.get('blocks')} master={r.get('master')}",flush=True)
            except Exception as e:
                r={"idx":idx,"film":film,"seg":seg,"err":repr(e)}; print(f"[ERR] idx{idx} {film[:36]}/{seg}: {e!r}",flush=True)
            summ.append(r)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"_SUMMARY.json").write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"\nFISO SUMMARY -> {OUT/'_SUMMARY.json'}")

if __name__=="__main__": main()
