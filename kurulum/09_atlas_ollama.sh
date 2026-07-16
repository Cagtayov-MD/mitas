#!/bin/bash
# ATLAS ollama — AYRI servis (:11435) + AYRI model deposu (/opt/atlas/models/ollama)
# İzolasyon kuralı: MITAS ile ortak model bile AYRI kopyalanır (paylaşım YOK).
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/09_atlas_ollama.log
exec > >(tee "$LOG") 2>&1
MODELDIR=/opt/atlas/models/ollama
ESRC="/run/media/cagatay/Yeni Birim/OllamaModels"

echo "=== [1/3] ATLAS model blob-kopya $(date) ==="
mkdir -p "$MODELDIR/blobs"
MODELS=("glm-ocr/atlas1" "bge-m3/atlas1" "qwen3/8b-atlas1" "qwen35-35b-test/latest")
for m in "${MODELS[@]}"; do
  mani="$ESRC/manifests/registry.ollama.ai/library/$m"
  [ -f "$mani" ] || { echo "MANIFEST YOK: $m"; continue; }
  echo "--- $m ---"
  dstmani="$MODELDIR/manifests/registry.ollama.ai/library/$m"
  mkdir -p "$(dirname "$dstmani")"
  cp "$mani" "$dstmani"
  for dig in $(grep -oE 'sha256:[a-f0-9]{64}' "$mani" | sort -u); do
    blob="sha256-${dig#sha256:}"
    if [ -f "$MODELDIR/blobs/$blob" ]; then echo "  var: $blob"; continue; fi
    if [ -f "$ESRC/blobs/$blob" ]; then
      echo "  kopya ($(du -h "$ESRC/blobs/$blob" | cut -f1)): $blob"
      cp "$ESRC/blobs/$blob" "$MODELDIR/blobs/$blob"
    else echo "  ! KAYNAK BLOB YOK: $blob"; fi
  done
done
sudo -n chown -R ollama:ollama "$MODELDIR"
sudo -n chmod -R a+rX "$MODELDIR"

echo "=== [2/3] ollama-atlas.service (:11435) ==="
sudo -n tee /etc/systemd/system/ollama-atlas.service > /dev/null <<'EOF'
[Unit]
Description=ATLAS Ollama Service (port 11435, ayri model deposu)
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="OLLAMA_HOST=127.0.0.1:11435"
Environment="OLLAMA_MODELS=/opt/atlas/models/ollama"
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

[Install]
WantedBy=multi-user.target
EOF
sudo -n systemctl daemon-reload
sudo -n systemctl enable --now ollama-atlas
sleep 3

echo "=== [3/3] doğrulama ==="
OLLAMA_HOST=127.0.0.1:11435 ollama list
echo "ATLAS-OLLAMA-TAMAM $(date)"
