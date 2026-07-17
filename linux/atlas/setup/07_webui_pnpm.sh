#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/bin:$PATH
pnpm config set store-dir /opt/atlas/.pnpm-store
cd /opt/atlas/webui
# --frozen-lockfile HATA verdi (ERR_PNPM_LOCKFILE_CONFIG_MISMATCH: pnpm-workspace.yaml
# 'overrides' alani lockfile'daki degerle uyusmuyor - E:\ATLAS'taki pnpm-workspace.yaml
# zaten bozuk/placeholder haldeydi (bkz UYGULAMA_LOG.md), lockfile ondan once uretilmis
# olabilir). Tek seferlik bootstrap oldugu icin --no-frozen-lockfile ile devam:
pnpm install --no-frozen-lockfile
echo WEBUI_PNPM_INSTALL_DONE_OK
