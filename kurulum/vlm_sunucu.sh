#!/bin/bash
# VIDEO-VL sunucusu (Qwen3-VL-8B, kanıtlı profil) — start|stop|durum
# NOT: GPU'yu ollama'yla paylaşır; start önce yüklü ollama modellerini boşaltır (ASR-subap emsali).
set -uo pipefail
export CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH HF_HOME=/opt/mitas/models/hf_cache
PORT="${MITAS_VIDEO_VL_PORT:-8100}"
# GPU payı: varsayılan 0.90 (kanıtlı profil). GPU'da başka iş varken geçici düşürmek için
# MITAS_VLLM_GPU_UTIL=0.85 gibi ver (2026-07-23, test_film koşusu — davranış değişikliği yok).
GPUUTIL="${MITAS_VLLM_GPU_UTIL:-0.90}"
# Kare piksel tavanı: varsayılan 125440 (kanıtlı profil). Süre/çözünürlük deneyleri için
# MITAS_VLLM_MAX_PIXELS ile geçici değiştirilebilir (2026-07-24) — davranış değişikliği yok.
MAXPX="${MITAS_VLLM_MAX_PIXELS:-125440}"
PIDF=/opt/mitas/kurulum/logs/vlm_sunucu.pid
LOGF=/opt/mitas/kurulum/logs/vlm_sunucu.log
SNAP=$(ls -d /opt/mitas/models/hf_cache/hub/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/*/ | head -1)

# DURUM KONTROLÜ — iki kusur düzeltildi (2026-08-01):
#  (1) `curl -s` HTTP 404'te de EXIT 0 döner (404 "başarılı HTTP işlemi"dir) →
#      eski kontrol sunucu HİÇ YOKKEN bile CALISIYOR diyordu. `-f` şart.
#  (2) Porta BAŞKASI oturmuş olabilir: 8100'ü bu makinede docker container
#      `odysseus-chromadb-1` tutuyor → /health 404 dönüyor ama port dinleniyor.
#      Bu yüzden vLLM'in GERÇEK imzası aranır: /v1/models JSON'unda "data".
#      Sonuç: video-VL sunucusu AYLARDIR hiç başlayamıyordu (start "zaten
#      çalışıyor" deyip çıkıyordu) ve kimse fark etmemişti.
durum() {
  if curl -sf -m 3 "http://127.0.0.1:$PORT/v1/models" 2>/dev/null | grep -q '"data"'; then
    echo CALISIYOR
  else
    echo KAPALI
  fi
}

# Portu BAŞKASI mı tutuyor? (bizim sunucumuz değil ama dinleyen var)
port_yabanci() {
  [ "$(durum)" = "CALISIYOR" ] && return 1
  ss -tln 2>/dev/null | grep -q ":$PORT " && return 0 || return 1
}

case "${1:-durum}" in
  start)
    [ "$(durum)" = "CALISIYOR" ] && { echo "zaten çalışıyor"; exit 0; }
    if port_yabanci; then
      echo "RED: port $PORT DİNLENİYOR ama vLLM DEĞİL (başka süreç/container tutuyor)."
      ss -tlnp 2>/dev/null | grep ":$PORT " | sed 's/^/     /'
      echo "     Çözüm: MITAS_VIDEO_VL_PORT=<boş port> ile başlat, ya da o süreci durdur."
      exit 1
    fi
    # ollama'daki yüklü modelleri boşalt (VRAM çakışması olmasın)
    for m in $(curl -s http://127.0.0.1:11434/api/ps 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(' '.join(x['name'] for x in d.get('models',[])))" 2>/dev/null); do
      curl -s http://127.0.0.1:11434/api/generate -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null 2>&1 || true
      echo "ollama boşaltıldı: $m"
    done
    sleep 3
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True nohup /opt/mitas/venvs/vllm/bin/vllm serve "$SNAP" \
      --served-model-name qwen3-vl-8b --port "$PORT" \
      --max-model-len 16384 --gpu-memory-utilization "$GPUUTIL" \
      --enforce-eager --allowed-local-media-path /opt/mitas \
      --limit-mm-per-prompt '{"video": 1}' \
      --mm-processor-kwargs "{\"max_pixels\": $MAXPX}" \
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
