#!/bin/bash
# 30.06 havuzundan film indir → son ~10dk tail'i frame çıkar → mp4 sil
# Kullanım: pool_cek_cikar.sh <dosya_listesi> <cikti_kok> <fps>
set -uo pipefail
GV="/run/user/1000/gvfs/smb-share:server=depo01cifs.int.trt.net.tr,share=sas_h264/30.06"
LISTE="$1"; KOK="$2"; FPS="${3:-2}"
TAIL_S="${TAIL_S:-600}"     # son 10 dk
mkdir -p "$KOK"

while IFS= read -r f; do
  [ -z "$f" ] && continue
  id=$(echo "$f" | grep -oP '\d{4}-\d{3,4}-\d-\d{4}-\d{2}-\d')
  ad=$(echo "$f" | grep -oP '\d{4}-\d{3,4}-\d-\d{4}-\d{2}-\d-\K[^.]*' | cut -c1-30)
  hedef="$KOK/${id}_${ad}"
  [ -d "$hedef" ] && [ "$(ls "$hedef"/*.png 2>/dev/null | wc -l)" -gt 50 ] && { echo "[atla] $ad"; continue; }
  mkdir -p "$hedef"
  tmp="/tmp/pool_$$.mp4"
  # indir (retry)
  ok=0
  for try in 1 2 3; do
    if timeout 400 gio copy "$GV/$f" "$tmp" 2>/dev/null && [ -s "$tmp" ]; then ok=1; break; fi
    rm -f "$tmp"
  done
  [ "$ok" = 0 ] && { echo "[İNDİRİLEMEDİ] $ad"; rmdir "$hedef" 2>/dev/null; continue; }
  # süre
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$tmp" 2>/dev/null | cut -d. -f1)
  [ -z "$dur" ] && dur=0
  ss=$(( dur > TAIL_S ? dur - TAIL_S : 0 ))
  # son TAIL_S saniyeyi FPS ile çıkar
  timeout 300 ffmpeg -y -v error -ss "$ss" -i "$tmp" -vf "fps=$FPS" -q:v 3 "$hedef/c_%05d.png" 2>/dev/null
  n=$(ls "$hedef"/*.png 2>/dev/null | wc -l)
  rm -f "$tmp"
  echo "[OK] $ad  süre=${dur}s ss=${ss} kare=$n"
done < "$LISTE"
echo "BİTTİ"
