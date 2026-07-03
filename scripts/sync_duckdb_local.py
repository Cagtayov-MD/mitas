# -*- coding: utf-8 -*-
"""sync_duckdb_local.py — KB duckdb'lerini SMB (X:/Y:) → yerel (E:\\MITAS\\cache\\duckdb) kopyala.

AMAÇ (hızlandırma planı Faz-1.1, 2026-07-04): credit_crosscheck KB-doğrulama sorguları ağ
(SMB) üzerindeki 30GB duckdb'lere her film-başı round-trip yapıyor (~20-60 sn/film). Yerel
kopya bu gecikmeyi keser. BYTE-NÖTR: aynı DB, yalnız yol değişir (aynı sorgu = aynı sonuç).

Bayatlama: kaynak mtime > yerel mtime VEYA boyut farkı → yeniden kopyala. IMDb/Wikidata
statik olduğundan pratikte tek-seferlik; günlük ucuz mtime-check idempotent.

Kullanım:
  python scripts/sync_duckdb_local.py             (mtime/boyut değiştiyse kopyala)
  python scripts/sync_duckdb_local.py --force     (koşulsuz yeniden kopyala)
  python scripts/sync_duckdb_local.py --check      (yalnız durum yazdır, kopyalama yok)

Kopya sonrası KULLANICI/başlatıcı env'i şöyle set etmeli (bu script ETMEZ — güvenli ayrım):
  MITAS_WIKIDATA_DUCKDB=E:\\MITAS\\cache\\duckdb\\mitas.duckdb
  MITAS_IMDB_DUCKDB=E:\\MITAS\\cache\\duckdb\\imdb.duckdb
FAIL-SAFE: kopya yarıda kalırsa .part kalır, hedef ESKİ haliyle geçerli kalır (atomik replace).
"""
from __future__ import annotations
import argparse
import os
import shutil
import sys
import time
from pathlib import Path

SRC = {
    "mitas.duckdb": os.environ.get("MITAS_WIKIDATA_DUCKDB_SRC", r"X:\DIGER\Mitas_Files\MitaData\mitas.duckdb"),
    "imdb.duckdb": os.environ.get("MITAS_IMDB_DUCKDB_SRC", r"Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb"),
}
DST_DIR = Path(os.environ.get("MITAS_DUCKDB_CACHE", r"E:\MITAS\cache\duckdb"))


def _need_copy(src: Path, dst: Path) -> bool:
    if not dst.exists():
        return True
    try:
        ss, ds = src.stat(), dst.stat()
        return (ss.st_size != ds.st_size) or (ss.st_mtime > ds.st_mtime + 2)
    except Exception:  # noqa: BLE001
        return True


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    DST_DIR.mkdir(parents=True, exist_ok=True)
    rep = {"copied": [], "skipped": [], "errors": []}
    for name, src_str in SRC.items():
        src, dst = Path(src_str), DST_DIR / name
        if not src.exists():
            rep["errors"].append(f"{name}: kaynak yok ({src})")
            continue
        need = a.force or _need_copy(src, dst)
        if a.check:
            print(f"  {name}: kaynak {src.stat().st_size/1e9:.1f}GB | "
                  f"yerel {'YOK' if not dst.exists() else f'{dst.stat().st_size/1e9:.1f}GB'} | "
                  f"kopya-gerekli={need}")
            continue
        if not need:
            rep["skipped"].append(name)
            continue
        t0 = time.perf_counter()
        part = dst.with_suffix(dst.suffix + ".part")
        try:
            shutil.copy2(src, part)               # .part'a yaz (yarım kalırsa hedef eski kalır)
            if part.stat().st_size != src.stat().st_size:
                raise IOError(f"boyut uyuşmazlığı: {part.stat().st_size} != {src.stat().st_size}")
            os.replace(part, dst)                  # atomik değiştir
            rep["copied"].append(f"{name} ({time.perf_counter()-t0:.0f}s, {dst.stat().st_size/1e9:.1f}GB)")
        except Exception as exc:  # noqa: BLE001
            rep["errors"].append(f"{name}: {type(exc).__name__}: {exc}")
            try:
                if part.exists():
                    part.unlink()
            except Exception:  # noqa: BLE001
                pass
    import json as _js
    print(_js.dumps(rep, ensure_ascii=False))
    return 1 if rep["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
