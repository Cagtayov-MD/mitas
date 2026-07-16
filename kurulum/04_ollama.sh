#!/bin/bash
# MITAS ollama kurulumu — en güncel resmi sürüm + model deposu /opt/mitas altında
# 3 özel model E:'den blob-kopya (tek seferlik tohum), 2 standart model pull
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/04_ollama.log
exec > >(tee "$LOG") 2>&1

MODELDIR=/opt/mitas/models/ollama
ESRC="/run/media/cagatay/Yeni Birim/OllamaModels"

echo "=== [1/5] ollama resmi kurulum (en güncel) $(date) ==="
curl -fsSL https://ollama.com/install.sh | sh || { echo "OLLAMA-KURULUM-HATA"; exit 1; }
ollama --version

echo "=== [2/5] model deposu + systemd yapılandırması ==="
sudo -n mkdir -p "$MODELDIR/blobs"
sudo -n mkdir -p /etc/systemd/system/ollama.service.d
sudo -n tee /etc/systemd/system/ollama.service.d/mitas.conf > /dev/null <<'EOF'
[Service]
Environment="OLLAMA_MODELS=/opt/mitas/models/ollama"
Environment="OLLAMA_HOST=127.0.0.1:11434"
EOF
sudo -n systemctl daemon-reload

echo "=== [3/5] 3 özel model blob-kopya (E: → F:) ==="
MODELS=("gemma-4-31b-it-qat-vision/latest" "gemma4/26b" "glm-ocr/latest")
for m in "${MODELS[@]}"; do
  mani="$ESRC/manifests/registry.ollama.ai/library/$m"
  [ -f "$mani" ] || { echo "MANIFEST YOK: $m"; continue; }
  echo "--- $m ---"
  dstmani="$MODELDIR/manifests/registry.ollama.ai/library/$m"
  sudo -n mkdir -p "$(dirname "$dstmani")"
  sudo -n cp "$mani" "$dstmani"
  for dig in $(grep -oE 'sha256:[a-f0-9]{64}' "$mani" | sort -u); do
    blob="sha256-${dig#sha256:}"
    if [ -f "$MODELDIR/blobs/$blob" ]; then echo "  var: $blob"; continue; fi
    if [ -f "$ESRC/blobs/$blob" ]; then
      echo "  kopya ($(du -h "$ESRC/blobs/$blob" | cut -f1)): $blob"
      sudo -n cp "$ESRC/blobs/$blob" "$MODELDIR/blobs/$blob"
    else echo "  ! KAYNAK BLOB YOK: $blob"; fi
  done
done
sudo -n chown -R ollama:ollama "$MODELDIR" 2>/dev/null || sudo -n chown -R root:root "$MODELDIR"
sudo -n chmod -R a+rX "$MODELDIR"

echo "=== [4/5] servis başlat + 2 standart model pull ==="
sudo -n systemctl enable --now ollama
sleep 3
for i in 1 2 3 4 5; do curl -s http://127.0.0.1:11434/api/tags >/dev/null && break; sleep 2; done
ollama pull qwen2.5vl:7b
ollama pull qwen3:8b

echo "=== [5/5] doğrulama ==="
ollama list
echo "OLLAMA-TAMAM $(date)"
