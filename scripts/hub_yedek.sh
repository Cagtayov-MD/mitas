#!/bin/bash
# hub_yedek.sh — /opt/mitas/Database artımlı hub-yedeği (rsync --link-dest snapshot).
#
# NEDEN (Çağatay onayı 2026-07-17, "Yalnız F-içi snapshot"): BAŞKAN VE MARI hub'ı 06-Tem
# force-rerun rmtree'siyle KAYBEDİLDİ; İP-7 force-rmtree'yi kaldırdı ama hub'lar tek kopyaydı.
# Bu yedek silme/bozulma kazalarını karşılar (aynı-disk: fiziksel arızayı KARŞILAMAZ — bilinçli).
#
# Tasarım:
#   /opt/yedek/mitas_db/<YYYYMMDD_HHMMSS>/Database  — her koşu bir snapshot
#   Değişmeyen dosyalar önceki snapshot'a HARDLINK (disk maliyeti ≈ yalnız delta).
#   'son' symlink'i en yeni snapshot'ı gösterir.
#   SİLME YOK: script hiçbir snapshot'ı silmez. Yer açmak gerekirse Çağatay elle siler
#   (bkz: du -sh /opt/yedek/mitas_db/* ; en eskiden silinir).
# Kill: systemctl disable --now mitas-hub-yedek.timer
set -euo pipefail
KAYNAK="/opt/mitas/Database"
KOK="/opt/yedek/mitas_db"
DAMGA="$(date +%Y%m%d_%H%M%S)"
HEDEF="$KOK/$DAMGA"
SON="$KOK/son"
LOG="$KOK/yedek.log"

mkdir -p "$KOK"
{
  echo "[$(date -Is)] BAŞLADI → $HEDEF"
  # Disk emniyeti: kökte en az 60G boş yoksa koşma (delta bile riske girmesin).
  BOS_G=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
  if [ "$BOS_G" -lt 60 ]; then
    echo "[$(date -Is)] İPTAL: / diskinde yalnız ${BOS_G}G boş (<60G eşiği)."
    exit 0
  fi
  LINKDEST=()
  [ -d "$SON/Database" ] && LINKDEST=(--link-dest="$SON/Database")
  mkdir -p "$HEDEF.tmp/Database"
  rsync -a --delete-excluded "${LINKDEST[@]}" "$KAYNAK/" "$HEDEF.tmp/Database/"
  mv "$HEDEF.tmp" "$HEDEF"
  ln -sfn "$HEDEF" "$SON"
  echo "[$(date -Is)] BİTTİ: $(du -sh "$HEDEF" | cut -f1) (görünür; hardlink'li gerçek delta için: du -sh $KOK)"
} >> "$LOG" 2>&1
