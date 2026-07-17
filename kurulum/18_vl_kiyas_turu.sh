#!/bin/bash
# VL KIYAS TURU — aynı jenerik parçası (parça-0) tüm VL modellere.
#  A) vLLM video_url (gerçek mp4-girdi): olmOCR-2-FP8, InternVL3_5-8B, Nemotron-12B-VL-FP8
#  B) ollama kare-dizisi (video desteği yok → aynı karelerden çoklu-görüntü):
#     qwen3-vl:8b/30b/32b, qwen2.5vl:32b, minicpm-v, mistral-small3.2, glm-ocr, deepseek-ocr
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/18_vl_kiyas.log
exec > >(tee "$LOG") 2>&1
export CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH HF_HOME=/opt/mitas/models/hf_cache
PORT=8100
MP4=/opt/mitas/outputs/jenerik_parca_0.mp4
RAPOR=/opt/mitas/outputs/VL_KIYAS_JENERIK_20260716.md
SORU="Bu bir film kapanış jeneriği. Her kartta genelde KÜÇÜK puntolu bir rol etiketi (örn. 'Directed by', 'Executive Producers') ve BÜYÜK puntolu isim vardır. Her kartı 'ETİKET: İSİM' biçiminde yaz — küçük yazıları da MUTLAKA oku. Etiket yoksa sadece ismi yaz. Uydurma."

echo "# VL Model Kıyası — Akıl Oyunları jenerik parça-0 (aynı girdi, aynı prompt)" > "$RAPOR"

vllm_oku() { # $1=snapshot-dizini $2=ad
  local SNAP="$1" AD="$2"
  echo "===== [vLLM] $AD $(date +%H:%M) ====="
  /opt/mitas/venvs/vllm/bin/vllm serve "$SNAP" --served-model-name kiyas \
    --port $PORT --max-model-len 32768 --gpu-memory-utilization 0.92 \
    --enforce-eager --trust-remote-code \
    --allowed-local-media-path /opt/mitas --limit-mm-per-prompt '{"video": 1}' \
    --mm-processor-kwargs '{"max_pixels": 235200}' --max-num-batched-tokens 28672 \
    > /opt/mitas/kurulum/logs/vllm_serve_$AD.log 2>&1 &
  local SRV=$!
  local OK=0
  for i in $(seq 1 150); do curl -s "http://127.0.0.1:$PORT/health" >/dev/null && { OK=1; break; }; sleep 2; done
  if [ "$OK" = "0" ]; then
    echo "$AD: SUNUCU-KALKMADI"; echo -e "\n## $AD (vLLM video)\nSUNUCU KALKMADI (log: vllm_serve_$AD.log)" >> "$RAPOR"
    kill $SRV 2>/dev/null; sleep 3; return
  fi
  SORU="$SORU" MP4="$MP4" AD="$AD" RAPOR="$RAPOR" /opt/mitas/venvs/vllm/bin/python - <<'PYEOF'
import json, os, time, urllib.request
soru, mp4, ad, rapor = os.environ["SORU"], os.environ["MP4"], os.environ["AD"], os.environ["RAPOR"]
payload = {"model": "kiyas", "temperature": 0, "max_tokens": 3000,
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
    open(rapor, "a", encoding="utf-8").write(f"\n## {ad} (vLLM, gerçek mp4-girdi) — {su:.1f}s\n\n{m}\n")
except Exception as e:  # noqa: BLE001
    print(f"{ad}: HATA {type(e).__name__}: {str(e)[:150]}")
    open(rapor, "a", encoding="utf-8").write(f"\n## {ad} (vLLM): HATA {type(e).__name__}: {str(e)[:200]}\n")
PYEOF
  kill $SRV 2>/dev/null; sleep 5
}

H=/opt/mitas/models/hf_cache/hub
vllm_oku "$(ls -d $H/models--allenai--olmOCR-2-7B-1025-FP8/snapshots/*/ | head -1)" "olmOCR-2-7B-FP8"
vllm_oku "$(ls -d $H/models--OpenGVLab--InternVL3_5-8B/snapshots/*/ | head -1)" "InternVL3_5-8B"
vllm_oku "$(ls -d $H/models--nvidia--NVIDIA-Nemotron-Nano-12B-v2-VL-FP8/snapshots/*/ | head -1)" "Nemotron-12B-VL-FP8"

echo "===== [B] ollama kare-dizisi turu ====="
SORU="$SORU" RAPOR="$RAPOR" /opt/mitas/venvs/vllm/bin/python - <<'PYEOF'
import base64, json, os, subprocess, time, urllib.request

soru, rapor = os.environ["SORU"], os.environ["RAPOR"]
# parça-0'dan 12 kare @768px (28-98s arası — jenerik bölgesi)
kareler = []
for i, s in enumerate(range(28, 100, 6)):
    p = f"/tmp/claude-1000/kiyas_{i}.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-ss", str(s), "-i",
                    "/opt/mitas/outputs/jenerik_parca_0.mp4", "-frames:v", "1",
                    "-vf", "scale=768:-2", "-q:v", "3", "-y", p], check=True)
    kareler.append(base64.b64encode(open(p, "rb").read()).decode())
print(f"{len(kareler)} kare hazir")

def sor(model, mesajlar, timeout=1800):
    payload = {"model": model, "stream": False, "think": False,
               "options": {"temperature": 0, "num_predict": 4096, "repeat_penalty": 1.0, "num_ctx": 16384},
               "messages": mesajlar}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
                                 data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=timeout))
    return (r.get("message", {}).get("content") or "").strip()

# Genel VL'ler: 12-kare çoklu-görüntü (video yok ama çok-kare bağlamı anlarlar)
COKLU = ["qwen3-vl:8b", "qwen3-vl:30b", "qwen3-vl:32b", "qwen2.5vl:32b",
         "minicpm-v:latest", "mistral-small3.2:latest"]
# Uzman-OCR'ler: TEK-görüntü modelleri (üretimdeki gerçek kullanım = kare-başına çağrı)
TEKLI = ["glm-ocr:latest", "deepseek-ocr:latest"]
TEKLI_SORU = "Bu bir film jeneriği karesi. Ekrandaki metni oldugu gibi, satir satir oku. Uydurma."

for m in COKLU:
    t = time.time()
    try:
        mtn = sor(m, [{"role": "user", "content": soru, "images": kareler}])
        su = time.time() - t
        print(f"{m}: {su:.1f}s, {len(mtn)} karakter")
        open(rapor, "a", encoding="utf-8").write(f"\n## {m} (ollama, 12-kare dizisi) — {su:.1f}s\n\n{mtn[:4000]}\n")
    except Exception as e:  # noqa: BLE001
        print(f"{m}: HATA {type(e).__name__}: {str(e)[:120]}")
        open(rapor, "a", encoding="utf-8").write(f"\n## {m} (ollama): HATA {type(e).__name__}: {str(e)[:200]}\n")
    try:
        urllib.request.urlopen(urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps({"model": m, "keep_alive": 0}).encode(),
            headers={"Content-Type": "application/json"}), timeout=60)
    except Exception:
        pass
    time.sleep(3)

for m in TEKLI:
    t = time.time()
    parcalar = []
    try:
        for ki, k in enumerate(kareler):
            mtn = sor(m, [{"role": "user", "content": TEKLI_SORU, "images": [k]}], timeout=600)
            parcalar.append(f"--- Kare {ki+1} ---\n{mtn}")
        su = time.time() - t
        birlesik = "\n".join(parcalar)
        print(f"{m}: {su:.1f}s (12 tekli çağrı), {len(birlesik)} karakter")
        open(rapor, "a", encoding="utf-8").write(
            f"\n## {m} (ollama, kare-başına TEK görüntü ×12 — üretim modu) — {su:.1f}s\n\n{birlesik[:4000]}\n")
    except Exception as e:  # noqa: BLE001
        print(f"{m}: HATA {type(e).__name__}: {str(e)[:120]}")
        open(rapor, "a", encoding="utf-8").write(f"\n## {m} (ollama): HATA {type(e).__name__}: {str(e)[:200]}\n")
    # VRAM: bir sonraki model için boşalt
    try:
        urllib.request.urlopen(urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps({"model": m, "keep_alive": 0}).encode(),
            headers={"Content-Type": "application/json"}), timeout=60)
    except Exception:
        pass
    time.sleep(3)
print("OLLAMA-TUR-BITTI")
PYEOF
echo "KIYAS-TURU-TAMAM $(date) — rapor: $RAPOR"
