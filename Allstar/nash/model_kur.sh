#!/usr/bin/env bash
# Nash'in okuma yiginini ve model agirligini kule ICINE kurar (~6.7 GB agirlik
# + ~3 GB torch). Git'te degil (Allstar/.gitignore: */model/).
#
# Neden kule icinde: Kobe'nin surum-dondurma dersi. Ortak bir hf_cache'te veya
# Ollama kutuphanesinde baskasi modeli guncellerse Nash'in ciktisi SESSIZCE
# kayar. Kule kendi agirligini tasir.
#
# YIGIN: DeepSeek-OCR uzak kodunun destekledigi transformers 4.46.3.
# transformers 5.x LlamaFlashAttention2 importunu kaldirdigi icin kullanilmaz.
# numpy 2.3.5'te TUTULUR — Nash'in havuz yarisi bu surume duyarli.
# Kurulumdan SONRA `venv/bin/python olcum/kapi1.py` MUTLAKA yeniden kosulur.
#
# Kullanim: ./model_kur.sh
set -euo pipefail

N="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
P="$N/venv/bin/python"
[ -x "$P" ] || { echo "once ./venv_kur.sh"; exit 1; }

echo "== 1/3 okuma yigini =="
"$N/venv/bin/pip" install --quiet \
  "numpy==2.3.5" \
  "torch==2.11.0" "torchvision==0.26.0" \
  "transformers==4.46.3" "tokenizers==0.20.3" "safetensors==0.8.0" \
  "accelerate==1.14.0" "huggingface_hub==0.36.2" "hf-xet==1.6.0" \
  "pillow==12.1.0" "einops" \
  addict matplotlib requests   # modeling_deepseekocr.py (uzak kod) bunlari import ediyor

echo "== 2/3 numpy hala 2.3.5 mi (KAPI 1 sigortasi) =="
"$P" -c "
import numpy, sys
print('  numpy', numpy.__version__)
if numpy.__version__ != '2.3.5':
    print('  !! numpy YUKSELTILDI — KAPI 1 yeniden kosulmali ve sapma olcuulmeli',
          file=sys.stderr)
"

echo "== 3/3 agirlik: deepseek-ai/DeepSeek-OCR -> model/deepseek-ocr =="
if [ -f "$N/model/deepseek-ocr/config.json" ]; then
  echo "  [atla] zaten var"
else
  NASH_KULE="$N" "$P" - <<'PY'
import os
from huggingface_hub import snapshot_download
from pathlib import Path
hedef = Path(os.environ["NASH_KULE"]) / "model" / "deepseek-ocr"
print("BITTI:", snapshot_download("deepseek-ai/DeepSeek-OCR",
                                  local_dir=hedef, max_workers=8))
PY
fi

echo
du -sh "$N"/model/* 2>/dev/null || true
echo
echo "SIMDI: venv/bin/python olcum/kapi1.py   (numpy degistiyse ZORUNLU)"
