#!/usr/bin/env bash
# ATLAS Faz E-1: ollama kur (.tar.zst asset - MITAS ollama_install3.sh deseni) + systemd.
# K-A2: PORT 11435 (MITAS'in 11434'u ile CAKISMAZ - ayni WSL2 VM, ortak port uzayi).
set -uo pipefail
DST=/opt/atlas/models/ollama
mkdir -p "$DST"
echo "=== 1) zstd + binary indir (.tar.zst) ==="
command -v zstd >/dev/null 2>&1 || apt-get install -y zstd >/dev/null 2>&1
cd /tmp
curl -fSL https://github.com/ollama/ollama/releases/download/v0.31.2/ollama-linux-amd64.tar.zst -o ollama_atlas.tar.zst 2>/tmp/ollama_dl_atlas.log
echo "indi: $(du -h ollama_atlas.tar.zst 2>/dev/null | cut -f1)"
tar --zstd -C /usr -xf ollama_atlas.tar.zst
echo "surum: $(/usr/bin/ollama --version 2>&1 | head -1)"

echo "=== 2) systemd birimi (atlas-ollama, port 11435) ==="
cat > /etc/systemd/system/atlas-ollama.service <<'EOF'
[Unit]
Description=ATLAS Ollama Service (izole, port 11435)
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/ollama serve
User=root
Restart=always
RestartSec=3
Environment="OLLAMA_MODELS=/opt/atlas/models/ollama"
Environment="OLLAMA_HOST=127.0.0.1:11435"
Environment="OLLAMA_KEEP_ALIVE=15m"

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now atlas-ollama
sleep 6
echo "servis: $(systemctl is-active atlas-ollama)"
echo "=== 3) canlilik (bos liste beklenir - modeller henuz kopyalanmadi) ==="
export OLLAMA_HOST=127.0.0.1:11435
/usr/bin/ollama list 2>&1 | head
echo OLLAMA_INSTALL_ATLAS_DONE
