#!/usr/bin/env bash
# ATLAS Faz D: 7 venv (core, ocr, asr, visual, face, nlp, audio). `lab` ERTELENDI
# (deneysel, Cagatay'in acik karari bekliyor - plan sS10 madde-4, MITAS emsali "simdilik HAYIR").
# MITAS build_venv3.sh kanitlanmis deseni: paddle(once) -> reqs(opencv-tek+strip) -> torch(SON) -> import-check.
set -uo pipefail
PY=/root/.pyenv/versions/3.10.11/bin/python
ROOT=/opt/atlas
REQS=$ROOT/linux/reqs
LOGD=$ROOT/linux/setup/logs
mkdir -p "$LOGD"

TORCH_IDX=https://download.pytorch.org/whl/cu126
PADDLE_IDX=https://www.paddlepaddle.org.cn/packages/stable/cu126/

# Windows-ozgu + ayri-kurulan (torch/nvidia/paddle) + TUM opencv (tekine indirilecek)
STRIP='^(oneocr|pywin32|pypiwin32|pywin32-ctypes|pywinpty|win32|win32_setctime|windows-curses|colorama|tensorflow-intel|torch==|torchvision==|torchaudio==|torch$|nvidia-|nvidia_|triton==|paddlepaddle-gpu==|paddlepaddle_gpu==|paddlepaddle==|opencv-python==|opencv_python==|opencv-contrib-python==|opencv_contrib_python==|opencv-python-headless==|opencv_python_headless==|opencv-contrib-python-headless==|opencv_contrib_python_headless==|pyreadline3==)'

# cu126-torch (GPU asr/visual/face) | paddle-index (ocr) | cpu-torch varsayilan-pypi (nlp) | duz (core/audio)
GPU_TORCH_CU126=" asr visual face "
PADDLE_PROFILES=" ocr "
CPU_TORCH_PROFILES=" nlp "
# ocr: paddlex/paddleocr non-headless opencv ister (MITAS Faz-D kanitli: 5.0.0.93, gapi-bug yok).
# digerleri: headless yeterli (goruntu yok, sunucu).
NONHEADLESS_OPENCV_PROFILES=" ocr "

ver() { grep -iE "^$2==" "$1" | head -1 | sed -E "s/^$2==([0-9]+\.[0-9]+(\.[0-9]+)?).*/\1/"; }
# torch/torchvision/torchaudio: TAM surumu (+cuXXX yerel etiketi DAHIL) koru -
# bare X.Y.Z ile pip cu126-index'te uyumsuz (ornegin cu130) bir varyanti sessizce
# secebiliyor (ASR ilk denemede kanitlandi: torchaudio libcudart.so.13 ariyordu).
ver_full() { grep -iE "^$2==" "$1" | head -1 | sed -E "s/^$2==//"; }

for p in "$@"; do
  req=$REQS/$p.txt
  log=$LOGD/$p.log
  if [ ! -f "$req" ]; then echo "SKIP $p (reqs yok)"; continue; fi
  echo "================ VENV: $p ================"
  : > "$log"
  rm -rf "$ROOT/venvs/$p"
  "$PY" -m venv "$ROOT/venvs/$p"
  vpy="$ROOT/venvs/$p/bin/python"
  "$vpy" -m pip install -q --upgrade pip wheel setuptools >>"$log" 2>&1

  # 1) paddle ONCE (varsa)
  if echo "$PADDLE_PROFILES" | grep -q " $p "; then
    pver=$(ver "$req" paddlepaddle_gpu); [ -z "$pver" ] && pver=$(ver "$req" paddlepaddle-gpu)
    "$vpy" -m pip install "paddlepaddle-gpu==$pver" -i "$PADDLE_IDX" >>"$log" 2>&1 \
      && echo "[paddle OK $pver]" || echo "[paddle HATA -> $log]"
  fi

  # 2) ana reqs (strip'li: torch/nvidia/paddle/opencv/win-ozgu disarida)
  linf="$LOGD/${p}_lin.txt"
  grep -viE "$STRIP" "$req" | grep -v '^#' > "$linf"
  if "$vpy" -m pip install -r "$linf" >>"$log" 2>&1; then echo "[reqs OK]"; else echo "[reqs HATA -> $log]"; fi

  # 2b) opencv (varsa) -> TEK temiz surum
  if grep -qiE '^opencv' "$req"; then
    if echo "$NONHEADLESS_OPENCV_PROFILES" | grep -q " $p "; then
      "$vpy" -m pip install "opencv-contrib-python==5.0.0.93" >>"$log" 2>&1 \
        && echo "[opencv non-headless 5.0.0.93 OK]" || echo "[opencv HATA]"
    else
      "$vpy" -m pip install "opencv-contrib-python-headless>=4.11" >>"$log" 2>&1 \
        && echo "[opencv headless OK]" || echo "[opencv HATA]"
    fi
  fi

  # 3) torch SON (nccl torch kazansin) - ONCE: adim-2'nin (open_clip/timm/transformers/
  # pyannote/speechbrain gibi paketlerin UNPINNED "torch" bagimliligi uzerinden) sessizce
  # surukleyebilecegi YANLIS torch/torchvision/torchaudio + nvidia-*-cu13 kutuphanelerini
  # TEMIZLE (ASR ilk denemede kanitlandi: adim-2 cu13-linked torchaudio surukledi, .so
  # libcudart.so.13 ariyordu ama surucu 12.6-max). Boylece adim-3 GERCEKTEN temiz kurar.
  if echo "$GPU_TORCH_CU126 $CPU_TORCH_PROFILES" | grep -q " $p "; then
    "$vpy" -m pip uninstall -y torch torchvision torchaudio torchcodec triton \
      $("$vpy" -m pip list 2>/dev/null | grep -iE '^nvidia-' | awk '{print $1}') \
      >>"$log" 2>&1 || true
  fi
  if echo "$GPU_TORCH_CU126" | grep -q " $p "; then
    tver=$(ver_full "$req" torch); tvis=$(ver_full "$req" torchvision); taud=$(ver_full "$req" torchaudio)
    pkgs=""; [ -n "$tver" ] && pkgs="torch==$tver"; [ -n "$tvis" ] && pkgs="$pkgs torchvision==$tvis"; [ -n "$taud" ] && pkgs="$pkgs torchaudio==$taud"
    if [ -n "$pkgs" ]; then
      "$vpy" -m pip install $pkgs --index-url "$TORCH_IDX" >>"$log" 2>&1 && echo "[torch cu126 OK]" || {
        echo "[torch cu126 exact-version HATA, versiyonsuz deneniyor]"
        "$vpy" -m pip install torch torchvision torchaudio --index-url "$TORCH_IDX" >>"$log" 2>&1 \
          && echo "[torch cu126 (versiyonsuz) OK]" || echo "[torch cu126 HATA -> $log]"
      }
    fi
  elif echo "$CPU_TORCH_PROFILES" | grep -q " $p "; then
    tver=$(ver "$req" torch)
    "$vpy" -m pip install "torch==$tver" >>"$log" 2>&1 && echo "[torch CPU $tver OK]" || {
      "$vpy" -m pip install torch >>"$log" 2>&1 && echo "[torch CPU (versiyonsuz) OK]" || echo "[torch CPU HATA -> $log]"
    }
  fi
  # 3b) dogrulama: kalan nvidia-*-cu13 kutuphanesi VAR MI (sessiz-yanlis-surum guard'i)
  if echo "$GPU_TORCH_CU126" | grep -q " $p "; then
    bad=$("$vpy" -m pip list 2>/dev/null | grep -icE '\-cu13\b')
    [ "$bad" != "0" ] && echo "[UYARI: $bad adet -cu13 paket hala kurulu -> muhtemel surum-karisikligi]"
  fi

  # 4) import-check (profile-farkli anahtar paketler)
  case "$p" in
    core)   "$vpy" -c "import sqlalchemy, alembic, cv2, reportlab, pandas, streamlit; print('[IMPORT core OK]')" 2>&1 | tail -3 ;;
    ocr)    "$vpy" -c "import paddle; from paddleocr import PaddleOCR; import cv2; print('[IMPORT ocr OK] paddle', paddle.__version__)" 2>&1 | tail -5 ;;
    asr)    "$vpy" -c "import torch, faster_whisper, pyannote.audio; print('[IMPORT asr OK] cuda=', torch.cuda.is_available())" 2>&1 | tail -5 ;;
    visual) "$vpy" -c "import torch, cv2; from scenedetect import open_video; import open_clip; print('[IMPORT visual OK] cuda=', torch.cuda.is_available())" 2>&1 | tail -5 ;;
    face)   "$vpy" -c "import torch, cv2, insightface, onnxruntime; print('[IMPORT face OK] cuda=', torch.cuda.is_available(), 'ort_providers=', onnxruntime.get_available_providers())" 2>&1 | tail -5 ;;
    nlp)    "$vpy" -c "import torch, gliner, transformers; print('[IMPORT nlp OK] cuda(should be False/CPU)=', torch.cuda.is_available())" 2>&1 | tail -5 ;;
    audio)  "$vpy" -c "import librosa, scipy, soundfile; print('[IMPORT audio OK]')" 2>&1 | tail -3 ;;
  esac
  echo "DONE: $p"
done
echo "BUILD_D_DONE"
