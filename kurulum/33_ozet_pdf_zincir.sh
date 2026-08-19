#!/bin/bash
# ÖZET→PDF ZİNCİRİ: web-özet turları (eksik kalanı tekrarlar) → künyeye işle → TAM PDF
cd /opt/mitas || exit 1
H=/opt/mitas/filmtest/kapanis_hasat
CATS=$(cat /tmp/claude-1000/-opt-mitas/8f9bec93-939c-4544-a0d3-e628081d6205/scratchpad/reliable_cats.txt)
for tur in 1 2 3 4; do
  echo "=== TUR $tur $(date '+%T')"
  venvs/ocr/bin/python kurulum/32_ozet_web.py --films "$CATS" --workers 2 2>&1 | tail -1
  KALAN=$(venvs/ocr/bin/python - <<'PY'
import json,glob,os
n=0
for f in glob.glob("/opt/mitas/filmtest/kapanis_hasat/*/kunye.json"):
    d=os.path.dirname(f); k=json.load(open(f))
    if k.get("yonetmen") and len(k.get("oyuncular") or [])>=3 and not os.path.exists(d+"/ozet_web.json"): n+=1
print(n)
PY
)
  echo "  eksik kalan: $KALAN"
  [ "$KALAN" -lt 5 ] && break
done
# özetleri künyeye işle (kesin-kimlik şartıyla)
venvs/ocr/bin/python - <<'PY'
import json,glob,os
n=0
for f in glob.glob("/opt/mitas/filmtest/kapanis_hasat/*/ozet_web.json"):
    d=os.path.dirname(f); w=json.load(open(f)); kj=d+"/kunye.json"
    if not os.path.exists(kj): continue
    k=json.load(open(kj))
    kesin = w.get("ozet") and w.get("kanit_yonetmen") and len(w.get("kanit_oyuncu") or [])>=2
    k["ozet"]=w["ozet"] if kesin else None
    if kesin: k["ozet_kaynak"]=w.get("kaynak"); n+=1
    json.dump(k,open(kj,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("kesin özet:",n)
PY
# TAM PDF bas
CATS2=$(venvs/ocr/bin/python - <<'PY'
import json,glob,os
out=[os.path.basename(os.path.dirname(f))[:9] for f in glob.glob("/opt/mitas/filmtest/kapanis_hasat/*/kunye.json")
     if (lambda k: k.get("yonetmen") and len(k.get("oyuncular") or [])>=3 and (k.get("ozet") or "").strip())(json.load(open(f)))]
print(",".join(sorted(set(out))))
PY
)
venvs/asr/bin/python kurulum/26_kapanis_pdf.py --films "$CATS2" --no-net 2>&1 | tail -1
# eksik olanları export'tan çıkar
venvs/ocr/bin/python - <<'PY'
import json,glob,os,shutil,re
E="/opt/mitas/export/KAPANIS_PDF_20260724"; EKS=E+"/_EKSIK"; os.makedirs(EKS,exist_ok=True)
k2={os.path.basename(os.path.dirname(f))[:9]:json.load(open(f)) for f in glob.glob("/opt/mitas/filmtest/kapanis_hasat/*/kunye.json")}
c=0
for p in glob.glob(E+"/*.pdf"):
    d=k2.get(re.match(r"(\d{4}-\d{4})",os.path.basename(p)).group(1),{})
    if not (d.get("yonetmen") and len(d.get("oyuncular") or [])>=3 and (d.get("ozet") or "").strip()):
        shutil.move(p,EKS+"/"+os.path.basename(p)); c+=1
print("çıkarılan:",c,"| TAM PDF:",len(glob.glob(E+"/*.pdf")))
PY
echo "ZİNCİR TAMAM $(date '+%T')"
