#!/usr/bin/env bash
# ATLAS Faz E-3: HF-cache (pyannote+laion) + faster-whisper + insightface -> F-ici kopya.
# Salt-okuma E:\ATLAS'tan; hicbir dosya degistirilmez/silinmez.
set -euo pipefail
SRC=/mnt/e/ATLAS
DST=/opt/atlas

echo "=== hf-cache (pyannote diarization + laion CLIP, offline-pin) ==="
mkdir -p "$DST/hf-cache"
cp -a "$SRC/hf-cache/." "$DST/hf-cache/"
du -sh "$DST/hf-cache"

echo "=== faster-whisper large-v3-turbo ==="
mkdir -p "$DST/models/asr"
cp -a "$SRC/models/asr/." "$DST/models/asr/"
du -sh "$DST/models/asr"

echo "=== insightface buffalo_l ==="
mkdir -p "$DST/models/insightface"
cp -a "$SRC/models/insightface/." "$DST/models/insightface/"
du -sh "$DST/models/insightface"

echo "HF_LOCAL_MODELS_COPIED_OK"
