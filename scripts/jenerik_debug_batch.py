# -*- coding: utf-8 -*-
"""jenerik_debug_batch.py — jdebug (jenerik provenance) TOPLU BACKFILL.

AMAÇ (hızlandırma planı Faz-2, 2026-07-04): koşu sırasında MITAS_JENERIK_PARALLEL_DEBUG=0
ile jdebug kapatılırsa provenance artefaktları (Database/<film>/jenerik_debug/) eksik kalır.
Bu araç eksik filmleri tarar ve _jenerik_parallel_debug.py'yi film-başına ÇEVRİMDIŞI koşar
(aynı-gün batch-backfill). Üretim kararına HİÇ dokunmaz — jdebug zaten karar-dışı gözlemdir.

Kullanım:
  python scripts/jenerik_debug_batch.py --dry-run          (eksikleri listele, koşma)
  python scripts/jenerik_debug_batch.py                    (eksikleri sırayla doldur)
  python scripts/jenerik_debug_batch.py --limit 5          (ilk 5 eksik)
  python scripts/jenerik_debug_batch.py --only "SINIR"     (ad-altdizgisiyle filtre)
  python scripts/jenerik_debug_batch.py --skip-vl          (GLM/VL GPU-adımlarını atla)

NOT: VL/GLM adımları ollama GPU kullanır — backfill'i pipeline BOŞTAYKEN koş (gece/batch-arası).
FAIL-SAFE: film-başına try/except; tek hata batch'i durdurmaz; özet JSON stdout'a.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(r"E:\MITAS")
DB = ROOT / "Database"
JDBG = ROOT / "scripts" / "_jenerik_parallel_debug.py"


def needs_backfill(clip: Path) -> bool:
    """jenerik_debug yok VEYA karşılaştırma raporu eksik → backfill gerekli.
    Yalnız çıkış-jenerik havuzu OLAN filmler aday (jdebug'ın girdisi frames/cikis_jenerik)."""
    if not (clip / "frames" / "cikis_jenerik").is_dir():
        return False
    jd = clip / "jenerik_debug"
    if not jd.is_dir():
        return True
    return not any(jd.glob("*comparison*")) and not any(jd.glob("*report*"))


def latest_ocr_out(clip: Path) -> str:
    jobs = sorted((p for p in (clip / "ocr").glob("ocr-*") if p.is_dir()
                   and not p.name.endswith("-fb")), key=lambda p: p.stat().st_mtime)
    return str(jobs[-1]) if jobs else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--skip-vl", action="store_true", help="GLM+VL GPU adımlarını atla")
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args()

    cands = []
    for clip in sorted(DB.iterdir()):
        if not clip.is_dir():
            continue
        if a.only and a.only.lower() not in clip.name.lower():
            continue
        if needs_backfill(clip):
            cands.append(clip)
    if a.limit > 0:
        cands = cands[: a.limit]

    print(f"eksik-jdebug film: {len(cands)}")
    if a.dry_run:
        for c in cands:
            print(f"  - {c.name}")
        return 0

    rep = {"done": [], "fail": []}
    for i, clip in enumerate(cands):
        cmd = [sys.executable, str(JDBG), "--clip", str(clip)]
        oo = latest_ocr_out(clip)
        if oo:
            cmd += ["--ocr-out", oo]
        if a.skip_vl:
            cmd += ["--skip-glm", "--skip-vl"]
        t0 = time.time()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=a.timeout)
            ok = p.returncode == 0
            (rep["done"] if ok else rep["fail"]).append(
                {"film": clip.name, "sure_s": round(time.time() - t0, 1),
                 **({} if ok else {"rc": p.returncode, "err": (p.stderr or "")[-200:]})})
            print(f"[{i+1}/{len(cands)}] {clip.name[:44]:46} {'OK' if ok else 'FAIL'} ({round(time.time()-t0,1)}s)")
        except Exception as exc:  # noqa: BLE001 — tek film batch'i durdurmaz
            rep["fail"].append({"film": clip.name, "err": f"{type(exc).__name__}: {exc}"})
            print(f"[{i+1}/{len(cands)}] {clip.name[:44]:46} EXC {type(exc).__name__}")
    print(json.dumps({"done": len(rep["done"]), "fail": len(rep["fail"]),
                      "fail_list": [f["film"] for f in rep["fail"]]}, ensure_ascii=False))
    return 1 if rep["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
