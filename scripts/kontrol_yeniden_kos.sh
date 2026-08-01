#!/bin/bash
# KONTROL KOHORTU — SIFIRDAN YENİDEN KOŞU (A/B doğrulama)
#
# Çağatay talimatı (2026-08-01): "Kontroldekileri başka yere TAŞI. Aynı videolar
# SIFIRDAN tekrar koş. Çıktıları birebir kıyaslarız — düzelttiklerimiz düzelmiş mi,
# beklediklerimiz ne olmuş."
#
# NEDEN BU KOHORT: 31.07 gece koşusunda KONTROL'e düşen 29 film. Bunlar HİBRİT
# okuyucuyla okundu — yani tek değişken BUGÜNKÜ DÜZELTMELER. Daha eski 158 KONTROL
# filmi Paddle/OneOCR ile okunmuştu; onları koşmak okuyucu+fix'i aynı anda değiştirir
# ve hangi kazanımın kimden geldiği ayrılamaz.
#
# SİLME YOK — taşıma var. Eski veri Database_kontrol_yedek_<ts>/ altında durur.
#
# TEST EDİLEN DÜZELTMELER:
#   500-satır kesmesi (yönetmen kartı atılıyordu) · giriş master körlüğü ·
#   model gevezeliği + kutu_n=0 süzgeci (sahte Latin-dışı) · yönetmen kurtarma +
#   adres teyidi · giriş penceresi 180→240 sn · kimlik etiketi dürüstlüğü ·
#   özet yabancı-ad kasası · tek master ailesi
set -u
KOK=/opt/mitas
cd "$KOK" || exit 1
TS=$(date +%Y%m%d_%H%M)
YEDEK="$KOK/Database_kontrol_yedek_$TS"
LISTE_KOK="$KOK/outputs/toplu_kosu"
S="${1:-}"

KOHORT=$(mktemp)
find "$KOK/Mitas Output/export/KONTROL" -name "*.pdf" -newermt "2026-07-31 19:00" -printf "%f\n" 2>/dev/null \
  | grep -oE "^[0-9]{4}-[0-9]{4}-[0-9]-[0-9]{4}-[0-9]{2}-[0-9]" | sort -u > "$KOHORT"
N=$(wc -l < "$KOHORT")
echo "=== KOHORT: $N film ==="
[ "$N" -lt 5 ] && { echo "RED: kohort şüpheli küçük ($N) — durdum"; exit 1; }

G="/run/user/1000/gvfs/smb-share:server=depo01cifs.int.trt.net.tr,share=sas_h264/Film Kapanış"
[ -d "$G" ] || { echo "RED: GVFS mount YOK — Çağatay'ın bağlaması gerek"; exit 1; }

# ── 1) ÖN DENETİM: her film için klasör + video VAR MI (taşımadan önce) ──
eksik=0
: > "$LISTE_KOK/yeniden_kosu_$TS.liste"
while read -r t; do
  [ -n "$t" ] || continue
  d=$(ls -d "$KOK"/Database/*"$t" 2>/dev/null | head -1)
  v=$(ls "$G" 2>/dev/null | grep -m1 -- "$t")
  if [ -z "$d" ] || [ -z "$v" ]; then
    echo "  EKSİK: $t (klasör=${d:+var} video=${v:+var})"; eksik=$((eksik+1)); continue
  fi
  echo "$v" >> "$LISTE_KOK/yeniden_kosu_$TS.liste"
done < "$KOHORT"
[ "$eksik" -gt 0 ] && { echo "RED: $eksik filmde klasör/video eksik — hiçbir şey taşımadım"; exit 1; }
echo "  ön denetim TAMAM: $N film, hepsinin klasörü ve videosu var"

if [ "$S" = "--dry" ]; then
  echo "DRY bitti. Koşmak için: bash scripts/kontrol_yeniden_kos.sh --uygula"
  exit 0
fi
[ "$S" = "--uygula" ] || { echo "kullanım: $0 --dry | --uygula"; exit 1; }

# ── 2) TAŞI (silme yok) — Database klasörleri + teslim PDF'leri ──
mkdir -p "$YEDEK/Database" "$YEDEK/KONTROL_pdf"
MAN="$YEDEK/tasima_manifest.txt"
{ echo "# KONTROL kohortu yeniden koşu — $TS"; echo "# SİLME YOK, taşıma."; } > "$MAN"
tas=0
while read -r t; do
  [ -n "$t" ] || continue
  d=$(ls -d "$KOK"/Database/*"$t" 2>/dev/null | head -1)
  [ -n "$d" ] && { mv "$d" "$YEDEK/Database/" && echo "DB : $d" >> "$MAN" && tas=$((tas+1)); }
  for p in "$KOK/Mitas Output/export/KONTROL/"*"$t"*.pdf; do
    [ -f "$p" ] && { mv "$p" "$YEDEK/KONTROL_pdf/" && echo "PDF: $p" >> "$MAN"; }
  done
done < "$KOHORT"
echo "  taşınan film klasörü: $tas → $YEDEK"

# ── 3) LİSTEYİ DEĞİŞTİR (eskisi saklanır) ──
[ -f "$LISTE_KOK/film_listesi.txt" ] && cp "$LISTE_KOK/film_listesi.txt" "$YEDEK/film_listesi_TAM.txt"
cp "$LISTE_KOK/yeniden_kosu_$TS.liste" "$LISTE_KOK/film_listesi.txt"
echo "  liste değişti: $(wc -l < "$LISTE_KOK/film_listesi.txt") film (tam liste yedekte)"

# ── 4) KOŞ ──
rm -f "$LISTE_KOK/DURDUR"
LOG="$LISTE_KOK/yeniden_kosu_$TS.log"
echo "  log: $LOG"
nohup bash "$KOK/scripts/toplu_kosu.sh" > "$LOG" 2>&1 &
echo "  KOŞU BAŞLADI pid=$!"
echo
echo "  BİTİNCE tam listeyi geri koy:"
echo "     cp $YEDEK/film_listesi_TAM.txt $LISTE_KOK/film_listesi.txt"
echo "  KIYAS:"
echo "     python3 scripts/kontrol_kiyas.py --yedek $YEDEK"
