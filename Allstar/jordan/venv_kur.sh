#!/usr/bin/env bash
# Jordan kulesinin calisma zamanini SIFIRDAN kurar.
#
# Kullanim:  ./venv_kur.sh          (varsa dokunmaz)
#            ./venv_kur.sh --temiz  (sifirdan kurar)
#
# NOT: model agirliklari BURADA kurulmaz — bkz. model_kur.sh.
set -euo pipefail

J="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMEL="/home/cagatay/.pyenv/versions/3.12.13/bin/python3.12"   # Kobe ile ayni
[ -x "$TEMEL" ] || TEMEL="$(command -v python3.12 || command -v python3)"

[ "${1:-}" = "--temiz" ] && rm -rf "$J/venv"

if [ ! -x "$J/venv/bin/python" ]; then
  echo "[1/3] venv olusturuluyor ($("$TEMEL" -V))"
  "$TEMEL" -m venv "$J/venv"
fi
P="$J/venv/bin/python"

echo "[2/3] pip guncelleniyor"
"$P" -m pip install --upgrade pip -q

# Cikis kodu KAYBOLMASIN: Kobe'de kurulum `| tail`den gecirilmis ve kabuk
# pip'in degil tail'in kodunu dondurup BASARISIZ kurulumu "exit 0" gostermisti.
echo "[3/3] bagimliliklar (torch CUDA tekerlekleri ~5 GB, surebilir)"
"$P" -m pip install -r "$J/gereksinimler.txt"

echo
echo "=== DOGRULAMA ==="
"$P" - <<'PY'
import torch, transformers, compressed_tensors, av
print("torch             ", torch.__version__, "| cuda:", torch.cuda.is_available())
print("transformers      ", transformers.__version__)
print("compressed-tensors", compressed_tensors.__version__)
print("av                ", av.__version__)
if torch.cuda.is_available():
    ad = torch.cuda.get_device_name(0)
    mm = torch.cuda.get_device_capability(0)
    print(f"gpu                {ad} sm_{mm[0]}{mm[1]}")
    if mm < (8, 9):
        print("  NOT: sm_89 altinda FP8 cekirdegi YOK — 8-bit icin INT8 (w8a8) kullanilir.")
PY
