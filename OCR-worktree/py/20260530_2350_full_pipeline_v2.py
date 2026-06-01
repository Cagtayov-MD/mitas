"""20260530_2350 — PIPELINE v2: madde 8 (statik ÇOK-KART bölme) — REGRESYON-GÜVENLİ.
v1 pipeline'ı import eder, SADECE statik branch'i değiştirir (scroll branch = fp.slitscan, AYNEN).
Kareler v1'den okunur (tester/<film>/<seg>/frames), çıktı tester_v2/ (v1 silinmez → kıyas).
Statik run -> split_cards (KARAR-2: text-gap + TB_SWAP swap -> sub-kart -> en keskin text-band -> dedup).
"""
import sys, json, glob, argparse, importlib.util, urllib.request
from pathlib import Path
import cv2, numpy as np

FP_PATH = r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py"
spec = importlib.util.spec_from_file_location("fp", FP_PATH)
fp = importlib.util.module_from_spec(spec); sys.modules["fp"] = fp; spec.loader.exec_module(fp)

V1BASE  = Path(r"E:\MITAS\OCR-worktree\tester")
OUTBASE = Path(r"E:\MITAS\OCR-worktree\tester_v2")
TB_SWAP, MIN_CARD, PAD = 20.0, 3, 8

def split_cards(frames):
    """KARAR-2 kart-ayırma: yazı kaybolur→geri gelir (gap) ya da yazı-bölgesi diff sıçrar (swap) = yeni kart."""
    sub=[]; cur=[]; pg=pm=None
    for f in frames:
        img=fp.rd(f)
        if img is None: continue
        g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY); m=fp.tophat(g); txt=fp.has_text(m)
        tb=0.0
        if pg is not None and pm is not None:
            reg=(m>0)|(pm>0)
            if reg.any(): tb=float(np.mean(np.abs(g[reg].astype(np.float32)-pg[reg].astype(np.float32))))
        pg=g; pm=m
        if cur and ((not txt) or tb>TB_SWAP): sub.append(cur); cur=[]
        if txt: cur.append((fp.sharpv(g), img, m))
    if cur: sub.append(cur)
    sub=[c for c in sub if len(c)>=MIN_CARD]
    bands=[]
    for c in sub:
        _,bimg,bm=max(c,key=lambda t:t[0]); tbnd=fp.text_band(bm)
        if tbnd is None: continue
        y0=max(0,tbnd[0]-PAD); y1=min(bimg.shape[0],tbnd[1]+PAD); bands.append(bimg[y0:y1,:])
    out=[]   # bitişik near-aynı kart dedup (içerik NCC)
    for b in bands:
        if out:
            a=cv2.cvtColor(out[-1],cv2.COLOR_BGR2GRAY).astype(np.float32); bb=cv2.cvtColor(b,cv2.COLOR_BGR2GRAY).astype(np.float32)
            if abs(a.shape[0]-bb.shape[0])<=6:
                hh=min(a.shape[0],bb.shape[0]); ww=min(a.shape[1],bb.shape[1])
                if float(cv2.matchTemplate(a[:hh,:ww],bb[:hh,:ww],cv2.TM_CCOEFF_NORMED).max())>=0.95: continue
        out.append(b)
    return out

def process_v2(framedir, outdir):
    frames=sorted(glob.glob(str(framedir/"f_*.png")))
    if not frames: return {"err":"no frames"}
    outdir.mkdir(parents=True, exist_ok=True)
    runs=fp.split_runs(frames)   # AYNI dy-split
    blocks=[]; man=[]
    for (a,b,lab) in runs:
        rf=frames[a:b+1]
        sh=[(fp.sharpv(cv2.cvtColor(fp.rd(f),cv2.COLOR_BGR2GRAY)),f) for f in rf]
        _,bestf=max(sh,key=lambda t:t[0]); bimg=fp.rd(bestf); bm=fp.tophat(cv2.cvtColor(bimg,cv2.COLOR_BGR2GRAY))
        if not fp.has_text(bm): man.append({"run":[a,b],"lab":lab,"skip":"no-text"}); continue
        try: pred=fp.qwen(bestf)
        except Exception as e: pred={"err":str(e)[:30]}
        if str(pred.get("is_credit")).lower()!="true":
            man.append({"run":[a,b],"lab":lab,"skip":"bekci-footage","pred":pred}); continue
        if lab=="R":   # SCROLL = AYNEN v1 (fp.slitscan, lumakey off)
            blk=fp.slitscan(rf, False)
            if blk is not None and blk.size: blocks.append(blk); man.append({"run":[a,b],"lab":lab,"kind":"scroll","h":int(blk.shape[0]),"pred":pred})
            else: man.append({"run":[a,b],"lab":lab,"skip":"empty-recon","pred":pred})
        else:          # STATIC = madde 8: kartlara böl
            cards=split_cards(rf); fb=False
            if not cards:   # FALLBACK: 0 kart çıkarsa v1 gibi tek-en-keskin kart (ASLA v1'den az verme)
                tb=fp.text_band(bm)
                if tb is not None:
                    cards=[bimg[max(0,tb[0]-PAD):min(bimg.shape[0],tb[1]+PAD), :]]; fb=True
            for cb in cards:
                if cb is not None and cb.size: blocks.append(cb)
            man.append({"run":[a,b],"lab":lab,"kind":"cards","n_cards":len(cards),"fallback":fb,"pred":pred})
    if blocks:
        W=max(b.shape[1] for b in blocks)
        norm=[cv2.copyMakeBorder(b,0,0,0,W-b.shape[1],cv2.BORDER_CONSTANT,value=(0,0,0)) if b.shape[1]<W else b for b in blocks]
        sep=[]
        for b in norm: sep.append(b); sep.append(np.zeros((12,W,3),np.uint8))
        master=np.vstack(sep[:-1]); fp.wr(outdir/"master.png",master); ms=[int(master.shape[1]),int(master.shape[0])]
    else: ms=None
    (outdir/"manifest.json").write_text(json.dumps({"blocks":len(blocks),"master":ms,"runs":man},ensure_ascii=False,indent=2),encoding="utf-8")
    return {"blocks":len(blocks),"master":ms}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--idxs",default=""); a=ap.parse_args()
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    meta=json.loads(Path(fp.META).read_text(encoding="utf-8")); idx2name={int(it["idx"]):Path(it["path"]).name for it in meta}
    want=[int(x) for x in a.idxs.split(",") if x.strip()] or sorted(fp.WIN.keys())  # boş → TÜM set
    try: urllib.request.urlopen(urllib.request.Request(fp.OLLAMA,json.dumps({"model":fp.MODEL,"prompt":"ok","stream":False,"keep_alive":"15m"}).encode(),{"Content-Type":"application/json"}),timeout=600).read()
    except Exception as e: print("warmup:",e)
    summary=[]
    for idx in want:
        name=idx2name.get(idx)
        if not name: print(f"[idx yok] {idx}"); continue
        film=fp.safe(Path(name).stem)
        for seg in ["giris","cikis"]:
            fdir=V1BASE/film/seg/"frames"
            if not fdir.exists(): print(f"[frames yok] {film}/{seg}"); continue
            try:
                r=process_v2(fdir, OUTBASE/film/seg); r.update(idx=idx,film=film,seg=seg)
                print(f"[OK] {film}/{seg}: blocks={r.get('blocks')} master={r.get('master')}",flush=True)
            except Exception as e:
                r={"idx":idx,"film":film,"seg":seg,"err":repr(e)}; print(f"[ERR] {film}/{seg}: {e!r}",flush=True)
            summary.append(r)
    OUTBASE.mkdir(parents=True,exist_ok=True)
    (OUTBASE/"_SUMMARY.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"\nv2 SUMMARY -> {OUTBASE/'_SUMMARY.json'}")

if __name__=="__main__": main()
