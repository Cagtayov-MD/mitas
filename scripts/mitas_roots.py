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
import stat
from pathlib import Path

# Linux geçişi 2026-07-16: env varsa onu kullan (Windows'ta env yoksa eski davranış birebir).
PROJECT_ROOT = Path(os.environ.get("MITAS_PROJECT_ROOT") or r"E:\MITAS")
CANDIDATE_ROOT = PROJECT_ROOT / "candidate_runs"


class RootSafetyError(ValueError):
    """Yazma kokunun production'a kacabilecegi durumlarda hard-fail."""


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_reparse_point(path: Path) -> bool:
    """Windows junction/symlink kacisini yakala; diger platformlarda symlink yeterlidir."""
    try:
        st = path.lstat()
    except OSError:
        return False
    attrs = getattr(st, "st_file_attributes", 0)
    return path.is_symlink() or bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def validate_candidate_run_root(run_root: str | Path) -> Path:
    r"""Candidate kokunu production'dan fiziksel ve mantiksal olarak ayir.

    Yalniz ``E:\MITAS\candidate_runs\<run-id>`` altina izin verilir. Kokun kendisi,
    goreli yollar ve candidate altindaki junction/symlink'ler reddedilir; boylece
    ``--run-root E:\MITAS`` veya production'a acilan bir junction izolasyonu delemez.
    """
    raw = Path(run_root).expanduser()
    if not raw.is_absolute():
        raise RootSafetyError(f"candidate run-root mutlak yol olmali: {run_root}")
    base = _resolved(raw)
    allowed = _resolved(CANDIDATE_ROOT)
    if base == allowed or not _is_relative_to(base, allowed):
        raise RootSafetyError(
            f"candidate run-root yalniz {allowed} altinda benzersiz bir run dizini olabilir: {base}")

    # Mevcut her alt bilesen reparse-point olmamali. Candidate kokunun kendisi kurulum
    # tercihi olabilir; onun ALTINDA production'a acilan junction/symlink kabul edilmez.
    rel = raw.resolve(strict=False).relative_to(allowed)
    cur = allowed
    for part in rel.parts:
        cur = cur / part
        if cur.exists() and _is_reparse_point(cur):
            raise RootSafetyError(f"candidate run-root reparse-point/junction iceremez: {cur}")
    return base


def is_candidate() -> bool:
    return bool(os.environ.get("MITAS_RUN_ROOT", "").strip())


def resolve(run_root: str | None = None) -> dict:
    """Tüm yazma-köklerini döndür. run_root=None → env MITAS_RUN_ROOT; o da boşsa üretim."""
    rr = (run_root if run_root is not None else os.environ.get("MITAS_RUN_ROOT", "")).strip()
    if rr:
        base = validate_candidate_run_root(rr)
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
            "AFIS_CACHE_DIR": base / "cache" / "afis",
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
        "AFIS_CACHE_DIR": PROJECT_ROOT / "_102_afis_cache",
    }


def resolve_production() -> dict:
    """Ortamda MITAS_RUN_ROOT olsa bile daima gercek production koklerini dondur."""
    return resolve("")


def export_child_env(roots: dict) -> None:
    """Candidate modunda alt-süreçlerin kendi sabitlerini run-root'a bağla (env-köprüsü):
    web_cache.py MITAS_WEB_CACHE_DIR'i, _api_status.py MITAS_API_STATUS_DIR'i,
    run_manifest.py MITAS_MANIFEST_DIR'i zaten env'den okur/okuyacak."""
    if roots.get("RUN_ROOT") is None:
        return
    # setdefault GUVENLI DEGIL: parent surecten kalan production override'i candidate
    # alt-surecine sizdirir. Candidate modunda bu dort degisken tek otoritedir.
    os.environ["MITAS_WEB_CACHE_DIR"] = str(roots["WEB_CACHE_DIR"])
    os.environ["MITAS_OUTPUTS_DIR"] = str(roots["OUTPUTS_DIR"])     # api_status + telemetri + lock
    os.environ["MITAS_MANIFEST_DIR"] = str(roots["MANIFEST_DIR"])
    os.environ["MITAS_AFIS_CACHE_DIR"] = str(roots["AFIS_CACHE_DIR"])
    os.environ["MITAS_RUN_ROOT"] = str(roots["RUN_ROOT"])   # alt-süreç zinciri aynı kökü görür
