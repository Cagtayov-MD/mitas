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
  (test icin hizli:) --asr-max-seconds 120 --ocr-head 60 --ocr-tail 120 --fps 2
"""
from __future__ import annotations
import argparse, json, subprocess, shutil, time, re, hashlib, unicodedata, os, sys
import urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

PROJECT_ROOT = Path(r"E:\MITAS")
DB_ROOT = PROJECT_ROOT / "Database"
OUT_ROOT = PROJECT_ROOT / "Mitas Output"
HAZIR = OUT_ROOT / "Hazır"
KONTROL = OUT_ROOT / "Kontrol"
EVENTS_PATH = PROJECT_ROOT / "outputs" / "system_events.jsonl"
MASTER_MD = OUT_ROOT / "_ISLEM_LOG.md"
MASTER_JSONL = OUT_ROOT / "_ISLEM_LOG.jsonl"
HERE = Path(__file__).resolve().parent
FFMPEG = PROJECT_ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"
FFPROBE = PROJECT_ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffprobe.exe"
PY_OCR = PROJECT_ROOT / "venvs" / "ocr" / "Scripts" / "python.exe"
PY_ASR = PROJECT_ROOT / "venvs" / "asr" / "Scripts" / "python.exe"
PY_PDF = Path(r"C:\Users\TRT03\AppData\Local\Programs\Python\Python310\python.exe")

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


def xml_original(video: Path) -> str:
    """Video yanindaki <stem>.xml sidecar'dan orijinal adi (<TITLE>) oku → afiş icin.
    Yabancı filmde TRT başlığı Türkçe ("SİYAH İNCİ"), XML <TITLE> orijinal ("BLACK BEAUTY").
    Yoksa "" (afiş Türkçe başlıkla denenir; bulunamazsa afiş yok, ses/altyazı bloğu kalır)."""
    try:
        import xml.etree.ElementTree as ET
        xp = video.with_suffix(".xml")
        if not xp.exists():
            return ""
        tt = ET.parse(str(xp)).getroot().find(".//TITLE")
        return (tt.text or "").strip() if tt is not None else ""
    except Exception:  # noqa: BLE001
        return ""


def xml_roles(video: Path) -> dict:
    """Video yanindaki <stem>.xml sidecar'dan rol listelerini cikar (rol akli ankraji).

    BEAN/PROPERTY: isim = V_ROL_FIRST + V_ROL_LAST, rol = V_ROLE_TYPE.
    (_hile_manifest.xml_data ile AYNI mantik: YONETMEN->yonetmen, YAPIM->yapimci,
    OYUNCU/ROL->oyuncu.) XML yoksa/bossa {} doner → _pipe_pdf'e arg verilmez."""
    oy, yon, yap = [], [], []
    try:
        import xml.etree.ElementTree as ET
        xp = video.with_suffix(".xml")
        if not xp.exists():
            return {}
        root = ET.parse(str(xp)).getroot()
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


def ffprobe_specs(video: Path):
    res = fps = dur = "—"
    dur_sec = 0.0
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


def extract_window(video: Path, dst: Path, *, prefix, fps, start=None, length=None, timeout=1800):
    """Native cozunurlukte (scale YOK) fps kareleri cikar. Kare sayisini dondurur."""
    dst.mkdir(parents=True, exist_ok=True)
    cmd = [FFMPEG if FFMPEG.exists() else "ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(video)]
    if length is not None:
        cmd += ["-t", str(length)]
    cmd += ["-vf", f"fps={fps}", str(dst / f"{prefix}_%04d.png")]
    run(cmd, timeout=timeout)
    return len(list(dst.glob(f"{prefix}_*.png")))


def extract_audio(video: Path, dst: Path, timeout=1800):
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
OZET_MAX_SOURCE_CHARS = 60000     # asr_server SUMMARY_MAX_SOURCE_CHARS
OZET_MAX_TOKENS = 1500            # asr_server SUMMARY_MAX_TOKENS
OZET_TIMEOUT_SECONDS = 90         # asr_server SUMMARY_TIMEOUT_SECONDS


def _ozet_source_text(transcript: str) -> str:
    """Uzun transcript'i kirp (asr_server._summary_source_text ile ayni)."""
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
    """Ozet KURALI (Cagatay): SADECE Latin alfabesi — Kiril/Cince/Arap/Yunan/CJK HARFLERI DUSER.
    Once yabanci-aksan ASCII'ye katlanir (_FOREIGN_ACCENT_FOLD; Turkce ç/ğ/ı/İ/ö/ş/ü KORUNUR),
    sonra Latin-disi harfler duser. Deterministik kemer: prompt slip etse bile non-Latin sizmaz,
    yabanci aksanli ad (José) da ASCII'ye (Jose) iner."""
    return "".join(ch for ch in (s or "").translate(_FOREIGN_ACCENT_FOLD)
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


def _generate_ozet(transcript_text: str, *, title: str = "", duration: str = "") -> str | None:
    """Transcript'ten Sonnet ile film/dizi olay-orgusu ozeti uretir (spoiler dahil).

    ANTHROPIC_API_KEY yoksa, prompt dosyasi yoksa, transcript bossa veya istek
    cokerse None doner — cagiran taraf placeholder'a geri duser. Pipeline'i ASLA
    cokertmez (tum hatalar yutulur).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    text = (transcript_text or "").strip()
    if not text:
        return None
    try:
        system_content = OZET_PROMPT_PATH.read_text(encoding="utf-8")
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
            return _latin_only(content.strip())   # SADECE Latin (Kiril/Çince düşer) — özet kuralı (kemer)
    except urllib.error.HTTPError as exc:  # kredi/kota ise durumu işaretle, sonra sessiz fallback
        _mark_anthropic_http_error(exc)
        return None
    except Exception:  # noqa: BLE001 — timeout/URLError/JSON vs.: mark YOK (yanlış-alarm olmasın)
        return None
    return None


def _fetch_internet_ozet(*, title="", original="", year="", duration=""):
    """Kürtçe/desteklenmeyen-dil filmi: ASR çeviremez → film kimliğinden (TMDB) internet plot çek,
    BİZİM özet promptumuzla (ozet_film.txt) özetle. Bulunamazsa None → çağıran dürüst placeholder'a düşer.
    (Çağatay direktifi: Kürtçe çıkarsa ASR uğraşmasın, özeti internetten bizim promptla çek.)"""
    key = os.environ.get("MITAS_TMDB")
    if not key:
        return None
    import urllib.parse
    import urllib.request

    def _overview(q, kind, lang):
        try:
            params = {"api_key": key, "query": q, "language": lang}
            if year and kind == "movie":
                params["year"] = year
            url = f"https://api.themoviedb.org/3/search/{kind}?" + urllib.parse.urlencode(params)
            with urllib.request.urlopen(url, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
            for res in (data.get("results") or [])[:1]:
                ov = (res.get("overview") or "").strip()
                if ov and len(ov) > 60:
                    return ov
        except Exception:  # noqa: BLE001
            return None
        return None

    overview = None
    for q in [x for x in (original, title) if x]:
        for lang in ("tr-TR", "en-US"):
            for kind in ("movie", "tv"):
                overview = _overview(q, kind, lang)
                if overview:
                    break
            if overview:
                break
        if overview:
            break
    if not overview:
        return None
    # BİZİM özet promptumuzla internet plotunu özetle (tutarlı v4 format)
    return _generate_ozet(overview, title=title, duration=duration)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--profile", default=None, help="film_dizi (tip TRT 3.parselden oto) | haber|belgesel|muzik|stt (yoksa TRT'den)")
    ap.add_argument("--fps", type=float, default=2.0, help="kare cikarim fps (native cozunurluk)")
    ap.add_argument("--ocr-head", type=float, default=180.0, help="acilis penceresi sn")
    ap.add_argument("--ocr-tail", type=float, default=240.0, help="kapanis penceresi sn")
    ap.add_argument("--asr-max-seconds", type=float, default=0.0, help="ASR'i ilk N sn ile sinirla (test)")
    ap.add_argument("--no-asr", action="store_true")
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--no-copy-source", action="store_true", help="kaynak videoyu hub'a kopyalama (test)")
    args = ap.parse_args(argv)

    t_all = time.perf_counter()
    timings = {}
    video = Path(args.video)
    if not video.exists():
        print(f"HATA: video yok: {video}")
        return 2

    trt, title, prof_from_id, bolum = parse_filename(video)
    original = xml_original(video)              # XML <TITLE> → afiş orijinal ad (yabancı film)
    xml_role_map = xml_roles(video)             # XML rol listeleri → rol aklı ankrajı (yoksa {})
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
    clip_id = media_id
    n = 2
    while (DB_ROOT / clip_id).exists():
        clip_id = f"{media_id}_{n}"; n += 1
    clip_dir = DB_ROOT / clip_id
    (clip_dir / "source").mkdir(parents=True, exist_ok=True)
    (clip_dir / "frames").mkdir(parents=True, exist_ok=True)
    (clip_dir / "ocr").mkdir(parents=True, exist_ok=True)
    (clip_dir / "asr").mkdir(parents=True, exist_ok=True)
    (clip_dir / "pdf").mkdir(parents=True, exist_ok=True)
    print(f"[hub] {clip_dir}  profil={profile} trt={trt} baslik={title!r}")

    # --- source kopya + clip.json ---
    size = video.stat().st_size
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
        "content_hash": "",
    })
    log_event("media_imported", summary=f"{video.name} pipeline'a alindi ({size // (1024*1024)} MB, profil={profile}).",
              module="pipeline", media_id=media_id, filename=video.name, detail={"clip_id": clip_id, "profile": profile, "trt_id": trt})

    res = fps_s = dur = "—"
    dur_sec = 0.0
    giris_frames = clip_dir / "frames" / "giris"
    cikis_frames = clip_dir / "frames" / "cikis"
    audio_path = clip_dir / "audio" / "audio16k.wav"

    # ===== BLOK ÇÖZ (ffmpeg: specs + native frame + ses) =====
    t0 = time.perf_counter()
    try:
        res, fps_s, dur, dur_sec = ffprobe_specs(video)
        head = min(args.ocr_head, dur_sec or args.ocr_head)
        nf_g = extract_window(video, giris_frames, prefix="g", fps=args.fps, start=0, length=head)
        nf_c = 0
        if dur_sec > (args.ocr_head + args.ocr_tail + 5):
            nf_c = extract_window(video, cikis_frames, prefix="c", fps=args.fps,
                                  start=max(0, dur_sec - args.ocr_tail), length=args.ocr_tail)
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
    if not args.no_ocr:
        frame_dirs = [str(giris_frames)]
        if cikis_frames.exists() and any(cikis_frames.glob("*.png")):
            frame_dirs.append(str(cikis_frames))
        ocr_cmd = [str(PY_OCR), str(HERE / "_pipe_ocr.py"), "--frames", *frame_dirs,
                   "--out", str(ocr_out), "--profile", profile]
        log_event("ocr_started", summary=f"{video.name} icin OCR kunye basladi.",
                  module="ocr", media_id=media_id, filename=video.name, job_id=ocr_job, detail={"clip_id": clip_id})
        ocr_proc = subprocess.Popen(ocr_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace")
        t_ocr = time.perf_counter()

    # ASR komutu hazırla ve başlat
    asr_proc = None
    t_asr = None
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
        log_event("asr_started", summary=f"{video.name} icin ASR basladi (profil={content_profile}).",
                  module="asr", media_id=media_id, filename=video.name, job_id=asr_job, detail={"clip_id": clip_id, "content_profile": content_profile})
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
            timings["ocr"] = round(time.perf_counter() - t_ocr, 2)
            st = j.get("status", "failed")
            update_clip_module(clip_dir, "ocr", "done" if st == "done" else "partial", ocr_job)
            log_event("ocr_completed" if st == "done" else "ocr_partial",
                      level="info" if st == "done" else "warn",
                      summary=f"{video.name}: OCR kunye {ocr_lines} satir, bucket={ocr_bucket}, motor={j.get('engine')} ({timings['ocr']} sn).",
                      module="ocr", media_id=media_id, filename=video.name, job_id=ocr_job, duration_seconds=timings["ocr"],
                      detail={"clip_id": clip_id, "bucket": ocr_bucket, "lines": ocr_lines, "engine": j.get("engine"), "stderr": err[-300:] if rc else None})
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

    # ===== BLOK VIDEO-KÜNYE (opsiyonel: MITAS_USE_VIDEO_CREDITS) =====
    # ASR communicate() BİTTİKTEN sonra (GPU serbest), PDF'ten ÖNCE → gemma+7b ile whisper ÇAKIŞMAZ.
    # Flag KAPALI (vars.) → blok hiç çalışmaz, video_credits=None, PDF'e arg eklenmez (sıfır etki). Asla çökmez.
    # film/dizi'de TEMİZ künye için video-okuma + v4 final VARSAYILAN AÇIK (eski OCR-only çöp üretiyordu:
    # yönetmen yok, "SERVING GIRL" yapımcı, cast boş). Acil geri dönüş: MITAS_NO_VIDEO_CREDITS=1.
    _vc_off = os.environ.get("MITAS_NO_VIDEO_CREDITS", "").strip().lower() in ("1", "true", "yes", "on")
    USE_VIDEO_CREDITS = not _vc_off
    video_credits = None
    if USE_VIDEO_CREDITS and not args.no_ocr and profile in ("film", "dizi"):
        t_vc = time.perf_counter()
        try:
            vc_cmd = [str(PY_OCR), str(HERE / "_pipe_credit_video.py"),
                      "--giris", str(giris_frames), "--cikis", str(cikis_frames)]
            rc_vc, out_vc, err_vc = run(vc_cmd, timeout=VC_TIMEOUT)
            video_credits = last_json(out_vc)
            timings["video_kunye"] = round(time.perf_counter() - t_vc, 2)
            log_event("credit_video_completed",
                      summary=f"{video.name}: video-kunye guven={(video_credits or {}).get('guven')} yon={(video_credits or {}).get('yonetmen')} ({timings.get('video_kunye')} sn).",
                      module="ocr", media_id=media_id, filename=video.name, duration_seconds=timings.get("video_kunye"),
                      detail={"clip_id": clip_id, "guven": (video_credits or {}).get("guven"),
                              "yonetmen": (video_credits or {}).get("yonetmen"),
                              "stderr": (err_vc or "")[-200:] if rc_vc else None})
        except Exception as exc:  # noqa: BLE001 — video-kunye akışı/PDF'i ASLA bozmaz
            log_event("credit_video_failed", level="warn", summary=f"video-kunye blogu hata (atlandi): {exc}",
                      module="ocr", media_id=media_id, filename=video.name, error=str(exc), detail={"clip_id": clip_id})

    # ===== BLOK PDF / teslim =====
    pdf_out = clip_dir / "pdf"
    pdf_info = {}
    t0 = time.perf_counter()
    try:
        # ozet: ASR transcript'inden Sonnet ile gercek olay-orgusu ozeti.
        # transcript_plain.txt = _pipe_asr.py'nin yazdigi tam temiz metin (asr_out/).
        # Key yok / transcript yok / istek coker → eski placeholder davranisi korunur.
        ozet = "(Özet ayrı bir adımda üretilecektir.)"
        if asr_info.get("language") == "ku":
            # Kürtçe-ailesi: whisper ÇEVİREMEZ (ASR atlandı) → özeti İNTERNETTEN çek (bizim prompt). Çağatay direktifi.
            # NOT: başlık eşleşmesi belirsizse yanlış film gelebilir — kadro-tabanlı kimlik ileride bağlanacak.
            net_ozet = _fetch_internet_ozet(title=title, original=original, year=film_year, duration=dur)
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
        # film/dizi → ses & altyazı bloğu: kaynak video + (ASR yazdıysa) kanal-dil JSON
        _pa_pdf = PROFILE_ASR.get(profile)
        if _pa_pdf and _pa_pdf.get("language") == "auto":
            cmd += ["--video", str(video)]
            _chl = asr_out / "chlang.json"
            if _chl.exists():
                cmd += ["--chlang", str(_chl)]
            cmd += ["--subtitle", str(asr_out / "subtitle.json")]   # 1.3 altyazi cache: yoksa _pipe_pdf hesaplar+yazar, varsa okur (yeniden tarama yok)
        rc, out, err = run(cmd, timeout=PDF_TIMEOUT)  # altyazı Paddle taraması / kanal-dil self-run payı
        pdf_info = last_json(out) or {"status": "failed", "pdf_error": err[-300:]}
        timings["pdf"] = round(time.perf_counter() - t0, 2)
        log_event("pdf_completed" if pdf_info.get("status") == "done" else "pdf_partial",
                  level="info" if pdf_info.get("status") == "done" else "warn",
                  summary=f"{video.name}: teslim hazirlandi (PDF={'var' if pdf_info.get('pdf_path') else 'yok, md'}, cast={pdf_info.get('cast_count')}) ({timings['pdf']} sn).",
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
    if USE_VIDEO_CREDITS and profile in ("film", "dizi") and pdf_info.get("pdf_path"):
        t_v4 = time.perf_counter()
        try:
            v4_tmp = pdf_out / "kunye_v4.pdf"
            v4_cmd = [str(PY_PDF), str(HERE / "tek_film_kunye.py"),
                      "--clip", str(clip_dir), "--title", title, "--out", str(v4_tmp)]
            if original:
                v4_cmd += ["--original", original]
            if film_year:
                v4_cmd += ["--year", str(film_year)]
            if video_credits:
                v4_cmd += ["--video-credits", json.dumps(video_credits, ensure_ascii=False)]
            v4_cmd += ["--profile", profile]               # Fix 3b: film/dizi → tek_film_kunye.py'e ilet
            if bolum:
                v4_cmd += ["--bolum", bolum]               # Fix 3b: BİZİM EVİN HALLERİ vb. bölüm numarası
            rc_v4, out_v4, err_v4 = run(v4_cmd, timeout=V4_TIMEOUT)
            if rc_v4 == 0 and v4_tmp.exists() and v4_tmp.stat().st_size > 10000:
                os.replace(str(v4_tmp), pdf_info["pdf_path"])
                v4_png = pdf_out / "kunye_v4_onizleme.png"
                if v4_png.exists():
                    os.replace(str(v4_png), str(pdf_out / "kunye_onizleme.png"))
                timings["v4_final"] = round(time.perf_counter() - t_v4, 2)
                log_event("v4_finalize_completed",
                          summary=f"{video.name}: kunye v4'e cevrildi ({timings['v4_final']} sn).",
                          module="pdf", media_id=media_id, filename=video.name,
                          duration_seconds=timings["v4_final"], detail={"clip_id": clip_id})
            else:
                log_event("v4_finalize_skipped", level="warn",
                          summary=f"{video.name}: v4 final atlandi (rc={rc_v4}); pre-v4 PDF kaldi.",
                          module="pdf", media_id=media_id, filename=video.name,
                          detail={"clip_id": clip_id, "stderr": (err_v4 or "")[-200:]})
        except Exception as exc:  # noqa: BLE001 — v4 final akışı/PDF'i ASLA bozmaz
            log_event("v4_finalize_failed", level="warn", summary=f"v4 final hata (atlandi): {exc}",
                      module="pdf", media_id=media_id, filename=video.name, error=str(exc), detail={"clip_id": clip_id})

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
            log_event("qwen_final_qc",
                      summary=f"{video.name}: qwen final-QC ({timings.get('qwen_qc')} sn) — {(qwen_qc or {}).get('notlar') or 'ok'}",
                      module="qc", media_id=media_id, filename=video.name,
                      detail={"clip_id": clip_id, "qwen_qc": qwen_qc})
        except Exception as exc:  # noqa: BLE001 — qwen-QC pipeline'i ASLA bozmaz (ollama yok/model yok vb.)
            qwen_qc = {"error": f"{type(exc).__name__}: {exc}"}
            log_event("qwen_final_qc_skipped", level="warn",
                      summary=f"{video.name}: qwen final-QC atlandi: {exc}",
                      module="qc", media_id=media_id, filename=video.name, detail={"clip_id": clip_id})

    # ===== YONLENDIR (Hazir/Kontrol) =====
    reasons = []
    if ocr_bucket not in ("GUVENILIR",):
        reasons.append(f"OCR bucket={ocr_bucket}")
    if asr_status not in ("done", "ATLANDI", "skipped_unsupported_lang"):  # Kürtçe-atla = kasıtlı, Kontrol DEĞİL
        reasons.append(f"ASR={asr_status}")
    if not pdf_info.get("pdf_path"):
        reasons.append("PDF render yok (md teslim)")
    # --- B-4: XML↔PDF cast tutarlılık kapısı (yanlış-film yakala) ---
    # XML oyuncu listesi ≥2 isim VE üretilen cast ≥2 isim VE fold/fuzzy kesişim == 0 → şüphe.
    # Tek-isim/boş listede FLAG YOK (dizi kısmi-kadro false-positive'ini önle).
    # credit_crosscheck.name_match/cast_overlap helper'larını YENİDEN YAZMADAN kullan.
    try:
        _xml_cast = [n for n in (xml_role_map.get("oyuncu") or []) if str(n).strip()]
        _pdf_cast = [n for n in (pdf_info.get("cast") or []) if str(n).strip() and str(n).strip() != "—"]
        if len(_xml_cast) >= 2 and len(_pdf_cast) >= 2:
            sys.path.insert(0, str(HERE))
            import credit_crosscheck as _cc
            if _cc.cast_overlap(_pdf_cast, _xml_cast) == 0:
                reasons.append("XML-PDF cast kesişimi 0 (yanlış-film şüphesi)")
    except Exception:  # noqa: BLE001 — kesişim kapısı kararı ASLA bozmaz (helper yoksa/hata → atla)
        pass
    # --- B-4 bonus: tek_film_kunye.py (v4) KB cross-check çelişkisini karara yansıt ---
    # out_v4 yakalanıyordu ama parse edilmiyordu. tek_film_kunye.py rapor'u indent=2 ÇOK-SATIR
    # basar (last_json tek-satır arar, tutmaz) → ilk '{'tan raw_decode ile blok-parse.
    # verdict/kimlik_dogru rapor["adimlar"]["cross_check"] altında (top-level değil).
    try:
        if USE_VIDEO_CREDITS and profile in ("film", "dizi") and "out_v4" in dir():
            _v4j = None
            _i = out_v4.find("{")
            if _i >= 0:
                try:
                    _v4j, _ = json.JSONDecoder().raw_decode(out_v4[_i:])
                except Exception:  # noqa: BLE001
                    _v4j = None
            _cc4 = ((_v4j or {}).get("adimlar") or {}).get("cross_check") or {}
            if _cc4.get("verdict") == "ÇELİŞKİ" or _cc4.get("kimlik_dogru") is False:
                reasons.append("kimlik çelişkisi (KB cross-check)")
            # KIRMIZI ÇİZGİ (2026-06-07): yönetmen OCR'dan okunamadıysa KB-fill YOK → künye Kontrol'e
            # (zorla doldurma yok; insan teyidi). v4 raporu yönetmeni boşsa işaretle.
            if not (((_v4j or {}).get("v4") or {}).get("yonetmen") or []):
                reasons.append("yönetmen okunamadı (KB-fill yok — kırmızı çizgi)")
            # KB cast-ekleme ORTA güven (yönetmen teyitsiz, sadece cast) → insan göz atsın
            if _cc4.get("cast_add_tier") == "ORTA":
                reasons.append("KB cast-ekleme ORTA güven (insan teyidi gerek)")
    except Exception:  # noqa: BLE001 — parse hatası kararı bozmasın
        pass
    # B-3 qwen-QC kalibrasyonu: afiş + büyük-harf qwen sinyalleri KIRILGAN (VLM yanılır; üstelik
    # büyük-harf zaten deterministik tr_upper/ozet_v4, afiş poster_fetch ile garanti) → bu İKİ sinyal
    # Kontrol TETİKLEMEZ, yalnız qwen_uyari'ya (log/QC görünürlüğü) yazılır. Diğer 5 sinyal reasons'ta KALIR.
    qwen_uyari = []
    if qwen_qc and not qwen_qc.get("error"):   # qwen final-QC: model gözüyle son kapı (PDF'i gören)
        if not qwen_qc.get("ozet_var"):
            reasons.append("qwen: özet yok/placeholder")
        if (qwen_qc.get("oyuncu_sayisi") or 0) < 1:
            reasons.append("qwen: oyuncu yok")
        if not qwen_qc.get("yonetmen_var") and not qwen_qc.get("yapimci_var"):
            reasons.append("qwen: yön+yapımcı yok")
        if not qwen_qc.get("ses_dil_var"):
            reasons.append("qwen: ses/dil yok")
        if qwen_qc.get("turkce_karakter_bozuk_var"):
            reasons.append("qwen: Türkçe karakter bozuk")
        if qwen_qc.get("latin_disi_alfabe_var"):                # başka alfabe (Kiril/Yunan/Arap/CJK) PDF'e sızmamalı
            reasons.append("qwen: Latin-dışı alfabe (deterministik kemer atladı → Kontrol)")
        # KIRILGAN ikili → uyarı (karar değil): false-Kontrol azalt
        if not qwen_qc.get("afis_var"):
            qwen_uyari.append("qwen: afiş yok (deterministik poster_fetch garanti — uyarı)")
        if not qwen_qc.get("hepsi_buyuk_harf"):
            qwen_uyari.append("qwen: büyük-harf değil (deterministik tr_upper — uyarı)")
        if qwen_qc.get("yabanci_ad_ascii_degil"):              # yabancı ad aksanlı: kemer+Sonnet birincil, qwen ince-aksanda güvenilmez → uyarı
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
    karar = "Hazır" if not reasons else "Kontrol"
    dest_root = HAZIR if karar == "Hazır" else KONTROL
    dest = dest_root / clip_id
    dest.mkdir(parents=True, exist_ok=True)
    # teslim parcalari kopyala
    for src in [kunye_path, Path(pdf_info.get("pdf_path") or ""), Path(pdf_info.get("preview_path") or ""),
                Path(pdf_info.get("md_path") or "")]:
        if src and src.exists():
            shutil.copy2(src, dest / src.name)
    total = round(time.perf_counter() - t_all, 2)
    timings["toplam"] = total

    summary_obj = {
        "clip_id": clip_id, "video": str(video), "profile": profile, "trt_id": trt, "title": title,
        "karar": karar, "neden": reasons, "qwen_uyari": qwen_uyari, "qwen_qc": qwen_qc, "ocr_bucket": ocr_bucket, "ocr_lines": ocr_lines,
        "asr_status": asr_status, "asr_segments": asr_info.get("clean_segments"),
        "transcript_chars": asr_info.get("transcript_chars"),
        "resolution": res, "fps": fps_s, "duration": dur, "timings_sec": timings,
        "hub": str(clip_dir), "teslim": str(dest),
        "pdf": pdf_info.get("pdf_path"), "md": pdf_info.get("md_path"), "ts": now_iso(),
    }
    write_json(clip_dir / "_DURUM.json", summary_obj)
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
        f"- Teslim: {dest}",
        "",
    ]
    if not MASTER_MD.exists():
        MASTER_MD.write_text("# MİTAS — İşlem Log'u (Hazır / Kontrol)\n\n", encoding="utf-8")
    with MASTER_MD.open("a", encoding="utf-8") as h:
        h.write("\n".join(md) + "\n")
    log_event("routed_" + ("hazir" if karar == "Hazır" else "kontrol"),
              level="info" if karar == "Hazır" else "warn",
              summary=f"{video.name} → {karar}" + (f" ({'; '.join(reasons)})" if reasons else "") + f" · toplam {total} sn.",
              module="pipeline", media_id=media_id, filename=video.name, duration_seconds=total,
              detail=summary_obj)
    print(json.dumps({"karar": karar, "neden": reasons, "hub": str(clip_dir), "teslim": str(dest), "timings": timings}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
