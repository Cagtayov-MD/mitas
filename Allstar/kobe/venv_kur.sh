#!/usr/bin/env bash
# Kobe kulesinin calisma zamanini SIFIRDAN kurar (spec karar 11).
#
# Neden ayri betik: paddlepaddle-gpu 3.x PyPI'de YOK (orada yalniz 2.6.x var).
# Paddle kendi indeksinden dagitiyor, bu yuzden duz `pip install -r` yetmiyor.
# Tarif reponun kendi kurulum betiginden alindi: kurulum/02_build_venv.sh:88-89.
#
# Kullanim:  ./venv_kur.sh          (varsa dokunmaz)
#            ./venv_kur.sh --temiz  (sifirdan kurar)
set -euo pipefail

K="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMEL="/home/cagatay/.pyenv/versions/3.12.13/bin/python3.12"   # venvs/ocr ile ayni
PADDLE_SURUM="3.3.1"
OPENCV_SURUM="5.0.0.93"
IDX_1="https://www.paddlepaddle.org.cn/packages/stable/cu126/"
IDX_2="https://www.paddlepaddle.org.cn/packages/stable/cu129/"

[ "${1:-}" = "--temiz" ] && rm -rf "$K/.venv"

if [ ! -x "$K/.venv/bin/python" ]; then
  echo "[1/4] venv olusturuluyor ($("$TEMEL" -V))"
  "$TEMEL" -m venv "$K/.venv"
fi
P="$K/.venv/bin/python"

echo "[2/4] pip guncelleniyor"
"$P" -m pip install --upgrade pip -q

echo "[3/4] paddlepaddle-gpu==$PADDLE_SURUM (Paddle kendi indeksi)"
"$P" -m pip install "paddlepaddle-gpu==$PADDLE_SURUM" -i "$IDX_1" \
  || "$P" -m pip install "paddlepaddle-gpu==$PADDLE_SURUM" -i "$IDX_2"

echo "[4/5] PyPI bagimliliklari"
"$P" -m pip install -r "$K/gereksinimler.txt"

# [5] opencv SON adimda ve BILEREK cakisarak kurulur.
# paddlex[ocr-core]==3.7.2 "opencv-contrib-python==4.10.0.84" istiyor, ama
# olcumun yapildigi venvs/ocr'da 5.0.0.93 duruyor (sonradan yukseltilmis).
# Kobe'nin kendi dosyalari cv2'yi HIC import etmiyor; opencv yalniz paddleocr/
# paddlex icinden dolayli kullaniliyor. Kapi "ayni davranis" istedigi icin
# olcumun yapildigi surumu esliyoruz — 4.10'da kalmak test edilmemis secim olurdu.
# gereksinimler.txt icinde OLAMAZ: pip cozumleyicisi ayni gecte iki celiskili
# kisiti gorup ResolutionImpossible verir. Ayri adimda ustune yazilir.
echo "[5/5] opencv-contrib-python==$OPENCV_SURUM (venvs/ocr ile ayni)"
"$P" -m pip install "opencv-contrib-python==$OPENCV_SURUM"

echo
echo "=== DOGRULAMA ==="
"$P" - <<'PY'
import paddle, paddleocr, numpy, PIL, cv2
print("paddle    ", paddle.__version__, "| cuda:", paddle.is_compiled_with_cuda())
print("paddleocr ", paddleocr.__version__)
print("numpy     ", numpy.__version__)
print("pillow    ", PIL.__version__)
print("opencv    ", cv2.__version__)
PY
