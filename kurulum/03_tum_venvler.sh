#!/bin/bash
# MITAS 18 venv sürücüsü — sırayla kurar, hata olsa da devam eder, sonda özet verir
set -u
KOK=/opt/mitas
LOGD="$KOK/kurulum/logs"
mkdir -p "$LOGD"
exec > >(tee "$LOGD/03_tum_venvler.log") 2>&1
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"

echo "=== Python 3.10 (en güncel) garanti ediliyor ==="
P310=$(pyenv install --list | grep -E '^\s*3\.10\.[0-9]+$' | tail -1 | tr -d ' ')
MAKE_OPTS="-j32" pyenv install -s "$P310" && echo "P310-OK=$P310"

echo "=== torch index probe (cu130 → cu126) ==="
TPROBE=$("$PYENV_ROOT/versions/$P310/bin/python" -m pip index versions torch --index-url https://download.pytorch.org/whl/cu130 2>/dev/null | head -1)
if [ -n "$TPROBE" ]; then
  export TORCH_INDEX="https://download.pytorch.org/whl/cu130"
else
  export TORCH_INDEX="https://download.pytorch.org/whl/cu126"
fi
echo "TORCH_INDEX=$TORCH_INDEX ($TPROBE)"

SIRA=(core tag ocr visual stt alignment denoise face audio translate tts asr ina vlm locateanything nemo internvl minicpmv)
declare -A SONUC
for v in "${SIRA[@]}"; do
  echo ""
  echo "########## VENV: $v ($(date +%H:%M)) ##########"
  if bash "$KOK/kurulum/02_build_venv.sh" "$v"; then
    SONUC[$v]="OK"
  else
    SONUC[$v]="HATA(exit=$?)"
  fi
  echo "SONUC[$v]=${SONUC[$v]}"
done

echo ""
echo "=========== 18 VENV ÖZET ==========="
for v in "${SIRA[@]}"; do printf "%-16s %s\n" "$v" "${SONUC[$v]}"; done
echo "VENV-SURUCU-BITTI $(date)"
