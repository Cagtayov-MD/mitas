#!/bin/bash
# MP4-GİRDİ (parçalı): 4×100s jenerik mp4'ü video_url ile sunucuya verilir.
# Girdi = mp4 DOSYASI (örnekleme model tarafında); parçalama sadece context sınırı için.
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/16_vllm_mp4_parcali.log
exec > >(tee "$LOG") 2>&1
SNAP=$(ls -d /opt/mitas/models/hf_cache/hub/models--Qwen--Qwen2.5-VL-7B-Instruct/snapshots/*/ | head -1)
export CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH HF_HOME=/opt/mitas/models/hf_cache
PORT=8100

echo "=== vllm serve $(date) ==="
/opt/mitas/venvs/vllm/bin/vllm serve "$SNAP" \
  --served-model-name qwen2.5-vl-7b \
  --port $PORT --max-model-len 32768 --gpu-memory-utilization 0.85 \
  --enforce-eager --dtype float16 \
  --allowed-local-media-path /opt/mitas \
  --limit-mm-per-prompt '{"video": 1}' \
  --mm-processor-kwargs '{"max_pixels": 125440}' \
  --max-num-batched-tokens 20480 \
  > /opt/mitas/kurulum/logs/vllm_serve.log 2>&1 &
SRV=$!
for i in $(seq 1 120); do curl -s "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 2; done
curl -s "http://127.0.0.1:$PORT/health" >/dev/null || { echo "SUNUCU-KALKMADI"; kill $SRV 2>/dev/null; exit 1; }
echo "SUNUCU-HAZIR"

/opt/mitas/venvs/vllm/bin/python - <<'PYEOF'
import json, time, urllib.request

SONUC = ["# MP4-girdi jenerik okuma — Akıl Oyunları (4×100s parça, video_url)", ""]
for i in range(4):
    mp4 = f"/opt/mitas/outputs/jenerik_parca_{i}.mp4"
    payload = {
        "model": "qwen2.5-vl-7b", "temperature": 0, "max_tokens": 4000,
        "messages": [{"role": "user", "content": [
            {"type": "video_url", "video_url": {"url": f"file://{mp4}"}},
            {"type": "text", "text": ("Bu bir film kapanış jeneriği (end credits) parçası. Görünen TÜM "
                                       "isimleri ve unvanları sırasıyla, AYNEN listele. Uydurma; okuyamadığını atla.")}
        ]}]
    }
    req = urllib.request.Request("http://127.0.0.1:8100/v1/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t = time.time()
    try:
        r = json.load(urllib.request.urlopen(req, timeout=1800))
        su = time.time() - t
        u = r.get("usage", {})
        m = r["choices"][0]["message"]["content"]
        print(f"PARCA {i}: {su:.1f}s prompt={u.get('prompt_tokens')} cikti={u.get('completion_tokens')}")
        SONUC.append(f"\n## Parça {i+1} (t={i*100}-{i*100+100}s) — {su:.1f}s, prompt {u.get('prompt_tokens')} tok\n")
        SONUC.append(m)
    except Exception as e:  # noqa: BLE001
        print(f"PARCA {i}: HATA {type(e).__name__}: {str(e)[:150]}")
        SONUC.append(f"\n## Parça {i+1}: HATA {type(e).__name__}")

open("/opt/mitas/outputs/JENERIK_MP4_GIRDI_SONUC.md", "w", encoding="utf-8").write("\n".join(SONUC) + "\n")
print("RAPOR: /opt/mitas/outputs/JENERIK_MP4_GIRDI_SONUC.md")
PYEOF
kill $SRV 2>/dev/null; sleep 3
echo "PARCALI-TEST-TAMAM $(date)"
