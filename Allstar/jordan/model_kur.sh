#!/usr/bin/env bash
# Jordan'in model agirliklarini kule ICINE kurar (~33 GB, git'te degil).
#
# Neden kule icinde: Kobe'nin surum-dondurma dersi. Ortak bir hf_cache'te
# baskasi modeli guncellerse Jordan'in ciktisi SESSIZCE kayar. Allstar/MAP.md
# "model agirliklari zemindedir" der; o kural PAYLASILAN kaynak icindir —
# bu iki checkpoint'i baska kule kullanmiyor, catallanacak bir sey yok.
#
# Kullanim:  ./model_kur.sh          (ikisini de)
#            ./model_kur.sh w8a8     (yalniz INT8)
#            ./model_kur.sh bf16     (yalniz orijinal)
set -euo pipefail

J="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
P="$J/venv/bin/python"
[ -x "$P" ] || { echo "once ./venv_kur.sh"; exit 1; }

indir() {  # $1=hf_repo  $2=hedef_alt_dizin
  if [ -f "$J/model/$2/config.json" ]; then
    echo "[atla] model/$2 zaten var"
    return
  fi
  echo "[indir] $1 -> model/$2"
  "$P" - "$1" "$J/model/$2" <<'PY'
import sys
from huggingface_hub import snapshot_download
print("BITTI:", snapshot_download(sys.argv[1], local_dir=sys.argv[2], max_workers=8))
PY
}

case "${1:-hepsi}" in
  w8a8)  indir RedHatAI/Qwen3.5-9B-quantized.w8a8 w8a8 ;;
  bf16)  indir Qwen/Qwen3.5-9B                    bf16 ;;
  hepsi)
    # INT8 — VARSAYILAN. RTX 3090 = Ampere sm_86; FP8 cekirdegi sm_89+ ister,
    # bu yuzden 8-bit surum FP8 degil INT8'dir. Gorüntü kulesi (model.visual.*)
    # bu checkpoint'te kuantize EDILMEMIS — pikseli okuyan kisim bf16 kalir.
    indir RedHatAI/Qwen3.5-9B-quantized.w8a8 w8a8
    # bf16 — kiyasin kontrol kolu. INT8'in ne kaybettirdigi OLCULMEDEN silinmez.
    indir Qwen/Qwen3.5-9B                    bf16 ;;
  *) echo "kullanim: $0 [w8a8|bf16|hepsi]"; exit 2 ;;
esac

echo
du -sh "$J"/model/* 2>/dev/null || true
