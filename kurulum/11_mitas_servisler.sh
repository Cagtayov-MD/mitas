#!/bin/bash
# MITAS systemd servisleri — Windows logon-autostart'ın Linux muadili
#   mitas-asr    :8787  core.api.asr_server:app        (ASR + özet)
#   mitas-tedial :8765  core.api.tedial.app:create_app (Tedial, --factory)
#   mitas-webui  :5173  vite dev (pnpm)
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/11_mitas_servisler.log
exec > >(tee "$LOG") 2>&1

birim() { # $1=ad $2=aciklama $3=execstart
sudo -n tee "/etc/systemd/system/$1.service" > /dev/null <<EOF
[Unit]
Description=$2
After=network-online.target ollama.service

[Service]
Type=simple
User=cagatay
Group=cagatay
WorkingDirectory=/opt/mitas
EnvironmentFile=/opt/mitas/mitas.env
ExecStart=$3
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
}

birim mitas-asr    "MITAS ASR+Ozet API (:8787)" \
  "/opt/mitas/venvs/asr/bin/python -m uvicorn core.api.asr_server:app --host 127.0.0.1 --port 8787"
birim mitas-tedial "MITAS Tedial API (:8765)" \
  "/opt/mitas/venvs/asr/bin/python -m uvicorn core.api.tedial.app:create_app --factory --host 127.0.0.1 --port 8765"
birim mitas-webui  "MITAS WebUI vite (:5173)" \
  "/usr/local/bin/pnpm run dev --host 127.0.0.1 --port 5173"
# webui çalışma dizini farklı:
sudo -n sed -i 's|WorkingDirectory=/opt/mitas$|WorkingDirectory=/opt/mitas/webui|' /etc/systemd/system/mitas-webui.service

sudo -n systemctl daemon-reload
sudo -n systemctl enable --now mitas-asr mitas-tedial mitas-webui
sleep 5
for u in mitas-asr mitas-tedial mitas-webui; do
  echo "$u: $(systemctl is-active $u)"
done
curl -s -o /dev/null -w "8787 HTTP=%{http_code}\n" http://127.0.0.1:8787/docs || true
curl -s -o /dev/null -w "8765 HTTP=%{http_code}\n" http://127.0.0.1:8765/tedial || true
curl -s -o /dev/null -w "5173 HTTP=%{http_code}\n" http://127.0.0.1:5173/ || true
echo "MITAS-SERVISLER-TAMAM $(date)"
