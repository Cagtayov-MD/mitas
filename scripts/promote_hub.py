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
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mitas_roots  # noqa: E402

TRT_RE = re.compile(r"(\d{4}-\d{3,4}-\d-\d{3,4}-\d{2}-\d)")
HARD_GATE_ALANLAR = ("yonetmen", "cast", "title", "tur")   # DOLU→BOŞ = HARD-BLOCK
REBASE_DOSYALAR = ("_DURUM.json", "clip.json", "run_manifest.json",
                   "karar.pipeline.json", "karar.view.json")
ARCHIVE_MAX_SURUM = 3          # aşımı = gc-adayı raporu (SİLME YOK — Çağatay onayı gerekir)


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


# ─────────────────────────── resolver ───────────────────────────
def resolve_canonical(trt: str, db_root: Path) -> Path | None:
    """0=NOT_FOUND(None) / 1=OK / >1=AMBIGUOUS_HUB hard-fail. NFC-normalize taramalı (GLM)."""
    trt = _nfc(trt).strip()
    hits = [d for d in db_root.iterdir()
            if d.is_dir() and trt in _nfc(d.name) and (d / "_DURUM.json").exists()]
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
    if lock_path.exists():
        try:
            old = json.loads(lock_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            old = {}
        pid = int(old.get("pid", -1))
        ad = _proc_name(pid)
        # PID-reuse zehirlenmesi (GLM): pid canlı AMA kayıtlı süreç-adıyla uyuşmuyorsa bayat say.
        if ad is not None and old.get("proc") and ad != old.get("proc"):
            sys.stderr.write(f"[kilit] PID-reuse: {pid} artık {ad} ({old.get('proc')} değil) — bayat devralındı\n")
        elif ad is not None or _pid_alive(pid):
            raise PromoteError(f"{kind}-kilidi dolu: pid={pid} proc={old.get('proc')} ts={old.get('ts')}")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(
        {"pid": os.getpid(), "proc": _proc_name(os.getpid()) or "python", "ts": _now(),
         "kind": kind}), encoding="utf-8")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except Exception:  # noqa: BLE001
        return True
    return True


def release_lock(lock_path: Path) -> None:
    try:
        if lock_path.exists() and json.loads(lock_path.read_text(encoding="utf-8")).get("pid") == os.getpid():
            lock_path.unlink()
    except Exception:  # noqa: BLE001
        pass


def hub_rw_lock_path(db_root: Path, trt: str) -> Path:
    return db_root / f".hub.{trt}.lock"


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
def rebase_paths(hub: Path, eski_kok: str, yeni_kok: str) -> int:
    """Taşınan hub içindeki mutlak-yolları güncelle — dosya-başına temp+os.replace (GLM)."""
    n = 0
    for ad in REBASE_DOSYALAR:
        p = hub / ad
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8")
        s2 = s.replace(json.dumps(eski_kok)[1:-1], json.dumps(yeni_kok)[1:-1])
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


def promote(candidate_hub: Path, *, apply: bool = False, approved_by: str = "",
            allow_remove: list[str] | None = None) -> dict:
    """Candidate hub'ı canonical'a taşı. DRY-RUN default; --apply + insan-onayı şart."""
    roots = mitas_roots.resolve(None)          # canonical HEP üretim kökü
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
    diff = semantic_diff(canonical, candidate_hub)
    plan = {"trt": trt, "canonical": str(canonical) if canonical else None,
            "candidate": str(candidate_hub), "diff": diff, "apply": apply}
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
    # Quiesce + kilitler
    tutanlar = quiesce_check(candidate_hub) + (quiesce_check(canonical) if canonical else [])
    if tutanlar:
        raise PromoteError("HUB-QUIESCE: açık dosyalar var — kapatın:\n  " + "\n  ".join(tutanlar[:10]))
    rw = hub_rw_lock_path(db_root, trt)
    acquire_lock(rw, "hub-rw")
    jp = _journal_path(db_root, trt)
    try:
        run_id = ""
        try:
            run_id = json.loads((candidate_hub / "run_manifest.json").read_text(encoding="utf-8")).get("run_id", "")
        except Exception:  # noqa: BLE001
            pass
        arch_root = db_root / "_archive" / trt
        arch_root.mkdir(parents=True, exist_ok=True)
        # %f (mikrosaniye): aynı saniyede iki promote (test/toplu-operasyon) arşiv-adı çakıştırmasın —
        # os.replace mevcut dolu-dizine Windows'ta patlar (testin yakaladığı gerçek risk).
        arch_dst = arch_root / f"{datetime.now():%Y%m%d_%H%M%S_%f}_{run_id or 'norun'}"
        canon_dst = db_root / candidate_hub.name if canonical is None else canonical

        j = {"schema_version": 1, "trt": trt, "ts": _now(), "approved_by": approved_by,
             "candidate": str(candidate_hub), "canonical": str(canon_dst),
             "archive": str(arch_dst) if canonical else None, "diff": diff,
             "state": "INTENT"}
        _jwrite(jp, j)
        if canonical:
            j["state"] = "ARCHIVING"; _jwrite(jp, j)
            _replace_backoff(canonical, arch_dst)          # TEK üst-düzey rename (ya hep ya hiç)
        j["state"] = "PROMOTING"; _jwrite(jp, j)
        _replace_backoff(candidate_hub, canon_dst)         # TEK üst-düzey rename
        j["state"] = "REBASING"; _jwrite(jp, j)
        j["rebased"] = rebase_paths(canon_dst, str(candidate_hub.parent), str(db_root))
        j["state"] = "DONE"; j["done_ts"] = _now(); _jwrite(jp, j)
        # arşiv-GC adayı raporu (SİLME YOK)
        surumler = sorted(p.name for p in arch_root.iterdir() if p.is_dir())
        if len(surumler) > ARCHIVE_MAX_SURUM:
            j["gc_adayi"] = surumler[:-ARCHIVE_MAX_SURUM]
            _jwrite(jp, j)
            sys.stderr.write(f"[arsiv-gc] {trt}: {len(surumler)} sürüm (>{ARCHIVE_MAX_SURUM}) — "
                             f"gc-adayları journal'da; SİLME Çağatay onayı ister\n")
        return j
    finally:
        release_lock(rw)


def startup_recovery(db_root: Path | None = None) -> list[str]:
    """Yarım journal'ları tara. YALNIZ güvenli tek-rename tamamlaması yapılır; geri kalan her şey
    İNSAN-KİLİDİ (qwen kuralı: script asla silme/geri-taşıma denemez)."""
    db_root = db_root or mitas_roots.resolve(None)["DB_ROOT"]
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
        if st in (None, "DONE", "INTENT"):
            continue
        cand, canon, arch = Path(j.get("candidate", "")), Path(j.get("canonical", "")), \
            Path(j.get("archive") or "")
        if st == "PROMOTING" and cand.exists() and not canon.exists():
            # arşivleme bitti, taşıma yarım → tamamlaması GÜVENLİ tek-rename
            _replace_backoff(cand, canon)
            j["state"] = "REBASING"; _jwrite(jp, j)
            j["rebased"] = rebase_paths(canon, str(cand.parent), str(db_root))
            j["state"] = "DONE"; j["recovered"] = _now(); _jwrite(jp, j)
            raporlar.append(f"{j.get('trt')}: PROMOTING-yarım TAMAMLANDI")
        elif st == "REBASING" and canon.exists():
            j["rebased"] = rebase_paths(canon, str(cand.parent), str(db_root))
            j["state"] = "DONE"; j["recovered"] = _now(); _jwrite(jp, j)
            raporlar.append(f"{j.get('trt')}: REBASING tamamlandı")
        else:
            j["state"] = "HUMAN_LOCK"; j["human_lock_reason"] = f"belirsiz yarım-durum ({st})"
            _jwrite(jp, j)
            raporlar.append(f"{j.get('trt')}: {st} belirsiz → İNSAN-KİLİDİ (dokunulmadı)")
    return raporlar


def demote(trt: str, *, approved_by: str) -> dict:
    """Son promotion'ı geri al: canonical → _archive/<yeni>, en yeni arşiv-sürümü → canonical,
    REBASING dahil (GLM: demote'ta rebase atlanmaz)."""
    if not approved_by:
        raise PromoteError("demote MANUEL: --approved-by zorunlu")
    db_root = mitas_roots.resolve(None)["DB_ROOT"]
    canonical = resolve_canonical(trt, db_root)
    arch_root = db_root / "_archive" / trt
    surumler = sorted((p for p in arch_root.iterdir() if p.is_dir()), reverse=True) \
        if arch_root.exists() else []
    if not surumler:
        raise PromoteError(f"demote: {trt} için arşiv-sürümü yok")
    geri = surumler[0]
    rw = hub_rw_lock_path(db_root, trt)
    acquire_lock(rw, "hub-rw")
    try:
        jp = _journal_path(db_root, trt)
        j = {"schema_version": 1, "trt": trt, "ts": _now(), "approved_by": approved_by,
             "demote_from": str(canonical) if canonical else None, "demote_to": str(geri),
             "state": "DEMOTE_ARCHIVING"}
        _jwrite(jp, j)
        canon_name = canonical.name if canonical else geri.name
        if canonical:
            yeni_arch = arch_root / f"{datetime.now():%Y%m%d_%H%M%S_%f}_demoted"
            _replace_backoff(canonical, yeni_arch)
            j["demoted_canonical_to"] = str(yeni_arch)
        j["state"] = "DEMOTE_PROMOTING"; _jwrite(jp, j)
        hedef = db_root / canon_name
        _replace_backoff(geri, hedef)
        j["state"] = "REBASING"; _jwrite(jp, j)
        j["rebased"] = rebase_paths(hedef, str(arch_root), str(db_root))
        j["state"] = "DONE"; j["done_ts"] = _now(); _jwrite(jp, j)
        return j
    finally:
        release_lock(rw)


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
