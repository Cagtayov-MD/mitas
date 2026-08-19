#!/bin/bash
# TAM ZİNCİR — Çağatay yok, "hepsini deneyebilirsin, diğer akışları kesebilirsin" (2026-07-30).
#
# 1) Kartı boşalt (ollama modelleri + kalan vLLM sunucuları)
# 2) TOPLAYICI TURU: kayıtlı olay listelerinden yalnız son adım, 4 orta-boy aday
#    → açık soru: 3090'daki bir model GLM'in 3/3'üne yetişiyor mu?
# 3) MODEL EKSENİ: Qwen3-VL-32B-AWQ ile tam parçalı hat (üç kez GPU kavgasından kesilmişti)
set -uo pipefail
cd /opt/mitas/harness/ozet_motor
LOG=tam_zincir.log
exec > >(tee -a "$LOG") 2>&1

echo "════════ TAM ZİNCİR $(date '+%H:%M:%S') ════════"

echo "── kart boşaltılıyor"
pkill -f 'vllm serve' 2>/dev/null && sleep 5
for m in $(curl -s http://127.0.0.1:11434/api/ps 2>/dev/null | python3 -c "import json,sys; print(' '.join(x['name'] for x in json.load(sys.stdin).get('models',[])))" 2>/dev/null); do
  curl -s http://127.0.0.1:11434/api/generate -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null 2>&1
  echo "   ollama boşaltıldı: $m"
done
sleep 10
echo "   boş VRAM: $(nvidia-smi --query-gpu=memory.free --format=csv,noheader)"

echo ""
echo "════ 1/2 TOPLAYICI TURU (ollama, orta-boy adaylar) $(date '+%H:%M:%S')"
python3 toplayici_turu.py --uc ollama --num-ctx 8192 \
  --modeller "gemma4:26b,mistral-small3.2:latest,qwen36-27b-test:latest,qwen36-35b-test:latest"
rc1=$?
echo "toplayıcı turu rc=$rc1"

echo "── kart boşaltılıyor (32B için)"
for m in $(curl -s http://127.0.0.1:11434/api/ps 2>/dev/null | python3 -c "import json,sys; print(' '.join(x['name'] for x in json.load(sys.stdin).get('models',[])))" 2>/dev/null); do
  curl -s http://127.0.0.1:11434/api/generate -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null 2>&1
done
sleep 12
echo "   boş VRAM: $(nvidia-smi --query-gpu=memory.free --format=csv,noheader)"

echo ""
echo "════ 2/2 MODEL EKSENİ — Qwen3-VL-32B-AWQ, parçalı hat $(date '+%H:%M:%S')"
if MITAS_OZET_MODEL=qwen3-32b-awq MITAS_OZET_GPU_UTIL=0.93 ./sunucu.sh start; then
  python3 kos.py --uc vllm --model qwen3-32b-awq --sekil cikar_ozetle --film 6 \
    --not "MODEL ekseni: 32B-AWQ tam parcali hat, eager"
  rc2=$?
  # 32B ayaktayken TOPLAYICI olarak da ölç — aynı listeler, tek çağrı (bedava ek veri)
  python3 toplayici_turu.py --uc vllm --vllm-host http://127.0.0.1:8101/v1 --modeller qwen3-32b-awq
  MITAS_OZET_MODEL=qwen3-32b-awq ./sunucu.sh stop
else
  echo "32B KALKMADI"; tail -12 /opt/mitas/kurulum/logs/ozet_sunucu.log; rc2=1
fi

echo ""
echo "════════ ZİNCİR BİTTİ $(date '+%H:%M:%S') — toplayıcı rc=$rc1 · 32B rc=${rc2:-?}"
nvidia-smi --query-gpu=memory.free --format=csv,noheader
ls -dt runs/*/ | head -4
