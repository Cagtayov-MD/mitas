#!/bin/bash
# Sistem CUDA toolkit — NVIDIA resmi ubuntu2604 deposu (vLLM/flashinfer JIT + gelecek ekosistem için)
# SADECE toolkit — sürücüye DOKUNMAZ (cuda metapaketi değil!)
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/08_cuda_toolkit.log
exec > >(tee "$LOG") 2>&1
cd /tmp
echo "=== keyring $(date) ==="
curl -fsSLO https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2604/x86_64/cuda-keyring_1.1-1_all.deb
sudo -n dpkg -i cuda-keyring_1.1-1_all.deb
sudo -n apt-get update -qq
echo "=== mevcut toolkit sürümleri ==="
apt-cache search --names-only '^cuda-toolkit-13' | sort
# Sürücü 595.71 = CUDA 13.2 → önce 13-2 (birebir), yoksa 13-3 (minor-uyumlu)
if apt-cache show cuda-toolkit-13-2 >/dev/null 2>&1; then TK=cuda-toolkit-13-2; else TK=cuda-toolkit-13-3; fi
echo "SECILEN=$TK"
sudo -n apt-get install -y "$TK"
ls -l /usr/local/ | grep cuda
/usr/local/cuda/bin/nvcc --version | tail -1
echo "CUDA-TOOLKIT-TAMAM $(date)"
