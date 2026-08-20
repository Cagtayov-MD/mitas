#!/bin/bash
# KAPANIŞ ORKESTRATÖRÜ v3 — Claude'suz tam otomatik, kendini onaran (2026-07-24).
# Döngü: (1) NIM okuma+zengin eksikse tek işçi-havuzu başlat/canlı tut,
#        (2) kilit altında 27 birleştir + 26 PDF (yalnız çekirdek-künyeli filmler),
#        (3) tüm NIM işi bitti + iş kalmadıysa TAMAMLANDI ile çık.
# Durdur: touch /opt/mitas/filmtest/kapanis_hasat/_DUR
# Başlat: nohup setsid bash kurulum/30_kapanis_zincir.sh >> .../_zincir.log 2>&1 &
cd /opt/mitas || exit 1
H=/opt/mitas/filmtest/kapanis_hasat
PYO=venvs/ocr/bin/python
LOG(){ echo "$(date '+%F %T') $*"; }
LOG "orkestratör v3 başladı pid=$$"

bekleyen_nim(){   # okuma yok VEYA zengin eski-stil (oyuncular_bilgi'siz) film sayısı
  $PYO - <<'PY'
import json,glob,os
n=0
for m in glob.glob("/opt/mitas/filmtest/kapanis_hasat/*/meta.json"):
    d=os.path.dirname(m)
    if not os.path.exists(d+"/okuma.json"): n+=1; continue
    z=d+"/zengin.json"
    try: eski = (not os.path.exists(z)) or ("oyuncular_bilgi" not in json.load(open(z)))
    except Exception: eski=True
    if eski: n+=1
print(n)
PY
}

while true; do
  [ -f "$H/_DUR" ] && { LOG "DUR görüldü, çıkılıyor"; exit 0; }

  # 1) NIM işçisini canlı tut (idempotent; tamamlananı atlar, eski-zengin'i yeniler)
  if ! pgrep -f "[2]9_nim_okuma" >/dev/null; then
    bn=$(bekleyen_nim)
    if [ "${bn:-0}" -gt 0 ]; then
      LOG "NIM başlatılıyor ($bn bekleyen)"
      nohup $PYO kurulum/29_nim_okuma.py --workers 8 >> "$H/_nim.log" 2>&1 &
      sleep 5
    fi
  fi

  # 2) birleştir + PDF (tek-yazıcı kilidi)
  flock "$H/_basim.lock" bash kurulum/_basim_adimi.sh
  LOG "tur bitti — pdf: $(find /opt/mitas/export/KAPANIS_PDF_20260724 -maxdepth 1 -name '*.pdf'|wc -l)"

  # 3) bitiş: NIM işi kalmadı + NIM çalışmıyor
  if [ "$(bekleyen_nim)" -eq 0 ] && ! pgrep -f "[2]9_nim_okuma" >/dev/null; then
    LOG "TAMAMLANDI"; exit 0
  fi
  sleep 600
done
