#!/bin/bash
# ÖZET-LLM sunucusu (vLLM, metin) — start|stop|durum. vlm_sunucu.sh deseninin ikizi, AYRI PORT (8101).
# Neden vLLM: doğru chat template (ollama GGUF-import şablon hatası yok), sabit --max-model-len
# (ollama bağlamı kendi seçiyor), AWQ, sürekli toplu iş. Bake-off 2026-06-27 elemelerinin çoğu
# ollama/LM-Studio koşum hatasıydı — bu sunucu o sınıf hatayı ortadan kaldırır.
set -uo pipefail
export CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH HF_HOME=/opt/mitas/models/hf_cache

PORT="${MITAS_OZET_PORT:-8101}"
MODEL="${MITAS_OZET_MODEL:-qwen3-32b-awq}"
GPUUTIL="${MITAS_OZET_GPU_UTIL:-0.92}"
PIDF=/opt/mitas/kurulum/logs/ozet_sunucu.pid
LOGF=/opt/mitas/kurulum/logs/ozet_sunucu.log

case "$MODEL" in
  qwen3-32b-awq)
    SNAP=$(ls -d /opt/mitas/models/hf_cache/hub/models--QuantTrio--Qwen3-VL-32B-Instruct-AWQ/snapshots/*/ | head -1)
    # ÖLÇÜLDÜ (2026-07-30): AWQ ağırlık + görsel kule + aktivasyon ≈ 21.2 GB. util 0.92'de KV'ye
    # yalnız 1.39 GiB kalıyor, 16k bağlam 2.0 GiB istiyor → KALKMIYOR. util 0.95 + 12k bağlam ile
    # KV ihtiyacı ~1.5 GiB'a iner ve sığar. Parçalı hat çağrı başına ≤8k gördüğü için 12k yeter.
    # ÖLÇÜLEN GERÇEK: ağırlık+aktivasyon ≈ 20.3 GB. Masaüstü ~1.3 GB tuttuğu için 0.95 istemek
    # kartı aşıyor (22.24 boş < 22.38 istek). 0.94 → 22.15 GB bütçe → KV'ye ~1.85 GB kalır.
    # 10240 bağlam fp8 KV'de ~1.34 GB ister → rahat sığar. Parçalı hat en fazla ~5.2k görüyor.
    # --enforce-eager ZORUNLU: ağırlık 19.42 GiB yüklendikten sonra CUDA-graph yakalama
    # OOM veriyor (kartta 98 MiB kalıyor). vlm_sunucu.sh de aynı sebeple eager koşuyor.
    EK="--max-model-len 10240 --kv-cache-dtype fp8 --enforce-eager"; IHTIYAC=22000 ;;
  qwen3-8b)
    SNAP=$(ls -d /opt/mitas/models/hf_cache/hub/models--Qwen--Qwen3-8B/snapshots/*/ | head -1)
    # FP16 ~16 GB + 32k KV ~4.8 GB ≈ 21 GB → tek başına sığar, TEK-ATIŞ tam bağlam görebilir.
    EK="--max-model-len 32768"; IHTIYAC=21000 ;;
  qwen3-8b-4bit)
    SNAP=$(ls -d /opt/mitas/models/hf_cache/hub/models--Qwen--Qwen3-8B/snapshots/*/ | head -1)
    # PAYLAŞIMLI KART PROFİLİ: bitsandbytes 4-bit (~5.5 GB) + fp8 KV → ~10 GB'a sığar, başka
    # oturumların işini bozmadan koşar. Kuantalama kavramayı bir miktar düşürür — ama ŞEKİL
    # ekseninde (tek-atış vs parçalı) iki kol da AYNI modeli kullandığı için kıyas geçerli kalır.
    EK="--max-model-len 24576 --quantization bitsandbytes --kv-cache-dtype fp8"; IHTIYAC=11500 ;;
  *) echo "bilinmeyen MITAS_OZET_MODEL=$MODEL (qwen3-32b-awq | qwen3-8b | qwen3-8b-4bit)"; exit 2 ;;
esac

durum() { curl -s "http://127.0.0.1:$PORT/health" >/dev/null && echo CALISIYOR || echo KAPALI; }

case "${1:-durum}" in
  start)
    [ "$(durum)" = "CALISIYOR" ] && { echo "zaten çalışıyor (:$PORT)"; exit 0; }
    bos=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
    ihtiyac="${IHTIYAC:-21000}"
    if [ "$bos" -lt "$ihtiyac" ]; then
      echo "GPU'da $bos MiB boş, ~$ihtiyac MiB gerekli — BAŞLATMIYORUM."
      echo "Koşan işi bozmamak için önce onun bitmesini bekle (Prensip 2)."
      exit 3
    fi
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True nohup /opt/mitas/venvs/vllm/bin/vllm serve "$SNAP" \
      --served-model-name "$MODEL" --port "$PORT" \
      --gpu-memory-utilization "$GPUUTIL" $EK \
      > "$LOGF" 2>&1 &
    echo $! > "$PIDF"
    for i in $(seq 1 180); do
      curl -s "http://127.0.0.1:$PORT/health" >/dev/null && { echo "HAZIR (:$PORT, $MODEL)"; exit 0; }
      sleep 2
    done
    echo "KALKMADI — log: $LOGF"; tail -20 "$LOGF"; exit 1 ;;
  stop)
    [ -f "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null && rm -f "$PIDF" && echo "durduruldu" || echo "pid yok" ;;
  durum) durum ;;
  *) echo "kullanım: $0 start|stop|durum"; exit 2 ;;
esac
