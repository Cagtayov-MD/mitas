#!/bin/bash
# SON ADAYLAR: MiMo-VL-7B, Kimi-VL-A3B, ERNIE-4.5-VL-AWQ, LLaVA-OneVision-1.5 — aynı jenerik testi
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/20_son_adaylar.log
exec > >(tee "$LOG") 2>&1
export CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH HF_HOME=/opt/mitas/models/hf_cache
PORT=8100
RAPOR=/opt/mitas/outputs/VL_KIYAS_JENERIK_20260716.md
SORU="Bu bir film kapanış jeneriği. Her kartta genelde KÜÇÜK puntolu bir rol etiketi (örn. 'Directed by', 'Executive Producers') ve BÜYÜK puntolu isim vardır. Her kartı 'ETİKET: İSİM' biçiminde yaz — küçük yazıları da MUTLAKA oku. Etiket YOKSA etiket uydurma, sadece ismi yaz."

oku() { local SNAP="$1" AD="$2" MP4="$3" MAXLEN="$4" EKSTRA="$5"
  echo "===== $AD ($(basename $MP4), len=$MAXLEN) $(date +%H:%M) ====="
  # shellcheck disable=SC2086
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /opt/mitas/venvs/vllm/bin/vllm serve "$SNAP" \
    --served-model-name kiyas --port $PORT \
    --max-model-len "$MAXLEN" --gpu-memory-utilization 0.90 \
    --enforce-eager --trust-remote-code \
    --allowed-local-media-path /opt/mitas --limit-mm-per-prompt '{"video": 1}' \
    --max-num-batched-tokens "$MAXLEN" $EKSTRA \
    > /opt/mitas/kurulum/logs/vllm_serve_$AD.log 2>&1 &
  local SRV=$!; local OK=0
  for i in $(seq 1 180); do
    curl -s "http://127.0.0.1:$PORT/health" >/dev/null && { OK=1; break; }
    kill -0 $SRV 2>/dev/null || break   # süreç öldüyse bekleme
    sleep 2
  done
  if [ "$OK" = "0" ]; then
    echo "$AD: SUNUCU-KALKMADI"; echo -e "\n## $AD\nSUNUCU KALKMADI (log: vllm_serve_$AD.log)" >> "$RAPOR"
    kill $SRV 2>/dev/null; sleep 5; return
  fi
  SORU="$SORU" MP4="$MP4" AD="$AD" RAPOR="$RAPOR" /opt/mitas/venvs/vllm/bin/python - <<'PYEOF'
import json, os, time, urllib.request
soru, mp4, ad, rapor = os.environ["SORU"], os.environ["MP4"], os.environ["AD"], os.environ["RAPOR"]
payload = {"model": "kiyas", "temperature": 0, "max_tokens": 2000,
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
    open(rapor, "a", encoding="utf-8").write(f"\n## {ad} (vLLM, gerçek mp4) — {su:.1f}s\n\n{m}\n")
except Exception as e:  # noqa: BLE001
    print(f"{ad}: HATA {type(e).__name__}: {str(e)[:150]}")
    open(rapor, "a", encoding="utf-8").write(f"\n## {ad}: HATA {type(e).__name__}: {str(e)[:200]}\n")
PYEOF
  kill $SRV 2>/dev/null; sleep 8
}

H=/opt/mitas/models/hf_cache/hub
QW='--mm-processor-kwargs {"max_pixels":125440}'
V60=/opt/mitas/outputs/jenerik_rol_test.mp4
V30A=/opt/mitas/outputs/jenerik_rol_a.mp4

oku "$(ls -d $H/models--XiaomiMiMo--MiMo-VL-7B-RL/snapshots/*/ | head -1)"                      "MiMo-VL-7B-RL"        "$V60"  16384 "$QW"
oku "$(ls -d $H/models--lmms-lab--LLaVA-OneVision-1.5-8B-Instruct/snapshots/*/ | head -1)"       "LLaVA-OneVision-8B"   "$V60"  16384 ""
oku "$(ls -d $H/models--cyankiwi--ERNIE-4.5-VL-28B-A3B-Thinking-AWQ-4bit/snapshots/*/ | head -1)" "ERNIE-4.5-VL-28B-AWQ" "$V30A" 12288 ""
oku "$(ls -d $H/models--moonshotai--Kimi-VL-A3B-Instruct/snapshots/*/ | head -1)"                "Kimi-VL-A3B"          "$V30A" 12288 ""
echo "SON-ADAYLAR-TEST-TAMAM $(date)"
