#!/usr/bin/env bash
# Iverson kulesinin çalışma zamanını kurar (kobe venv_kur.sh kalıbı).
#
# Temel: 3.10.20 — venvs/asr ile AYNI (freeze o sürümden alındı).
# torch/torchaudio/torchvision +cu130 sürümleri PyPI'da yok → cu130 index'i ek.
#
# Kullanım:  ./venv_kur.sh          (varsa dokunmaz)
#            ./venv_kur.sh --temiz  (sıfırdan kurar)
set -euo pipefail

K="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMEL="/home/cagatay/.pyenv/versions/3.10.20/bin/python3.10"
IDX="https://download.pytorch.org/whl/cu130"

[ "${1:-}" = "--temiz" ] && rm -rf "$K/venv"

if [ ! -x "$K/venv/bin/python" ]; then
  echo "[1/3] venv olusturuluyor ($("$TEMEL" -V))"
  "$TEMEL" -m venv "$K/venv"
fi
P="$K/venv/bin/python"

echo "[2/3] pip guncelleniyor"
"$P" -m pip install --upgrade pip -q

echo "[3/3] bagimliliklar (258 pin — venvs/asr birebir freeze)"
# --no-deps bilinçli: venvs/asr el-le-yonetilen bir ortamdir (deepfilternet
# numpy<2.0 isterken ortamda 2.2.6 yasiyor — pip cozumleyicisi bu gecmisi
# yeniden kuramaz). TAM pip freeze zaten TAM gecisli kapali kume icerir;
# --no-deps ile birebir ayni surum seti kurulur.
"$P" -m pip install --no-deps -r "$K/gereksinimler.txt" --extra-index-url "$IDX"

echo
echo "=== DOGRULAMA ==="
"$P" - <<'PY'
import faster_whisper, torch, ctranslate2, soundfile
print("faster_whisper", faster_whisper.__version__)
print("torch         ", torch.__version__, "| cuda:", torch.cuda.is_available())
print("ctranslate2   ", ctranslate2.__version__)
print("soundfile     ", soundfile.__version__)
PY
echo "--- model varlik kontrolu:"
[ -f "$K/model/faster-whisper/large-v3-turbo/model.bin" ] && echo "model large-v3-turbo: OK" || echo "model large-v3-turbo: EKSIK"
[ -f "$K/model/faster-whisper/large-v3/model.bin" ] && echo "model large-v3: OK" || echo "model large-v3: EKSIK"
