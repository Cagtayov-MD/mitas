#!/bin/bash
# run_all.sh <stage:1|2|slice|vl> [model] [backend] [base_url]
# 51 filmi verilen aşamadan geçirir. Resumable: o aşama state'te varsa atlar.
# GPU-seri aşamalar (1, vl) sıralı; CPU aşamalar (2, slice) sıralı (cv2 zaten çok-çekirdek).
set -uo pipefail
cd /opt/mitas
source /opt/mitas/harness/env.sh
STAGE="${1:?stage gerekli}"; MODEL="${2:-qwen2.5vl:7b}"; BACKEND="${3:-ollama}"; BASE="${4:-}"
STATE_DIR="$MITAS_RUN_ROOT/state"
mapfile -t FILMS < <(ls "$FILMS_DIR"/*.mp4 "$FILMS_DIR"/*.mxf 2>/dev/null | sort)
echo "[run_all] stage=$STAGE model=$MODEL film=${#FILMS[@]}"
START_TS=$(date +%s)
MODEL_BUDGET="${MODEL_BUDGET:-4200}"   # vl: model başına süre tavanı (sn, 70dk); yavaş model zinciri tıkamasın
# AĞIR-MODEL KISITI (Çağatay 2026-07-17): 27-35B'ler pratik-okumada kullanılmaz → yalnız TADIM.
# 5 film + 25dk toplam + film-başı 10dk kesme. Env ile override edilmezse ada göre otomatik.
FILM_CAP="${FILM_CAP:-0}"; PERFILM_TIMEOUT="${PERFILM_TIMEOUT:-2400}"
case "$MODEL" in
  *:30b*|*:32b*|*:35b*|*36-27b*|qwen36-35b*|qwen2.5vl:32b*)
    [ "$FILM_CAP" = 0 ] && FILM_CAP=5
    MODEL_BUDGET=1500; PERFILM_TIMEOUT=600
    echo "[ağır-tadım] $MODEL: FILM_CAP=$FILM_CAP budget=${MODEL_BUDGET}s perfilm=${PERFILM_TIMEOUT}s" ;;
esac
i=0; done_count=0
for f in "${FILMS[@]}"; do
  i=$((i+1))
  if [ "$STAGE" = vl ]; then
    EL=$(( $(date +%s) - START_TS ))
    if [ "$EL" -gt "$MODEL_BUDGET" ]; then echo "[budget] $MODEL süre doldu (${EL}s > ${MODEL_BUDGET}s), kalan $(( ${#FILMS[@]} - i + 1 )) film atlanıyor"; break; fi
    if [ "$FILM_CAP" != 0 ] && [ "$done_count" -ge "$FILM_CAP" ]; then echo "[film-cap] $MODEL: $FILM_CAP film tadım tamam, kalan atlanıyor"; break; fi
  fi
  id=$(basename "${f%.*}")
  st="$STATE_DIR/$id.json"
  # resumability: aşama tamamlandıysa atla
  skip=0
  if [ -f "$st" ]; then
    case "$STAGE" in
      1)     grep -q '"stage1"' "$st" && skip=1 ;;
      2)     grep -q '"stage2"' "$st" && skip=1 ;;
      slice) grep -q '"slice"'  "$st" && skip=1 ;;
      vl)    grep -q "\"$MODEL\"" "$st" && skip=1 ;;
    esac
  fi
  if [ "$skip" = 1 ]; then echo "[$i/${#FILMS[@]}] SKIP $id"; continue; fi
  echo "[$i/${#FILMS[@]}] $STAGE :: $id"
  args=(--film "$f" --stage "$STAGE")
  if [ "$STAGE" = vl ]; then args+=(--model "$MODEL" --backend "$BACKEND"); [ -n "$BASE" ] && args+=(--base "$BASE"); fi
  timeout "$PERFILM_TIMEOUT" "$PY_OCR" "$HARNESS/kunye_stages.py" "${args[@]}" 2>&1 | tail -1
  done_count=$((done_count+1))
done
echo "[run_all] stage=$STAGE DONE"
