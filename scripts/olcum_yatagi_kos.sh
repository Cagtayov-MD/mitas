#!/bin/bash
# ÖLÇÜM YATAĞI KOŞUCUSU — 15 filmlik jenerik-okuma ölçüm yatağını kurar.
#
# NEDEN AYRI BİR KOŞUCU: toplu_kosu.sh üretim kuyruğudur (1825 film, ASR dahil,
# Database'e yazar). Bu ise ÖLÇÜM yatağıdır: ASR yok (künye ölçümüne katkısı sıfır,
# film başına en pahalı adım), sabit 15 filmlik liste, kendi log kökü.
#
# TEK GEÇİŞTE ÜÇ İŞ:
#   1. Yatak      → frames/cikis_jenerik havuzu + reading_master_runaware.png + manifest
#   2. QC1 kapısı → yeni credit_qc1_* olaylarının gerçek filmde bastığının kanıtı
#   3. Baseline   → mevcut Paddle→gemma künyesi (yeni mimariyle kıyaslanacak taban)
#
# KONVANSİYON: toplu_kosu.sh ile aynı — mitas.env, staging kopya (SMB kopmasına
# dayanıklı), disk sigortası, DURDUR dosyası, kaldığı yerden devam.
#
# KULLANIM:
#   bash scripts/olcum_yatagi_kos.sh                 # listedeki tüm filmler
#   bash scripts/olcum_yatagi_kos.sh 1               # yalnız 1. film (pilot)
#   bash scripts/olcum_yatagi_kos.sh 3 7            # 3..7 arası
#   touch outputs/olcum_yatagi/DURDUR                # temiz durdurma
set -u
set -a; . /opt/mitas/mitas.env; set +a

PYA=/opt/mitas/venvs/asr/bin/python
KOK=/opt/mitas/outputs/olcum_yatagi
STAGE=/opt/mitas/cache/staging/olcum
mkdir -p "$KOK" "$STAGE"
# Yatak listesi repo içinde durur (scratchpad geçicidir, harness kalıcı olmalı).
# Üreteci: outputs/olcum_yatagi/yatak_sec.py (tohum 20260731 → tekrar-üretilebilir).
YATAK_JSON="${OLCUM_YATAK_JSON:-$KOK/yatak_15.json}"

BAS="${1:-1}"
SON="${2:-999}"

if [ ! -s "$YATAK_JSON" ]; then
  echo "HATA: yatak listesi yok: $YATAK_JSON"; exit 2
fi

# Listeyi TSV'ye çevir: sira \t trt_id \t mp4yolu
TSV="$KOK/yatak.tsv"
python3 - "$YATAK_JSON" > "$TSV" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
for f in d["filmler"]:
    print(f"{f['sira']}\t{f['trt_id']}\t{f['mp4']}")
PY

TOPLAM=$(wc -l < "$TSV")
echo "=== ÖLÇÜM YATAĞI KOŞUSU $(date +%F' '%H:%M:%S) — $TOPLAM film, aralık $BAS..$SON ==="
echo "    ASR KAPALI (--no-asr) · kaynak kopyası KAPALI (--no-copy-source)"

while IFS=$'\t' read -r SIRA MID MP4; do
  [ "$SIRA" -lt "$BAS" ] && continue
  [ "$SIRA" -gt "$SON" ] && continue
  [ -f "$KOK/DURDUR" ] && { echo "DURDUR görüldü — duruyorum ($(date +%H:%M))"; break; }

  bos=$(df --output=avail -BG /opt/mitas | tail -1 | tr -dc 0-9)
  if [ "${bos:-0}" -lt 40 ]; then
    echo "DISK SIGORTASI: ${bos}G kaldı (<40G) — duruyorum."; break
  fi

  # Tekrar-atlama: Database'de varsa yeniden koşma (kaldığı yerden devam)
  if ls -d /opt/mitas/Database/*"$MID"* >/dev/null 2>&1; then
    echo "[$SIRA/$TOPLAM] ATLA(Database'de var): $MID"
    continue
  fi

  AD=$(basename "$MP4")
  if [ ! -f "$MP4" ]; then
    echo "[$SIRA/$TOPLAM] HATA(kaynak yok, mount düşmüş olabilir): $AD"
    continue
  fi

  echo "[$SIRA/$TOPLAM] $MID — staging kopya ($(date +%H:%M:%S))"
  cp -f "$MP4" "$STAGE/$AD" 2>/dev/null || { echo "  HATA(staging kopya)"; continue; }

  LOG="$KOK/film_${SIRA}_${MID}.log"
  T0=$(date +%s)
  echo "[$SIRA/$TOPLAM] pipeline başlıyor → $LOG"
  $PYA /opt/mitas/scripts/mitas_pipeline.py \
      --video "$STAGE/$AD" --profile film --no-asr --no-copy-source \
      > "$LOG" 2>&1 < /dev/null
  RC=$?
  T1=$(date +%s)
  SURE=$(( T1 - T0 ))
  echo "[$SIRA/$TOPLAM] bitti rc=$RC süre=$((SURE/60))dk$((SURE%60))sn"
  echo -e "$SIRA\t$MID\t$RC\t$SURE\t$(date -Iseconds)" >> "$KOK/sureler.tsv"

  rm -f "$STAGE/$AD"
done < "$TSV"

echo "=== KOŞU BİTTİ $(date +%F' '%H:%M:%S) ==="
echo "Süreler: $KOK/sureler.tsv"
echo "QC1 ölçümü: python3 scripts/qc1_olcum.py --detay"
