#!/bin/bash
# TELAFİ TURU: (A) KV-cache'ten düşen vLLM modelleri --max-model-len 16384 ile
#             (B) ollama doğru-ayar turu: glm(varsayılan-fren), deepseek(Free OCR.), minicpm(kare-başına)
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/18c_telafi.log
exec > >(tee "$LOG") 2>&1
export CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH HF_HOME=/opt/mitas/models/hf_cache
PORT=8100
MP4=/opt/mitas/outputs/jenerik_rol_test.mp4
RAPOR=/opt/mitas/outputs/VL_KIYAS_JENERIK_20260716.md
SORU="Bu bir film kapanış jeneriği. Her kartta genelde KÜÇÜK puntolu bir rol etiketi (örn. 'Directed by', 'Executive Producers') ve BÜYÜK puntolu isim vardır. Her kartı 'ETİKET: İSİM' biçiminde yaz — küçük yazıları da MUTLAKA oku. Etiket YOKSA etiket uydurma, sadece ismi yaz."

vllm_oku() { local SNAP="$1" AD="$2" EKSTRA="$3"
  echo "===== [vLLM-16k] $AD $(date +%H:%M) ====="
  # shellcheck disable=SC2086
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /opt/mitas/venvs/vllm/bin/vllm serve "$SNAP" \
    --served-model-name kiyas --port $PORT \
    --max-model-len 16384 --gpu-memory-utilization 0.90 \
    --enforce-eager --trust-remote-code \
    --allowed-local-media-path /opt/mitas --limit-mm-per-prompt '{"video": 1}' \
    --max-num-batched-tokens 16384 $EKSTRA \
    > /opt/mitas/kurulum/logs/vllm_serve_${AD}_16k.log 2>&1 &
  local SRV=$!; local OK=0
  for i in $(seq 1 180); do curl -s "http://127.0.0.1:$PORT/health" >/dev/null && { OK=1; break; }; sleep 2; done
  if [ "$OK" = "0" ]; then
    echo "$AD: SUNUCU-KALKMADI(16k)"; echo -e "\n## $AD (vLLM 16k)\nSUNUCU KALKMADI" >> "$RAPOR"
    kill $SRV 2>/dev/null; sleep 5; return
  fi
  SORU="$SORU" MP4="$MP4" AD="$AD" RAPOR="$RAPOR" /opt/mitas/venvs/vllm/bin/python - <<'PYEOF'
import json, os, time, urllib.request
soru, mp4, ad, rapor = os.environ["SORU"], os.environ["MP4"], os.environ["AD"], os.environ["RAPOR"]
payload = {"model": "kiyas", "temperature": 0, "max_tokens": 2500,
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
    print(f"{ad}: {su:.1f}s prompt={u.get('prompt_tokens')} cikti={u.get('completion_tokens')}")
    open(rapor, "a", encoding="utf-8").write(f"\n## {ad} (vLLM 16k, gerçek mp4, 60s) — {su:.1f}s\n\n{m}\n")
except Exception as e:  # noqa: BLE001
    print(f"{ad}: HATA {type(e).__name__}: {str(e)[:150]}")
    open(rapor, "a", encoding="utf-8").write(f"\n## {ad} (vLLM 16k): HATA {type(e).__name__}: {str(e)[:200]}\n")
PYEOF
  kill $SRV 2>/dev/null; sleep 8
}

H=/opt/mitas/models/hf_cache/hub
QW='--mm-processor-kwargs {"max_pixels":125440}'
# Düşenler buraya (tur sonunda güncellenir):
vllm_oku "$(ls -d $H/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/*/ | head -1)"               "Qwen3-VL-8B"          "$QW"
vllm_oku "$(ls -d $H/models--QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ/snapshots/*/ | head -1)"  "Qwen3-VL-30B-A3B-AWQ" "$QW"
vllm_oku "$(ls -d $H/models--QuantTrio--Qwen3-VL-32B-Instruct-AWQ/snapshots/*/ | head -1)"      "Qwen3-VL-32B-AWQ"     "$QW"
EXTRA_LIST="${TELAFI_EK:-}"
for AD in $EXTRA_LIST; do
  case "$AD" in
    InternVL3_5-8B)      vllm_oku "$(ls -d $H/models--OpenGVLab--InternVL3_5-8B/snapshots/*/ | head -1)" "$AD" "" ;;
    Nemotron-12B-VL-FP8) vllm_oku "$(ls -d $H/models--nvidia--NVIDIA-Nemotron-Nano-12B-v2-VL-FP8/snapshots/*/ | head -1)" "$AD" "" ;;
    MiniCPM-V-4.5)       vllm_oku "$(ls -d $H/models--openbmb--MiniCPM-V-4_5/snapshots/*/ | head -1)" "$AD" "" ;;
    GLM-4.1V-9B)         vllm_oku "$(ls -d $H/models--zai-org--GLM-4.1V-9B-Thinking/snapshots/*/ | head -1)" "$AD" "" ;;
  esac
done

echo "===== [B] ollama doğru-ayar turu ====="
RAPOR="$RAPOR" /opt/mitas/venvs/vllm/bin/python - <<'PYEOF'
import base64, json, os, time, urllib.request
rapor = os.environ["RAPOR"]
kareler = [base64.b64encode(open(f"/tmp/claude-1000/kiyas_{i}.jpg", "rb").read()).decode() for i in range(12)]

def sor(model, icerik, imgs, opts, timeout=900):
    payload = {"model": model, "stream": False, "think": False, "options": opts,
               "messages": [{"role": "user", "content": icerik, "images": imgs}]}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
                                 data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=timeout))
    return (r.get("message", {}).get("content") or "").strip()

def bosalt(model):
    try:
        urllib.request.urlopen(urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps({"model": model, "keep_alive": 0}).encode(),
            headers={"Content-Type": "application/json"}), timeout=60)
    except Exception:
        pass

# glm-ocr: VARSAYILAN fren (repeat_penalty gönderme!) + kare-başına
t = time.time(); parca = []
for ki, k in enumerate(kareler):
    mtn = sor("glm-ocr:latest", "Bu bir film jeneriği karesi. Ekrandaki metni oldugu gibi, satir satir oku.",
              [k], {"temperature": 0, "num_predict": 1024})
    parca.append(f"--- Kare {ki+1} ---\n{mtn}")
print(f"glm-ocr(fix): {time.time()-t:.1f}s, {sum(len(p) for p in parca)} karakter")
open(rapor, "a", encoding="utf-8").write(f"\n## glm-ocr (DOĞRU ayar: varsayılan-fren, kare-başına) — {time.time()-t:.1f}s\n\n" + "\n".join(parca)[:4000] + "\n")
bosalt("glm-ocr:latest")

# deepseek-ocr: "Free OCR." prompt'u (WSL-kanıtı) + kare-başına
t = time.time(); parca = []
for ki, k in enumerate(kareler):
    mtn = sor("deepseek-ocr:latest", "Free OCR.", [k], {"temperature": 0, "num_predict": 1024})
    parca.append(f"--- Kare {ki+1} ---\n{mtn}")
print(f"deepseek-ocr(fix): {time.time()-t:.1f}s, {sum(len(p) for p in parca)} karakter")
open(rapor, "a", encoding="utf-8").write(f"\n## deepseek-ocr (DOĞRU ayar: 'Free OCR.', kare-başına) — {time.time()-t:.1f}s\n\n" + "\n".join(parca)[:4000] + "\n")
bosalt("deepseek-ocr:latest")

# minicpm-v: kare-başına (çoklu-görüntüde boş dönmüştü)
t = time.time(); parca = []
for ki, k in enumerate(kareler):
    mtn = sor("minicpm-v:latest", "Bu bir film jeneriği karesi. Ekrandaki metni oldugu gibi, satir satir oku. Uydurma.",
              [k], {"temperature": 0, "num_predict": 1024})
    parca.append(f"--- Kare {ki+1} ---\n{mtn}")
print(f"minicpm-v(kare-başına): {time.time()-t:.1f}s, {sum(len(p) for p in parca)} karakter")
open(rapor, "a", encoding="utf-8").write(f"\n## minicpm-v (kare-başına) — {time.time()-t:.1f}s\n\n" + "\n".join(parca)[:4000] + "\n")
bosalt("minicpm-v:latest")
print("OLLAMA-FIX-TURU-BITTI")
PYEOF
echo "TELAFI-TURU-TAMAM $(date)"
