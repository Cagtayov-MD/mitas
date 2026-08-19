#!/bin/bash
# NÖBETÇİ v2 — süreç adına DEĞİL, boş VRAM'e bakar. Hangi oturum ne başlatırsa başlatsın çalışır.
# Kart yeterince boşalınca eksik kalan turu koşturur. Prensip 2: koşan işi ASLA bozmaz, bekler.
#
# EKSİK TUR: Qwen3-VL-32B-AWQ · cikar_ozetle · 6 film → MODEL ekseni (toplayıcı kavraması).
# 8B turu 13:41'de bitti (runs/20260730-134114-vllm-qwen3-8b).
set -uo pipefail
cd /opt/mitas/harness/ozet_motor
LOG=/opt/mitas/harness/ozet_motor/nobetci.log
exec > >(tee -a "$LOG") 2>&1

GEREKLI=${GEREKLI:-22000}      # 32B-AWQ + eager + 10k fp8 KV için ölçülmüş eşik
KARARLI=3                      # üst üste bu kadar ölçümde boş kalsın (anlık dip yanıltmasın)

echo "════ nöbetçi v2 başladı $(date '+%H:%M:%S') — ${GEREKLI} MiB bekleniyor"
sayac=0; bekleme=0
while :; do
  bos=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
  if [ "$bos" -ge "$GEREKLI" ]; then
    sayac=$((sayac + 1))
    [ $sayac -ge $KARARLI ] && break
  else
    sayac=0
  fi
  sleep 20; bekleme=$((bekleme + 20))
  [ $((bekleme % 600)) -eq 0 ] && echo "  … $((bekleme / 60)) dk — boş ${bos} MiB (gerekli ${GEREKLI})"
  [ $bekleme -gt 14400 ] && { echo "4 saat doldu — nöbetçi çekildi. Elle: ./nobetci.sh"; exit 4; }
done
echo "════ kart boşaldı: ${bos} MiB ($((bekleme / 60)) dk beklendi)"

echo ""
echo "──── TUR: qwen3-32b-awq · cikar_ozetle · $(date '+%H:%M:%S')"
MITAS_OZET_MODEL=qwen3-32b-awq MITAS_OZET_GPU_UTIL=0.93 ./sunucu.sh start || {
  echo "SUNUCU KALKMADI"; tail -12 /opt/mitas/kurulum/logs/ozet_sunucu.log; exit 1; }
python3 kos.py --uc vllm --model qwen3-32b-awq --sekil cikar_ozetle --film 6 \
  --not "MODEL ekseni: 32B-AWQ toplayici, parcali hat, eager"
rc=$?
MITAS_OZET_MODEL=qwen3-32b-awq ./sunucu.sh stop
echo "════ nöbetçi bitti rc=$rc $(date '+%H:%M:%S') — GPU serbest"
ls -dt runs/*/ | head -2
