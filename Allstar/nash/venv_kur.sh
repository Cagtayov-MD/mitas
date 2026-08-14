#!/usr/bin/env bash
# Nash kulesinin kendi calisma zamani. --temiz ile sifirdan kurar.
set -euo pipefail
N="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ "${1:-}" = "--temiz" ] && rm -rf "$N/venv"
# 3.12.13 ZORUNLU: referans olcum verisini ureten ortam bu (venvs/ocr).
# Sistem python3'u 3.14 — havuz cikitisinin surumden bagimsiz oldugu
# OLCULMEDEN varsayilmaz (Kobe dersi: ortam butun olarak dondurulur).
PY312="${MITAS_PY312:-$HOME/.pyenv/versions/3.12.13/bin/python3.12}"
[ -x "$PY312" ] || { echo "HATA: python 3.12.13 bulunamadi: $PY312" >&2; exit 1; }
[ -d "$N/venv" ] || "$PY312" -m venv "$N/venv"
"$N/venv/bin/pip" install --quiet --upgrade pip
"$N/venv/bin/pip" install --quiet -r "$N/gereksinimler.txt"
echo "Nash venv hazir: $("$N/venv/bin/python" -V)"
"$N/venv/bin/python" - <<'PY'
import numpy, cv2
print(f"  numpy  {numpy.__version__}")
print(f"  opencv {cv2.__version__}")
PY
