#!/bin/bash
# havuz_kur.sh tur-tekrarlayıcısı: GVFS aralıklı hatalarında eksikler bitene
# veya iki tur üst üste ilerleme olmayana kadar yeniden dener.
set -u
V="/opt/mitas/harness/kunye_kiyas/veri"
KOK="/opt/mitas/Allstar/kobe/havuz"
LOG="$V/havuz_tekrar.log"
exec >>"$LOG" 2>&1

eksik_say() {
  local n=0
  while IFS=$'\t' read -r kaynak hedef; do
    [ -z "$kaynak" ] && continue
    [ "$(ls "$KOK/$hedef"/*.png 2>/dev/null | wc -l)" -gt 50 ] || n=$((n+1))
  done < "$V/eslesme.tsv"
  echo "$n"
}

onceki=999; ayni=0
for tur in 1 2 3 4 5 6; do
  # süren havuz_kur bitene kadar bekle
  while pgrep -f "veri/havuz_kur.sh" >/dev/null 2>&1; do sleep 60; done
  e=$(eksik_say)
  echo "$(date '+%F %T') tur=$tur eksik=$e"
  [ "$e" -eq 0 ] && { echo "TAMAM: eksik yok"; break; }
  if [ "$e" -ge "$onceki" ]; then ayni=$((ayni+1)); else ayni=0; fi
  [ "$ayni" -ge 2 ] && { echo "DURDU: 2 tur ilerleme yok (eksik=$e)"; break; }
  onceki=$e
  sleep 30
  bash "$V/havuz_kur.sh"
done
echo "$(date '+%F %T') havuz_tekrar bitti; kalan eksik=$(eksik_say)"
