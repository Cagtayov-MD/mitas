#!/bin/bash
# VIDEO-VL sunucusu (Qwen3-VL-8B, kanıtlı profil) — start|stop|durum
# NOT: GPU'yu ollama'yla paylaşır; start önce yüklü ollama modellerini boşaltır (ASR-subap emsali).
set -uo pipefail
export CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH HF_HOME=/opt/mitas/models/hf_cache
PORT="${MITAS_VIDEO_VL_PORT:-8100}"
PIDF=/opt/mitas/kurulum/logs/vlm_sunucu.pid
LOGF=/opt/mitas/kurulum/logs/vlm_sunucu.log
SNAP=$(ls -d /opt/mitas/models/hf_cache/hub/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/*/ | head -1)

durum() { curl -s "http://127.0.0.1:$PORT/health" >/dev/null && echo CALISIYOR || echo KAPALI; }

case "${1:-durum}" in
  start)
    [ "$(durum)" = "CALISIYOR" ] && { echo "zaten çalışıyor"; exit 0; }
    # ollama'daki yüklü modelleri boşalt (VRAM çakışması olmasın)
    for m in $(curl -s http://127.0.0.1:11434/api/ps 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(' '.join(x['name'] for x in d.get('models',[])))" 2>/dev/null); do
      curl -s http://127.0.0.1:11434/api/generate -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null 2>&1 || true
      echo "ollama boşaltıldı: $m"
    done
    sleep 3
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True nohup /opt/mitas/venvs/vllm/bin/vllm serve "$SNAP" \
      --served-model-name qwen3-vl-8b --port "$PORT" \
      --max-model-len 16384 --gpu-memory-utilization 0.90 \
      --enforce-eager --allowed-local-media-path /opt/mitas \
      --limit-mm-per-prompt '{"video": 1}' \
      --mm-processor-kwargs '{"max_pixels": 125440}' \
      --max-num-batched-tokens 16384 \
      > "$LOGF" 2>&1 &
    echo $! > "$PIDF"
    for i in $(seq 1 120); do curl -s "http://127.0.0.1:$PORT/health" >/dev/null && { echo "HAZIR (:$PORT, qwen3-vl-8b)"; exit 0; }; sleep 2; done
    echo "KALKMADI — log: $LOGF"; exit 1 ;;
  stop)
    [ -f "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null && rm -f "$PIDF"
    pkill -f "[v]llm serve.*$PORT" 2>/dev/null || true
    sleep 3; echo "durduruldu ($(durum))" ;;
  durum|*) durum ;;
esac
