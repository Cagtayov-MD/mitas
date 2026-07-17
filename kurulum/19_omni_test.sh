#!/bin/bash
# OMNİ TESTİ: Haziran lab'ının yarım kalan işi — iki Omni'ye gerçek mp4 jenerik okutma (vLLM).
#  1) Qwen2.5-Omni-7B-AWQ  (60s klip)
#  2) Qwen3-Omni-30B-A3B-AWQ-4bit (30s klip ×2 — VRAM-dar profil)
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/19_omni.log
exec > >(tee "$LOG") 2>&1
export CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH
export HF_HOME=/opt/mitas/models/QwenOmni/hf-cache
PORT=8100
RAPOR=/opt/mitas/outputs/VL_KIYAS_JENERIK_20260716.md
SORU="Bu bir film kapanış jeneriği. Her kartta genelde KÜÇÜK puntolu bir rol etiketi (örn. 'Directed by', 'Executive Producers') ve BÜYÜK puntolu isim vardır. Her kartı 'ETİKET: İSİM' biçiminde yaz — küçük yazıları da MUTLAKA oku. Etiket YOKSA etiket uydurma, sadece ismi yaz."

oku() { # $1=snapshot $2=ad $3=mp4 $4=maxlen
  local SNAP="$1" AD="$2" MP4="$3" MAXLEN="$4"
  echo "===== [Omni] $AD ($MP4) $(date +%H:%M) ====="
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /opt/mitas/venvs/vllm/bin/vllm serve "$SNAP" \
    --served-model-name kiyas --port $PORT \
    --max-model-len "$MAXLEN" --gpu-memory-utilization 0.90 \
    --enforce-eager --trust-remote-code \
    --allowed-local-media-path /opt/mitas --limit-mm-per-prompt '{"video": 1}' \
    --max-num-batched-tokens "$MAXLEN" \
    > /opt/mitas/kurulum/logs/vllm_serve_$AD.log 2>&1 &
  local SRV=$!; local OK=0
  for i in $(seq 1 180); do curl -s "http://127.0.0.1:$PORT/health" >/dev/null && { OK=1; break; }; sleep 2; done
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

HO=/opt/mitas/models/QwenOmni/hf-cache/hub
S25=$(ls -d "$HO"/models--Qwen--Qwen2.5-Omni-7B-AWQ/snapshots/*/ | head -1)
S3=$(ls -d "$HO"/models--cpatonn--Qwen3-Omni-30B-A3B-Instruct-AWQ-4bit/snapshots/*/ | head -1)
# max_pixels ayarı Omni işlemcisinde farklı olabilir → kwargs'sız, kısa klipler
oku "$S25" "Qwen2.5-Omni-7B-AWQ"      /opt/mitas/outputs/jenerik_rol_test.mp4 16384
oku "$S3"  "Qwen3-Omni-30B-AWQ-a"     /opt/mitas/outputs/jenerik_rol_a.mp4    12288
oku "$S3"  "Qwen3-Omni-30B-AWQ-b"     /opt/mitas/outputs/jenerik_rol_b.mp4    12288

# Dar-VRAM telafileri: GLM-4.1V (10k) + Qwen3-VL-30B-AWQ (12k) — 30s klipler
export HF_HOME=/opt/mitas/models/hf_cache
H=/opt/mitas/models/hf_cache/hub
oku "$(ls -d $H/models--zai-org--GLM-4.1V-9B-Thinking/snapshots/*/ | head -1)"                 "GLM-4.1V-9B-a"        /opt/mitas/outputs/jenerik_rol_a.mp4 10240
oku "$(ls -d $H/models--zai-org--GLM-4.1V-9B-Thinking/snapshots/*/ | head -1)"                 "GLM-4.1V-9B-b"        /opt/mitas/outputs/jenerik_rol_b.mp4 10240
oku "$(ls -d $H/models--QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ/snapshots/*/ | head -1)"       "Qwen3-VL-30B-AWQ-a"   /opt/mitas/outputs/jenerik_rol_a.mp4 12288
oku "$(ls -d $H/models--QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ/snapshots/*/ | head -1)"       "Qwen3-VL-30B-AWQ-b"   /opt/mitas/outputs/jenerik_rol_b.mp4 12288
echo "OMNI-TEST-TAMAM $(date)"
