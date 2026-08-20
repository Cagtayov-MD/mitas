#!/usr/bin/env bash
set -uo pipefail
J="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; KLIP=/home/cagatay/Belgeler/test
MODEL="${1:?}"; TUR="${2:?}"; shift 2
KOK="$J/olcum/kosular/$TUR"; mkdir -p "$KOK"
SHARP="flags=lanczos,hqdn3d=2:2:2,unsharp=5:5:1.0"
SCENE="select='gt(scene,0.2)'"
# ad|suzgec|fps|parca_sn|greedy
VARYANT=(
"E_sahne|scale=720:-2:$SHARP,$SCENE|2|15|1"
"F_sahne_buyutmesiz|scale='min(iw,720)':-2:$SHARP,$SCENE|2|15|1"
"G_sahne_6sn|scale=720:-2:$SHARP,$SCENE|2|6|1"
"H_sahne_ornekleme|scale=720:-2:$SHARP,$SCENE|2|15|0"
)
for v in "${VARYANT[@]}"; do
  IFS='|' read -r ad suz fps psn gr <<< "$v"
  for nn in "$@"; do
    fid="${ad}__${nn}"; [ -f "$J/out/$fid/cikis/_TAMAM" ] && { echo "[atla] $fid"; continue; }
    t0=$(date +%s); g=(); [ "$gr" = "1" ] && g=(--greedy)
    "$J/jordan" tek --video "$KLIP/cag_output${nn}.mp4" --film-id "$fid" \
      --model "$MODEL" --suzgec "$suz" --fps "$fps" --parca-sn "$psn" "${g[@]}" \
      >"$KOK/${fid}.log" 2>&1
    echo "[$ad] klip $nn — $(( $(date +%s) - t0 )) sn"
  done
done
echo; echo "=== SONUC ($TUR) ==="
{ for v in "${VARYANT[@]}"; do ad="${v%%|*}"
  for nn in "$@"; do
    gt="$J/olcum/gt/$nn/gt.txt"; ck="$J/out/${ad}__${nn}/cikis/jordan.txt"
    [ -f "$gt" ] && [ -f "$ck" ] || continue
    printf "%-22s klip %s  " "$ad" "$nn"
    "$J/venv/bin/python" "$J/olcum/puanla.py" "$ck" --gt "$gt" | "$J/venv/bin/python" -c \
"import sys,json;d=json.load(sys.stdin);print(f\"skor={d['skor']} recall={d['recall']} tr={d['tr_dogru']} uyd={d['uydurma_oran']} satir={d['okunan_satir']}\")"
  done; done; } | tee "$KOK/ozet.txt"
