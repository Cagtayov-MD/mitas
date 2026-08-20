#!/usr/bin/env bash
set -euo pipefail
KULE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -m venv "$KULE/venv"
"$KULE/venv/bin/python" -m pip install --upgrade pip
"$KULE/venv/bin/python" -m pip install -r "$KULE/gereksinimler.txt"
