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

# Linux geçişi 2026-07-16: env varsa onu kullan; fallback Linux kök dizini.
# 2026-08-03: Windows kalıntısı E:\MITAS kaldırıldı — sistem tamamen Linux'ta.
PROJECT_ROOT = Path(os.environ.get("MITAS_PROJECT_ROOT") or "/opt/mitas")
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

    Yalniz ``/opt/mitas/candidate_runs/<run-id>`` altina izin verilir. Kokun kendisi,
    goreli yollar ve candidate altindaki junction/symlink'ler reddedilir; boylece
    ``--run-root /opt/mitas`` veya production'a acilan bir junction izolasyonu delemez.
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


def link_hub_frames(from_hub, clip_dir) -> None:
    r"""FROM-HUB: kaynak hub'ın giris/cikis frame dizinlerini candidate ``clip_dir``ine bağla.

    KÖK-SEBEP FIX (2026-07-30): symlink HEDEFİ MUTLAK olmalı. Eskiden ``_src_f`` göreli
    ``--from-hub`` argümanıyla göreli kalıyor, ``os.symlink`` göreli hedef yazıyor ve link kendi
    dizinine göre çözülünce DANGLING oluyordu → glob 0 kare → ``_pipe_ocr`` fallback → sahte
    MOTOR_YOK (fitz_dogrulama/YAĞMACILAR kanıtı; readlink -e = YOK). ``from_hub``ı mutlağa
    çevirmek link hedefini mutlak yapar → dangling kökten biter. Windows junction (mklink /J)
    zaten mutlak yol alır; davranış korunur. copytree fallback her iki yolda da güvenli."""
    import shutil
    import subprocess

    src_root = Path(from_hub).resolve()          # MUTLAK: göreli --from-hub'da dangling'i önler
    dst_root = Path(clip_dir)
    for _fdir in ("giris", "cikis"):
        _src_f = src_root / "frames" / _fdir
        _dst_f = dst_root / "frames" / _fdir
        if _src_f.exists() and not _dst_f.exists():
            _dst_f.parent.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                _r = subprocess.run(["cmd", "/c", "mklink", "/J", str(_dst_f), str(_src_f)],
                                    capture_output=True, text=True, timeout=30)
                if _r.returncode:                # junction başarısız (yetki vb.) → kopyaya düş
                    shutil.copytree(_src_f, _dst_f)
            else:
                try:
                    os.symlink(_src_f, _dst_f, target_is_directory=True)
                except Exception:  # noqa: BLE001 — symlink yasak/yok → kopya (yavaş ama güvenli)
                    shutil.copytree(_src_f, _dst_f)


def find_usable_ocr(clip_dir):
    """clip_dir/ocr/*/kunye.txt icinden en-yeni KULLANILABILIR yol; yoksa None.

    Kullanilabilir = -fb kardesi DEGIL + bos DEGIL + bucket MOTOR_YOK DEGIL. Tek-kaynak seciciler:
    _pipe_credit_text._find_ocr (karar okuyucusu) VE from-hub reuse-kapisi bunu kullanir.
    KÖK-SEBEP (2026-07-30): BOŞ/MOTOR_YOK bir (from-hub candidate) re-OCR'i, iyi eski/kopya okumayi
    en-yeni-mtime kuraliyla GOLGELIYORDU → sahte 'Kontrol'. frames_rerun.py:87-88 zaten bu kalkani
    uyguluyordu; uretim karar-okuyucusu uygulamiyordu."""
    import glob as _glob
    import json as _json
    if not clip_dir:
        return None
    g = sorted(_glob.glob(os.path.join(str(clip_dir), "ocr", "*", "kunye.txt")),
               key=lambda p: os.path.getmtime(p))
    for p in reversed(g):                       # en-yeniden eskiye: ilk kullanilabilir
        d = os.path.dirname(p)
        if os.path.basename(d).endswith("-fb"):
            continue                            # -fb (fallback) kardesi otoriter degil
        try:
            if not any(ln.strip() for ln in open(p, encoding="utf-8", errors="replace")):
                continue                        # bos/yalniz-bosluk kunye
        except OSError:
            continue
        try:
            if _json.load(open(os.path.join(d, "ocr_summary.json"),
                               encoding="utf-8")).get("bucket") == "MOTOR_YOK":
                continue                        # motor kurulamadi (sahte-kirmizi)
        except Exception:  # noqa: BLE001 — summary yok/bozuk → boyut-temelli kabule birak
            pass
        return p
    return None


def should_reuse_hub_ocr(from_hub, force_ocr, clip_dir) -> bool:
    """from-hub'da taze OCR yerine kopyalanan hub OCR'i yeniden kullan? (Q1, Cagatay 2026-07-30).

    Evet ANCAK: from-hub modu + --force-ocr YOK + kullanilabilir kopya OCR var. Boylece hub'in
    GUVENILIR OCR'i varken from-hub candidate koşusu bir daha sahte-MOTOR_YOK/regresyon uretmez
    ve ~10x hizlanir; OCR degisikligi test edilecekse --force-ocr ile taze koşulur
    (frames_rerun.py:86 akilli-varsayilani)."""
    return bool(from_hub) and not force_ocr and find_usable_ocr(clip_dir) is not None
