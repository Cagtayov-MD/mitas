#!/bin/bash
# MITAS venv kurucu — "en güncel + istisna pinler" politikası
# Kullanım: 02_build_venv.sh <venv_adi>
# Politika:
#   - Varsayılan: freeze'deki pinler SÖKÜLÜR → pip en günceli çözer
#   - İstisna venv'ler (model/framework kilidi): pinler AYNEN korunur
#   - torch: cu130 (fallback cu126) index'ten EN GÜNCEL; ocr'de paddle ÖNCE, torch EN SON
#   - Windows-only paketler süzülür; opencv → TEK opencv-contrib-python
#   - Başarıda: import-smoke + yeni kanonik freeze (linux/reqs_linux/<ad>.txt)
set -uo pipefail
AD="${1:?venv adi gerekli}"
KOK=/opt/mitas
REQ="$KOK/linux/reqs/$AD.txt"
VENV="$KOK/venvs/$AD"
LOGD="$KOK/kurulum/logs"
YENI_REQS="$KOK/linux/reqs_linux"
mkdir -p "$LOGD" "$YENI_REQS" "$KOK/venvs"
LOG="$LOGD/venv_$AD.log"
exec > >(tee "$LOG") 2>&1
export PYENV_ROOT="$HOME/.pyenv"
[ -f "$REQ" ] || { echo "HATA: $REQ yok"; exit 2; }

# ---- Python sürüm seçimi ----
case "$AD" in
  ina|asr|vlm|locateanything) PYMINOR="3.10" ;;   # tf2.11 / decord kısıtı
  denoise)                    PYMINOR="3.11" ;;   # DeepFilterLib son wheel cp311 (cp312 YOK)
  *)                          PYMINOR="3.12" ;;
esac
PYVER=$(ls "$PYENV_ROOT/versions/" | grep -E "^${PYMINOR}\." | sort -V | tail -1)
[ -n "$PYVER" ] || { echo "HATA: pyenv'de $PYMINOR yok"; exit 3; }
PYBIN="$PYENV_ROOT/versions/$PYVER/bin/python"
echo "=== $AD → Python $PYVER ==="

# ---- Pin politikası ----
PIN_KORU=0   # 1: freeze pinleri aynen (istisna venv)
case "$AD" in
  ina|asr) PIN_KORU=1 ;;            # tensorflow 2.11 ekosistemi kırılgan
esac

# ---- torch index (driver CUDA 13.2) ----
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cu130}"
case "$AD" in
  translate) TORCH_INDEX="https://download.pytorch.org/whl/cpu" ;;  # CPU venv
  internvl)  TORCH_INDEX="https://download.pytorch.org/whl/cu121" ;; # torch 2.5.1 kilidi
esac

# ---- req listesi hazırla ----
TMP=$(mktemp -d)
# 1) Windows-only + yönetilen paketleri süz
grep -vE '^\s*(#|$)' "$REQ" \
 | grep -viE '^(oneocr|pywin32|pypiwin32|winocr|wmi|windows-curses|win32-setctime|win32_setctime|tensorflow-intel|pyreadline3?)\b' \
 | grep -vE '^(nvidia-|triton)' \
 | grep -vE '^(torch|torchvision|torchaudio)\b' \
 | grep -vE '^(opencv-|opencv_)' \
 | grep -vE ' @ file://' \
 | grep -viE '^craft[-_]text[-_]detector\b' \
 > "$TMP/liste_pinli.txt"
# craft-text-detector: kodda 0 kullanım + py3.12'de kurulamaz (opencv<4.5.4.62 kaynak-derleme) → bilinçli dışarıda
OPENCV_VAR=$(grep -cE '^(opencv-|opencv_)' "$REQ" || true)
# ocr: paddle ayrı yönetilir
if [ "$AD" = "ocr" ]; then
  grep -viE '^(paddle|aistudio)' "$TMP/liste_pinli.txt" > "$TMP/t" && mv "$TMP/t" "$TMP/liste_pinli.txt"
fi
# 2) pin söküm (URL'li satırlara dokunma)
if [ "$PIN_KORU" = "1" ]; then
  cp "$TMP/liste_pinli.txt" "$TMP/liste.txt"
else
  awk '{ if ($0 ~ / @ https?:\/\//) print; else { sub(/==.*/,""); print } }' "$TMP/liste_pinli.txt" > "$TMP/liste.txt"
fi
# 3) venv-özel kilit pinleri geri yaz
kilitle() { local pkg="$1" pin="$2"; sed -i -E "s|^${pkg}$|${pkg}==${pin}|" "$TMP/liste.txt"; }
case "$AD" in
  minicpmv)  kilitle transformers 4.44.2 ;;
  internvl)  kilitle transformers 4.52.4 ;;
  vlm|locateanything) kilitle decord 0.6.0 ;;
  denoise)   kilitle DeepFilterLib 0.5.6; kilitle DeepFilterNet 0.5.6 ;;  # son sürüm zaten bu (2023-son)
esac

# ---- venv kur ----
rm -rf "$VENV"
"$PYBIN" -m venv "$VENV"
P="$VENV/bin/pip"
"$VENV/bin/python" -m pip install -q -U pip wheel setuptools || exit 4

# ---- ocr: paddle ÖNCE (kanıtlı sıra) ----
if [ "$AD" = "ocr" ]; then
  echo "--- paddlepaddle-gpu (Paddle index, en güncel) ---"
  "$P" install paddlepaddle-gpu -i https://www.paddlepaddle.org.cn/packages/stable/cu126/ \
    || "$P" install paddlepaddle-gpu -i https://www.paddlepaddle.org.cn/packages/stable/cu129/ \
    || { echo "PADDLE-HATA"; exit 5; }
  echo "--- paddleocr + paddlex[ocr] (en güncel) ---"
  "$P" install paddleocr "paddlex[ocr]" || { echo "PADDLEOCR-HATA"; exit 5; }
fi

# ---- torch (ocr HARİÇ önce; ocr'de EN SON) ----
torch_kur() {
  if [ "$AD" = "internvl" ]; then
    "$P" install torch==2.5.1 torchvision==0.20.1 --index-url "$TORCH_INDEX"
  elif [ "$AD" = "denoise" ]; then
    # DeepFilterNet 0.5.6 → torchaudio.backend API'si 2.9+'ta yok; WSL-kanıtlı 2.8.0+cu126
    "$P" install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126
  else
    "$P" install -U torch torchvision torchaudio --index-url "$TORCH_INDEX" \
      || "$P" install -U torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
  fi
}
GEREK_TORCH=$(grep -cE '^(torch|torchvision|torchaudio)' "$REQ" || true)
if [ "$GEREK_TORCH" -gt 0 ] && [ "$AD" != "ocr" ]; then torch_kur || { echo "TORCH-HATA"; exit 6; }; fi

# ---- ana liste ----
echo "--- ana paket listesi ($(wc -l < "$TMP/liste.txt") satır) ---"
"$P" install -r "$TMP/liste.txt" || {
  echo "İLK-DENEME-HATA → legacy-resolver deneniyor"
  "$P" install --use-deprecated=legacy-resolver -r "$TMP/liste.txt" || { echo "ANA-LISTE-HATA"; exit 7; }
}

# ---- alignment: whisperx eski ctranslate2 (4.4, execstack-hatalı) getiriyor → en güncele zorla ----
if [ "$AD" = "alignment" ]; then
  "$P" install -U ctranslate2 || { echo "CT2-HATA"; exit 10; }
fi
# ---- translate: legacy-resolver transformers↔tokenizers çiftini bozabiliyor → çifti birlikte çöz ----
if [ "$AD" = "translate" ]; then
  "$P" install -U transformers tokenizers || { echo "TR-TOK-HATA"; exit 11; }
fi

# ---- opencv: TEK paket kuralı ----
if [ "$OPENCV_VAR" -gt 0 ] || [ "$AD" = "ocr" ]; then
  "$P" list 2>/dev/null | grep -iE '^opencv' | awk '{print $1}' | xargs -r "$P" uninstall -y
  "$P" install -U opencv-contrib-python || { echo "OPENCV-HATA"; exit 8; }
fi

# ---- ocr: torch EN SON (paddle nvidia-lib çakışması: torch kazanır) ----
if [ "$AD" = "ocr" ] && [ "$GEREK_TORCH" -gt 0 ]; then torch_kur || { echo "TORCH-HATA"; exit 6; }; fi

# ---- import smoke ----
case "$AD" in
  alignment)      SMOKE="import whisperx, faster_whisper, torch" ;;
  asr)            SMOKE="import faster_whisper, librosa, speechbrain, fastapi, uvicorn" ;;  # TF asr'de üretimde import edilmez (ina kendi venv'inde)
  audio)          SMOKE="import librosa, tensorflow, soundfile" ;;
  core)           SMOKE="import torch, silero_vad, pydantic" ;;
  denoise)        SMOKE="import torch, torchaudio; from df import enhance" ;;
  face)           SMOKE="import insightface, cv2, onnxruntime" ;;
  ina)            SMOKE="import tensorflow; from inaSpeechSegmenter import Segmenter" ;;
  internvl)       SMOKE="import torch, transformers, timm" ;;
  locateanything) SMOKE="import torch, transformers, decord" ;;
  minicpmv)       SMOKE="import torch, transformers, timm" ;;
  ocr)            SMOKE="import paddleocr, easyocr, cv2, torch" ;;
  stt)            SMOKE="import faster_whisper, ctranslate2, torch" ;;
  tag)            SMOKE="import nltk, zeyrek, rapidfuzz" ;;
  translate)      SMOKE="import ctranslate2, transformers" ;;
  tts)            SMOKE="import spacy" ;;
  nemo)           SMOKE="import nemo, torch" ;;
  visual)         SMOKE="import torch, ultralytics, cv2, scenedetect" ;;
  vlm)            SMOKE="import torch, transformers, av, decord" ;;
  *)              SMOKE="print('genel-ok')" ;;
esac
cd /opt/mitas
if "$VENV/bin/python" -c "$SMOKE"; then
  echo "SMOKE-OK"
else
  echo "SMOKE-HATA ($SMOKE)"; exit 9
fi

# ---- yeni kanonik freeze ----
"$P" freeze > "$YENI_REQS/$AD.txt"
rm -rf "$TMP"
echo "VENV-TAMAM=$AD python=$PYVER"
