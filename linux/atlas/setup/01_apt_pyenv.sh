#!/usr/bin/env bash
# ATLAS Faz B: apt sistem paketleri + pyenv Python 3.10.11 + node20/pnpm.
# MITAS Faz B şablonu (linux/12_WSL_F_SIFIRDAN_KURULUM.md) uyarlaması.
# Tesseract GEREKMEZ (ATLAS kullanmıyor - MITAS'tan fark, bkz 00_ATLAS_TASIMA_PLANI.md §4.2).
set -euo pipefail

echo "=== 1) apt update + paketler ==="
apt-get update -y
apt-get install -y \
    ffmpeg build-essential git curl ca-certificates sqlite3 \
    libgl1 libglib2.0-0 \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
    libffi-dev liblzma-dev \
    zstd unzip

echo "=== 2) Node 20 LTS + pnpm ==="
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v 2>/dev/null)" != v20* ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
npm uninstall -g pnpm >/dev/null 2>&1 || true
npm install -g pnpm@9   # pnpm>=11 gerektirir Node>=22 (node:sqlite) - Node 20 LTS ile pnpm 9 uyumlu

echo "=== 3) pyenv + Python 3.10.11 ==="
if [ ! -d /root/.pyenv ]; then
  curl -fsSL https://pyenv.run | bash
fi
export PYENV_ROOT="/root/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(/root/.pyenv/bin/pyenv init -)"
/root/.pyenv/bin/pyenv install -s 3.10.11

echo "=== KAPI B doğrulama ==="
/root/.pyenv/versions/3.10.11/bin/python --version
ffmpeg -version | head -1
node -v
pnpm -v
echo "APT_PYENV_DONE_OK"
