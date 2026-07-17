#!/usr/bin/env bash
V=/opt/atlas/venvs/asr/bin
echo "=== torch/torchaudio/torchvision surumleri ==="
"$V/pip" show torch torchaudio torchvision 2>&1 | grep -E "^Name|^Version"
echo "=== ldd .so (eksik kutuphane var mi) ==="
ldd /opt/atlas/venvs/asr/lib/python3.10/site-packages/torchaudio/lib/_torchaudio.abi3.so 2>&1 | grep -i "not found"
echo "=== torch import (sadece) ==="
"$V/python" -c "import torch; print('torch OK', torch.__version__, 'cuda=', torch.cuda.is_available())" 2>&1 | tail -5
echo "=== torchaudio import (izole) ==="
"$V/python" -c "import torchaudio" 2>&1 | tail -20
