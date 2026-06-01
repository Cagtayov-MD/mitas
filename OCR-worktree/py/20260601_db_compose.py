"""20260601 — DATABASE frame'lerinden MASTER PNG (composition testi, qwen/glm YOK).
DATABASE/<film>/entry_frames (giriş) + exit_frames (çıkış) HAZIR jenerik frame'leri.
Çekirdek composition: split_runs (scroll/static) -> scroll=slitscan, static=en-keskin-kart -> diz -> master.
qwen-bekçi ATLANIR (frame'ler zaten izole jenerik). Native çöz korunur (512x288, downscale yok).
Çıktı: E:\\MITAS\\OCR-worktree\\db_masters\\<film>\\{giris,cikis}\\master.png + manifest.
Sıra: alfabetik. --start/--count ile devam; --film SUBSTR ile tek film testi.
"""
import sys, glob, json, argparse, importlib.util, time
from pathlib import Path
import cv2, numpy as np
spec=importlib.util.spec_from_file_location("fp",r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py")
fp=importlib.util.module_from_spec(spec); sys.modules["fp"]=fp; spec.loader.exec_module(fp)
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

DB=Path(r"F:\REPO_GitHub\DATABASE"); OUT=Path(r"E:\MITAS\OCR-worktree\db_masters")
SEGS=[("giris","entry_frames"),("cikis","exit_frames")]

def compose(frames):
    """fp.process'in çekirdeği — qwen YOK. split_runs -> scroll=slitscan / static=kart -> master."""
    runs=fp.split_runs(frames); blocks=[]; man=[]
    for (a,b,lab) in runs:
        rf=frames[a:b+1]
        sh=[(fp.sharpv(cv2.cvtColor(fp.rd(f),cv2.COLOR_BGR2GRAY)),f) for f in rf]
        _,bestf=max(sh,key=lambda t:t[0]); bimg=fp.rd(bestf); bm=fp.tophat(cv2.cvtColor(bimg,cv2.COLOR_BGR2GRAY))
        if not fp.has_text(bm): man.append({"run":[a,b],"lab":lab,"skip":"no-text"}); continue
        if lab=="R":
            blk=fp.slitscan(rf,False); kind="scroll"
        else:
            tb=fp.text_band(bm); blk=bimg[max(0,tb[0]-fp.PAD):min(bimg.shape[0],tb[1]+fp.PAD),:] if tb else None; kind="card"
        if blk is not None and blk.size:
            blocks.append(blk); man.append({"run":[a,b],"lab":lab,"kind":kind,"h":int(blk.shape[0])})
        else:
            man.append({"run":[a,b],"lab":lab,"skip":"empty"})
    if not blocks: return None, man
    W=max(b.shape[1] for b in blocks)
    norm=[cv2.copyMakeBorder(b,0,0,0,W-b.shape[1],cv2.BORDER_CONSTANT,value=(0,0,0)) if b.shape[1]<W else b for b in blocks]
    sep=[]
    for b in norm: sep.append(b); sep.append(np.zeros((12,W,3),np.uint8))
    return np.vstack(sep[:-1]), man

def process_film(film_dir):
    res={"film":film_dir.name}
    for seg,sub in SEGS:
        frames=sorted(glob.glob(str(film_dir/sub/"*.png")))
        od=OUT/fp.safe(film_dir.name)/seg; od.mkdir(parents=True,exist_ok=True)
        if (od/"master.png").exists():   # resume
            res[seg]={"skip":"var"}; continue
        if not frames:
            res[seg]={"frames":0}; (od/"manifest.json").write_text("[]",encoding="utf-8"); continue
        try:
            master,man=compose(frames)
            if master is not None:
                fp.wr(od/"master.png",master)
                res[seg]={"frames":len(frames),"blocks":sum(1 for m in man if "kind" in m),"master":[int(master.shape[1]),int(master.shape[0])]}
            else:
                res[seg]={"frames":len(frames),"master":None}
            (od/"manifest.json").write_text(json.dumps(man,ensure_ascii=False,indent=2),encoding="utf-8")
        except Exception as e:
            res[seg]={"frames":len(frames),"err":repr(e)[:120]}
    return res

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--start",type=int,default=0); ap.add_argument("--count",type=int,default=100)
    ap.add_argument("--film",default=None,help="substring -> tek film testi")
    a=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    dirs=sorted([d for d in DB.iterdir() if d.is_dir()])
    if a.film:
        sel=[d for d in dirs if a.film.lower() in d.name.lower()][:1]
    else:
        sel=dirs[a.start:a.start+a.count]
    print(f"=== DB-COMPOSE: {len(sel)} film (toplam {len(dirs)}; aralık {a.start}-{a.start+a.count}) ===",flush=True)
    summ=[]
    for i,fd in enumerate(sel):
        t0=time.time(); r=process_film(fd); dt=round(time.time()-t0,1)
        gi=r.get("giris",{}); ci=r.get("cikis",{})
        print(f"[{a.start+i:3}] {fd.name[:46]:46} | giriş:{gi.get('master') or gi.get('skip') or gi.get('frames')} çıkış:{ci.get('master') or ci.get('skip') or ci.get('frames')} ({dt}s)",flush=True)
        summ.append(r)
    sp=OUT/f"_SUMMARY_{a.start}_{a.start+a.count}.json"
    sp.write_text(json.dumps(summ,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"\n-> {sp}",flush=True)

if __name__=="__main__": main()
