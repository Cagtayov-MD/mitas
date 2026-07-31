#!/bin/bash
# ÖLÇÜM YATAĞI'na özel vLLM sunucusu — kurulum/vlm_sunucu.sh'e DOKUNMAZ.
#
# NEDEN AYRI: üretim betiği `--limit-mm-per-prompt '{"video": 1}'` ile açıyor.
# Master bantları GÖRÜNTÜ (video değil) → o bayrakla reddedilir. Burada
# `{"video":1,"image":N}` veriyoruz. Çalıştığı kanıtlanınca üretim betiğine
# eklenmesi AYRI bir karar (Çağatay'a sorulacak) — önce sor sonra dokun.
#
# Ayrıca ölçüm portu farklı (8110) ki üretimin 8100'ü ile çakışmasın.
#
# KULLANIM:
#   bash scripts/olcum_vllm.sh start    # kaldır (ollama'yı boşaltır)
#   bash scripts/olcum_vllm.sh durum
#   bash scripts/olcum_vllm.sh stop
#   bash scripts/olcum_vllm.sh sina     # görüntü kabul ediyor mu — tek çağrı
set -u

PORT="${OLCUM_VLLM_PORT:-8110}"
GPUUTIL="${OLCUM_VLLM_GPU_UTIL:-0.85}"
MAXPX="${OLCUM_VLLM_MAX_PIXELS:-1003520}"   # master bantları büyük: 1100px yükseklik
IMGN="${OLCUM_VLLM_IMAGE_N:-4}"
KOK=/opt/mitas/outputs/olcum_yatagi
LOGF="$KOK/vllm.log"
PIDF="$KOK/vllm.pid"
mkdir -p "$KOK"

SNAP=$(ls -d /opt/mitas/models/hf_cache/hub/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/*/ 2>/dev/null | head -1)

case "${1:-durum}" in
  start)
    if curl -s -m 3 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
      echo "ZATEN AYAKTA (:$PORT)"; exit 0
    fi
    [ -z "$SNAP" ] && { echo "HATA: Qwen3-VL-8B snapshot bulunamadı"; exit 2; }
    # Ollama'daki modelleri boşalt — toplu fazda kart tek modelin olmalı
    for m in $(curl -s -m 5 http://127.0.0.1:11434/api/ps 2>/dev/null \
               | python3 -c "import sys,json;print(' '.join(x['name'] for x in (json.load(sys.stdin).get('models') or [])))" 2>/dev/null); do
      curl -s -m 10 http://127.0.0.1:11434/api/generate \
        -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null 2>&1
      echo "  ollama boşaltıldı: $m"
    done
    sleep 3
    echo "vLLM kalkıyor: port=$PORT gpu_util=$GPUUTIL image_n=$IMGN max_pixels=$MAXPX"
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
      nohup /opt/mitas/venvs/vllm/bin/vllm serve "$SNAP" \
      --served-model-name qwen3-vl-8b --port "$PORT" \
      --max-model-len 16384 --gpu-memory-utilization "$GPUUTIL" \
      --enforce-eager --allowed-local-media-path /opt/mitas \
      --limit-mm-per-prompt "{\"video\": 1, \"image\": $IMGN}" \
      --mm-processor-kwargs "{\"max_pixels\": $MAXPX}" \
      --max-num-batched-tokens 16384 \
      > "$LOGF" 2>&1 &
    echo $! > "$PIDF"
    for i in $(seq 1 180); do
      curl -s -m 3 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && {
        echo "HAZIR (:$PORT, qwen3-vl-8b) — $((i*2)) sn"; exit 0; }
      sleep 2
    done
    echo "KALKMADI (360 sn) — log: $LOGF"; tail -25 "$LOGF"; exit 1 ;;

  stop)
    [ -f "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null && echo "durduruldu"
    [ -f "$PIDF" ] && rm -f "$PIDF"
    pkill -f "[v]llm serve.*$PORT" 2>/dev/null || true
    echo "temiz" ;;

  durum)
    curl -s -m 5 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 \
      && { echo "CALISIYOR (:$PORT)"; curl -s -m 5 "http://127.0.0.1:$PORT/v1/models"; echo; } \
      || echo "KAPALI (:$PORT)" ;;

  sina)
    # GÖRÜNTÜ KABUL SINAVI — asıl bilinmez bu. Reddederse hata metni görünür.
    IMG="${2:-}"
    if [ -z "$IMG" ]; then
      IMG=$(ls "$KOK"/klipler/*/reading_master_runaware.png 2>/dev/null | head -1)
    fi
    [ -z "$IMG" ] && { echo "HATA: sınanacak görüntü yok"; exit 2; }
    echo "sınanan: $IMG"
    python3 - "$IMG" "$PORT" <<'PY'
import base64, json, sys, urllib.request, urllib.error
img, port = sys.argv[1], sys.argv[2]
b64 = base64.b64encode(open(img, "rb").read()).decode()
gov = {"model": "qwen3-vl-8b", "temperature": 0.0, "max_tokens": 400,
       "messages": [{"role": "user", "content": [
           {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
           {"type": "text", "text": "Free OCR."}]}]}
req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
                             data=json.dumps(gov).encode(),
                             headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=300) as r:
        j = json.loads(r.read())
    icerik = (((j.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
    print("=== GÖRÜNTÜ KABUL EDİLDİ ===")
    print(icerik[:1200])
except urllib.error.HTTPError as e:
    print("=== REDDEDİLDİ ===", e.code)
    print(e.read().decode(errors="replace")[:1200])
except Exception as e:
    print("=== HATA ===", type(e).__name__, str(e)[:500])
PY
    ;;
  *) echo "kullanım: $0 start|stop|durum|sina [görüntü]"; exit 2 ;;
esac
