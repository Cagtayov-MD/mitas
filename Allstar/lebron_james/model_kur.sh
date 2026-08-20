#!/usr/bin/env bash
# LeBron'un ölçülmüş hızlı DeepSeek-OCR GGUF/Ollama yığınını kule içine alır.
# Ağ/Hugging Face kullanılmaz; mevcut HF ağırlığı geri dönüş için korunur.
set -euo pipefail

L="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_STORE=/opt/mitas/models/ollama
SRC_BIN=/usr/local/bin/ollama
SRC_LIB=/usr/local/lib/ollama
DEST_RUNTIME="$L/model/ollama-runtime"
DEST_STORE="$L/model/ollama"
MANIFEST_REL=manifests/registry.ollama.ai/library/deepseek-ocr/latest

EXPECTED_BIN=e010ce570cfa04334b30867c228a45781857b2ff5071630f3f59ef7cc2513d1f
EXPECTED_MANIFEST=0e7b018b8a22373167ee79c9a852821235488cbd2a2a5a93495558627423278c
BLOBS=(
  c8efaf6dac5aab4dc1030895032f0f028d7835348bdb21d4aebb89cda5788fe5
  3a18673ff291a1d8de94d490877127899356d33a18028d5f3945bf245c11b02c
  a406579cd136771c705c521db86ca7d60a6f3de7c9b5460e6193a2df27861bde
  ae40a217c1c4002e9358f0f6597a349acaace0cfb95dc53db7ce646d57a56271
)

[ -x "$SRC_BIN" ] || { echo "kaynak Ollama yok: $SRC_BIN" >&2; exit 2; }
[ -d "$SRC_LIB" ] || { echo "kaynak Ollama kutuphanesi yok: $SRC_LIB" >&2; exit 2; }
[ -x /usr/bin/bwrap ] || {
  echo "bubblewrap yok: özel Ollama HOME izolasyonu kurulamaz" >&2; exit 2;
}
[ -f "$SRC_STORE/$MANIFEST_REL" ] || {
  echo "kaynak deepseek-ocr manifesti yok: $SRC_STORE/$MANIFEST_REL" >&2; exit 2;
}

echo "== kaynak kilidi =="
printf '%s  %s\n' "$EXPECTED_BIN" "$SRC_BIN" | sha256sum --check --status || {
  echo "Ollama binary beklenen 0.32.0 kilidiyle uyusmuyor" >&2; exit 2;
}
printf '%s  %s\n' "$EXPECTED_MANIFEST" "$SRC_STORE/$MANIFEST_REL" \
  | sha256sum --check --status || {
  echo "DeepSeek-OCR manifest kilidi uyusmuyor" >&2; exit 2;
}
for digest in "${BLOBS[@]}"; do
  source_blob="$SRC_STORE/blobs/sha256-$digest"
  [ -f "$source_blob" ] || { echo "kaynak blob yok: $source_blob" >&2; exit 2; }
  printf '%s  %s\n' "$digest" "$source_blob" | sha256sum --check --status || {
    echo "kaynak blob kilidi uyusmuyor: $digest" >&2; exit 2;
  }
done

mkdir -p "$L/model"
if [ ! -x "$DEST_RUNTIME/bin/ollama" ]; then
  echo "== kule-owned Ollama runtime (yerel kopya) =="
  tmp_runtime="$(mktemp -d "$L/model/.ollama-runtime.XXXXXX")"
  trap 'rm -rf -- "$tmp_runtime"' EXIT
  mkdir -p "$tmp_runtime/bin" "$tmp_runtime/lib"
  cp -a -- "$SRC_BIN" "$tmp_runtime/bin/ollama"
  cp -a -- "$SRC_LIB" "$tmp_runtime/lib/ollama"
  mv -- "$tmp_runtime" "$DEST_RUNTIME"
  trap - EXIT
else
  echo "[atla] yerel Ollama runtime zaten var"
fi

if [ ! -f "$DEST_STORE/$MANIFEST_REL" ]; then
  echo "== kule-owned DeepSeek-OCR store (yalniz kilitli 4 blob) =="
  tmp_store="$(mktemp -d "$L/model/.ollama-store.XXXXXX")"
  trap 'rm -rf -- "$tmp_store"' EXIT
  mkdir -p "$tmp_store/blobs" "$(dirname "$tmp_store/$MANIFEST_REL")"
  cp -a -- "$SRC_STORE/$MANIFEST_REL" "$tmp_store/$MANIFEST_REL"
  for digest in "${BLOBS[@]}"; do
    cp -a -- "$SRC_STORE/blobs/sha256-$digest" "$tmp_store/blobs/sha256-$digest"
  done
  mv -- "$tmp_store" "$DEST_STORE"
  trap - EXIT
else
  echo "[atla] yerel DeepSeek-OCR store zaten var"
fi

echo "== çalışma-zamanı doğrulaması =="
LEBRON_KULE="$L" PYTHONPATH="$L/src" "$L/venv/bin/python" - <<'PY'
import os
from pathlib import Path
from model import _verify_install

root = Path(os.environ["LEBRON_KULE"])
binary, library, store, model = _verify_install(root, {})
print("runtime:", binary)
print("library:", library)
print("store:", store)
print("model:", model)
PY

du -sh "$DEST_RUNTIME" "$DEST_STORE" "$L/model/deepseek-ocr" 2>/dev/null || true
echo "BITTI: ag kullanilmadi; mevcut HF kopyasi silinmedi."
