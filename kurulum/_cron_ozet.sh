#!/bin/bash
H=/opt/mitas/filmtest/kapanis_hasat
[ -f "$H/_OZET_DUR" ] && exit 0
[ -f "$H/_OZET_BITTI" ] && exit 0
pgrep -f "[3]5_ozet_dongu" >/dev/null && exit 0
cd /opt/mitas && setsid nohup bash kurulum/35_ozet_dongu.sh >> "$H/_ozet_dongu.log" 2>&1 < /dev/null &
