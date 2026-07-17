#!/usr/bin/env bash
# ATLAS Faz C: kod tohumu (tek seferlik).
# ONEMLI SAPMA (00_ATLAS_TASIMA_PLANI.md "git archive HEAD" onerisinden): E:\ATLAS calisma
# agacinda 244 tracked dosyada commit'lenmemis degisiklik var (config/app.yaml, config/taksonomi.yaml,
# src/atlas/*.py, scripts/*.py, webui/* dahil - GERCEK kod/konfig farklari). "git archive HEAD" bu
# degisiklikleri SESSIZCE atlardi (davranis-notr gocu BOZAR). Onun yerine: git ls-files (tracked
# path listesi, ayni disari-birakma kumesini verir) + calisma-agacindaki GUNCEL icerigi kopyala.
# Sonuc ayni disklama (gitignore) ama commit'lenmemis GERCEK degisiklikler DAHIL. Salt-okuma E:'den.
set -euo pipefail
SRC=/mnt/e/ATLAS
DST=/opt/atlas
mkdir -p "$DST"

echo "=== 1) tracked dosyalar (calisma-agaci icerigi, commit'lenmemis DAHIL) -> $DST ==="
cd "$SRC"
NFILES=$(git ls-files | wc -l)
git ls-files -z | tar --null -T - -cf - | tar -xf - -C "$DST"
echo "  kopyalanan tracked dosya sayisi: $NFILES"

echo "=== 2) ekstra calisma-bagimliligi (gitignore'da ama GEREKLI) ==="
mkdir -p "$DST/tools"
cp -a "$SRC/tools/audfprint" "$DST/tools/audfprint"
cp -a "$SRC/atlas.db" "$DST/atlas.db"

echo "=== 3) .gitseed (opsiyonel - tam git tarihi, sadece okuma E:\\ATLAS_git'ten) ==="
git clone --bare /mnt/e/ATLAS_git/atlas.git "$DST/.gitseed" >/tmp/gitseed.log 2>&1 && echo "  gitseed OK" || { echo "  gitseed HATA:"; tail -10 /tmp/gitseed.log; }

echo "=== 4) gerekli bos dizinler ==="
mkdir -p "$DST/data" "$DST/models/ollama" "$DST/hf-cache" "$DST/outputs" "$DST/logs" "$DST/cache"

echo "=== dogrulama ==="
du -sh "$DST" 2>&1
find "$DST" -maxdepth 1 | sort
echo "CODE_SEED_DONE_OK"
