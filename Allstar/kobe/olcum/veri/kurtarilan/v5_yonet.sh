#!/bin/bash
# batch_v5'i tüm inen filmler işlenene + retry-download bitene kadar yönet.
S=/tmp/claude-1000/-opt-mitas/1bd0cb57-0064-4841-b568-8555832193d6/scratchpad
cd /opt/mitas/harness/kunye_kiyas
while true; do
  # batch_v5 çalışmıyorsa başlat (idempotent — işlenenleri atlar)
  if ! pgrep -f batch_v5.py >/dev/null; then
    /opt/mitas/venvs/ocr/bin/python "$S/batch_v5.py" >> "$S/batch_v5.log" 2>&1
  fi
  isl=$(python3 -c "import json;print(len(json.load(open('$S/v5_tahminler.json'))))" 2>/dev/null || echo 0)
  ind=$(ls -d "$S/pool_frames"/*/ 2>/dev/null | wc -l)
  dl_bitti=0
  pgrep -f "pool_cek_cikar" >/dev/null || dl_bitti=1
  echo "DURUM: işlenen=$isl indirilen=$ind download_bitti=$dl_bitti"
  # hepsi işlendi VE download bitti → HAZIR
  if [ "$dl_bitti" = 1 ] && [ "$isl" -ge "$ind" ]; then
    echo "HAZIR: $isl film işlendi, doğrulamaya hazır"
    break
  fi
  sleep 20
done
