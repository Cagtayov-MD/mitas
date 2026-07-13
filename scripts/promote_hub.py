# -*- coding: utf-8 -*-
"""promote_hub.py — CANDIDATE → CANONICAL crash-recoverable promotion/demote (İP-6, 2026-07-11).

Plan rev.4 + qwen/GLM İP-6-tur kararları:
  • ARCHIVING ve PROMOTING = TEK üst-düzey os.replace ("ya hep ya hiç" — GLM-a; kısmî-arşiv
    imkânsız, manifest'li geri-sarma gereksiz).
  • Yarım-durum kurtarması yalnız GÜVENLİ tek-rename tamamlamaları yapar; belirsiz her durum
    İNSAN-KİLİDİ (quarantine) — script ASLA silme/geri-taşıma denemez (qwen).
  • REBASING dosya-başına temp+os.replace; demote'ta da koşar (GLM).
  • promotion.lock: pid + süreç-adı doğrulaması (PID-reuse zehirlenmesi — GLM).
  • Hub-Quiesce: promote öncesi açık-handle kontrolü (psutil varsa; yoksa uyarı) (qwen).
  • hub RW-kilidi: hub.<trt>.lock — retry-read açıkken promote BLOK (GLM yarış senaryosu).
  • os.replace: üstel-backoff 5 deneme (0.5..8s) + AccessDenied mesajı.
  • Arşiv-GC: max sürüm aşımı OTOMATİK SİLME DEĞİL (silme-yasak kanunu) — gc-adayı raporu.
  • Semantic-diff HARD-GATE: yönetmen/cast/başlık/tür DOLU→BOŞ ise promotion RED
    (operation=REMOVE + approved_by=human ile bilinçli-kaldırma hariç).
  • Promotion HEP MANUEL komut; otomatik promote YOK.

Kullanım:
  python scripts/promote_hub.py --candidate <candidate-hub-dir> [--apply] [--demote <trt>]
  (--apply'siz DRY-RUN: diff + plan basar, dokunmaz.)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mitas_roots  # noqa: E402

TRT_RE = re.compile(r"(\d{4}-\d{3,4}-\d-\d{3,4}-\d{2}-\d)")
HARD_GATE_ALANLAR = ("yonetmen", "cast", "title", "tur")   # DOLU→BOŞ = HARD-BLOCK
REBASE_DOSYALAR = ("_DURUM.json", "clip.json", "run_manifest.json",
                   "karar.pipeline.json", "karar.view.json")
ARCHIVE_MAX_SURUM = 3          # aşımı = gc-adayı raporu (SİLME YOK — Çağatay onayı gerekir)
_OWNED_LOCK_TOKENS: dict[str, str] = {}


class PromoteError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def _replace_backoff(src: Path, dst: Path, tries: int = 5) -> None:
    """os.replace + üstel-backoff (Windows AccessDenied: antivirüs/indeksleyici/açık-handle)."""
    delay = 0.5
    for i in range(tries):
        try:
            os.replace(str(src), str(dst))
            return
        except OSError as exc:
            if i == tries - 1:
                raise PromoteError(
                    f"os.replace {tries} denemede başarısız ({src} → {dst}): {exc} — "
                    f"açık dosya/antivirüs olabilir; dosyaları kapatın") from exc
            time.sleep(delay)
            delay = min(delay * 2, 8.0)


def _atomic_json(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(str(tmp), str(path))


def _load_json(path: Path, label: str) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise PromoteError(f"{label} okunamadi/bozuk: {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise PromoteError(f"{label} JSON nesnesi degil: {path}")
    return obj


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def _trt_of_name(name: str) -> str | None:
    m = TRT_RE.search(_nfc(name))
    return m.group(1) if m else None


# ─────────────────────────── resolver ───────────────────────────
def resolve_canonical(trt: str, db_root: Path) -> Path | None:
    """0=NOT_FOUND(None) / 1=OK / >1=AMBIGUOUS_HUB hard-fail. NFC-normalize taramalı (GLM)."""
    trt = _nfc(trt).strip()
    hits = [d for d in db_root.iterdir()
            if d.is_dir() and _trt_of_name(d.name) == trt and (d / "_DURUM.json").exists()]
    if len(hits) > 1:
        raise PromoteError(
            f"AMBIGUOUS_HUB: {trt} için {len(hits)} kopya ({[h.name for h in hits]}) — "
            f"önce dedup prosedürü (bkz ADI CARMEN raporu); promotion RED")
    return hits[0] if hits else None


# ─────────────────────────── kilitler ───────────────────────────
def _proc_name(pid: int) -> str | None:
    try:
        import psutil
        return psutil.Process(pid).name()
    except Exception:  # noqa: BLE001 — psutil yok/erisim yok → None (ad-doğrulaması yapılamaz)
        return None


def acquire_lock(lock_path: Path, kind: str) -> None:
    """O_EXCL ile atomik kilit al; stale devralma da rename-yarisi guvenlidir."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    payload = json.dumps(
        {"pid": os.getpid(), "proc": _proc_name(os.getpid()) or "python", "ts": _now(),
         "kind": kind, "token": token}, ensure_ascii=False).encode("utf-8")
    for _ in range(8):
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                old = json.loads(lock_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                old = {}
            pid = int(old.get("pid", -1))
            ad = _proc_name(pid)
            if ad is not None and old.get("proc") and ad != old.get("proc"):
                sys.stderr.write(
                    f"[kilit] PID-reuse: {pid} artık {ad} ({old.get('proc')} değil) — bayat devralındı\n")
            elif ad is not None or _pid_alive(pid):
                raise PromoteError(
                    f"{kind}-kilidi dolu: pid={pid} proc={old.get('proc')} ts={old.get('ts')}")
            stale = lock_path.with_name(f"{lock_path.name}.stale.{os.getpid()}.{uuid.uuid4().hex}")
            try:
                os.replace(str(lock_path), str(stale))
            except FileNotFoundError:
                continue  # baska aday stale'i devraldi; atomik create'i yeniden dene
            try:
                stale.unlink()
            except OSError:
                pass
            continue
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        _OWNED_LOCK_TOKENS[str(lock_path.resolve(strict=False))] = token
        return
    raise PromoteError(f"{kind}-kilidi atomik olarak alinamadi: {lock_path}")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            process_query_limited_information = 0x1000
            still_active = 259
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            handle = kernel32.OpenProcess(process_query_limited_information, False, int(pid))
            if not handle:
                return False
            try:
                code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return True
                return code.value == still_active
            finally:
                kernel32.CloseHandle(handle)
        except Exception:  # noqa: BLE001 — WinAPI yoksa salt-sorgu psutil'e dus
            try:
                import psutil
                return psutil.pid_exists(pid)
            except Exception:
                return True  # fail-safe: sorgulanamayan PID canli sayilir, kilit ezilmez
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except Exception:  # noqa: BLE001
        return True
    return True


def release_lock(lock_path: Path) -> None:
    try:
        key = str(lock_path.resolve(strict=False))
        token = _OWNED_LOCK_TOKENS.get(key)
        old = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else {}
        if token and old.get("pid") == os.getpid() and old.get("token") == token:
            lock_path.unlink()
        _OWNED_LOCK_TOKENS.pop(key, None)
    except Exception:  # noqa: BLE001
        pass


def hub_rw_lock_path(db_root: Path, trt: str) -> Path:
    return db_root / f".hub.{trt}.lock"


def promotion_lock_path(db_root: Path) -> Path:
    return db_root / ".promotion.lock"


def quiesce_check(hub: Path) -> list[str]:
    """Hub-Quiesce (qwen): hub altındaki dosyaları açık tutan süreçleri bul (psutil best-effort).
    Bulunanlar promotion'ı RED'letir ('dosyaları kapatın'); psutil yoksa boş-liste + uyarı."""
    try:
        import psutil
    except Exception:  # noqa: BLE001
        sys.stderr.write("[quiesce] psutil yok — açık-handle taraması atlandı (backoff'a güveniliyor)\n")
        return []
    tutanlar = []
    hub_s = str(hub).lower()
    for p in psutil.process_iter(["pid", "name", "open_files"]):
        try:
            for f in (p.info.get("open_files") or []):
                if str(f.path).lower().startswith(hub_s):
                    tutanlar.append(f"{p.info['name']}({p.info['pid']}): {f.path}")
                    break
        except Exception:  # noqa: BLE001 — erişilemeyen süreç atlanır
            continue
    return tutanlar


# ─────────────────────────── candidate + export dogrulama ───────────────────────────
def _candidate_context(candidate_hub: Path, canonical: Path | None, trt: str) -> dict:
    """Candidate'in kimlik, lineage, kaynak-imza ve teslim sozlesmesini hard-gate et."""
    try:
        candidate_hub = candidate_hub.resolve(strict=True)
    except OSError as exc:
        raise PromoteError(f"candidate hub bulunamadi: {candidate_hub}: {exc}") from exc
    if not candidate_hub.is_dir() or candidate_hub.parent.name.casefold() != "database":
        raise PromoteError(
            f"CANDIDATE-PARENT: beklenen yapi <run-root>/Database/<hub>: {candidate_hub}")
    run_root = mitas_roots.validate_candidate_run_root(candidate_hub.parent.parent)
    if candidate_hub.parent.resolve() != (run_root / "Database").resolve(strict=False):
        raise PromoteError(f"CANDIDATE-PARENT: hub beklenen Database altinda degil: {candidate_hub}")

    durum = _load_json(candidate_hub / "_DURUM.json", "candidate _DURUM")
    clip = _load_json(candidate_hub / "clip.json", "candidate clip")
    manifest = _load_json(candidate_hub / "run_manifest.json", "candidate run_manifest")
    ids = {str(durum.get("trt_id") or "").strip(), str(clip.get("trt_id") or "").strip(), trt}
    if ids != {trt}:
        raise PromoteError(f"KIMLIK-TUTARSIZ: klasor/_DURUM/clip TRT-ID uyusmuyor: {sorted(ids)}")
    if manifest.get("status") in (None, "", "running") or not manifest.get("finished_at"):
        raise PromoteError("MANIFEST-TAMAMLANMADI: status/finished_at eksik veya kosu halen running")
    if str(manifest.get("status")) != str(durum.get("karar")):
        raise PromoteError(
            f"KARAR-DRIFT: manifest={manifest.get('status')} _DURUM={durum.get('karar')}")
    if manifest.get("source_drift") is not False:
        raise PromoteError(
            f"SOURCE-DRIFT: manifest source_drift={manifest.get('source_drift')!r}; temiz kosu kaniti yok")
    if manifest.get("git_dirty") is not False:
        raise PromoteError("DIRTY-CANDIDATE: git_dirty=true kosu production'a promote edilemez")
    inp = manifest.get("input") if isinstance(manifest.get("input"), dict) else {}
    if not inp.get("sig_sha256"):
        raise PromoteError("INPUT-IMZA: manifest input.sig_sha256 eksik/null")

    cfg = manifest.get("config_snapshot") if isinstance(manifest.get("config_snapshot"), dict) else {}
    cfg_root = cfg.get("MITAS_RUN_ROOT")
    if not cfg_root or Path(cfg_root).resolve(strict=False) != run_root:
        raise PromoteError(
            f"RUN-ROOT-DRIFT: manifest={cfg_root!r} gercek={run_root}")

    # from-hub adayinda hem kaynak hub yolu hem onun run_id'si beklenen parent olmalidir.
    if inp.get("kind") == "hub" or str(cfg.get("MITAS_FROM_HUB", "")) == "1":
        src_hub_s = inp.get("hub")
        if not src_hub_s or canonical is None:
            raise PromoteError("EXPECTED-PARENT: from-hub girdisi canonical parent gostermiyor")
        src_hub = Path(src_hub_s).resolve(strict=False)
        if src_hub != canonical.resolve(strict=False):
            raise PromoteError(f"EXPECTED-PARENT: manifest={src_hub} canonical={canonical}")
        import run_manifest as _run_manifest
        current_input = _run_manifest.hub_input_signature(canonical)
        if current_input.get("sig_sha256") != inp.get("sig_sha256"):
            raise PromoteError(
                "INPUT-DRIFT: canonical hub, candidate kosusundan sonra degismis; taze rerun gerekir")
        # LEGACY-CANONICAL uyumu (2026-07-12): İP-1-öncesi üretim hub'larında run_manifest.json YOK
        # (tüm mevcut üretim hub'ları böyle). O durumda parent-run_id doğrulanamaz; ama parent-kanıtı
        # zaten YUKARIDAKİ INPUT-DRIFT ile sağlanıyor (deterministik input-imza + EXPECTED-PARENT yol
        # eşleşmesi) — bu, run_id'den DAHA güçlü, içerik-tabanlı bir kanıt. Manifest VARSA run_id de
        # kontrol edilir (yeni-nesil hub'lar için sıkı kalır); YOKSA input-imza kanıtına güvenilir.
        _canon_mf = canonical / "run_manifest.json"
        if _canon_mf.is_file():
            parent_manifest = _load_json(_canon_mf, "canonical run_manifest")
            expected_parent_run = str(parent_manifest.get("run_id") or "")
            if not expected_parent_run or str(manifest.get("parent_run_id") or "") != expected_parent_run:
                raise PromoteError(
                    f"PARENT-RUN-DRIFT: candidate={manifest.get('parent_run_id')!r} "
                    f"canonical={expected_parent_run!r}")

    ext = str(durum.get("extraction_status") or "").upper()
    if ext == "TECHNICAL_FAILURE":
        raise PromoteError("TECHNICAL_FAILURE candidate production'a promote edilemez")

    hub_pdf_s = durum.get("pdf")
    teslim_s = durum.get("teslim")
    if not hub_pdf_s or not teslim_s:
        raise PromoteError("TESLIM-TAMLIK: _DURUM.pdf veya _DURUM.teslim eksik")
    hub_pdf = Path(hub_pdf_s).resolve(strict=False)
    teslim = Path(teslim_s).resolve(strict=False)
    if not _is_under(hub_pdf, candidate_hub) or not hub_pdf.is_file():
        raise PromoteError(f"TESLIM-TAMLIK: hub PDF candidate altinda degil/yok: {hub_pdf}")
    candidate_export = (run_root / "export").resolve(strict=False)
    if not _is_under(teslim, candidate_export) or not teslim.is_file():
        raise PromoteError(f"TESLIM-TAMLIK: teslim candidate export altinda degil/yok: {teslim}")
    if teslim.suffix.lower() != ".pdf" or teslim.stat().st_size <= 8:
        raise PromoteError(f"TESLIM-TAMLIK: gecersiz teslim PDF: {teslim}")
    with teslim.open("rb") as f:
        teslim_magic = f.read(4)
        f.seek(max(0, teslim.stat().st_size - 2048))
        teslim_tail = f.read()
    with hub_pdf.open("rb") as f:
        hub_magic = f.read(4)
        f.seek(max(0, hub_pdf.stat().st_size - 2048))
        hub_tail = f.read()
    if (teslim_magic != b"%PDF" or hub_magic != b"%PDF"
            or b"%%EOF" not in teslim_tail or b"%%EOF" not in hub_tail):
        raise PromoteError("TESLIM-TAMLIK: dosya gecerli PDF baslangic/EOF imzasi tasimiyor")
    if _sha256(hub_pdf) != _sha256(teslim):
        raise PromoteError("TESLIM-DRIFT: hub PDF ile candidate export PDF byte-esit degil")
    expected_bucket = "ONAYLI" if durum.get("karar") == "Hazır" else "KONTROL"
    if teslim.parent.name.casefold() != expected_bucket.casefold():
        raise PromoteError(
            f"TESLIM-ROTA-DRIFT: karar={durum.get('karar')} teslim={teslim.parent.name}")
    return {"hub": candidate_hub, "run_root": run_root, "durum": durum, "clip": clip,
            "manifest": manifest, "delivery": teslim, "delivery_sha256": _sha256(teslim),
            "bucket": expected_bucket}


def _export_roots(roots: dict) -> dict[str, Path]:
    return {"ONAYLI": Path(roots["HAZIR"]), "KONTROL": Path(roots["KONTROL"]),
            "OZEL": Path(roots["SPECIAL_GENRE_DIR"])}


def _active_export_files(roots: dict, trt: str) -> list[tuple[str, Path]]:
    hits: list[tuple[str, Path]] = []
    for bucket, root in _export_roots(roots).items():
        if not root.exists():
            continue
        for p in root.iterdir():
            if (p.is_file() and _trt_of_name(p.name) == trt
                    and ".promotion." not in p.name and not p.name.endswith(".tmp")):
                hits.append((bucket, p))
    return hits


def _stage_export_copy(src: Path, dst: Path, expected_sha: str) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    staged = dst.with_name(f".{dst.name}.promotion.{uuid.uuid4().hex}.tmp")
    with src.open("rb") as inp, staged.open("xb") as out:
        shutil.copyfileobj(inp, out, length=1024 * 1024)
        out.flush()
        os.fsync(out.fileno())
    if _sha256(staged) != expected_sha:
        staged.unlink(missing_ok=True)
        raise PromoteError("EXPORT-STAGE: kopya hash'i candidate teslim ile uyusmuyor")
    return staged


def _validate_rebased_state(canon: Path, prod_delivery: Path) -> None:
    d = _load_json(canon / "_DURUM.json", "promoted _DURUM")
    if Path(str(d.get("hub") or "")).resolve(strict=False) != canon.resolve(strict=False):
        raise PromoteError(f"REBASE-DRIFT: _DURUM.hub production canonical degil: {d.get('hub')}")
    if Path(str(d.get("teslim") or "")).resolve(strict=False) != prod_delivery.resolve(strict=False):
        raise PromoteError(f"REBASE-DRIFT: _DURUM.teslim production export degil: {d.get('teslim')}")
    pdf = Path(str(d.get("pdf") or "")).resolve(strict=False)
    if not _is_under(pdf, canon) or not pdf.is_file():
        raise PromoteError(f"REBASE-DRIFT: _DURUM.pdf canonical altinda degil/yok: {pdf}")


def _archive_export_files(items: list[dict]) -> None:
    for item in items:
        src, dst = Path(item["src"]), Path(item["archive"])
        if not src.exists():
            if dst.exists():
                continue
            raise PromoteError(f"EXPORT-ARCHIVE: kaynak ve arsiv birlikte yok: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        _replace_backoff(src, dst)


def _assert_no_live_production_writer(roots: dict) -> None:
    p = Path(roots["OUTPUTS_DIR"]) / ".mitas_writer.lock"
    if not p.exists():
        return
    try:
        old = json.loads(p.read_text(encoding="utf-8"))
        pid = int(old.get("pid", -1))
    except Exception:  # noqa: BLE001 — bozuk/bayat writer lock promotion'i sonsuza dek tutmasin
        return
    if _pid_alive(pid):
        raise PromoteError(
            f"PRODUCTION-WRITER-AKTIF: pid={pid} ts={old.get('ts')} — batch biterken promote edin")


def production_writer_lock_path(roots: dict) -> Path:
    # run_manifest.LOCK_PATH ile birebir ayni production koordinasyon noktasi.
    return Path(roots["OUTPUTS_DIR"]) / ".mitas_writer.lock"


# ─────────────────────────── semantic diff ───────────────────────────
def _durum_alanlar(hub: Path) -> dict:
    try:
        d = json.loads((hub / "_DURUM.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    k = d.get("kunye") or {}
    return {
        "yonetmen": d.get("yonetmen") or k.get("yonetmen") or [],
        "cast": d.get("cast") or k.get("cast") or [],
        "title": d.get("title") or "",
        "tur": d.get("tur") or "",
        "karar": d.get("karar"), "ocr_bucket": d.get("ocr_bucket"),
        "extraction_status": d.get("extraction_status"),
    }


def semantic_diff(canonical: Path | None, candidate: Path) -> dict:
    """Alan-diff + HARD-GATE. PDF metin-diff'i v1'de alan-diff'e vekildir (normalize whitelist
    — ligatür/font-order — İP-8 kabul-matrisi işi; GLM notu kabul)."""
    eski = _durum_alanlar(canonical) if canonical else {}
    yeni = _durum_alanlar(candidate)
    fark, hard_block = [], []
    for a in sorted(set(eski) | set(yeni)):
        if eski.get(a) != yeni.get(a):
            fark.append({"alan": a, "eski": eski.get(a), "yeni": yeni.get(a)})
            if a in HARD_GATE_ALANLAR and eski.get(a) and not yeni.get(a):
                hard_block.append(a)
    return {"fark": fark, "hard_block": hard_block}


# ─────────────────────────── rebase ───────────────────────────
def rebase_paths(hub: Path, eski_kok: str, yeni_kok: str,
                 extra_replacements: list[tuple[str, str]] | None = None) -> int:
    """Taşınan hub içindeki mutlak-yolları güncelle — dosya-başına temp+os.replace (GLM)."""
    n = 0
    replacements = [(eski_kok, yeni_kok), *(extra_replacements or [])]
    for ad in REBASE_DOSYALAR:
        p = hub / ad
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8")
        s2 = s
        # Uzun/kapsayici kokler once: run-root/export gibi yollar, run-root'tan once donussun.
        for old, new in sorted(replacements, key=lambda x: len(x[0]), reverse=True):
            s2 = s2.replace(json.dumps(str(old))[1:-1], json.dumps(str(new))[1:-1])
        if s2 != s:
            tmp = p.with_suffix(p.suffix + ".rebase.tmp")
            tmp.write_text(s2, encoding="utf-8")
            os.replace(str(tmp), str(p))
            n += 1
    return n


# ─────────────────────────── journal + promote ───────────────────────────
def _journal_path(db_root: Path, trt: str) -> Path:
    d = db_root / "_promotion_journal"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{trt}.journal.json"


def _jwrite(jp: Path, obj: dict) -> None:
    _atomic_json(jp, obj)


def _recovery_rebase_and_export(jp: Path, j: dict, db_root: Path, roots: dict) -> str:
    canon = Path(j["canonical"])
    cand = Path(j["candidate"])
    if not canon.exists():
        raise PromoteError(f"recovery canonical yok: {canon}")
    run_root = Path(j.get("run_root") or cand.parent.parent)
    j["state"] = "REBASING"; _jwrite(jp, j)
    j["rebased"] = rebase_paths(
        canon, str(cand.parent), str(db_root),
        [(str(run_root / "export"), str(roots["EXPORT_ROOT"])),
         (str(run_root / "muzikal_animasyon_belgesel"), str(roots["SPECIAL_GENRE_DIR"]))])
    staged = Path(j.get("staged_delivery") or "")
    prod = Path(j.get("production_delivery") or "")
    expected = str(j.get("delivery_sha256") or "")
    if not prod.name or not expected:
        raise PromoteError("recovery export journal alanlari eksik")
    _validate_rebased_state(canon, prod)
    j["state"] = "EXPORT_PROMOTING"; _jwrite(jp, j)
    if staged.is_file():
        _replace_backoff(staged, prod)
    if not prod.is_file() or _sha256(prod) != expected:
        raise PromoteError(f"recovery production teslim yok/hash uyusmuyor: {prod}")
    j["state"] = "DONE"; j["recovered"] = _now(); _jwrite(jp, j)
    return f"{j.get('trt')}: promotion + export TAMAMLANDI"


def promote(candidate_hub: Path, *, apply: bool = False, approved_by: str = "",
            allow_remove: list[str] | None = None) -> dict:
    """Candidate hub'ı canonical'a taşı. DRY-RUN default; --apply + insan-onayı şart."""
    # Ortamda MITAS_RUN_ROOT miras kalmis olsa bile canonical daima production'dir.
    roots = mitas_roots.resolve_production()
    db_root = roots["DB_ROOT"]
    candidate_hub = Path(candidate_hub)
    if not (candidate_hub / "_DURUM.json").exists():
        raise PromoteError(f"candidate hub'da _DURUM.json yok: {candidate_hub}")
    m = TRT_RE.search(_nfc(candidate_hub.name))
    if not m:
        raise PromoteError(f"candidate hub adında TRT-ID yok: {candidate_hub.name}")
    trt = m.group(1)

    # TESLİM-TAMLIK KAPISI (Opus akış-incelemesi 2026-07-11): promote bütün-dizin taşımadır —
    # iskelet-aday (yalnız ocr/ içeren LEAN çıktısı gibi) TAM kanoniği DEĞİŞTİRİRSE teslim bozulur.
    # Zorunlu: _DURUM.json + clip.json + ≥1 PDF (hepsi boyut>0). Eksikse promotion RED.
    _eksik = []
    for _gerekli in ("_DURUM.json", "clip.json"):
        _p = candidate_hub / _gerekli
        if not (_p.exists() and _p.stat().st_size > 0):
            _eksik.append(_gerekli)
    _pdfler = [p for p in candidate_hub.rglob("*.pdf") if p.stat().st_size > 0]
    if not _pdfler:
        _eksik.append("teslim-PDF (hiç yok)")
    if _eksik:
        raise PromoteError(
            f"TESLİM-TAMLIK: aday-hub eksik ({', '.join(_eksik)}) — iskelet-aday tam kanoniği "
            f"değiştiremez; önce tam-kapı koşusuyla (mitas_pipeline --from-hub) teslim-seti üretin")

    canonical = resolve_canonical(trt, db_root)
    ctx = _candidate_context(candidate_hub, canonical, trt)
    candidate_hub = ctx["hub"]
    diff = semantic_diff(canonical, candidate_hub)
    plan = {"trt": trt, "canonical": str(canonical) if canonical else None,
            "candidate": str(candidate_hub), "diff": diff, "apply": apply,
            "run_root": str(ctx["run_root"]), "delivery": str(ctx["delivery"]),
            "delivery_sha256": ctx["delivery_sha256"],
            "active_exports": [str(p) for _, p in _active_export_files(roots, trt)]}
    if diff["hard_block"]:
        izinli = set(allow_remove or [])
        bloklu = [a for a in diff["hard_block"] if a not in izinli]
        if bloklu:
            raise PromoteError(
                f"HARD-GATE: {bloklu} alan(lar)ı DOLU→BOŞ — promotion RED. Bilinçli kaldırma için "
                f"--allow-remove {' '.join(bloklu)} + --approved-by <isim> (insan onayı) gerekir.")
        if not approved_by:
            raise PromoteError("--allow-remove insan onayı ister: --approved-by <isim>")
    if not apply:
        return plan

    if not approved_by:
        raise PromoteError("promotion MANUEL: --approved-by <isim> zorunlu (insan kapısı)")
    writer_lock = production_writer_lock_path(roots)
    acquire_lock(writer_lock, "production-writer")
    # Quiesce + kilitler
    tutanlar = quiesce_check(candidate_hub) + (quiesce_check(canonical) if canonical else [])
    if tutanlar:
        release_lock(writer_lock)
        raise PromoteError("HUB-QUIESCE: açık dosyalar var — kapatın:\n  " + "\n  ".join(tutanlar[:10]))
    global_lock = promotion_lock_path(db_root)
    rw = hub_rw_lock_path(db_root, trt)
    try:
        acquire_lock(global_lock, "promotion-global")
    except Exception:
        release_lock(writer_lock)
        raise
    try:
        acquire_lock(rw, "hub-rw")
    except Exception:
        release_lock(global_lock)
        release_lock(writer_lock)
        raise
    jp = _journal_path(db_root, trt)
    staged_export: Path | None = None
    journal_started = False
    try:
        run_id = str(ctx["manifest"].get("run_id") or "")
        arch_root = db_root / "_archive" / trt
        arch_root.mkdir(parents=True, exist_ok=True)
        # %f (mikrosaniye): aynı saniyede iki promote (test/toplu-operasyon) arşiv-adı çakıştırmasın —
        # os.replace mevcut dolu-dizine Windows'ta patlar (testin yakaladığı gerçek risk).
        txn_name = f"{datetime.now():%Y%m%d_%H%M%S_%f}_{run_id or 'norun'}"
        arch_dst = arch_root / txn_name
        export_arch_root = arch_root / "_exports" / txn_name
        export_arch_root.mkdir(parents=True, exist_ok=False)
        canon_dst = db_root / candidate_hub.name if canonical is None else canonical
        prod_delivery = Path(roots["HAZIR"] if ctx["bucket"] == "ONAYLI" else roots["KONTROL"]) / ctx["delivery"].name
        staged_export = _stage_export_copy(ctx["delivery"], prod_delivery, ctx["delivery_sha256"])
        export_moves = []
        for bucket, old in _active_export_files(roots, trt):
            export_moves.append({"bucket": bucket, "src": str(old),
                                 "archive": str(export_arch_root / bucket / old.name)})

        j = {"schema_version": 1, "trt": trt, "ts": _now(), "approved_by": approved_by,
              "candidate": str(candidate_hub), "canonical": str(canon_dst),
              "archive": str(arch_dst) if canonical else None, "diff": diff,
              "run_root": str(ctx["run_root"]), "candidate_delivery": str(ctx["delivery"]),
              "production_delivery": str(prod_delivery), "staged_delivery": str(staged_export),
              "delivery_sha256": ctx["delivery_sha256"], "export_moves": export_moves,
              "archive_exports_root": str(export_arch_root), "state": "INTENT"}
        _jwrite(jp, j)
        journal_started = True
        if canonical:
            j["state"] = "ARCHIVING"; _jwrite(jp, j)
            _replace_backoff(canonical, arch_dst)          # TEK üst-düzey rename (ya hep ya hiç)
        j["state"] = "EXPORT_ARCHIVING"; _jwrite(jp, j)
        _archive_export_files(export_moves)
        j["state"] = "PROMOTING"; _jwrite(jp, j)
        _replace_backoff(candidate_hub, canon_dst)         # TEK üst-düzey rename
        j["state"] = "REBASING"; _jwrite(jp, j)
        j["rebased"] = rebase_paths(
            canon_dst, str(candidate_hub.parent), str(db_root),
            [(str(ctx["run_root"] / "export"), str(roots["EXPORT_ROOT"])),
             (str(ctx["run_root"] / "muzikal_animasyon_belgesel"),
              str(roots["SPECIAL_GENRE_DIR"]))])
        _validate_rebased_state(canon_dst, prod_delivery)
        j["state"] = "EXPORT_PROMOTING"; _jwrite(jp, j)
        _replace_backoff(staged_export, prod_delivery)
        staged_export = None
        if _sha256(prod_delivery) != ctx["delivery_sha256"]:
            raise PromoteError("EXPORT-PROMOTE: production teslim hash dogrulamasi basarisiz")
        j["state"] = "DONE"; j["done_ts"] = _now(); _jwrite(jp, j)
        # arşiv-GC adayı raporu (SİLME YOK)
        surumler = sorted(p.name for p in arch_root.iterdir()
                           if p.is_dir() and not p.name.startswith("_"))
        if len(surumler) > ARCHIVE_MAX_SURUM:
            j["gc_adayi"] = surumler[:-ARCHIVE_MAX_SURUM]
            _jwrite(jp, j)
            sys.stderr.write(f"[arsiv-gc] {trt}: {len(surumler)} sürüm (>{ARCHIVE_MAX_SURUM}) — "
                             f"gc-adayları journal'da; SİLME Çağatay onayı ister\n")
        return j
    finally:
        # INTENT yazilmadan once hata olduysa gecici export'u birakma. Journal sonrasi yarim
        # durumlarda recovery icin staged dosya korunur.
        if staged_export is not None and not journal_started:
            staged_export.unlink(missing_ok=True)
        release_lock(rw)
        release_lock(global_lock)
        release_lock(writer_lock)


def _startup_recovery_unlocked(db_root: Path | None = None) -> list[str]:
    """Yarım journal'ları tara. YALNIZ güvenli tek-rename tamamlaması yapılır; geri kalan her şey
    İNSAN-KİLİDİ (qwen kuralı: script asla silme/geri-taşıma denemez)."""
    roots = mitas_roots.resolve_production()
    db_root = db_root or roots["DB_ROOT"]
    raporlar = []
    jdir = db_root / "_promotion_journal"
    if not jdir.exists():
        return raporlar
    for jp in jdir.glob("*.journal.json"):
        try:
            j = json.loads(jp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            raporlar.append(f"{jp.name}: BOZUK-JOURNAL → İNSAN-KİLİDİ")
            continue
        st = j.get("state")
        if st in (None, "DONE", "HUMAN_LOCK", "ABORTED"):
            continue
        cand, canon, arch = Path(j.get("candidate", "")), Path(j.get("canonical", "")), \
            Path(j.get("archive") or "")
        # v1 journal'lar export alanlari tasimaz: eski guvenli davranisi koru.
        if not j.get("production_delivery"):
            if st == "PROMOTING" and cand.exists() and not canon.exists():
                _replace_backoff(cand, canon)
                j["state"] = "REBASING"; _jwrite(jp, j)
                j["rebased"] = rebase_paths(canon, str(cand.parent), str(db_root))
                j["state"] = "DONE"; j["recovered"] = _now(); _jwrite(jp, j)
                raporlar.append(f"{j.get('trt')}: PROMOTING-yarım TAMAMLANDI (legacy)")
            elif st == "REBASING" and canon.exists():
                j["rebased"] = rebase_paths(canon, str(cand.parent), str(db_root))
                j["state"] = "DONE"; j["recovered"] = _now(); _jwrite(jp, j)
                raporlar.append(f"{j.get('trt')}: REBASING tamamlandı (legacy)")
            else:
                j["state"] = "HUMAN_LOCK"; j["human_lock_reason"] = f"belirsiz yarım-durum ({st})"
                _jwrite(jp, j)
                raporlar.append(f"{j.get('trt')}: {st} belirsiz → İNSAN-KİLİDİ (dokunulmadı)")
            continue
        try:
            if st == "INTENT":
                staged = Path(j.get("staged_delivery") or "")
                if staged.is_file() and ".promotion." in staged.name and staged.suffix == ".tmp":
                    staged.unlink()
                j["state"] = "ABORTED"; j["recovered"] = _now(); _jwrite(jp, j)
                raporlar.append(f"{j.get('trt')}: INTENT iptal edildi (canonical dokunulmadi)")
                continue
            if st == "ARCHIVING":
                if canon.exists() and not arch.exists():
                    arch.parent.mkdir(parents=True, exist_ok=True)
                    _replace_backoff(canon, arch)
                elif not arch.exists():
                    raise PromoteError("ARCHIVING: canonical ve archive birlikte yok")
                st = "EXPORT_ARCHIVING"
                j["state"] = st; _jwrite(jp, j)
            if st == "EXPORT_ARCHIVING":
                _archive_export_files(j.get("export_moves") or [])
                st = "PROMOTING"
                j["state"] = st; _jwrite(jp, j)
            if st == "PROMOTING":
                if cand.exists() and not canon.exists():
                    _replace_backoff(cand, canon)
                elif not canon.exists():
                    raise PromoteError("PROMOTING: candidate ve canonical birlikte yok")
                st = "REBASING"
            if st in ("REBASING", "EXPORT_PROMOTING"):
                raporlar.append(_recovery_rebase_and_export(jp, j, db_root, roots))
            else:
                raise PromoteError(f"desteklenmeyen state: {st}")
        except Exception as exc:  # noqa: BLE001
            j["state"] = "HUMAN_LOCK"; j["human_lock_reason"] = f"belirsiz yarım-durum ({st})"
            j["recovery_error"] = f"{type(exc).__name__}: {exc}"
            _jwrite(jp, j)
            raporlar.append(f"{j.get('trt')}: {st} recovery basarisiz → İNSAN-KİLİDİ: {exc}")
    return raporlar


def startup_recovery(db_root: Path | None = None) -> list[str]:
    """Promotion recovery'yi production writer ve global promotion kilidi altinda kos."""
    roots = mitas_roots.resolve_production()
    actual_db = db_root or roots["DB_ROOT"]
    wl = production_writer_lock_path(roots)
    acquire_lock(wl, "production-writer-recovery")
    gl = promotion_lock_path(actual_db)
    try:
        acquire_lock(gl, "promotion-recovery")
    except Exception:
        release_lock(wl)
        raise
    try:
        return _startup_recovery_unlocked(actual_db)
    finally:
        release_lock(gl)
        release_lock(wl)


def demote(trt: str, *, approved_by: str) -> dict:
    """Son promotion'ı geri al: canonical → _archive/<yeni>, en yeni arşiv-sürümü → canonical,
    REBASING dahil (GLM: demote'ta rebase atlanmaz)."""
    if not approved_by:
        raise PromoteError("demote MANUEL: --approved-by zorunlu")
    roots = mitas_roots.resolve_production()
    db_root = roots["DB_ROOT"]
    canonical = resolve_canonical(trt, db_root)
    if canonical is None:
        raise PromoteError(f"demote: canonical hub yok: {trt}")
    arch_root = db_root / "_archive" / trt
    surumler = sorted((p for p in arch_root.iterdir()
                       if p.is_dir() and not p.name.startswith("_")), reverse=True) \
        if arch_root.exists() else []
    if not surumler:
        raise PromoteError(f"demote: {trt} için arşiv-sürümü yok")
    geri = surumler[0]
    restore_exports = arch_root / "_exports" / geri.name
    if not restore_exports.is_dir():
        raise PromoteError(
            f"demote export arsivi yok: {restore_exports} — hub-only geri alma state drift uretir")
    writer_lock = production_writer_lock_path(roots)
    acquire_lock(writer_lock, "production-writer")
    global_lock = promotion_lock_path(db_root)
    rw = hub_rw_lock_path(db_root, trt)
    try:
        acquire_lock(global_lock, "promotion-global")
    except Exception:
        release_lock(writer_lock)
        raise
    try:
        acquire_lock(rw, "hub-rw")
    except Exception:
        release_lock(global_lock)
        release_lock(writer_lock)
        raise
    try:
        jp = _journal_path(db_root, trt)
        txn_name = f"{datetime.now():%Y%m%d_%H%M%S_%f}_demoted"
        yeni_arch = arch_root / txn_name
        yeni_export_arch = arch_root / "_exports" / txn_name
        yeni_export_arch.mkdir(parents=True, exist_ok=False)
        current_export_moves = [
            {"bucket": bucket, "src": str(p),
             "archive": str(yeni_export_arch / bucket / p.name)}
            for bucket, p in _active_export_files(roots, trt)
        ]
        restore_moves = []
        export_roots = _export_roots(roots)
        for p in restore_exports.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(restore_exports)
            if len(rel.parts) < 2 or rel.parts[0] not in export_roots:
                raise PromoteError(f"demote export arsivi bozuk yol: {p}")
            restore_moves.append({"src": str(p), "dst": str(export_roots[rel.parts[0]] / p.name)})
        j = {"schema_version": 1, "trt": trt, "ts": _now(), "approved_by": approved_by,
              "demote_from": str(canonical) if canonical else None, "demote_to": str(geri),
              "canonical": str(canonical), "archive": str(yeni_arch),
              "current_export_moves": current_export_moves, "restore_export_moves": restore_moves,
              "state": "DEMOTE_ARCHIVING"}
        _jwrite(jp, j)
        canon_name = canonical.name if canonical else geri.name
        _replace_backoff(canonical, yeni_arch)
        j["demoted_canonical_to"] = str(yeni_arch)
        j["state"] = "DEMOTE_EXPORT_ARCHIVING"; _jwrite(jp, j)
        _archive_export_files(current_export_moves)
        j["state"] = "DEMOTE_PROMOTING"; _jwrite(jp, j)
        hedef = db_root / canon_name
        _replace_backoff(geri, hedef)
        j["state"] = "REBASING"; _jwrite(jp, j)
        j["rebased"] = rebase_paths(hedef, str(arch_root), str(db_root))
        j["state"] = "DEMOTE_EXPORT_RESTORING"; _jwrite(jp, j)
        for item in restore_moves:
            src, dst = Path(item["src"]), Path(item["dst"])
            dst.parent.mkdir(parents=True, exist_ok=True)
            _replace_backoff(src, dst)
        j["state"] = "DONE"; j["done_ts"] = _now(); _jwrite(jp, j)
        return j
    finally:
        release_lock(rw)
        release_lock(global_lock)
        release_lock(writer_lock)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--candidate", help="candidate hub dizini (promote)")
    ap.add_argument("--demote", metavar="TRT", help="son promotion'ı geri al")
    ap.add_argument("--recover", action="store_true", help="startup-recovery taraması")
    ap.add_argument("--apply", action="store_true", help="dry-run değil GERÇEK uygula")
    ap.add_argument("--approved-by", default="", help="insan onayı (apply/demote için zorunlu)")
    ap.add_argument("--allow-remove", nargs="*", default=None,
                    help="HARD-GATE alanlarını bilinçli kaldırma izni (insan onaylı)")
    a = ap.parse_args()
    try:
        if a.recover:
            for r in startup_recovery():
                print(r)
        elif a.demote:
            print(json.dumps(demote(a.demote, approved_by=a.approved_by), ensure_ascii=False, indent=1))
        elif a.candidate:
            print(json.dumps(promote(Path(a.candidate), apply=a.apply, approved_by=a.approved_by,
                                     allow_remove=a.allow_remove), ensure_ascii=False, indent=1))
        else:
            ap.print_help()
    except PromoteError as e:
        print(f"RED: {e}")
        sys.exit(2)
