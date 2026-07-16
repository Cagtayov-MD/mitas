#!/bin/bash
# vLLM — en güncel sürüm, kendi venv'i (py3.12). Bare-metal'de UVA duvarı YOK → çalışmalı.
set -uo pipefail
LOG=/opt/mitas/kurulum/logs/07_vllm.log
exec > >(tee "$LOG") 2>&1
export PYENV_ROOT="$HOME/.pyenv"
P312=$(ls "$PYENV_ROOT/versions/" | grep -E '^3\.12\.' | sort -V | tail -1)
V=/opt/mitas/venvs/vllm

echo "=== vLLM venv (python $P312, en güncel vllm) $(date) ==="
if [ ! -x "$V/bin/python" ]; then
  "$PYENV_ROOT/versions/$P312/bin/python" -m venv "$V"
fi
"$V/bin/pip" install -q -U pip wheel
"$V/bin/pip" install -U vllm || { echo "VLLM-KURULUM-HATA"; exit 1; }
"$V/bin/python" -c "import vllm, torch; print('vllm', vllm.__version__, '| torch', torch.__version__, '| cuda-ok', torch.cuda.is_available())" || exit 2
cp /opt/mitas/kurulum/vllm_test.py /opt/mitas/kurulum/.vllm_test_hazir 2>/dev/null || true
echo "VLLM-KURULUM-TAMAM $(date)"
