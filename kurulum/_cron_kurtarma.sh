#!/bin/bash
H=/opt/mitas/filmtest/kapanis_hasat
[ -f "$H/_KURT_DUR" ] && exit 0
[ -f "$H/_KURT_BITTI" ] && exit 0
pgrep -f "[3]7_kurtarma" >/dev/null && exit 0
cd /opt/mitas && setsid nohup bash kurulum/37_kurtarma_zinciri.sh >> "$H/_kurtarma.log" 2>&1 < /dev/null &
