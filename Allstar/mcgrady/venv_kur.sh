#!/usr/bin/env bash
# McGrady kulesinin çalışma zamanını kurar (kobe venv_kur.sh kalıbı, hafif kule).
#
# Kullanım:  ./venv_kur.sh          (varsa dokunmaz)
#            ./venv_kur.sh --temiz  (sıfırdan kurar)
set -euo pipefail

K="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMEL="/home/cagatay/.pyenv/versions/3.12.13/bin/python3.12"   # kobe ile aynı temel

[ "${1:-}" = "--temiz" ] && rm -rf "$K/venv"

if [ ! -x "$K/venv/bin/python" ]; then
  echo "[1/3] venv olusturuluyor ($("$TEMEL" -V))"
  "$TEMEL" -m venv "$K/venv"
fi
P="$K/venv/bin/python"

echo "[2/3] pip guncelleniyor"
"$P" -m pip install --upgrade pip -q

echo "[3/3] bagimliliklar (pin'li)"
"$P" -m pip install -r "$K/gereksinimler.txt"

echo
echo "=== DOGRULAMA ==="
"$P" - <<'PY'
import duckdb, PIL, yaml
print("duckdb", duckdb.__version__)
print("pillow", PIL.__version__)
print("yaml   ", yaml.__version__)
PY
