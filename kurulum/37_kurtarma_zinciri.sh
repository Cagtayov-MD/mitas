#!/bin/bash
# KURTARMA: boş kuyruk kırp → yeniden oku (NIM) → birleştir → özet → PDF
cd /opt/mitas || exit 1
H=/opt/mitas/filmtest/kapanis_hasat
S=/tmp/claude-1000/-opt-mitas/8f9bec93-939c-4544-a0d3-e628081d6205/scratchpad
[ -f "$H/_KURT_DUR" ] && exit 0
echo "=== KURTARMA BAŞLADI $(date '+%F %T')"
venvs/ocr/bin/python kurulum/36_kuyruk_kirp.py --films-file "$S/dtier.txt" --workers 6 2>&1 | tail -2
echo "--- yeniden okuma (NIM)"
venvs/ocr/bin/python kurulum/29_nim_okuma.py --workers 8 2>&1 | tail -1
echo "--- birleştir"
venvs/ocr/bin/python kurulum/27_kapanis_birlestir.py 2>&1 | tail -1
echo "--- durum"
venvs/ocr/bin/python - <<'PY'
import json,glob,os
def kareli(ks): return {k["ad"].strip().upper() for k in ks or [] if isinstance(k,dict) and k.get("kare") and k.get("guven") in ("yuksek","orta")}
H="/opt/mitas/filmtest/kapanis_hasat/"
fo={};fy={}
for od in glob.glob(H+"*/okuma.json"):
    kat=os.path.basename(os.path.dirname(od))[:9]; o=json.load(open(od))
    fo.setdefault(kat,set()); fo[kat]|=kareli(o.get("oyuncular")); fy.setdefault(kat,set()); fy[kat]|=kareli(o.get("yonetmen"))
s={"A":0,"B":0,"C":0,"D":0}
for f in glob.glob(H+"*/kunye.json"):
    kat=os.path.basename(os.path.dirname(f))[:9]; k=json.load(open(f))
    yon=[x.upper() for x in (k.get("yonetmen") or [])]; oy=[x.upper() for x in (k.get("oyuncular") or [])]
    fyon=any(y in fy.get(kat,set()) for y in yon); foy=sum(1 for x in oy if x in fo.get(kat,set()))
    if not (k.get("yonetmen") and len(oy)>=3): s["D"]+=1
    elif fyon and foy>=3: s["A" if (k.get("ozet") or "").strip() else "B"]+=1
    else: s["C"]+=1
print("KURTARMA SONRASI → A:",s["A"],"B:",s["B"],"C:",s["C"],"D:",s["D"],"| künye-kesin:",s["A"]+s["B"])
PY
touch "$H/_KURT_BITTI"
echo "=== KURTARMA BİTTİ $(date '+%F %T')"
