"""Paddle dil testi: en vs latin vs tr — hangisi ş/ğ/ı/İ üretiyor? DİRİLİŞ çıkış master.
TR-diakritik satır sayısı + ilk satırlar. Charset kontrolü.
"""
import sys, glob, importlib.util
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("fp",r"E:\MITAS\OCR-worktree\py\20260530_1744_full_pipeline.py")
fp=importlib.util.module_from_spec(spec); sys.modules["fp"]=fp; spec.loader.exec_module(fp)

TR_MARK=set("şŞğĞıİ")
def fold(s):
    s=(s or "").lower()
    for a,b in [("ı","i"),("İ","i"),("i̇","i"),("ş","s"),("ğ","g"),("ç","c"),("ö","o"),("ü","u"),("'",""),("-"," ")]:
        s=s.replace(a,b)
    return " ".join(s.split())

m=glob.glob(r"E:\MITAS\OCR-worktree\tester_fiso\*DİRİLİŞ_ERTUĞRUL\cikis\master.png")
m=[x for x in m if "0010" in x][0]
img=fp.rd(m); H=img.shape[0]; print("master:",m,"H=",H,flush=True)
TILE,OV=1500,120; step=TILE-OV

def read_lang(lang):
    from paddleocr import PaddleOCR
    try:
        ocr=PaddleOCR(lang=lang, use_textline_orientation=False)
    except Exception as e:
        return None, f"INIT FAIL: {str(e)[:120]}"
    seen={}; y=0
    while y<H:
        tile=img[y:min(y+TILE,H),:]
        try: results=ocr.predict(tile)
        except Exception as e:
            y+=step; continue
        for item in (results or []):
            d=item if isinstance(item,dict) else (getattr(item,"json",{}) or {})
            res=d.get("res",d) if isinstance(d,dict) else {}
            if not isinstance(res,dict): res={}
            texts=res.get("rec_texts") or d.get("rec_texts") or []
            for t in texts:
                t=(t or "").strip()
                if len(t)<2: continue
                fk=fold(t)
                if fk not in seen: seen[fk]=t
        y+=step
    lines=list(seen.values())
    return lines, None

for lang in ["en","latin","tr"]:
    print(f"\n===== lang='{lang}' =====",flush=True)
    lines,err=read_lang(lang)
    if err: print("  ",err,flush=True); continue
    tr=sum(1 for t in lines if any(c in TR_MARK for c in t))
    print(f"  satır={len(lines)}  TR-diakritik(ş/ğ/ı/İ) satır={tr}",flush=True)
    print("  ilk 14:",flush=True)
    for t in lines[:14]: print("    ",t,flush=True)
