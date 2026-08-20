#!/usr/bin/env bash
set -euo pipefail
K="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "${1:-}" = "--temiz" ]; then rm -rf "$K/venv"; fi
python3 -m venv "$K/venv"
"$K/venv/bin/python" -m pip install --upgrade pip
"$K/venv/bin/python" -m pip install -r "$K/gereksinimler.txt"
"$K/venv/bin/python" -c 'from PIL import Image; print("Pillow OK", Image.__version__)'
