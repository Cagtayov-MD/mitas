"""20260531_2200 — OneOCR (Windows yerleşik) dene + Paddle/qwen ile kıyas. DİRİLİŞ cikis.
oneocr.OcrEngine().recognize_cv2(bgr) -> {'lines':[{'text','bounding_rect',...}]}. img ≤10000px → tile.
"""
import sys, time, glob, json, importlib.util
from pathlib import Path
import cv2, numpy as np
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("fp",r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py"); fp=importlib.util.module_from_spec(spec); sys.modules["fp"]=fp; spec.loader.exec_module(fp)

def fold(s):
    s=(s or "").lower()
    for a,b in [("ı","i"),("İ","i"),("i̇","i"),("ş","s"),("ğ","g"),("ç","c"),("ö","o"),("ü","u"),("'",""),("-"," ")]:
        s=s.replace(a,b)
    return " ".join(s.split())

import oneocr
print("OcrEngine başlatılıyor...", flush=True)
eng=oneocr.OcrEngine()
print("OcrEngine OK", flush=True)

m=glob.glob(r"E:\MITAS\OCR-worktree\tester_fiso\*DİRİLİŞ*\cikis\master.png")[0]
img=fp.rd(m); H,W=img.shape[:2]; print("master:",m,"boyut:",img.shape)
TILE=1500; OV=120; step=TILE-OV
t0=time.time(); seen={}; rows=[]
y=0
while y<H:
    tile=img[y:min(y+TILE,H),:]
    if tile.shape[0]<50: break
    try:
        res=eng.recognize_cv2(np.ascontiguousarray(tile))
    except Exception as e:
        print("  tile hata:",str(e)[:80]); y+=step; continue
    for ln in (res.get("lines") or []):
        t=(ln.get("text") or "").strip()
        if not t: continue
        br=ln.get("bounding_rect") or {}
        yt=int(br.get("y1",0) or 0)+y
        fk=fold(t)
        if fk and fk not in seen: seen[fk]=(t,yt)
    y+=step
dt=time.time()-t0
lines=sorted(seen.values(), key=lambda x:x[1])
print(f"\n=== OneOCR ===")
print(f"  süre: {dt:.1f} sn | satır (fold-dedup): {len(lines)}")
print("  ilk 22 (Türkçe diakritik korunuyor mu?):")
for t,yt in lines[:22]: print("    ",t)

# Paddle transcript ile kıyas
pt=Path(r"E:\MITAS\OCR-worktree\tester_read\DIRILIS\cikis\transcript.txt")
if pt.exists():
    pl=pt.read_text(encoding="utf-8").splitlines(); pf={fold(x) for x in pl}
    of={fold(t) for t,_ in lines}
    print(f"\n=== Paddle vs OneOCR ===")
    print(f"  Paddle: {len(pl)} | OneOCR: {len(lines)} | ortak(fold): {len(pf&of)}")
    print("  OneOCR'de VAR Paddle'da YOK (ilk 10):")
    for t,_ in [x for x in lines if fold(x[0]) not in pf][:10]: print("    +",t)
# kaydet
out=Path(r"E:\MITAS\OCR-worktree\tester_read\DIRILIS\cikis\oneocr_transcript.txt")
out.write_text("\n".join(t for t,_ in lines), encoding="utf-8")
print(f"\n  -> {out}")
