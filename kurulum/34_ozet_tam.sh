#!/bin/bash
cd /opt/mitas || exit 1
S=/tmp/claude-1000/-opt-mitas/8f9bec93-939c-4544-a0d3-e628081d6205/scratchpad
for tur in 1 2 3; do
  # her turda GÜNCEL özetsiz listeyi hesapla
  venvs/ocr/bin/python - > $S/hedef.txt <<'PY'
import json,glob,os
out=[]
for f in glob.glob("/opt/mitas/filmtest/kapanis_hasat/*/kunye.json"):
    d=os.path.dirname(f); k=json.load(open(f))
    if not (k.get("yonetmen") and len(k.get("oyuncular") or [])>=3): continue
    wf=d+"/ozet_web.json"
    if os.path.exists(wf) and json.load(open(wf)).get("ozet"): continue
    out.append(os.path.basename(d)[:9])
print(",".join(sorted(set(out))))
PY
  N=$(tr ',' '\n' < $S/hedef.txt | grep -c .)
  echo "=== TUR $tur: $N özetsiz film $(date '+%T')"
  [ "$N" -lt 5 ] && break
  venvs/ocr/bin/python kurulum/32_ozet_web.py --films-file "$S/hedef.txt" --force --workers 3 2>&1 | tail -1
done
# doğrulanmış özetleri künyeye işle (diğerlerini boşalt)
venvs/ocr/bin/python - <<'PY'
import json,glob,os
n=0
for f in glob.glob("/opt/mitas/filmtest/kapanis_hasat/*/kunye.json"):
    d=os.path.dirname(f); k=json.load(open(f)); wf=d+"/ozet_web.json"
    w=json.load(open(wf)) if os.path.exists(wf) else {}
    kesin=bool(w.get("ozet")) and bool(w.get("kanit_yonetmen")) and len(w.get("kanit_oyuncu") or [])>=2
    k["ozet"]=w["ozet"] if kesin else None
    if kesin: k["ozet_kaynak"]=w.get("kaynak"); n+=1
    json.dump(k,open(f,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("doğrulanmış özet:",n)
PY
# TAM PDF bas + eksikleri çıkar
C=$(venvs/ocr/bin/python - <<'PY'
import json,glob,os
print(",".join(sorted({os.path.basename(os.path.dirname(f))[:9] for f in glob.glob("/opt/mitas/filmtest/kapanis_hasat/*/kunye.json")
   if (lambda k: k.get("yonetmen") and len(k.get("oyuncular") or [])>=3 and (k.get("ozet") or "").strip())(json.load(open(f)))})))
PY
)
venvs/asr/bin/python kurulum/26_kapanis_pdf.py --films "$C" --no-net 2>&1 | tail -1
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
echo "TAM ZİNCİR BİTTİ $(date '+%T')"
