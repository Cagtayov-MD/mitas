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
#
# BUDAMA (Çağatay kararı 2026-07-31 — eski "SİLME YOK" kuralının yerine):
#   En yeni $TUT snapshot tutulur, gerisi otomatik silinir. Sebep: sınırsız birikim
#   17 Tem–31 Tem arası 219G yedi; 13 eski snapshot elle temizlendi (+56G).
#   Retention bir RİSK doğurur: kaynak sessizce boşalırsa $TUT gün sonra iyi
#   snapshot'lar da budanır ve veri kalıcı gider (07-29'da Database 300→197→0 oldu,
#   sebep hâlâ doğrulanmadı — o gün bizi sınırsız birikim kurtarmıştı).
#   Bu yüzden budamanın karşı-ağırlığı aşağıdaki KÜÇÜLME FRENİ'dir: ikisi bir paket,
#   birini kaldırırken diğerini de gözden geçir.
# Kill: systemctl disable --now mitas-hub-yedek.timer
set -euo pipefail
KAYNAK="/opt/mitas/Database"
KOK="/opt/yedek/mitas_db"
DAMGA="$(date +%Y%m%d_%H%M%S)"
HEDEF="$KOK/$DAMGA"
SON="$KOK/son"
LOG="$KOK/yedek.log"
TUT=14              # kaç snapshot saklanır (delta'lar ~30MB → 14 gün ≈ bedava)
KUCULME_ESIK=70     # kaynak, son snapshot'ın %bu kadarından azsa yedek ALINMAZ

mkdir -p "$KOK"
{
  echo "[$(date -Is)] BAŞLADI → $HEDEF"
  # Disk emniyeti: kökte en az 60G boş yoksa koşma (delta bile riske girmesin).
  BOS_G=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
  if [ "$BOS_G" -lt 60 ]; then
    echo "[$(date -Is)] İPTAL: / diskinde yalnız ${BOS_G}G boş (<60G eşiği)."
    exit 0
  fi
  # KÜÇÜLME FRENİ: kaynak son snapshot'a göre ani daraldıysa DOKUNMA. Hem bozuk
  # yedek almayı hem de budamanın iyi snapshot'ları yemesini engeller (07-29 olayı).
  if [ -d "$SON/Database" ]; then
    YENI_N=$(find "$KAYNAK"        -maxdepth 1 -mindepth 1 -type d | wc -l)
    ESKI_N=$(find "$SON/Database"  -maxdepth 1 -mindepth 1 -type d | wc -l)
    if [ "$ESKI_N" -gt 0 ] && [ $(( YENI_N * 100 / ESKI_N )) -lt "$KUCULME_ESIK" ]; then
      echo "[$(date -Is)] İPTAL: kaynak $ESKI_N → $YENI_N film (%$KUCULME_ESIK eşiğinin altı)."
      echo "[$(date -Is)] Yedek ALINMADI, budama YAPILMADI — mevcut snapshot'lar korundu."
      echo "[$(date -Is)] Kasıtlıysa: son snapshot'ı elle sil veya KUCULME_ESIK'i geçici düşür."
      exit 0
    fi
  fi

  LINKDEST=()
  [ -d "$SON/Database" ] && LINKDEST=(--link-dest="$SON/Database")
  rm -rf "$HEDEF.tmp"          # önceki başarısız koşudan kalıntı varsa (sessiz alan sızıntısı)
  mkdir -p "$HEDEF.tmp/Database"
  rsync -a --delete-excluded "${LINKDEST[@]}" "$KAYNAK/" "$HEDEF.tmp/Database/"
  mv "$HEDEF.tmp" "$HEDEF"
  ln -sfn "$HEDEF" "$SON"
  echo "[$(date -Is)] BİTTİ: $(du -sh "$HEDEF" | cut -f1) (görünür; hardlink'li gerçek delta için: du -sh $KOK)"

  # BUDAMA: en yeni $TUT snapshot kalır. 'son' symlink'i -type d ile eşleşmez (lstat).
  # '20*_*' deseni + ${KOK:?} = yanlış hedefe rm -rf'e karşı çift emniyet.
  find "$KOK" -maxdepth 1 -mindepth 1 -type d -name '20*_*' ! -name '*.tmp' -printf '%f\n' \
    | sort -r | tail -n +$((TUT + 1)) \
    | while IFS= read -r ESKI_D; do
        rm -rf "${KOK:?}/${ESKI_D:?}"
        echo "[$(date -Is)] BUDANDI: $ESKI_D"
      done
} >> "$LOG" 2>&1
