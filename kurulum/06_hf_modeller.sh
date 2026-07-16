#!/bin/bash
# HF modelleri — ollama'dan bağımsız çalışma için (en güncel huggingface_hub CLI)
# Hedef: /opt/mitas/models/hf_cache (HF_HOME)
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/06_hf_modeller.log
exec > >(tee "$LOG") 2>&1
export PYENV_ROOT="$HOME/.pyenv"
P312=$(ls "$PYENV_ROOT/versions/" | grep -E '^3\.12\.' | sort -V | tail -1)

# araclar venv (hf CLI + küçük yardımcılar için kalıcı yardımcı venv)
V=/opt/mitas/venvs/araclar
if [ ! -x "$V/bin/python" ]; then
  "$PYENV_ROOT/versions/$P312/bin/python" -m venv "$V"
  "$V/bin/pip" install -q -U pip "huggingface_hub[cli]"
fi

set -a; source /opt/mitas/mitas.env; set +a
export HF_HOME
echo "HF_HOME=$HF_HOME"

for repo in Qwen/Qwen2.5-VL-7B-Instruct Qwen/Qwen3-8B; do
  echo "=== indiriliyor: $repo $(date +%H:%M) ==="
  "$V/bin/hf" download "$repo" 2>&1 | tail -2
  echo "SONUC[$repo]=$?"
done
echo "HF-MODELLER-BITTI $(date)"
