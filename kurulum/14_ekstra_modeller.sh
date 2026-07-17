#!/bin/bash
# Ekstra modeller: qwen3-vl:30b + qwen36-27b/35b-test (E:\OllamaModels → MITAS ollama deposu)
#                  + QwenOmni deney alanı (D: → /opt/mitas/models/QwenOmni)
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/14_ekstra_modeller.log
exec > >(tee "$LOG") 2>&1
MODELDIR=/opt/mitas/models/ollama
ESRC="/mnt/e/OllamaModels"
DSRC="/run/media/cagatay/Yeni Birim/QwenOmni"

echo "=== [1/3] 3 ekstra ollama modeli blob-kopya $(date) ==="
for m in "qwen3-vl/30b" "qwen36-27b-test/latest" "qwen36-35b-test/latest"; do
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
sudo -n chown -R ollama:ollama "$MODELDIR" && sudo -n chmod -R a+rX "$MODELDIR"

echo "=== [2/3] QwenOmni deney alanı (49G, D: → F:) ==="
mkdir -p /opt/mitas/models/QwenOmni
rsync -rlt --info=progress2 "$DSRC/" /opt/mitas/models/QwenOmni/ 2>&1 | tail -1

echo "=== [3/3] doğrulama ==="
ollama list
du -sh /opt/mitas/models/QwenOmni
echo "EKSTRA-MODELLER-TAMAM $(date)"
