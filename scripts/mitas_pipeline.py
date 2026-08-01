# -*- coding: utf-8 -*-
"""MITAS Film/Dizi pipeline orkestratoru (stdlib; global python ile kosar).

video -> Database/<clip>/ hub (clip.json + source + frames + ocr + asr + pdf)
      -> OCR kunye (venvs/ocr) + ASR transcript (venvs/asr) + PDF (global python)
      -> Hazir/Kontrol yonlendirme + Mitas Output master log
Olaylar outputs/system_events.jsonl'e (UI /api/events) log_event formatinda yazilir.

Her blok try/except: bir blok cokerse pipeline durmaz, olay loglanir, modul
'failed/partial' isaretlenir ve teslim Kontrol'e yonlenir. Commit YOK.

Kullanim:
  python scripts/mitas_pipeline.py --video "E:\\MITAS\\testklipler\\3.mp4" --profile film
  (test icin hizli:) --asr-max-seconds 120 --ocr-head 60 --ocr-tail 120 --fps 1.5
"""
from __future__ import annotations
import argparse, json, subprocess, shutil, time, re, hashlib, unicodedata, os, sys, functools
import urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import debug_trace as dbg

# Windows: alt-sürecin stdout/stderr codec'i ANSI (TR Windows'ta cp1254) olur. ensure_ascii=False
# basılan son JSON'daki cp1254-DIŞI karakter (ör. isim-QC nedenindeki '→' U+2192, ya da yabancı
# film özetindeki œ/ø) print()'i UnicodeEncodeError ile ÇÖKERTİR → film 'failed' görünür (künye
# KONTROL'e düşmüş olsa bile flow-worker JSON satırını alamaz). utf-8'e sabitle: çökmeyi önler +
# flow-worker'ın okuduğu mesajdaki � bozulmasını da giderir (parent zaten utf-8 decode ediyor).
for _std in (sys.stdout, sys.stderr):
    try:
        _std.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — reconfigure yoksa (eski py)/pipe değilse sessiz geç
        pass

# İP-5 (2026-07-11, plan rev.4): kökler artık mitas_roots.resolve()'den — MITAS_RUN_ROOT boşsa
# üretim yolları BYTE-AYNI; doluysa (candidate modu) TÜM yazma-yüzeyleri run-root altına gider
# (izolasyon; --run-root CLI aşağıda argparse'ta env'i set eder, _rebind_roots yeniden bağlar).
# SABİT KURAL (Çağatay 2026-06-08): tüm çıktı export/ altında → ONAYLI | KONTROL. Başka teslim yok.
# ÖZEL-TÜR (Çağatay 2026-06-21): müzikal/belgesel/animasyon 'muzikal_animasyon_belgesel/' altında.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mitas_roots as _roots  # noqa: E402

PROJECT_ROOT = _roots.PROJECT_ROOT
DB_ROOT = OUT_ROOT = EXPORT_ROOT = HAZIR = KONTROL = None  # _rebind_roots doldurur
SPECIAL_GENRE_DIR = EVENTS_PATH = MASTER_MD = MASTER_JSONL = None


def _rebind_roots(run_root=None):
    """Modül-global kökleri (yeniden) bağla. Candidate modunda alt-süreç env-köprüsünü de kurar."""
    global DB_ROOT, OUT_ROOT, EXPORT_ROOT, HAZIR, KONTROL
    global SPECIAL_GENRE_DIR, EVENTS_PATH, MASTER_MD, MASTER_JSONL
    r = _roots.resolve(run_root)
    DB_ROOT, OUT_ROOT, EXPORT_ROOT = r["DB_ROOT"], r["OUT_ROOT"], r["EXPORT_ROOT"]
    HAZIR, KONTROL = r["HAZIR"], r["KONTROL"]
    SPECIAL_GENRE_DIR, EVENTS_PATH = r["SPECIAL_GENRE_DIR"], r["EVENTS_PATH"]
    MASTER_MD, MASTER_JSONL = r["MASTER_MD"], r["MASTER_JSONL"]
    _roots.export_child_env(r)
    return r


_rebind_roots()
# Linux geçişi 2026-07-16: araç/yorumlayıcı yolları env+platform-farkında (Windows'ta env yoksa birebir eski).
FFMPEG = Path(os.environ.get("MITAS_FFMPEG") or (
    PROJECT_ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"))
FFPROBE = Path(os.environ.get("MITAS_FFPROBE") or (
    PROJECT_ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffprobe.exe"))


def _venv_python(_ad):
    if os.name == "nt":
        return PROJECT_ROOT / "venvs" / _ad / "Scripts" / "python.exe"
    return PROJECT_ROOT / "venvs" / _ad / "bin" / "python"


PY_OCR = _venv_python("ocr")
PY_ASR = _venv_python("asr")
PY_PDF = Path(os.environ.get("MITAS_PDF_PYTHON")
              or r"C:\Users\TRT03\AppData\Local\Programs\Python\Python310\python.exe")

# Dis API kredi/kota durum kaydi (best-effort). HERE (=scripts) zaten _generate_ozet
# cagrildiginda sys.path'e ekleniyor (798/828) ama import'u burada da deneyelim;
# patlarsa _status_mark no-op olur — OZET URETIMI ASLA ETKILENMEZ.
try:
    sys.path.insert(0, str(HERE))
    from _api_status import mark as _api_mark  # noqa: E402
except Exception:  # noqa: BLE001 - modul yok/bozuk -> no-op stub, ozet etkilenmesin
    def _api_mark(api: str, ok: bool, detail: str = "") -> None:  # type: ignore[misc]
        return None


def _status_mark(api: str, ok: bool, detail: str = "") -> None:
    """_api_mark guvenli sarmal — mark patlarsa sessiz (ozet/pipeline cokmesin)."""
    try:
        _api_mark(api, ok, detail)
    except Exception:  # noqa: BLE001
        pass


# Profil → ASR aksiyon konfigi (PROFIL_KONFIG.md ile SENKRON).
# film_dizi (film/dizi) → LEAN: özet için sadece METİN (turbo tek-pass; align/diarize/fallback YOK).
# Tanımsız profil = full ASR (eski davranış, run_asr_pipeline). Çağatay buraya ekler (eklemeler gelecek).
PROFILE_ASR: dict = {
    "film": dict(lean=True, model="large-v3-turbo", beam_size=1, vad="on", language="auto"),
    "dizi": dict(lean=True, model="large-v3-turbo", beam_size=1, vad="on", language="auto"),  # ses işi dizide de geçerli
    # "belgesel": ...  "muzik": ...  "spor": ...  "studio": ...  "haber": ...  "stt": ...   (DOLDURULACAK)
}
TRT_RE = re.compile(r"(\d{4})-(\d{3,4})-(\d)-(\d{3,4})-(\d{2})-(\d)")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(kind, *, summary, level="info", module=None, media_id=None, filename=None,
              job_id=None, duration_seconds=None, error=None, detail=None):
    """outputs/system_events.jsonl'e observability.log_event ile AYNI formatta yazar."""
    ev = {"event_id": f"evt-{uuid4().hex[:12]}", "ts": now_iso(), "kind": kind,
          "level": level if level in ("info", "warn", "error") else "info", "summary": summary}
    if module:
        ev["module"] = module
    if media_id:
        ev["media_id"] = media_id
    if filename:
        ev["filename"] = filename
    if job_id:
        ev["job_id"] = job_id
    if duration_seconds is not None:
        ev["duration_seconds"] = round(float(duration_seconds), 3)
    if error:
        ev["error"] = str(error)[:4000]
    if detail:
        ev["detail"] = detail
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Basit rotasyon: dosya >5MB ise .1.jsonl'a kaydır (sadece 1 onceki, eski .1 silinir).
    try:
        if EVENTS_PATH.exists() and EVENTS_PATH.stat().st_size > 5_000_000:
            backup = EVENTS_PATH.with_suffix(".1.jsonl")
            if backup.exists():
                backup.unlink()
            EVENTS_PATH.rename(backup)
    except Exception:  # noqa: BLE001 — rotasyon log akışını bozmasın
        pass
    with EVENTS_PATH.open("a", encoding="utf-8") as h:
        h.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return ev


def run(cmd, timeout=3600):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def last_json(stdout: str):
    for line in reversed([l.strip() for l in stdout.splitlines() if l.strip()]):
        if line.startswith("{"):
            try:
                return json.loads(line)
            except Exception:  # noqa: BLE001
                continue
    return None


def sanitize(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", (s or "").strip()).strip("._-") or "media"


# Arşiv klasör/dosya adlandırma (DATABASE düzeni). sanitize()'tan AYRI: Türkçe harf/apostrof/
# boşluğu KORUR, yalnız Windows-yasak karakter + kontrol karakterlerini çıkarır.
_ILLEGAL_WIN = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_TRAIL = " . \t"


def _ad_clean(s: str) -> str:
    return re.sub(r"\s{2,}", " ", _ILLEGAL_WIN.sub(" ", (s or "").strip())).strip(_TRAIL)


def folder_name(title: str, trt: str, fallback_stem: str = "") -> str:
    """Arşiv klasör adı '<BAŞLIK> <TRT>' (ad önce). Türkçe/apostrof/boşluk KORUNUR; ASCII'ye EZMEZ."""
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
    """Kök teslimat dosya tabanı '<TRT> <BAŞLIK>' (TRT önce — DATABASE dosya + export kuralı)."""
    t = _ad_clean(title)
    tr = (trt or "").strip()
    name = f"{tr} {t}".strip() if (tr or t) else "media"
    return _ad_clean(name)[:180].strip(_TRAIL) or "media"


def md_to_readable(md: str) -> str:
    """kunye_teslim.md → insan-okunur .txt (saf string dönüşümü; model çağrısı YOK). Bölüm sırası korunur."""
    out = []
    for raw in (md or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            out.append("")
        elif line.startswith("# "):                       # '# MİTAS • FİLM • BAŞLIK' → başlık
            parts = [p.strip() for p in line[2:].split("•")]
            title = parts[-1] if parts else line[2:].strip()
            out += ["=" * 64, f"  {title}", "=" * 64]
        elif line.startswith("## "):                       # '## Bölüm' → ayraçlı başlık
            out += ["", f"--- {line[3:].strip()} ---"]
        elif line.startswith("- "):                        # '- madde' → girintili madde
            out.append(f"  {line[2:].strip()}")
        else:
            out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out).strip() + "\n")


def _patch_md_credits(md_text: str, v4: dict) -> str:
    """PROPAGATION fix (2026-06-20): yüzey .txt'yi V4 PDF ile HİZALA.
    Yüzey .txt, _pipe_pdf'in yazdığı kunye_teslim.md'den üretilir; o .md kimi koşuda HAM parse_credits
    çöpünü taşır (şoför/craft/müzik-kredi), oysa V4 (tek_film_kunye) PDF'i TEMİZ üretir → PDF≠txt.
    V4 rapor JSON'ındaki OTORİTER cast/yön/yapımcı/keyword ile .md'nin ilgili 3 bölümünü değiştir
    (tur_override deseniyle aynı). YALNIZ V4 değer SAĞLADIYSA (anahtar var); yoksa DOKUNMA (wipe yok)."""
    if not v4 or not isinstance(v4, dict):
        return md_text
    cast = v4.get("cast_list")
    kw = v4.get("keywords")
    yon = v4.get("yonetmen_list")
    yap = v4.get("yapimci_list")
    notu = v4.get("film_notu") or []          # FİLM NOTU (2026-07-04): PDF kutusuyla md/txt hizası
    if cast is None and yon is None and yap is None and kw is None and not notu:
        return md_text
    lines = md_text.splitlines()
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        h = line.strip()
        # bir bölüm gövdesini (header sonrası boş/'## ' gelene dek satırlar) yeni değerle değiştir
        if h == "## Anahtar Sözcükler" and kw is not None:
            out.append(line); i += 1
            while i < n and lines[i].strip() and not lines[i].startswith("## "):
                i += 1
            out.append(kw if kw else "—")
            continue
        if h == "## Oyuncular" and cast is not None:
            out.append(line); i += 1
            while i < n and lines[i].strip() and not lines[i].startswith("## "):
                i += 1
            out.extend([f"- {c}" for c in cast] if cast else ["—"])
            continue
        if h == "## Yapım Ekibi" and (yon is not None or yap is not None):
            out.append(line); i += 1
            while i < n and lines[i].strip() and not lines[i].startswith("## "):
                i += 1
            out.append(f"- Yapımcı: {', '.join(yap) if yap else '—'}")
            out.append(f"- Yönetmen: {', '.join(yon) if yon else '—'}")
            continue
        if h == "## Film Notu" and notu:          # var olan bölümü V4 notlarıyla değiştir
            out.append(line); i += 1
            while i < n and lines[i].strip() and not lines[i].startswith("## "):
                i += 1
            out.extend([f"- {x}" for x in notu])
            continue
        if h == "## Özet" and notu and "## Film Notu" not in md_text:
            out.extend(["## Film Notu"] + [f"- {x}" for x in notu] + [""])   # bölüm yoksa Özet'ten önce enjekte
            out.append(line); i += 1
            continue
        out.append(line); i += 1
    return "\n".join(out)


def surface_deliverables(clip_dir: Path, trt: str, title: str, pdf_info: dict, tur_override: str = "",
                         v4_credits: dict = None) -> None:
    """Köke temiz teslimat yüzeyle: '<TRT> <BAŞLIK>.pdf' + afis.jpg + '<TRT> <BAŞLIK>.txt'.
    Mevcut artefaktları KOPYALAR (yeniden üretmez). Çağıran try/except ile sarmalı — pipeline'ı bozmaz.
    v4_credits: V4 rapor 'v4' bloğu (cast_list/yonetmen_list/yapimci_list/keywords) → .txt'yi PDF ile hizalar."""
    base = file_base(trt, title)
    pdf_out = clip_dir / "pdf"
    # is_file (exists DEĞİL): pdf_path=None → Path("")=Path('.') var olan DİZİN sayılır,
    # copy2('.', hedef) Errno 21 patlatır + fallback araması atlanırdı (2026-07-30 kanıtlı).
    pdf_src = Path((pdf_info or {}).get("pdf_path") or "")
    if not (pdf_src and pdf_src.is_file()):
        for cand in ("kunye_fixed.pdf", "kunye.pdf"):
            p = pdf_out / cand
            if p.is_file():
                pdf_src = p
                break
    if pdf_src and pdf_src.is_file():
        shutil.copy2(pdf_src, clip_dir / f"{base}.pdf")
    afis = pdf_out / "afis.jpg"
    if afis.exists():
        shutil.copy2(afis, clip_dir / "afis.jpg")
    md = pdf_out / "kunye_teslim.md"
    if md.exists():
        md_text = md.read_text(encoding="utf-8", errors="replace")
        # TÜR'ü PDF-nihai değerle hizala (divergence fix): kunye_teslim.md _pipe_pdf'te yalnız tur_xml
        # taşıyordu; tur_override (v4 nihai = IMDb/Wikidata fallback'li) ile değiştir. SADECE tur_override
        # doluyken; boşsa md'deki mevcut değere DOKUNMA (uydurma/wipe yok). "Tür: <X>  ·  Süre" sınırlı.
        if tur_override:
            import re as _re
            md_text = _re.sub(r"(Tür:)\s*[^·\n]*?(\s*·\s*Süre:|\s*\n|$)",
                              lambda m: f"{m.group(1)} {tur_override}{m.group(2)}", md_text, count=1)
        # PROPAGATION fix: cast/yön/yapımcı/keyword'ü V4 PDF otoriteriyle hizala (PDF≠txt sapması biter)
        if v4_credits:
            md_text = _patch_md_credits(md_text, v4_credits)
        # MD-SENKRON FIX (117-film taraması 2026-07-03): patch'li içerik DİSKTEKİ kunye_teslim.md'ye
        # de yazılır. En az 6 filmde (ŞİRKET İLİŞKİLERİ, GÜLE GÜLE JÜPİTER, DAĞ KADINI, MEKKE'YE
        # YOLCULUK, RÜZGAR BİZİ SÜRÜKLEYECEK, LOTR-2001...) md v4-öncesi BAYAT halde kalıp nihai
        # PDF ile çelişiyordu → denetim/QC ajanları ve _teknik.txt yanlış kaynaktan okuyordu.
        try:
            md.write_text(md_text, encoding="utf-8")
        except Exception:  # noqa: BLE001 — md yazılamazsa yüzey .txt yine patch'li üretilir
            pass
        (clip_dir / f"{base}.txt").write_text(
            md_to_readable(md_text), encoding="utf-8")


def _read_json_safe(p: Path):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _credit_validate_strong_director(cv_result: dict) -> bool:
    if not isinstance(cv_result, dict):
        return False
    yd = cv_result.get("yonetmen") or {}
    if yd.get("status") != "DOGRULANDI" or yd.get("confidence") != "KESIN" or not yd.get("value"):
        return False
    sources = {str(s).strip().lower() for s in (yd.get("sources_confirm") or []) if str(s).strip()}
    if not ("xml" in sources and ({"imdb", "wiki", "wikidata"} & sources)):
        return False
    kaynaklar = cv_result.get("kaynaklar") or {}
    return bool(((kaynaklar.get("imdb") or {}).get("key"))
                or ((kaynaklar.get("wiki") or {}).get("key")))


def _ocr_bucket_can_be_warning(ocr_bucket: str, v4_report: dict) -> bool:
    """Ham OCR GOZDEN_GECIR iken final künye kapıları temizse bucket'ı karar sebebi yapma."""
    if str(ocr_bucket or "").strip() != "GOZDEN_GECIR" or not isinstance(v4_report, dict):
        return False
    v4 = v4_report.get("v4") or {}
    adimlar = v4_report.get("adimlar") or {}
    cc4 = adimlar.get("cross_check") or {}
    qcb = adimlar.get("qc_block") or {}
    audit = v4.get("qc_block_otorite_audit") or qcb.get("otorite_audit") or {}

    locked = bool(cc4.get("kimlik_dogru")) or cc4.get("verdict") == "TEYİT" or ((cc4.get("cast_ortusme") or 0) >= 3)
    if not locked:
        return False
    if not (v4.get("yonetmen") or v4.get("yonetmen_list")):
        return False
    if (v4.get("cast") or len(v4.get("cast_list") or [])) < 3:
        return False
    floor = v4.get("qc_block_floor") or qcb.get("floor") or {}
    if floor and floor.get("kabul") is False:
        return False
    if cc4.get("cast_garble") or v4.get("yon_garble_lex") or (v4.get("cast_garble_lex_count") or 0) > 0:
        return False
    if isinstance(audit, dict) and audit.get("ocr_authority_violation") is True:
        return False

    hard_markers = (
        "kimlik kurulamadı", "zayıf-teyit", "Latin-dışı", "oyuncu yetersiz",
        "oyuncu yok", "garble", "yönetmen okunamadı",
    )
    for g in (v4.get("qc_block_gerekceler") or qcb.get("gerekceler") or []):
        gs = str(g)
        if "özet yok/kısa" in gs:
            continue
        if any(m in gs for m in hard_markers):
            return False
    return True


def _fmt_mb(b) -> str:
    try:
        return f"{int(b) / (1024 * 1024):.1f} MB"
    except Exception:  # noqa: BLE001
        return "—"


def _md_section(md: str, header: str) -> list:
    """kunye_teslim.md '## <header>' altındaki '- ' satırlarını döndür."""
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
    """Referans _teknik.txt benzeri insan-okunur teknik rapor (eldeki clip.json/_DURUM.json/künye'den)."""
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
    L += [f"    - {n}" for n in nedenler] if nedenler else ["    (tüm bloklar temiz)"]
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
    """Global system_events(.1).jsonl'den bu filmin (media_id) olaylarını çek (kronolojik)."""
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
                    except Exception:  # noqa: BLE001
                        continue
                    if o.get("media_id") == media_id:
                        evs.append(o)
        except Exception:  # noqa: BLE001
            continue
    evs.sort(key=lambda e: e.get("ts", ""))
    return evs


def surface_logs(clip_dir: Path, trt: str = "", title: str = "") -> None:
    """Köke '<TRT> <BAŞLIK>_teknik.txt' (insan-okunur) + '_log.jsonl' (filmin olayları) yaz.
    Tüm veri klasörden okunur → pipeline ve backfill AYNI çıktıyı verir. Çağıran try/except ile sarmalı."""
    clipj = _read_json_safe(clip_dir / "clip.json") or {}
    durum = _read_json_safe(clip_dir / "_DURUM.json") or {}
    trt = trt or clipj.get("trt_id") or durum.get("trt_id") or ""
    title = title or clipj.get("title") or durum.get("title") or ""
    base = file_base(trt, title)
    mdp = clip_dir / "pdf" / "kunye_teslim.md"
    md_txt = mdp.read_text(encoding="utf-8", errors="replace") if mdp.exists() else ""
    (clip_dir / f"{base}_teknik.txt").write_text(build_teknik(clipj, durum, md_txt), encoding="utf-8")
    media_id = clipj.get("media_id") or durum.get("clip_id") or ""
    evs = extract_clip_events(media_id)
    if evs:
        with (clip_dir / "_log.jsonl").open("w", encoding="utf-8") as h:
            for e in evs:
                h.write(json.dumps(e, ensure_ascii=False) + "\n")


def hash_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_filename(video: Path):
    """(trt_id, title, profile, bolum) — TRT kimlikten film/dizi; yoksa profile=None."""
    stem = video.stem
    m = TRT_RE.search(stem)
    trt = title = profile = bolum = None
    if m:
        trt = "-".join(m.groups())
        typ = m.group(3)
        profile = "film" if typ == "1" else ("dizi" if typ == "0" else None)
        if typ == "0":
            bolum = f"{int(m.group(4))}. BÖLÜM"
        # başlık = TRT id'den SONRAKİ kısım (içerik adı). TRT öncesi sistem önekidir
        # (web_client_CAG1_, evoArcadmin_COZUMLEMEV2S20_ vb.) → başlığa KATMA.
        # (KÖPRÜ _hile_manifest ile aynı kural.)
        title = stem[m.end():].lstrip("-_ ").replace("_", " ").strip(" -_")
        title = re.sub(r" {2,}", " ", title)                # Fix 5: çoklu boşluk sıkıştır (ESK   EH R → ESKEHR)
        if not title:                       # ad nadiren TRT'den önceyse geri düş
            title = stem[:m.start()].replace("_", " ").strip(" -_")
    else:
        title = stem.replace("_", " ").strip()
    return trt, title or stem, profile, bolum


def _clean_xml_title(s: str) -> str:
    """XML <TITLE> temizliği: zero-width / yön / soft-hyphen / kontrol karakterleri at, boşluğu
    normalize et. (Türkçe harfler KORUNUR — görünüm okunur kalsın; poster_fetch sorgu için kendi
    ASCII-fold'unu yapar.) ~%10 bozuk XML başlığını (encoding tuzağı) kullanılabilir hale getirir."""
    s = s or ""
    s = re.sub(r"[​‌‍‎‏‪-‮﻿­]", "", s)  # zero-width/yon/soft-hyphen
    s = re.sub(r"\s+", " ", s).strip()
    return s


@functools.lru_cache(maxsize=64)
def _xml_root_cached(path_str: str, _mtime: float):
    """(yol, mtime) anahtarlı ElementTree kökü — aynı sidecar XML'i tekrar tekrar parse etme.
    mtime anahtara dahil → dosya değişirse cache kendiliğinden tazelenir. SALT-OKUNUR kullan
    (kök paylaşılır; çağıranlar yalnız find/iter eder, mutasyon yok)."""
    import xml.etree.ElementTree as ET
    return ET.parse(path_str).getroot()


def _xml_root(video: Path):
    """Video yanındaki <stem>.xml sidecar kökünü BİR KEZ parse edip yeniden kullan.
    xml_original/xml_roles/xml_genre/genre_class hepsi aynı dosyayı okur; film başına 4-5
    tekrarlı IO/parse yerine tek parse. Yoksa/bozuksa None (çağıran kendi default'una düşer)."""
    xp = video.with_suffix(".xml")
    try:
        if not xp.exists():
            return None
        return _xml_root_cached(str(xp), xp.stat().st_mtime)
    except Exception:  # noqa: BLE001
        return None


def xml_original(video: Path) -> str:
    """Video yanindaki <stem>.xml sidecar'dan orijinal adi (<TITLE>) oku → afiş + ses/altyazı orijinal-ad.
    Yabancı filmde TRT başlığı Türkçe ("SİYAH İNCİ"), XML <TITLE> orijinal ("BLACK BEAUTY").
    BİRİNCİL kaynak (491/491 dolu, sıfır halüsinasyon). Yoksa/bozuksa "" → _pipe_pdf kadro-konsensüs
    fallback'i (credit_identity) devreye girer (Çağatay 2026-06-08: XML eksik olabilir, çalışsın)."""
    try:
        root = _xml_root(video)
        if root is None:
            return ""
        tt = root.find(".//TITLE")
        return _clean_xml_title(tt.text or "") if tt is not None else ""
    except Exception:  # noqa: BLE001
        return ""


def xml_roles(video: Path) -> dict:
    """Video yanindaki <stem>.xml sidecar'dan rol listelerini cikar (rol akli ankraji).

    BEAN/PROPERTY: isim = V_ROL_FIRST + V_ROL_LAST, rol = V_ROLE_TYPE.
    (_hile_manifest.xml_data ile AYNI mantik: YONETMEN->yonetmen, YAPIM->yapimci,
    OYUNCU/ROL->oyuncu.) XML yoksa/bossa {} doner → _pipe_pdf'e arg verilmez."""
    oy, yon, yap = [], [], []
    try:
        root = _xml_root(video)
        if root is None:
            return {}
        for b in root.iter("BEAN"):
            d = {p.attrib.get("NAME", ""): (p.text or "").strip() for p in b.findall("PROPERTY")}
            nm = (d.get("V_ROL_FIRST", "") + " " + d.get("V_ROL_LAST", "")).strip()
            rt = d.get("V_ROLE_TYPE", "").upper()
            if not nm:
                continue
            if "YÖNETMEN" in rt or "YONETMEN" in rt:
                yon.append(nm)
            elif "YAPIM" in rt:
                yap.append(nm)
            elif "OYUNCU" in rt or "ROL" in rt:
                oy.append(nm)
    except Exception:  # noqa: BLE001
        return {}
    roles = {"oyuncu": oy, "yonetmen": yon, "yapimci": yap}
    return roles if (oy or yon or yap) else {}


def xml_genre(video: Path) -> str:
    """XML tür — KADEMELİ (tek-alan bağımlılığı tür-eksikliğine yol açıyordu, 2026-06-15):
      1) JT:CLASSIFICATION:EDIT_FMT_NAME      (birincil: DRAMA/EĞLENCE-SHOW…)
      2) boşsa JT:CLASSIFICATION:EDIT_CONTENT_NAME  ("KURMACA / DRAMA" → DRAMA)
      3) boşsa JT:CLASSIFICATION:PEV_INTENTION_NAME (EĞLENCE…)
    Hepsi aynı TRT-kataloğu (doldurma değil, yedek-alan). IMDb/Wiki türü v4/validate katmanında."""
    try:
        root = _xml_root(video)
        if root is None:
            return ""
        fmt = content = intent = ""
        for p in root.iter("PROPERTY"):
            n = p.attrib.get("NAME")
            t = (p.text or "").strip()
            if not t:
                continue
            if n == "JT:CLASSIFICATION:EDIT_FMT_NAME" and not fmt:
                fmt = t
            elif n == "JT:CLASSIFICATION:EDIT_CONTENT_NAME" and not content:
                content = t
            elif n == "JT:CLASSIFICATION:PEV_INTENTION_NAME" and not intent:
                intent = t
        if fmt:
            return fmt
        if content:                                   # "KURMACA / DRAMA" → tür kısmı
            return content.split("/")[-1].strip()
        return intent or ""
    except Exception:  # noqa: BLE001
        return ""


# ── ÖZEL-TÜR SINIFLANDIRICI (Çağatay 2026-06-15): müzikal/belgesel/animasyon işlenmez ──
# İKİ sinyal birleşir (keskin tespit):
#   (1) XML EDIT_FMT_NAME/CONTENT imzası — TRT katalogcusunun İNSAN-ELİ işareti, yüksek isabet
#       (ölçüm 2026-06-15: 2060 arşiv XML; ÇİZGİ/ANİMASYON=22, KURMACA OLMAYAN=14, MÜZİK/BALE=10).
#   (2) final TÜR string (KB/IMDb türevli) — XML'in 'DRAMA' catch-all'ı belgeseli GİZLEDİĞİNDE
#       yakalar (İKİZLER örneği: XML=DRAMA ama IMDb 'Documentary'→TÜR=BELGESEL).
# XML imzası ÖNCE (same-title KB yanlış-eşleşmesi skip kararını bozmasın); yoksa final-TÜR keyword.
_GENRE_XML_SIG = {        # EDIT_FMT_NAME → kanonik sınıf (ölçülmüş gerçek değerler)
    "KURMACA OLMAYAN": "BELGESEL", "BELGESEL": "BELGESEL", "DÖKÜDRAMA": "BELGESEL",
    "ÇİZGİ/ANİMASYON": "ANİMASYON",
    "MÜZİK / BALE / DANS / SANATSAL GÖSTERİ": "MÜZİKAL",
}
_GENRE_CONTENT_SIG = {    # EDIT_CONTENT_NAME yedek imza
    "KURMACA OLMAYAN / BİLGİLENDİRME": "BELGESEL",
    "MÜZİK, BALE, DANS": "MÜZİKAL", "BALE": "MÜZİKAL",
}


def _genre_fold(s: str) -> str:
    """Aksan/Türkçe-harf bağımsız BÜYÜK-harf (keyword eşleşmesi için)."""
    import unicodedata
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()


def _special_genre_from_text(s: str) -> str:
    """Metnin içinde özel tür geçiyorsa kanonik tür döndür."""
    raw = (s or "").strip()
    if not raw:
        return ""
    folded = _genre_fold(raw)
    for table in (_GENRE_XML_SIG, _GENRE_CONTENT_SIG):
        if raw in table:
            return table[raw]
        for key, genre in table.items():
            if folded == _genre_fold(key):
                return genre
    # Anahtar-kelime (TR + İng): "her türlü sağla" — KB Türkçe verir ama ham IMDb/etiket İng. olabilir.
    if "BELGESEL" in folded or "DOCUMENTARY" in folded:
        return "BELGESEL"
    if "ANIMASYON" in folded or "ANIMATION" in folded or "ANIMATED" in folded:
        return "ANİMASYON"
    if "MUZIKAL" in folded or "MUSICAL" in folded:   # 'MÜZİK'/'MUSIC' (müzik) DEĞİL — yalnız müzikal
        return "MÜZİKAL"
    return ""


def genre_class(video: Path, final_tur: str = "") -> str:
    """Filmi özel-tür sınıfına sok: BELGESEL / MÜZİKAL / ANİMASYON / DİĞER (skip kararı için).
    1) XML EDIT_FMT_NAME/CONTENT/INTENTION içinde özel tür geçiyorsa onu döndür.
    2) yoksa final TÜR string içindeki özel tür anahtar kelimesi (KB/IMDb; XML 'DRAMA' catch-all'ı yakalar).
    3) DİĞER. (Görünür PDF TÜR'ünü DEĞİŞTİRMEZ — yalnız skip sinyali.)"""
    fmt = content = intent = ""
    try:
        root = _xml_root(video)
        if root is not None:
            for p in root.iter("PROPERTY"):
                n, t = p.attrib.get("NAME"), (p.text or "").strip()
                if n == "JT:CLASSIFICATION:EDIT_FMT_NAME" and not fmt:
                    fmt = t
                elif n == "JT:CLASSIFICATION:EDIT_CONTENT_NAME" and not content:
                    content = t
                elif n == "JT:CLASSIFICATION:PEV_INTENTION_NAME" and not intent:
                    intent = t
    except Exception:  # noqa: BLE001
        pass
    for value in (fmt, content, intent, final_tur):
        special = _special_genre_from_text(value)
        if special:
            return special
    return "DİĞER"


def _safe_remove_mitas_work_dir(path: Path) -> tuple[bool, str]:
    """Yalnız MITAS çalışma kökü altındaki klasörü temizle; kaynak medyaya dokunma."""
    try:
        root = DB_ROOT.resolve()
        target = path.resolve()
        if target == root or root not in target.parents:
            return False, f"unsafe_target:{target}"
        if not target.exists():
            return True, "not_created"
        shutil.rmtree(target)
        return True, "deleted"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _skip_special_genre(video: Path, clip_dir: Path, *, media_id: str, trt: str, title: str,
                        profile: str, tur_xml: str, genre_name: str, reason: str,
                        stage: str) -> int:
    cleanup_ok, cleanup_note = _safe_remove_mitas_work_dir(clip_dir)
    log_event(
        "media_skipped_special_genre",
        summary=f"{video.name}: {reason}; işleme alınmadı.",
        module="pipeline",
        media_id=media_id,
        filename=video.name,
        detail={
            "trt_id": trt,
            "title": title,
            "profile": profile,
            "tur_xml": tur_xml,
            "genre_class": genre_name,
            "stage": stage,
            "work_dir": str(clip_dir),
            "work_dir_cleanup_ok": cleanup_ok,
            "work_dir_cleanup": cleanup_note,
            "source_deleted": False,
        },
    )
    print(json.dumps({
        "karar": "Silindi",
        "neden": [reason],
        "tur": genre_name,
        "stage": stage,
        "hub": str(clip_dir),
        "calisma_klasoru": cleanup_note,
        "kaynak_silindi": False,
    }, ensure_ascii=False))
    return 0


def ffprobe_specs(video: Path):
    res = fps = dur = "—"
    dur_sec = 0.0
    # FROM-HUB modu (2026-07-11, Opus akış-incelemesi sonrası): kaynak video OFFLINE iken
    # frames-only TAM-kapı koşusu — specs kaynak-hub clip.json/_DURUM'dan gelir, ffprobe atlanır.
    _fh = os.environ.get("MITAS_FROM_HUB_SPECS", "")
    if _fh:
        try:
            s = json.loads(_fh)
            return (s.get("res", "—"), s.get("fps", "—"), s.get("dur", "—"),
                    float(s.get("dur_sec") or 0.0))
        except Exception:  # noqa: BLE001 — bozuk env → normal yola düş
            pass
    try:
        rc, out, _ = run([FFPROBE if FFPROBE.exists() else "ffprobe", "-v", "error",
                          "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate", "-show_entries", "format=duration",
                          "-of", "json", str(video)], timeout=120)
        d = json.loads(out)
        st = (d.get("streams") or [{}])[0]
        w, h = st.get("width"), st.get("height")
        if w and h:
            res = f"{w}x{h}"
        rfr = st.get("r_frame_rate") or "0/0"
        if "/" in rfr:
            a, b = rfr.split("/")
            if float(b or 0):
                fps = f"{float(a) / float(b):.3f}".rstrip("0").rstrip(".")
        dur_sec = float((d.get("format") or {}).get("duration") or 0.0)
        if dur_sec:
            h_, rem = divmod(int(dur_sec), 3600)
            m_, s_ = divmod(rem, 60)
            dur = f"{h_:02d}:{m_:02d}:{s_:02d}"
    except Exception:  # noqa: BLE001
        pass
    return res, fps, dur, dur_sec


class FrameContractError(RuntimeError):
    """Kullanici tarafindan istenen kare sayisi eksik uretildiginde pipeline'i durdurur."""


def expected_frame_count(length: float, fps: float) -> int:
    """Ondalik kayan-nokta sapmasindan etkilenmeden hedef kare sayisini hesaplar."""
    if length <= 0 or fps <= 0:
        raise FrameContractError(f"gecersiz kare sozlesmesi: length={length}, fps={fps}")
    return int(length * fps + 0.5)


def exit_frame_contract(duration: float, tail: float, fps: float) -> tuple[float, float, int]:
    """Cikis havuzunu kullanicinin tail/fps talimatina kilitler."""
    if duration <= 0:
        raise FrameContractError(f"video suresi okunamadi: duration={duration}")
    length = min(float(tail), float(duration))
    start = max(0.0, float(duration) - length)
    return start, length, expected_frame_count(length, fps)


def extract_window(video: Path, dst: Path, *, prefix, fps, start=None, length=None,
                   expected_count=None, timeout=1800):
    """Native kareleri gecici alanda uretir; eksik ciktiyi yayina almadan reddeder."""
    # FROM-HUB modu: frames junction'la hazir geldi — ffmpeg KOSULMAZ, mevcut sayi doner
    # (video offline; kare-sozlesmesi kaynak-hub'da zaten saglanmisti).
    if os.environ.get("MITAS_FROM_HUB", "") == "1" and dst.exists():
        _mevcut = len(list(dst.glob(f"{prefix}_*.png"))) or len(list(dst.glob("*.png")))
        if _mevcut:
            return _mevcut
    stage = dst.parent / f".{dst.name}.{prefix}.extract-{uuid4().hex}"
    stage.mkdir(parents=True, exist_ok=False)
    cmd = [FFMPEG if FFMPEG.exists() else "ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(video)]
    if length is not None:
        cmd += ["-t", str(length)]
    cmd += ["-vf", f"fps={fps}"]
    if expected_count is not None:
        cmd += ["-frames:v", str(int(expected_count))]
    cmd += [str(stage / f"{prefix}_%04d.png")]
    try:
        rc, _, err = run(cmd, timeout=timeout)
        if rc:
            raise RuntimeError(f"ffmpeg frame extraction failed rc={rc}: {err[-500:]}")
        staged = sorted(stage.glob(f"{prefix}_*.png"))
        count = len(staged)
        if expected_count is not None and count != int(expected_count):
            raise FrameContractError(
                f"eksik frame: beklenen={int(expected_count)}, uretilen={count}, "
                f"start={start}, length={length}, fps={fps}"
            )

        # Yalniz basarili ve dogrulanmis ciktiyi canli klasore aktar. Eski fazla
        # numarali kareler yeni sayimi maskeleyemesin diye aktarimdan sonra temizlenir.
        dst.mkdir(parents=True, exist_ok=True)
        new_names = {p.name for p in staged}
        for src in staged:
            os.replace(str(src), str(dst / src.name))
        for old in dst.glob(f"{prefix}_*.png"):
            if old.name not in new_names:
                old.unlink()
        return count
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def extract_audio(video: Path, dst: Path, timeout=1800):
    if os.environ.get("MITAS_FROM_HUB", "") == "1":
        return False, "from-hub modu: video offline, ses cikarilamaz (ASR zaten kapali)"
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [FFMPEG if FFMPEG.exists() else "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", str(dst)]
    rc, _, err = run(cmd, timeout=timeout)
    return dst.exists() and dst.stat().st_size > 0, err


def write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")            # 1.10 atomik yazim: kismi/bozuk JSON birakma
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(p))


def _is_technical_failure(video_credits) -> bool:
    """Teslim kapisinin tek teknik-kaza sinyali (saf/test-edilebilir)."""
    return (isinstance(video_credits, dict)
            and str(video_credits.get("extraction_status") or "").upper() == "TECHNICAL_FAILURE")


def _is_strong_screen_alias_conflict(cross_check: dict) -> bool:
    """Kimlik kilitliyken guclu ekran-rol kanitli ad farki (mahlas/AKA) blocker degildir."""
    if not isinstance(cross_check, dict) or cross_check.get("kimlik_dogru") is not True:
        return False
    conflicts = cross_check.get("yon_screen_conflict") or []
    return bool(conflicts) and all(
        isinstance(x, dict) and x.get("okunan") and x.get("ekran_kaniti") for x in conflicts)


def _has_identity_contradiction(cross_check: dict, *, qc2_resolved: bool = False,
                                strong_director: bool = False) -> bool:
    """Gercek kimlik celiskisini mahlas/AKA ekran farkindan VE OCR yazim-variantindan ayir."""
    if qc2_resolved or strong_director or not isinstance(cross_check, dict):
        return False
    if cross_check.get("kimlik_dogru") is False:
        return True
    # DENİZ EJDERİ C-fix (2026-07-12): kimlik_dogru cast-çapasıyla (cast_ov>=2) yönetmenden BAĞIMSIZ
    # kurulabilir → kimlik_dogru=True TEK BAŞINA verdict=ÇELİŞKİ'yi aklamaz. verdict=ÇELİŞKİ iken:
    #   • OCR-yönetmeni KB'ye name_close (yazım/OCR varyantı, ör. AUGUST~Ágúst) → yanlış-film DEĞİL → aklanır.
    #   • name_close PATLARSA (gerçek farklı yönetmen / aynı-başlık remake tuzağı; cast örtüşse bile) → KORUNUR.
    # Mahlas/AKA güçlü-ekran-kanıtı istisnası da korunur. (qwen+glm konsey: A çok açar, C güvenli koridor.)
    if cross_check.get("kimlik_dogru") is True:
        if (cross_check.get("verdict") == "ÇELİŞKİ"
                and not cross_check.get("yon_name_close")
                and not _is_strong_screen_alias_conflict(cross_check)):
            return True
        return False
    return (cross_check.get("verdict") == "ÇELİŞKİ"
            and not _is_strong_screen_alias_conflict(cross_check))


def _write_extraction_retry_work_item(clip_dir: Path, *, video: Path, profile: str,
                                      source_run_id: str, from_hub: Path | None = None) -> dict:
    """TF kosusunu kaybolmayan, candidate-only FULL retry isine cevir.

    Bu dosya kuyruk tuketicisi gelene kadar hub icindeki kalici PENDING is kaydidir; komut
    retry_planner'in silmesiz candidate sozlesmesinden uretilir. Otomatik calistirmaz.
    """
    import retry_planner as _rp

    seed = f"{source_run_id or 'norun'}:TECHNICAL_FAILURE"
    plan = _rp.plan_retry(str(video), "FULL", seed=seed,
                          db_root=PROJECT_ROOT / "Database")
    if from_hub is not None:
        # Kaynak video offline olan frames-only kosu ayni canonical hub'dan tekrar edilmelidir.
        plan["cmd"] = ["--from-hub", str(from_hub), "--profile", profile,
                       "--run-root", plan["run_root"]]
        plan["source_hub"] = str(from_hub)
    item = {
        "schema_version": 1,
        "status": "PENDING",
        "reason_code": "TEKNIK_ARIZA_EXTRACTION",
        "stage": "FULL",
        "source_run_id": source_run_id,
        "created_at": now_iso(),
        "plan": plan,
    }
    write_json(clip_dir / "retry_work_item.json", item)
    return item


def _write_mesru_bos_pending(clip_dir: Path, *, v4_credits: dict | None,
                             video_credits: dict | None) -> dict | None:
    """Bos final alanlari VL/insan ikinci tanigina PENDING yaz; terminal/muhur URETMEZ."""
    import mesru_bos as _mb

    v4 = v4_credits if isinstance(v4_credits, dict) else {}
    vc = video_credits if isinstance(video_credits, dict) else {}
    alanlar = {
        "YONETMEN": list(v4.get("yonetmen_list") or vc.get("yonetmen") or []),
        "YAPIMCI": list(v4.get("yapimci_list") or vc.get("yapimci") or []),
        "CAST": list(v4.get("cast_list") or vc.get("cast") or []),
    }
    # Opening+closing pencerelerinin ikisi de mevcut degilse kapsam kaniti yetersizdir.
    giris = clip_dir / "frames" / "giris"
    cikis = clip_dir / "frames" / "cikis"
    coverage_ok = (giris.exists() and any(giris.glob("*.png"))
                   and cikis.exists() and any(cikis.glob("*.png")))
    pending = []
    for field, values in alanlar.items():
        if values:
            continue
        sonuc = _mb.classify_field(
            ocr_empty=True, legibility="unknown", vl_verdict=None,
            coverage_ok=bool(coverage_ok), policy_na=False)
        # Bu production koprusu OCR-only'dir: terminal karar ve muhur verme yetkisi yoktur.
        if sonuc.get("terminal"):
            raise RuntimeError(f"OCR-only MESRU_BOS terminal uretmeye calisti: {field} {sonuc}")
        pending.append({"field": field, **sonuc})
    if not pending:
        return None
    obj = {
        "schema_version": 1,
        "gate_version": _mb.GATE_VERSION,
        "status": "PENDING_SECOND_WITNESS",
        "created_at": now_iso(),
        "coverage_ok": bool(coverage_ok),
        "items": pending,
    }
    write_json(clip_dir / "mesru_bos.pending.json", obj)
    return obj


_PERSON_GATE_HEADERS = [
    "TRT_ID", "Film", "Karar", "Rol", "Durum", "Okunan", "PDF_Yazilan",
    "Kaynak", "Harf_Farki", "Neden", "Teslim_PDF", "Saat",
]


def _person_gate_excel_rows(trt: str, title: str, karar: str, gate_report: dict, dest: Path) -> list[list]:
    """Yalnız DÜŞEN ve FUZZY ile DÜZELTİLEN kişi kapısı olaylarını Excel satırına çevir."""
    role_label = {"director": "Yönetmen", "cast": "Oyuncu", "producer": "Yapımcı"}
    rows: list[list] = []
    if not isinstance(gate_report, dict):
        return rows
    for role, rep in gate_report.items():
        if not isinstance(rep, dict):
            continue
        label = role_label.get(role, role)
        for item in rep.get("kept") or []:
            if not isinstance(item, dict):
                continue
            if item.get("action") != "FUZZY_DUZELDI":
                continue
            rows.append([
                trt or "", title or "", karar or "", label, "FUZZY_DUZELDI",
                item.get("in") or "", item.get("out") or "", item.get("source") or "",
                item.get("distance") or 0, "1 harf strict fuzzy ile geçti",
                str(dest), now_iso(),
            ])
        for item in rep.get("dropped") or []:
            if isinstance(item, dict):
                nm = item.get("in") or ""
                reason = item.get("reason") or "global/rol eşleşmesi yok"
            else:
                nm = str(item)
                reason = "global/rol eşleşmesi yok"
            rows.append([
                trt or "", title or "", karar or "", label, "DUSTU",
                nm, "", "", "", reason, str(dest), now_iso(),
            ])
    return rows


def _write_person_gate_excel(xlsx_path: Path, trt: str, title: str, karar: str, gate_report: dict, dest: Path) -> None:
    """Mitas Output/export altında kişi kapısı raporunu güncelle. Fail-safe: pipeline kararını bozmaz."""
    rows = _person_gate_excel_rows(trt, title, karar, gate_report, dest)
    try:
        import openpyxl
        from openpyxl.styles import Font, Alignment
        from openpyxl.utils import get_column_letter

        xlsx_path.parent.mkdir(parents=True, exist_ok=True)
        if xlsx_path.exists():
            wb = openpyxl.load_workbook(xlsx_path)
            ws = wb.active
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "kisi_kapisi"
            ws.append(_PERSON_GATE_HEADERS)
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(wrap_text=True)

        # Aynı TRT tekrar işlenirse eski bulguları temizle; yeni koşu tek gerçek olsun.
        for r in range(ws.max_row, 1, -1):
            if str(ws.cell(r, 1).value or "") == str(trt or ""):
                ws.delete_rows(r, 1)

        for row in rows:
            ws.append(row)

        widths = [18, 34, 12, 12, 16, 28, 28, 18, 10, 36, 58, 22]
        for idx, width in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(idx)].width = width
        ws.freeze_panes = "A2"
        wb.save(xlsx_path)
    except Exception as exc:  # noqa: BLE001
        log_event("person_gate_excel_failed", level="warn",
                  summary=f"kişi kapısı Excel yazılamadı: {exc}", module="qc",
                  detail={"xlsx": str(xlsx_path), "trt": trt, "rows": len(rows)})


def _env_int(name: str, default: int) -> int:
    try:
        v = os.environ.get(name)
        return int(v) if v else default
    except (ValueError, TypeError):
        return default


# 1.5 Alt-adim subprocess timeout'lari — env ile override edilebilir; default = onceki sabit degerler
OCR_TIMEOUT = _env_int("MITAS_OCR_TIMEOUT", 3600)
ASR_TIMEOUT = _env_int("MITAS_ASR_TIMEOUT", 7200)
PDF_TIMEOUT = _env_int("MITAS_PDF_TIMEOUT", 1800)
V4_TIMEOUT = _env_int("MITAS_V4_TIMEOUT", 900)
VC_TIMEOUT = _env_int("MITAS_VIDEO_CREDIT_TIMEOUT", 1800)
VL_TIMEOUT = _env_int("MITAS_VL_FALLBACK_TIMEOUT", 900)   # VL-fallback (2 model × kare); fail-safe
SHADOW_VL_TIMEOUT = _env_int("MITAS_SHADOW_VL_TIMEOUT", 900)  # gölge-VL subprocess; fail-safe, default AKTIF


def update_clip_module(clip_dir: Path, module: str, status: str, job_id: str):
    cj = clip_dir / "clip.json"
    rec = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else {}
    mods = rec.setdefault("modules", {})
    st = mods.setdefault(module, {"jobs": [], "latest_job_id": None, "status": None})
    if job_id not in st["jobs"]:
        st["jobs"].append(job_id)
    st["latest_job_id"] = job_id
    st["status"] = status
    st["updated_at"] = now_iso()
    write_json(cj, rec)


# --- Sonnet ozet (asr_server film dali ile AYNI mantik; bagimsiz kopya) ---
# asr_server'i komple import ETMEYIZ (FastAPI app + agir yan etki); buraya hafif
# bir kopya konur. Prompt/parametreler core/api/asr_server.py ile SENKRON tutulur.
OZET_PROMPT_PATH = PROJECT_ROOT / "core" / "api" / "prompts" / "ozet_film.txt"
OZET_PROMPT_V2_PATH = PROJECT_ROOT / "core" / "api" / "prompts" / "ozet_film_v2.txt"  # testas-yalın (MITAS_OZET_V2)
OZET_MAX_SOURCE_CHARS = 60000     # asr_server SUMMARY_MAX_SOURCE_CHARS
OZET_MAX_TOKENS = 1500            # asr_server SUMMARY_MAX_TOKENS
OZET_TIMEOUT_SECONDS = 90         # asr_server SUMMARY_TIMEOUT_SECONDS


def _load_sibling(_name):
    """scripts/ içindeki kardeş modülü güvenle yükle (import edilemezse None)."""
    try:
        import importlib
        return importlib.import_module(_name)
    except Exception:  # noqa: BLE001 — sys.path'te değilse modül-yolu ile dene
        try:
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location(_name, str(HERE / (_name + ".py")))
            _m = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_m)
            return _m
        except Exception:  # noqa: BLE001 — hâlâ yoksa None (sağlayıcı atlanır)
            return None


# Özet sağlayıcı istemcileri (yoksa None → o sağlayıcı atlanır, zincir sıradakine düşer).
_gemini = _load_sibling("_gemini")
_deepseek = _load_sibling("_deepseek")
_ozet_kalite = _load_sibling("_ozet_kalite")   # testas kapalı-döngü: kalite kapısı + onarım (v2 yolu)


# ASR zaman damgasi deseni: "[00:33:26] ". Ozete SIFIR katki, ama LLM tokenizer'inda ~2x sisirir
# (rakam/iki-nokta/koseli-parantez kotu bolunur). Uzun filmde toplam token baglam-penceresini asip
# modeli tek-token coplu cikti uretmeye iter (kanitli: SUCLU KIM 60K char damgali >32K token -> "H";
# damga soyununca 42K char/17.7K token -> temiz ozet). Soymak hem bu hatayi onler hem ~%30 token kazandirir.
# NOT (denetim 2026-06-28): ANA pipeline yolu zaten DAMGASIZ transcript_plain.txt'ten besleniyor
# (_pipe_asr transcript_plain'i damgasiz yazar) → bu regex ana yolda no-op. SAVUNMA KEMERI olarak
# tutuluyor: damgali metin baska bir kaynaktan (or. internet/transcript.txt) gelirse devreye girer.
_OZET_TS_RE = re.compile(r"\[\d\d:\d\d:\d\d\]\s*")


def _ozet_source_text(transcript: str) -> str:
    """Uzun transcript'i kirp (asr_server._summary_source_text ile ayni).

    2026-06-27: kirpmadan ONCE ASR zaman damgalarini soyar (MITAS_OZET_STRIP_TS, default ON; fail-safe).
    Damgalar ozet icin gurultu + token-sisirici; soymak uzun-film baglam-asimi cop ciktisini onler."""
    if os.environ.get("MITAS_OZET_STRIP_TS", "1").strip().lower() not in ("0", "false", "off", "no"):
        transcript = _OZET_TS_RE.sub("", transcript)
    if len(transcript) <= OZET_MAX_SOURCE_CHARS:
        return transcript
    head = transcript[:25000]
    middle_start = max(0, len(transcript) // 2 - 7500)
    middle = transcript[middle_start:middle_start + 15000]
    tail = transcript[-20000:]
    return f"{head}\n\n[... orta bolumden secki ...]\n\n{middle}\n\n[... son bolum ...]\n\n{tail}"


# Yabanci (TURKCE-OLMAYAN) Latin aksanlarini ASCII'ye katla; TURKCE harfler KORUNUR.
# PAYLASIMLI ç/ğ/ı/İ/ö/ş/ü (Turkce ile AYNI kod-noktasi) haritada YOK -> Sonnet'e kalir (calisiyor).
# Ozet kurali: yabanci ozel ad ASCII. Sonnet zaten ASCII yaziyor (ozet_film.txt); bu kemer nadir
# slip'i de yakalar: José->Jose, Begoña->Begona, Émile->Emile, Kieślowski->Kieslowski, Søren->Soren.
_FOREIGN_ACCENT_FOLD = str.maketrans({
    "à": "a", "á": "a", "â": "a", "ã": "a", "ä": "a", "å": "a", "ā": "a", "ą": "a",
    "À": "A", "Á": "A", "Â": "A", "Ã": "A", "Ä": "A", "Å": "A", "Ā": "A", "Ą": "A",
    "è": "e", "é": "e", "ê": "e", "ë": "e", "ē": "e", "ę": "e", "ě": "e",
    "È": "E", "É": "E", "Ê": "E", "Ë": "E", "Ē": "E", "Ę": "E", "Ě": "E",
    "ì": "i", "í": "i", "î": "i", "ï": "i", "ī": "i",
    "Ì": "I", "Í": "I", "Î": "I", "Ï": "I", "Ī": "I",
    "ò": "o", "ó": "o", "ô": "o", "õ": "o", "ø": "o", "ō": "o",
    "Ò": "O", "Ó": "O", "Ô": "O", "Õ": "O", "Ø": "O", "Ō": "O",
    "ù": "u", "ú": "u", "û": "u", "ū": "u", "Ù": "U", "Ú": "U", "Û": "U", "Ū": "U",
    "ñ": "n", "ń": "n", "Ñ": "N", "Ń": "N", "ć": "c", "č": "c", "Ć": "C", "Č": "C",
    "ś": "s", "š": "s", "Ś": "S", "Š": "S", "ź": "z", "ż": "z", "ž": "z", "Ź": "Z", "Ż": "Z", "Ž": "Z",
    "ý": "y", "ÿ": "y", "Ý": "Y", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D",
    "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE",
})


def _latin_only(s: str) -> str:
    """Ozet KURALI (Cagatay): cikti SADECE Latin/ASCII. 2026-06-28: Latin-disi harfi SILMEDEN ONCE
    transliterE et (Иван→Ivan, Λαμπρος→Lampros) → yabanci isim ozette KAYBOLMAZ, cikti yine Latin
    (KANUN B3). Sonra eski kemer: yabanci-aksan ASCII'ye (José→Jose, Turkce ç/ğ/ı/İ/ö/ş/ü KORUNUR),
    translit edilemeyen kalinti (unidecode yoksa Arapca) yine duser (kacinilmaz fallback)."""
    src = s or ""
    try:
        import translit_util as _tu
        src, _ = _tu.transliterate_mixed(src)
    except Exception:  # noqa: BLE001 — translit_util yok/bozuk → eski davranis (Latin-disi duser)
        pass
    return "".join(ch for ch in src.translate(_FOREIGN_ACCENT_FOLD)
                   if ch.isascii()
                   or unicodedata.category(ch)[0] != "L"
                   or "LATIN" in unicodedata.name(ch, ""))


# Anthropic yanit govdesinde kredi/kota tukenmesi sinyalleri (kuckuk harf eslesme).
_ANTHROPIC_CREDIT_SIGNALS = ("credit", "balance", "quota", "insufficient", "too low")


def _mark_anthropic_http_error(exc: "urllib.error.HTTPError") -> None:
    """Anthropic HTTPError'i kredi/kota acisindan siniflandirip durum kaydina yaz.

    KREDI/KOTA isareti (mark False) sayilan durumlar:
      - code == 400 ve govdede "credit"/"balance"/"too low" (Anthropic dusuk-bakiye 400 doner),
      - code in (402, 429)  (kredi-bitti / rate-kota),
      - govdede kredi sinyali ("credit"/"balance"/"quota"/"insufficient"/"too low").
    Diger HTTP hatalari (401 yetki, 404, 5xx vb.) YANLIS-ALARM olmasin diye mark EDILMEZ.
    """
    try:
        code = int(getattr(exc, "code", 0) or 0)
        body_txt = ""
        try:
            body_txt = exc.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            body_txt = ""
        low = (str(getattr(exc, "reason", "") or "") + " " + body_txt).lower()
        credit_sig = any(s in low for s in _ANTHROPIC_CREDIT_SIGNALS)
        is_credit = (
            (code == 400 and any(s in low for s in ("credit", "balance", "too low")))
            or code in (402, 429)
            or credit_sig
        )
        if is_credit:
            snippet = body_txt.strip().replace("\n", " ")[:120]
            _status_mark("anthropic", False, f"HTTP {code} {snippet}".strip())
    except Exception:  # noqa: BLE001 - siniflandirma best-effort
        return


def _ozet_anthropic(system_content: str, user_msg: str) -> str | None:
    """Sonnet (Anthropic) ile özet. Anahtar/yanıt yoksa None; kredi/kota → durum işaretlenir."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    model = os.environ.get("MITAS_ANTHROPIC_MODEL", "claude-sonnet-4-6")
    body = {
        "model": model,
        "max_tokens": OZET_MAX_TOKENS,
        "temperature": 0.2,
        "system": system_content,
        "messages": [{"role": "user", "content": user_msg}],
    }
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=OZET_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
        blocks = payload.get("content", [])
        content = next((b.get("text") for b in blocks if b.get("type") == "text"), None)
        if isinstance(content, str) and content.strip():
            _status_mark("anthropic", True)   # basarili icerik -> durum ok
            return content.strip()
    except urllib.error.HTTPError as exc:  # kredi/kota ise durumu işaretle, sonra sessiz fallback
        _mark_anthropic_http_error(exc)
        return None
    except Exception:  # noqa: BLE001 — timeout/URLError/JSON vs.: mark YOK (yanlış-alarm olmasın)
        return None
    return None


def _ozet_gemini(system_content: str, user_msg: str) -> str | None:
    """Gemini (Google) ile özet. _gemini istemcisi/anahtar yoksa None.

    Gemma/Gemini modelleri zaman zaman yanıt öncesinde zincir-düşünce (taslak/analiz)
    üretir. Gerçek özet her zaman SON paragraftır — önceki her şeyi at.
    """
    if _gemini is None:
        return None
    # BİRİNCİL: gemini-2.5-flash (2026-06-14 Çağatay A/B: en kısa-net cümle + en doğru plot +
    # ÇALIŞIYOR; Sonnet boş/kredisiz, DeepSeek 402). gemini-2.5 düşünmeyi API-içi yapar → TEMİZ
    # final döner (gemma-4-31b gibi ham zincir-düşünce DÖKMEZ). Kota dolunca (429) zincir gemma-local'e düşer.
    model = os.environ.get("MITAS_GEMINI_MODEL", "gemini-2.5-flash")
    # SAFETY=BLOCK_NONE: özet KURGU içeriği özetler (şiddet/ölüm/silah olağan). Gemini default safety
    # filtresi bu sahneleri BLOKLAYIP boş döndürüyordu (Sundown/Taşıyıcı gibi → kayıp özet). Özet
    # üretimi olduğu için tüm kategoriler BLOCK_NONE (2026-06-27 bake-off: blok→boş→gemma'ya düşüyordu).
    # THINKING BÜTÇESİ: gemini-2.5-flash bir düşünme modeli; thinkingBudget=0 uzun system-prompt'ta
    # BOŞ yanıt döndürüyor (2026-06-27 bake-off: SUNDOWN finishReason=None, 0 token). KÜÇÜK bütçe (512)
    # hem boşluğu çözer hem kavramayı artırır (Tate'in sağ kaldığı final ancak bütçeyle doğru çıktı) —
    # tam-reasoning'in halüsinasyon riskine girmeden. MITAS_GEMINI_THINK ile ayarlanır.
    try:
        _think = int(os.environ.get("MITAS_GEMINI_THINK", "512") or "512")
    except Exception:  # noqa: BLE001
        _think = 512
    raw = _gemini.gemini_text(
        system=system_content, prompt=user_msg,
        model=model, temperature=0.0, max_tokens=OZET_MAX_TOKENS, timeout=OZET_TIMEOUT_SECONDS,
        thinking_budget=_think,
        safetySettings=[{"category": c, "threshold": "BLOCK_NONE"} for c in (
            "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")],
    )
    if not isinstance(raw, str) or not raw.strip():
        return None
    # gemini-2.5 zaten temiz prose döner → doğrudan. Yalnız gemma-* ham zincir-düşünce dökerse
    # _gemma_extract_summary ile son TAM Türkçe özeti ayıkla (yoksa None → sıradaki sağlayıcı).
    if str(model).lower().startswith("gemma"):
        return _gemma_extract_summary(raw)
    return raw.strip()


# Gemma ham CoT çıktısından geçerli özet adaylarını ayıkla (meta/draft/kesik ele).
_GEMMA_META_LABEL = re.compile(
    r"^\s*(Draft\s*\d+|Final\s*Polish[^:]*|Refining[^:]*|Self-?Correction[^:]*"
    r"|Characters?|Setting|Plot|Ending|Trigger|Conflict|Decision|Action|Main\s*Character)\s*:?\s*\**\s*",
    re.I)
_GEMMA_META_WORD = re.compile(
    r"\b(draft|polish|refining|self-?correction|spoiler|paragraph|ceiling|adjective|transcript|ascii)\b", re.I)


def _gemma_extract_summary(raw: str) -> str | None:
    """Gemma-4 zincir-düşünce ham çıktısından SON tam Türkçe özet paragrafını çıkar.

    Aday = nokta ile biten, 25-95 kelime, meta-işaretsiz, harf-içeren Türkçe prose.
    Draft/Final-Polish gibi etiketler (satır-başı veya satır-içi) ve "(NN words) - *...*"
    açıklamaları soyulur. En sondaki geçerli aday alınır (genelde 'Final Polish' = en iyi).
    Hiç geçerli aday yoksa None → çağıran zinciri temiz sağlayıcıya düşürür."""
    if not raw:
        return None
    cands: list[str] = []
    for block in raw.split("\n\n"):
        kept: list[str] = []
        for ln in block.splitlines():
            s = ln.strip().lstrip("*#>-•`\t ").strip()
            if not s:
                continue
            s = _GEMMA_META_LABEL.sub("", s).strip()   # satır-başı/içi "Draft 2:" vb. etiketi soy
            if not s:
                continue
            kept.append(s)
        if not kept:
            continue
        txt = " ".join(kept).strip()
        txt = re.sub(r"\(\s*\d+\s*words?\s*\).*$", "", txt, flags=re.I).strip()  # "(66 words) - *Better.*" soy
        txt = re.sub(r"\s*[-–]\s*\*[^*]*\*\s*$", "", txt).strip()
        txt = txt.strip("*").strip()
        if not txt.endswith("."):
            continue                                   # kesik/yarım → ele
        wc = len(txt.split())
        if not (25 <= wc <= 95):
            continue                                   # çok kısa (çöp) / çok uzun (analiz) → ele
        if _GEMMA_META_WORD.search(txt):
            continue                                   # İngilizce meta/analiz sızıntısı → ele
        if not re.search(r"[A-Za-zğüşıöçİĞÜŞÖÇ]", txt):
            continue
        cands.append(txt)
    return cands[-1] if cands else None


def _ozet_deepseek(system_content: str, user_msg: str) -> str | None:
    """DeepSeek (V3) ile özet. _deepseek istemcisi/anahtar yoksa None."""
    if _deepseek is None:
        return None
    return _deepseek.deepseek_text(
        messages=[{"role": "system", "content": system_content},
                  {"role": "user", "content": user_msg}],
        model=os.environ.get("MITAS_DEEPSEEK_MODEL", "deepseek-chat"),
        temperature=0.2, max_tokens=OZET_MAX_TOKENS, timeout=OZET_TIMEOUT_SECONDS,
    )


def _ozet_gemma_local(system_content: str, user_msg: str) -> str | None:
    """Yerel gemma4 (ollama) ile özet — think=FALSE (zincir-düşünce KAPALI → doğrudan akıcı prose).

    2026-06-14 Çağatay: gemma4 bir DÜŞÜNME modeli; Google API'de (gemma-4-31b-it) düşünce-dökümü
    telgraf/kesik özet veriyordu. ollama'da `think:false` düşünmeyi KAPATIR → temiz akıcı tek-paragraf
    (ESKİ_KOCAM'da 70 kelime, nedensellik tam, 17s, kanıtlı). Yerel + bedava + kotasız (gemini 429 yok),
    ATLAS için zaten RAM'de. _generate_ozet'te BİRİNCİL; ollama yoksa/boşsa sıradaki sağlayıcıya düşer."""
    model = os.environ.get("MITAS_OZET_OLLAMA_MODEL", "gemma4:26b")
    base = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434").rstrip("/")
    body = json.dumps({
        "model": model, "system": system_content, "prompt": user_msg,
        "stream": False, "think": False,
        "options": {"temperature": 0.0, "num_predict": OZET_MAX_TOKENS},
    }).encode("utf-8")
    try:
        req = urllib.request.Request(base + "/api/generate", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=OZET_TIMEOUT_SECONDS) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        text = (out.get("response") or "").strip()
        return text or None
    except Exception:  # noqa: BLE001 — ollama yok/kapalı/timeout → None (sıradaki sağlayıcı)
        return None


# Özet SAĞLAYICI ZİNCİRİ — TEK-MODEL/TAM-YEREL (Çağatay 2026-06-23): SADECE gemma-local.
# Bulut (Sonnet/gemini/DeepSeek) DEVRE DIŞI → qwen/bulut bağımlılığı yok, "her şey gemma + yerel" hedefi.
# NOT: özet gemma4:26b ile üretilir. gemma-4-31b-it-qat-vision serbest-metin özette DEJENERE oluyor
# ("Pay"/boş; 3 varyant test edildi 2026-06-23) — o yüzden yapısal işlerde (extract/QC), özet 26b'de.
# gemma4:26b think=False ile temiz akıcı özet verir (ALİTA 59 kelime doğrulandı).
# Bulutu geri açmak: tuple'a ("sonnet", _ozet_anthropic) vb. ekle (fonksiyonlar korunuyor). KALİTE NOTU:
# Sonnet özet kalitesinde daha iyiydi; tam-yerellik için 26b'ye geçildi.
_OZET_SAGLAYICILAR = (
    ("gemma-local", _ozet_gemma_local),
)


def _ozet_chain():
    """Özet sağlayıcı zinciri. Default: SADECE gemma-local (tam-yerel, sürpriz maliyet yok).

    OPT-IN BULUT (2026-06-27, model-bake-off bulgusu): MITAS_OZET_CLOUD=1 ise zincirin BAŞINA Sonnet
    eklenir → bulut ÖNCE denenir, gemma-local FALLBACK kalır. Gerekçe: 7-model yerel bake-off'unda
    (gemma/Qwen3.6-27B/qwen3:30b-a3b/gpt-oss/nemotron/Haiku) HİÇBİR yerel model güvenilir-sağlıklı
    Türkçe özet veremedi (kim-kime karışması, kilit-dönüm atlama, dil/garble); yalnız Sonnet doğruydu.
    Flag default-OFF → anahtar ortamda olsa bile bilerek açılmadıkça bulut ÇAĞRILMAZ (maliyet koruması).
    Anahtar yoksa _ozet_anthropic/_ozet_gemini zaten None döner → otomatik gemma fallback (fail-safe).

    GEMINI (2026-06-27 model-bake-off KAZANANI): MITAS_OZET_GEMINI=1 → zincir başına gemini-2.5-flash.
    7-model yerel bake-off + tarafsız jüri: yerel hiçbir model sağlıklı değil; gemini-2.5-flash 0 HATALI
    (Sonnet-sınıfı kavrama) + ~10x ucuz + 2-3s + anahtar (MITAS_GEMINI) zaten kurulu. Sıra (varsa):
    gemini → sonnet → gemma-local (fallback). Herhangi biri None/kota → otomatik sıradakine düşer."""
    _on = ("1", "true", "on", "yes")
    chain = []
    # DeepSeek = testas'ın BİRİNCİL özet motoru (Çağatay 2026-07-23: "testas hangi API'yi
    # kullanıyorsa MITAS da onu kullansın"). Flag açıksa zincirin BAŞINA → birincil olur.
    if os.environ.get("MITAS_OZET_DEEPSEEK", "0").strip().lower() in _on:
        chain.append(("deepseek", _ozet_deepseek))
    if os.environ.get("MITAS_OZET_GEMINI", "0").strip().lower() in _on:
        chain.append(("gemini", _ozet_gemini))
    if os.environ.get("MITAS_OZET_CLOUD", "0").strip().lower() in _on:
        chain.append(("sonnet", _ozet_anthropic))
    # GEMMA-ÖZET AYRILDI (Çağatay 2026-07-31 akşam): "verimli özet alamadık,
    # bir sürü özet boş geldi — özeti gemmadan ayır." MITAS_OZET_GEMMA=0 iken
    # gemma zincire HİÇ girmez; başka sağlayıcı da açık değilse özet dürüstçe
    # atlanır (ozet_atlandi log'u + PDF'te placeholder). Bozuk/boş özet basmak
    # yerine hiç basmamak — testas felsefesiyle aynı. Geri: MITAS_OZET_GEMMA=1.
    if os.environ.get("MITAS_OZET_GEMMA", "1").strip().lower() in _on:
        chain.extend(_OZET_SAGLAYICILAR)   # gemma-local fallback (en sonda)
    return tuple(chain)


def _generate_ozet_v2(system_content: str, user_msg: str, chain, turlar: int) -> str | None:
    """testas kapalı-döngü özet: her sağlayıcıda K-deneme öz-düzeltme + kalite kapısı + onarım.

    Akış (sağlayıcı başına, MITAS_OZET_V2_ATTEMPTS=3 deneme):
      üret → _ozet_kalite.repair_generated_summary → summary_errors
        • kapı GEÇER + spoiler-final  → HEMEN dön (tercih edilen).
        • kapı GEÇER ama finalsiz      → 'best' yedeğe al, sıradaki sağlayıcıyı dene.
        • kapı GEÇMEZ                  → hata + kelime sayısını BİRİKİMLİ ekle, aynı sağlayıcıyı tekrar dene.
    Hiçbir sağlayıcı spoiler-final vermezse 'best' (finalsiz ama geçerli) döner. Hiçbir sağlayıcı
    çıktı veremezse (boş/kota/503) eski transient-retry (backoff) devreye girer; çıktı gelip
    hiçbiri kapıdan geçmezse beklemeden None döner (bozuk özet yerine placeholder — testas felsefesi).
    Çıktıya eski yolla AYNI _latin_only kemeri uygulanır.
    """
    qa = _ozet_kalite
    try:
        _att = max(1, int(os.environ.get("MITAS_OZET_V2_ATTEMPTS", "3") or "3"))
    except Exception:  # noqa: BLE001
        _att = 3
    best = None
    for _tur in range(turlar):
        produced_any = False
        for _ad, _fn in chain:
            cur_user = user_msg
            for _k in range(_att):
                try:
                    out = _fn(system_content, cur_user)
                except Exception:  # noqa: BLE001 — sağlayıcı çökerse sıradakine düş
                    out = None
                if not (isinstance(out, str) and out.strip()):
                    break   # bu sağlayıcı bir şey veremedi → sıradaki sağlayıcı
                produced_any = True
                cand = qa.repair_generated_summary(out.strip())
                errs = qa.summary_errors(cand)
                if not errs:
                    if qa.has_spoiler_final(cand):
                        return _latin_only(cand)          # tercih: geçerli + spoiler final
                    if best is None:
                        best = cand                        # geçerli ama finalsiz → yedek
                    break   # bu sağlayıcı geçerli-finalsiz verdi; başka sağlayıcı dene
                # geçersiz → geri bildirimi BİRİKTİREREK ekle (testas gibi; birikimsiz feedback
                # 'final ekle↔kısalt' osilasyonuna yol açabilir — konsey bug-avı bulgusu 2026-07-23).
                cur_user = (
                    cur_user
                    + "\n\nÖnceki çıktı uygun değildi: " + "; ".join(errs)
                    + f". Kelime sayısı: {qa.summary_word_count(cand)}."
                    + " 35-60 kelime, 3-4 cümle, tek paragraf, noktalı virgül yok, TAM cümleyle biten,"
                    + " SADECE özeti yeniden yaz."
                )
        if best is not None:
            return _latin_only(best)      # elimizdekinin en iyisi (finalsiz ama geçerli)
        if produced_any:
            break   # çıktı geldi ama kapıdan geçen yok → transient değil, beklemenin anlamı yok
        if _tur < turlar - 1:             # hiçbir sağlayıcı çıktı vermedi → geçici hata olabilir
            try:
                _bo = float(os.environ.get("MITAS_OZET_RETRY_BACKOFF", "6") or "6")
            except Exception:  # noqa: BLE001
                _bo = 6.0
            time.sleep(_bo * (_tur + 1))
    return _latin_only(best) if best else None


def _generate_ozet(transcript_text: str, *, title: str = "", duration: str = "") -> str | None:
    """Transcript'ten Gemini→Sonnet→DeepSeek zinciriyle film/dizi olay-örgüsü özeti (spoiler dahil).

    Prompt dosyası/transcript yoksa VEYA tüm denemeler başarısızsa None döner — çağıran
    placeholder'a düşer. Pipeline'ı ASLA çökertmez (tüm hatalar yutulur). Kazanan çıktıya
    _latin_only kemeri (Kiril/Çince düşer, yabancı aksan ASCII'ye katlanır) uygulanır.

    DAYANIKLILIK (Çağatay 2026-06-09): zincirin TAMAMI başarısız olursa özeti HEMEN BIRAKMAZ —
    kısa bekleyip TEKRAR dener (MITAS_OZET_RETRIES, default 3 tur). Geçici rate-limit/503'te
    bir film placeholder'a düşmeden önce 3 tam tur şans alır.
    """
    text = (transcript_text or "").strip()
    if not text:
        return None
    # v2 (testas kapalı-döngü) yolu: MITAS_OZET_V2=1 VE _ozet_kalite modülü yüklüyse devrede.
    _v2 = (
        os.environ.get("MITAS_OZET_V2", "0").strip().lower() in ("1", "true", "on", "yes")
        and _ozet_kalite is not None
    )
    try:
        system_content = (OZET_PROMPT_V2_PATH if _v2 else OZET_PROMPT_PATH).read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return None
    if not system_content.strip():
        return None
    source = _ozet_source_text(text)
    user_msg = (
        f"Dosya: {title or '—'}\n"
        f"Süre: {duration or '—'}\n\n"
        f"TRANSKRİPT:\n{source}"
    )
    try:
        _turlar = max(1, int(os.environ.get("MITAS_OZET_RETRIES", "3") or "3"))
    except Exception:  # noqa: BLE001
        _turlar = 3
    _chain = _ozet_chain()
    if _v2:
        return _generate_ozet_v2(system_content, user_msg, _chain, _turlar)
    for _tur in range(_turlar):
        for _ad, _fn in _chain:
            try:
                out = _fn(system_content, user_msg)
            except Exception:  # noqa: BLE001 — bir sağlayıcı çökerse sıradakine düş
                out = None
            if isinstance(out, str) and out.strip():
                return _latin_only(out.strip())   # SADECE Latin (Kiril/Çince düşer) — özet kuralı (kemer)
        # Bu turda HİÇBİR sağlayıcı özet veremedi → geçici hata (rate-limit/503) olabilir;
        # bekle ve TEKRAR dene (son turda bekleme yok).
        if _tur < _turlar - 1:
            try:
                _bo = float(os.environ.get("MITAS_OZET_RETRY_BACKOFF", "6") or "6")
            except Exception:  # noqa: BLE001
                _bo = 6.0
            time.sleep(_bo * (_tur + 1))   # 6s, 12s, ... (artan backoff)
    return None


def _ozet_name_tokens(s):
    """İsmi aksan-bağımsız ≥3-harf token kümesine çevir (soyad-eşleşme için)."""
    import unicodedata
    a = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return {t for t in re.split(r"[^A-Z]+", a) if len(t) >= 3}


def _ozet_identity_matches(tmdb_dir, tmdb_cast, verify_director, verify_cast):
    """TMDB sonucunun kimliği, OCR'ın okuduğuyla örtüşüyor mu? (same-title tuzağı kapısı)
      • yönetmen: OCR-yön ile TMDB-yön ≥1 ortak ≥3-harf token (soyad) → EŞLEŞTİ
      • ya da cast: OCR-cast ile TMDB-cast ≥2 ortak isim → EŞLEŞTİ
    Doğrulanamıyorsa False → özet KULLANILMAZ (yanlış film plotunu basmaktansa placeholder)."""
    vd = [d for d in (verify_director or []) if d]
    vc = [c for c in (verify_cast or []) if c]
    # yönetmen eşleşmesi (en güçlü sinyal)
    for d in vd:
        dt = _ozet_name_tokens(d)
        for td in (tmdb_dir or []):
            if dt and (dt & _ozet_name_tokens(td)):
                return True
    # cast örtüşmesi (≥2 isim soyad-token paylaşıyor)
    hits = 0
    for c in vc:
        ct = _ozet_name_tokens(c)
        if ct and any(ct & _ozet_name_tokens(tc) for tc in (tmdb_cast or [])):
            hits += 1
    return hits >= 2


def _fetch_internet_ozet(*, title="", original="", year="", duration="", verify_director=None, verify_cast=None):
    """Kürtçe/desteklenmeyen-dil filmi: ASR çeviremez → film kimliğinden (TMDB) internet plot çek,
    BİZİM özet promptumuzla (ozet_film.txt) özetle. Bulunamazsa None → çağıran dürüst placeholder'a düşer.
    SAME-TITLE KAPISI (2026-06-15 Çağatay): TMDB sonucunun yönetmeni/oyuncusu OCR'ın okuduğuyla
    DOĞRULANMADIKÇA plot KULLANILMAZ — "Beyaz Balon" arayıp ünlü Panahi 1995'i kapmasın (BEYAZ BALON
    Ghasemi 2021). Doğrulayacak OCR-kimlik yoksa → None (placeholder → KONTROL). 'Bulamadım > uydur'."""
    key = os.environ.get("MITAS_TMDB")
    if not key:
        return None
    if not (verify_director or verify_cast):
        return None                       # doğrulayacak OCR-kimlik yok → güvenli reddet (uydurma yok)
    import urllib.parse
    import urllib.request

    def _get(path, params):
        try:
            url = f"https://api.themoviedb.org/3/{path}?" + urllib.parse.urlencode({"api_key": key, **params})
            with urllib.request.urlopen(url, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return None

    def _credits_match(kind, mid):
        cr = _get(f"{kind}/{mid}/credits", {})
        if not cr:
            return False
        tmdb_dir = [c.get("name") for c in (cr.get("crew") or []) if c.get("job") == "Director"]
        tmdb_cast = [c.get("name") for c in (cr.get("cast") or [])[:12]]
        return _ozet_identity_matches(tmdb_dir, tmdb_cast, verify_director, verify_cast)

    for q in [x for x in (original, title) if x]:
        for lang in ("tr-TR", "en-US"):
            for kind in ("movie", "tv"):
                params = {"query": q, "language": lang}
                if year and kind == "movie":
                    params["year"] = year
                data = _get(f"search/{kind}", params)
                for res in (data or {}).get("results", [])[:3]:     # ilk 3 adayı kimlikle ele
                    ov = (res.get("overview") or "").strip()
                    if not ov or len(ov) <= 60 or not res.get("id"):
                        continue
                    if _credits_match(kind, res["id"]):              # OCR-kimlik DOĞRULANDI mı?
                        return _generate_ozet(ov, title=title, duration=duration)
    return None                                                     # doğrulanan aday yok → placeholder


# ── ÜRETİM-DOĞRULANMIŞ FLAG SETİ (config-to-code, 2026-06-23 FIX-A) ──────────────────────────────
# start_mitas.ps1:22-69 üretim-doğrulanmış flag setidir; ANCAK güvenlik-kritik flag'ler KODDA
# default-OFF olduğundan bare 'python mitas_pipeline.py --no-asr' koşusu bunları DEVRE-DIŞI bırakır
# (panel bulgusu: MITAS_QC_BLOCK kodda default-OFF, yalnız PowerShell başlatıcısı açıyordu →
# başlatıcıyı atlayan koşu sessizce daha bozuk konfigle çalışıyordu). Burada os.environ.setdefault
# ile koda taşıyoruz: setdefault => yalnız anahtar YOKSA yazar → kullanıcının/ps1'in/sunucunun
# verdiği env ASLA ezilmez (override + OCR-otorite invariant'ı korunur). ADDITIVE: yalnız yoksa
# env-default sağlar; hiçbir mevcut karar/davranış değiştirilmez. Alt-süreçler (OCR/ASR/v4/PDF/
# master-png) env= verilmeden spawn edildiğinden bu os.environ'u miras alır → main BAŞINDA (ilk
# subprocess'ten ÖNCE) çağrılırsa çocuklar da doğru env'i alır. MITAS_OCR_FORM_KEEP ps1'de SET
# EDİLMEMEKTEDİR → burada da YOK (A/B bekleniyor). Diğer C2/C5 flag'ler (CAST_OCR_KEEP/
# QC_NONCAST_FILTER/CAST_CAP) artık ps1 ile aynılıdır (aşağıdaki set'e ekli).
# AYNA: aşağıdaki set start_mitas.ps1:22-69 ile BİREBİR aynı olmalı (bir default değişirse İKİ yeri de
# elle senkron tut). DRIFT NOTU: bazı alt-modüllerin KENDİ kod-default'u farklı olabilir — ör.
# _pipe_ocr.py:623 MITAS_OCR_GLM_CONSENSUS kod-default '1' (AÇIK) iken burada '0' (KAPALI). Pipeline
# alt-süreçleri os.environ'u miras aldığından bu setdefault değeri kazanır (bare-pipeline'da GLM=0);
# yalnız alt-modül STANDALONE koşulursa kendi default'u geçerli olur.
_PROD_DEFAULTS = {
    "MITAS_QC2": "1",
    "MITAS_QC2_WEB": "1",
    "MITAS_QC_BLOCK": "1",
    "MITAS_SES_DIL_KONTROL": "0",
    "MITAS_QC_DIRECTOR_ANCHOR": "1",
    "MITAS_CREDIT_DETECT": "1",
    "MITAS_KB_CAST_ADD": "0",
    "MITAS_GEMMA_FULLCOVER": "1",
    "MITAS_OCR_GLM_CONSENSUS": "0",
    "MITAS_QC_OTORITE_AUDIT": "1",
    "MITAS_QC_FLOORFILL_OCRGUARD": "1",
    "MITAS_QC_FUZZY_DEDUP": "1",
    "MITAS_QC_PRODUCER_STRONGID": "1",
    "MITAS_XMLCAST_GATE_RELAX": "1",
    "MITAS_POSTER_VER_GATE": "1",
    "MITAS_LID_TR_VETO": "1",
    "MITAS_GARBLE_NGRAM": "1",
    "MITAS_GARBLE_NGRAM_ROUTE": "0",
    "MITAS_QC_OTORITE_ROUTE": "1",   # FIX-B: OCR-otorite ihlali → KONTROL (additive route)
    "MITAS_PDF_RENDER_AUDIT": "1",   # FIX-D: S5 form-ezme gözlem sinyali (route YOK)
    # C2/C5 flag'ler (2026-06-28 mirror fix): ps1:79-83 ile AYNI; MITAS_OCR_FORM_KEEP ps1'de YOK → burada da yok.
    "MITAS_CAST_OCR_KEEP": "1",      # C2: OCR-okunan oyuncu S6'dan düşerse kurtar (ADDITIVE)
    "MITAS_CAST_CAP": "18",          # C2c (2026-07-07): 10→18 — 50-film cap-düşen (UTANMAZ ADAM 14 oyuncu)
    "MITAS_QC_NONCAST_FILTER": "1",  # C5: non-cast qc_block S1 filtresi
    "MITAS_QC_ROLE_FILTER": "1",     # KAPI1 (2026-06-28): karakter-rol/tarif çöpü ele (yapısal-kesin, ad ezmez)
    "MITAS_DIRECTOR_RESCUE": "1",   # C-fix (2026-06-29): yönetmen-rescue; LLM boş → DIRECTED BY +1 (VETO: yapım etiketi/cast-çelişki)
    "MITAS_FRAME_DEDUP": "0",        # frame-dedup default OFF (A/B opt-in)
    # HIZLANDIRMA Faz-2 (2026-07-04, plan-karari + Sonnet SAFE): jdebug kosuda KAPALI (medyan
    # 184sn/film; karar/PDF'e sifir etki — blok karar-SONRASI). Backfill: jenerik_debug_batch.py.
    # DIKKAT: MITAS_JENERIK_PARALLEL_POOL AYRI ve ASLA kapatilmaz (master-PNG/dilim/K1 zinciri).
    "MITAS_JENERIK_PARALLEL_DEBUG": "0",
    # HIZLANDIRMA Faz-2 devami (2026-07-05, DALGA-181 olcumu): GOLGE-VL film-basina ~5-6dk GPU
    # yiyor (vl_pool + gemma okuma; _DURUM-SONRASI kostugu icin timings'e gorunmuyordu = "olu-zaman"
    # sanilan sey). Sonnet cakisma-denetimi SAFE demisti (jdebug ile ayni sinif, karar-disi golge).
    # Backfill: vl_pool/gemma okumasi offline kosulabilir (K2 hatti). Geri: =1.
    "MITAS_SHADOW_VL": "0",
    # HIZLANDIRMA Faz-0 hiz-modu (2026-07-04): LLM resident 15dk (soguk-start ~56sn/film eler);
    # ASR-subap (MITAS_ASR_LLM_VALVE) large-v3 oncesi tahliye eder -> VRAM guvenli. "-1" YASAK.
    "MITAS_OLLAMA_KEEP_ALIVE": "15m",
    # ÖZET MOTORU (2026-06-27 model-bake-off, Çağatay zincir kararı): gemini-2.5-flash (1) → Sonnet (2,
    # yedek) → gemma-local (3, max-fixed yerel). Gemini 0 HATALI/Sonnet-sınıfı/~10x ucuz/anahtar kurulu.
    # Sonnet yedek: ANTHROPIC_API_KEY yoksa _ozet_anthropic None döner → otomatik gemma'ya düşer (atıl).
    # Her katman kota/anahtar/hata'da sıradakine düşer (fail-safe). Kapatmak: ilgili flag=0.
    "MITAS_OZET_GEMINI": "1",
    "MITAS_OZET_CLOUD": "1",
}


def _apply_production_defaults() -> dict:
    """start_mitas.ps1 üretim flag setini os.environ.setdefault ile koda taşır (override korunur).

    Dönüş: {flag: (deger, kaynak)} — kaynak 'env' (kullanıcı/ps1 verdi, dokunulmadı) veya
    'default' (burada setdefault ile sağlandı). MITAS_PROD_DEFAULTS=0 ile tüm katman kapatılır."""
    snapshot: dict = {}
    _off = ("0", "false", "off", "no")
    if os.environ.get("MITAS_PROD_DEFAULTS", "1").strip().lower() in _off:
        for k in _PROD_DEFAULTS:                       # katman kapalı: yalnız mevcutları rapor et
            if k in os.environ:
                snapshot[k] = (os.environ[k], "env")
        return snapshot
    for k, v in _PROD_DEFAULTS.items():
        had = k in os.environ
        os.environ.setdefault(k, v)
        snapshot[k] = (os.environ[k], "env" if had else "default")
    return snapshot


def main(argv=None) -> int:
    # FIX-A: bare-CLI koşusunda da üretim flag setini garanti et (setdefault → override ezilmez).
    # İlk subprocess (OCR Popen) spawn'ından ÖNCE çalışır → tüm alt-süreçler doğru env'i miras alır.
    _cfg = _apply_production_defaults()
    try:
        log_event("pipeline_config_applied",
                  summary="Uretim flag seti uygulandi (config-to-code, setdefault).",
                  module="pipeline",
                  detail={"flags": {k: val for k, (val, _src) in _cfg.items()},
                          "source": {k: src for k, (_val, src) in _cfg.items()},
                          "prod_defaults_layer": os.environ.get("MITAS_PROD_DEFAULTS", "1")})
    except Exception:  # noqa: BLE001 — config-log ASLA pipeline'i bozmaz (fail-safe)
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=False, default=None,
                    help="kaynak video (ZORUNLU — yalnız --from-hub modunda otomatik türetilir)")
    ap.add_argument("--profile", default=None, help="film_dizi (tip TRT 3.parselden oto) | haber|belgesel|muzik|stt (yoksa TRT'den)")
    ap.add_argument("--fps", type=float, default=1.5, help="kare cikarim fps (native cozunurluk)")
    ap.add_argument("--ocr-head", type=float, default=180.0, help="acilis penceresi sn")
    ap.add_argument("--ocr-tail", type=float, default=480.0, help="kapanis penceresi sn")
    ap.add_argument("--asr-max-seconds", type=float, default=0.0, help="ASR'i ilk N sn ile sinirla (test)")
    ap.add_argument("--no-asr", action="store_true")
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--force-ocr", action="store_true",
                    help="from-hub: kopyalanan hub OCR'ını yeniden kullanma, frame'den TAZE OCR koş "
                         "(yalnız OCR/pipeline değişikliğini test ederken gerekir)")
    ap.add_argument("--no-copy-source", action="store_true", help="kaynak videoyu hub'a kopyalama (test)")
    ap.add_argument("--run-root", default=None,
                    help="İP-5 candidate modu: TÜM yazma-kökleri bu dizin altına (üretime sıfır dokunuş). "
                         "Env eşdeğeri: MITAS_RUN_ROOT (alt-süreçlere otomatik geçer).")
    ap.add_argument("--from-hub", default=None,
                    help="FRAMES-ONLY TAM-KAPI modu (2026-07-11, Opus incelemesi): kaynak video offline "
                         "iken üretim-hub'ının frames+ocr'ından TÜM kapıları (kimlik/QC/karar/PDF) koş. "
                         "--run-root ZORUNLU (üretime yazma imkânsızlaştırılır). ASR/detect otomatik kapalı.")
    args = ap.parse_args(argv)

    # === FROM-HUB hazırlığı (video'suz tam-kapı) ===
    _from_hub = Path(args.from_hub) if args.from_hub else None
    if not args.video and not _from_hub:
        ap.error("--video zorunlu (veya --from-hub kullanın)")
    if _from_hub:
        if not (args.run_root or os.environ.get("MITAS_RUN_ROOT", "").strip()):
            print("HATA: --from-hub yalnız --run-root ile koşar (üretim-koruması)")
            return 2
        if not (_from_hub / "clip.json").exists():
            print(f"HATA: from-hub clip.json yok: {_from_hub}")
            return 2
        _src_clip = json.loads((_from_hub / "clip.json").read_text(encoding="utf-8"))
        # video = KAYNAK DOSYA ADI (parse_filename TRT/başlığı addan çözer; dosya var olmayabilir)
        args.video = str(_from_hub / "source" / (_src_clip.get("filename") or _from_hub.name))
        os.environ["MITAS_FROM_HUB"] = "1"
        os.environ["MITAS_FROM_HUB_PATH"] = str(_from_hub.resolve())
        try:
            _parent_manifest = json.loads(
                (_from_hub / "run_manifest.json").read_text(encoding="utf-8"))
            _parent_run_id = str(_parent_manifest.get("run_id") or "").strip()
            if _parent_run_id:
                os.environ["MITAS_PARENT_RUN_ID"] = _parent_run_id
        except Exception:  # noqa: BLE001 — eski hub'da manifest olmayabilir; from-hub yine calisir
            pass
        os.environ["MITAS_JENERIK_DETECT"] = "0"          # detect video ister → kapalı (kill-switch)
        try:
            _src_durum = json.loads((_from_hub / "_DURUM.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            _src_durum = {}
        _fh_dursec = float(_src_durum.get("dur_sec") or 0.0)
        _fh_dur = _src_durum.get("dur", "—")
        if not _fh_dursec and isinstance(_fh_dur, str) and _fh_dur.count(":") == 2:
            try:  # "HH:MM:SS" → saniye
                _hh, _mm, _ss = (int(x) for x in _fh_dur.split(":"))
                _fh_dursec = _hh * 3600 + _mm * 60 + _ss
            except ValueError:
                pass
        if not _fh_dursec:  # son çare: çıkış-frame sayısından tahmin (fps=1.5, kuyruk 480s varsayımı)
            _nc = len(list((_from_hub / "frames" / "cikis").glob("*.png")))
            _fh_dursec = max(1800.0, (_nc / 1.5) + 900.0)
        os.environ["MITAS_FROM_HUB_SPECS"] = json.dumps({
            "res": _src_durum.get("res", "—"), "fps": "—",
            "dur": _fh_dur, "dur_sec": _fh_dursec})

    # İP-5: --run-root verildiyse env'i set edip kökleri YENİDEN bağla (import-anı çözümü ezilir).
    if args.run_root:
        os.environ["MITAS_RUN_ROOT"] = str(args.run_root)
    if os.environ.get("MITAS_RUN_ROOT", "").strip():
        _rebind_roots()
        print(f"[candidate] RUN_ROOT aktif: {os.environ['MITAS_RUN_ROOT']} "
              f"(DB={DB_ROOT} | export={EXPORT_ROOT}) — üretim köklerine YAZILMAZ")

    t_all = time.perf_counter()
    timings = {}
    video = Path(args.video)
    if not video.exists() and not _from_hub:
        print(f"HATA: video yok: {video}")
        return 2

    # === İP-1 (2026-07-11, plan rev.4): PREFLIGHT sağlık kapısı — HARD-FAIL. ===
    # Geçmişte ollama-deposu boşken 36 film "işlendi" sanıldı (sahte-KONTROL dalgası); bu kapı
    # o sınıfı koşu BAŞLAMADAN keser. Batch-modda (MITAS_BATCH_MODE=1) ek kural: tracked-ağaç
    # TEMİZ + tek-writer kilidi, bypass YOK. Tek-film geliştirmede MITAS_PREFLIGHT=0 kaçışı var.
    import run_manifest as _rm
    _batch_mode = os.environ.get("MITAS_BATCH_MODE", "").strip() == "1"
    try:
        _preflight_info = _rm.run_preflight(batch_mode=_batch_mode)
    except _rm.PreflightError as exc:
        print(f"PREFLIGHT-FAIL (koşu başlatılmadı): {exc}")
        log_event("preflight_fail", summary=str(exc)[:400], module="pipeline",
                  filename=video.name)
        return 3

    trt, title, prof_from_id, bolum = parse_filename(video)
    original = xml_original(video)              # XML <TITLE> → afiş orijinal ad (yabancı film)
    xml_role_map = xml_roles(video)             # XML rol listeleri → rol aklı ankrajı (yoksa {})
    tur_xml = xml_genre(video)                  # XML JT:CLASSIFICATION:EDIT_FMT_NAME → tür
    film_year = trt.split("-")[0] if trt else ""  # TRT katalog yılı (zayıf ayraç; afişte kadro birincil)
    raw_profile = (args.profile or "").strip().lower()
    if raw_profile in ("", "film_dizi", "filmdizi", "film/dizi", "auto"):
        # TEK 'Film/Dizi' profili → tip TRT 3. parselden otomatik (1→film, 0→dizi)
        profile = (prof_from_id or "film")
    else:
        profile = raw_profile
    is_film = profile.startswith("film") and profile != "film_dizi"
    content_profile = "film" if profile in ("film", "dizi") else (
        "bulten_haber" if profile in ("haber", "stt") else
        "belgesel" if profile == "belgesel" else
        "muzik_programi" if profile in ("muzik", "muzik_eglence") else "film")
    media_id = sanitize(video.stem)
    clip_id = media_id                            # internal ASCII id (event/master log/subprocess --media-id)
    # Klasör adı DATABASE düzeninde temiz: '<BAŞLIK> <TRT>' (ad önce, Türkçe korunur). clip_id AYRI kalır.
    clean = folder_name(title, trt, video.stem)
    dir_name = clean
    n = 2
    while (DB_ROOT / dir_name).exists():
        dir_name = f"{clean} {n}"; n += 1
    clip_dir = DB_ROOT / dir_name

    # ÖZEL-TÜR ERKEN TESPİT (Çağatay 2026-06-21): müzikal/belgesel/animasyon ARTIK atlanmaz —
    # tam künye üretilir, en sonda 'muzikal_animasyon_belgesel/' klasörüne toplanır. Sinyali ileri taşı.
    early_genre_class = genre_class(video, tur_xml)
    _PROFILE_GENRE = {"belgesel": "BELGESEL", "muzik": "MÜZİKAL",
                      "muzik_eglence": "MÜZİKAL", "animasyon": "ANİMASYON"}
    forced_special_genre = ""
    if early_genre_class in ("BELGESEL", "MÜZİKAL", "ANİMASYON"):
        forced_special_genre = early_genre_class
    elif profile in _PROFILE_GENRE:
        forced_special_genre = _PROFILE_GENRE[profile]
    # Geri-uyum: eski 'işlenmez/sil' davranışı yalnız MITAS_SKIP_SPECIAL_GENRE=1 ile (varsayılan KAPALI).
    if forced_special_genre and os.environ.get("MITAS_SKIP_SPECIAL_GENRE", "").strip().lower() in ("1", "true", "on", "yes"):
        return _skip_special_genre(
            video, clip_dir,
            media_id=media_id, trt=trt, title=title, profile=profile,
            tur_xml=tur_xml, genre_name=forced_special_genre,
            reason=f"özel tür {forced_special_genre}", stage="early_xml",
        )

    (clip_dir / "source").mkdir(parents=True, exist_ok=True)
    (clip_dir / "frames").mkdir(parents=True, exist_ok=True)
    (clip_dir / "ocr").mkdir(parents=True, exist_ok=True)
    (clip_dir / "asr").mkdir(parents=True, exist_ok=True)
    (clip_dir / "pdf").mkdir(parents=True, exist_ok=True)
    dbg.start_trace(clip_dir, clip_id=clip_id, title=title, profile=profile, video=video, trt_id=trt)
    # İP-1: koşu kimlik-kartı — "bu sonucu hangi kod/model/ayar üretti" her zaman cevaplı olsun.
    _manifest = _rm.build_manifest(video, profile, argv, preflight_info=_preflight_info)
    _rm.write_start(clip_dir, _manifest)
    print(f"[hub] {clip_dir}  profil={profile} trt={trt} baslik={title!r} run_id={_manifest['run_id']}")

    # === FROM-HUB: frames junction + ocr-kopyası (video offline; kaynak-hub salt-okunur) ===
    if _from_hub:
        args.no_copy_source = True
        # frames giris/cikis → mutlak-hedefli symlink (mitas_roots.link_hub_frames).
        # KÖK-SEBEP FIX (2026-07-30): eskiden inline `os.symlink(_src_f, ...)` göreli --from-hub'da
        # göreli/DANGLING link üretiyordu → 0 kare → sahte-MOTOR_YOK. Helper from_hub'ı mutlağa çevirir.
        _roots.link_hub_frames(_from_hub, clip_dir)
        _src_ocrs = sorted((d for d in (_from_hub / "ocr").glob("ocr-*")
                            if (d / "kunye.txt").exists() and not d.name.endswith("-fb")),
                           key=lambda d: d.stat().st_mtime)
        if _src_ocrs:  # en-yeni ocr işi kopyalanır → OCR adımı taze koşsa da referans hazır
            _dst_ocr = clip_dir / "ocr" / _src_ocrs[-1].name
            if not _dst_ocr.exists():
                shutil.copytree(_src_ocrs[-1], _dst_ocr)
        print(f"[from-hub] frames junction + ocr-kopya hazır ← {_from_hub.name}")

    # --- source kopya + clip.json ---
    size = (video.stat().st_size if video.exists()
            else int(_src_clip.get("size_bytes") or 0) if _from_hub else 0)
    if args.no_copy_source:
        source_path = video
    else:
        source_path = clip_dir / "source" / video.name
        if not source_path.exists():
            shutil.copy2(video, source_path)
    write_json(clip_dir / "clip.json", {
        "clip_id": clip_id, "media_id": media_id, "filename": video.name,
        "imported_at": now_iso(), "size_bytes": size, "source_path": str(source_path),
        "profile": profile, "trt_id": trt, "title": title, "bolum": bolum, "modules": {},
        "folder_name": dir_name, "content_hash": "", "tur": tur_xml,
    })
    log_event("media_imported", summary=f"{video.name} pipeline'a alindi ({size // (1024*1024)} MB, profil={profile}).",
              module="pipeline", media_id=media_id, filename=video.name, detail={"clip_id": clip_id, "profile": profile, "trt_id": trt})

    res = fps_s = dur = "—"
    dur_sec = 0.0
    giris_frames = clip_dir / "frames" / "giris"
    cikis_frames = clip_dir / "frames" / "cikis"
    cikis_jenerik_frames = clip_dir / "frames" / "cikis_jenerik"
    giris_jenerik_frames = clip_dir / "frames" / "giris_jenerik"
    jenerik_debug_root = clip_dir / "jenerik_debug"
    audio_path = clip_dir / "audio" / "audio16k.wav"
    _detect_changed = False   # SONUÇ-TEMELLİ YEDEK: detect penceresi sabit-varsayılandan saptı mı?
    dur_sec = 0.0
    _giris_start = 0.0        # GİRİŞ capture başlangıcı (kural: 0'dan DEĞİL, tespit edilen jenerik-başından)

    # ===== BLOK ÇÖZ (ffmpeg: specs + native frame + ses) =====
    t0 = time.perf_counter()
    try:
        res, fps_s, dur, dur_sec = ffprobe_specs(video)
        # GİRİŞ penceresi (sabit default; MITAS_CREDIT_DETECT=1 ise detect_both'tan dinamik güncellenir)
        head = min(args.ocr_head, dur_sec or args.ocr_head)
        _fixed_cik_start, _fixed_cik_len, _fixed_cik_expected = exit_frame_contract(
            dur_sec, args.ocr_tail, args.fps
        )
        _cik_start = _fixed_cik_start
        _cik_len = _fixed_cik_len
        nf_c = 0
        if dur_sec > (args.ocr_head + args.ocr_tail + 5):
            # JENERİK-SINIR TESPİTİ (flag MITAS_CREDIT_DETECT, default KAPALI; Çağatay 2026-06-14):
            # OpusCreditDetector detect_both() → GİRİŞ + ÇIKIŞ jeneriğini TEK cap geçişinde bulur.
            # GİRİŞ no-regress: head asla args.ocr_head(180s) altına inmez, gerekirse uzar (max 720s).
            # ÇIKIŞ no-regress: _cik_start = min(tespit−5s, eski-pencere) → asla eski pencerenin gerisine.
            # Fail-safe: detector kapalı/patlar/bulamaz → sabit pencereler (head ve _cik_start değişmez).
            # DEDEKTÖR SEÇİMİ: YENİ 4-tip jenerik dedektörü (MITAS_JENERIK_DETECT, default AÇIK) —
            # OCR-geriye start (çıkış) + OCR-ileri film-başı (giriş) + paralel; şema-uyumlu, fail-safe.
            # Eski OpusCreditDetector için MITAS_JENERIK_DETECT=0 + MITAS_CREDIT_DETECT=1.
            _use_jenerik = os.environ.get("MITAS_JENERIK_DETECT", "1").strip().lower() not in ("0", "false", "off", "no")
            _use_credit_old = os.environ.get("MITAS_CREDIT_DETECT", "").strip().lower() in ("1", "true", "on", "yes")
            if _use_jenerik or _use_credit_old:
                try:
                    # GÜVEN-EŞİĞİ (Çağatay 2026-06-15): detect normalde conf ≥ eşik ise pencereyi oynatır.
                    # Uzun/persistan scroll istisnası: bazı filmlerde ana cast jeneriğin başında, sabit son
                    # pencere ise yalnız teknik ekipte kalıyor. Düşük ama makul güvenli uzun scroll'u kabul et.
                    _DETECT_MINCONF = float(os.environ.get("MITAS_CREDIT_DETECT_MINCONF", "0.60") or 0.60)
                    _DETECT_LOWCONF = float(os.environ.get("MITAS_CREDIT_DETECT_LOWCONF_MINCONF", "0.45") or 0.45)
                    _DETECT_LOWSPAN = float(os.environ.get("MITAS_CREDIT_DETECT_LOWCONF_MIN_DUR", "180") or 180)
                    # KN-1 fix (Çağatay 2026-06-22, default AÇIK; kill-flag MITAS_CREDIT_DETECT_TIGHT_CLOSE=0):
                    # ÇIKIŞ no-regress `min(tespit−5, dur−240)` kuralı, kapanış jeneriği son 240s İÇİNDE
                    # başlayınca dedektörün hassas başlangıcını atıp sabit 240s kuyruğu seçiyordu → medyan
                    # ~157s footage çıkış penceresinin BAŞINA giriyordu. TIGHT_CLOSE iken min() YOK: hassas
                    # tespite güven (_cik_start=_ds). Fail-safe: _cik_start sabit-kuyruktan ERKEN olduğundan
                    # _detect_changed=True → daraltılmış pencere <30 OCR satırı verirse sabit kuyruk re-OCR'lanır.
                    _TIGHT_CLOSE = os.environ.get("MITAS_CREDIT_DETECT_TIGHT_CLOSE", "").strip().lower() not in ("0", "false", "off", "no")
                    if _use_jenerik:   # YENİ 4-tip dedektör (OCR-geriye + giriş film-başı + paralel)
                        _detect_cmd = [str(PY_OCR), str(HERE / "_jenerik_detect.py"),
                                       "--video", str(video), "--parallel"]
                    else:              # eski OpusCreditDetector (geri-uyum)
                        _detect_cmd = [str(PY_OCR), str(HERE / "_credit_detect.py"), "--video", str(video)]
                    _rcd, _outd, _errd = run(_detect_cmd, timeout=360)
                    _both = last_json(_outd) or {}
                    _opening = _both.get("opening") or {}
                    _closing = _both.get("closing") or {}

                    def _credit_span_seconds(obj):
                        try:
                            return max(0.0, float(obj.get("end_sec") or 0.0) - float(obj.get("start_sec") or 0.0))
                        except Exception:
                            return 0.0

                    def _accept_credit_detect(obj, conf):
                        if conf >= _DETECT_MINCONF:
                            return True, "normal"
                        span = _credit_span_seconds(obj)
                        if (obj.get("found") and str(obj.get("type") or "").lower() == "scroll"
                                and conf >= _DETECT_LOWCONF and span >= _DETECT_LOWSPAN):
                            return True, "uzun-scroll"
                        return False, ""

                    # --- GİRİŞ penceresi — GÜVEN ≥ eşik ise: 0'dan DEĞİL tespit edilen jenerik-BAŞINDAN başla
                    # (KURAL, Çağatay 2026-06-15: öncesi logo/cold-open footage → süpürme = gürültü). düşük güven → sabit ---
                    _op_conf = float(_opening.get("confidence") or 0.0)
                    _op_ok, _op_accept = _accept_credit_detect(_opening, _op_conf)
                    if _opening.get("found") and _opening.get("end_sec") is not None and _op_ok:
                        _new_head = max(args.ocr_head, float(_opening["end_sec"]) + 5.0)
                        _new_head = min(_new_head, 720.0)
                        head = min(_new_head, dur_sec or _new_head)
                        _giris_start = max(0.0, float(_opening.get("start_sec") or 0.0) - 5.0)   # 0'dan DEĞİL
                        log_event("credit_detect_opening",
                                  summary=f"{video.name}: GİRİŞ jenerik {_opening.get('type')} "
                                          f"@ {float(_opening.get('start_sec', 0)):.0f}s–{float(_opening['end_sec']):.0f}s "
                                          f"(conf {_op_conf:.3f}, kabul={_op_accept}) → pencere {_giris_start:.0f}s–{head:.0f}s",
                                  module="ocr", media_id=media_id, filename=video.name,
                                  detail={"clip_id": clip_id, "opening": _opening})
                    else:
                        _why = (f"düşük güven {_op_conf:.3f}<{_DETECT_MINCONF}"
                                if _opening.get("found") else "bulunamadı")
                        log_event("credit_detect_opening",
                                  summary=f"{video.name}: GİRİŞ jenerik {_why} — sabit head={head:.0f}s",
                                  module="ocr", media_id=media_id, filename=video.name,
                                  detail={"clip_id": clip_id, "opening": _opening})
                    # --- ÇIKIŞ penceresi — GÜVEN ≥ eşik ise: başlangıcı tespit-başına çek + tespit-SONUNDA bitir
                    # (KURAL, Çağatay 2026-06-15: film-sonuna GİTME → arası footage = gürültü). Eğer tespit yanılırsa
                    # (erken/kısa) → OCR satırı düşük → SONUÇ-TEMELLİ YEDEK eski sabit pencereyle re-OCR yapar (ağ).
                    _cl_conf = float(_closing.get("confidence") or 0.0)
                    _cl_ok, _cl_accept = _accept_credit_detect(_closing, _cl_conf)
                    # HATA #2 fix (Çağatay 2026-06-21): end_sec None ise tespit kabul edilmez — eskiden _ce=10s'e
                    # çöküp pencere 30s tabanına düşüyordu; artık sabit pencereye (fail-safe) gider.
                    _cl_has = bool(_closing.get("found") and _closing.get("start_sec") is not None
                                   and _closing.get("end_sec") is not None)
                    # DÜŞÜK-GÜVEN BİRLEŞTİRME (flag-kapılı, default KAPALI; Çağatay 2026-06-21): güven eşiğin
                    # ALTINDA ama alt-sınırın (0.40) ÜSTÜNDEyse tespit edilen jeneriği ATMA → sabit pencereyle
                    # BİRLEŞTİR (union, aralığın tamamı: baş tespit-başına çekilir, son film-sonuna uzar). Araya
                    # giren footage'ı CLIP bekçisi (CREDIT_MIN_RUN) eler → jenerik kaçmaz, footage gürültüsü düşük.
                    _LC_MERGE = os.environ.get("MITAS_CREDIT_DETECT_LOWCONF_MERGE", "").strip().lower() in ("1", "true", "on", "yes")
                    _LC_MERGE_MIN = float(os.environ.get("MITAS_CREDIT_DETECT_LOWCONF_MERGE_MINCONF", "0.40") or 0.40)
                    if _cl_has and _cl_ok:
                        _ds = max(0.0, float(_closing["start_sec"]) - 5.0)            # 5s emniyet payı
                        if _TIGHT_CLOSE:
                            _cik_start = _ds                                         # KN-1: hassas tespite güven (min YOK → footage-bloat'ı kes)
                        else:
                            _cik_start = min(_ds, _cik_start)                        # eski: asla eski-pencereden GEÇ başlama
                        # CLOSE-BACK (Çağatay 2026-06-23, flag MITAS_CREDIT_DETECT_CLOSE_BACK, default AKTİF):
                        # tespit-başı GEÇ olabilir (sondaki statik kartı bulur, ondan ÖNCEKİ scroll-başını = ANA
                        # KADRO bloğunu kaçırır → TIGHT_CLOSE o geç başlangıca güvenip kapanış başını keser).
                        # FOOTAGE-GÜVENLİ geri-uzatma: [dur−ocr_tail, _cik_start] probe çıkar → _close_back_scan
                        # has_text ile geriye 'KREDİ OLDUKÇA' uzat, ardışık footage'da DUR (blanket DEĞİL). FAIL-SAFE.
                        # Kapatmak için MITAS_CREDIT_DETECT_CLOSE_BACK=0.
                        if os.environ.get("MITAS_CREDIT_DETECT_CLOSE_BACK", "1").strip().lower() in ("1", "true", "on", "yes"):
                            try:
                                _cb_to = max(0.0, dur_sec - args.ocr_tail)
                                if _cb_to < _cik_start - 1.0:
                                    _pdir = clip_dir / "frames" / "_close_probe"
                                    extract_window(video, _pdir, prefix="p", fps=args.fps,
                                                   start=_cb_to, length=(_cik_start - _cb_to))
                                    _rcp, _outp, _errp = run([str(PY_OCR), str(HERE / "_close_back_scan.py"),
                                                              "--frames", str(_pdir)], timeout=180)
                                    _sj = last_json(_outp) or {}
                                    _eidx = _sj.get("earliest_credit_idx")
                                    _np = int(_sj.get("n_frames") or 0)
                                    if _eidx is not None and _np > 0:
                                        _new_start = _cb_to + float(_eidx) / args.fps
                                        if _cb_to <= _new_start < _cik_start:
                                            log_event("credit_detect_close_back",
                                                      summary=f"{video.name}: kapanış GERİ-UZATILDI {_cik_start:.0f}s→{_new_start:.0f}s "
                                                              f"(footage-güvenli, {_sj.get('credit_count')}/{_np} kredi-kare)",
                                                      module="ocr", media_id=media_id, filename=video.name,
                                                      detail={"clip_id": clip_id, "old_start": _cik_start,
                                                              "new_start": _new_start, "scan": _sj})
                                            _cik_start = _new_start
                                    shutil.rmtree(_pdir, ignore_errors=True)
                            except Exception as _cbe:  # noqa: BLE001 — FAIL-SAFE: _cik_start dokunulmaz
                                log_event("credit_detect_close_back_skip", level="warn",
                                          summary=f"{video.name}: kapanış geri-uzatma atlandı ({type(_cbe).__name__})",
                                          module="ocr", media_id=media_id, filename=video.name,
                                          detail={"clip_id": clip_id})
                        _ce = float(_closing.get("end_sec") or 0.0) + 10.0           # tespit edilen jenerik SONU +10s
                        _cik_end = min(dur_sec, max(_ce, _cik_start + 60.0))         # film-sonuna GİTME; en az 60s
                        _cik_len = _cik_end - _cik_start
                        log_event("credit_detect_closing",
                                  summary=f"{video.name}: ÇIKIŞ jenerik {_closing.get('type')} "
                                          f"@ {float(_closing['start_sec']):.0f}s–{float(_closing.get('end_sec') or 0):.0f}s "
                                          f"(conf {_cl_conf:.3f}, kabul={_cl_accept}) → pencere {_cik_start:.0f}s–{_cik_end:.0f}s",
                                  module="ocr", media_id=media_id, filename=video.name,
                                  detail={"clip_id": clip_id, "closing": _closing})
                    elif _LC_MERGE and _cl_has and (not _cl_ok) and _cl_conf >= _LC_MERGE_MIN:
                        # union: baş tespit-başına çek (erken olan kazanır), son film-sonuna uzat (sabit kuyruğu da kapsar)
                        _ds = max(0.0, float(_closing["start_sec"]) - 5.0)
                        _cik_start = min(_ds, _cik_start)
                        _cik_end = dur_sec
                        _cik_len = _cik_end - _cik_start
                        log_event("credit_detect_closing_merge",
                                  summary=f"{video.name}: ÇIKIŞ jenerik DÜŞÜK-GÜVEN BİRLEŞTİRME {_closing.get('type')} "
                                          f"@ {float(_closing['start_sec']):.0f}s–{float(_closing.get('end_sec') or 0):.0f}s "
                                          f"(conf {_cl_conf:.3f} ∈ [{_LC_MERGE_MIN:.2f},{_DETECT_MINCONF:.2f})) → union {_cik_start:.0f}s–{_cik_end:.0f}s",
                                  module="ocr", media_id=media_id, filename=video.name,
                                  detail={"clip_id": clip_id, "closing": _closing, "lowconf_merge": True})
                    else:
                        _why = (f"düşük güven {_cl_conf:.3f}<{_DETECT_MINCONF}"
                                if _closing.get("found") else "bulunamadı")
                        log_event("credit_detect_closing",
                                  summary=f"{video.name}: ÇIKIŞ jenerik {_why} — sabit pencere {_cik_start:.0f}s +{_cik_len:.0f}s",
                                  module="ocr", media_id=media_id, filename=video.name,
                                  detail={"clip_id": clip_id, "closing": _closing})
                except Exception as _de:  # noqa: BLE001 — fail-safe: sabit pencereler
                    log_event("credit_detect_skip", level="warn",
                              summary=f"{video.name}: credit-detect atlandı ({_de}) — sabit pencereler",
                              module="ocr", media_id=media_id, filename=video.name, detail={"clip_id": clip_id})
            # SONUÇ-TEMELLİ YEDEK bayrağı artık yalnız giriş penceresi içindir.
            # Çıkış `--ocr-tail × --fps` sözleşmesine aşağıda koşulsuz kilitlenir.
            _detect_changed = (abs(head - min(args.ocr_head, dur_sec or args.ocr_head)) > 0.5
                               or _giris_start > 0.5)

        # BAĞLAYICI ÇIKIŞ KARE SÖZLEŞMESİ:
        # Dedektör yalnız jenerik hakkında kanıt üretir; kullanıcının istediği ham
        # çıkış havuzunu daraltamaz. 480 sn × 1.5 fps ise sonuç tam 720 karedir.
        if (abs(_cik_start - _fixed_cik_start) > 0.001
                or abs(_cik_len - _fixed_cik_len) > 0.001):
            log_event(
                "exit_frame_contract_enforced",
                level="warn",
                summary=(
                    f"{video.name}: dedektor cikis penceresi {_cik_start:.3f}s +{_cik_len:.3f}s "
                    f"reddedildi; talimat {_fixed_cik_start:.3f}s +{_fixed_cik_len:.3f}s "
                    f"@ {args.fps:g} fps = {_fixed_cik_expected} kare."
                ),
                module="pipeline",
                media_id=media_id,
                filename=video.name,
                detail={
                    "clip_id": clip_id,
                    "detector_start": _cik_start,
                    "detector_length": _cik_len,
                    "required_start": _fixed_cik_start,
                    "required_length": _fixed_cik_len,
                    "required_fps": args.fps,
                    "required_frames": _fixed_cik_expected,
                },
            )
        _cik_start = _fixed_cik_start
        _cik_len = _fixed_cik_len
        # ── HIZLANDIRMA Faz-1 (2026-07-04, Sonnet KANITLI-GÜVENLİ): çıkış-frame + giriş-frame + ses
        # üçlüsü PARALEL. Kanıt: üçü de yalnız `video`yu okur (salt-okunur), FARKLI dizinlere yazar
        # (cikis_frames/giris_frames/audio_path), her extract kendi uuid-staged klasöründe çalışıp
        # os.replace ile taşır (çakışan yazma yok); TÜM tüketiciler (jenerik-havuzlar 1775+/1854+,
        # OCR, ASR, DİLİM-TAZELE) bu bloğun BİTİMİNDEN sonra. .result() sıralı alınır → ilk hata
        # aynen bugünkü gibi yükselir (FrameContractError dahil, davranış-özdeş). NVMe+32-çekirdek:
        # coz ~80-115s → en-yavaş-tekil-işe iner (~1.5-2.5x). MITAS_FFMPEG_EXTRACT_PARALLEL=0 kill-switch.
        _ffpar_on = os.environ.get("MITAS_FFMPEG_EXTRACT_PARALLEL", "1").strip().lower() not in ("0", "false", "off", "no")
        if _ffpar_on:
            import concurrent.futures as _cf
            with _cf.ThreadPoolExecutor(max_workers=3) as _ex:
                _fut_c = _ex.submit(extract_window, video, cikis_frames, prefix="c", fps=args.fps,
                                    start=_cik_start, length=_cik_len, expected_count=_fixed_cik_expected)
                _fut_g = _ex.submit(extract_window, video, giris_frames, prefix="g", fps=args.fps,
                                    start=_giris_start, length=max(1.0, head - _giris_start))
                _fut_a = _ex.submit(extract_audio, video, audio_path)
                nf_c = _fut_c.result()
                nf_g = _fut_g.result()
                ok_audio, aerr = _fut_a.result()
        else:
            nf_c = extract_window(
                video,
                cikis_frames,
                prefix="c",
                fps=args.fps,
                start=_cik_start,
                length=_cik_len,
                expected_count=_fixed_cik_expected,
            )
        log_event(
            "exit_frame_contract_verified",
            summary=(
                f"{video.name}: cikis frame sozlesmesi dogrulandi "
                f"({_fixed_cik_len:.3f}s × {args.fps:g} fps = {nf_c}/{_fixed_cik_expected})."
            ),
            module="pipeline",
            media_id=media_id,
            filename=video.name,
            detail={
                "clip_id": clip_id,
                "start": _cik_start,
                "length": _cik_len,
                "fps": args.fps,
                "expected_frames": _fixed_cik_expected,
                "actual_frames": nf_c,
            },
        )
        # GİRİŞ kareleri: _giris_start (0 = sabit; >0 = tespit edilen jenerik-başı) → head; KURAL: 0'dan başlama
        if not _ffpar_on:
            nf_g = extract_window(video, giris_frames, prefix="g", fps=args.fps,
                                  start=_giris_start, length=max(1.0, head - _giris_start))
            ok_audio, aerr = extract_audio(video, audio_path)
        timings["coz"] = round(time.perf_counter() - t0, 2)
        log_event("cozumleme_completed",
                  summary=f"{video.name}: {res}, {dur}, giris {nf_g} + cikis {nf_c} native kare, ses={'var' if ok_audio else 'YOK'} ({timings['coz']} sn).",
                  module="pipeline", media_id=media_id, filename=video.name, duration_seconds=timings["coz"],
                  detail={"clip_id": clip_id, "resolution": res, "fps": fps_s, "duration": dur,
                          "giris_frames": nf_g, "cikis_frames": nf_c, "audio_ok": ok_audio})
    except Exception as exc:  # noqa: BLE001
        timings["coz"] = round(time.perf_counter() - t0, 2)
        log_event("cozumleme_failed", level="error", summary=f"ÇÖZ blogu hata: {exc}",
                  module="pipeline", media_id=media_id, filename=video.name, error=str(exc), detail={"clip_id": clip_id})
        if isinstance(exc, FrameContractError):
            raise

    # ===== PARALEL JENERIK HAVUZU (test/provenance): frames/cikis -> frames/cikis_jenerik =====
    # Ana OneOCR akışı bu havuzu KULLANMAZ; normal frames/giris + frames/cikis okumaya devam eder.
    # GLM/VL/master debug işleri bu alt havuzdan beslenecek. Fail-safe: hata pipeline'ı bozmaz.
    # HAVUZ-PARALEL (hız #1, 2026-07-05): havuzlar frames/{giris,cikis}'i SALT-OKUR ve ayrık
    # klasörlere yazar (_pipe_ocr kaynak kare SİLMEZ) → OCR∥ASR ile güvenle örtüşür. Paralel modda
    # burada yalnız Popen başlatılır; TOPLAMA ASR-toplamadan sonra, ilk tüketiciden (jdebug/master-
    # compose) önce. Kapatma: MITAS_POOL_PARALLEL=0 → birebir eski sıralı davranış.
    _pp_par = os.environ.get("MITAS_POOL_PARALLEL", "1").strip().lower() not in ("0", "false", "off", "no")
    _jp_proc = _gjp_proc = None
    _jp_cmd = None
    t_jp = t_gjp = _t_jp_wall = _t_gjp_wall = None
    # stdout DOSYAYA (hakem bulgusu, 2026-07-05): havuzun final JSON'u (copied_files listesi,
    # 50-170KB) Windows'un 8KB anon-pipe tamponunu aşıyor → child print'te toplamaya kadar bloke
    # kalıp GPU/RAM'i pencere boyunca rehin tutuyordu. Dosyaya yazınca iş bitince saniyeler içinde
    # exit eder; TOPLAMA JSON'u dosyadan okur.
    _jp_outf = jenerik_debug_root / "pool_stdout.log"
    _jp_errf = jenerik_debug_root / "pool_stderr.log"
    _gjp_outf = jenerik_debug_root / "giris_pool_stdout.log"
    _gjp_errf = jenerik_debug_root / "giris_pool_stderr.log"
    _jpool_on = os.environ.get("MITAS_JENERIK_PARALLEL_POOL", "1").strip().lower() not in ("0", "false", "off", "no")
    if _jpool_on and not args.no_ocr:
        t_jp = time.perf_counter()
        try:
            _jp_cmd = [str(PY_OCR), str(HERE / "_jenerik_pool.py"),
                       "--frames", str(cikis_frames),
                       "--pool", str(cikis_jenerik_frames),
                       "--debug-root", str(jenerik_debug_root)]
            if os.environ.get("MITAS_JENERIK_DEBUG_SHEET", "").strip().lower() in ("1", "true", "on", "yes"):
                _jp_cmd.append("--debug-sheet")
            if _pp_par:
                # HAVUZ-PARALEL v2 (2026-07-05 gece, kök-kazı): çıkış-havuz LANSMANI buradan
                # ASR-toplama SONRASINA taşındı. Kanıt: 0439+0289'da child spawn-anında öldü
                # (stdout/stderr 0 bayt = commit-tükenmesi, error-1455 ailesi) — ASR'ın CUDA/commit
                # TEPE penceresine paddle'lı child bindirmek güvensiz. Yeni pencere: LLM/v4/pdf
                # kuyruğu (gemma-resident + havuz birlikteliği eski seri akışta zaten kanıtlı).
                pass
            else:
                _rcjp, _outjp, _errjp = run(
                    _jp_cmd,
                    timeout=int(os.environ.get("MITAS_JENERIK_POOL_TIMEOUT", "900") or 900),
                )
                _jjp = last_json(_outjp) or {}
                if not cikis_jenerik_frames.exists():
                    cikis_jenerik_frames.mkdir(parents=True, exist_ok=True)
                timings["jenerik_pool"] = round(time.perf_counter() - t_jp, 2)
                log_event("jenerik_pool_completed",
                          level="info" if _jjp.get("status") != "error" else "warn",
                          summary=f"{video.name}: paralel jenerik havuzu {cikis_jenerik_frames.name} "
                                  f"status={_jjp.get('status')} frame={_jjp.get('pool_frames', 0)} "
                                  f"({timings['jenerik_pool']} sn).",
                          module="jenerik-pool", media_id=media_id, filename=video.name,
                          duration_seconds=timings["jenerik_pool"],
                          detail={"clip_id": clip_id, "pool": str(cikis_jenerik_frames),
                                  "result": _jjp, "stderr": (_errjp or "")[-300:] if _rcjp else None})
        except Exception as _jpe:  # noqa: BLE001
            try:
                cikis_jenerik_frames.mkdir(parents=True, exist_ok=True)
                (jenerik_debug_root / "errors.jsonl").parent.mkdir(parents=True, exist_ok=True)
                with (jenerik_debug_root / "errors.jsonl").open("a", encoding="utf-8") as _eh:
                    _eh.write(json.dumps({"ts": now_iso(), "stage": "pool", "error": str(_jpe)[:500]},
                                         ensure_ascii=False) + "\n")
            except Exception:
                pass
            log_event("jenerik_pool_failed", level="warn",
                      summary=f"{video.name}: paralel jenerik havuzu atlandı ({type(_jpe).__name__}).",
                      module="jenerik-pool", media_id=media_id, filename=video.name,
                      error=str(_jpe)[:300], detail={"clip_id": clip_id})

    # ===== ÇIKIŞ YEDEK HAVUZU (jenerik bulunamazsa): frames/cikis -> frames/cikis_yazi =====
    # Çağatay 2026-06-29: credit_detect çıkış jeneriğini bulamayınca cikis_jenerik BOŞ kalır. Fikir: o filmlerde
    # giriş-mantığıyla yedek havuz kur → VL'e temiz girdi. AYRI klasör (cikis_yazi); otorite cikis_jenerik'te kalır;
    # master'a BESLENMEZ (master_png_monitor cikis_yazi'yi kullanmaz — yalnız VL içindir).
    # DEFAULT-OFF: gerçek-test (GLENN MILLER tabela / SOĞUK SUYA 'FIN', 2026-06-29) gösterdi ki boş-çıkış filmleri
    # GENELDE gerçekten künyesiz (footage/sahne-yazısı/epilog) → fallback kredi değil sahne-yazısı topluyor.
    # Yalnız detektörün GERÇEK kredi-kaçırdığı nadir filmde değerli; güvenli kullanım için kalite-kapısı + VL-doğrulama
    # şart. Açmak için MITAS_CIKIS_FALLBACK_POOL=1.
    _cfb_on = os.environ.get("MITAS_CIKIS_FALLBACK_POOL", "0").strip().lower() in ("1", "true", "on", "yes")

    def _cikis_fallback_pool():
        # HAVUZ-PARALEL notu: boşluk kontrolü cikis_jenerik havuzu TAMAMLANDIKTAN sonra anlamlı —
        # sıralı modda buradan hemen, paralel modda TOPLAMA bloğundan çağrılır.
        if not (_cfb_on and not args.no_ocr):
            return
        _cikis_pool_empty = not (cikis_jenerik_frames.exists() and any(cikis_jenerik_frames.glob("*.png")))
        if not (_cikis_pool_empty and cikis_frames.exists() and any(cikis_frames.glob("*.png"))):
            return
        t_cfb = time.perf_counter()
        try:
            _cfb_cmd = [str(PY_OCR), str(HERE / "giris_jenerik_havuzu.py"),
                        "--frames", str(cikis_frames), "--pool-name", "cikis_yazi"]
            _rccfb, _outcfb, _errcfb = run(
                _cfb_cmd, timeout=int(os.environ.get("MITAS_CIKIS_FALLBACK_TIMEOUT", "900") or 900))
            _cfj = last_json(_outcfb) or {}
            timings["cikis_fallback_pool"] = round(time.perf_counter() - t_cfb, 2)
            log_event("cikis_fallback_pool_completed",
                      level="info" if _cfj.get("status") not in ("error", None) else "warn",
                      summary=f"{video.name}: çıkış jeneriği bulunamadı → YEDEK havuz cikis_yazi "
                              f"status={_cfj.get('status')} havuz={_cfj.get('total_dedup_representatives', 0)} "
                              f"({timings['cikis_fallback_pool']} sn).",
                      module="cikis-fallback-pool", media_id=media_id, filename=video.name,
                      duration_seconds=timings["cikis_fallback_pool"],
                      detail={"clip_id": clip_id, "pool": str(clip_dir / "frames" / "cikis_yazi"),
                              "result": _cfj, "stderr": (_errcfb or "")[-300:] if _rccfb else None})
        except Exception as _cfbe:  # noqa: BLE001
            log_event("cikis_fallback_pool_failed", level="warn",
                      summary=f"{video.name}: çıkış yedek havuzu atlandı ({type(_cfbe).__name__}).",
                      module="cikis-fallback-pool", media_id=media_id, filename=video.name,
                      error=str(_cfbe)[:300], detail={"clip_id": clip_id})

    if not _pp_par:
        _cikis_fallback_pool()

    # ===== GİRİŞ JENERİK HAVUZU (yazı-varlığı seçimi): frames/giris -> frames/giris_jenerik =====
    # cikis_jenerik'e PARALEL (Çağatay 2026-06-29): giriş karelerinden YAZI-olan (altyazı hariç) kareleri
    # OneOCR ile seçip giris_jenerik havuzuna kopyalar + aynı-yazı dedup. master-PNG bu havuzdan üretilir.
    # Fail-safe: hata pipeline'ı bozmaz. Kapatma: MITAS_GIRIS_JENERIK_POOL=0.
    _gjpool_on = os.environ.get("MITAS_GIRIS_JENERIK_POOL", "1").strip().lower() not in ("0", "false", "off", "no")
    if _gjpool_on and not args.no_ocr and giris_frames.exists():
        t_gjp = time.perf_counter()
        try:
            _gjp_cmd = [str(PY_OCR), str(HERE / "giris_jenerik_havuzu.py"),
                        "--frames", str(giris_frames)]
            if _pp_par:
                jenerik_debug_root.mkdir(parents=True, exist_ok=True)
                _t_gjp_wall = time.time()
                with open(_gjp_outf, "w", encoding="utf-8", errors="replace") as _fo, \
                        open(_gjp_errf, "w", encoding="utf-8", errors="replace") as _fe:
                    _gjp_proc = subprocess.Popen(_gjp_cmd, stdout=_fo, stderr=_fe)
            else:
                _rcgjp, _outgjp, _errgjp = run(
                    _gjp_cmd,
                    timeout=int(os.environ.get("MITAS_GIRIS_JENERIK_POOL_TIMEOUT", "900") or 900),
                )
                _gjj = last_json(_outgjp) or {}
                timings["giris_jenerik_pool"] = round(time.perf_counter() - t_gjp, 2)
                log_event("giris_jenerik_pool_completed",
                          level="info" if _gjj.get("status") not in ("error", None) else "warn",
                          summary=f"{video.name}: giriş jenerik havuzu {giris_jenerik_frames.name} "
                                  f"status={_gjj.get('status')} kept={_gjj.get('total_kept', 0)} "
                                  f"rep={_gjj.get('total_dedup_representatives', 0)} "
                                  f"({timings['giris_jenerik_pool']} sn).",
                          module="giris-jenerik-pool", media_id=media_id, filename=video.name,
                          duration_seconds=timings["giris_jenerik_pool"],
                          detail={"clip_id": clip_id, "pool": str(giris_jenerik_frames),
                                  "result": _gjj, "stderr": (_errgjp or "")[-300:] if _rcgjp else None})
        except Exception as _gjpe:  # noqa: BLE001
            log_event("giris_jenerik_pool_failed", level="warn",
                      summary=f"{video.name}: giriş jenerik havuzu atlandı ({type(_gjpe).__name__}).",
                      module="giris-jenerik-pool", media_id=media_id, filename=video.name,
                      error=str(_gjpe)[:300], detail={"clip_id": clip_id})

    # ===== WEB-ISITICI (hız #2+#3, 2026-07-05): kimlik/afiş URL'lerini boş pencerede ön-ısıt =====
    # Ateşle-ve-unut: sonucu BEKLENMEZ, film klasörüne dokunmaz, yalnız cache/web'i doldurur
    # (web_cache.py). Gerçek karar mantığı (poster_fetch / web_identity / credit_identity)
    # DEĞİŞMEDİ — aynı URL'ler v4 aşamasında diskten döner. Kapatma: MITAS_WEB_ISIT=0.
    if (os.environ.get("MITAS_WEB_ISIT", "1").strip().lower() not in ("0", "false", "off", "no")
            and profile in ("film", "dizi") and title):
        try:
            subprocess.Popen([str(PY_PDF), str(HERE / "web_isit.py"), "--title", str(title),
                              "--original", str(original or ""),
                              "--year", str(film_year or "")],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log_event("web_isit_started",
                      summary=f"{video.name}: web-ısıtıcı ateşlendi (kimlik/afiş URL ön-yükleme).",
                      module="pipeline", media_id=media_id, filename=video.name,
                      detail={"clip_id": clip_id, "title": title, "year": film_year})
        except Exception as _wie:  # noqa: BLE001 — ısıtıcı pipeline'ı ASLA bozmaz
            log_event("web_isit_failed", level="warn",
                      summary=f"{video.name}: web-ısıtıcı başlatılamadı ({type(_wie).__name__}).",
                      module="pipeline", media_id=media_id, filename=video.name,
                      error=str(_wie)[:200], detail={"clip_id": clip_id})

    # ===== BLOK OCR + ASR (paralel) =====
    ocr_bucket = "ATLANDI"
    ocr_lines = 0
    ocr_job = f"ocr-{uuid4().hex[:8]}"
    ocr_out = clip_dir / "ocr" / ocr_job
    kunye_path = ocr_out / "kunye.txt"
    asr_status = "ATLANDI"
    asr_job = f"asr-{uuid4().hex[:8]}"
    asr_out = clip_dir / "asr" / asr_job / "run"
    asr_info = {}

    # OCR komutu hazırla
    ocr_proc = None
    t_ocr = None
    # Q1 (from-hub reuse, Çağatay 2026-07-30): hub'ın GUVENILIR OCR'ı yukarıda kopyalandı; --force-ocr
    # YOKSA taze OCR KOŞMA → from-hub candidate koşusu bir daha sahte-MOTOR_YOK/regresyon üretmez +
    # ~10x hız. OCR/pipeline değişikliği test edilecekse --force-ocr ile taze koşulur. Karar tek-kaynaktan
    # (_roots.should_reuse_hub_ocr: from-hub + not force + kullanılabilir kopya OCR var).
    if _roots.should_reuse_hub_ocr(_from_hub, args.force_ocr, clip_dir):
        _reused_kunye = Path(_roots.find_usable_ocr(str(clip_dir)))
        ocr_out = _reused_kunye.parent
        ocr_job = ocr_out.name
        kunye_path = _reused_kunye
        try:
            _rs = json.loads((ocr_out / "ocr_summary.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — summary yok/bozuk → satır say
            _rs = {}
        ocr_bucket = _rs.get("bucket", "GUVENILIR")
        ocr_lines = int(_rs.get("kunye_line_count") or sum(
            1 for _l in kunye_path.read_text(encoding="utf-8", errors="replace").splitlines() if _l.strip()))
        timings["ocr"] = 0.0
        update_clip_module(clip_dir, "ocr", "done", ocr_job)
        log_event("ocr_reused",
                  summary=f"{video.name}: from-hub OCR yeniden kullanıldı ({ocr_lines} satır, "
                          f"bucket={ocr_bucket}) — taze OCR atlandı (--force-ocr ile koşulur).",
                  module="ocr", media_id=media_id, filename=video.name, job_id=ocr_job,
                  detail={"clip_id": clip_id, "bucket": ocr_bucket, "lines": ocr_lines, "reused": True})
    elif not args.no_ocr:
        frame_dirs = [str(giris_frames)]
        if cikis_frames.exists() and any(cikis_frames.glob("*.png")):
            frame_dirs.append(str(cikis_frames))
        # HİBRİT OKUMA (Çağatay 2026-07-31 akşam): Paddle okuma kalitesi güvenilmez
        # ('CO SUBBING' ×5 bozulma vakası) → ana yol Messi(frame)+İbra(master)+birleşim,
        # okuyucu deepseek. _pipe_hibrit_okuma.py, _pipe_ocr ile AYNI CLI/çıktı/JSON
        # sözleşmesini taşır; içinde Paddle FAIL-SAFE'i var (çökerse yüksek sesle düşer).
        # Kill-switch: MITAS_OKUMA_MOTORU=paddle → eski yol birebir.
        _okuma_motoru = os.environ.get("MITAS_OKUMA_MOTORU", "hibrit").strip().lower()
        _okuma_betik = "_pipe_ocr.py" if _okuma_motoru == "paddle" else "_pipe_hibrit_okuma.py"
        ocr_cmd = [str(PY_OCR), str(HERE / _okuma_betik), "--frames", *frame_dirs,
                   "--out", str(ocr_out), "--profile", profile]
        dbg.emit("ocr", "stage_started",
                 subject={"field": "ocr_job", "after": ocr_job, "reason": "OCR subprocess started"},
                 evidence={"frame_dirs": frame_dirs, "profile": profile},
                 source={"module": "scripts/mitas_pipeline.py", "input_paths": frame_dirs,
                         "output_paths": [str(ocr_out)]})
        log_event("ocr_started", summary=f"{video.name} icin OCR kunye basladi.",
                  module="ocr", media_id=media_id, filename=video.name, job_id=ocr_job, detail={"clip_id": clip_id})
        ocr_proc = subprocess.Popen(ocr_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace")
        t_ocr = time.perf_counter()

    # ASR komutu hazırla ve başlat
    asr_proc = None
    t_asr = None
    # === ASR KALICI DEVRE-DIŞI (Çağatay 2026-07-11): test/kalite-ölçüm koşularında ASR ===
    # tamamen ayrı bir işlemdir, frame-okumayla (OCR/künye) İLGİSİ YOK → boşa zaman+token harcamasın.
    # İki tetik (aksi emre kadar): sentinel dosya E:\MITAS\ASR_KAPALI.flag VEYA MITAS_DISABLE_ASR=1.
    # Yeniden açmak için: dosyayı sil / env'i kaldır. (--no-asr tek-koşu; bu KALICI kill-switch.)
    _asr_kapali = ((PROJECT_ROOT / "ASR_KAPALI.flag").exists()
                   or os.environ.get("MITAS_DISABLE_ASR", "").strip().lower()
                   in ("1", "true", "on", "yes"))
    if _asr_kapali and not args.no_asr:
        args.no_asr = True
        print("[ASR] KALICI DEVRE-DIŞI (ASR_KAPALI.flag/MITAS_DISABLE_ASR) — özet/transkript atlanır")
    if not args.no_asr:
        _pa = PROFILE_ASR.get(profile)
        # KRİTİK: auto-language'da _pipe_asr'e VİDEO ver (downmix değil). Kanal-LID (MMS-LID) +
        # Kürtçe-atla + internet-özet ANCAK videoyla çalışır; audio16k.wav verilirse _pipe_asr
        # LID'i atlar (suffix==.wav) -> bu özellikler ÖLÜR (B-1 ölü-nokta). Sabit-dil profilde wav yeter.
        _auto = bool(_pa and _pa.get("lean") and _pa.get("language") == "auto")
        asr_in = video if _auto else (audio_path if audio_path.exists() else video)
        asr_cmd = [str(PY_ASR), str(HERE / "_pipe_asr.py"), "--input", str(asr_in),
                   "--out", str(asr_out), "--media-id", media_id, "--job-id", asr_job,
                   "--content-profile", content_profile]
        if _pa and _pa.get("lean"):
            asr_cmd += ["--lean", "--model", _pa["model"],
                        "--beam-size", str(_pa["beam_size"]), "--vad", _pa["vad"]]
            if _pa.get("language") == "auto":
                asr_cmd += ["--auto-language"]
            elif _pa.get("language"):
                asr_cmd += ["--language", _pa["language"]]
        if args.asr_max_seconds and args.asr_max_seconds > 0:
            asr_cmd += ["--max-seconds", str(args.asr_max_seconds)]
        # C6 FIX (2026-06-22): LID TR-veto — menşei Türkçe olan filmde Kürtçe yanlış tespiti engelle.
        # Menşei: original (yabancı orijinal ad) boş VEYA title ile aynıysa → yerli Türkçe yapım.
        # _pipe_asr --tr-provenance alınca language=="ku" + TR-LID-oyu>0 ise TR'ye döner.
        if os.environ.get("MITAS_LID_TR_VETO", "1").strip().lower() not in ("0", "false", "off", "no"):
            import re as _re
            _lid_on = _re.sub(r"[^a-z0-9]", "", (original or "").lower())
            _lid_tn = _re.sub(r"[^a-z0-9]", "", (title or "").lower())
            if (not _lid_on) or (_lid_on == _lid_tn):
                asr_cmd += ["--tr-provenance"]
        log_event("asr_started", summary=f"{video.name} icin ASR basladi (profil={content_profile}).",
                  module="asr", media_id=media_id, filename=video.name, job_id=asr_job, detail={"clip_id": clip_id, "content_profile": content_profile})
        # ASR-ÖN-SÜBAP (2026-07-06 gece, kitlesel-ASR-ölümü fixi): sübabı çocuğa bırakmak GEÇ —
        # commit-tavanı doygunken (186GB; gece 1.3-2GB'a düştü) ASR çocuğu CT2/CUDA DLL import
        # ANINDA WinError-1455 ile ölüyor (20:31'den beri 15/15 film, stderr boş, ~14sn). Ebeveyn
        # spawn'dan ÖNCE resident LLM'i (31b/26b, ~24GB commit) tahliye eder ve commit-boşluğu
        # bekler (maks 90sn) — sonra doğurur. FAIL-SAFE: her hata sessiz geçer, ASR yine başlar.
        # Kill-switch: MITAS_ASR_PRE_VALVE=0. Çocuk-içi sübap da durur (çifte-tahliye zararsız).
        if os.environ.get("MITAS_ASR_PRE_VALVE", "1").strip().lower() not in ("0", "false", "off", "no"):
            try:
                _oll_v = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434").rstrip("/")
                for _mv in ("gemma-4-31b-it-qat-vision:latest", "gemma4:26b"):
                    try:
                        urllib.request.urlopen(urllib.request.Request(
                            _oll_v + "/api/generate",
                            data=json.dumps({"model": _mv, "keep_alive": 0}).encode("utf-8"),
                            headers={"Content-Type": "application/json"}), timeout=15).read()
                    except Exception:  # noqa: BLE001 — model yüklü değil/hata: sonrakine geç
                        pass
                if os.name == "nt":
                    import ctypes as _ct

                    class _MSX(_ct.Structure):
                        _fields_ = ([("dwLength", _ct.c_ulong), ("dwMemoryLoad", _ct.c_ulong)]
                                    + [(_n, _ct.c_ulonglong) for _n in
                                       ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile",
                                        "ullAvailPageFile", "ullTotalVirtual", "ullAvailVirtual",
                                        "ullAvailExtendedVirtual")])

                    def _commit_bos_gb():
                        _m = _MSX(); _m.dwLength = _ct.sizeof(_MSX)
                        _ct.windll.kernel32.GlobalMemoryStatusEx(_ct.byref(_m))
                        return _m.ullAvailPageFile / 2**30
                else:
                    # Linux geçişi 2026-07-17: windll yok → sübap sessizce hiç çalışmıyordu.
                    # Commit-boşluğu karşılığı: MemAvailable + SwapFree (/proc/meminfo, kB→GB).
                    def _commit_bos_gb():
                        _mi = {}
                        with open("/proc/meminfo", encoding="ascii") as _f:
                            for _ln in _f:
                                _k, _, _rest = _ln.partition(":")
                                _mi[_k] = int(_rest.split()[0])
                        return (_mi.get("MemAvailable", 0) + _mi.get("SwapFree", 0)) / 2**20

                _hedef = float(os.environ.get("MITAS_ASR_MIN_COMMIT_GB", "8") or 8)
                _t_v = time.perf_counter()
                _bos = _commit_bos_gb()
                while _bos < _hedef and (time.perf_counter() - _t_v) < 90:
                    time.sleep(5)
                    _bos = _commit_bos_gb()
                log_event("asr_pre_valve",
                          summary=f"{video.name}: ASR-ön-sübap — LLM tahliye + commit-boş "
                                  f"{_bos:.1f} GB (hedef ≥{_hedef:.0f}, bekleme {time.perf_counter()-_t_v:.0f} sn).",
                          module="asr", media_id=media_id, filename=video.name,
                          detail={"clip_id": clip_id, "commit_bos_gb": round(_bos, 1)})
            except Exception:  # noqa: BLE001 — ön-sübap ASLA ASR'yi engellemez
                pass
        asr_proc = subprocess.Popen(asr_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace")
        t_asr = time.perf_counter()

    # OCR sonucunu topla
    if ocr_proc is not None:
        try:
            out, err = ocr_proc.communicate(timeout=OCR_TIMEOUT)
            rc = ocr_proc.returncode
            j = last_json(out) or {}
            ocr_bucket = j.get("bucket", "HATA")
            ocr_lines = int(j.get("kunye_line_count") or 0)
            paddle_lines = int(j.get("paddle_line_count") or 0)
            timings["ocr"] = round(time.perf_counter() - t_ocr, 2)
            st = j.get("status", "failed")
            update_clip_module(clip_dir, "ocr", "done" if st == "done" else "partial", ocr_job)
            _paddle_info = f" | Paddle {paddle_lines} satir" if paddle_lines else ""
            log_event("ocr_completed" if st == "done" else "ocr_partial",
                      level="info" if st == "done" else "warn",
                      summary=f"{video.name}: OCR kunye {ocr_lines} satir{_paddle_info}, bucket={ocr_bucket}, motor={j.get('engine')} ({timings['ocr']} sn).",
                      module="ocr", media_id=media_id, filename=video.name, job_id=ocr_job, duration_seconds=timings["ocr"],
                      detail={"clip_id": clip_id, "bucket": ocr_bucket, "lines": ocr_lines, "paddle_lines": paddle_lines, "engine": j.get("engine"), "stderr": err[-300:] if rc else None})
            dbg.emit("ocr", "stage_completed",
                     status="ok" if st == "done" else "warn",
                     duration_ms=timings["ocr"] * 1000,
                     subject={"field": "kunye", "after": str(kunye_path), "reason": f"bucket={ocr_bucket}"},
                     evidence={"bucket": ocr_bucket, "lines": ocr_lines, "paddle_lines": paddle_lines,
                               "engine": j.get("engine"), "summary_path": j.get("summary_path")},
                     source={"module": "scripts/mitas_pipeline.py", "input_paths": frame_dirs,
                             "output_paths": [str(kunye_path), str(j.get("summary_path") or "")]})
        except Exception as exc:  # noqa: BLE001
            timings["ocr"] = round(time.perf_counter() - (t_ocr or time.perf_counter()), 2)
            ocr_bucket = "HATA"
            try:
                ocr_proc.kill()
                ocr_proc.communicate(timeout=10)   # pipe drenaji + reaping (zombie/handle birakma)
            except Exception:  # noqa: BLE001
                pass
            update_clip_module(clip_dir, "ocr", "failed", ocr_job)
            log_event("ocr_failed", level="error", summary=f"OCR blogu hata: {exc}",
                      module="ocr", media_id=media_id, filename=video.name, job_id=ocr_job, error=str(exc), detail={"clip_id": clip_id})
            dbg.emit("ocr", "stage_completed", status="error", duration_ms=timings["ocr"] * 1000,
                     subject={"field": "ocr_job", "after": ocr_job, "reason": "OCR subprocess failed"},
                     evidence={"bucket": ocr_bucket}, error=str(exc),
                     source={"module": "scripts/mitas_pipeline.py", "input_paths": frame_dirs,
                             "output_paths": [str(ocr_out)]})

    # ===== SONUÇ-TEMELLİ YEDEK (Çağatay 2026-06-15): detect-penceresi OCR'ı düşürdüyse re-OCR =====
    # detect pencereyi SABİT-varsayılandan saptırdı VE OCR satırı şüpheli az (<eşik) → eski sabit
    # pencerelerle (giriş 0–head + çıkış son-tail) YENİDEN çıkar+OCR; ÇOK-satırlı sonucu TUT.
    # VL'den ÖNCE çalışır: 35B'ye İYİ METİN ver (oyuncu-hatalı VL'e hiç düşmesin). Güvene değil ÇIKAN
    # sonuca bakar → yüksek-güvenli detect mis-fire'ını bile yakalar. FAIL-SAFE: hata → detect sonucu.
    # ASR hâlâ paralel koşuyor (ayrı subprocess) → re-OCR onunla örtüşür, ek bekleme yok.
    if (ocr_proc is not None and not args.no_ocr and _detect_changed
            and dur_sec and dur_sec > (args.ocr_head + args.ocr_tail + 5)):
        _MIN_OCR_LINES = int(os.environ.get("MITAS_OCR_MIN_LINES", "30") or 30)
        if ocr_lines < _MIN_OCR_LINES:
            try:
                _fb_gir = clip_dir / "frames" / "giris_fb"
                _fb_cik = clip_dir / "frames" / "cikis_fb"
                _fb_head = min(args.ocr_head, dur_sec)
                _fb_cs = max(0.0, dur_sec - args.ocr_tail)
                extract_window(video, _fb_gir, prefix="g", fps=args.fps, start=0, length=_fb_head)
                extract_window(video, _fb_cik, prefix="c", fps=args.fps, start=_fb_cs, length=args.ocr_tail)
                _fb_dirs = [str(_fb_gir)]
                if _fb_cik.exists() and any(_fb_cik.glob("*.png")):
                    _fb_dirs.append(str(_fb_cik))
                _fb_out = clip_dir / "ocr" / f"{ocr_job}-fb"
                _rcfb, _ofb, _efb = run([str(PY_OCR), str(HERE / "_pipe_ocr.py"),
                                         "--frames", *_fb_dirs, "--out", str(_fb_out),
                                         "--profile", profile], timeout=OCR_TIMEOUT)
                _jfb = last_json(_ofb) or {}
                _fb_lines = int(_jfb.get("kunye_line_count") or 0)
                if _fb_lines > ocr_lines:
                    ocr_out = _fb_out
                    kunye_path = ocr_out / "kunye.txt"
                    ocr_bucket = _jfb.get("bucket", ocr_bucket)
                    log_event("ocr_fallback_default", level="warn",
                              summary=f"{video.name}: detect-OCR {ocr_lines} satır (<{_MIN_OCR_LINES}) → "
                                      f"sabit-pencere re-OCR {_fb_lines} satır KULLANILDI (detect mis-fire yakalandı).",
                              module="ocr", media_id=media_id, filename=video.name, job_id=ocr_job,
                              detail={"clip_id": clip_id, "detect_lines": ocr_lines, "fallback_lines": _fb_lines})
                    ocr_lines = _fb_lines
                else:
                    log_event("ocr_fallback_default", level="info",
                              summary=f"{video.name}: sabit-pencere re-OCR {_fb_lines} ≤ detect {ocr_lines} → detect sonucu korundu.",
                              module="ocr", media_id=media_id, filename=video.name, job_id=ocr_job,
                              detail={"clip_id": clip_id, "detect_lines": ocr_lines, "fallback_lines": _fb_lines})
            except Exception as _fbe:  # noqa: BLE001 — yedek pipeline'ı ASLA bozmaz
                log_event("ocr_fallback_failed", level="warn",
                          summary=f"{video.name}: sonuç-temelli yedek atlandı ({_fbe}) — detect sonucu korunur.",
                          module="ocr", media_id=media_id, filename=video.name, detail={"clip_id": clip_id})

    # ASR sonucunu topla
    if asr_proc is not None:
        try:
            out, err = asr_proc.communicate(timeout=ASR_TIMEOUT)
            asr_info = last_json(out) or {}
            # SAVUNMA: CTranslate2/CUDA cikis-crash'i (0xC0000409) stdout JSON'unu silebilir;
            # transcript diske yazildiysa (gercek kanit) ASR'i basarili say. _pipe_asr os._exit
            # korumasina EK katman — boylece transcript varken ASLA "failed/Kontrol"e dusmez.
            _tp = asr_out / "transcript_plain.txt"
            if asr_info.get("status") != "done" and _tp.exists():
                try:
                    _txt = _tp.read_text(encoding="utf-8").strip()
                except Exception:  # noqa: BLE001
                    _txt = ""
                if _txt:
                    _nseg = sum(1 for _l in _txt.splitlines() if _l.strip())
                    asr_info = {**asr_info, "status": "done", "clean_segments": _nseg,
                                "transcript_chars": len(_txt), "recovered_from_disk": True}
            if not asr_info:
                asr_info = {"status": "failed", "error": (err or "")[-400:]}
            asr_status = asr_info.get("status", "failed")
            timings["asr"] = round(time.perf_counter() - t_asr, 2)
            _asr_ok = asr_status in ("done", "partial", "skipped_unsupported_lang")  # ku-atla = kasıtlı, hata DEĞİL
            update_clip_module(clip_dir, "asr", "done" if asr_status == "done" else ("partial" if asr_status in ("partial", "skipped_unsupported_lang") else "failed"), asr_job)
            kind = {"done": "asr_completed", "partial": "asr_partial", "skipped_unsupported_lang": "asr_skipped_kurtce"}.get(asr_status, "asr_failed")
            log_event(kind, level="info" if _asr_ok else "error",
                      summary=f"{video.name}: ASR {asr_status}, {asr_info.get('clean_segments', 0)} segment, {asr_info.get('transcript_chars', 0)} karakter ({timings['asr']} sn).",
                      module="asr", media_id=media_id, filename=video.name, job_id=asr_job, duration_seconds=timings["asr"],
                      detail={"clip_id": clip_id, "asr_total_seconds": asr_info.get("asr_total_seconds"),
                              "fallback_triggered": asr_info.get("fallback_triggered"), "profile_used": asr_info.get("profile_used"),
                              "error": asr_info.get("error")})
        except Exception as exc:  # noqa: BLE001
            timings["asr"] = round(time.perf_counter() - (t_asr or time.perf_counter()), 2)
            asr_status = "failed"
            try:
                asr_proc.kill()
                asr_proc.communicate(timeout=10)   # pipe drenaji + reaping (zombie/handle birakma)
            except Exception:  # noqa: BLE001
                pass
            update_clip_module(clip_dir, "asr", "failed", asr_job)
            log_event("asr_failed", level="error", summary=f"ASR blogu hata: {exc}",
                      module="asr", media_id=media_id, filename=video.name, job_id=asr_job, error=str(exc), detail={"clip_id": clip_id})

    # ===== HAVUZ-PARALEL TOPLAMA/LANSMAN (hız #1, 2026-07-05; v2 kök-kazı aynı gece) =====
    # Giriş-havuzu (CPU-OneOCR) burada TOPLANIR (OCR∥ASR ile örtüştü; kanıt: bekleme ~0).
    # Çıkış-havuzu (paddle'lı child) burada LANSE edilir: ASR bitti → commit/CUDA tepesi geçti;
    # LLM/v4/pdf kuyruğuyla örtüşür (gemma-resident+havuz birlikteliği eski seride kanıtlı).
    # Toplaması ilk tüketiciden (jdebug/master-compose) hemen önce. KANIT (v2 nedeni): 0439+0289'da
    # ASR-penceresinde spawn edilen child ANINDA öldü (stdout/stderr 0B = commit-tükenmesi/1455).
    if _pp_par and _jp_cmd and _jp_proc is None and not args.no_ocr:
        try:
            jenerik_debug_root.mkdir(parents=True, exist_ok=True)
            _t_jp_wall = time.time()
            t_jp = time.perf_counter()
            with open(_jp_outf, "w", encoding="utf-8", errors="replace") as _fo, \
                    open(_jp_errf, "w", encoding="utf-8", errors="replace") as _fe:
                _jp_proc = subprocess.Popen(_jp_cmd, stdout=_fo, stderr=_fe)
        except Exception as _jpe:  # noqa: BLE001
            log_event("jenerik_pool_failed", level="warn",
                      summary=f"{video.name}: çıkış-havuz lansmanı başarısız ({type(_jpe).__name__}).",
                      module="jenerik-pool", media_id=media_id, filename=video.name,
                      error=str(_jpe)[:300], detail={"clip_id": clip_id})
    if _gjp_proc is not None:
        _t_col = time.perf_counter()
        try:
            _rcgjp = _gjp_proc.wait(
                timeout=int(os.environ.get("MITAS_GIRIS_JENERIK_POOL_TIMEOUT", "900") or 900))
            _outgjp = _gjp_outf.read_text(encoding="utf-8", errors="replace") if _gjp_outf.exists() else ""
            _errgjp = _gjp_errf.read_text(encoding="utf-8", errors="replace") if _gjp_errf.exists() else ""
            _gjj = last_json(_outgjp) or {}
            timings["giris_jenerik_pool"] = round(time.perf_counter() - _t_col, 2)
            _gjp_wall = (round(_gjp_outf.stat().st_mtime - _t_gjp_wall, 2)
                         if (_t_gjp_wall and _gjp_outf.exists()) else None)
            log_event("giris_jenerik_pool_completed",
                      level="info" if _gjj.get("status") not in ("error", None) else "warn",
                      summary=f"{video.name}: giriş jenerik havuzu {giris_jenerik_frames.name} "
                              f"status={_gjj.get('status')} kept={_gjj.get('total_kept', 0)} "
                              f"rep={_gjj.get('total_dedup_representatives', 0)} "
                              f"(OCR∥ASR-örtüşük, iş {_gjp_wall} sn, ek bekleme {timings['giris_jenerik_pool']} sn).",
                      module="giris-jenerik-pool", media_id=media_id, filename=video.name,
                      duration_seconds=timings["giris_jenerik_pool"],
                      detail={"clip_id": clip_id, "pool": str(giris_jenerik_frames), "paralel": True,
                              "pool_wall_sn": _gjp_wall,
                              "result": _gjj, "stderr": (_errgjp or "")[-300:] if _rcgjp else None})
        except Exception as _gjpe:  # noqa: BLE001
            try:
                _gjp_proc.kill()
                _gjp_proc.wait(timeout=10)
            except Exception:  # noqa: BLE001
                pass
            log_event("giris_jenerik_pool_failed", level="warn",
                      summary=f"{video.name}: giriş jenerik havuzu toplama hatası ({type(_gjpe).__name__}).",
                      module="giris-jenerik-pool", media_id=media_id, filename=video.name,
                      error=str(_gjpe)[:300], detail={"clip_id": clip_id})

    # ===== BLOK KÜNYE-OKUMA (OneOCR ham metninden rol-eşleme; VLM DEVRE DIŞI) =====
    # KURAL: Qwen'e mümkünse kayıplı kunye.txt değil, daha ham OCR sidecar'ı (ocr_ham/raw) verilir;
    # temizleme/garble/KB/crew-sızıntı kapıları Qwen SONRASINDA çalışır. _pipe_credit_text LLM ile
    # yalnız ROL-EŞLEME yapar (pikselden OKUMAZ; halüsinasyon kalkanlı: her isim OCR metninde olmalı).
    # Eski VLM (credit_video_read: gemma4+qwen2.5vl) ÇIKARILDI —
    # pikselden okuyup HALÜSİNE ediyordu (KÖTÜ EVLAT: metin "Henry Hathaway" iken VLM "John Ford").
    # ASR'den sonra (GPU serbest), PDF'ten önce. KAPALI (MITAS_NO_VIDEO_CREDITS=1) → blok çalışmaz,
    # video_credits=None, PDF credit_parse-only'ye düşer (acil geri dönüş). Asla çökmez.
    _vc_off = os.environ.get("MITAS_NO_VIDEO_CREDITS", "").strip().lower() in ("1", "true", "yes", "on")
    USE_VIDEO_CREDITS = not _vc_off
    video_credits = None
    # LLM-PREFLIGHT (2026-07-03): ollama'da üretim modelleri VAR MI? KANIT: F: diski değişince
    # OLLAMA_MODELS boş birime baktı → rol-eşleme/VL/GLM/qwen-QC SESSİZCE öldü, filmler LLM'siz
    # "yönetmen okunamadı" ile KONTROL'e aktı (03.07.2026 sabahı canlı yaşandı, saatlerce fark
    # edilmedi). Bu bekçi durumu GÖRÜNÜR kılar: error-event + karara "LLM katmanı çalışmadı"
    # gerekçesi. FAIL-SAFE: probe hatası (ollama kapalı dahil) aynı şekilde işaretlenir ama
    # pipeline'ı ASLA durdurmaz.
    _llm_dead = False
    if USE_VIDEO_CREDITS and not args.no_ocr and profile in ("film", "dizi"):
        try:
            _oll = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434").rstrip("/")
            _probe_model = os.environ.get("MITAS_CREDIT_TEXT_MODEL", "gemma-4-31b-it-qat-vision:latest")
            _req = urllib.request.Request(_oll + "/api/show",
                                          data=json.dumps({"name": _probe_model}).encode("utf-8"),
                                          headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(_req, timeout=10):
                    pass
            except urllib.error.HTTPError as _he:
                if _he.code == 404:
                    _llm_dead = True
            except Exception:  # noqa: BLE001 — sunucu kapalı/timeout: LLM katmanı yine kullanılamaz
                _llm_dead = True
            if _llm_dead:
                # OLLAMA-BEKÇİSİ (2026-07-06, Çağatay: "ollama neden çökmüş, fixle"): işaretleyip
                # LLM'siz geçmek yerine ÖNCE DİRİLT — (1) ebeveyni ölü ÖKSÜZ llama-server'ı temizle
                # (06.07 vakası: 21GB VRAM + 23.5GB commit'i 4 saat kilitledi, yeni yükleme 500 verdi),
                # (2) ollama serve başlat, (3) ≤120sn model-probe bekle. Başarıda film LLM'Lİ devam
                # eder. FAIL-SAFE: her adım sessiz; olmadıysa eski görünür-işaretleme aynen kalır.
                # Kill-switch: MITAS_OLLAMA_BEKCI=0.
                if os.environ.get("MITAS_OLLAMA_BEKCI", "1").strip().lower() not in ("0", "false", "off", "no"):
                    try:
                        if os.name == "nt":
                            subprocess.run(
                                ["powershell", "-NoProfile", "-Command",
                                 "Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | "
                                 "ForEach-Object { if (-not (Get-Process -Id $_.ParentProcessId "
                                 "-ErrorAction SilentlyContinue)) { Stop-Process -Id $_.ProcessId -Force } }"],
                                capture_output=True, timeout=30)
                            try:
                                urllib.request.urlopen(_oll + "/api/version", timeout=5).read()
                            except Exception:  # noqa: BLE001 — sunucu kapalı → başlat
                                _oexe = os.path.join(os.environ.get("LOCALAPPDATA", ""),
                                                     "Programs", "Ollama", "ollama.exe")
                                subprocess.Popen([_oexe, "serve"], creationflags=0x08000000)
                        # Linux geçişi 2026-07-17: powershell/ollama.exe/creationflags üçü de POSIX'te
                        # patlayıp bekçiyi ilk satırda öldürüyordu. Linux'ta ollama systemd servisi
                        # (Restart=always) — çöktüyse systemd diriltir; restart yetkimiz yok
                        # (mitas-asr User=cagatay). Aşağıdaki probe-bekleme döngüsü yeterli.
                        _t_ob = time.perf_counter()
                        while time.perf_counter() - _t_ob < 120:
                            try:
                                with urllib.request.urlopen(_req, timeout=10):
                                    _llm_dead = False
                                    break
                            except Exception:  # noqa: BLE001
                                time.sleep(5)
                        if not _llm_dead:
                            log_event("llm_preflight_recovered", level="warn",
                                      summary=f"{video.name}: ollama-bekçisi DİRİLTTİ (öksüz-runner "
                                              f"temizliği + serve + probe) — film LLM'li devam ediyor.",
                                      module="ocr", media_id=media_id, filename=video.name,
                                      detail={"clip_id": clip_id, "ollama": _oll})
                    except Exception:  # noqa: BLE001 — bekçi ASLA pipeline'ı bozmaz
                        pass
            if _llm_dead:
                log_event("llm_preflight_failed", level="error",
                          summary=f"{video.name}: LLM preflight BAŞARISIZ — ollama'da '{_probe_model}' yok "
                                  f"(OLLAMA_MODELS deposu boş/kopuk olabilir; F:-disk-değişimi vakası). "
                                  f"Künye LLM'siz, eksik çıkacak.",
                          module="ocr", media_id=media_id, filename=video.name,
                          detail={"clip_id": clip_id, "ollama": _oll, "model": _probe_model})
        except Exception:  # noqa: BLE001 — preflight'ın kendisi ASLA pipeline'ı bozmaz
            _llm_dead = False
    # ── DİLİM-TAZELE (K1, "master-PNG hayata geçir" 2026-07-03) ──
    # Önceki koşunun reading-master'ları diskteyse: dilimle + OneOCR ile oku + GÜNCEL ocr_job
    # damgala → aynı koşunun VL hayalet-kalkanı korpusu (run-scope şartıyla) dilim satırlarını
    # görebilir. Kanıt: İHTİRAS 'DIRECTED BY / Bill L. Norton' ana zincirde yokken dilim-OneOCR'da
    # exact; 117-tarama C-vakalarında 14/17 kayıp yönetmen dilim-korpusuyla piksel-teyitli.
    # Maliyet ~2-5 sn/film (ölçüldü: ~0.2 sn/parça). FAIL-SAFE: hata pipeline'ı ASLA bozmaz.
    # Kill-switch: MITAS_MASTER_DILIM_AUTO=0.
    if (USE_VIDEO_CREDITS and not args.no_ocr and profile in ("film", "dizi")
            and os.environ.get("MITAS_MASTER_DILIM_AUTO", "1").strip().lower() not in ("0", "false", "off", "no")):
        try:
            _has_master = bool(list(clip_dir.glob("*reading_master_runaware.png")))
            if _has_master:
                _dl_t = time.perf_counter()
                run([str(PY_OCR), str(HERE / "master_png_dilimle.py"), "--clip", str(clip_dir)],
                    timeout=int(os.environ.get("MITAS_MASTER_DILIM_TIMEOUT", "180") or 180))
                run([str(PY_OCR), str(HERE / "master_dilim_oku.py"), "--clip", str(clip_dir),
                     "--ocr-job", ocr_job, "--force"],
                    timeout=int(os.environ.get("MITAS_MASTER_DILIM_TIMEOUT", "180") or 180))
                timings["dilim_tazele"] = round(time.perf_counter() - _dl_t, 2)
                log_event("master_dilim_refreshed",
                          summary=f"{video.name}: dilim-korpusu tazelendi ({timings['dilim_tazele']} sn, job={ocr_job}).",
                          module="ocr", media_id=media_id, filename=video.name,
                          detail={"clip_id": clip_id, "ocr_job": ocr_job})
        except Exception as _dle:  # noqa: BLE001 — dilim-tazele ASLA künye akışını bozmaz
            log_event("master_dilim_refresh_failed", level="warn",
                      summary=f"{video.name}: dilim-tazele atlandı ({type(_dle).__name__}).",
                      module="ocr", media_id=media_id, filename=video.name,
                      error=str(_dle)[:200], detail={"clip_id": clip_id})
    if USE_VIDEO_CREDITS and not args.no_ocr and profile in ("film", "dizi"):
        t_vc = time.perf_counter()
        try:
            vc_cmd = [str(PY_PDF), str(HERE / "_pipe_credit_text.py"),
                      "--ocr", str(kunye_path), "--title", title or "", "--profile", profile]
            rc_vc, out_vc, err_vc = run(vc_cmd, timeout=VC_TIMEOUT)
            video_credits = last_json(out_vc)
            # İP-2 (2026-07-11): 4. yutma-noktası kapandı — alt-süreç JSON basamadan öldüyse bu da
            # TEKNİK-KAZADIR (eski davranış: None → sessizce boş-gibi devam). Sözlük boş değilse
            # extraction_status alanını _pipe_credit_text zaten taşıdı.
            if not isinstance(video_credits, dict) or not video_credits:
                video_credits = {"extraction_status": "TECHNICAL_FAILURE",
                                 "extraction_detail": {"reason": "subprocess_no_json",
                                                       "rc": rc_vc,
                                                       "stderr_kuyruk": (err_vc or "")[-400:]}}
            timings["video_kunye"] = round(time.perf_counter() - t_vc, 2)
            # İP-3 (2026-07-11): extraction telemetrisi — num_ctx clamp-formülünün gelecekteki
            # veri-tabanı (prompt_eval/eval sayaçları model-başına; run_id ile manifest'e bağlı).
            _rm.append_telemetry({
                "run_id": _manifest.get("run_id"), "trt": trt, "title": title,
                "extraction_status": video_credits.get("extraction_status"),
                "models": (video_credits.get("extraction_detail") or {}).get("models"),
                "degraded": video_credits.get("degraded"),
            })
            dbg.emit("credit_text", "candidate_read",
                     status="ok" if video_credits else "warn",
                     duration_ms=timings["video_kunye"] * 1000,
                     subject={"field": "credits", "after": video_credits,
                              "reason": "text/LLM extraction from OCR source"},
                     evidence={"model": (video_credits or {}).get("model"),
                               "ocr_source": (video_credits or {}).get("ocr_source"),
                               "guven": (video_credits or {}).get("guven")},
                     source={"module": "scripts/mitas_pipeline.py",
                             "input_paths": [str(kunye_path)],
                             "output_paths": []})
            log_event("credit_text_completed",
                      summary=f"{video.name}: kunye-okuma(metin) model={(video_credits or {}).get('model')} guven={(video_credits or {}).get('guven')} yon={(video_credits or {}).get('yonetmen')} ({timings.get('video_kunye')} sn).",
                      module="ocr", media_id=media_id, filename=video.name, duration_seconds=timings.get("video_kunye"),
                      detail={"clip_id": clip_id, "guven": (video_credits or {}).get("guven"),
                              "yonetmen": (video_credits or {}).get("yonetmen"),
                              "model": (video_credits or {}).get("model"),
                              "stderr": (err_vc or "")[-200:] if rc_vc else None})
        except Exception as exc:  # noqa: BLE001 — kunye-okuma akışı/PDF'i ASLA bozmaz
            log_event("credit_text_failed", level="warn", summary=f"kunye-okuma(metin) blogu hata (atlandi): {exc}",
                      module="ocr", media_id=media_id, filename=video.name, error=str(exc), detail={"clip_id": clip_id})
            dbg.emit("credit_text", "stage_completed", status="warn",
                     subject={"field": "credits", "reason": "text credit extraction skipped/failed"},
                     evidence={"stderr": str(exc)}, error=str(exc),
                     source={"module": "scripts/mitas_pipeline.py", "input_paths": [str(kunye_path)]})

    # ===== BLOK VL-FALLBACK — QC1 kapılı, çift-kontrollü (2026-06-14) =====
    # Akış: OneOCR → 35b Ayıklayıcı → QC1 → RED ise gemma4 VL → QC1 tekrar → hâlâ RED → _qc1_failed işareti
    # ── YÖNETMEN KURTARMA (etiket-tabanlı, deterministik) — VL'DEN ÖNCE ─────────
    # ÖLÇÜM (2026-08-01): yönetmen etiketi olan 145 filmin 35'inde (%24) etiket
    # künyede VAR ama alan BOŞ. Kanıt KUTSAL HAZİNE 1998-0325: g_0244.png'de
    # "Directed by / JOHN CONNICK" ekranda, okuma doğru, hakem onaylı (kutu_n=2),
    # kunye.txt:252-253'e yazılmış — gemma 18 oyuncuyu buldu ama 264 satırın
    # 252.'sindeki bu alanı atladı; VL yedeği de bulamadı. Prompt SUÇSUZ (kural 4
    # tam bu kalıbı tarif ediyor) → model hatırlama hatası, uzun-kuyruk sınıfı.
    # DURUŞ: LLM'i değiştirme (aynı metinden 18 oyuncuyu doğru çıkardı); bulanık
    # işi LLM'e, ETİKETLİ kesin alanı KURAL'a bırak. Yalnız BOŞ alanı doldurur,
    # dolu alanı ASLA ezmez → sıfır regresyon. Kill-switch: MITAS_YON_KURTAR=0.
    if (video_credits and not video_credits.get("yonetmen")
            and os.environ.get("MITAS_YON_KURTAR", "1").strip().lower() not in ("0", "false", "off")):
        try:
            sys.path.insert(0, str(HERE))
            import yonetmen_kurtar as _yk
            _kunye_yolu = ocr_out / "kunye.txt"
            _iz_yolu = ocr_out / "hibrit_iz.jsonl"
            if _kunye_yolu.is_file():
                _bulgu = _yk.kurtar(
                    _kunye_yolu.read_text(encoding="utf-8", errors="ignore").splitlines(),
                    iz_yolu=(str(_iz_yolu) if _iz_yolu.is_file() else None))
                # KANIT KAPISI: otomatik doldurma YALNIZ adres teyitli olduğunda.
                # Kuru koşu (125 film) yapısal süzgeç tek başına %75 isabet verdi —
                # kritik alan için YETMEZ (HOTEL RWANDA: 'A FILM BY' + oyuncu adı
                # tesadüfen komşu → Terry George yerine Fana Mokoena yazardı).
                # Etiket ve isim AYNI KAREDE ise kart gerçekten yönetmen kartıdır.
                # Teyitsiz aday SİLİNMEZ, aday olarak kaydedilir → KONTROL insanı görür.
                _teyit = (_bulgu or {}).get("kare_teyidi")
                _saglam = _teyit in ("etiketle_ayni_satir",) or (
                    _teyit and _teyit.endswith(".png"))
                if _bulgu and _saglam:
                    video_credits["yonetmen"] = [_bulgu["yonetmen"]]
                    video_credits["_yonetmen_kurtarildi"] = _bulgu
                    log_event("credit_yonetmen_kurtarildi",
                              summary=f"{video.name}: yönetmen alanı BOŞTU, künye etiketinden "
                                      f"kurtarıldı → {_bulgu['yonetmen']} "
                                      f"(etiket={_bulgu['etiket']!r}, satır={_bulgu['satir']}, "
                                      f"teyit={_teyit}).",
                              module="ocr", media_id=media_id, filename=video.name,
                              detail={"clip_id": clip_id, **_bulgu})
                elif _bulgu:
                    video_credits["_yonetmen_adayi"] = _bulgu     # doldurmaz, işaretler
                    log_event("credit_yonetmen_adayi_teyitsiz", level="warn",
                              summary=f"{video.name}: yönetmen adayı bulundu ama ADRES TEYİDİ YOK "
                                      f"({_bulgu['yonetmen']}, teyit={_teyit}) — alan BOŞ bırakıldı, "
                                      f"insan teyidine gidiyor.",
                              module="ocr", media_id=media_id, filename=video.name,
                              detail={"clip_id": clip_id, **_bulgu})
        except Exception as _e:          # noqa: BLE001 — kurtarma ASLA hattı düşürmez
            dbg.emit("yonetmen_kurtar_hata", {"hata": f"{type(_e).__name__}: {_e}"})

    # QC1 kriteri: yönetmen BOŞSA veya cast < 3  →  RED.
    # gemma4 VL (tek model): kare oku → yönetmen doldur + cast<3 ise cast'i de doldur (--fill-cast).
    # Kill-switch: MITAS_NO_VL_FALLBACK=1. Her hata → video_credits AYNEN (FAIL-SAFE).
    _vl_off = os.environ.get("MITAS_NO_VL_FALLBACK", "").strip().lower() in ("1", "true", "yes", "on")
    # ANİMASYON erken-sinyali (2026-07-04): XML türü animasyon diyorsa cast<3 "eksik" DEĞİL "doğru"dur
    # (oyuncu yok, seslendirme var) → cast-tetikli VL-fallback'i atla (halüsinasyon + GPU israfı önlenir).
    # Yönetmen-boş tetiği KALIR (animasyonda da yönetmen aranır). Yalnız XML-sinyali (erken aşamada
    # KB henüz yok); XML sessizse davranış AYNEN eski.
    _anim_early = any(k in (tur_xml or "").upper() for k in ("ANİMASYON", "ANIMASYON", "ANIMATION", "ÇİZGİ", "CIZGI"))
    if USE_VIDEO_CREDITS and not _vl_off and not args.no_ocr and video_credits and profile in ("film", "dizi"):
        _vl_need = (not video_credits.get("yonetmen")) or ((len(video_credits.get("cast") or []) < 3) and not _anim_early)
        if _vl_need:
            _dir_before = list(video_credits.get("yonetmen") or [])   # VL-sertleştirme: VL-EKLEDİĞİ yönetmeni ayırt et
            _cast_before = list(video_credits.get("cast") or [])
            dbg.emit("qc1", "qc_decision", status="warn",
                     subject={"field": "credit_quality", "before": {"yonetmen": _dir_before, "cast": len(_cast_before)},
                              "reason": "QC1 RED; VL fallback will run"},
                     evidence={"yonetmen_var": bool(video_credits.get("yonetmen")),
                               "cast_count": len(video_credits.get("cast") or []),
                               "vl_fallback": True},
                     source={"module": "scripts/mitas_pipeline.py"})
            log_event("credit_qc1_red",
                      summary=f"{video.name}: QC1-RED — yön={'VAR' if video_credits.get('yonetmen') else 'BOŞ'}, cast={len(video_credits.get('cast') or [])}, gemma4 VL-fallback başlıyor.",
                      module="ocr", media_id=media_id, filename=video.name,
                      detail={"clip_id": clip_id, "yonetmen": video_credits.get("yonetmen"), "cast_count": len(video_credits.get("cast") or [])})
            t_vl = time.perf_counter()
            try:
                vl_cmd = [str(PY_PDF), str(HERE / "_pipe_credit_vl.py"), "--clip", str(clip_dir),
                          "--title", title or "", "--profile", profile, "--fill-cast",
                          "--ocr-job", ocr_job,   # A1 (2026-07-03): kalkan korpusu bu koşuya (+ '-fb' kardeşi) sınırlı
                          "--original", original or "",             # A2: ÇAPA-1 KB film-kimlik araması
                          "--year", (trt.split("-")[0] if trt else ""),
                          "--text-credits", json.dumps(video_credits, ensure_ascii=False)]
                rc_vl, out_vl, err_vl = run(vl_cmd, timeout=VL_TIMEOUT)
                _merged = last_json(out_vl)
                if _merged:
                    video_credits = _merged
                # VL-SERTLEŞTİRME (Çağatay 2026-06-15): VL pikselden yönetmen "doldurduysa" ama o isim
                # CAST'te de geçiyorsa → açılış-kartı BAŞROLÜ yönetmen sanılmış (BAŞKA BİR DÜNYA: VL
                # 'Anthony Bajon'=oyuncu dedi). "okunamadı > yanlış" → o yönetmeni DÜŞÜR (boş bırak → KONTROL).
                if _merged and not _dir_before and (_merged.get("yonetmen")):
                    _nf = lambda s: " ".join(str(s or "").casefold().split())
                    _cast_fold = {_nf(c) for c in ((_merged.get("cast") or []) + _cast_before)}
                    _vl_dir = _merged.get("yonetmen") or []
                    _keep = [d for d in _vl_dir if _nf(d) not in _cast_fold]
                    if _keep != _vl_dir:
                        _drop = [d for d in _vl_dir if _nf(d) in _cast_fold]
                        video_credits["yonetmen"] = _keep
                        # A0-ek (2026-07-03, inceleme bulgusu): cast-çakışmasıyla düşen VL-yönetmen de
                        # insana yüzeylenebilsin diye kaydedilir (yalnız kalkan-düşmeleri görünüyordu).
                        video_credits["vl_yon_cast_dropped"] = _drop
                        log_event("credit_vl_director_dropped", level="warn",
                                  summary=f"{video.name}: VL-yönetmen {_drop} CAST'te de var → açılış-kartı oyuncusu "
                                          f"yönetmen sanıldı, DÜŞÜRÜLDÜ (okunamadı>yanlış).",
                                  module="ocr", media_id=media_id, filename=video.name,
                                  detail={"clip_id": clip_id, "dropped": _drop, "vl_cast": _merged.get("cast")})
                        dbg.emit("vl_fallback", "candidate_dropped", status="warn",
                                 subject={"field": "yonetmen", "before": _vl_dir, "after": _keep,
                                          "reason": "VL director also appeared in cast; dropped"},
                                 evidence={"dropped": _drop, "vl_cast": _merged.get("cast")},
                                 source={"module": "scripts/mitas_pipeline.py"})
                timings["vl_fallback"] = round(time.perf_counter() - t_vl, 2)
                dbg.emit("vl_fallback", "fallback_triggered",
                         status="ok" if _merged else "warn",
                         duration_ms=timings["vl_fallback"] * 1000,
                         subject={"field": "credits", "before": {"yonetmen": _dir_before, "cast": _cast_before},
                                  "after": _merged, "reason": "QC1 RED triggered VL fallback"},
                         evidence={"vl": (_merged or {}).get("vl"),
                                   "cast_supplement": (_merged or {}).get("vl_cast_supplement"),
                                   "vl_yon_hallucinated": (_merged or {}).get("vl_yon_hallucinated"),
                                   "vl_cast_hallucinated": (_merged or {}).get("vl_cast_hallucinated")},
                         source={"module": "scripts/mitas_pipeline.py", "input_paths": [str(clip_dir)]})
                log_event("credit_vl_fallback",
                          summary=f"{video.name}: gemma4 VL-fallback ({(_merged or {}).get('vl')}) yon={(_merged or {}).get('yonetmen')} cast={len((_merged or {}).get('cast') or [])} ({timings.get('vl_fallback')} sn).",
                          module="ocr", media_id=media_id, filename=video.name, duration_seconds=timings.get("vl_fallback"),
                          detail={"clip_id": clip_id, "vl": (_merged or {}).get("vl"),
                                  "yonetmen": (_merged or {}).get("yonetmen"),
                                  "cast_supplement": (_merged or {}).get("vl_cast_supplement")})
            except Exception as exc:  # noqa: BLE001 — FAIL-SAFE: pipeline'ı ASLA bozma
                log_event("credit_vl_failed", level="warn", summary=f"VL-fallback hata (atlandi): {exc}",
                          module="ocr", media_id=media_id, filename=video.name, error=str(exc), detail={"clip_id": clip_id})
            # QC1 tekrar: VL sonrası durumu değerlendir
            _vl_need_2 = (not video_credits.get("yonetmen")) or (len(video_credits.get("cast") or []) < 3)
            if _vl_need_2:
                video_credits["_qc1_failed"] = True
                dbg.emit("qc1", "qc_decision", status="warn",
                         subject={"field": "credit_quality",
                                  "after": {"yonetmen": video_credits.get("yonetmen"),
                                            "cast_count": len(video_credits.get("cast") or [])},
                                  "reason": "QC1 still RED after VL fallback"},
                         evidence={"route": "Kontrol", "qc1_failed": True},
                         source={"module": "scripts/mitas_pipeline.py"})
                log_event("credit_qc1_failed", level="warn",
                          summary=f"{video.name}: QC1 VL sonrası da RED — yön={'VAR' if video_credits.get('yonetmen') else 'BOŞ'}, cast={len(video_credits.get('cast') or [])} → KONTROL.",
                          module="ocr", media_id=media_id, filename=video.name,
                          detail={"clip_id": clip_id, "yonetmen": video_credits.get("yonetmen"), "cast_count": len(video_credits.get("cast") or [])})
            else:
                dbg.emit("qc1", "qc_decision",
                         subject={"field": "credit_quality",
                                  "after": {"yonetmen": video_credits.get("yonetmen"),
                                            "cast_count": len(video_credits.get("cast") or [])},
                                  "reason": "QC1 PASS after VL fallback"},
                         evidence={"qc1_failed": False},
                         source={"module": "scripts/mitas_pipeline.py"})
                log_event("credit_qc1_passed",
                          summary=f"{video.name}: QC1-PASS (VL sonrası) — yön={video_credits.get('yonetmen')} cast={len(video_credits.get('cast') or [])}.",
                          module="ocr", media_id=media_id, filename=video.name,
                          detail={"clip_id": clip_id})
        else:
            dbg.emit("qc1", "qc_decision",
                     subject={"field": "credit_quality",
                              "after": {"yonetmen": video_credits.get("yonetmen"),
                                        "cast_count": len(video_credits.get("cast") or [])},
                              "reason": "QC1 PASS; VL fallback not run"},
                     evidence={"vl_fallback": False, "qc1_failed": False,
                               "yonetmen_var": bool(video_credits.get("yonetmen")),
                               "cast_count": len(video_credits.get("cast") or [])},
                     source={"module": "scripts/mitas_pipeline.py"})
            # ÖLÇÜM KANCASI: temiz geçiş de olay bassın. Yoksa QC1 başarı oranının
            # PAYDASI log'da olmuyor — 'credit_qc1_passed' yalnız RED→VL→kurtarıldı
            # yolunu kapsıyor, ilk denemede geçen film sıfır olay üretiyordu
            # (ampirik: 33 filmden 17'si görünmez). dbg.emit per-film trace'e gider,
            # system_events.jsonl'e DEĞİL → kohort ölçümü yapılamıyordu.
            log_event("credit_qc1_passed_first_try",
                      summary=f"{video.name}: QC1-PASS (ilk deneme, VL koşmadı) — "
                              f"yön={video_credits.get('yonetmen')} cast={len(video_credits.get('cast') or [])}.",
                      module="ocr", media_id=media_id, filename=video.name,
                      detail={"clip_id": clip_id,
                              "yonetmen": video_credits.get("yonetmen"),
                              "cast_count": len(video_credits.get("cast") or []),
                              "vl_fallback": False})
    elif USE_VIDEO_CREDITS and _vl_off and not args.no_ocr and video_credits and profile in ("film", "dizi"):
        dbg.emit("qc1", "qc_decision", status="skipped",
                 subject={"field": "credit_quality",
                          "after": {"yonetmen": video_credits.get("yonetmen"),
                                    "cast_count": len(video_credits.get("cast") or [])},
                          "reason": "VL fallback disabled by MITAS_NO_VL_FALLBACK"},
                 evidence={"vl_fallback": False, "disabled": True},
                 source={"module": "scripts/mitas_pipeline.py"})
        # ÖLÇÜM KANCASI: bu dalda QC1 HİÇ değerlendirilmiyor — _qc1_failed set
        # edilmiyor, yani routing'e (satır ~3367) QC1 sinyali gitmiyor. Kohortu
        # 'geçti' sananın önüne geçmek için ayrı kind: paydaya girer, sayıya girmez.
        log_event("credit_qc1_skipped", level="warn",
                  summary=f"{video.name}: QC1 değerlendirilmedi — MITAS_NO_VL_FALLBACK ile "
                          f"kapatıldı; yön={'VAR' if video_credits.get('yonetmen') else 'BOŞ'}, "
                          f"cast={len(video_credits.get('cast') or [])}.",
                  module="ocr", media_id=media_id, filename=video.name,
                  detail={"clip_id": clip_id,
                          "yonetmen": video_credits.get("yonetmen"),
                          "cast_count": len(video_credits.get("cast") or []),
                          "reason": "MITAS_NO_VL_FALLBACK"})

    # ===== BLOK YÖNETMEN-DOĞRULAMA (credit_validate; flag MITAS_CREDIT_VALIDATE, fail-safe) =====
    # 35B çıktısını mitas.duckdb (IMDb+Wikidata) + XML ile DOĞRULA → CELISKI/OKUNAMADI = KONTROL sinyali.
    # ADDITIVE: yalnız 'reasons'a sinyal ekler (yönetmen/PDF AKIŞINI DEĞİŞTİRMEZ). Hata → atlanır (asla bozmaz).
    cv_result = None
    if os.environ.get("MITAS_CREDIT_VALIDATE", "").strip().lower() in ("1", "true", "on", "yes") \
            and video_credits and profile in ("film", "dizi"):
        try:
            cv_cmd = [str(PY_OCR), str(HERE / "_pipe_credit_validate.py"),
                      "--video-credits", json.dumps(video_credits, ensure_ascii=False),
                      "--video", str(video), "--title", title or "", "--ocr", str(kunye_path),
                      "--profile", profile]
            # ORİJİNAL-AD İKİNCİ ANAHTAR (2026-07-31, Çağatay): bu çağrı --original HİÇ GEÇMİYORDU →
            # credit_validate.py DB-arama SADECE Türkçe başlıkla çalışıyordu (yabancı filmde DB'de
            # yalnız İngilizce ad varsa 0 aday → yönetmen doğrulama hep "kaynak veri yok" kalıyordu).
            # XML <TITLE> zaten satır ~1806'da (original=) hesaplanmış; afiş aramasında kullanılıyor —
            # burada da AYNI değeri iletmek additive (original boşsa davranış birebir aynı).
            if original:
                cv_cmd += ["--original", original]
            _rc_cv, _out_cv, _err_cv = run(cv_cmd, timeout=180)
            cv_result = last_json(_out_cv)
            dbg.emit("credit_validate", "external_lookup",
                     status="ok" if cv_result else "warn",
                     subject={"field": "yonetmen", "before": (video_credits or {}).get("yonetmen"),
                              "after": (cv_result or {}).get("yonetmen"),
                              "reason": "IMDb/Wikidata/XML director validation"},
                     evidence={"result": cv_result},
                     source={"module": "scripts/mitas_pipeline.py",
                             "input_paths": [str(kunye_path), str(video)]})
            log_event("credit_validate",
                      summary=f"{video.name}: yön-doğrulama={(cv_result or {}).get('yonetmen', {}).get('status')}",
                      module="ocr", media_id=media_id, filename=video.name,
                      detail={"clip_id": clip_id, "result": cv_result})
        except Exception as exc:  # noqa: BLE001 — doğrulama pipeline'ı ASLA bozmaz
            log_event("credit_validate_failed", level="warn", summary=f"yön-doğrulama atlandı: {exc}",
                      module="ocr", media_id=media_id, filename=video.name, detail={"clip_id": clip_id})

    # C2-fix (2026-06-29): credit_validate DOGRULANDI+KESIN yönetmeni video_credits'e GERİ-YAZ.
    # validate KB (IMDb+Wiki+XML) 3-kaynak teyitle OCR-garble'ı KANONİK yazıma düzeltti (val=pool-canonical).
    # SADECE status=DOGRULANDI & confidence=KESIN yazılır → OKUNAMADI/CELISKI/DOGRULANAMADI/ORTA SIZMAZ
    # ('okunamadı>yanlış' korunur). Bu noktadan SONRA cmd(~2086)+v4_cmd(~2134) güncel video_credits'i okur.
    if cv_result:
        _cvd_fix = cv_result.get("yonetmen") or {}
        if (_cvd_fix.get("status") == "DOGRULANDI"
                and _cvd_fix.get("confidence") == "KESIN"
                and _cvd_fix.get("value")):
            _cv_val = _cvd_fix["value"]
            _new_dir = None
            if isinstance(_cv_val, list):
                _new_dir = [str(x).strip() for x in _cv_val if x and str(x).strip()]
            elif isinstance(_cv_val, str) and _cv_val.strip():
                _new_dir = [_cv_val.strip()]
            if _new_dir:
                _old_dir = video_credits.get("yonetmen")
                video_credits["yonetmen"] = _new_dir
                video_credits["_director_validation"] = {
                    "value": _new_dir,
                    "status": _cvd_fix.get("status"),
                    "confidence": _cvd_fix.get("confidence"),
                    "sources_confirm": _cvd_fix.get("sources_confirm") or [],
                    "imdb_id": (((cv_result.get("kaynaklar") or {}).get("imdb") or {}).get("key")
                                if isinstance(cv_result, dict) else None),
                }
                if _credit_validate_strong_director(cv_result):
                    if video_credits.get("_qc1_failed"):
                        video_credits["_qc1_failed_overridden_by_credit_validate"] = True
                        # ÖLÇÜM KANCASI: "QC1 RED → sonradan kurtarıldı" vakası
                        # olay düzeyinde görünmüyordu; yalnız credit_validate_backfill
                        # basılıyordu ve o QC1'den bağımsız da tetiklenebiliyor.
                        # Kohort sayımında bu filmler 'failed' kalıyordu → sahte kötümser.
                        log_event("credit_qc1_recovered_by_validate",
                                  summary=f"{video.name}: QC1-RED, credit_validate güçlü yönetmen "
                                          f"buldu → bayrak KALDIRILDI ({_new_dir}).",
                                  module="ocr", media_id=media_id, filename=video.name,
                                  detail={"clip_id": clip_id, "yonetmen": _new_dir,
                                          "sources": _cvd_fix.get("sources_confirm"),
                                          "confidence": _cvd_fix.get("confidence")})
                    video_credits["_qc1_failed"] = False
                    video_credits["_credit_validate_strong_director"] = True
                dbg.emit("credit_validate", "candidate_changed",
                         subject={"field": "yonetmen", "before": _old_dir, "after": _new_dir,
                                  "reason": "C2-fix: KB-confirmed canonical director backfill"},
                         evidence={"sources_confirm": _cvd_fix.get("sources_confirm"),
                                   "confidence": _cvd_fix.get("confidence"),
                                   "status": _cvd_fix.get("status")},
                         source={"module": "scripts/mitas_pipeline.py"})
                log_event("credit_validate_backfill",
                          summary=f"{video.name}: C2-fix yön KB-teyitli yazıldı {_new_dir} (eski={_old_dir}).",
                          module="ocr", media_id=media_id, filename=video.name,
                          detail={"clip_id": clip_id, "value": _new_dir, "eski": _old_dir,
                                  "sources": _cvd_fix.get("sources_confirm")})

    # ===== BLOK PDF / teslim =====
    pdf_out = clip_dir / "pdf"
    pdf_info = {}
    _ext_tf = _is_technical_failure(video_credits)
    _ext_degraded = (isinstance(video_credits, dict)
                     and str(video_credits.get("extraction_status") or "").upper() == "DEGRADED")
    t0 = time.perf_counter()
    try:
        # ozet: ASR transcript'inden Sonnet ile gercek olay-orgusu ozeti.
        # transcript_plain.txt = _pipe_asr.py'nin yazdigi tam temiz metin (asr_out/).
        # Key yok / transcript yok / istek coker → eski placeholder davranisi korunur.
        # ASR anahtari KAPALI (no_asr) → ozet BOS: _make_pdf ozet-bos paneli hic cizmez,
        # PDF placeholder'siz temiz cikar (Cagatay 2026-07-30: test klipleri ASR'siz).
        ozet = "" if args.no_asr else "(Özet ayrı bir adımda üretilecektir.)"
        if asr_info.get("language") == "ku":
            # Kürtçe-ailesi: whisper ÇEVİREMEZ (ASR atlandı) → özeti İNTERNETTEN çek (bizim prompt). Çağatay direktifi.
            # NOT: başlık eşleşmesi belirsizse yanlış film gelebilir — kadro-tabanlı kimlik ileride bağlanacak.
            net_ozet = _fetch_internet_ozet(title=title, original=original, year=film_year, duration=dur,
                                            verify_director=(video_credits or {}).get("yonetmen") or [],
                                            verify_cast=(video_credits or {}).get("cast") or [])
            if net_ozet:
                ozet = net_ozet
                log_event("ozet_internet",
                          summary=f"{video.name}: Kurtce -> internet ozeti uretildi ({len(net_ozet)} karakter).",
                          module="summary", media_id=media_id, filename=video.name,
                          detail={"clip_id": clip_id, "ozet_chars": len(net_ozet), "source": "tmdb-internet"})
            else:
                ozet = "Bu kopya Kürtçe/desteklenmeyen dilde; transkript çıkarılamadı, internette de eşleşme bulunamadı."
                log_event("ozet_atlandi", level="warn",
                          summary=f"{video.name}: Kurtce + internet ozeti bulunamadi.",
                          module="summary", media_id=media_id, filename=video.name, detail={"clip_id": clip_id})
        else:
            if asr_info.get("transcript_head"):
                ozet = "(Ham transcript önizleme — kalıp özet sonra) " + asr_info["transcript_head"]
            transcript_txt_path = asr_out / "transcript_plain.txt"
            transcript_text = ""
            if transcript_txt_path.exists():
                try:
                    transcript_text = transcript_txt_path.read_text(encoding="utf-8").strip()
                except Exception:  # noqa: BLE001
                    transcript_text = ""
            if transcript_text:
                real_ozet = _generate_ozet(transcript_text, title=title, duration=dur)
                if real_ozet:
                    ozet = real_ozet
                    log_event("ozet_completed",
                              summary=f"{video.name}: Sonnet ozeti uretildi ({len(real_ozet)} karakter).",
                              module="summary", media_id=media_id, filename=video.name,
                              detail={"clip_id": clip_id, "ozet_chars": len(real_ozet), "transcript_chars": len(transcript_text)})
                else:
                    log_event("ozet_atlandi", level="warn",
                              summary=f"{video.name}: Sonnet ozeti uretilemedi (key yok / istek bos / hata) — placeholder kaldi.",
                              module="summary", media_id=media_id, filename=video.name,
                              detail={"clip_id": clip_id, "transcript_chars": len(transcript_text)})
            else:
                log_event("ozet_atlandi", level="info",
                          summary=f"{video.name}: transcript yok (ASR atlandi/bos) — ozet uretilmedi.",
                          module="summary", media_id=media_id, filename=video.name, detail={"clip_id": clip_id})
        cmd = [PY_PDF, HERE / "_pipe_pdf.py", "--kunye", str(kunye_path), "--out", str(pdf_out),
               "--title", title, "--trt-id", trt or "", "--profile", "film" if is_film else "dizi",
               "--resolution", res, "--duration", dur, "--ozet", ozet]
        # SAĞLAM DİL (2026-06-28): ASR'nin (whisper) tespit ettiği konuşma dilini PDF'e fail-safe fallback
        # geçir → chlang yoksa/boş dönerse "Ana dil" boş kalmasın. _pipe_pdf yalnız ana_dil boşken kullanır.
        _asr_lang = (asr_info or {}).get("language")
        if _asr_lang and str(_asr_lang).strip().lower() not in ("none", ""):
            cmd += ["--asr-lang", str(_asr_lang).strip()]
        # KARE HIZI KALDIRILDI (v4): _pipe_pdf artık fps basmaz; TÜR'ü v4-final (tek_film_kunye, KB) doldurur.
        # fps_s yalnız telemetride (clip.json/_DURUM) kalır — künyeye girmez.
        if bolum:
            cmd += ["--bolum", bolum]
        if original:                       # afiş: orijinal ad birincil sorgu (yabancı film)
            cmd += ["--original", original]
        if film_year:                      # afiş: çok-sürümde yedek ayraç (kadro teyidi birincil)
            cmd += ["--year", film_year]
        if xml_role_map:                   # rol aklı: XML rol ankrajı (yoksa arg verilmez → eski davranış)
            cmd += ["--xml-roles", json.dumps(xml_role_map, ensure_ascii=False)]
        if USE_VIDEO_CREDITS and video_credits:   # video-künye: PDF augment (flag açıkken)
            cmd += ["--video-credits", json.dumps(video_credits, ensure_ascii=False)]
        # film/dizi → ses & altyazı bloğu: kaynak video + (ASR yazdıysa) kanal-dil JSON.
        # --no-asr gerçek ASR-hariç modudur: PDF'ye --video geçme; yoksa _pipe_pdf kanal-dil
        # için _channel_lang.py'yi ASR venv ile tekrar çalıştırır.
        _pa_pdf = PROFILE_ASR.get(profile)
        if (not args.no_asr) and _pa_pdf and _pa_pdf.get("language") == "auto":
            cmd += ["--video", str(video)]
            _chl = asr_out / "chlang.json"
            if _chl.exists():
                cmd += ["--chlang", str(_chl)]
            cmd += ["--subtitle", str(asr_out / "subtitle.json")]   # 1.3 altyazi cache: yoksa _pipe_pdf hesaplar+yazar, varsa okur (yeniden tarama yok)
        if _ext_tf:
            # Teknik-kaza bilincli-bos degildir. Hub/OCR/trace korunur fakat teslim render'i
            # calistirilmaz; boylece kismi mekanik/LLM verisi PDF veya export'a sizamaz.
            pdf_info = {
                "status": "withheld_technical_failure",
                "delivery_withheld": True,
                "reason_code": "TEKNIK_ARIZA_EXTRACTION",
            }
        else:
            rc, out, err = run(cmd, timeout=PDF_TIMEOUT)  # altyazı Paddle taraması / kanal-dil self-run payı
            pdf_info = last_json(out) or {"status": "failed", "pdf_error": err[-300:]}
        timings["pdf"] = round(time.perf_counter() - t0, 2)
        dbg.emit("pdf", "stage_completed",
                 status=("error" if _ext_tf else ("ok" if pdf_info.get("status") == "done" else "warn")),
                 duration_ms=timings["pdf"] * 1000,
                 subject={"field": "pdf", "after": pdf_info.get("pdf_path") or pdf_info.get("md_path"),
                          "reason": "PDF/MD delivery render"},
                 evidence={"pdf_info": pdf_info},
                 source={"module": "scripts/mitas_pipeline.py",
                         "input_paths": [str(kunye_path)],
                         "output_paths": [str(pdf_info.get("pdf_path") or ""),
                                          str(pdf_info.get("md_path") or "")]})
        log_event(("pdf_withheld_technical_failure" if _ext_tf else
                   ("pdf_completed" if pdf_info.get("status") == "done" else "pdf_partial")),
                  level=("error" if _ext_tf else ("info" if pdf_info.get("status") == "done" else "warn")),
                  summary=(f"{video.name}: extraction TECHNICAL_FAILURE — PDF/teslim URETILMEDI."
                           if _ext_tf else
                           f"{video.name}: teslim hazirlandi (PDF={'var' if pdf_info.get('pdf_path') else 'yok, md'}, cast={pdf_info.get('cast_count')}) ({timings['pdf']} sn)."),
                  module="pdf", media_id=media_id, filename=video.name, duration_seconds=timings["pdf"],
                  detail={"clip_id": clip_id, "pdf": pdf_info.get("pdf_path"), "md": pdf_info.get("md_path"), "pdf_error": pdf_info.get("pdf_error")})
    except Exception as exc:  # noqa: BLE001
        timings["pdf"] = round(time.perf_counter() - t0, 2)
        log_event("pdf_failed", level="error", summary=f"PDF blogu hata: {exc}",
                  module="pdf", media_id=media_id, filename=video.name, error=str(exc), detail={"clip_id": clip_id})

    # ===== BLOK V4 FİNAL (film/dizi: temiz video-okuma + cross-check → kunye.pdf'i v4'e çevir) =====
    # tek_film_kunye.py (PY_PDF): video_credits (yukarıda) + KB yapımcı/yönetmen-dolgu/TÜR/afiş + v4 düzen
    # (efekt-siz kanal, sadece Yön+Yap, BÜYÜK-harf özet). kunye_teslim.md'den özet/kanal/süre okur.
    # GÜVENLİ: kunye_v4.pdf'e yazar, BAŞARIRSA kunye.pdf üzerine taşır; hata olursa eski PDF olduğu gibi kalır.
    rc_v4, out_v4, err_v4, v4_exc = None, "", "", None   # A-1: v4 çökse bile karar kapıları sinyali görsün
    # TÜR DIVERGENCE FIX (2026-06-15): .txt yüzeyi şimdiye dek SADECE tur_xml görüyordu; PDF (v4) ise
    # IMDb/Wikidata fallback'li nihai TÜR'ü basıyordu → .txt ≠ PDF. v4 başarınca nihai TÜR'ü (rapor JSON)
    # yakala ve surface'a ilet. v4 koşmaz/başarısızsa tur_xml fallback (eski davranış, additive).
    tur_final = tur_xml
    v4_credits = None   # PROPAGATION fix: V4 otoriter cast/yön/yapımcı → surface .txt'yi PDF ile hizalar
    _v4j = None         # K1 FIX (2026-06-20): erken init — v4 çökerse/profil film-dışıysa _v4j atanmaz,
                        #   satır ~2036 MITAS_QC_BLOCK bloğu (_v4j or {}) → UnboundLocalError çökme önlenir.
    _v4_off = os.environ.get("MITAS_NO_V4_FINAL", "").strip().lower() in ("1", "true", "yes", "on")
    if USE_VIDEO_CREDITS and profile in ("film", "dizi") and pdf_info.get("pdf_path") and not _v4_off:
        t_v4 = time.perf_counter()
        try:
            v4_tmp = pdf_out / "kunye_v4.pdf"
            # FİLM NOTU (2026-07-04, Çağatay): deterministik pipeline-sinyalleri → v4 PDF FİLM NOTU kutusu.
            # Yalnız KESİN ölçülmüş durumlar (sinyal→standart-cümle; LLM-üretimi serbest metin YOK).
            _v4_anim = False                        # v4 rapor 'animasyon' bayrağı (aşağıda dolar; QC bastırmada kullanılır)
            _film_notu_pipe = []
            try:
                _fn_seg = int(asr_info.get("clean_segments") or 0)
                _fn_chr = int(asr_info.get("transcript_chars") or 0)
                if asr_status == "done" and _fn_seg == 0 and _fn_chr < 40:
                    _film_notu_pipe.append("SESSİZ/DİYALOGSUZ — filmde konuşma tespit edilemedi; özet üretilemez.")
                if ocr_bucket == "BOS" or (ocr_lines or 0) == 0:
                    _film_notu_pipe.append("JENERİK YOK — filmde okunur jenerik tespit edilemedi.")
            except Exception:  # noqa: BLE001 — not üretimi PDF akışını ASLA bozmaz
                _film_notu_pipe = []
            v4_cmd = [str(PY_PDF), str(HERE / "tek_film_kunye.py"),
                      "--clip", str(clip_dir), "--title", title, "--out", str(v4_tmp)]
            if _film_notu_pipe:
                v4_cmd += ["--notlar", json.dumps(_film_notu_pipe, ensure_ascii=False)]
            if original:
                v4_cmd += ["--original", original]
            if film_year:
                v4_cmd += ["--year", str(film_year)]
            if video_credits:
                v4_cmd += ["--video-credits", json.dumps(video_credits, ensure_ascii=False)]
            if xml_role_map:
                v4_cmd += ["--xml-roles", json.dumps(xml_role_map, ensure_ascii=False)]
            v4_cmd += ["--profile", profile]               # Fix 3b: film/dizi → tek_film_kunye.py'e ilet
            if tur_xml:
                v4_cmd += ["--tur", tur_xml]
            if bolum:
                v4_cmd += ["--bolum", bolum]               # Fix 3b: BİZİM EVİN HALLERİ vb. bölüm numarası
            rc_v4, out_v4, err_v4 = run(v4_cmd, timeout=V4_TIMEOUT)
            if rc_v4 == 0 and v4_tmp.exists() and v4_tmp.stat().st_size > 10000:
                os.replace(str(v4_tmp), pdf_info["pdf_path"])
                v4_png = pdf_out / "kunye_v4_onizleme.png"
                if v4_png.exists():
                    os.replace(str(v4_png), str(pdf_out / "kunye_onizleme.png"))
                # Nihai TÜR'ü v4 rapor JSON'ından al (PDF ile .txt'i hizala). "—"/boş ise tur_xml kalır.
                try:
                    # K2 FIX (2026-06-20): tek_film_kunye rapor'u indent=2 ÇOK-SATIR basar → last_json
                    # (tek-satır arar) HEP None döndürüyordu → v4_credits HEP None → PROPAGATION ÖLÜYDÜ.
                    # Satır ~1907'deki ile AYNI raw_decode'a geçildi; v4_credits artık gerçek V4 değerini alır.
                    _ji = out_v4.find("{")
                    _v4j = {}
                    if _ji >= 0:
                        _v4j, _ = json.JSONDecoder().raw_decode(out_v4[_ji:])
                    _v4tur = ((_v4j.get("v4") or {}).get("tur") or "").strip()
                    if _v4tur and _v4tur != "—":
                        tur_final = _v4tur
                    # PROPAGATION fix: V4 otoriter cast/yön/yapımcı/keyword → yüzey .txt PDF ile birebir
                    _v4block = _v4j.get("v4") or {}
                    if isinstance(_v4block, dict) and ("cast_list" in _v4block or "yonetmen_list" in _v4block):
                        v4_credits = _v4block
                    _v4_anim = bool(isinstance(_v4block, dict) and _v4block.get("animasyon"))
                except Exception:  # noqa: BLE001 — TÜR yakalama yüzeylemeyi ASLA bozmaz
                    pass
                timings["v4_final"] = round(time.perf_counter() - t_v4, 2)
                dbg.emit("v4", "stage_completed",
                         duration_ms=timings["v4_final"] * 1000,
                         subject={"field": "v4_pdf", "after": pdf_info.get("pdf_path"),
                                  "reason": "v4 final replaced pre-v4 PDF"},
                         evidence={"v4": ((_v4j or {}).get("v4") or {}),
                                   "cross_check": ((_v4j or {}).get("adimlar") or {}).get("cross_check")},
                         source={"module": "scripts/mitas_pipeline.py",
                                 "input_paths": [str(v4_tmp), str(clip_dir)],
                                 "output_paths": [str(pdf_info.get("pdf_path") or "")]})
                log_event("v4_finalize_completed",
                          summary=f"{video.name}: kunye v4'e cevrildi ({timings['v4_final']} sn).",
                          module="pdf", media_id=media_id, filename=video.name,
                          duration_seconds=timings["v4_final"], detail={"clip_id": clip_id})
            else:
                dbg.emit("v4", "stage_completed", status="warn",
                         subject={"field": "v4_pdf", "reason": f"v4 final skipped rc={rc_v4}"},
                         evidence={"stderr": (err_v4 or "")[-1000:]},
                         source={"module": "scripts/mitas_pipeline.py", "input_paths": [str(clip_dir)]})
                log_event("v4_finalize_skipped", level="warn",
                          summary=f"{video.name}: v4 final atlandi (rc={rc_v4}); pre-v4 PDF kaldi.",
                          module="pdf", media_id=media_id, filename=video.name,
                          detail={"clip_id": clip_id, "stderr": (err_v4 or "")[-200:]})
        except Exception as exc:  # noqa: BLE001 — v4 final akışı/PDF'i ASLA bozmaz
            v4_exc = f"{type(exc).__name__}: {exc}"
            log_event("v4_finalize_failed", level="warn", summary=f"v4 final hata (atlandi): {exc}",
                      module="pdf", media_id=media_id, filename=video.name, error=str(exc), detail={"clip_id": clip_id})
    elif _v4_off and USE_VIDEO_CREDITS and profile in ("film", "dizi") and pdf_info.get("pdf_path"):
        log_event("v4_finalize_skipped", level="info",
                  summary=f"{video.name}: v4 final MITAS_NO_V4_FINAL ile atlandi; _pipe_pdf PDF'i korundu.",
                  module="pdf", media_id=media_id, filename=video.name, detail={"clip_id": clip_id})

    # ===== qwen FINAL-QC: render edilen v4 künyeyi GÖR + beklentileri doğrula (Hazır kapısına ek) =====
    # qwen2.5vl önizleme PNG'sine bakar; SADECE-gördüğüyle eksik bulursa (placeholder özet / eksik afiş /
    # küçük-harf / bozuk-İ / yön+yapımcı yok) → Kontrol. Ollama yok/hata → atla (kapıyı BOZMA, kural-tabanlıya düş).
    qwen_qc = None
    _qc_png = pdf_out / "kunye_onizleme.png"
    if profile in ("film", "dizi") and _qc_png.exists():
        _t_qc = time.perf_counter()
        try:
            sys.path.insert(0, str(HERE))
            import _kunye_qwen_check as _kqc
            qwen_qc = _kqc.check(str(_qc_png))
            timings["qwen_qc"] = round(time.perf_counter() - _t_qc, 2)
            dbg.emit("qc_final", "qc_decision",
                     duration_ms=timings["qwen_qc"] * 1000,
                     subject={"field": "qwen_qc", "after": qwen_qc,
                              "reason": "visual final QC over preview PNG"},
                     evidence={"preview": str(_qc_png), "qwen_qc": qwen_qc},
                     source={"module": "scripts/mitas_pipeline.py", "input_paths": [str(_qc_png)]})
            log_event("qwen_final_qc",
                      summary=f"{video.name}: qwen final-QC ({timings.get('qwen_qc')} sn) — {(qwen_qc or {}).get('notlar') or 'ok'}",
                      module="qc", media_id=media_id, filename=video.name,
                      detail={"clip_id": clip_id, "qwen_qc": qwen_qc})
        except Exception as exc:  # noqa: BLE001 — qwen-QC pipeline'i ASLA bozmaz (ollama yok/model yok vb.)
            qwen_qc = {"error": f"{type(exc).__name__}: {exc}"}
            dbg.emit("qc_final", "qc_decision", status="warn",
                     subject={"field": "qwen_qc", "reason": "qwen final QC skipped"},
                     evidence={"preview": str(_qc_png)}, error=str(exc),
                     source={"module": "scripts/mitas_pipeline.py", "input_paths": [str(_qc_png)]})
            log_event("qwen_final_qc_skipped", level="warn",
                      summary=f"{video.name}: qwen final-QC atlandi: {exc}",
                      module="qc", media_id=media_id, filename=video.name, detail={"clip_id": clip_id})

    # ===== YONLENDIR (Hazir/Kontrol) =====
    reasons = []
    qwen_uyari = []   # FIX-C (2026-07-06): erken bloklar da uyarı yazabilsin diye init öne alındı
    # LLM-PREFLIGHT sonucu (2026-07-03): model deposu kopuksa film GÖRÜNÜR işaretlenir — böyle bir
    # film "yönetmen okunamadı" ile karışmaz; disk/depo onarılınca yeniden koşulması gerektiği bellidir.
    if _llm_dead:
        reasons.append("LLM katmanı çalışmadı (ollama model deposu boş/erişilemez — film yeniden koşulmalı)")
    _person_gate_report = {}
    # SES-DİL KAPISI (Çağatay 2026-06-20): ses/dil/ASR sorunu KÜNYE sorunu DEĞİL → tek başına KONTROL'e
    # YOLLAMAZ (özet'i Çağatay ayrı ele alır). Default KAPALI; MITAS_SES_DIL_KONTROL=1 ile geri açılır.
    _SES_DIL_GATE = os.environ.get("MITAS_SES_DIL_KONTROL", "").strip().lower() in ("1", "true", "on", "yes")
    if ocr_bucket not in ("GUVENILIR",):
        reasons.append(f"OCR bucket={ocr_bucket}")
    if _SES_DIL_GATE and asr_status not in ("done", "ATLANDI", "skipped_unsupported_lang"):  # Kürtçe-atla = kasıtlı
        reasons.append(f"ASR={asr_status}")
    if not pdf_info.get("pdf_path"):
        reasons.append("PDF render yok (md teslim)")
    # --- B-4: XML↔PDF cast tutarlılık kapısı (yanlış-film yakala) ---
    # XML oyuncu listesi ≥2 isim VE üretilen cast ≥2 isim VE fold/fuzzy kesişim == 0 → şüphe.
    # Tek-isim/boş listede FLAG YOK (dizi kısmi-kadro false-positive'ini önle).
    # C9 FIX (2026-06-22): erken reasons.append KALDIRILDI → yalnız şüphe işareti (_xmlcast_susp) set edilir.
    # Asıl karar _cc4 (kimlik/verdict/cast_ortusme) bilindikten SONRA emit edilir (aşağıda).
    # credit_crosscheck.name_match/cast_overlap helper'larını YENİDEN YAZMADAN kullan.
    _xmlcast_susp = False
    try:
        _xml_cast = [n for n in (xml_role_map.get("oyuncu") or []) if str(n).strip()]
        _pdf_cast = [n for n in (pdf_info.get("cast") or []) if str(n).strip() and str(n).strip() != "—"]
        if len(_xml_cast) >= 2 and len(_pdf_cast) >= 2:
            sys.path.insert(0, str(HERE))
            import credit_crosscheck as _cc
            _xmlcast_susp = (_cc.cast_overlap(_pdf_cast, _xml_cast) == 0)
    except Exception:  # noqa: BLE001 — kesişim kapısı kararı ASLA bozmaz (helper yoksa/hata → atla)
        _xmlcast_susp = False
    # A-3: ana_dil yabancı + altyazı YOK = SES_MANTIKSIZ → ses-dil kapısı (default KAPALI, künye-dışı)
    if _SES_DIL_GATE and pdf_info.get("ses_uyari") == "SES_MANTIKSIZ":
        reasons.append("ana_dil yabancı + altyazı yok (SES_MANTIKSIZ)")
    # C1 FIX (2026-06-20): QC1 çift-katman RED (OneOCR→35b→VL ikisi de QC1'i geçemedi → _qc1_failed işareti
    # ~1652'de set ediliyordu ama HİÇBİR YERDE okunmuyordu = ölü-kablo). En kötü-kalite künye; v4 KB-fill
    # yanlış-kimlikten yön doldurursa diğer kapılar maskelenip sessizce ONAYLI olabiliyordu → KONTROL'e bağla.
    _cv_strong_director = _credit_validate_strong_director(cv_result) if cv_result else bool(
        isinstance(video_credits, dict) and video_credits.get("_credit_validate_strong_director"))
    # APOLLO 11 fix (2026-07-12): QC1-RED kriteri "yönetmen boş VEYA cast<3". Yönetmen QC1 anında
    # ND-UNIT-garble bloklandığı için BOŞtu → RED; ama tek_film_kunye SONRA ham-OCR'da KB-adıyla BİREBİR
    # corroborate etti (yon_ocr_teyit) ve cast≥3 → QC1-RED artık BAYAT sinyal (yönetmen okundu + cast yeterli).
    # Bu, credit_validate strong-director override'ının (2910) OCR-corroboration muadili. Cast<3 veya
    # corroboration yoksa QC1-RED KORUNUR (gerçek düşük-kalite). (read-after-resolve dikişi, aynı kök.)
    _yon_ocr_corrob = bool((((_v4j or {}).get("adimlar") or {}).get("cross_check") or {}).get("yon_ocr_teyit"))
    _qc1_cast_ok = bool(isinstance(video_credits, dict) and len(video_credits.get("cast") or []) >= 3)
    if isinstance(video_credits, dict) and video_credits.get("_qc1_failed") and not _cv_strong_director:
        if _yon_ocr_corrob and _qc1_cast_ok:
            qwen_uyari.append("QC1-RED bayat: yönetmen ham-OCR'da KB-adıyla teyitli + cast≥3 (yon_ocr_teyit) → karar-etkisiz uyarı")
        else:
            reasons.append("QC1 başarısız (OCR+VL ikisi de RED — düşük künye kalitesi, OCR yetersiz)")
    # --- B-4 bonus: tek_film_kunye.py (v4) KB cross-check çelişkisini karara yansıt ---
    # out_v4 yakalanıyordu ama parse edilmiyordu. tek_film_kunye.py rapor'u indent=2 ÇOK-SATIR
    # basar (last_json tek-satır arar, tutmaz) → ilk '{'tan raw_decode ile blok-parse.
    # verdict/kimlik_dogru rapor["adimlar"]["cross_check"] altında (top-level değil).
    try:
        if USE_VIDEO_CREDITS and profile in ("film", "dizi") and pdf_info.get("pdf_path"):
            if v4_exc is not None or rc_v4 != 0:
                # A-1: v4 koşamadı/çöktü → kapılar değerlendirilemedi; SESSİZCE ONAYLI'ya GİDEMEZ
                reasons.append("v4 final çalışmadı (" + (("exc: " + v4_exc[:80]) if v4_exc else f"rc={rc_v4}") + ") — yönetmen/özet/kimlik doğrulanamadı")
            else:
                _v4j = None
                _i = out_v4.find("{")
                if _i >= 0:
                    try:
                        _v4j, _ = json.JSONDecoder().raw_decode(out_v4[_i:])
                    except Exception:  # noqa: BLE001
                        _v4j = None
                # B1 FIX (2026-06-20): rc==0 ama v4 rapor JSON parse edilemediyse (_v4j boş) TÜM künye-kapıları
                # (_v4j or {}) ile sessizce geçer → doğrulanmamış film ONAYLI'ya gider. rc!=0 ile AYNI invariant:
                # "kapılar değerlendirilemedi → SESSİZCE ONAYLI'ya GİDEMEZ" → KONTROL.
                if not isinstance(_v4j, dict) or not _v4j:
                    reasons.append("v4 rapor parse edilemedi (rc=0 ama JSON okunamadı) — yönetmen/özet/kimlik doğrulanamadı")
                _cc4 = ((_v4j or {}).get("adimlar") or {}).get("cross_check") or {}
                _gate4 = _cc4.get("global_person_gate") or {}
                _person_gate_report = _gate4 if isinstance(_gate4, dict) else {}
                _gate_drops = []
                if isinstance(_gate4, dict):
                    for _role, _gr in _gate4.items():
                        if isinstance(_gr, dict):
                            for _nm in (_gr.get("dropped") or []):
                                if isinstance(_nm, dict):
                                    _gate_drops.append(f"{_role}:{_nm.get('in') or ''}")
                                else:
                                    _gate_drops.append(f"{_role}:{_nm}")
                if _gate_drops:
                    reasons.append("global kişi kapısı düşürdü: " + ", ".join(_gate_drops[:6]))
                # VERSİYON GÜVENLİĞİ (OCR-otorite kanunu 2026-06-13): web YALNIZ title+year ile kilitlediyse
                # (qc2_web method=tmdb; cast/yönetmen bağımsız teyit YOK) = versiyon BELİRSİZ (aynı başlık
                # 88/96 farklı film riski). Asla otomatik ONAYLI değil → KONTROL (insan versiyonu onaylar).
                # ANCHOR-1 (method=director, OCR-yönetmen eşleşti) versiyon-teyitli → bu kural onu TUTMAZ.
                _qc2_web4 = ((_v4j or {}).get("adimlar") or {}).get("qc2_web") or {}
                if str(_qc2_web4.get("method")) == "tmdb":
                    reasons.append("versiyon cast-teyitsiz (web title+year kilidi — insan onayı)")
                # OCR-OTORİTE (A+A 2026-06-13): cast'te KB-imzasız garble OCR ismi var → SİLİNMEDİ
                # (OCR otorite), insan temizlesin → KONTROL.
                if _cc4.get("cast_garble"):
                    reasons.append("cast garble şüphesi (OCR-otorite — KB-imzasız isim, insan teyidi)")
                # GARBLE-ROUTING (2026-06-20): nihai cast/yön'de LEKSİKAL garble (rol/kurum token 'CRAFT
                # SERVICES', cümle-eki, garbled rol-etiketi) kaldıysa → KONTROL (KB-bağımsız, FUZZY-DBQC
                # kurtaramadı; "okunamadı>yanlış", SİLME YOK). Sinyal tek_film_kunye rapor.v4'ten.
                _v4blk_g = (_v4j or {}).get("v4") or {}
                if (_v4blk_g.get("cast_garble_lex_count") or 0) > 0:
                    reasons.append("cast garble (leksikal, kurtarılamadı — insan teyidi)")
                if _v4blk_g.get("yon_garble_lex"):
                    reasons.append("yönetmen okunamadı (garble — leksikal)")
                # QC2 (flag): kimlik KİLİTLİ iken yönetmeni KB ile çözdüyse (çelişki=cameo→gerçek yön),
                # "kimlik çelişkisi" reason'ı tetikleme — QC2 hatayı düzeltti → ONAYLI'ya gidebilir.
                _qc2_on = os.environ.get("MITAS_QC2", "").strip().lower() in ("1", "true", "on", "yes")
                _qc2_resolved = str(_cc4.get("yonetmen_kaynak", "")).startswith("QC2")
                if _is_strong_screen_alias_conflict(_cc4):
                    qwen_uyari.append(
                        "yönetmen ekran adı KB adından farklı (güçlü rol kanıtlı; mahlas/AKA olabilir)"
                    )
                if _has_identity_contradiction(
                        _cc4, qc2_resolved=bool(_qc2_on and _qc2_resolved),
                        strong_director=bool(_cv_strong_director)):
                    reasons.append("kimlik çelişkisi (KB cross-check)")
                # KIRMIZI ÇİZGİ (2026-06-07): yönetmen OCR'dan okunamadıysa KB-fill YOK → künye Kontrol'e
                # (zorla doldurma yok; insan teyidi). v4 raporu yönetmeni boşsa işaretle.
                _v4_yon = (((_v4j or {}).get("v4") or {}).get("yonetmen") or [])
                if not _v4_yon:
                    reasons.append("yönetmen okunamadı (KB-fill yok — kırmızı çizgi)")
                    # A0 (2026-07-03): VL'nin okuyup hayalet-kalkanının düşürdüğü aday İNSANA görünür
                    # olsun — bugüne dek yalnız debug-trace'e gidiyordu, denetçi Askoldov/Jackson gibi
                    # DOĞRU adayları sıfırdan araştırmak zorunda kalıyordu. Alan DOLDURULMAZ (kırmızı
                    # çizgi korunur), yalnız gerekçeye ipucu eklenir. Metin, router substring'leriyle
                    # ("yönetmen okunamadı" vb.) ÇAKIŞMAZ → routing değişmez (karar-nötr, salt-görünürlük).
                    try:
                        if isinstance(video_credits, dict):
                            _vl_aday = list(video_credits.get("vl_yon_hallucinated") or [])
                            _vl_aday += list(video_credits.get("vl_yon_cast_dropped") or [])
                            _vl_aday += list(video_credits.get("vl_yon_dop_dropped") or [])
                            if _vl_aday:
                                reasons.append("VL aday ismi (teyitsiz, insan baksın): "
                                               + ", ".join(dict.fromkeys(str(x) for x in _vl_aday))[:120])
                    except Exception:  # noqa: BLE001 — yüzeyleme ASLA kararı bozmaz
                        pass
                elif isinstance(video_credits, dict) and any(
                        t in str(video_credits.get("vl_yon_kaynak") or "") for t in ("fuzzy", "kb-anchor")):
                    # İnceleme-koşulu (2026-07-03, Fable-1/Opus-F1): fuzzy/yazım-varyant VEYA kb-anchor
                    # (A2 shadow-dönemi) yoluyla dolan VL-yönetmen ASLA sessizce ONAYLI'ya gidemez —
                    # isim PDF'te kalır (insan hızla teyit eder) ama film KONTROL'e işaretlenir.
                    # exact/crossline(kart-istifi) bu bendin DIŞINDADIR (güçlü kanıt).
                    _vlk = str(video_credits.get("vl_yon_kaynak") or "")
                    reasons.append(f"yönetmen VL-dolumu ({_vlk.split('+', 1)[-1]} teyidi — insan onayı bekler)")
                elif len(_v4_yon) > 2:
                    # A-2: tek/çift yönetmen normal; 3+ isim = crew karışması şüphesi → insan baksın
                    reasons.append(f"yönetmen listesi şüpheli ({len(_v4_yon)} isim — crew karışması olası)")
                elif any(len(str(_n).strip()) > 45 for _n in _v4_yon):
                    reasons.append("yönetmen adı şüpheli (>45 karakter — OCR cümle karışması)")
                # ÖZET KAPISI (QC2-sistemik, DETERMİNİSTİK — qwen-QC'ye bağlı DEĞİL, her zaman çalışır):
                # v4 özeti placeholder reddi sonrası "—"/boş ya da çok kısa (gerçek özet üretilmemiş).
                # KONTROL-MAHKEMESİ FIX-C (2026-07-06, Çağatay anayasası): özet-yokluğu KÜNYE
                # kalitesinden bağımsızdır (sessiz-film meşru-boş VEYA ASR/LLM-katman arızası =
                # yeniden-koşu işi) → künyesi tam filmi tek başına Kontrol'e DÜŞÜRMEZ; uyarı +
                # ÖZET-KUYRUK işareti olur. Placeholder-çöp zaten v4'te reddedilip boşaltılıyor
                # (PDF'e çöp girmez). Eski davranış: MITAS_OZET_KONTROL=1.
                _v4_ozk = ((_v4j or {}).get("v4") or {}).get("ozet_kelime", 0) or 0
                if _v4_ozk < 20:
                    if os.environ.get("MITAS_OZET_KONTROL", "0").strip().lower() in ("1", "true", "on", "yes"):
                        reasons.append(f"özet yok/kısa ({_v4_ozk}k — gerçek özet üretilmemiş)")
                    else:
                        qwen_uyari.append(f"özet-eksik({_v4_ozk}k) → ÖZET-KUYRUK adayı (karar-etkisiz)")
                # C9 FIX (2026-06-22): XML-PDF cast kesişimi 0 şüphesini _cc4 bilgisiyle değerlendir.
                # kimlik_dogru veya verdict==TEYİT veya cast_ortusme≥2 → film doğrulandı → KONTROL ekleme.
                # _cc4=={} (parse hatası) → _locked=False → şüphe korunur (sessiz-pass YOK).
                _relax_xmlcast = os.environ.get("MITAS_XMLCAST_GATE_RELAX", "1").strip().lower() not in ("0", "false", "off", "no")
                if _xmlcast_susp:
                    _locked_xmlcast = bool(_cc4.get("kimlik_dogru")) or (_cc4.get("verdict") == "TEYİT") or ((_cc4.get("cast_ortusme") or 0) >= 2)
                    if not (_relax_xmlcast and _locked_xmlcast):
                        reasons.append("XML-PDF cast kesişimi 0 (yanlış-film şüphesi)")
    except Exception:  # noqa: BLE001 — parse hatası kararı bozmasın
        pass
    _ocr_bucket_reason = f"OCR bucket={ocr_bucket}"
    if _ocr_bucket_reason in reasons and _ocr_bucket_can_be_warning(ocr_bucket, _v4j):
        reasons = [r for r in reasons if r != _ocr_bucket_reason]
        qwen_uyari.append(
            "OCR bucket=GOZDEN_GECIR bastırıldı: final v4 kimlik/künye temiz "
            "(karar-etkisiz, ham OCR görünürlük)"
        )
    # B-3 qwen-QC kalibrasyonu: afiş + büyük-harf qwen sinyalleri KIRILGAN (VLM yanılır; üstelik
    # büyük-harf zaten deterministik tr_upper/ozet_v4, afiş poster_fetch ile garanti) → bu İKİ sinyal
    # Kontrol TETİKLEMEZ, yalnız qwen_uyari'ya (log/QC görünürlüğü) yazılır. Diğer 5 sinyal reasons'ta KALIR.
    # (qwen_uyari init'i FIX-C ile YONLENDIR başına taşındı — burada SIFIRLANMAZ)
    if qwen_qc and not qwen_qc.get("error"):   # qwen final-QC: model gözüyle son kapı (PDF'i gören)
        if not qwen_qc.get("ozet_var"):
            # FIX-C (2026-07-06): özet-yokluğu karar-etkisiz (üstteki deterministik kapıyla aynı kural)
            if os.environ.get("MITAS_OZET_KONTROL", "0").strip().lower() in ("1", "true", "on", "yes"):
                reasons.append("qwen: özet yok/placeholder")
            else:
                qwen_uyari.append("qwen: özet yok/placeholder (ÖZET-KUYRUK — karar-etkisiz)")
        if (qwen_qc.get("oyuncu_sayisi") or 0) < 1 and not _v4_anim:
            reasons.append("qwen: oyuncu yok")     # ANİMASYON muaf (2026-07-04): oyuncu alanı BİLEREK boş
        elif (qwen_qc.get("oyuncu_sayisi") or 0) < 1 and _v4_anim:
            qwen_uyari.append("qwen: oyuncu yok (animasyon — bilinçli boş, KONTROL tetiklemez)")
        if not qwen_qc.get("yonetmen_var") and not qwen_qc.get("yapimci_var"):
            reasons.append("qwen: yön+yapımcı yok")
        if _SES_DIL_GATE and not qwen_qc.get("ses_dil_var"):
            reasons.append("qwen: ses/dil yok")
        if qwen_qc.get("turkce_karakter_bozuk_var"):
            reasons.append("qwen: Türkçe karakter bozuk")
        if qwen_qc.get("latin_disi_alfabe_var"):                # başka alfabe (Kiril/Yunan/Arap/CJK) PDF'e sızmamalı
            reasons.append("qwen: Latin-dışı alfabe (deterministik kemer atladı → Kontrol)")

    # yönetmen doğrulama (credit_validate, flag-gated): kaynak-çelişkisi/okunamadı → KONTROL sinyali
    if cv_result:
        _cvd = cv_result.get("yonetmen") or {}
        if _cvd.get("status") == "CELISKI":
            _ad = ", ".join((_cvd.get("conflict_candidates") or [])[:3])
            reasons.append(f"yönetmen doğrulama: kaynak-çelişkisi (aday: {_ad})" if _ad else "yönetmen doğrulama: kaynak-çelişkisi")
        elif _cvd.get("status") == "OKUNAMADI":
            # APOLLO 11 fix (2026-07-12): credit_validate garble-ÖNCESİ girdide "okunamadı" der; ama
            # tek_film_kunye yönetmeni ham-OCR korpusunda KB-adıyla BİREBİR teyit ettiyse (yon_ocr_teyit:
            # kimlik güçlü + isim fiziksel OCR'da mevcut → KÖR KB-fill DEĞİL) alan aslında OKUNDU. Bu bayat
            # sinyal routing'i yanlış-Kontrol'e sürüklemesin → karar-etkisiz uyarıya indir. (read-after-resolve)
            _yon_ocr_teyit = bool((((_v4j or {}).get("adimlar") or {}).get("cross_check") or {}).get("yon_ocr_teyit"))
            if _yon_ocr_teyit:
                qwen_uyari.append("yönetmen: credit_validate 'okunamadı' DEDİ ama ham-OCR'da KB-adıyla birebir teyitli (yon_ocr_teyit) → karar-etkisiz uyarı")
            else:
                reasons.append("yönetmen doğrulama: okunamadı (yeniden-okuma/insan)")
        # KIRILGAN ikili → uyarı (karar değil): false-Kontrol azalt. C4 FIX (2026-06-20): qwen_qc None-guard
        # (qwen-QC atlandıysa qwen_qc=None kalır; bu blok `if cv_result:` içinde → MITAS_CREDIT_VALIDATE=1 +
        # preview-PNG yok'ta None.get → AttributeError film-çökme. Guard ile önlenir; default env'de zaten dormant).
        if qwen_qc and not qwen_qc.get("afis_var"):
            qwen_uyari.append("qwen: afiş yok (deterministik poster_fetch garanti — uyarı)")
        if qwen_qc and not qwen_qc.get("hepsi_buyuk_harf"):
            qwen_uyari.append("qwen: büyük-harf değil (deterministik tr_upper — uyarı)")
        if qwen_qc and qwen_qc.get("yabanci_ad_ascii_degil"):  # yabancı ad aksanlı: kemer+Sonnet birincil, qwen ince-aksanda güvenilmez → uyarı
            qwen_uyari.append("qwen: yabancı ad aksanlı/ASCII değil (deterministik kemer+Sonnet birincil — uyarı)")
    # --- ZİNCİR SONU: DETERMİNİSTİK isim/künye TESPİT-QC (karakter→DB→DeepSeek→ASCII zincirinin SON kapısı) ---
    # Kural: künye SADECE Latin; TÜRKÇE ad Türkçe-harf, YABANCI ad SADE ASCII. Türkçe harf (çğıİöşü) SERBEST;
    # non-ASCII + non-Türkçe HARF (é/ñ/ø/Kiril/Yunan/CJK...) = NET İHLAL → Kontrol. qwen-QC görsel+kırılgan;
    # bu kemer karakter düzeyinde %100 deterministik — isim/özet çıktısında KAÇANI yakalar. Paylaşımlı ç/ö/ü
    # yabancıda ayırt edilemez (onu Sonnet/DB+qwen kapsar); bu yalnız KESİN ihlalleri Kontrol'e düşürür.
    try:
        _TR_OK = set("çÇğĞıİöÖşŞüÜ")
        def _bad_chars(_s):
            return sorted({c for c in str(_s or "")
                           if (not c.isascii()) and unicodedata.category(c).startswith("L") and c not in _TR_OK})
        _name_qc = []
        for _nm in (pdf_info.get("cast") or []):
            _b = _bad_chars(_nm)
            if _b:
                _name_qc.append(f"oyuncu '{_nm}'→{''.join(_b)}")
        for _role, _nms in (pdf_info.get("crew") or []):
            for _nm in (_nms if isinstance(_nms, list) else [_nms]):
                _b = _bad_chars(_nm)
                if _b:
                    _name_qc.append(f"{_role} '{_nm}'→{''.join(_b)}")
        _bo = _bad_chars(ozet)
        if _bo:
            _name_qc.append(f"özet→{''.join(_bo)}")
        if _name_qc:
            reasons.append("isim-QC: Latin-dışı/yabancı-aksan kalıntısı (" + " ; ".join(_name_qc[:5]) + ")")
    except Exception:  # noqa: BLE001 — tespit-QC kararı ASLA bozmaz (alan yok/hata → atla)
        pass
    # ── BİRLEŞİK QC BLOĞU (flag MITAS_QC_BLOCK): tek_film_kunye'nin yazdığı qc_block kararının NEW
    #    kapılarını (floor-8 / Latin-dışı kalıntı / kimlik-kurulamadı) reasons'a KAT. ADDITIVE: yalnız
    #    EKLER, mevcut reasons'ı EZMEZ (yanlış-ONAYLI üretmez). Default kapalı → blok hiç çalışmaz.
    _qcb_floor_fail = False
    if os.environ.get("MITAS_QC_BLOCK", "").strip().lower() in ("1", "true", "on", "yes"):
        _qcb4 = (_v4j or {}).get("v4") or {}
        _qcb_fl = _qcb4.get("qc_block_floor") or {}
        _qcb_floor_fail = bool(_qcb_fl.get("hedef") == 8 and not _qcb_fl.get("kabul")
                               and (_qcb_fl.get("ulasilan", 0) or 0) >= 1)
        for _g in (_qcb4.get("qc_block_gerekceler") or []):
            # B2 FIX (2026-06-20): "oyuncu yok" (sıfır-cast) eklendi — legacy'de deterministik boş-cast kapısı
            # YOK; qc_block "oyuncu yok" der ama bu filtre köprülemiyordu → sıfır-cast film sessizce ONAYLI'ya
            # gidiyordu. Diğer qc_block gerekçeleri (cast garble/özet/afiş) zaten legacy kapılarca yakalanır.
            if (("oyuncu yetersiz" in _g) or ("oyuncu yok" in _g)
                    or ("Latin-dışı" in _g) or ("kimlik kurulamadı" in _g)
                    or ("zayıf-teyit" in _g)):   # C2 FIX: director-anchor-weak KONTROL'ü köprüle
                # ANİMASYON muaf (2026-07-04): oyuncu alanı BİLEREK boş (seslendirme kadrosu) —
                # cast-boşluğu sinyalleri KONTROL tetiklemez; kimlik/Latin-dışı sinyaller KALIR.
                if _v4_anim and (("oyuncu yetersiz" in _g) or ("oyuncu yok" in _g)):
                    qwen_uyari.append("qc_block: " + _g + " (animasyon — bilinçli boş)")
                    continue
                _gk = "qc_block: " + _g
                if _gk not in reasons:
                    reasons.append(_gk)
        # FIX-B (2026-06-23): OCR-OTORİTE İHLALİ ROUTE (flag MITAS_QC_OTORITE_ROUTE, default ON).
        #   credit_qc_block.otorite_audit.ocr_authority_violation == True → KEDİ GÖZÜ substitüsyon
        #   imzası (ham-OCR'da OKUNAN başrol final'de DÜŞTÜ + ham-OCR'da OLMAYAN saf-KB ismi EKLENDİ).
        #   Şimdiye dek SIFIR-ROUTE (yalnız _DURUM'a yazılıyordu); artık ADDITIVE reason → KONTROL.
        #   Yalnız reason EKLER (ONAYLI'yı ASLA üretmez); audit boş/None/{'hata':True} → sessiz atla.
        if os.environ.get("MITAS_QC_OTORITE_ROUTE", "").strip().lower() in ("1", "true", "on", "yes"):
            _qcb_aud = _qcb4.get("qc_block_otorite_audit") or {}
            if isinstance(_qcb_aud, dict) and _qcb_aud.get("ocr_authority_violation") is True:
                # Auditability: hangi başrol düştü / hangi okunmayan eklendi reason'a göm (denetlenebilir).
                _drp = ", ".join([str(x) for x in (_qcb_aud.get("ocr_dropped") or [])][:3])
                _add = ", ".join([str(x) for x in (_qcb_aud.get("kb_floor_added") or [])][:3])
                _ar = ("qc_block: OCR-otorite ihlali — okunan düştü: " + (_drp or "?")
                       + " | okunmayan eklendi: " + (_add or "?"))
                if not any(r.startswith("qc_block: OCR-otorite ihlali") for r in reasons):
                    reasons.append(_ar)
        # fix3-A 2026-06-29 — CAST_CAP_DUSEN köprüsü. KONTROL-MAHKEMESİ FIX-D (2026-07-06,
        # Çağatay anayasası): sinyalin orijinal niyeti GÖRÜNÜRLÜK'tü ama reasons'a eklenince
        # tek başına dolu-PDF filmi Kontrol'e düşürüyordu (MURDER SCENE vakası, kod-teyitli).
        # Artık YALNIZ uyarı katmanına yazılır (karar-etkisiz); _DURUM/log'da görünür kalır.
        try:
            for _hf in (_qcb4.get("qc_block_hafif") or []):
                _hf_neden = (_hf.get("neden") or "") if isinstance(_hf, dict) else str(_hf)
                if "CAST_CAP_DUSEN" in _hf_neden:
                    if not any("CAST_CAP_DUSEN" in u for u in qwen_uyari):
                        qwen_uyari.append("qc_block: " + _hf_neden + " (görünürlük — karar-etkisiz)")
        except Exception:  # noqa: BLE001 — sinyal hatası pipeline'ı ASLA bozmasın
            pass

    # ── KİŞİ-TEYİT (2026-07-05, Çağatay politika-kararı): "Kişi doğruysa eşleştir; filme kilitlenme."
    #    Ekrandan okunan isimler TEK TEK kişi-olarak KB'de doğrulanır (actress-fix'li verify).
    #    cast>=5 VE kişi-ONAY-oranı>=0.6 VE (yön boş VEYA yön kişi-ONAY) → film-kimliği/teyit sınıfı
    #    reason'ları BASTIRILIR (KB filmi tanımasa bile ONAYLI yolu açılır). "QC1 başarısız" gibi
    #    OKUMA-kalitesi reason'ları KALIR (okunamadı>yanlış-oku korunur). MITAS_KISI_TEYIT=0 kill-switch.
    _kisi_teyit_notu = None
    if (reasons and os.environ.get("MITAS_KISI_TEYIT", "1").strip().lower() not in ("0", "false", "off", "no")):
        try:
            _kt_cast = list((v4_credits or {}).get("cast_list") or [])
            _kt_yon = list((v4_credits or {}).get("yonetmen_list") or [])
            if len(_kt_cast) >= 3:   # süzgeç-sonrası cast zaten teyitli — eşik 3
                sys.path.insert(0, str(HERE))
                import credit_video_read as _cvr
                _kb_kt = _cvr.KB()
                _v_list = [_kb_kt.verify(n, "actor") for n in _kt_cast]
                _on = sum(1 for v in _v_list if v == "ONAY")
                _oran = _on / max(1, len(_kt_cast))
                # KONTROL-MAHKEMESİ FIX-1 (2026-07-06): KB-KAPSAMA-FARKINDALIK — eski/yerel filmlerde
                # KB kişilerin çoğunu hiç TANIMAZ (kayit-yok); onları paydada tutmak kişi-teyidi
                # haksız düşürüyordu (BÜYÜK MÜCADELE 1960 vakası). Oran ayrıca "KB'nin bildiği"
                # kişiler üzerinden hesaplanır: bilinen>=2 VE bilinen-oran>=0.75 de bastırma açar.
                # KB hiç kimseyi tanımıyorsa (bilinen<2) bu dal AÇILMAZ (güvenli taraf).
                _bilinen = sum(1 for v in _v_list if v != "kayit-yok")
                _oran_bilinen = _on / _bilinen if _bilinen else 0.0
                _yon_ok = (not _kt_yon) or any(_kb_kt.verify(n, "director") == "ONAY" for n in _kt_yon)
                if (_oran >= 0.6 or (_bilinen >= 2 and _oran_bilinen >= 0.75)) and _yon_ok:
                    _BASTIR = ("kimlik", "zayıf-teyit", "versiyon cast-teyitsiz",
                               "yönetmen doğrulama: kaynak-çelişkisi")
                    _kalan = [r for r in reasons if not any(b in r for b in _BASTIR)]
                    if len(_kalan) < len(reasons):
                        _kisi_teyit_notu = ("kişi-teyit: cast %d/%d KB-ONAY" % (_on, len(_kt_cast))
                                            + (", yön KB-ONAY" if _kt_yon else ", yön boş")
                                            + " → film-KB'siz doğrulama (Çağatay kuralı)")
                        qwen_uyari.append(_kisi_teyit_notu)
                        reasons = _kalan
        except Exception:  # noqa: BLE001 — kişi-teyit hatası karar akışını ASLA bozmaz
            pass

    # ── QC ROUTING (şiddet × tip) — credit_severity_router: HAFİF→AUTOFIX, AĞIR→tip-klasörü ──
    #    FAIL-SOFT: router import/çağrı hatasında ESKİ ikili karara DÜŞ (pipeline ASLA bozulmaz).
    #    REASON-TEMELLİ (qwen false-pozitif EKLEMEZ): mevcut kalibre 'reasons' tiplenir; 'qwen_uyari' → AUTOFIX.
    # OTORİTE-GÖRÜNÜRLÜK (117-film taraması 2026-07-03, fix#2 AŞAMA-1): qc_block'un "temiz-okunan
    # isim düştü" (ocr_dropped) sinyali karara DEĞİL uyarı-katmanına bağlanır — GENERALİN KIZI /
    # VAHŞETİN ÇAĞRISI (Rutger Hauer!) / SON YARIŞ tipi sessiz-kayıplar artık _DURUM'da görünür.
    # AŞAMA-2 (route'a bağlama) canlı gözlem sonrasına bırakıldı (KONTROL-kuyruğu şişme riski).
    try:
        _oa_drop = list((((_v4j or {}).get("v4") or {}).get("qc_block_otorite_audit") or {}).get("ocr_dropped") or [])
        if _oa_drop:
            qwen_uyari.append("otorite: temiz-okunan isim düştü → " + ", ".join(str(x) for x in _oa_drop[:6]))
    except Exception:  # noqa: BLE001 — görünürlük kararı ASLA bozmaz
        pass
    karar = "Hazır" if not reasons else "Kontrol"          # fallback varsayılan (router hatasında geçerli)
    dest_root = HAZIR if karar == "Hazır" else KONTROL
    route_info = None
    try:
        import credit_severity_router as _router
        _R, _U = (reasons or []), (qwen_uyari or [])
        _sig = {
            "yon_missing":       any(("yönetmen okunamadı" in r) or ("yön+yapımcı yok" in r) or ("yönetmen doğrulama: okunamadı" in r) for r in _R),
            "yon_garble":        any(("yönetmen okunamadı" in r) or ("yönetmen doğrulama: okunamadı" in r) for r in _R),
            "yon_fillable":      False,
            "wrongfilm_suspect": any(("kimlik çelişki" in r) or ("yanlış-film" in r) or ("cast kesişimi 0" in r) or ("kimlik kurulamadı" in r) or ("yönetmen doğrulama: kaynak-çelişkisi" in r) for r in _R),
            "cast_count":        0 if (any("oyuncu yok" in r for r in _R) or _qcb_floor_fail) else 1,
            "cast_all_garble":   any("cast garble" in r for r in _R),   # garble-routing köprüsü (2026-06-20)
            "ozet_missing":      any("özet yok" in r for r in _R),
            "non_latin":         any("Latin-dışı" in r for r in _R),
            "char_broken":       any(("karakter bozuk" in r) or ("isim-QC" in r) for r in _R),
            "char_broken_autofixable": False,   # pipeline'da auto-fix yok → ciddi say
            "afis_missing":      any("afiş yok" in u for u in _U),
            # FIX (Çağatay 2026-06-21): qwen-casing KARARDAN ÇIKARILDI. Casing deterministik tr_upper/
            # ozet_v4 ile ZATEN garanti (16/16 doğru çıktı); qwen2.5vl görü-modeli YAPIM EKİBİ bloğundaki
            # title-case rol-etiketini ("Yönetmen"/"Yapımcı", _make_pdf:243) isim sanıp HEP false basıyordu
            # → temiz filmleri boşuna AUTOFIX'e yolluyordu. qwen_uyari log'u (2021) kalır ama KARAR vermez.
            "casing_bad":        False,
            "foreign_accent":    any("yabancı ad" in u for u in _U),
            # fix3-A 2026-06-29 — CAST_CAP_DUSEN: cap-üstü temiz-okunan oyuncu düştü (hafif; görünürlük)
            "cast_cap_dusen":    any("CAST_CAP_DUSEN" in r for r in _R),
        }
        _r = _router.classify(_sig)
        # FLAT KURAL (Çağatay 2026-06-21): export'ta SADECE ONAYLI ve KONTROL var. NEEDS_REVIEW_HAFIF
        # (eski adıyla AUTOFIX — İP-4 2026-07-11 davranış-nötr rename) ve KONTROL tier'larının her
        # ikisi de KONTROL'e gider; sorun etiketi dosya adına yazılır.
        if _r["tier"] == "TEMIZ":
            karar, dest_root = "Hazır", HAZIR
        else:                                              # NEEDS_REVIEW_HAFIF veya KONTROL → KONTROL/ (flat)
            karar, dest_root = "Kontrol", KONTROL
        # GÜVENLİK: 'reasons' var ama tipe eşlenmedi → yine KONTROL (mis-deliver önle)
        if _R and (not _r["agir"]):
            karar, dest_root = "Kontrol", KONTROL
        route_info = _r
    except Exception as _rexc:  # noqa: BLE001 — FAIL-SAFE: router hatası → ESKİ karar geçerli kalır
        route_info = {"error": f"router: {type(_rexc).__name__}: {_rexc}"}
    # ── İP-2 (2026-07-11, plan rev.4): TEKNİK-ARIZA İNSAN KAPISINI ATLAYAMAZ ──────────────────
    # extraction TECHNICAL_FAILURE olan koşu ASLA Hazır/ONAYLI'ya gidemez — kaza "film boşmuş"
    # diye arşive mühürlenemez. PDF/render/export yukarıda withheld; burada retryable karar kaydı
    # zorlanır ve aşağıda silmesiz candidate FULL retry work-item'i üretilir.
    _ext_st = (str(video_credits.get("extraction_status") or "").upper()
               if isinstance(video_credits, dict) else "")
    if _ext_st == "TECHNICAL_FAILURE":
        karar, dest_root = "Kontrol", KONTROL
        if not any(str(r).startswith("TEKNIK_ARIZA: LLM-extraction") for r in reasons):
            reasons.append("TEKNIK_ARIZA: LLM-extraction TECHNICAL_FAILURE (TECH_RETRY adayı)")
    elif _ext_st == "DEGRADED":
        karar, dest_root = "Kontrol", KONTROL
        if not any(str(r).startswith("DEGRADED: LLM-extraction") for r in reasons):
            reasons.append("DEGRADED: LLM-extraction kısmi model teknik arızası (insan kontrolü)")
    # ── ÖZEL-TÜR YÖNLENDİRME (Çağatay 2026-06-21): müzikal/belgesel/animasyon AYRI klasörde toplanır
    #    (ONAYLI/KONTROL'e DEĞİL). Erken sinyal (XML/profil) VEYA final TÜR (KB/IMDb) — biri yeterli
    #    ("her türlü sağla"). Tam künye üretildi; yalnız hedef klasör değişir, teslim akışı aynı kalır.
    special_genre = ""
    try:
        special_genre = forced_special_genre or genre_class(video, tur_final)
        if special_genre in ("BELGESEL", "MÜZİKAL", "ANİMASYON"):
            dest_root = SPECIAL_GENRE_DIR
        else:
            special_genre = ""
    except Exception:  # noqa: BLE001 — FAIL-SAFE: tür-tespit hatası kararı/teslimi bozmaz
        special_genre = ""
    # TF'de export klasoru dahil hicbir teslim yuzeyine yazma. Hub teknik kayitlari asagida korunur.
    if not _ext_tf:
        dest_root.mkdir(parents=True, exist_ok=True)
    # ÇIKTI ADI — TEK FORMAT: "<TRT-ID> <BAŞLIK>". Teslime hazır → "_onaylı" eki + ONAYLI klasörü
    # (Çağatay 2026-06-15: ayrı "teslime hazır" klasörü YOK, hazırsa doğrudan ONAYLI'ya).
    # Düz dosya (alt-klasör yok): export\ONAYLI\1999-2020-1-0000-90-1 PİNOKYO_onaylı.pdf
    _safe_title = re.sub(r'[\\/:*?"<>|]+', " ", (title or "")).strip()
    # KONTROL filmlerinin dosya adına SORUN ETİKETİ yaz (örn. '_YONETMEN_KIMLIK') → açmadan görünür
    _kontrol_lbl = ""
    if isinstance(route_info, dict) and route_info.get("kontrol_tip") and karar == "Kontrol":
        _kontrol_lbl = " _" + str(route_info["kontrol_tip"]).replace("+", "_")
    if special_genre:
        # Özel tür: dosya adına TÜR etiketi birincil (örn. '_BELGESEL'); sorun varsa onu da ekle.
        base_name = (f"{trt} {_safe_title}").strip() + f"_{special_genre}" + (_kontrol_lbl if karar == "Kontrol" else "")
    else:
        base_name = (f"{trt} {_safe_title}").strip() + ("_onaylı" if karar == "Hazır" else _kontrol_lbl)
    # is_file (exists DEĞİL): pdf_path=None → Path('.') dizini "var" sayılıp md teslimini
    # İPTAL ediyor ve sahte .pdf yolu raporluyordu (Errno 21, 2026-07-30 kanıtlı).
    pdf_src = Path(pdf_info.get("pdf_path") or "")
    md_src = Path(pdf_info.get("md_path") or "")
    src_file = pdf_src if (pdf_src and pdf_src.is_file()) else (md_src if (md_src and md_src.is_file()) else None)
    ext = ".pdf" if (pdf_src and pdf_src.is_file()) else (".md" if (md_src and md_src.is_file()) else "")
    dest = (dest_root / f"{base_name}{ext}") if not _ext_tf else None
    if src_file and dest is not None:
        try:
            shutil.copy2(src_file, dest)
        except Exception as e:
            print(f"WARN: shutil.copy2 failed: {e}")
    dbg.emit("routing", "qc_decision",
             status="ok" if karar == "Hazır" else "warn",
             subject={"field": "karar", "after": karar,
                      "reason": "; ".join(reasons) if reasons else "tüm bloklar temiz"},
             evidence={"reasons": reasons, "qwen_uyari": qwen_uyari,
                       "route_info": route_info, "dest": str(dest) if dest is not None else None,
                       "special_genre": special_genre},
             source={"module": "scripts/mitas_pipeline.py",
                     "input_paths": [str(src_file) if src_file else ""],
                     "output_paths": [str(dest) if dest is not None else ""]})
    if not _ext_tf:
        _write_person_gate_excel(EXPORT_ROOT / "_KISI_KAPISI_RAPORU.xlsx",
                                 trt or "", title or "", karar, _person_gate_report, dest)
    # Köke temiz teslimat yüzeyle (DATABASE düzeni): '<TRT> <BAŞLIK>.pdf' + afis.jpg + '<TRT> <BAŞLIK>.txt'.
    if not _ext_tf:
        try:
            surface_deliverables(clip_dir, trt, title, pdf_info, tur_override=tur_final, v4_credits=v4_credits)
        except Exception as exc:  # noqa: BLE001 — yüzeyleme ASLA pipeline kararını bozmaz
            log_event("surface_failed", summary=f"kok yuzeyleme hata: {exc}", module="pipeline",
                      media_id=media_id, filename=video.name, detail={"clip_id": clip_id})
    total = round(time.perf_counter() - t_all, 2)
    timings["toplam"] = total

    _retry_work_item = None
    _mesru_bos_pending = None
    if _ext_tf:
        try:
            _retry_work_item = _write_extraction_retry_work_item(
                clip_dir, video=video, profile=profile,
                source_run_id=str(_manifest.get("run_id") or ""), from_hub=_from_hub)
            log_event("retry_work_item_created", level="warn",
                      summary=f"{video.name}: extraction TF icin PENDING FULL candidate-retry isi yazildi.",
                      module="pipeline", media_id=media_id, filename=video.name,
                      detail={"clip_id": clip_id, "retry": _retry_work_item})
        except Exception as exc:  # noqa: BLE001 — teknik kayit yine _DURUM/manifest'te kalir
            log_event("retry_work_item_failed", level="error",
                      summary=f"{video.name}: retry work item yazilamadi: {exc}",
                      module="pipeline", media_id=media_id, filename=video.name, error=str(exc))
    else:
        try:
            _mesru_bos_pending = _write_mesru_bos_pending(
                clip_dir, v4_credits=v4_credits, video_credits=video_credits)
            if _mesru_bos_pending:
                log_event("mesru_bos_pending", level="warn",
                          summary=f"{video.name}: bos final alanlar ikinci-tanik bekliyor; muhur yok.",
                          module="pipeline", media_id=media_id, filename=video.name,
                          detail={"clip_id": clip_id,
                                  "fields": [x["field"] for x in _mesru_bos_pending["items"]]})
        except Exception as exc:  # noqa: BLE001 — pending koprusu karari/teslimi bozamaz
            log_event("mesru_bos_pending_failed", level="error",
                      summary=f"{video.name}: mesru-bos pending yazilamadi: {exc}",
                      module="pipeline", media_id=media_id, filename=video.name, error=str(exc))

    summary_obj = {
        "clip_id": clip_id, "video": str(video), "profile": profile, "trt_id": trt, "title": title,
        "karar": karar, "route": route_info, "neden": reasons, "qwen_uyari": qwen_uyari, "qwen_qc": qwen_qc, "ocr_bucket": ocr_bucket, "ocr_lines": ocr_lines,
        "asr_status": asr_status, "asr_segments": asr_info.get("clean_segments"),
        "transcript_chars": asr_info.get("transcript_chars"),
        "resolution": res, "fps": fps_s, "duration": dur, "timings_sec": timings,
        # TÜR + orijinal-ad teslim PDF (v4) ve kök .txt'de zaten DOĞRU; _DURUM iç-durumu bunları
        # taşımıyordu (summary_obj'de alan yoktu) → QC/denetim ara-dosyaya bakınca "eksik" sanıyordu.
        # Teslimle hizala (2026-06-28). tur_final: xml_genre→v4 nihai; original: XML <TITLE> (yabancı ad).
        "tur": tur_final, "orijinal_ad": original,
        "hub": str(clip_dir), "teslim": (str(dest) if dest is not None else None),
        "processing_status": ("RETRYABLE_FAILURE" if _ext_tf else
                              ("DEGRADED" if _ext_degraded else "SUCCEEDED")),
        "delivery_status": "WITHHELD_TECHNICAL_FAILURE" if _ext_tf else "PRODUCED",
        "retry_work_item": (str(clip_dir / "retry_work_item.json") if _retry_work_item else None),
        "mesru_bos_pending": (str(clip_dir / "mesru_bos.pending.json")
                              if _mesru_bos_pending else None),
        # FIX-D/B (2026-06-23): OCR-otorite denetim sinyalini _DURUM'a yüzeyle (görünürlük) —
        # ocr_dropped/kb_floor_added/ocr_authority_violation + s5_form_overwrites. v4 raporundan okunur;
        # yoksa None (additive, kararı etkilemez). "başarısızlığı nereden anlarız" sinyali burada görünür.
        "otorite_audit": ((_v4j or {}).get("v4") or {}).get("qc_block_otorite_audit"),
        # A0 (2026-07-03): kalkanın düşürdüğü VL adayları makine-okunur alanda — KONTROL denetçisi ve
        # toplu-analiz (karar_gunlugu / QC ajanları) debug-trace kazmadan görsün. Additive; karar etkisiz.
        "vl_yon_aday": (video_credits.get("vl_yon_hallucinated")
                        if isinstance(video_credits, dict) else None),
        "vl_cast_aday": (video_credits.get("vl_cast_hallucinated_names")
                         if isinstance(video_credits, dict) else None),
        "vl_yon_kaynak": (video_credits.get("vl_yon_kaynak")
                          if isinstance(video_credits, dict) else None),
        "vl_yon_eslesme": (video_credits.get("vl_yon_eslesme")
                           if isinstance(video_credits, dict) else None),
        "vl_yon_dop_dropped": (video_credits.get("vl_yon_dop_dropped")
                               if isinstance(video_credits, dict) else None),
        "vl_yon_cast_dropped": (video_credits.get("vl_yon_cast_dropped")
                                if isinstance(video_credits, dict) else None),
        # ÖLÇÜM (2026-07-31): QC1 sonucu YAPISAL alan olarak _DURUM'da. Önceden yalnız
        # serbest metin olarak 'neden'/'qwen_uyari' içinde sızıyordu → toplu analiz
        # dizgi-eşleşmesine mahkûmdu. _qc1_failed bellekte doğup süreç bitince
        # kayboluyordu (karara etki ediyor: satır ~3392). Additive, karar etkisiz.
        "qc1": ({"failed": bool(video_credits.get("_qc1_failed")),
                 "yonetmen_var": bool(video_credits.get("yonetmen")),
                 "cast_n": len(video_credits.get("cast") or []),
                 "vl_kostu": bool(video_credits.get("vl")),
                 "validate_override": bool(
                     video_credits.get("_qc1_failed_overridden_by_credit_validate")),
                 "validate_strong_director": bool(
                     video_credits.get("_credit_validate_strong_director"))}
                if isinstance(video_credits, dict) else None),
        # İP-2 (2026-07-11): extraction sözleşmesi _DURUM'da görünür — "teknik-kaza mı, meşru-boş mu"
        # sorusunun kalıcı veri-tabanı (TECH_RETRY worklist'i ve İP-4 reason-code'ları buradan beslenir).
        "extraction_status": (video_credits.get("extraction_status")
                              if isinstance(video_credits, dict) else None),
        "extraction_detail": (video_credits.get("extraction_detail")
                              if isinstance(video_credits, dict) else None),
        "pdf": pdf_info.get("pdf_path"), "md": pdf_info.get("md_path"), "ts": now_iso(),
    }
    write_json(clip_dir / "_DURUM.json", summary_obj)
    # İP-4 (2026-07-11): karar.pipeline.json GÖLGE-yazımı — _DURUM'u üreten AYNI noktadan
    # (tek-yazıcı sözleşmesi). Otorite _DURUM'da; gölge asla koşuyu bozmaz.
    try:
        import credit_severity_router as _router_shadow
        _router_shadow.write_pipeline_karar(
            clip_dir, route_info, karar=karar, reasons=reasons, qwen_uyari=qwen_uyari,
            extraction_status=(video_credits.get("extraction_status")
                               if isinstance(video_credits, dict) else None),
            run_id=_manifest.get("run_id"))
        _drift = _router_shadow.check_drift(clip_dir)
        if _drift:
            log_event("karar_drift", summary=_drift[:300], module="pipeline", media_id=media_id)
    except Exception as _shexc:  # noqa: BLE001 — gölge-yazım koşuyu ASLA bozmaz
        log_event("karar_shadow_fail", summary=f"{type(_shexc).__name__}: {_shexc}",
                  module="pipeline", media_id=media_id)
    # İP-1: manifest'i kapat (status=karar; best-effort, koşuyu asla bozmaz).
    _rm.finalize(clip_dir, status=("RETRYABLE_FAILURE" if _ext_tf else karar),
                 extra={"teslim": (str(dest) if dest is not None else None), "timings": timings,
                        "ocr_bucket": ocr_bucket, "reasons": reasons,
                        "processing_status": ("RETRYABLE_FAILURE" if _ext_tf else
                                              ("DEGRADED" if _ext_degraded else "SUCCEEDED")),
                        "delivery_status": "WITHHELD_TECHNICAL_FAILURE" if _ext_tf else "PRODUCED",
                        "retry_work_item": (str(clip_dir / "retry_work_item.json") if _retry_work_item else None),
                        "extraction_status": (video_credits.get("extraction_status")
                                              if isinstance(video_credits, dict) else None)})
    if _batch_mode:
        _rm.release_writer_lock()
    dbg.finalize_trace(timings=timings,
                       final_status=("RETRYABLE_FAILURE" if _ext_tf else karar), reasons=reasons,
                       outputs={"hub": str(clip_dir), "teslim": (str(dest) if dest is not None else None),
                                "pdf": pdf_info.get("pdf_path"), "md": pdf_info.get("md_path"),
                                "durum": str(clip_dir / "_DURUM.json")})
    # Köke insan-okunur _teknik.txt + per-film _log.jsonl (DATABASE düzeni — herşey tek klasörde).
    try:
        surface_logs(clip_dir, trt, title)
    except Exception as exc:  # noqa: BLE001 — log/teknik yüzeyleme ASLA kararı bozmaz
        log_event("surface_failed", summary=f"log/teknik yuzeyleme hata: {exc}", module="pipeline",
                  media_id=media_id, filename=video.name, detail={"clip_id": clip_id})
    # master log (jsonl + md)
    MASTER_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with MASTER_JSONL.open("a", encoding="utf-8") as h:
        h.write(json.dumps(summary_obj, ensure_ascii=False) + "\n")
    md = [
        f"## {clip_id}  —  [{karar.upper()}]",
        f"- Tarih: {summary_obj['ts']}  ·  Profil: {profile}  ·  TRT: {trt or '—'}",
        f"- Karar: **{karar}**" + (f" — Neden: {'; '.join(reasons)}" if reasons else " (tüm bloklar temiz)"),
        f"- Süreler: TOPLAM {total} sn  |  ÇÖZ {timings.get('coz')}  |  OCR {timings.get('ocr')}  |  ASR {timings.get('asr')}  |  PDF {timings.get('pdf')}",
        f"- Künye: {ocr_lines} satır (bucket={ocr_bucket})  |  Transcript: {asr_info.get('clean_segments') or 0} segment, {asr_info.get('transcript_chars') or 0} karakter",
        f"- Çözünürlük: {res}  ·  Süre: {dur}",
        f"- Hub: {clip_dir}",
        f"- Teslim: {dest if dest is not None else 'URETILMEDI (TECHNICAL_FAILURE)'}",
        "",
    ]
    if not MASTER_MD.exists():
        MASTER_MD.write_text("# MİTAS — İşlem Log'u (Hazır / Kontrol)\n\n", encoding="utf-8")
    with MASTER_MD.open("a", encoding="utf-8") as h:
        h.write("\n".join(md) + "\n")

    # ===== HAVUZ-PARALEL v2: ÇIKIŞ-HAVUZ TOPLAMA (ilk tüketiciden hemen önce) =====
    # Lansman ASR-toplama sonrasıydı; LLM/v4/pdf kuyruğu (~100-160 sn) havuz işini (~50-60 sn)
    # gölgeledi → beklenen ek bekleme ~0. Fail-safe: hata pipeline'ı bozmaz.
    if _jp_proc is not None:
        _t_col = time.perf_counter()
        try:
            _rcjp = _jp_proc.wait(
                timeout=int(os.environ.get("MITAS_JENERIK_POOL_TIMEOUT", "900") or 900))
            _outjp = _jp_outf.read_text(encoding="utf-8", errors="replace") if _jp_outf.exists() else ""
            _errjp = _jp_errf.read_text(encoding="utf-8", errors="replace") if _jp_errf.exists() else ""
            _jjp = last_json(_outjp) or {}
            if not cikis_jenerik_frames.exists():
                cikis_jenerik_frames.mkdir(parents=True, exist_ok=True)
            timings["jenerik_pool"] = round(time.perf_counter() - _t_col, 2)
            _jp_wall = (round(_jp_outf.stat().st_mtime - _t_jp_wall, 2)
                        if (_t_jp_wall and _jp_outf.exists()) else None)   # gerçek iş süresi (exit anı)
            log_event("jenerik_pool_completed",
                      level="info" if _jjp.get("status") != "error" else "warn",
                      summary=f"{video.name}: paralel jenerik havuzu {cikis_jenerik_frames.name} "
                              f"status={_jjp.get('status')} frame={_jjp.get('pool_frames', 0)} "
                              f"(LLM/v4-örtüşük, iş {_jp_wall} sn, ek bekleme {timings['jenerik_pool']} sn).",
                      module="jenerik-pool", media_id=media_id, filename=video.name,
                      duration_seconds=timings["jenerik_pool"],
                      detail={"clip_id": clip_id, "pool": str(cikis_jenerik_frames), "paralel": True,
                              "pool_wall_sn": _jp_wall,
                              "result": _jjp, "stderr": (_errjp or "")[-300:] if _rcjp else None})
        except Exception as _jpe:  # noqa: BLE001
            try:
                _jp_proc.kill()
                _jp_proc.wait(timeout=10)
            except Exception:  # noqa: BLE001
                pass
            try:
                cikis_jenerik_frames.mkdir(parents=True, exist_ok=True)
                with (jenerik_debug_root / "errors.jsonl").open("a", encoding="utf-8") as _eh:
                    _eh.write(json.dumps({"ts": now_iso(), "stage": "pool-collect", "error": str(_jpe)[:500]},
                                         ensure_ascii=False) + "\n")
            except Exception:  # noqa: BLE001
                pass
            log_event("jenerik_pool_failed", level="warn",
                      summary=f"{video.name}: paralel jenerik havuzu toplama hatası ({type(_jpe).__name__}).",
                      module="jenerik-pool", media_id=media_id, filename=video.name,
                      error=str(_jpe)[:300], detail={"clip_id": clip_id})
    if _pp_par:
        _cikis_fallback_pool()   # havuz kapalı/lansman-hata dallarında da çalışır (kendi guard'ları var)

    # ===== VIDEO-VL JENERİK OKUMA (2026-07-16): mp4-parçalı ADAY-ÜRETİCİ =====
    # Havuz dedektörünün start_pos'u → film sonuna 60s SESSİZ mp4 parçaları → vLLM (Qwen3-VL-8B,
    # kıyas kazananı) kare-bölümlü okuma → hub/video_vl/. Karar/PDF'e DOKUNMAZ (OCR-otorite korunur).
    # Default KAPALI; açmak: MITAS_VIDEO_VL=1 + kurulum/vlm_sunucu.sh start (sunucu yoksa dürüst-atlar).
    if (os.environ.get("MITAS_VIDEO_VL", "0").strip().lower() in ("1", "true", "on", "yes")
            and not args.no_ocr):
        _vv_t = time.perf_counter()
        try:
            # Pencere/fps İLETİLİR (_jenerik_dense ile aynı desen): kareler HANGİ
            # saniyeden HANGİ fps ile çıkarıldıysa video kesimi de ondan hesaplanmalı.
            # İletilmezse script dur-600 varsayardı → üretim tail'i 480 iken 120 sn kayma.
            _vv_cmd = [str(PY_OCR), str(HERE / "_pipe_video_vl.py"),
                       "--clip", str(clip_dir), "--video", str(video),
                       "--win-start", f"{float(_cik_start):.3f}", "--src-fps", str(args.fps)]
            _rcvv, _outvv, _errvv = run(
                _vv_cmd,
                timeout=int(os.environ.get("MITAS_VIDEO_VL_TIMEOUT", "1800") or 1800),
            )
            timings["video_vl"] = round(time.perf_counter() - _vv_t, 2)
            log_event("video_vl_completed", level="info" if _rcvv == 0 else "warn",
                      summary=f"{video.name}: video-VL jenerik okuma bitti "
                              f"(rc={_rcvv}, {timings['video_vl']} sn).",
                      module="video-vl", media_id=media_id, filename=video.name,
                      duration_seconds=timings["video_vl"], detail={"clip_id": clip_id})
        except Exception as _vve:  # noqa: BLE001
            log_event("video_vl_failed", level="warn",
                      summary=f"{video.name}: video-VL hata ({type(_vve).__name__}).",
                      module="video-vl", media_id=media_id, filename=video.name,
                      error=str(_vve)[:300], detail={"clip_id": clip_id})

    # ===== PARALEL JENERIK DEBUG: OneOCR normal havuz + GLM/VL/master cikis_jenerik havuzu =====
    # ÜRETİME DOKUNMAZ: karar/PDF zaten verildi. Kalıcı provenance:
    # Database/<film>/jenerik_debug/{oneocr,glm,vl,master_png,compare,analysis_report.md}
    _jdebug_on = (_jpool_on and os.environ.get("MITAS_JENERIK_PARALLEL_DEBUG", "1").strip().lower()
                  not in ("0", "false", "off", "no"))
    if _jdebug_on and not args.no_ocr:
        _jd_t = time.perf_counter()
        try:
            _jd_cmd = [str(PY_OCR), str(HERE / "_jenerik_parallel_debug.py"),
                       "--clip", str(clip_dir), "--ocr-out", str(ocr_out)]
            _rcjd, _outjd, _errjd = run(
                _jd_cmd,
                timeout=int(os.environ.get("MITAS_JENERIK_PARALLEL_DEBUG_TIMEOUT", "1800") or 1800),
            )
            _jjd = last_json(_outjd) or {}
            timings["jenerik_debug"] = round(time.perf_counter() - _jd_t, 2)
            log_event("jenerik_debug_completed",
                      level="info" if _jjd.get("status") != "error" else "warn",
                      summary=f"{video.name}: paralel jenerik debug tamamlandı "
                              f"({timings['jenerik_debug']} sn).",
                      module="jenerik-debug", media_id=media_id, filename=video.name,
                      duration_seconds=timings["jenerik_debug"],
                      detail={"clip_id": clip_id, "debug_root": str(jenerik_debug_root),
                              "result": _jjd, "stderr": (_errjd or "")[-500:] if _rcjd else None})
        except Exception as _jde:  # noqa: BLE001
            try:
                (jenerik_debug_root / "errors.jsonl").parent.mkdir(parents=True, exist_ok=True)
                with (jenerik_debug_root / "errors.jsonl").open("a", encoding="utf-8") as _eh:
                    _eh.write(json.dumps({"ts": now_iso(), "stage": "parallel_debug", "error": str(_jde)[:500]},
                                         ensure_ascii=False) + "\n")
            except Exception:
                pass
            log_event("jenerik_debug_failed", level="warn",
                      summary=f"{video.name}: paralel jenerik debug atlandı ({type(_jde).__name__}).",
                      module="jenerik-debug", media_id=media_id, filename=video.name,
                      error=str(_jde)[:300], detail={"clip_id": clip_id})
    if _jdebug_on:
        try:
            _detector_status = ""
            _pool_frames = None
            _pool_manifest = jenerik_debug_root / "pool" / "manifest.json"
            if _pool_manifest.exists():
                _pool_obj = _read_json_safe(_pool_manifest) or {}
                _detector_status = str(_pool_obj.get("status") or "")
                _pool_frames = _pool_obj.get("pool_frames")
            summary_obj["timings_sec"] = timings
            summary_obj["jenerik_debug"] = {
                "enabled": True,
                "root": str(jenerik_debug_root),
                "analysis_report": str(jenerik_debug_root / "analysis_report.md"),
                "detector_status": _detector_status,
                "pool": str(cikis_jenerik_frames),
                "pool_frames": _pool_frames,
            }
            write_json(clip_dir / "_DURUM.json", summary_obj)
        except Exception as _jdu:  # noqa: BLE001 - visibility update must not affect routing
            log_event("jenerik_debug_surface_failed", level="warn",
                      summary=f"{video.name}: jenerik debug _DURUM yüzeyleme atlandı ({type(_jdu).__name__}).",
                      module="jenerik-debug", media_id=media_id, filename=video.name,
                      error=str(_jdu)[:200], detail={"clip_id": clip_id})

    # ===== KANONİK MASTER-PNG (giriş+çıkış, film KÖKÜNDE açıkta) — Çağatay 2026-06-29 =====
    # Master-PNG artık SADECE çıkış değil GİRİŞ için de üretilir. Kaynak = derlenmiş havuzlar
    # (frames/giris_jenerik & frames/cikis_jenerik); çıktı film KÖKÜNDE "<TRT BAŞLIK> {giris,cikis}.png"
    # (eski master/ alt-klasörü gen_master tarafından KALDIRILIR — yeni master üretildiyse). Havuz boşsa
    # (cold-open/yazı yok) o segment için master üretilmez (ham footage'a düşmez). Paralel-debug açıkken
    # jenerik_debug/master_png/ debug master'ı AYRICA üretmeye devam eder (provenance — dokunulmadı).
    # FAIL-SAFE: hata/timeout ASLA pipeline'ı/kararı bozmaz; üretilemezse eski master/ KORUNUR ("kötü yerine hiç").
    if os.environ.get("MITAS_MASTER_PNG_AUTO", "1").strip().lower() not in ("0", "false", "off", "no"):
        _has_fr = any(p.exists() and any(p.glob("*.png")) for p in
                      (giris_jenerik_frames, cikis_jenerik_frames, giris_frames, cikis_frames))
        if _has_fr:
            # AŞAMA-2v2 DENSE (2026-07-17): master'dan ÖNCE çıkış havuzu için adaptif yoğun-kare
            # KARDEŞ havuz üret (frames/cikis_jenerik_dense) — 1.5fps'te kayan kredi dy≈75px
            # 'cut' sanılıp smear/collapse üretiyordu (HALLERİ/MAVZER/ZENGİN kökü). Havuz
            # DEĞİŞMEZ; tercihi monitor yapar. Kill: MITAS_MASTER_DENSE=0. FAIL-SAFE: hata/
            # timeout/video-yok (from-hub offline) → dense'siz devam, mevcut davranış birebir.
            if os.environ.get("MITAS_MASTER_DENSE", "1").strip().lower() not in ("0", "false", "off", "no"):
                try:
                    if video is not None and Path(video).exists() and cikis_jenerik_frames.is_dir() \
                            and any(cikis_jenerik_frames.glob("*.png")):
                        run([str(PY_OCR), str(HERE / "_jenerik_dense.py"), "--clip", str(clip_dir),
                             "--video", str(video), "--seg", "cikis",
                             "--win-start", f"{float(_cik_start):.3f}", "--src-fps", str(args.fps)],
                            timeout=int(os.environ.get("MITAS_DENSE_TIMEOUT", "600") or 600))
                except Exception:  # noqa: BLE001 — dense ASLA master'ı/kararı bozmaz
                    pass
            _mp_runner = PROJECT_ROOT / "OCR-worktree" / "master_png_monitor.py"
            _mp_base = file_base(trt, title)
            try:
                _mp = subprocess.run(
                    [str(PY_OCR), str(_mp_runner), "--once", str(clip_dir), "--base", _mp_base],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=int(os.environ.get("MITAS_MASTER_PNG_TIMEOUT", "300") or 300))
                _mp_ok = bool(list(clip_dir.glob("* giris.png")) or list(clip_dir.glob("* cikis.png")))
                log_event("master_png_completed" if _mp_ok else "master_png_empty",
                          level="info" if _mp_ok else "warn",
                          summary=f"{video.name}: master-PNG {'üretildi' if _mp_ok else 'üretilemedi'} "
                                  f"(kökte '<ad> giris/cikis.png', rc={_mp.returncode}).",
                          module="master-png", media_id=media_id, filename=video.name,
                          detail={"clip_id": clip_id, "rc": _mp.returncode, "base": _mp_base})
                # K1 KOŞU-SONU DİLİM (2026-07-03): taze master'lar dilimlenir + OneOCR ile okunur —
                # bir SONRAKİ koşunun DİLİM-TAZELE adımı hazır veri bulur; damga güncel ocr_job.
                # Kill-switch DİLİM-TAZELE ile ortak: MITAS_MASTER_DILIM_AUTO=0. FAIL-SAFE.
                if (os.environ.get("MITAS_MASTER_DILIM_AUTO", "1").strip().lower()
                        not in ("0", "false", "off", "no")):
                    try:
                        run([str(PY_OCR), str(HERE / "master_png_dilimle.py"), "--clip", str(clip_dir)],
                            timeout=int(os.environ.get("MITAS_MASTER_DILIM_TIMEOUT", "180") or 180))
                        run([str(PY_OCR), str(HERE / "master_dilim_oku.py"), "--clip", str(clip_dir),
                             "--ocr-job", ocr_job, "--force"],
                            timeout=int(os.environ.get("MITAS_MASTER_DILIM_TIMEOUT", "180") or 180))
                    except Exception:  # noqa: BLE001 — koşu-sonu dilim ASLA teslimi bozmaz
                        pass
            except Exception as _mpe:  # noqa: BLE001 — master-PNG ASLA pipeline'ı bozmaz
                log_event("master_png_failed", level="warn",
                          summary=f"{video.name}: master-PNG atlandı ({type(_mpe).__name__}).",
                          module="master-png", media_id=media_id, filename=video.name,
                          error=str(_mpe)[:200], detail={"clip_id": clip_id})

    # ===== TRACK-KUNYE GÖLGE (2026-07-30): MESSİ + İBRA-OKUMA + RONALDO — 3 çıktı =====
    # Spec: docs/superpowers/specs/2026-07-30-track-kunye-uretim-entegrasyon-design.md
    # ÜRETİME DOKUNMAZ: karar/PDF/teslim verildi; çıktılar clip_dir/track_kunye/ + kökte
    # "<ad> kunye3.txt". MASTER-PNG bloğundan SONRA koşmak ZORUNDA (runaware'i salt-okur).
    # FAIL-SAFE: hata/timeout ASLA pipeline'ı/kararı bozmaz. Kill: MITAS_TRACK_KUNYE=0.
    if (os.environ.get("MITAS_TRACK_KUNYE", "1").strip().lower() not in ("0", "false", "off", "no")
            and not args.no_ocr):
        _tk_t = time.perf_counter()
        _tk_ad = video.name if video is not None else clip_dir.name
        try:
            if cikis_frames.is_dir() and any(cikis_frames.glob("*.png")):
                _tk_cmd = [str(PY_OCR), str(HERE / "_pipe_track_kunye.py"),
                           "--clip", str(clip_dir), "--frames", str(cikis_frames),
                           "--base", file_base(trt, title)]
                _rctk, _outtk, _errtk = run(
                    _tk_cmd,
                    timeout=int(os.environ.get("MITAS_TRACK_KUNYE_TIMEOUT", "1200") or 1200))
                _jtk = last_json(_outtk) or {}
                timings["track_kunye"] = round(time.perf_counter() - _tk_t, 2)
                _tk_status = str(_jtk.get("status") or ("done" if _rctk == 0 else "failed"))
                _tk_band = _jtk.get("band")
                log_event("track_kunye_completed" if _tk_status == "done" else
                          ("track_kunye_skipped" if _tk_status == "skipped"
                           else "track_kunye_failed"),
                          level="info" if _tk_status == "done" else "warn",
                          summary=f"{_tk_ad}: track-kunye {_tk_status} "
                                  f"(band={_tk_band}, {timings['track_kunye']} sn).",
                          module="track-kunye", media_id=media_id, filename=_tk_ad,
                          duration_seconds=timings["track_kunye"],
                          detail={"clip_id": clip_id, "ozet": _jtk,
                                  # betik SÖZLEŞME gereği hep rc=0 döner — stderr'i
                                  # rc'ye bakmadan logla (konsey bug-avı KIM-3)
                                  "stderr": (_errtk or "")[-300:] or None})
                if _tk_status == "done" and _tk_band in ("red", None):
                    log_event("ronaldo_band_red" if _tk_band == "red" else "ronaldo_band_null",
                              level="warn",
                              summary=f"{_tk_ad}: Ronaldo güven bandı {_tk_band or 'yok'} — göz-QC önerilir.",
                              module="track-kunye", media_id=media_id, filename=_tk_ad,
                              detail={"clip_id": clip_id, "common_blind": _jtk.get("common_blind")})
                if _tk_status == "done" and _jtk.get("common_blind"):
                    log_event("ronaldo_common_blind", level="warn",
                              summary=f"{_tk_ad}: ortak-körlük bayrağı — kapsama düşük, içerik-tamlık garantisi YOK.",
                              module="track-kunye", media_id=media_id, filename=_tk_ad,
                              detail={"clip_id": clip_id, "coverage_ratio": _jtk.get("coverage_ratio")})
                summary_obj["track_kunye"] = {"status": _tk_status, "band": _tk_band,
                                              "dir": str(clip_dir / "track_kunye")}
                write_json(clip_dir / "_DURUM.json", summary_obj)
            else:
                log_event("track_kunye_skipped", level="info",
                          summary=f"{_tk_ad}: track-kunye atlandı — frames/cikis yok/boş.",
                          module="track-kunye", media_id=media_id, filename=_tk_ad,
                          detail={"clip_id": clip_id})
        except Exception as _tke:  # noqa: BLE001 — gölge blok ASLA pipeline'ı bozmaz
            log_event("track_kunye_failed", level="warn",
                      summary=f"{_tk_ad}: track-kunye atlandı ({type(_tke).__name__}).",
                      module="track-kunye", media_id=media_id, filename=_tk_ad,
                      error=str(_tke)[:300], detail={"clip_id": clip_id})

    # ===== LEGACY GÖLGE VL — paralel debug kapalıysa eski davranışı koru =====
    # ÜRETİME DOKUNMAZ: karar/PDF zaten verildi. FAIL-SAFE: hata/timeout ASLA kararı bozmaz.
    # Paralel debug açıkken VL artık frames/cikis_jenerik üzerinden jenerik_debug/vl altında çalışır.
    # Kapatmak için MITAS_SHADOW_VL=0. Maliyet ~1-4dk/film (arka-plan, teslimi geciktirmez).
    if (not _jdebug_on) and os.environ.get("MITAS_SHADOW_VL", "1").strip().lower() in ("1", "true", "on", "yes"):
        _svl_frames_ok = (giris_frames.exists() and any(giris_frames.glob("*.png"))) or \
                         (cikis_frames.exists() and any(cikis_frames.glob("*.png")))
        if _svl_frames_ok:
            _svl_out = clip_dir / "gemma_kunye.json"
            _svl_job = f"svl-{uuid4().hex[:8]}"
            _svl_p = None
            try:
                log_event("shadow_vl_started", level="info",
                          summary=f"{video.name}: gölge-VL başladı → {_svl_out.name}.",
                          module="shadow-vl", media_id=media_id, filename=video.name,
                          job_id=_svl_job, detail={"clip_id": clip_id})
                _svl_p = subprocess.Popen(
                    [str(PY_OCR), str(HERE / "_pipe_shadow_vl.py"),
                     "--clip", str(clip_dir), "--out", str(_svl_out)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", errors="replace")
                _svl_so, _svl_se = _svl_p.communicate(timeout=SHADOW_VL_TIMEOUT)
                _svl_ok = _svl_out.exists()
                log_event("shadow_vl_completed" if _svl_ok else "shadow_vl_empty",
                          level="info" if _svl_ok else "warn",
                          summary=f"{video.name}: gölge-VL {'tamamlandı' if _svl_ok else 'çıktı üretemedi'} (rc={_svl_p.returncode}).",
                          module="shadow-vl", media_id=media_id, filename=video.name,
                          job_id=_svl_job, detail={"clip_id": clip_id, "rc": _svl_p.returncode,
                                                    "stderr": _svl_se[-300:] if _svl_p.returncode else None})
                update_clip_module(clip_dir, "shadow-vl", "done" if _svl_ok else "partial", _svl_job)
            except Exception as _svle:  # noqa: BLE001 — FAIL-SAFE: gölge-VL ASLA pipeline'ı bozmaz
                try:
                    if _svl_p is not None:
                        _svl_p.kill()
                        _svl_p.communicate(timeout=10)
                except Exception:  # noqa: BLE001
                    pass
                update_clip_module(clip_dir, "shadow-vl", "failed", _svl_job)
                log_event("shadow_vl_failed", level="warn",
                          summary=f"{video.name}: gölge-VL atlandı ({type(_svle).__name__}).",
                          module="shadow-vl", media_id=media_id, filename=video.name,
                          job_id=_svl_job, error=str(_svle)[:200], detail={"clip_id": clip_id})
        else:
            log_event("shadow_vl_skipped", level="info",
                      summary=f"{video.name}: gölge-VL atlandı — frames/giris|cikis yok.",
                      module="shadow-vl", media_id=media_id, filename=video.name,
                      detail={"clip_id": clip_id})

    log_event(("routed_retryable_failure" if _ext_tf else
               "routed_" + ("hazir" if karar == "Hazır" else "kontrol")),
              level="error" if _ext_tf else ("info" if karar == "Hazır" else "warn"),
              summary=(f"{video.name} → RETRYABLE_FAILURE / teslim yok" if _ext_tf else
                       f"{video.name} → {karar}")
                      + (f" ({'; '.join(reasons)})" if reasons else "") + f" · toplam {total} sn.",
              module="pipeline", media_id=media_id, filename=video.name, duration_seconds=total,
              detail=summary_obj)
    print(json.dumps({"karar": karar,
                      "processing_status": ("RETRYABLE_FAILURE" if _ext_tf else
                                            ("DEGRADED" if _ext_degraded else "SUCCEEDED")),
                      "delivery_status": "WITHHELD_TECHNICAL_FAILURE" if _ext_tf else "PRODUCED",
                      "neden": reasons, "hub": str(clip_dir),
                      "teslim": str(dest) if dest is not None else None, "timings": timings},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
