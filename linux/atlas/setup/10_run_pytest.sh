#!/usr/bin/env bash
# ATLAS Faz H-1: pytest tests/ (core venv - testler agirlikli core/db/facet mantigi).
# Video/GPU gerektirmeyen testler icin core venv yeterli olmali; asr/ocr/face-bagimli
# testler ilgili venv olmadan (henuz kurulmadiysa) hata verebilir - o testler ayrica
# not edilir, KAPI H tam degerlendirmesi tum venv'ler + test verisi sonrasi yapilir.
set -uo pipefail
cd /opt/atlas
set -a; source /opt/atlas/atlas.env; set +a
export PYTHONPATH=/opt/atlas/src
/opt/atlas/venvs/core/bin/python -m pytest tests/ -q 2>&1 | tee /opt/atlas/linux/setup/logs/pytest_run.log
echo "PYTEST_EXIT=${PIPESTATUS[0]}"
