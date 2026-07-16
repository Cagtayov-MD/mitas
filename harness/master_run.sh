#!/bin/bash
# master_run.sh — MITAS künye 51-film OTONOM yürütme zinciri (garanti çekirdek).
# stage1(bekle) -> stage2 -> slice -> VL(ollama çekirdek roster) -> her adımda temel rapor.
# Robust: set -u ama pipefail YOK (tek film hatası zinciri durdurmaz). Her adım loglanır + flag.
set -u
H=/opt/mitas/harness
source "$H/env.sh"
RUN=$MITAS_RUN_ROOT
LOG=$RUN/logs; mkdir -p "$LOG"
ML=$LOG/master.log
mark(){ echo "$(date '+%m-%d %H:%M:%S') | $*" | tee -a "$ML"; }
basic(){ "$PY_OCR" "$H/report_basic.py" >> "$LOG/report_basic.log" 2>&1; }

mark "MASTER BAŞLADI"

# --- E1: stage-1 bulk bitişini bekle (ayrı iş) ---
mark "E1: stage-1 bulk bekleniyor"
for i in $(seq 1 240); do   # max ~2h
  grep -q 'stage=1 DONE' "$LOG/stage1_bulk.log" 2>/dev/null && break
  sleep 30
done
mark "E1: stage-1 bitti (state: $(ls $RUN/state/*.json 2>/dev/null | wc -l)/51)"
basic

# --- ollama pulls bitişini bekle (VL'den önce) ---
mark "pulls bekleniyor"
for i in $(seq 1 120); do   # max ~1h
  grep -q 'ALL PULLS DONE' "$LOG/ollama_pull.log" 2>/dev/null && break
  sleep 30
done
mark "pulls durumu: $(grep -E 'OK|FAIL' $LOG/ollama_pull.log 2>/dev/null | tr '\n' ' ')"

# --- E2: stage-2 (master png) ---
mark "E2: stage-2 başladı"
bash "$H/run_all.sh" 2 >> "$LOG/stage2_bulk.log" 2>&1
mark "E2: stage-2 bitti"
basic

# --- E3: slice ---
mark "E3: slice başladı"
bash "$H/run_all.sh" slice >> "$LOG/slice_bulk.log" 2>&1
mark "E3: slice bitti"
basic

run_vl_model(){  # $1=model $2=faz-etiketi
  local m="$1" tag="$2"
  if ! ollama show "$m" >/dev/null 2>&1; then mark "$tag: SKIP $m (ollama'da yok)"; return; fi
  mark "$tag: VL $m başladı"
  local slug; slug=$(echo "$m" | tr -c 'a-zA-Z0-9' '_')
  bash "$H/run_all.sh" vl "$m" ollama >> "$LOG/vl_${slug}.log" 2>&1
  mark "$tag: VL $m bitti"
  basic
}

# --- E4: VL — ollama ÇEKİRDEK (önem+hız sırası; eksik model ollama show ile atlanır) ---
# baseline -> hızlı dense -> OCR uzmanları -> user-key MoE -> user-key dense-27
CORE_MODELS=(qwen2.5vl:7b qwen3-vl:8b glm-ocr:latest deepseek-ocr:latest qwen3-vl:30b qwen36-27b-test)
for m in "${CORE_MODELS[@]}"; do run_vl_model "$m" "E4"; done
mark "ÇEKİRDEK VL TAMAM"
touch "$RUN/CORE_DONE.flag"

# --- E5: STRETCH ollama (best-effort, yavaş/sıkı; çekirdeği bloklamaz) ---
STRETCH_MODELS=(minicpm-v:latest qwen3-vl:32b qwen36-35b-test)
for m in "${STRETCH_MODELS[@]}"; do run_vl_model "$m" "E5"; done

mark "TÜM OLLAMA VL TAMAM"
touch "$RUN/ALL_DONE.flag"
mark "MASTER BİTTİ"
