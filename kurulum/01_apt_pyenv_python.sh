#!/bin/bash
# MITAS Linux kurulum — Adım 1: apt paketleri + pyenv + Python derlemeleri
# Politika: her şey en güncel; tek seferlik, kalıcı, temiz.
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/01_apt_pyenv_python.log
mkdir -p /opt/mitas/kurulum/logs
exec > >(tee -a "$LOG") 2>&1

echo "=== [1/3] APT paketleri $(date) ==="
export DEBIAN_FRONTEND=noninteractive
sudo -n apt-get update -y
sudo -n apt-get install -y \
  build-essential cmake ninja-build pkg-config \
  curl wget git zstd unzip p7zip-full jq sqlite3 \
  ffmpeg mediainfo sox \
  libgl1 libglib2.0-0 \
  libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
  libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
  libffi-dev liblzma-dev \
  htop tmux
echo "APT-SONUC=$?"

echo "=== [2/3] pyenv (en guncel) $(date) ==="
if [ ! -d "$HOME/.pyenv" ]; then
  curl -fsSL https://pyenv.run | bash
fi
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$("$PYENV_ROOT/bin/pyenv" init -)" 2>/dev/null || true
"$PYENV_ROOT/bin/pyenv" --version
echo "PYENV-SONUC=$?"

echo "=== [3/3] Python derlemeleri $(date) ==="
# En guncel kararli minor'lar: 3.12 (ana), 3.11 (fallback). 64 cekirdek paralel derleme.
export MAKE_OPTS="-j32" PYTHON_CFLAGS="-O2"
P312=$("$PYENV_ROOT/bin/pyenv" install --list | grep -E '^\s*3\.12\.[0-9]+$' | tail -1 | tr -d ' ')
P311=$("$PYENV_ROOT/bin/pyenv" install --list | grep -E '^\s*3\.11\.[0-9]+$' | tail -1 | tr -d ' ')
echo "Secilen surumler: $P312 (ana), $P311 (fallback)"
"$PYENV_ROOT/bin/pyenv" install -s "$P312" && echo "P312-OK=$P312"
"$PYENV_ROOT/bin/pyenv" install -s "$P311" && echo "P311-OK=$P311"
"$PYENV_ROOT/versions/$P312/bin/python" --version && "$PYENV_ROOT/versions/$P311/bin/python" --version
echo "=== ADIM-1-TAMAM $(date) ==="
