#!/bin/bash
# MP4-GİRDİ testi: vLLM OpenAI sunucusu + video_url ile DOSYA olarak jenerik verme.
# Kare seçimini biz DEĞİL, modelin kendi işlemcisi yapar (fps=1.0 mm-processor ayarı).
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/15_vllm_mp4_girdi.log
exec > >(tee "$LOG") 2>&1
SNAP=$(ls -d /opt/mitas/models/hf_cache/hub/models--Qwen--Qwen2.5-VL-7B-Instruct/snapshots/*/ | head -1)
export CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH HF_HOME=/opt/mitas/models/hf_cache
PORT=8100
MP4=/opt/mitas/outputs/jenerik_kesit_akiloyunlari.mp4

echo "=== vllm serve başlıyor (video_url modu) $(date) ==="
/opt/mitas/venvs/vllm/bin/vllm serve "$SNAP" \
  --served-model-name qwen2.5-vl-7b \
  --port $PORT --max-model-len 32768 --gpu-memory-utilization 0.85 \
  --enforce-eager --dtype float16 \
  --allowed-local-media-path /opt/mitas \
  --limit-mm-per-prompt '{"video": 1}' \
  --mm-processor-kwargs '{"max_pixels": 125440}' \
  --media-io-kwargs '{"video": {"num_frames": 120}}' \
  > /opt/mitas/kurulum/logs/vllm_serve.log 2>&1 &
SRV=$!
for i in $(seq 1 120); do curl -s "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 2; done
curl -s "http://127.0.0.1:$PORT/health" >/dev/null || { echo "SUNUCU-KALKMADI"; kill $SRV 2>/dev/null; exit 1; }
echo "SUNUCU-HAZIR"

echo "=== mp4 dosyası video_url olarak veriliyor ==="
/opt/mitas/venvs/vllm/bin/python - <<PYEOF
import json, time, urllib.request
payload = {
  "model": "qwen2.5-vl-7b",
  "temperature": 0,
  "max_tokens": 6000,
  "messages": [{
    "role": "user",
    "content": [
      {"type": "video_url", "video_url": {"url": "file://$MP4"}},
      {"type": "text", "text": "Bu bir film kapanış jeneriği (end credits). Görünen TÜM isimleri ve unvanları sırasıyla, AYNEN listele. Uydurma; okuyamadığını atla."}
    ]
  }]
}
req = urllib.request.Request("http://127.0.0.1:$PORT/v1/chat/completions",
    data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
t = time.time()
r = json.load(urllib.request.urlopen(req, timeout=1800))
su = time.time() - t
u = r.get("usage", {})
print(f"SURE={su:.1f}s prompt_tokens={u.get('prompt_tokens')} completion_tokens={u.get('completion_tokens')}")
metin = r["choices"][0]["message"]["content"]
open("/opt/mitas/outputs/JENERIK_MP4_GIRDI_SONUC.md", "w", encoding="utf-8").write(
    f"# MP4-girdi jenerik okuma (video_url, fps=1.0 model-tarafı örnekleme)\\n\\n"
    f"Süre: {su:.1f}s · prompt {u.get('prompt_tokens')} tok · üretim {u.get('completion_tokens')} tok\\n\\n" + metin + "\\n")
print("=" * 60)
print(metin[:2500])
PYEOF
echo "=== sunucu kapatılıyor ==="
kill $SRV 2>/dev/null; sleep 3
echo "MP4-GIRDI-TEST-TAMAM $(date)"
