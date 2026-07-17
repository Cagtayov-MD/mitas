# -*- coding: utf-8 -*-
"""43 film toplu önce/sonra: YENİ ensemble okuyucu (credit_text_read) çıktısını
gerçek-zemin (audit workflow) yönetmeniyle karşılaştır. ASIL ÖLÇÜT: yanlış yönetmen = 0.
Eski davranış (ilk-dolu-model) referansı için her modeli tek tek de koşar."""
import glob, json, sys, re, unicodedata
sys.path.insert(0, r"E:\MITAS\scripts")
import credit_text_read as ctr

def fold(s):
    s=(s or "")
    for a,b in (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),("Ğ","g"),("ğ","g"),
                ("Ü","u"),("ü","u"),("Ö","o"),("ö","o"),("Ç","c"),("ç","c")):
        s=s.replace(a,b)
    return unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().lower().strip()

# GT: audit workflow sonucundan dogru_yonetmen
raw=open(r"C:\Users\TRT03\AppData\Local\Temp\claude\E--MITAS\28d49f5c-3526-4e51-9e6a-307b0914ffde\tasks\w3tz88lbf.output",encoding="utf-8",errors="ignore").read()
TAB=json.loads(raw)["result"]["table"]
GT={r["id"]:(r.get("dogru_yonetmen") or []) for r in TAB}
TITLE={r["id"]:r.get("tr","") for r in TAB}

def ocr_lines(fid):
    p=glob.glob(rf"E:\MITAS\Database\evoArcadmin*{fid}*\ocr\ocr-*\kunye.txt")
    return open(p[0],encoding="utf-8",errors="ignore").read().splitlines() if p else None

def yon_match(got, gt):
    """got listesindeki bir isim, GT listesindeki birinin SOYADINI içeriyor mu (folded)."""
    if not got: return "ABSTAIN"
    if not gt:  return "GT-YOK"
    gf=[fold(g) for g in gt]
    for y in got:
        yf=fold(y)
        for g in gf:
            toks=[t for t in g.split() if len(t)>2]
            if toks and (toks[-1] in yf or yf in g or g in yf):
                return "MATCH"
    return "WRONG"

def garble_count(names):
    return sum(1 for n in names if ctr._looks_garble(n))

mt={"MATCH":0,"ABSTAIN":0,"WRONG":0,"GT-YOK":0}
tot_garble=0; tot_cast=0
print(f"{'FİLM':<30}{'YÖN-SINIF':<10}{'YENİ YÖNETMEN'}", flush=True)
print("-"*90, flush=True)
for fid in GT:
    lines=ocr_lines(fid)
    if lines is None:
        print(f" {TITLE[fid][:28]:<29}{'OCR-YOK':<10}", flush=True); continue
    try:
        r=ctr.read_credits_auto(lines, TITLE[fid])
    except Exception as e:
        print(f" {TITLE[fid][:28]:<29}HATA:{type(e).__name__}: {str(e)[:40]}", flush=True); continue
    yon=r.get("yonetmen") or []; cast=r.get("cast") or []
    cls=yon_match(yon, GT[fid])
    mt[cls]=mt.get(cls,0)+1
    g=garble_count(cast); tot_garble+=g; tot_cast+=len(cast)
    flag="‼" if cls=="WRONG" else (" " if cls in("MATCH","OCR-YOK") else "·")
    print(f"{flag}{TITLE[fid][:28]:<29}{cls:<10}{str(yon)[:30]:<31}{len(cast)} cast, garble={g}", flush=True)
print("-"*90, flush=True)
n=len([r for r in rows if r[2] in mt])
print(f"YÖNETMEN: MATCH={mt['MATCH']}  ABSTAIN(boş/okunamadı)={mt['ABSTAIN']}  WRONG={mt['WRONG']}  (GT-yok={mt['GT-YOK']})  /{n}")
print(f"  → ASIL ÖLÇÜT: YANLIŞ yönetmen = {mt['WRONG']} (hedef 0)")
print(f"CAST: toplam {tot_cast} isim, garble (looks_garble) = {tot_garble} (hedef ~0)")
