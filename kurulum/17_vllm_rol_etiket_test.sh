#!/bin/bash
# ROL-ETİKETİ deneyi: parça-0'ı (a) yüksek max_pixels (b) etiket-koruyan prompt ile yeniden oku.
# Hipotez: "Directed by/Executive Producers" küçük puntoları 420px'te siliniyor + liste-prompt'u isimlere indirgiyor.
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/17_rol_etiket.log
exec > >(tee "$LOG") 2>&1
SNAP=$(ls -d /opt/mitas/models/hf_cache/hub/models--Qwen--Qwen2.5-VL-7B-Instruct/snapshots/*/ | head -1)
export CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH HF_HOME=/opt/mitas/models/hf_cache
PORT=8100

PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /opt/mitas/venvs/vllm/bin/vllm serve "$SNAP" \
  --served-model-name qwen2.5-vl-7b \
  --port $PORT --max-model-len 32768 --gpu-memory-utilization 0.90 \
  --enforce-eager --dtype float16 \
  --allowed-local-media-path /opt/mitas \
  --limit-mm-per-prompt '{"video": 1}' \
  --mm-processor-kwargs '{"max_pixels": 125440}' \
  --max-num-batched-tokens 20480 \
  > /opt/mitas/kurulum/logs/vllm_serve.log 2>&1 &
SRV=$!
for i in $(seq 1 120); do curl -s "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 2; done
curl -s "http://127.0.0.1:$PORT/health" >/dev/null || { echo "SUNUCU-KALKMADI"; kill $SRV 2>/dev/null; exit 1; }
echo "SUNUCU-HAZIR (max_pixels=235200)"

/opt/mitas/venvs/vllm/bin/python - <<'PYEOF'
import json, time, urllib.request
payload = {
  "model": "qwen2.5-vl-7b", "temperature": 0, "max_tokens": 3000,
  "messages": [{"role": "user", "content": [
    {"type": "video_url", "video_url": {"url": "file:///opt/mitas/outputs/jenerik_rol_test.mp4"}},
    {"type": "text", "text": ("Bu bir film kapanış jeneriği. Her kartta genelde KÜÇÜK puntolu bir rol "
                               "etiketi (örn. 'Directed by', 'Executive Producers') ve BÜYÜK puntolu isim "
                               "vardır. Her kartı 'ETİKET: İSİM' biçiminde yaz — küçük yazıları da MUTLAKA "
                               "oku. Etiket yoksa sadece ismi yaz. Uydurma.")}
  ]}]
}
req = urllib.request.Request("http://127.0.0.1:8100/v1/chat/completions",
                             data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
t = time.time()
r = json.load(urllib.request.urlopen(req, timeout=1800))
u = r.get("usage", {})
print(f"SURE={time.time()-t:.1f}s prompt={u.get('prompt_tokens')} cikti={u.get('completion_tokens')}")
print("=" * 60)
print(r["choices"][0]["message"]["content"])
PYEOF
kill $SRV 2>/dev/null; sleep 3
echo "ROL-ETIKET-TEST-TAMAM"
