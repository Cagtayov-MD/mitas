#!/bin/bash
# 22_hub_yedek_kur.sh — hub-yedeği systemd timer kurulumu (günlük 06:30).
# Çalıştır: sudo bash kurulum/22_hub_yedek_kur.sh
set -euo pipefail

cat > /etc/systemd/system/mitas-hub-yedek.service <<'EOF'
[Unit]
Description=MITAS Database hub yedegi (rsync link-dest snapshot, F-ici)

[Service]
Type=oneshot
User=cagatay
ExecStart=/bin/bash /opt/mitas/scripts/hub_yedek.sh
Nice=15
IOSchedulingClass=idle
EOF

cat > /etc/systemd/system/mitas-hub-yedek.timer <<'EOF'
[Unit]
Description=MITAS hub yedegi - gunluk 06:30 (gece kosulari bittikten sonra)

[Timer]
OnCalendar=*-*-* 06:30:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

mkdir -p /opt/yedek && chown cagatay:cagatay /opt/yedek
systemctl daemon-reload
systemctl enable --now mitas-hub-yedek.timer
systemctl list-timers mitas-hub-yedek.timer --no-pager
echo "KURULDU. İlk yedek elle: systemctl start mitas-hub-yedek.service (veya bash scripts/hub_yedek.sh)"
