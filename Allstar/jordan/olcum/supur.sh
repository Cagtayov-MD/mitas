#!/usr/bin/env bash
# Config supurmesi — bir model, N ffmpeg/uretim varyanti, secilen klipler.
# Kullanim: ./supur.sh <model_yolu> <tur_adi> <klip_no...>
set -uo pipefail
J="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KLIP=/home/cagatay/Belgeler/test
MODEL="${1:?model yolu}"; TUR="${2:?tur adi}"; shift 2
KOK="$J/olcum/kosular/$TUR"; mkdir -p "$KOK"

# ── VARYANTLAR: ad|suzgec|fps ────────────────────────────────────────────
# A = mevcut config (600px kaynagi 720'ye BUYUTUR)
# B = asla buyutme (tavan 720)
# C = her zaman 1.5x buyut (kucuk punto icin daha cok token/glif)
VARYANT=(
"A_mevcut|scale=720:-2:flags=lanczos,hqdn3d=2:2:2,unsharp=5:5:1.0|2"
"B_buyutme_yok|scale='min(iw,720)':-2:flags=lanczos,hqdn3d=2:2:2,unsharp=5:5:1.0|2"
"C_1_5x|scale=iw*1.5:-2:flags=lanczos,hqdn3d=2:2:2,unsharp=5:5:1.0|2"
)

for v in "${VARYANT[@]}"; do
  ad="${v%%|*}"; kalan="${v#*|}"; suz="${kalan%|*}"; fps="${kalan##*|}"
  for nn in "$@"; do
    fid="${ad}__${nn}"
    [ -f "$J/out/$fid/cikis/_TAMAM" ] && { echo "[atla] $fid"; continue; }
    t0=$(date +%s)
    "$J/jordan" tek --video "$KLIP/cag_output${nn}.mp4" --film-id "$fid" \
      --model "$MODEL" --suzgec "$suz" --fps "$fps" \
      >"$KOK/${fid}.log" 2>&1
    echo "[$ad] klip $nn — $(( $(date +%s) - t0 )) sn"
  done
done

# ── PUANLA ──────────────────────────────────────────────────────────────
echo; echo "=== SONUC ($TUR / $(basename "$MODEL")) ==="
for v in "${VARYANT[@]}"; do
  ad="${v%%|*}"
  for nn in "$@"; do
    gt="$J/olcum/gt/$nn/gt.txt"; ck="$J/out/${ad}__${nn}/cikis/jordan.txt"
    [ -f "$gt" ] && [ -f "$ck" ] || continue
    printf "%-16s klip %s  " "$ad" "$nn"
    "$J/venv/bin/python" "$J/olcum/puanla.py" "$ck" --gt "$gt" \
      | "$J/venv/bin/python" -c "import sys,json; d=json.load(sys.stdin); \
print(f\"skor={d['skor']}  recall={d['recall']}  tr={d['tr_dogru']}  uydurma={d['uydurma_oran']}  satir={d['okunan_satir']}\")"
  done
done | tee "$KOK/ozet.txt"
