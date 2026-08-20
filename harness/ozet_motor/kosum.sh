#!/bin/bash
# KISA TUR — Qwen3-8B, tek_atis vs cikar_ozetle, 6 film. Eksen: PARÇALAMA işe yarıyor mu?
# Çağatay 2026-07-30: "sen GPU'ya el koy işi hallet."
set -uo pipefail
cd /opt/mitas/harness/ozet_motor

echo "boş VRAM: $(nvidia-smi --query-gpu=memory.free --format=csv,noheader)"

export MITAS_OZET_MODEL=${MITAS_OZET_MODEL:-qwen3-8b-4bit} MITAS_OZET_GPU_UTIL=${MITAS_OZET_GPU_UTIL:-0.55}
./sunucu.sh start || { echo "SUNUCU KALKMADI"; tail -30 /opt/mitas/kurulum/logs/ozet_sunucu.log; exit 1; }

echo "=== kısa tur başlıyor $(date '+%H:%M:%S')"
python3 kos.py --uc vllm --model "$MITAS_OZET_MODEL" --sekil tek_atis,cikar_ozetle --film 6 \
  --not "kisa tur: PARCALAMA ekseni, model sabit. Konsey duzeltmeleri uygulandi."
rc=$?

./sunucu.sh stop
echo "=== bitti rc=$rc $(date '+%H:%M:%S') — GPU serbest"
exit $rc
