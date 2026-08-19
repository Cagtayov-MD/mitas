#!/bin/bash
H=/opt/mitas/filmtest/kapanis_hasat
[ -f "$H/_DUR" ] && exit 0
pgrep -f "[3]0_kapanis_zincir" >/dev/null && exit 0
cd /opt/mitas || exit 1
nohup setsid bash kurulum/30_kapanis_zincir.sh >> "$H/_zincir.log" 2>&1 < /dev/null &
