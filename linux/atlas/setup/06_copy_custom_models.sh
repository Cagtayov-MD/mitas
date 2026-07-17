#!/usr/bin/env bash
# ATLAS Faz E-2: ozel (registry'de olmayan) uretim modellerini E:\OllamaModels'tan
# ATLAS'in KENDI ollama deposuna SECEREK kopyala (manifest + referansli blob'lar).
# Tek seferlik tohum; E:\OllamaModels yalniz OKUNUR, hicbir dosya degistirilmez/silinmez.
# Orijinal MITAS'la HICBIR PAYLASIM yok - blob'lar da AYRI kopyalanir (K-A1/izolasyon).
set -uo pipefail
SRC=/mnt/e/OllamaModels
DST=/opt/atlas/models/ollama
MODELS=("glm-ocr/atlas1" "bge-m3/atlas1" "qwen35-35b-test/latest" "qwen3/8b-atlas1")
mkdir -p "$DST/blobs"
for m in "${MODELS[@]}"; do
  mani="$SRC/manifests/registry.ollama.ai/library/$m"
  if [ ! -f "$mani" ]; then echo "MANIFEST YOK: $m"; continue; fi
  echo "======================== $m ========================"
  dstmani="$DST/manifests/registry.ollama.ai/library/$m"
  mkdir -p "$(dirname "$dstmani")"
  cp "$mani" "$dstmani"
  for dig in $(grep -oE 'sha256:[a-f0-9]{64}' "$mani" | sort -u); do
    blob="sha256-${dig#sha256:}"
    if [ -f "$DST/blobs/$blob" ]; then echo "  zaten var: $blob"; continue; fi
    if [ -f "$SRC/blobs/$blob" ]; then
      sz=$(du -h "$SRC/blobs/$blob" | cut -f1)
      echo "  kopyalaniyor ($sz): $blob"
      cp "$SRC/blobs/$blob" "$DST/blobs/$blob"
    else
      echo "  ! KAYNAK BLOB YOK: $blob"
    fi
  done
done
echo "=== dogrulama ==="
du -sh "$DST"
export OLLAMA_HOST=127.0.0.1:11435
/usr/bin/ollama list 2>&1
echo CUSTOM_MODELS_COPIED_ATLAS_OK
