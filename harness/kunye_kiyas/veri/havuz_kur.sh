#!/bin/bash
# Büyük-havuz karelerini yeniden kur — kaynak artık "Film Kapanış"
# (30.06 boşaltıldı; filmler evoArcadmin_<parti>_<id>-<AD>.mp4 adıyla taşındı).
# Klasör adları GT (dogrulama_sonuc.json) film adlarıyla BİREBİR tutulur.
# Parite kanıtı: OPERADAKİ_HAYALET yeni indirmede v5=1161 (kayıtla aynı).
set -uo pipefail
V="/opt/mitas/harness/kunye_kiyas/veri"
KOK="/opt/mitas/data/jenerik_havuz/pool_frames"
SMB="smb://depo01cifs.int.trt.net.tr/sas_h264/Film Kapanış"
GV="/run/user/1000/gvfs/smb-share:server=depo01cifs.int.trt.net.tr,share=sas_h264/Film Kapanış"
LOG="$V/havuz_kur.log"
TAIL_S=600; FPS=2
mkdir -p "$KOK"
exec >>"$LOG" 2>&1
echo "=== $(date '+%F %T') havuz_kur v2 (Film Kapanış) başladı ==="

# 1) mount bekle (kopmalara dayanıklı)
for i in $(seq 1 2880); do
  [ -d "$GV" ] && break
  timeout 20 gio mount "smb://depo01cifs.int.trt.net.tr/sas_h264" >/dev/null 2>&1
  sleep 30
done
[ -d "$GV" ] || { echo "VAZGEÇİLDİ: mount yok"; exit 1; }

# 2) liste + eşleme (tam id; olmazsa YYYY-NNNN; hata filmleri öne)
ls "$GV" > "$V/liste_kapanis.txt"
/opt/mitas/venvs/ocr/bin/python - <<'EOF'
import json, re
V="/opt/mitas/harness/kunye_kiyas/veri"
d=json.load(open(f"{V}/dogrulama_sonuc.json",encoding="utf-8"))["filmler"]
liste=[l.strip() for l in open(f"{V}/liste_kapanis.txt",encoding="utf-8")
       if l.strip().endswith(".mp4")]
def tam_id(s):
    m=re.search(r"(\d{4}-\d{3,4}-\d-\d{4}-\d{2}-\d)",s); return m.group(1) if m else None
def kisa_id(s):
    m=re.search(r"(\d{4}-\d{3,4})",s); return m.group(1) if m else None
tam={}; kisa={}
for l in liste:
    t=tam_id(l); k=kisa_id(l)
    if t: tam.setdefault(t,l)
    if k: kisa.setdefault(k,[]).append(l)
hata=[x for x in d if x["karar"]!="dogru"]; dogru=[x for x in d if x["karar"]=="dogru"]
satir=[]; fuzzy=[]; yok=[]
for x in hata+dogru:
    ad=x["film"]
    if not re.match(r"\d{4}-",ad): yok.append(ad); continue
    t=tam_id(ad); k=kisa_id(ad)
    if t and t in tam:
        satir.append(f"{tam[t]}\t{ad}")
    elif k and len(kisa.get(k,[]))==1:
        satir.append(f"{kisa[k][0]}\t{ad}"); fuzzy.append(f"{ad} <= {kisa[k][0]}")
    else:
        yok.append(ad)
open(f"{V}/eslesme.tsv","w",encoding="utf-8").write("\n".join(satir)+"\n")
open(f"{V}/eslesme_fuzzy.txt","w",encoding="utf-8").write("\n".join(fuzzy)+"\n")
print(f"eşlenen={len(satir)} fuzzy={len(fuzzy)} eşlenemeyen={len(yok)}")
for y in yok: print("  YOK:",y)
EOF

# 3) indirici — eslesme.tsv: kaynak_dosya<TAB>hedef_klasör
indir() {
  local LISTE="$1"
  while IFS=$'\t' read -r kaynak hedef; do
    [ -z "$kaynak" ] && continue
    local H="$KOK/$hedef"
    [ -d "$H" ] && [ "$(ls "$H"/*.png 2>/dev/null | wc -l)" -gt 50 ] && { echo "[atla] $hedef"; continue; }
    mkdir -p "$H"
    local tmp="/opt/mitas/data/jenerik_havuz/_dl_$$.mp4" ok=0
    for try in 1 2 3; do
      if timeout 500 gio copy "$GV/$kaynak" "$tmp" 2>/dev/null && [ -s "$tmp" ]; then ok=1; break; fi
      rm -f "$tmp"; sleep 5
    done
    [ "$ok" = 0 ] && { echo "[İNDİRİLEMEDİ] $hedef"; rmdir "$H" 2>/dev/null; continue; }
    local dur ss n
    dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$tmp" 2>/dev/null | cut -d. -f1)
    [ -z "$dur" ] && dur=0
    ss=$(( dur > TAIL_S ? dur - TAIL_S : 0 ))
    timeout 300 ffmpeg -y -v error -ss "$ss" -i "$tmp" -vf "fps=$FPS" -q:v 3 "$H/c_%05d.png" 2>/dev/null
    n=$(ls "$H"/*.png 2>/dev/null | wc -l)
    rm -f "$tmp"
    echo "[OK] $hedef süre=${dur}s kare=$n"
  done < "$LISTE"
  echo "İŞÇİ BİTTİ: $LISTE"
}

awk 'NR%2==1' "$V/eslesme.tsv" > "$V/esl_a.tsv"
awk 'NR%2==0' "$V/eslesme.tsv" > "$V/esl_b.tsv"
indir "$V/esl_a.tsv" & PA=$!
indir "$V/esl_b.tsv" & PB=$!
wait $PA $PB

# 4) parite raporu: kare sayısı GT 'kare' alanıyla uyuşuyor mu
/opt/mitas/venvs/ocr/bin/python - <<'EOF'
import json, glob, os
V="/opt/mitas/harness/kunye_kiyas/veri"
KOK="/opt/mitas/data/jenerik_havuz/pool_frames"
t={x["film"]:x.get("kare") for x in json.load(open(f"{V}/v5_tahminler.json",encoding="utf-8"))["filmler"]}
sat=[]
for d in sorted(glob.glob(f"{KOK}/*/")):
    ad=os.path.basename(d.rstrip("/")); n=len(glob.glob(d+"*.png")); b=t.get(ad)
    durum="OK" if (b and abs(n-b)<=2) else f"FARK({n} vs {b})"
    sat.append(f"{durum:<14} {ad}")
open(f"{V}/parite_rapor.txt","w",encoding="utf-8").write("\n".join(sat)+"\n")
print("parite:", sum(1 for s in sat if s.startswith("OK")), "/", len(sat))
EOF
echo "=== $(date '+%F %T') havuz_kur BİTTİ: $(ls -d "$KOK"/*/ 2>/dev/null | wc -l) klasör ==="
