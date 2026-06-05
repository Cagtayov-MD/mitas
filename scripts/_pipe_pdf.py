# -*- coding: utf-8 -*-
"""MITAS pipeline — PDF/teslim blok runner (GLOBAL python: reportlab+fitz).

Künye metnini cast/crew'e ayırır (ORTAK pdf-mitas/credit_parse) ve pdf-mitas/_make_pdf
ile altın "Dosya" PDF'i render eder. reportlab/fitz yoksa yapılandırılmış .md teslimi
yazar (sistem buna takılmaz). stdout'a tek satır JSON sonuç basar.

Profil: TEK 'Film/Dizi' — tip TRT 3. parselden OTOMATİK:
  1 → FİLM (ilk 8 oyuncu + Yapımcı/Yönetmen)
  0 → DİZİ (tüm oyuncular + tüm jenerik, kanonik sıra)
"""
from __future__ import annotations
import sys, json, os, re, argparse, importlib.util, datetime
import urllib.error, urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PDFMITAS = Path(r"E:\MITAS\OCR-worktree\pdf-mitas")
MAKE_PDF = PDFMITAS / "_make_pdf.py"
CREDIT_PARSE = PDFMITAS / "credit_parse.py"
HERE = Path(__file__).resolve().parent
PY_ASR = Path(r"E:\MITAS\venvs\asr\Scripts\python.exe")   # kanal-dil (faster-whisper)
PY_OCR = Path(r"E:\MITAS\venvs\ocr\Scripts\python.exe")   # altyazı (Paddle)
CHLANG_SCRIPT = HERE / "_channel_lang.py"
SUBTITLE_SCRIPT = HERE / "_subtitle_detect.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cp = _load("credit_parse", CREDIT_PARSE)
nn = _load("name_normalize", PDFMITAS / "name_normalize.py")   # Türkçe koru / diğer ASCII (+Qwen)
pf = _load("poster_fetch", PDFMITAS / "poster_fetch.py")       # güvenli IMDb afiş
# rol aklı: OCR rollerini XML (birincil) + meslek-DB (ikincil) ile düzelt.
# Yükleme cökerse reconcile tamamen atlanır (eski davranış korunur, asla boş PDF).
try:
    rr = _load("role_reconcile", PDFMITAS / "role_reconcile.py")
except Exception:  # noqa: BLE001
    rr = None


def _run_json(cmd, timeout=1800):
    """alt-venv script'ini çalıştır → stdout'taki SON JSON satırı (yoksa None)."""
    import subprocess
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except Exception:  # noqa: BLE001
        return None
    for line in reversed([l.strip() for l in (r.stdout or "").splitlines() if l.strip()]):
        if line.startswith("{"):
            try:
                return json.loads(line)
            except Exception:  # noqa: BLE001
                continue
    return None


def _load_json(path):
    try:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    return None


_LANG_CODES = {
    "türkçe": "TR", "turkce": "TR", "türk": "TR", "tr": "TR",
    "ingilizce": "EN", "english": "EN", "en": "EN",
    "almanca": "DE", "german": "DE", "de": "DE",
    "fransızca": "FR", "french": "FR", "fr": "FR",
    "arapça": "AR", "arabic": "AR", "ar": "AR",
    "rusça": "RU", "russian": "RU", "ispanyolca": "ES", "italyanca": "IT",
}


# "efekt" ailesi — ses kanalı konuşma içermiyor; bunlar ses listesinden elenir.
_EFEKT_LABELS = {"efekt", "ef", "efekt/zayıf", "efekt/sessiz", "boş", "sessiz"}


def _lang_code(s):
    """Dil adini koda cevir: Türkçe->TR, English->EN. Bilinmeyen->ilk 2 harf (BUYUK).
    'efekt' ailesi → 'EF' (konuşmasız kanal); None/boş → '—'."""
    t = (s or "").strip().lower()
    if not t:
        return "—"
    if t in _EFEKT_LABELS or t.startswith("efekt"):
        return "EF"
    for k, v in _LANG_CODES.items():
        if k in t:
            return v
    return t.upper()[:2]


def _derive_audio(cl):
    """cl = _channel_lang.main() çıktısı VEYA _pipe_asr detect_info ({units, selected}).
    → (ses_kanallari[:4] dil-KODU, ana_dil KODU, sesler_ic_ice) | None.
    Dil adlari TR/EN/... koduna cevrilir (kullanici kurali: 'Türkçe' degil 'TR').
    EF kanalları ses listesinden elenir; hepsi EF ise ses=None.
    summary_language=None ise ana_dil='—' (düşük-güven fallback atanmaz)."""
    if not cl:
        return None
    units = cl.get("units") or []
    speech = [u for u in units if u.get("role") == "konuşma"]
    # Tüm kanallar için kod üret; EF olmayanları al (konuşma kanalları)
    all_codes = [_lang_code(u.get("label", "")) for u in units[:4]]
    non_ef = [c for c in all_codes if c != "EF"]
    ses = non_ef if non_ef else None   # hepsi EF ise ses=None → PDF ses satırı basmasın
    # summary_language None ise ana_dil "—" (konuşma yok veya belirsiz → atama yok)
    raw_ana = cl.get("summary_language") or (cl.get("selected") or {}).get("language")
    ana = _lang_code(raw_ana) if raw_ana else "—"
    ic = cl.get("sesler_ic_ice")
    if ic is None:
        ic = any(u.get("mixed") for u in speech)
    return ses, ana, bool(ic)


def audio_subtitle_block(args) -> dict:
    """Ses & altyazı bloğu (film/dizi): kanal-dil + altyazı tespiti → _make_pdf anahtarları.

    Kanal-dil: ASR'nin yazdığı --chlang JSON varsa ONU kullan (yeniden koşma), yoksa --video ile koş.
    Altyazı: önceden hesaplanmış --subtitle JSON, yoksa --video ile Paddle alt-bant taraması.
    Sadece --video/--chlang verilince çalışır. Hata olursa boş döner → PDF bloksuz devam eder.
    """
    block: dict = {}
    try:
        cl = _load_json(args.chlang) if args.chlang else None
        if cl is None and args.video and Path(args.video).exists():
            cl = _run_json([PY_ASR, CHLANG_SCRIPT, args.video])
        der = _derive_audio(cl)
        if der and der[0]:                       # ses kanalları çıktıysa
            block["ses_kanallari"] = der[0]
            block["ana_dil"] = der[1]
            block["sesler_ic_ice"] = der[2]
        sub = _load_json(args.subtitle) if args.subtitle else None
        if sub is None and args.video and Path(args.video).exists():
            sub = _run_json([PY_OCR, SUBTITLE_SCRIPT, args.video])
        if sub is not None and "altyazili" in sub:
            block["altyazi"] = "EVET" if sub.get("altyazili") else "HAYIR"
        # Tutarlılık denetimi: ana_dil TR ve "—" dışında bir değerse VE altyazı HAYIR ise → uyarı
        # (TRT yayıncısı TR'dir; başka dil + altyazısız mantıksız → KONTROL'e yönlendir)
        _ana = block.get("ana_dil", "—")
        _alt = block.get("altyazi")
        if _ana not in ("TR", "—", None) and _alt == "HAYIR":
            block["ses_uyari"] = "SES_MANTIKSIZ"
    except Exception:  # noqa: BLE001 - ses/altyazı bloğu PDF'i ASLA bozmaz
        pass
    return block


def write_md(out: Path, d: dict) -> Path:
    md = out / "kunye_teslim.md"
    lines = [
        f"# MİTAS • {d['profile']} • {d['title']}",
        f"Üretim: {d['date']}", "",
        "## Künye",
        f"- ID: {d['trt'] or '—'}",
        f"- Çözünürlük: {d['res']}  ·  Kare: {d['fps']}  ·  Süre: {d['dur']}",
    ]
    if d["bolum"]:
        lines.append(f"- Bölüm: {d['bolum']}")
    lines += ["", "## Anahtar Sözcükler", " ; ".join(d["cast"]) or "—", "", "## Oyuncular"]
    lines += [f"- {c}" for c in d["cast"]] or ["—"]
    lines += ["", "## Yapım Ekibi"]
    for role, names in d["crew"]:
        nm = names if isinstance(names, list) else [names]
        lines.append(f"- {role}: " + ", ".join(nm))
    if d.get("ses_kanallari") or d.get("altyazi"):
        lines += ["", "## Ses & Altyazı"]
        for i, l in enumerate(d.get("ses_kanallari", []), 1):
            lines.append(f"- {i}. kanal: {l}")
        if d.get("ana_dil"):
            lines.append(f"- Ana dil: {d['ana_dil']}")
        if d.get("altyazi"):
            lines.append(f"- Altyazı: {d['altyazi']}")
        if d.get("sesler_ic_ice"):
            lines.append("- Sesler iç içedir (seslendirme + orijinal)")
    lines += ["", "## Özet", d["ozet"]]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md


def _xml_roles_from_args(args) -> dict | None:
    """CLI'dan XML rol sözlüğü çıkar: {oyuncu:[], yonetmen:[], yapimci:[]}.

    Öncelik: --xml-roles JSON (varsa) → yoksa virgülle ayrık --xml-* listeleri.
    Hiçbiri yoksa None (XML ankrajı atlanır → eski davranış)."""
    if args.xml_roles:
        try:
            d = json.loads(args.xml_roles)
            if isinstance(d, dict):
                out = {k: [str(x).strip() for x in (d.get(k) or []) if str(x).strip()]
                       for k in ("oyuncu", "yonetmen", "yapimci")}
                return out if any(out.values()) else None
        except Exception:  # noqa: BLE001 — bozuk JSON → listelere geri düş
            pass
    sp = lambda s: [x.strip() for x in (s or "").split(",") if x.strip()]
    out = {"oyuncu": sp(args.xml_oyuncu), "yonetmen": sp(args.xml_yonetmen),
           "yapimci": sp(args.xml_yapimci)}
    return out if any(out.values()) else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kunye", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--trt-id", default="")
    ap.add_argument("--profile", default="film_dizi")  # tek profil; tip TRT'den otomatik
    ap.add_argument("--resolution", default="—")
    ap.add_argument("--fps", default="—")
    ap.add_argument("--duration", default="—")
    ap.add_argument("--bolum", default="")
    ap.add_argument("--ozet", default="(Özet ayrı bir adımda üretilecektir.)")
    ap.add_argument("--video", default="")      # kaynak video → ses & altyazı tespiti (film/dizi)
    ap.add_argument("--chlang", default="")     # ASR'nin yazdığı kanal-dil JSON (yeniden koşmamak için)
    ap.add_argument("--subtitle", default="")   # önceden hesaplanmış altyazı JSON (opsiyonel)
    ap.add_argument("--original", default="")   # XML orijinal ad → afiş birincil sorgu (yabancı film)
    ap.add_argument("--year", default="")        # film/yayın yılı → afiş çok-sürümde yedek ayraç
    # XML rol ankrajı (rol aklı): virgülle ayrık listeler VEYA tek --xml-roles JSON.
    # Boş/verilmezse XML adımı atlanır (eski davranış).
    ap.add_argument("--xml-oyuncu", default="")
    ap.add_argument("--xml-yonetmen", default="")
    ap.add_argument("--xml-yapimci", default="")
    ap.add_argument("--xml-roles", default="")   # tek JSON: {"oyuncu":[...],"yonetmen":[...],"yapimci":[...]}
    ap.add_argument("--video-credits", default="")  # video-künye JSON {yonetmen,yapimci,cast} (flag; "" → atla, eski davranış)
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = [l.strip() for l in Path(args.kunye).read_text(encoding="utf-8", errors="ignore").splitlines()
           if l.strip() and not l.startswith("#")] if Path(args.kunye).exists() else []

    # --- tip TRT 3. parselden otomatik (§3) ---
    dizi = cp.is_dizi(args.profile, args.trt_id or args.title)
    profile_label = "DİZİ" if dizi else "FİLM"
    cast, crew = cp.parse_credits(raw, args.title, dizi=dizi)
    # --- video-künye AUGMENT (flag): cast birleştir + yönetmen/yapımcı crew'e ekle ---
    # Sadece --video-credits verildiyse (mitas_pipeline flag açıkken) çalışır; "" → atla.
    # reconcile (aşağıda) augmented veriyi XML+KB ile temizler = ikinci savunma. REPLACE değil AUGMENT.
    if args.video_credits:
        try:
            _vc = json.loads(args.video_credits)
        except Exception:  # noqa: BLE001
            _vc = {}
        def _vfold(s):
            for a, b in (("ö","o"),("ü","u"),("ı","i"),("ş","s"),("ğ","g"),("ç","c"),("İ","i")):
                s = s.replace(a, b)
            return s.lower()
        _vcast = [c for c in (_vc.get("cast") or []) if c and str(c).strip()]
        if _vcast:
            cast = cp._dedup(list(cast) + _vcast)
            if not dizi:
                cast = cast[:8]
        def _aug_crew(crew, kw, label, names):
            names = [n for n in (names or []) if n and str(n).strip()]
            if not names:
                return crew
            crew = list(crew)
            for i, (rol, lst) in enumerate(crew):
                if kw in _vfold(rol):
                    crew[i] = (rol, cp._dedup(list(lst) + names)); return crew
            crew.append((label, cp._dedup(names))); return crew
        crew = _aug_crew(crew, "yonet", "Yönetmen", _vc.get("yonetmen"))
        crew = _aug_crew(crew, "yapim", "Yapımcı", _vc.get("yapimci"))
    # --- rol aklı: OCR rollerini XML (birincil) + meslek-DB (ikincil) ile düzelt ---
    # normalize'den ÖNCE (XML eşleşmesi ham OCR isimleriyle, fold credit_parse'tan).
    # DB/duckdb global python'da çökerse reconcile XML-only veya no-op; ASLA pipeline'ı bozma.
    reconcile_meta = None
    xml_roles = _xml_roles_from_args(args)
    if rr is not None and (xml_roles or True):   # xml yoksa da KB adımı çalışabilir
        try:
            cast, crew, reconcile_meta = rr.reconcile(cast, crew, xml_roles=xml_roles, use_kb=True)
        except Exception:  # noqa: BLE001 — rol aklı PDF'i ASLA bozmaz
            reconcile_meta = None
    # isim karakter kuralı: Türkçe isimler ç/ğ/ı/ö/ş/ü KORUNUR, diğer diller ASCII
    # (belirsiz ç/ö/ü isimleri Qwen'e sorulur — name_normalize)
    cast = nn.normalize_names(cast)
    crew = nn.normalize_crew(crew)
    # kunye BUYUK harf: Turkce isim Turkce-upper (irfan->İRFAN, i->İ),
    # yabanci ASCII-upper (ivan->IVAN, i->I); koken Qwen ile (saf-ASCII).
    cast = nn.upper_names(cast)
    crew = nn.upper_crew(crew)
    # afiş: güvenli IMDb eşleşmesi → out/afis.jpg.
    # yabancı film: orijinal ad (XML) birincil sorgu + kadro çapraz-kontrolü (TRT yılı güvenilmez).
    # bulunamazsa None → afiş yok, sol ray ses/altyazı bloğu kalır (frame YOK).
    poster_path = None
    try:
        poster_path = pf.fetch_poster(
            args.title, out / "afis.jpg",
            original=args.original or None, year=args.year or None,
            cast=cast, crew=crew,
        )
    except Exception:  # noqa: BLE001
        poster_path = None

    bolum = args.bolum
    if dizi and not bolum:
        _, _, b, _ = cp.classify_trt(args.trt_id or "")
        bolum = b or ""

    ozet = args.ozet
    if Path(args.ozet).exists():
        try:
            ozet = Path(args.ozet).read_text(encoding="utf-8")[:4000]
        except Exception:  # noqa: BLE001
            pass

    # ses & altyazı (film/dizi): kanal-dil + altyazı tespiti → sol ray bloğu
    audio = audio_subtitle_block(args)

    d = {
        "profile": profile_label, "trt": args.trt_id, "title": (args.title or "—")[:60],
        "res": args.resolution, "fps": args.fps, "dur": args.duration, "bolum": bolum or None,
        "cast": cast or ["—"], "crew": crew or [("Yapımcı", ["—"]), ("Yönetmen", ["—"])],
        "ozet": ozet, "date": datetime.datetime.now().strftime("%d.%m.%Y · %H:%M"),
        **audio,
    }
    md_path = write_md(out, d)

    pdf_path = preview_path = None
    pdf_error = None
    try:
        mp = _load("mp", MAKE_PDF)
        import fitz
        pdf_dict = dict(
            profile=profile_label, date=d["date"], title=d["title"],
            subtitle=None, bolum=d["bolum"], poster=poster_path,
            specs=[("ÇÖZÜNÜRLÜK", args.resolution), ("KARE HIZI", args.fps),
                   ("TOPLAM SÜRE", args.duration), ("TRT KİMLİK", args.trt_id or "—")],
            keywords=" ; ".join(cast) if cast else "—", cast=cast or ["—"],
            crew=crew or [("Yapımcı", ["—"]), ("Yönetmen", ["—"])], ozet=ozet,
            **audio,
        )
        pdf_path = out / "kunye.pdf"
        mp.build(str(pdf_path), pdf_dict)
        preview_path = out / "kunye_onizleme.png"
        fitz.open(str(pdf_path))[0].get_pixmap(dpi=150).save(str(preview_path))
    except Exception as exc:  # noqa: BLE001
        pdf_error = f"{type(exc).__name__}: {exc}"
        pdf_path = preview_path = None

    print(json.dumps({
        "status": "done" if pdf_path else "partial",
        "pdf_path": str(pdf_path) if pdf_path else None,
        "preview_path": str(preview_path) if preview_path else None,
        "md_path": str(md_path),
        "profile": profile_label,
        "cast_count": len(cast),
        "crew_roles": [r for r, _ in crew],
        "role_reconcile": reconcile_meta,   # {moved, unverified, xml_used, kb_used} | None
        "altyazi": audio.get("altyazi"),
        "ana_dil": audio.get("ana_dil"),
        "ses_kanallari": audio.get("ses_kanallari"),
        "sesler_ic_ice": audio.get("sesler_ic_ice"),
        "pdf_error": pdf_error,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
