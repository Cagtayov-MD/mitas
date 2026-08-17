#!/usr/bin/env bash
# GİRİŞ ölçüm yatağı kurulumu (G6) — EKSIKLER G5/G6 tarifi.
#
# İKİ kaynak:
#   1) filmtest/depo_3006/*.mp4            — TAM filmler (evoArcadmin_... önekli ad)
#   2) filmtest/test_film_vl/*/giris_240.mp4 — zaten İLK 240 sn'lik kesitler
#      (VL deneylerinden; ÇIKIŞ için 'parça' sayılırlar ama GİRİŞ için tam
#      pencere — kullanılabilir, 2026-08-17 kararı)
#
# Çıkarım: her filmin İLK 240 sn'si, fps 2 → 480 kare/film.
# Tarif main.py:kare_cikar(bolum="giris") ile BİREBİR (ss=0, -t 240,
# fps=2, -q:v 3, c_%05d.png) — sinir.bul'un kare-no ↔ sn hizası buna dayanır.
# DEĞİŞTİRME: giriş ölçümleri bu kare üretimiyle yapılır.
#
# Idempotent: klasörde >=50 kare varsa atlar. Yeniden kurmak için klasörü sil.
set -euo pipefail

HEDEF="/opt/mitas/Allstar/kobe/havuz/giris"   # */havuz/ ignore kuralı — git dışı
PENCERE_SN=240
FPS=2
KALITE=3

mkdir -p "$HEDEF"
sayi=0
islec() {   # islec <mp4> <film-id>
  local mp4="$1" fid="$2" dizin
  dizin="$HEDEF/$fid"
  if [ -d "$dizin" ] && [ "$(ls "$dizin"/*.png 2>/dev/null | wc -l)" -ge 50 ]; then
    echo "[atla] $fid (hazır)"
    return
  fi
  mkdir -p "$dizin"
  echo "[kur] $fid ..."
  ffmpeg -y -v error -ss 0 -i "$mp4" -t "$PENCERE_SN" \
         -vf fps=$FPS -q:v $KALITE "$dizin/c_%05d.png"
  sayi=$((sayi + 1))
}

for mp4 in /opt/mitas/filmtest/depo_3006/*.mp4; do
  [ -e "$mp4" ] || continue
  # evoArcadmin_..._<arşiv-no>-<AD>.mp4 → <arşiv-no>-<AD>
  fid="$(basename "$mp4" .mp4 | sed 's/^evoArcadmin_[0-9]*SAYFA[0-9]*_//')"
  islec "$mp4" "$fid"
done

for mp4 in /opt/mitas/filmtest/test_film_vl/*/giris_240.mp4; do
  [ -e "$mp4" ] || continue
  fid="$(basename "$(dirname "$mp4")")"    # <yıl>-<no>_<AD>
  islec "$mp4" "$fid"
done

echo "tamam: $sayi film çıkarıldı, yatak: $HEDEF"
ls -d "$HEDEF"/*/ | wc -l | xargs echo "yatakta film:"

