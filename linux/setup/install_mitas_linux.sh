#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# MITAS Linux — kurulum-sonrası otomatik hazırlık (Ubuntu 24.04, bare-metal F diski)
#
# Ubuntu kurulduktan + GPU sürücüsü geldikten SONRA çalıştırılır. Adım adım,
# her aşama idempotent (yeniden çalıştırılabilir) ve DURAKLAR ile — kör basmaz.
#
# Kullanım:
#   1) Kod + linux/reqs/*.txt + linux/mitas.env bu makinede olmalı (git clone / kopya).
#   2) Aşağıdaki DEĞİŞKENLERİ kontrol et.
#   3) bash install_mitas_linux.sh   (adım adım sorar)
#
# NOT: Bu script F-diski wipe'ından bağımsızdır — E:\MITAS\linux\ (git) altında durur,
#      bare-metal Linux'a taşınır. Faz 0 (WSL) yerine doğrudan bare-metal için de kullanılır.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── DEĞİŞKENLER (kontrol et) ──────────────────────────────────────────────────
MITAS_ROOT="${MITAS_ROOT:-/opt/mitas}"          # kod + venv buraya
DATA_ROOT="${DATA_ROOT:-/data/mitas}"           # DuckDB/model/veri buraya
PY_VERSION="${PY_VERSION:-3.10.11}"
SRC="${SRC:-}"                                   # kod kaynağı: git URL veya kopya-yol (BOŞSA sorar)
REQS_DIR="${REQS_DIR:-$MITAS_ROOT/linux/reqs}"  # dondurulmuş venv reçeteleri
TORCH_CUDA_INDEX="https://download.pytorch.org/whl/cu124"

# Kurulum önceliği: önce bu üçü (golden çekirdeği), sonra gerisi.
VENV_PRIORITY=(core ocr asr)
VENV_REST=(alignment audio denoise face ina internvl locateanything minicpmv nemo stt tag translate tts visual vlm)
# GPU (torch/CUDA) gereken profiller — torch CUDA-index'ten kurulur:
GPU_VENVS=(asr ocr vlm nemo face visual internvl minicpmv locateanything ina tts)
# Linux'ta ATLANACAK paketler (Windows-özgü):
STRIP='^(oneocr|pywin32|pypiwin32|win32|windows-curses|torch|torchvision|torchaudio)'

pause() { read -rp "  ↳ [ENTER] devam, [Ctrl-C] dur: " _; }
say()   { echo -e "\n=== $* ==="; }

# ── Adım 1: sistem paketleri ──────────────────────────────────────────────────
say "1) Sistem paketleri (apt)"
echo "  ffmpeg, tesseract, mscorefonts, ntfs-3g, build tools, git, curl"
pause
sudo apt update
sudo apt install -y ffmpeg tesseract-ocr tesseract-ocr-tur \
    build-essential git curl ca-certificates \
    ttf-mscorefonts-installer fonts-liberation ntfs-3g \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
    libffi-dev liblzma-dev

# ── Adım 2: pyenv + Python 3.10.11 ────────────────────────────────────────────
say "2) pyenv + Python $PY_VERSION"
if ! command -v pyenv >/dev/null 2>&1; then
  curl -fsSL https://pyenv.run | bash
  export PYENV_ROOT="$HOME/.pyenv"; export PATH="$PYENV_ROOT/bin:$PATH"
  eval "$(pyenv init -)"
fi
pyenv install -s "$PY_VERSION"
echo "  Python $PY_VERSION hazır."

# ── Adım 3: dizinler + kod ────────────────────────────────────────────────────
say "3) Dizinler + kod"
sudo mkdir -p "$MITAS_ROOT" "$DATA_ROOT"/{MitaData,IMDB/db,models/hf_cache,models/ollama,seriler}
sudo chown -R "$USER":"$USER" "$MITAS_ROOT" "$DATA_ROOT"
if [ ! -d "$MITAS_ROOT/.git" ] && [ ! -f "$MITAS_ROOT/scripts/mitas_pipeline.py" ]; then
  if [ -z "$SRC" ]; then echo "  ! SRC boş — kodu $MITAS_ROOT'a elle al (git clone / kopya), sonra tekrar çalıştır."; exit 1; fi
  if [[ "$SRC" == *.git || "$SRC" == http* ]]; then git clone "$SRC" "$MITAS_ROOT";
  else cp -a "$SRC"/. "$MITAS_ROOT"/; fi
fi
mkdir -p "$MITAS_ROOT/cache/"{staging,web,duckdb}
cd "$MITAS_ROOT"
cat >/dev/null <<'NOTE'
HF cache ve ollama modelleri veri diskinde (kökü doldurmamak için):
  ln -sfn "$DATA_ROOT/models/hf_cache" ~/.cache/huggingface
NOTE
mkdir -p ~/.cache && ln -sfn "$DATA_ROOT/models/hf_cache" ~/.cache/huggingface

# ── Adım 4: mitas.env ─────────────────────────────────────────────────────────
say "4) mitas.env yerleştir"
if [ -f "$MITAS_ROOT/linux/mitas.env" ]; then
  cp -n "$MITAS_ROOT/linux/mitas.env" "$MITAS_ROOT/mitas.env"
  chmod 600 "$MITAS_ROOT/mitas.env"
  echo "  $MITAS_ROOT/mitas.env kopyalandı. ⚠ SIRLARI (API anahtarları) doldur!"
  echo "  Düzenle: nano $MITAS_ROOT/mitas.env"
  pause
fi

# ── Adım 5: venv'ler ──────────────────────────────────────────────────────────
mk_venv() {
  local p="$1" req="$REQS_DIR/$1.txt"
  [ -f "$req" ] || { echo "  ! $req yok, atlanıyor"; return; }
  echo "  → venv: $p"
  pyenv exec python -m venv "$MITAS_ROOT/venvs/$p"
  local py="$MITAS_ROOT/venvs/$p/bin/python"
  "$py" -m pip -q install --upgrade pip
  # GPU profili ise torch'u reçete-sürümüyle CUDA-index'ten:
  if printf '%s\n' "${GPU_VENVS[@]}" | grep -qx "$p"; then
    local tver; tver=$(grep -iE '^torch==' "$req" | head -1 | cut -d= -f3)
    if [ -n "$tver" ]; then "$py" -m pip install "torch==$tver" --index-url "$TORCH_CUDA_INDEX" || \
      "$py" -m pip install torch --index-url "$TORCH_CUDA_INDEX"; fi
  fi
  # kalan paketler (Windows-özgü + torch satırları çıkarılarak):
  grep -viE "$STRIP" "$req" > "/tmp/${p}_lin.txt" || true
  "$py" -m pip install -r "/tmp/${p}_lin.txt" || echo "  ! $p: bazı paketler kurulamadı — logda incele"
}

say "5a) ÖNCELİK venv'leri: ${VENV_PRIORITY[*]} (golden çekirdeği)"
pause
for p in "${VENV_PRIORITY[@]}"; do mk_venv "$p"; done

say "5b) Kalan venv'ler: ${VENV_REST[*]}  (uzun sürer, GB'larca indirir)"
echo "  Şimdi kurmak istemiyorsan Ctrl-C — çekirdek üçlü zaten kuruldu."
pause
for p in "${VENV_REST[@]}"; do mk_venv "$p"; done

# ── Adım 6: duman testi ───────────────────────────────────────────────────────
say "6) Duman testi (çekirdek)"
set +e
"$MITAS_ROOT/venvs/asr/bin/python" -c "import torch; print('torch.cuda:', torch.cuda.is_available())"
"$MITAS_ROOT/venvs/ocr/bin/python" -c "import paddle; print('paddle ok')" 2>/dev/null
set -e
echo "  cuda True olmalı. Değilse: nvidia sürücü + CUDA wheel kontrol (bkz. 06)."

say "BİTTİ (temel). Sırada: modeller (ollama pull), systemd (07), golden (09)."
echo "  Modeller:  ollama pull <üretim-etiketi>   (mitas_pipeline model adlarından liste çıkar)"
echo "  systemd:   linux/07_SERVISLER_SYSTEMD.md birimlerini /etc/systemd/system'e kur"
echo "  Golden:    linux/reqs referans + scripts/regresyon_golden.py (KAPI 2)"
