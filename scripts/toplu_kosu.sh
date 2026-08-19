#!/bin/bash
# TOPLU KOŞU — Film Kapanış share'indeki tüm evoArcadmin filmlerini Paddle
# hattıyla sıralı işler. SİLME YAPMAZ (Database koruması); hijyen için
# scripts/toplu_hijyen.sh Çağatay'ın terminalinden ayrıca koşar.
#
# Özellikler: tekrar-atlama (media_id Database'de varsa), staging kopya
# (SMB kopmasına dayanıklı; staging kopyası işlem sonrası silinir — cache'tir),
# disk sigortası (<40 GB → durur), DURDUR dosyası (outputs/toplu_kosu/DURDUR),
# kaldığı yerden devam (atlama sayesinde yeniden başlatmak güvenli).
set -u
set -a; . /opt/mitas/mitas.env; set +a
PYA=/opt/mitas/venvs/asr/bin/python
G="/run/user/1000/gvfs/smb-share:server=depo01cifs.int.trt.net.tr,share=sas_h264/Film Kapanış"
KOK=/opt/mitas/outputs/toplu_kosu
STAGE=/opt/mitas/cache/staging/toplu
mkdir -p "$KOK" "$STAGE"
LISTE="$KOK/film_listesi.txt"
if [ ! -s "$LISTE" ]; then
  ls "$G" | grep "^evoArcadmin_.*\.mp4$" | sort > "$LISTE"
fi
TOPLAM=$(wc -l < "$LISTE")
echo "=== TOPLU KOSU BASLADI $(date +%F' '%H:%M:%S) — listede $TOPLAM film ==="

N=0
while IFS= read -r f; do
  N=$((N+1))
  [ -f "$KOK/DURDUR" ] && { echo "DURDUR dosyası görüldü — duruyorum ($(date +%H:%M))"; break; }
  bos=$(df --output=avail -BG /opt/mitas | tail -1 | tr -dc 0-9)
  if [ "${bos:-0}" -lt 40 ]; then
    echo "DISK SIGORTASI: ${bos}G kaldı (<40G) — duruyorum. toplu_hijyen.sh koşunca yeniden başlatın."
    break
  fi
  mid=$(echo "$f" | grep -oE '[0-9]{4}-[0-9]{4}-[0-9]-[0-9]{4}-[0-9]{2}-[0-9]' | head -1)
  if [ -z "$mid" ]; then
    echo "ATLA(kimliksiz ad): $f"
    continue
  fi
  if ls -d /opt/mitas/Database/*"$mid"* >/dev/null 2>&1; then
    echo "ATLA(Database'de var): $f"
    continue
  fi
  bekleme=0
  while [ ! -f "$G/$f" ]; do
    if ls "$G" >/dev/null 2>&1; then
      echo "ATLA(kaynak dosya yok): $f"
      continue 2
    fi
    bekleme=$((bekleme+1))
    [ "$bekleme" -gt 60 ] && { echo "ATLA(60dk kaynak yok): $f"; continue 2; }
    [ -f "$KOK/DURDUR" ] && break 2
    echo "kaynak/mount bekleniyor (${bekleme}dk): $f"
    sleep 60
  done
  cp -f "$G/$f" "$STAGE/$f" 2>/dev/null || { echo "HATA(staging kopya): $f"; continue; }
  echo "=== [$N/$TOPLAM] $f ($(date +%F' '%H:%M:%S))"
  $PYA /opt/mitas/scripts/mitas_pipeline.py --video "$STAGE/$f" --profile film --no-copy-source < /dev/null
  rc=$?
  rm -f "$STAGE/$f"
  echo "--- [$N/$TOPLAM] rc=$rc $f ($(date +%H:%M:%S))"
done < "$LISTE"
echo "=== TOPLU KOSU BITTI/DURDU $(date +%F' '%H:%M:%S) ==="
