#!/bin/bash
# Kıyas turu A-bölümü ONARIM: model-ailesine göre ayarlar + kanıtlı bellek profili.
# Girdi: jenerik_rol_test.mp4 (60s kart bölgesi — hepsi için güvenli boyut)
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/18b_onarim.log
exec > >(tee "$LOG") 2>&1
export CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH HF_HOME=/opt/mitas/models/hf_cache
PORT=8100
MP4=/opt/mitas/outputs/jenerik_rol_test.mp4
RAPOR=/opt/mitas/outputs/VL_KIYAS_JENERIK_20260716.md
SORU="Bu bir film kapanış jeneriği. Her kartta genelde KÜÇÜK puntolu bir rol etiketi (örn. 'Directed by', 'Executive Producers') ve BÜYÜK puntolu isim vardır. Her kartı 'ETİKET: İSİM' biçiminde yaz — küçük yazıları da MUTLAKA oku. Etiket YOKSA etiket uydurma, sadece ismi yaz."

vllm_oku() { # $1=snapshot $2=ad $3=ekstra-arglar(str)
  local SNAP="$1" AD="$2" EKSTRA="$3"
  echo "===== [vLLM] $AD $(date +%H:%M) ====="
  # shellcheck disable=SC2086
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /opt/mitas/venvs/vllm/bin/vllm serve "$SNAP" \
    --served-model-name kiyas --port $PORT \
    --max-model-len 32768 --gpu-memory-utilization 0.90 \
    --enforce-eager --trust-remote-code \
    --allowed-local-media-path /opt/mitas --limit-mm-per-prompt '{"video": 1}' \
    --max-num-batched-tokens 20480 $EKSTRA \
    > /opt/mitas/kurulum/logs/vllm_serve_$AD.log 2>&1 &
  local SRV=$!
  local OK=0
  for i in $(seq 1 180); do curl -s "http://127.0.0.1:$PORT/health" >/dev/null && { OK=1; break; }; sleep 2; done
  if [ "$OK" = "0" ]; then
    echo "$AD: SUNUCU-KALKMADI"; echo -e "\n## $AD (vLLM video)\nSUNUCU KALKMADI (log: vllm_serve_$AD.log)" >> "$RAPOR"
    kill $SRV 2>/dev/null; sleep 5; return
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
    open(rapor, "a", encoding="utf-8").write(f"\n## {ad} (vLLM, gerçek mp4-girdi, 60s) — {su:.1f}s\n\n{m}\n")
except Exception as e:  # noqa: BLE001
    print(f"{ad}: HATA {type(e).__name__}: {str(e)[:150]}")
    open(rapor, "a", encoding="utf-8").write(f"\n## {ad} (vLLM): HATA {type(e).__name__}: {str(e)[:200]}\n")
PYEOF
  kill $SRV 2>/dev/null; sleep 8
}

H=/opt/mitas/models/hf_cache/hub
QW='--mm-processor-kwargs {"max_pixels":125440}'
vllm_oku "$(ls -d $H/models--allenai--olmOCR-2-7B-1025-FP8/snapshots/*/ | head -1)"        "olmOCR-2-7B-FP8"      "$QW"
vllm_oku "$(ls -d $H/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/*/ | head -1)"           "Qwen3-VL-8B"          "$QW"
vllm_oku "$(ls -d $H/models--QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ/snapshots/*/ | head -1)" "Qwen3-VL-30B-A3B-AWQ" "$QW"
vllm_oku "$(ls -d $H/models--QuantTrio--Qwen3-VL-32B-Instruct-AWQ/snapshots/*/ | head -1)"  "Qwen3-VL-32B-AWQ"     "$QW"
vllm_oku "$(ls -d $H/models--OpenGVLab--InternVL3_5-8B/snapshots/*/ | head -1)"             "InternVL3_5-8B"       ""
vllm_oku "$(ls -d $H/models--nvidia--NVIDIA-Nemotron-Nano-12B-v2-VL-FP8/snapshots/*/ | head -1)" "Nemotron-12B-VL-FP8" ""
vllm_oku "$(ls -d $H/models--openbmb--MiniCPM-V-4_5/snapshots/*/ | head -1)"                "MiniCPM-V-4.5"        ""
vllm_oku "$(ls -d $H/models--zai-org--GLM-4.1V-9B-Thinking/snapshots/*/ | head -1)"         "GLM-4.1V-9B"          ""
echo "ONARIM-TURU-TAMAM $(date)"
