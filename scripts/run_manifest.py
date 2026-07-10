# -*- coding: utf-8 -*-
"""RUN-MANIFEST + PREFLIGHT (İP-1, 2026-07-11 — KONTROL-sağlıklılaştırma planı rev.4).

NEDEN: (1) "Bu sonucu hangi kod/model/ayar üretti?" sorusu bugüne dek cevapsızdı — 35-film
OCR-partial vakasının kökünü bulmak bir gün sürdü; manifest olsaydı dakikaydı. (2) Geçmişte
ollama model-deposu boşken 36 film "işlendi" sanıldı (sahte-KONTROL dalgası) — preflight
bunu koşu BAŞLAMADAN keser.

SÖZLEŞME (konsey şartnamesi, outputs/KONSEY_KONTROL_SARTNAME_2026-07-10.md):
  • Manifest her koşuda hub'a yazılır: run_id, git_sha, dirty/patch-hash, input_sig,
    model_digests, prompt_source_hashes, config_snapshot (MITAS_*), parent_run_id.
  • Preflight HARD-FAIL: ollama erişilebilir + model gerçek-inference verebiliyor,
    DuckDB KB dosyaları yerinde (import edilebiliyorsa SELECT 1), disk yeterli.
  • Dirty iki-mod: tek-film geliştirme serbest (patch-hash manifest'e KANIT olarak);
    MITAS_BATCH_MODE=1 → tracked-diff TEMİZ zorunlu (bypass YOK) + tek-writer kilidi.
  • "Temiz" tanımı: git tracked-diff (diff HEAD) boş; untracked artefaktlar (outputs/ vb.)
    SAYILMAZ — bilinçli karar, plan rev.4.

Stdlib-only (urllib/hashlib/subprocess); duckdb import'u opsiyonel (global py'da olmayabilir,
bkz credit_kb_lookup.py notu) — yoksa dosya-varlığı kontrolüne düşer, not manifest'e yazılır.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(r"E:\MITAS")
OUT_MANIFEST_DIR = PROJECT_ROOT / "outputs" / "manifests"
LOCK_PATH = PROJECT_ROOT / "outputs" / ".mitas_writer.lock"
OLLAMA = os.environ.get("MITAS_OLLAMA_URL", "http://127.0.0.1:11434")
# credit_crosscheck.py ile AYNI env adları/varsayılanları (tek-kaynak: oradaki tanım esas).
WIKIDATA_DB = os.environ.get("MITAS_WIKIDATA_DUCKDB", r"X:\DIGER\Mitas_Files\MitaData\mitas.duckdb")
IMDB_DB = os.environ.get("MITAS_IMDB_DUCKDB", r"Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb")
# Prompt'ları taşıyan kaynak dosyalar — hash'leri "prompt sürümü" vekilidir (v1; İP-4'te
# gate_version ile rafine edilir).
PROMPT_SOURCES = ("credit_text_read.py", "credit_qc_block.py", "_pipe_pdf.py")
SCHEMA_VERSION = 1


class PreflightError(RuntimeError):
    """Preflight hard-fail — koşu BAŞLAMAMALI."""


# --------------------------------------------------------------------------- git
def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(PROJECT_ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} rc={r.returncode}: {(r.stderr or '')[:200]}")
    return (r.stdout or "").strip()


def git_state() -> dict:
    """Tracked-diff temelli durum. Untracked SAYILMAZ (plan rev.4 bilinçli karar)."""
    sha = _git("rev-parse", "HEAD")
    diff = subprocess.run(["git", "diff", "HEAD"], cwd=str(PROJECT_ROOT), capture_output=True,
                          timeout=120).stdout or b""
    dirty = bool(diff.strip())
    return {
        "git_sha": sha,
        "git_dirty": dirty,
        "dirty_patch_sha256": hashlib.sha256(diff).hexdigest() if dirty else None,
        "dirty_patch_bytes": len(diff) if dirty else 0,
    }


# --------------------------------------------------------------------------- girdi imzası
def input_signature(video: Path, chunk_mb: int = 8) -> dict:
    """Tam-dosya sha256 çok pahalı (W:\\ üzerinde 4GB video). İmza: boyut + ilk/son 8MB sha256.
    Aynı dosyanın sessiz değişimini yakalamaya yeter; kriptografik bütünlük iddiası değildir."""
    size = video.stat().st_size
    h = hashlib.sha256()
    n = chunk_mb * 1024 * 1024
    with video.open("rb") as f:
        h.update(f.read(n))
        if size > 2 * n:
            f.seek(size - n)
            h.update(f.read(n))
    h.update(str(size).encode())
    return {"size_bytes": size, "sig_sha256": h.hexdigest()}


# --------------------------------------------------------------------------- ollama / KB
def _http_json(url: str, payload: dict | None = None, timeout: float = 10.0) -> dict:
    if payload is None:
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def ollama_models() -> dict:
    """name→digest haritası (/api/tags). Sunucu kapalıysa exception — preflight yakalar."""
    data = _http_json(OLLAMA + "/api/tags", timeout=10)
    return {m.get("name", "?"): (m.get("digest") or "")[:19] for m in data.get("models", [])}


def ollama_generate_ping(model: str, timeout: float = 240.0) -> float:
    """1-token GERÇEK inference (GPT şartı: model-listesi yetmez). Soğuk yüklemede uzun
    sürebilir; yan-fayda: modeli ısıtır (keep_alive). Süreyi döndürür."""
    t0 = time.perf_counter()
    _http_json(OLLAMA + "/api/generate",
               {"model": model, "prompt": "ping", "stream": False,
                "options": {"num_predict": 1},
                "keep_alive": os.environ.get("MITAS_OLLAMA_KEEP_ALIVE", "15m")},
               timeout=timeout)
    return round(time.perf_counter() - t0, 1)


def duckdb_check() -> list[str]:
    """KB dosyaları yerinde mi + (duckdb import edilebiliyorsa) SELECT 1.
    36-sahte-KONTROL dalgasının ikinci kökü (CSV-fallback aksan-kaybı) bu kapıyla kesilir."""
    problems: list[str] = []
    notes: list[str] = []
    for label, p in (("wikidata", WIKIDATA_DB), ("imdb", IMDB_DB)):
        if not Path(p).exists():
            problems.append(f"duckdb-{label} dosyası YOK: {p}")
    if not problems:
        try:
            import duckdb  # global py'da olmayabilir — o zaman dosya-varlığı yeterli sayılır
            for p in (WIKIDATA_DB, IMDB_DB):
                con = duckdb.connect(p, read_only=True)
                con.execute("SELECT 1").fetchone()
                con.close()
        except ImportError:
            notes.append("duckdb-import-yok(global-py): yalnız dosya-varlığı doğrulandı")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"duckdb SELECT 1 başarısız: {exc}")
    duckdb_check.notes = notes  # type: ignore[attr-defined]
    return problems


# --------------------------------------------------------------------------- kilit
def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except Exception:  # noqa: BLE001 — Windows PermissionError: süreç var ama erişim yok
        return True
    return True


def acquire_writer_lock() -> None:
    """Batch tek-writer kilidi. Bayat kilit (ölü pid) uyarıyla devralınır."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        try:
            old = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            if _pid_alive(int(old.get("pid", -1))):
                raise PreflightError(
                    f"writer-kilidi dolu: pid={old.get('pid')} ts={old.get('ts')} ({LOCK_PATH})")
            sys.stderr.write(f"[preflight] bayat writer-kilidi devralindi (olu pid={old.get('pid')})\n")
        except PreflightError:
            raise
        except Exception:  # noqa: BLE001 — bozuk kilit dosyası = bayat say
            sys.stderr.write("[preflight] bozuk writer-kilidi devralindi\n")
    LOCK_PATH.write_text(json.dumps({"pid": os.getpid(), "ts": datetime.now().isoformat()}),
                         encoding="utf-8")
    # Erken-return/istisna yollarında kilit sızmasın: süreç çıkışında idempotent release.
    import atexit
    atexit.register(release_writer_lock)


def release_writer_lock() -> None:
    try:
        if LOCK_PATH.exists():
            old = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            if int(old.get("pid", -1)) == os.getpid():
                LOCK_PATH.unlink()
    except Exception:  # noqa: BLE001 — kilit temizliği asla koşuyu bozmaz
        pass


# --------------------------------------------------------------------------- preflight
def run_preflight(batch_mode: bool = False) -> dict:
    """Sağlık kapısı. batch_mode'da bypass YOK; tek-film modunda MITAS_PREFLIGHT=0 kaçışı var
    (yalnız geliştirme). Dönen dict manifest'e gömülür."""
    if not batch_mode and os.environ.get("MITAS_PREFLIGHT", "1").strip() == "0":
        return {"skipped": True, "reason": "MITAS_PREFLIGHT=0 (tek-film gelistirme kacisi)"}

    problems: list[str] = []
    info: dict = {"schema_version": SCHEMA_VERSION}

    # 1) ollama: sunucu + gerçek inference
    try:
        models = ollama_models()
        info["ollama_models"] = models
        if not models:
            problems.append("ollama model-deposu BOŞ (36-sahte-KONTROL kökü!)")
    except Exception as exc:  # noqa: BLE001
        models = {}
        problems.append(f"ollama erişilemedi ({OLLAMA}): {exc}")
    if models and os.environ.get("MITAS_PREFLIGHT_GENERATE", "1").strip() != "0":
        model = os.environ.get("MITAS_PREFLIGHT_MODEL", "gemma-4-31b-it-qat-vision:latest")
        if model not in models:
            problems.append(f"preflight-modeli depoda yok: {model}")
        else:
            try:
                info["ollama_ping_sn"] = ollama_generate_ping(model)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"ollama 1-token inference başarısız ({model}): {exc}")

    # 2) DuckDB KB'ler
    problems += duckdb_check()
    info["duckdb_notes"] = getattr(duckdb_check, "notes", [])

    # 3) Disk
    import shutil as _sh
    free_gb = _sh.disk_usage(str(PROJECT_ROOT)).free / (1024 ** 3)
    info["disk_free_gb"] = round(free_gb, 1)
    min_gb = float(os.environ.get("MITAS_PREFLIGHT_MIN_DISK_GB", "20"))
    if free_gb < min_gb:
        problems.append(f"disk yetersiz: {free_gb:.1f}GB < {min_gb}GB")

    # 4) Batch-modu: temiz-ağaç + tek-writer (bypass YOK — plan rev.4/GPT şartı)
    gs = git_state()
    info["git"] = gs
    if batch_mode:
        if gs["git_dirty"]:
            problems.append(
                f"batch-modu kirli tracked-ağaçla koşamaz (+{gs['dirty_patch_bytes']}B diff, "
                f"patch-sha {gs['dirty_patch_sha256']}) — önce commit")
        acquire_writer_lock()
        info["writer_lock"] = str(LOCK_PATH)

    if problems:
        if batch_mode:
            release_writer_lock()
        raise PreflightError(" | ".join(problems))
    return info


# --------------------------------------------------------------------------- manifest
def build_manifest(video: Path, profile: str, argv: list[str] | None,
                   preflight_info: dict | None = None) -> dict:
    cfg = {k: v for k, v in sorted(os.environ.items()) if k.startswith("MITAS_")}
    prompt_hashes = {}
    for name in PROMPT_SOURCES:
        p = PROJECT_ROOT / "scripts" / name
        if p.exists():
            prompt_hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    try:
        models = ollama_models()
    except Exception:  # noqa: BLE001 — preflight zaten denetledi; burada best-effort
        models = {}
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": uuid.uuid4().hex[:12],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "parent_run_id": os.environ.get("MITAS_PARENT_RUN_ID") or None,
        "video": str(video),
        "profile": profile,
        "argv": list(argv or sys.argv[1:]),
        "input": input_signature(video),
        **git_state(),
        "model_digests": models,
        "prompt_source_hashes": prompt_hashes,
        "config_snapshot": cfg,
        "preflight": preflight_info or {},
        "status": "running",
    }


def write_start(clip_dir: Path, manifest: dict) -> None:
    p = clip_dir / "run_manifest.json"
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        OUT_MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_MANIFEST_DIR / f"{manifest['run_id']}.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:  # noqa: BLE001 — merkez kopya best-effort, hub kopyası esas
        pass


def finalize(clip_dir: Path, status: str, extra: dict | None = None) -> None:
    """Koşu sonunda manifest'i tamamla. ASLA koşuyu bozmaz (best-effort)."""
    try:
        p = clip_dir / "run_manifest.json"
        m = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        m["status"] = status
        m["finished_at"] = datetime.now().isoformat(timespec="seconds")
        if extra:
            m["result"] = extra
        p.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        rid = m.get("run_id")
        if rid:
            OUT_MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
            (OUT_MANIFEST_DIR / f"{rid}.json").write_text(
                json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[manifest] finalize hatasi (kosu etkilenmez): {exc}\n")


# --------------------------------------------------------------------------- CLI
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="run_manifest standalone: --preflight ile sağlık kapısını tek başına koş")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--batch", action="store_true", help="batch-modu kuralları (temiz-ağaç + kilit)")
    a = ap.parse_args()
    if a.preflight:
        try:
            inf = run_preflight(batch_mode=a.batch)
            print("PREFLIGHT OK")
            print(json.dumps(inf, ensure_ascii=False, indent=1))
            if a.batch:
                release_writer_lock()
        except PreflightError as e:
            print(f"PREFLIGHT FAIL: {e}")
            sys.exit(3)
