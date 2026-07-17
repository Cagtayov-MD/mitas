#!/bin/bash
# 30B-VL final denemesi: max_pixels 100352 (video ~10k tok) + 12288 len — iki 30s klip
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/19c_30b.log
exec > >(tee "$LOG") 2>&1
export CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH HF_HOME=/opt/mitas/models/hf_cache
PORT=8100
RAPOR=/opt/mitas/outputs/VL_KIYAS_JENERIK_20260716.md
SORU="Bu bir film kapanış jeneriği. Her kartta genelde KÜÇÜK puntolu bir rol etiketi (örn. 'Directed by', 'Executive Producers') ve BÜYÜK puntolu isim vardır. Her kartı 'ETİKET: İSİM' biçiminde yaz — küçük yazıları da MUTLAKA oku. Etiket YOKSA etiket uydurma, sadece ismi yaz."
S30=$(ls -d /opt/mitas/models/hf_cache/hub/models--QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ/snapshots/*/ | head -1)

PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /opt/mitas/venvs/vllm/bin/vllm serve "$S30" \
  --served-model-name kiyas --port $PORT \
  --max-model-len 13440 --gpu-memory-utilization 0.90 \
  --enforce-eager --trust-remote-code \
  --allowed-local-media-path /opt/mitas --limit-mm-per-prompt '{"video": 1}' \
  --max-num-batched-tokens 13440 --mm-processor-kwargs '{"max_pixels": 100352}' \
  > /opt/mitas/kurulum/logs/vllm_serve_30B_final.log 2>&1 &
SRV=$!
for i in $(seq 1 180); do curl -s "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 2; done
curl -s "http://127.0.0.1:$PORT/health" >/dev/null || { echo "30B: SUNUCU-KALKMADI"; kill $SRV; exit 1; }
echo SUNUCU-HAZIR
for P in a b; do
  SORU="$SORU" P="$P" RAPOR="$RAPOR" /opt/mitas/venvs/vllm/bin/python - <<'PYEOF'
import json, os, time, urllib.request
soru, p, rapor = os.environ["SORU"], os.environ["P"], os.environ["RAPOR"]
mp4 = f"/opt/mitas/outputs/jenerik_rol_{p}.mp4"
payload = {"model": "kiyas", "temperature": 0, "max_tokens": 1500,
           "messages": [{"role": "user", "content": [
               {"type": "video_url", "video_url": {"url": f"file://{mp4}"}},
               {"type": "text", "text": soru}]}]}
req = urllib.request.Request("http://127.0.0.1:8100/v1/chat/completions",
                             data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
t = time.time()
try:
    r = json.load(urllib.request.urlopen(req, timeout=1800))
    su = time.time() - t
    m = r["choices"][0]["message"]["content"]
    u = r.get("usage", {})
    print(f"30B-{p}: {su:.1f}s prompt={u.get('prompt_tokens')} cikti={u.get('completion_tokens')}")
    open(rapor, "a", encoding="utf-8").write(f"\n## Qwen3-VL-30B-AWQ (gerçek mp4, 30s-{p}, 376px) — {su:.1f}s\n\n{m}\n")
except Exception as e:  # noqa: BLE001
    print(f"30B-{p}: HATA {type(e).__name__}: {str(e)[:150]}")
    open(rapor, "a", encoding="utf-8").write(f"\n## Qwen3-VL-30B-AWQ 30s-{p}: HATA {type(e).__name__}: {str(e)[:150]}\n")
PYEOF
done
kill $SRV 2>/dev/null; sleep 5
echo "30B-FINAL-TAMAM $(date)"
