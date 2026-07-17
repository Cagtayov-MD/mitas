#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MITAS Database konsolidasyon — çirkin adlı klasörleri DATABASE düzenine getirir.

  - Klasör adı  : '<BAŞLIK> <TRT>'  (ad önce; Türkçe/apostrof/boşluk korunur)
  - Kök dosyalar : '<TRT> <BAŞLIK>.pdf' + 'afis.jpg' + '<TRT> <BAŞLIK>.txt' (DATABASE dosya kuralı)
  - İç yapı (asr/audio/frames/ocr/pdf) DOKUNULMAZ.
  - HİÇBİR ŞEY SİLİNMEZ (yalnız os.rename + copy2). Aynı disk → atomik.
  - In-flight (canlı işlenen) klasörlere DOKUNMAZ.

Varsayılan --dry-run. Kullanım:
  python scripts/consolidate_database.py --dry-run
  python scripts/consolidate_database.py --apply [--stale-minutes 20] [--include-partial]
  python scripts/consolidate_database.py --apply --only-trt 1969-0023-1-0000-90-1     # tek klasör smoke
  python scripts/consolidate_database.py --reconcile                                  # dağınık PDF raporu
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Linux geçişi 2026-07-17: env-aware kök (elle koşuşta betik konumundan türet).
PROJECT_ROOT = Path(os.environ.get("MITAS_PROJECT_ROOT") or Path(__file__).resolve().parents[1])
DB_ROOT = PROJECT_ROOT / "Database"
OUT_ROOT = PROJECT_ROOT / "Mitas Output"
EVENTS_PATH = PROJECT_ROOT / "outputs" / "system_events.jsonl"
TRT_RE = re.compile(r"(\d{4})-(\d{3,4})-(\d)-(\d{3,4})-(\d{2})-(\d)")

# --- adlandırma (mitas_pipeline.py ile birebir aynı; bağımsız kopya) ---
_ILLEGAL_WIN = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_TRAIL = " . \t"


def _ad_clean(s: str) -> str:
    return re.sub(r"\s{2,}", " ", _ILLEGAL_WIN.sub(" ", (s or "").strip())).strip(_TRAIL)


def folder_name(title: str, trt: str, fallback_stem: str = "") -> str:
    t = _ad_clean(title)
    tr = (trt or "").strip()
    if t and tr:
        name = f"{t} {tr}"
    elif t:
        name = t
    elif tr:
        name = tr
    else:
        name = _ad_clean(fallback_stem) or "media"
    return _ad_clean(name)[:180].strip(_TRAIL) or "media"


def file_base(trt: str, title: str) -> str:
    t = _ad_clean(title)
    tr = (trt or "").strip()
    name = f"{tr} {t}".strip() if (tr or t) else "media"
    return _ad_clean(name)[:180].strip(_TRAIL) or "media"


def md_to_readable(md: str) -> str:
    out = []
    for raw in (md or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            out.append("")
        elif line.startswith("# "):
            parts = [p.strip() for p in line[2:].split("•")]
            title = parts[-1] if parts else line[2:].strip()
            out += ["=" * 64, f"  {title}", "=" * 64]
        elif line.startswith("## "):
            out += ["", f"--- {line[3:].strip()} ---"]
        elif line.startswith("- "):
            out.append(f"  {line[2:].strip()}")
        else:
            out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out).strip() + "\n")


# --- insan-okunur _teknik.txt + per-film _log.jsonl (mitas_pipeline ile birebir) ---
def _fmt_mb(b) -> str:
    try:
        return f"{int(b) / (1024 * 1024):.1f} MB"
    except Exception:
        return "—"


def _md_section(md: str, header: str) -> list:
    out, grab = [], False
    for ln in (md or "").splitlines():
        s = ln.strip()
        if s.startswith("## "):
            grab = (s[3:].strip().lower() == header.lower())
            continue
        if grab and s.startswith("- "):
            out.append(s[2:].strip())
    return out


def build_teknik(clipj: dict, durum: dict, teslim_md: str) -> str:
    c, d = (clipj or {}), (durum or {})
    title = c.get("title") or d.get("title") or ""
    trt = c.get("trt_id") or d.get("trt_id") or ""
    bar, sub = "=" * 65, "-" * 65
    L = [bar, "  BLOK 1 — VİDEO / İŞLEM BİLGİLERİ", bar, ""]
    L.append(f"  Dosya        : {c.get('filename') or os.path.basename(d.get('video', '') or '')}")
    L.append(f"  Film/Program : {title}")
    L.append(f"  TRT Kimlik   : {trt}")
    if c.get("bolum"):
        L.append(f"  Bölüm        : {c.get('bolum')}")
    L.append(f"  Süre         : {d.get('duration', '—')}")
    L.append(f"  Çözünürlük   : {d.get('resolution', '—')} @ {d.get('fps', '—')} FPS")
    L.append(f"  Boyut        : {_fmt_mb(c.get('size_bytes'))}")
    L.append(f"  Profil       : {d.get('profile') or c.get('profile') or '—'}")
    L.append(f"  OCR          : {d.get('ocr_bucket', '—')} ({d.get('ocr_lines', '—')} satır)")
    seg, ch = d.get("asr_segments"), d.get("transcript_chars")
    L.append(f"  ASR          : {d.get('asr_status', '—')}" + (f" ({seg} segment, {ch} karakter)" if seg else ""))
    L += ["", sub, "  KARAR", sub, ""]
    L.append(f"  Durum        : {(d.get('karar') or '—').upper()}")
    nedenler = d.get("neden") or []
    L += ([f"    - {n}" for n in nedenler] if nedenler else ["    (tüm bloklar temiz)"])
    tm = d.get("timings_sec") or {}
    if tm:
        L += ["", sub, "  PIPELINE (saniye)", sub, ""]
        order = ["coz", "ocr", "video_kunye", "credit_text", "credit_vl", "name_verify", "asr", "pdf", "toplam"]
        keys = [k for k in order if k in tm] + [k for k in tm if k not in order]
        L += [f"  {k:<14}: {tm[k]}" for k in keys]
    cast = _md_section(teslim_md, "Oyuncular")
    L += ["", bar, "  BLOK 2 — OYUNCULAR", bar, ""]
    L += ([f"  {x}" for x in cast] if cast else ["  (yok)"])
    crew = _md_section(teslim_md, "Yapım Ekibi")
    L += ["", bar, "  BLOK 3 — YAPIM EKİBİ", bar, ""]
    L += ([f"  {x}" for x in crew] if crew else ["  (yok)"])
    return "\n".join(L) + "\n"


def extract_clip_events(media_id: str) -> list:
    evs = []
    if not media_id:
        return evs
    for p in (EVENTS_PATH, EVENTS_PATH.with_suffix(".1.jsonl")):
        if not p.exists():
            continue
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                if media_id in line:
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    if o.get("media_id") == media_id:
                        evs.append(o)
        except Exception:
            continue
    evs.sort(key=lambda e: e.get("ts", ""))
    return evs


# --- metadata çözümleme ---
def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def resolve_meta(d: Path):
    """(title, trt, source). clip.json > _DURUM.json > kunye_teslim.md + klasör adı. Yoksa (None, None, None)."""
    cj = _read_json(d / "clip.json")
    if cj and (cj.get("title") or cj.get("trt_id")):
        return cj.get("title"), cj.get("trt_id"), "clip.json"
    du = _read_json(d / "_DURUM.json")
    if du and (du.get("title") or du.get("trt_id")):
        return du.get("title"), du.get("trt_id"), "_DURUM.json"
    title = trt = None
    md = d / "pdf" / "kunye_teslim.md"
    if md.exists():
        try:
            txt = md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            txt = ""
        first = (txt.splitlines() or [""])[0]
        if first.startswith("# "):
            parts = [p.strip() for p in first[2:].split("•")]
            title = parts[-1] if parts else None
        m = TRT_RE.search(txt)
        if m:
            trt = "-".join(m.groups())
    if not trt:
        m = TRT_RE.search(d.name)
        if m:
            trt = "-".join(m.groups())
    if title or trt:
        return title, trt, "md/foldername"
    return None, None, None


# --- in-flight koruması ---
def running_trts() -> set:
    """Çalışan python süreçlerinin cmdline'larında geçen TRT id'leri (canlı klasörleri korumak için)."""
    trts = set()
    try:
        ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" "
              "| ForEach-Object { $_.CommandLine }")
        raw = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, timeout=40).stdout
        # latin-1 asla patlamaz; TRT id'leri ASCII rakam → güvenle çıkar
        out = raw.decode("latin-1", "ignore") if isinstance(raw, (bytes, bytearray)) else (raw or "")
    except Exception:
        out = ""
    for m in TRT_RE.finditer(out or ""):
        trts.add("-".join(m.groups()))
    return trts


def is_inflight(d: Path, live_trts: set, trt: str, stale_sec: int):
    if trt and trt in live_trts:
        return True, "live-process"
    now = time.time()
    newest = d.stat().st_mtime
    cj = d / "clip.json"
    if cj.exists():
        newest = max(newest, cj.stat().st_mtime)
    if (now - newest) < stale_sec:
        return True, "fresh-mtime"
    return False, ""


# --- köke teslimat yüzeyle (mitas_pipeline.surface_deliverables ile aynı mantık) ---
def surface(d: Path, trt: str, title: str) -> dict:
    base = file_base(trt, title)
    pdfdir = d / "pdf"
    got = {"pdf": False, "afis": False, "txt": False}
    pdf_src = None
    for cand in ("kunye_fixed.pdf", "kunye.pdf"):
        p = pdfdir / cand
        if p.exists():
            pdf_src = p
            break
    if pdf_src:
        shutil.copy2(pdf_src, d / f"{base}.pdf")
        got["pdf"] = True
    afis = pdfdir / "afis.jpg"
    if afis.exists():
        try:
            if afis.resolve() != (d / "afis.jpg").resolve():
                shutil.copy2(afis, d / "afis.jpg")
        except Exception:
            shutil.copy2(afis, d / "afis.jpg")
        got["afis"] = True
    md = pdfdir / "kunye_teslim.md"
    md_txt = ""
    if md.exists():
        md_txt = md.read_text(encoding="utf-8", errors="replace")
        (d / f"{base}.txt").write_text(md_to_readable(md_txt), encoding="utf-8")
        got["txt"] = True
    # insan-okunur _teknik.txt + per-film _log.jsonl (DATABASE düzeni — herşey tek klasörde)
    clipj = _read_json(d / "clip.json") or {}
    durum = _read_json(d / "_DURUM.json") or {}
    (d / f"{base}_teknik.txt").write_text(build_teknik(clipj, durum, md_txt), encoding="utf-8")
    got["teknik"] = True
    media_id = clipj.get("media_id") or durum.get("clip_id") or ""
    evs = extract_clip_events(media_id)
    if evs:
        with (d / "_log.jsonl").open("w", encoding="utf-8") as h:
            for e in evs:
                h.write(json.dumps(e, ensure_ascii=False) + "\n")
        got["log"] = len(evs)
    return got


# --- dağınık PDF mutabakatı (REPORT-only) ---
def reconcile() -> dict:
    cols = [OUT_ROOT / "102_HAZIR", OUT_ROOT / "BUGUN_PDF"]
    if (OUT_ROOT / "export").exists():
        cols += [p for p in (OUT_ROOT / "export").iterdir() if p.is_dir()]
    cols += sorted(OUT_ROOT.glob("103_TESLIM_*"))
    tdir = PROJECT_ROOT / "teslimat" / "export"
    if tdir.exists():
        cols += [tdir]
    db_trts = set()
    for d in DB_ROOT.iterdir():
        if d.is_dir():
            m = TRT_RE.search(d.name)
            if m:
                db_trts.add("-".join(m.groups()))
    pdfs_seen = covered = 0
    orphans = []
    for c in cols:
        if not (c.exists() and c.is_dir()):
            continue
        for pdf in c.rglob("*.pdf"):
            pdfs_seen += 1
            m = TRT_RE.search(pdf.name)
            if not m:
                continue
            trt = "-".join(m.groups())
            if trt in db_trts:
                covered += 1
            else:
                orphans.append({"pdf": str(pdf), "trt": trt})
    return {"collections": [str(c) for c in cols if c.exists()],
            "pdfs_seen": pdfs_seen, "covered": covered,
            "orphan_count": len(orphans), "orphans": orphans}


def main() -> int:
    ap = argparse.ArgumentParser(description="MITAS Database → DATABASE düzeni konsolidasyon")
    ap.add_argument("--apply", action="store_true", help="gerçekten uygula (yoksa dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="hiçbir şeyi değiştirme (varsayılan)")
    ap.add_argument("--stale-minutes", type=int, default=20, help="bu kadar dk içinde değişen klasör = in-flight, atla")
    ap.add_argument("--include-partial", action="store_true", help="_DURUM.json'suz klasörleri de işle")
    ap.add_argument("--limit", type=int, default=0, help="en çok N klasör işle (0=sınırsız)")
    ap.add_argument("--only-trt", default="", help="yalnız bu TRT'li klasörü işle (smoke test)")
    ap.add_argument("--reconcile", action="store_true", help="dağınık PDF mutabakat raporunu da çıkar")
    args = ap.parse_args()
    try:                                  # konsol cp1254 → utf-8 (Türkçe + ⚠ basılabilsin)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    apply = args.apply and not args.dry_run
    mode = "APPLY" if apply else "DRY-RUN"
    if not DB_ROOT.exists():
        print(f"HATA: {DB_ROOT} yok"); return 2

    live = running_trts()
    stale_sec = args.stale_minutes * 60
    dirs = sorted([p for p in DB_ROOT.iterdir() if p.is_dir()], key=lambda p: p.name.lower())

    res = {
        "mode": mode, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "db_root": str(DB_ROOT), "total_folders": len(dirs),
        "stale_minutes": args.stale_minutes, "live_trts": sorted(live),
        "renamed": [], "already_clean": 0, "skipped": [], "unresolved": [], "same_trt_pairs": [],
    }
    seen_trt = {}
    processed = 0
    for d in dirs:
        if args.limit and processed >= args.limit:
            break
        title, trt, source = resolve_meta(d)
        if args.only_trt and trt != args.only_trt:
            continue
        processed += 1
        if not (title or trt):
            res["unresolved"].append(d.name)
            continue
        if trt:
            if trt in seen_trt and seen_trt[trt] != d.name:
                res["same_trt_pairs"].append([seen_trt[trt], d.name])
            else:
                seen_trt.setdefault(trt, d.name)
        target = folder_name(title, trt, d.name)
        dest = DB_ROOT / target
        n = 2
        while dest.exists() and dest != d:
            dest = DB_ROOT / f"{target} {n}"
            n += 1
        if dest == d:                         # zaten temiz (suffix dahil) → sadece log/teknik yüzeyle
            res["already_clean"] += 1
            if apply:
                inflight, _why = is_inflight(d, live, trt, stale_sec)
                if not inflight:                  # canlı klasörü pipeline kendisi yazar
                    try:
                        surface(d, trt, title)
                    except Exception as e:  # noqa: BLE001
                        res.setdefault("surface_errors", []).append({"folder": d.name, "error": str(e)})
            continue
        durum = (d / "_DURUM.json").exists()
        if not durum and not args.include_partial:
            res["skipped"].append({"folder": d.name, "reason": "no-durum"})
            continue
        inflight, why = is_inflight(d, live, trt, stale_sec)
        if inflight:
            res["skipped"].append({"folder": d.name, "reason": why})
            continue
        rec = {"old": d.name, "new": dest.name, "trt": trt, "title": title, "source": source}
        if apply:
            try:
                os.rename(str(d), str(dest))
            except Exception as e:  # noqa: BLE001
                res["skipped"].append({"folder": d.name, "reason": f"rename-fail: {e}"})
                continue
            try:                                  # yüzeyleme best-effort; rename zaten oldu
                rec["surfaced"] = surface(dest, trt, title)
            except Exception as e:  # noqa: BLE001
                rec["surface_error"] = str(e)
        res["renamed"].append(rec)

    if args.reconcile:
        res["reconcile"] = reconcile()

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    mani = OUT_ROOT / f"_consolidate_manifest_{stamp}.json"
    mani.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    # özet
    print(f"[{mode}]  toplam={res['total_folders']}  işlenen={processed}")
    print(f"  yeniden-adlandır : {len(res['renamed'])}")
    print(f"  zaten-temiz       : {res['already_clean']}")
    print(f"  atlanan           : {len(res['skipped'])}  " +
          ("(in-flight/no-durum)" if res["skipped"] else ""))
    print(f"  çözülemeyen       : {len(res['unresolved'])}")
    if res["same_trt_pairs"]:
        print(f"  ⚠ aynı-TRT çifti  : {len(res['same_trt_pairs'])} (manuel incele)")
    if args.reconcile:
        rc = res["reconcile"]
        print(f"  mutabakat: {rc['pdfs_seen']} PDF, {rc['covered']} kapsanan, {rc['orphan_count']} ÖKSÜZ")
    for r in res["renamed"][:12]:
        print(f"    {r['old']}\n      → {r['new']}")
    if len(res["renamed"]) > 12:
        print(f"    … +{len(res['renamed']) - 12} daha (manifest'te)")
    print(f"\nmanifest: {mani}")
    if not apply:
        print("(DRY-RUN — hiçbir şey değişmedi. Uygulamak için --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
