#!/bin/bash
# %100 KLASÖRÜ — üç kapıyı geçen PDF'leri biriktirir (silme yok, sadece ekleme).
cd /opt/mitas || exit 1
venvs/ocr/bin/python - <<'PY'
import glob,os,json,re,shutil,subprocess
E="/opt/mitas/export/KAPANIS_PDF_20260724"; T="/opt/mitas/export/KAPANIS_PDF_100"
H="/opt/mitas/filmtest/kapanis_hasat/"; IZIN="ÇĞİÖŞÜçğıöşüâîûÂÎÛ’·—"
os.makedirs(T,exist_ok=True)
def kareli(ks): return {x["ad"].strip().upper() for x in ks or [] if isinstance(x,dict) and x.get("kare") and x.get("ad") and x.get("guven") in ("yuksek","orta")}
fo={};fy={}
for od in glob.glob(H+"*/okuma.json"):
    kat=os.path.basename(os.path.dirname(od))[:9]; o=json.load(open(od))
    fo.setdefault(kat,set()); fo[kat]|=kareli(o.get("oyuncular")); fy.setdefault(kat,set()); fy[kat]|=kareli(o.get("yonetmen"))
k2={os.path.basename(os.path.dirname(f))[:9]:json.load(open(f)) for f in glob.glob(H+"*/kunye.json")}
w2={os.path.basename(os.path.dirname(f))[:9]:json.load(open(f)) for f in glob.glob(H+"*/ozet_web.json")}
yeni=0
for p in sorted(glob.glob(E+"/*.pdf")):
    ad=os.path.basename(p)
    if os.path.exists(T+"/"+ad): continue
    kat=re.match(r"(\d{4}-\d{4})",ad).group(1); d=k2.get(kat,{}); w=w2.get(kat,{})
    try: t=subprocess.run(["pdftotext",p,"-"],capture_output=True,text=True,timeout=30).stdout
    except Exception: continue
    if ("Yönetmen" not in t or "ÖZET" not in t or "OYUNCULAR" not in t
        or any(ord(c)>0x24F and c not in IZIN for c in t) or "SESLENDİREN" in t.upper()): continue
    if not (d.get("ozet") or "").strip() or not d.get("ozet_kaynak"): continue
    fyon=any(y.upper() in fy.get(kat,set()) for y in (d.get("yonetmen") or []))
    fn=sum(1 for x in (d.get("oyuncular") or []) if x.upper() in fo.get(kat,set()))
    wy=len(w.get("kanit_yonetmen") or []); wo=len(w.get("kanit_oyuncu") or [])
    if not ((fyon and fn>=2) or fn>=3 or ((fyon or fn>=2) and wy>=1 and wo>=3)): continue
    shutil.copy2(p, T+"/"+ad); yeni+=1
print(f"%100 klasörüne eklenen: {yeni} | toplam: {len(glob.glob(T+'/*.pdf'))}")
PY
