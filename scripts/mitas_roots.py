# -*- coding: utf-8 -*-
"""MITAS veri-kökleri çözücüsü (İP-5, 2026-07-11 — plan rev.4 RUN_ROOT sözleşmesi).

NEDEN: Kökler mitas_pipeline.py L35-49'da hardcode'du ve Database dışında 7 üretim yazma-yüzeyi
vardı (export, özel-tür, master-log, Excel, event, api_status, web-cache) — tek --db-root
candidate izolasyonu SAĞLAMAZDI (GPT tur-3 6/6 doğrulaması). Bu modül TÜM yazma-köklerini tek
RUN_ROOT parametresinden türetir.

SÖZLEŞME:
  • MITAS_RUN_ROOT boş/yok → mevcut üretim yolları BYTE-AYNI (sıfır davranış değişikliği).
  • MITAS_RUN_ROOT=<dir> (candidate modu) → tüm YAZMA kökleri o dizin altına:
        <RUN_ROOT>/Database, <RUN_ROOT>/export{,ONAYLI,KONTROL,_ISLEM_LOG.*},
        <RUN_ROOT>/muzikal_animasyon_belgesel, <RUN_ROOT>/events/system_events.jsonl,
        <RUN_ROOT>/manifests, <RUN_ROOT>/outputs (api_status/telemetri), <RUN_ROOT>/cache/web
  • OKUMA kökleri (KB duckdb'ler, kaynak videolar, tools/venvs) ÜRETİMDEN okunmaya devam eder —
    candidate izolasyonu yalnız YAZMA yüzeyleri içindir.
  • İzolasyon kanıtı: candidate koşusu sonrası üretim Database/ + 'Mitas Output'/ hash/mtime
    diff = 0 (İP-5 pilot + side-effect testi).

Saf modül: ağır import yok — testler mitas_pipeline'ı import etmeden bunu doğrular."""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(r"E:\MITAS")


def is_candidate() -> bool:
    return bool(os.environ.get("MITAS_RUN_ROOT", "").strip())


def resolve(run_root: str | None = None) -> dict:
    """Tüm yazma-köklerini döndür. run_root=None → env MITAS_RUN_ROOT; o da boşsa üretim."""
    rr = (run_root if run_root is not None else os.environ.get("MITAS_RUN_ROOT", "")).strip()
    if rr:
        base = Path(rr)
        out_root = base                       # 'Mitas Output' eşleniği: candidate kökünün kendisi
        export = base / "export"
        return {
            "PROJECT_ROOT": PROJECT_ROOT,     # kod/araç kökü DEĞİŞMEZ (okuma)
            "RUN_ROOT": base,
            "DB_ROOT": base / "Database",
            "OUT_ROOT": out_root,
            "EXPORT_ROOT": export,
            "HAZIR": export / "ONAYLI",
            "KONTROL": export / "KONTROL",
            "SPECIAL_GENRE_DIR": base / "muzikal_animasyon_belgesel",
            "EVENTS_PATH": base / "events" / "system_events.jsonl",
            "MASTER_MD": export / "_ISLEM_LOG.md",
            "MASTER_JSONL": export / "_ISLEM_LOG.jsonl",
            "MANIFEST_DIR": base / "manifests",
            "OUTPUTS_DIR": base / "outputs",
            "WEB_CACHE_DIR": base / "cache" / "web",
        }
    out_root = PROJECT_ROOT / "Mitas Output"
    export = out_root / "export"
    return {
        "PROJECT_ROOT": PROJECT_ROOT,
        "RUN_ROOT": None,
        "DB_ROOT": PROJECT_ROOT / "Database",
        "OUT_ROOT": out_root,
        "EXPORT_ROOT": export,
        "HAZIR": export / "ONAYLI",
        "KONTROL": export / "KONTROL",
        "SPECIAL_GENRE_DIR": out_root / "muzikal_animasyon_belgesel",
        "EVENTS_PATH": PROJECT_ROOT / "outputs" / "system_events.jsonl",
        "MASTER_MD": export / "_ISLEM_LOG.md",
        "MASTER_JSONL": export / "_ISLEM_LOG.jsonl",
        "MANIFEST_DIR": PROJECT_ROOT / "outputs" / "manifests",
        "OUTPUTS_DIR": PROJECT_ROOT / "outputs",
        "WEB_CACHE_DIR": PROJECT_ROOT / "cache" / "web",
    }


def export_child_env(roots: dict) -> None:
    """Candidate modunda alt-süreçlerin kendi sabitlerini run-root'a bağla (env-köprüsü):
    web_cache.py MITAS_WEB_CACHE_DIR'i, _api_status.py MITAS_API_STATUS_DIR'i,
    run_manifest.py MITAS_MANIFEST_DIR'i zaten env'den okur/okuyacak."""
    if roots.get("RUN_ROOT") is None:
        return
    os.environ.setdefault("MITAS_WEB_CACHE_DIR", str(roots["WEB_CACHE_DIR"]))
    os.environ.setdefault("MITAS_OUTPUTS_DIR", str(roots["OUTPUTS_DIR"]))     # api_status + telemetri + lock
    os.environ.setdefault("MITAS_MANIFEST_DIR", str(roots["MANIFEST_DIR"]))
    os.environ["MITAS_RUN_ROOT"] = str(roots["RUN_ROOT"])   # alt-süreç zinciri aynı kökü görür
