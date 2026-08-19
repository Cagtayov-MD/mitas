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
# 2026-08-18'den once Paddle bu venv'e kuruluyordu. O kurulumun CUDA 12
# paketlerini bir kez temizle; aksi halde Torch CUDA 13 yanlis libnccl acar.
if "$N/venv/bin/pip" show paddlepaddle-gpu >/dev/null 2>&1; then
  "$N/venv/bin/pip" uninstall --quiet -y \
    paddlepaddle-gpu paddleocr paddlex \
    nvidia-cublas-cu12 nvidia-cuda-cccl-cu12 nvidia-cuda-cupti-cu12 \
    nvidia-cuda-nvrtc-cu12 nvidia-cuda-runtime-cu12 nvidia-cudnn-cu12 \
    nvidia-cufft-cu12 nvidia-cufile-cu12 nvidia-curand-cu12 \
    nvidia-cusolver-cu12 nvidia-cusparse-cu12 nvidia-cusparselt-cu12 \
    nvidia-nccl-cu12 nvidia-nvjitlink-cu12 nvidia-nvtx-cu12
  # Iki dagitimin ortak `nvidia/*/lib` dosyalari ezilmis olabilir. Metadata
  # kurulu gorundugu icin normal `pip install -r` bunlari onarmaz; CUDA 13
  # runtime paketlerini bir defa zorla geri koy.
  "$N/venv/bin/pip" install --quiet --force-reinstall --no-deps \
    "nvidia-cublas==13.1.0.3" "nvidia-cuda-cupti==13.0.85" \
    "nvidia-cuda-nvrtc==13.0.88" "nvidia-cuda-runtime==13.0.96" \
    "nvidia-cudnn-cu13==9.19.0.56" "nvidia-cufft==12.0.0.61" \
    "nvidia-cufile==1.15.1.6" "nvidia-curand==10.4.0.35" \
    "nvidia-cusolver==12.0.4.66" "nvidia-cusparse==12.6.3.3" \
    "nvidia-cusparselt-cu13==0.8.0" "nvidia-nccl-cu13==2.28.9" \
    "nvidia-nvjitlink==13.0.88" "nvidia-nvshmem-cu13==3.4.5" \
    "nvidia-nvtx==13.0.85"
fi
"$N/venv/bin/pip" install --quiet -r "$N/gereksinimler.txt"
# Ana-havuz text detectoru hem surec hem venv olarak ayridir. Paddle CUDA 12
# ve Torch CUDA 13 paketleri ayni site-packages'ta `nvidia/nccl` yolunu ortak
# kullaniyor; yan yana kurulurlarsa son kurulan digerinin libnccl.so'sunu
# ezer. Ayrı venv bu ABI cakismasini ve VRAM omurlerini birlikte kapatir.
[ "${1:-}" = "--temiz" ] && rm -rf "$N/detector_venv"
[ -d "$N/detector_venv" ] || "$PY312" -m venv "$N/detector_venv"
"$N/detector_venv/bin/pip" install --quiet --upgrade pip
"$N/detector_venv/bin/pip" install --quiet \
  "paddlepaddle-gpu==3.3.1" \
  -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
"$N/detector_venv/bin/pip" install --quiet \
  "paddleocr==3.7.0" "paddlex==3.7.2" \
  "opencv-contrib-python==4.10.0.84"
# Ana Nash venv'i referans OpenCV 5.0'da kalir. Detector venv'inde 4.10,
# PaddleX 3.7.2'nin resmi ve tam pinli `ocr-core` bagimliligidir.

# Paddle agirliklarini genel ~/.paddlex cache'ine emanet etme. Ilk kurulumda
# resmi modeller cache'e iner, sonra Nash model alanina kopyalanir. Uretim
# worker'i yalniz bu yerel dizinleri kullanir.
if [ ! -f "$N/model/paddle/PP-OCRv6_medium_det/inference.yml" ] || \
   [ ! -f "$N/model/paddle/latin_PP-OCRv5_mobile_rec/inference.yml" ] || \
   [ ! -f "$N/model/paddle/arabic_PP-OCRv5_mobile_rec/inference.yml" ] || \
   [ ! -f "$N/model/paddle/eslav_PP-OCRv5_mobile_rec/inference.yml" ]; then
  PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
    "$N/detector_venv/bin/python" - <<'PY'
from paddleocr import PaddleOCR
PaddleOCR(text_detection_model_name="PP-OCRv6_medium_det",
          text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
          use_doc_orientation_classify=False, use_doc_unwarping=False,
          use_textline_orientation=False, device="cpu")
PaddleOCR(text_detection_model_name="PP-OCRv6_medium_det",
          text_recognition_model_name="arabic_PP-OCRv5_mobile_rec",
          use_doc_orientation_classify=False, use_doc_unwarping=False,
          use_textline_orientation=False, device="cpu")
PaddleOCR(text_detection_model_name="PP-OCRv6_medium_det",
          text_recognition_model_name="eslav_PP-OCRv5_mobile_rec",
          use_doc_orientation_classify=False, use_doc_unwarping=False,
          use_textline_orientation=False, device="cpu")
PY
  mkdir -p "$N/model/paddle/PP-OCRv6_medium_det" \
           "$N/model/paddle/latin_PP-OCRv5_mobile_rec" \
           "$N/model/paddle/arabic_PP-OCRv5_mobile_rec" \
           "$N/model/paddle/eslav_PP-OCRv5_mobile_rec"
  cp -a "$HOME/.paddlex/official_models/PP-OCRv6_medium_det/." \
        "$N/model/paddle/PP-OCRv6_medium_det/"
  cp -a "$HOME/.paddlex/official_models/latin_PP-OCRv5_mobile_rec/." \
        "$N/model/paddle/latin_PP-OCRv5_mobile_rec/"
  cp -a "$HOME/.paddlex/official_models/arabic_PP-OCRv5_mobile_rec/." \
        "$N/model/paddle/arabic_PP-OCRv5_mobile_rec/"
  cp -a "$HOME/.paddlex/official_models/eslav_PP-OCRv5_mobile_rec/." \
        "$N/model/paddle/eslav_PP-OCRv5_mobile_rec/"
fi
"$N/venv/bin/pip" check
"$N/detector_venv/bin/pip" check
echo "Nash venv hazir: $("$N/venv/bin/python" -V)"
"$N/venv/bin/python" - <<'PY'
import numpy, cv2, torch, transformers
print(f"  numpy  {numpy.__version__}")
print(f"  opencv {cv2.__version__}")
print(f"  torch {torch.__version__}")
print(f"  transformers {transformers.__version__}")
PY
"$N/detector_venv/bin/python" - <<'PY'
import cv2, paddle
print(f"  detector paddle {paddle.__version__}")
print(f"  detector opencv {cv2.__version__}")
PY
