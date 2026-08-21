#!/usr/bin/env bash
set -euo pipefail
K="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
if [[ "${1:-}" == "--temiz" ]]; then rm -rf "$K/venv"; fi
"$PY" -m venv "$K/venv"
"$K/venv/bin/python" -m pip install --upgrade pip
"$K/venv/bin/pip" install -r "$K/gereksinimler.txt"
"$K/venv/bin/python" -m pytest -q "$K/tests"
