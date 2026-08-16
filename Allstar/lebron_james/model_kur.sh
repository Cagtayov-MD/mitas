#!/usr/bin/env bash
# Lebron'un OKUMA yiginini ve model agirligini kule ICINE kurar
# (~3 GB torch + ~6.3 GB agirlik). Git'te degil (Allstar/.gitignore: */model/).
#
# NEDEN KULE ICINDE (Cagatay, 2026-08-15): "icine deepseek kur, kule icinde
# yasasin." Uretimdeki okuyucu (_pipe_hibrit_okuma.kol_master) Ollama'ya HTTP
# atiyor — disaridaki bir servise bagli kule kendi kendine yeten bir kule
# degildir. Ayrica olculmus yan etkisi var: Ollama acikken Kobe skoru
# %94.5 -> %93.6 dusuyor. Nash ayni gecisi yapti; bu betik onun izinde.
#
# OKUMA MANTIGI DEGISMIYOR, YALNIZ TASIYICI DEGISIYOR:
#   ayni model (DeepSeek-OCR) · ayni istem ("Free OCR.") · ayni bant geometrisi
#   (1100 px / 120 bindirme). Ollama'da llama.cpp handler'i "<image>" on-ekini
#   kendi ekliyordu; transformers'ta ACIKCA verilir (bkz. src/model.py).
#
# SURUMLER: Nash'in venv'inde GERCEKTEN calisan pinler alindi (model_kur.sh'inde
# yazan 5.14.1 DEGIL — orada cozumleyici 4.46.3'e dusmus). DeepSeek-OCR'in uzak
# kodu transformers 5.x ile calismiyor.
#
# !! KURULUMDAN SONRA ZORUNLU: olcum/kapi_sadakat.py YENIDEN kosulur.
#    Gerekce Kobe'nin pahali dersi: kulenin CIKTISI, kodunun hic import
#    etmedigi paketlere bagli olabiliyor. torch/transformers ayni venv'e
#    girince Paddle'in davranisi kayabilir. Sapma 0 GORULMEDEN bu kurulum
#    "tamam" sayilmaz.
#
# Kullanim: ./model_kur.sh
set -euo pipefail

L="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
P="$L/venv/bin/python"
[ -x "$P" ] || { echo "once ./venv_kur.sh"; exit 1; }

NASH_MODEL="$L/../nash/model/deepseek-ocr"

echo "== 1/4 numpy suruimu (kurulum ONCESI) =="
"$P" -c "import numpy; print('  numpy', numpy.__version__)"

echo "== 2/4 okuma yigini =="
"$L/venv/bin/pip" install --quiet \
  "numpy==2.3.5" \
  "torch==2.11.0" "torchvision==0.26.0" \
  "transformers==4.46.3" "tokenizers==0.20.3" "safetensors==0.8.0" \
  "accelerate==1.14.0" "einops==0.8.2" \
  "addict==2.4.0" "easydict==1.13" \
  matplotlib requests   # modeling_deepseekocr.py (uzak kod) bunlari import ediyor

echo "== 3/4 numpy hala 2.3.5 mi (sadakat kapisi sigortasi) =="
"$P" -c "
import numpy, sys
print('  numpy', numpy.__version__)
if numpy.__version__ != '2.3.5':
    print('  !! numpy DEGISTI — sadakat kapisi YENIDEN kosulmali', file=sys.stderr)
"

echo "== 4/4 agirlik: DeepSeek-OCR -> model/deepseek-ocr =="
if [ -f "$L/model/deepseek-ocr/config.json" ]; then
  echo "  [atla] zaten var"
elif [ -f "$NASH_MODEL/config.json" ]; then
  # Nash'in yanindaki kopyadan al: ayni agirlik, 6.3 GB indirme yok.
  # Bu bir CALISMA ZAMANI baglantisi DEGIL, tek seferlik kurulum kopyasi —
  # kopyalandiktan sonra Lebron Nash'i hic tanimaz.
  echo "  Nash'in kopyasindan aliniyor (indirme yok)"
  mkdir -p "$L/model"
  cp -r "$NASH_MODEL" "$L/model/deepseek-ocr"
else
  echo "  Hugging Face'ten indiriliyor"
  cd "$L" && "$P" - <<'PY'
from huggingface_hub import snapshot_download
print("BITTI:", snapshot_download("deepseek-ai/DeepSeek-OCR",
                                  local_dir="model/deepseek-ocr", max_workers=8))
PY
fi

echo "== 5/5 nvrtc kopruisu (CUDA nesil carpismasi) =="
# Paddle cu12, torch cu13 — ayni venv'de. torch'un JIT'i
# libnvrtc-builtins.so.13.0'i duz adla ariyor ve cu12 dizinindeki 12.6
# surumunu bulup patliyor ("failed to open libnvrtc-builtins.so.13.0").
# YALNIZ o tek dosyayi ayri bir dizinde gorunur kiliyoruz; cu13/lib'i komple
# yola eklemek Paddle'in cu12 kutuphanelerini golgelerdi (ayni soname'ler var).
CU13="$L/venv/lib/python3.12/site-packages/nvidia/cu13/lib/libnvrtc-builtins.so.13.0"
if [ -f "$CU13" ]; then
  mkdir -p "$L/venv/nvrtc13"
  ln -sf "$CU13" "$L/venv/nvrtc13/libnvrtc-builtins.so.13.0"
  echo "  kuruldu: venv/nvrtc13/"
else
  echo "  [atla] cu13 nvrtc bulunamadi — torch surumu degismis olabilir"
fi

echo
echo "=== DOGRULAMA ==="
"$P" - <<'PY'
import torch, transformers, tokenizers, numpy, paddle
print("torch       ", torch.__version__, "| cuda:", torch.cuda.is_available())
print("transformers", transformers.__version__)
print("tokenizers  ", tokenizers.__version__)
print("numpy       ", numpy.__version__)
print("paddle      ", paddle.__version__, "| cuda:", paddle.is_compiled_with_cuda())
PY
du -sh "$L"/model/* 2>/dev/null || true
echo
echo "SIMDI ZORUNLU:  cd olcum && ../venv/bin/python kapi_sadakat.py --n 8"
echo "                (sapma 0 gormeden bu kurulum TAMAM sayilmaz)"
