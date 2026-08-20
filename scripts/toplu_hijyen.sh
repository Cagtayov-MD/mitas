#!/bin/bash
# TOPLU HİJYEN — ÇAĞATAY'IN TERMİNALİNDEN KOŞAR (Database silme koruması gereği).
# İki iş yapar:
#  (A) BİRİKMİŞ TEMİZLİK (tek sefer):
#      1. İlk-turdan kalan kopya klasörler: " 2" kardeşi olan orijinal dizinler
#         (PDF'siz, geçersiz teslimli) + onların export kalıntıları silinir.
#      2. Database'deki source/ kopyalarından, dosyaları ŞU AN share'de birebir
#         mevcut olanlar silinir (arşivden yeniden çekilebilir). Share'de
#         olmayan source'a DOKUNULMAZ.
#  (B) SÜREKLİ HİJYEN DÖNGÜSÜ: 10 dakikada bir, İŞİ BİTMİŞ (karar verilmiş,
#      _DURUM.json'lu, en az 30 dk dokunulmamış) klip dizinlerinde ham kareleri
#      (frames/giris, frames/cikis) ve 50MB+ wav'ları siler. HAVUZLAR
#      (frames/*_jenerik*) ve tüm künye/PDF/track_kunye çıktıları KALIR.
#
# Kullanım:
#   bash scripts/toplu_hijyen.sh --dry     # ne silineceğini GÖSTERİR, silmez
#   bash scripts/toplu_hijyen.sh --uygula  # (A) siler + (B) döngüye girer
# Durdurmak: Ctrl-C (döngü kısmı zararsız, istediğin an kesilir).
set -u
G="/run/user/1000/gvfs/smb-share:server=depo01cifs.int.trt.net.tr,share=sas_h264/Film Kapanış"
KOK=/opt/mitas/outputs/toplu_kosu
mkdir -p "$KOK"
MOD="${1:---dry}"
MAN="$KOK/hijyen_manifest_$(date +%Y%m%d_%H%M).txt"
SIL="rm -rf"
[ "$MOD" = "--dry" ] && SIL="echo SILINECEK:"

echo "MOD: $MOD — manifest: $MAN"
ls "$G" > "$KOK/share_listesi.txt" 2>/dev/null || echo "UYARI: share listelenemedi, source temizliği atlanacak"

# (A1) run-1 kopya klasörleri
for d2 in /opt/mitas/Database/*" 2"; do
  [ -d "$d2" ] || continue
  d1="${d2% 2}"
  [ -d "$d1" ] || continue
  boyut=$(du -sm "$d1" | cut -f1)
  teslim=$(/opt/mitas/venvs/ocr/bin/python -c "import json;print(json.load(open('$d1/_DURUM.json')).get('teslim') or '')" 2>/dev/null)
  echo "RUN1: $d1 (${boyut}MB) teslim=$teslim" | tee -a "$MAN"
  [ -n "$teslim" ] && [ -e "$teslim" ] && $SIL "$teslim"
  $SIL "$d1"
done

# (A2) share-doğrulamalı source kopyaları
if [ -s "$KOK/share_listesi.txt" ]; then
  find /opt/mitas/Database -maxdepth 2 -type d -name source | while read -r s; do
    hepsi_var=1; dosya_var=0
    while IFS= read -r f; do
      dosya_var=1
      grep -qxF "$(basename "$f")" "$KOK/share_listesi.txt" || { hepsi_var=0; break; }
    done < <(find "$s" -type f)
    if [ "$dosya_var" = 1 ] && [ "$hepsi_var" = 1 ]; then
      echo "SOURCE ($(du -sm "$s" | cut -f1)MB): $s" | tee -a "$MAN"
      $SIL "$s"
    else
      echo "SOURCE-KORU (share'de yok/boş): $s" >> "$MAN"
    fi
  done
fi
df -h /opt/mitas | tail -1

[ "$MOD" = "--dry" ] && { echo "DRY bitti — silmek için: bash scripts/toplu_hijyen.sh --uygula"; exit 0; }

# (B) sürekli hijyen döngüsü
echo "Sürekli hijyen döngüsü başladı (10 dk aralık, Ctrl-C ile çık)."
while true; do
  find /opt/mitas/Database -maxdepth 1 -mindepth 1 -type d | while read -r d; do
    [ -f "$d/_DURUM.json" ] || continue
    # son 30 dk içinde dokunulmuş dizine karışma (işlenmekte olabilir)
    [ -n "$(find "$d/_DURUM.json" -mmin -30 2>/dev/null)" ] && continue
    for ham in "$d/frames/giris" "$d/frames/cikis"; do
      [ -d "$ham" ] && { echo "HAM-SIL: $ham ($(du -sm "$ham" | cut -f1)MB)" >> "$MAN"; rm -rf "$ham"; }
    done
    find "$d/audio" -name "*.wav" -size +50M -print -delete 2>/dev/null | sed 's/^/WAV-SIL: /' >> "$MAN"
  done
  sleep 600
done
