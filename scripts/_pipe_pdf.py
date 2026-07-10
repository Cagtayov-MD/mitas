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
import debug_trace as dbg

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
try:
    import credit_text_read as ctr
except Exception:  # noqa: BLE001
    ctr = None


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
        if der:
            if der[0]:                            # ses kanalları çıktıysa (kanal listesi opsiyonel)
                block["ses_kanallari"] = der[0]
                block["sesler_ic_ice"] = der[2]
            # SAĞLAM DİL (2026-06-28): konuşma dili kanal-listesinden BAĞIMSIZ yazılır — kanal listesi
            # boş (hepsi EF) olsa bile tespit edilen dil PDF'e geçer (eskiden der[0]'a bağlıydı → düşüyordu).
            if der[1] and der[1] != "—":
                block["ana_dil"] = der[1]
        sub = _load_json(args.subtitle) if (args.subtitle and Path(args.subtitle).exists()) else None
        if sub is None and args.video and Path(args.video).exists():
            sub = _run_json([PY_OCR, SUBTITLE_SCRIPT, args.video])
            if sub is not None and args.subtitle:   # 1.3 cache'e yaz: sonraki PDF kosusu altyaziyi yeniden taramasin
                try:
                    Path(args.subtitle).write_text(json.dumps(sub, ensure_ascii=False), encoding="utf-8")
                except Exception:  # noqa: BLE001
                    pass
        if sub is not None and "altyazili" in sub:
            block["altyazi"] = "EVET" if sub.get("altyazili") else "HAYIR"
        # SAĞLAM DİL FALLBACK (2026-06-28): chlang türetmesi dil vermediyse, ASR'nin (whisper için zaten
        # algıladığı) konuşma dilini kullan → "Ana dil" satırı ~%10 filmde boş kalmasın. ASR-dili ISO
        # 2-harf kodu (tr/en/ku…) → BÜYÜK. Yalnız BOŞ/"—" iken devreye girer (mevcut tespiti ASLA ezmez).
        if (not block.get("ana_dil") or block.get("ana_dil") == "—") and getattr(args, "asr_lang", ""):
            _al = str(args.asr_lang).strip().upper()
            if _al and _al not in ("—", "EF", "NONE"):
                block["ana_dil"] = _al
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
        f"- Çözünürlük: {d['res']}  ·  Tür: {d['tur']}  ·  Süre: {d['dur']}",
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
        # SES KANAL LİSTESİ (1./2./3./4. kanal) ARTIK YAZILMIYOR (Çağatay 2026-06-20):
        # ne kunye_teslim.md'ye ne yüzey .txt'ye ne PDF'e — yalnız Ana dil + Altyazı kalır.
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


def _dedup_nonempty(values) -> list[str]:
    return cp._dedup([str(v).strip() for v in (values or []) if str(v).strip()])


def _role_fold(s: str) -> str:
    s = str(s or "")
    for a, b in (("ö", "o"), ("ü", "u"), ("ı", "i"), ("ş", "s"), ("ğ", "g"),
                 ("ç", "c"), ("İ", "i"), ("Ö", "o"), ("Ü", "u"), ("Ş", "s"),
                 ("Ğ", "g"), ("Ç", "c")):
        s = s.replace(a, b)
    return s.lower()


def _set_authoritative_role(crew, role_key: str, label: str, names: list[str]):
    key = _role_fold(role_key)
    kept = []
    for rol, lst in (crew or []):
        rf = _role_fold(rol)
        if key == "yonet":
            same_tr = rf == "yonetmen"
            same_en = rf == "director"
        elif key == "yapim":
            same_tr = rf == "yapimci"
            same_en = rf == "producer"
        else:
            same_tr = key in rf
            same_en = False
        if not same_tr and not same_en:
            kept.append((rol, lst))
    if names:
        kept.append((label, cp._dedup(names)))
    return kept


def _apply_video_credits_authoritative(cast, crew, video_credits, *, dizi: bool):
    """Use guarded text/VL credits as the PDF source of truth when supplied.

    The old code augmented the mechanical kunye.txt parser output. That allowed
    crew/music rows from flattened kunye.txt to survive even after Qwen/raw-context
    filtering. With video_credits on, empty guarded fields are safer than wrong fields.

    DEFERANS KURALI (2026-06-28): video_credits sağlandıysa, yönetmen ve yapımcı
    DAIMA yapısal hattan (LLM-extractor) gelir. credit_parse mekanik çıktısı her zaman
    temizlenir — video_credits sözlüğünde ilgili anahtar bulunmasa bile. "Anahtar yok"
    durumu LLM'nin o rolü boş döndürdüğü anlamına gelir; çöp mekanik parser çıktısına
    dönülmez. flag=MITAS_CREDIT_DEFERENCE default-AÇIK ("1").
    """
    if not video_credits:
        return cast, crew

    # İP-2 DEFERANS ÖN-KOŞULU (2026-07-11, plan rev.4 / GPT tur-2 düzeltmesi): teknik-kaza
    # (length/timeout/parse-fail) BİLİNÇLİ-BOŞ değildir. DEFERANS yalnız OK/ABSTAIN'de uygulanır;
    # TECHNICAL_FAILURE'da mekanik parser sonucu SİLİNMEZ (dar risk penceresi kapanır: LLM kazası
    # okunmuş yönetmeni artık PDF'ten düşüremez). Politika (okunamadı>yanlış-oku) AYNEN korunur.
    if str(video_credits.get("extraction_status") or "").upper() == "TECHNICAL_FAILURE":
        return cast, crew

    if "cast" in video_credits:
        cast = _dedup_nonempty(video_credits.get("cast"))
        if not dizi:
            # C-fix-canli 2026-06-29: standalone default 8→10.
            _cap = int(os.environ.get("MITAS_CAST_CAP", "10") or 10)
            cast = cast[:_cap]

    # DEFERANS: video_credits verilmişse yönetmen/yapımcıyı her durumda otoriteye bağla.
    # Anahtar yoksa LLM o rolü boş bıraktı demek → credit_parse çöpünü TEMİZLE (boş liste).
    # Eski davranış: yalnız anahtar VARSA üzerine yaz (anahtar yoksa credit_parse hayatta kalırdı).
    _deference_on = os.environ.get("MITAS_CREDIT_DEFERENCE", "1").strip().lower() \
        not in ("0", "false", "off", "no")
    crew = list(crew or [])
    if _deference_on:
        # Yapısal hat koştu: yönetmen/yapımcı için credit_parse çıktısını KOŞULSUZ temizle;
        # video_credits'teki değeri (boş da olsa) otorite kabul et.
        crew = _set_authoritative_role(
            crew, "yonet", "Yönetmen", _dedup_nonempty(video_credits.get("yonetmen"))
        )
        crew = _set_authoritative_role(
            crew, "yapim", "Yapımcı", _dedup_nonempty(video_credits.get("yapimci"))
        )
    else:
        # ESKİ DAVRANIŞA DÜŞ (MITAS_CREDIT_DEFERENCE=0): yalnız anahtar varsa üzerine yaz.
        if "yonetmen" in video_credits:
            crew = _set_authoritative_role(
                crew, "yonet", "Yönetmen", _dedup_nonempty(video_credits.get("yonetmen"))
            )
        if "yapimci" in video_credits:
            crew = _set_authoritative_role(
                crew, "yapim", "Yapımcı", _dedup_nonempty(video_credits.get("yapimci"))
            )
    return cast, crew


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kunye", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--trt-id", default="")
    ap.add_argument("--profile", default="film_dizi")  # tek profil; tip TRT'den otomatik
    ap.add_argument("--resolution", default="—")
    ap.add_argument("--tur", default="—")        # v4: KARE HIZI KALDIRILDI → TÜR (DRAM/KOMEDİ…); KB/v4-final doldurur, yoksa "—"
    ap.add_argument("--duration", default="—")
    ap.add_argument("--bolum", default="")
    ap.add_argument("--ozet", default="(Özet ayrı bir adımda üretilecektir.)")
    ap.add_argument("--video", default="")      # kaynak video → ses & altyazı tespiti (film/dizi)
    ap.add_argument("--chlang", default="")     # ASR'nin yazdığı kanal-dil JSON (yeniden koşmamak için)
    ap.add_argument("--asr-lang", dest="asr_lang", default="")  # ASR'nin (whisper) tespit ettiği konuşma dili kodu → ana_dil fail-safe fallback
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
    # --- video-künye AUTHORITATIVE (flag): Qwen/ham-context sonrası liste eski parser'ı ezer ---
    # Sadece --video-credits verildiyse (mitas_pipeline flag açıkken) çalışır; "" → atla.
    # Eski AUGMENT davranışı, flattened kunye.txt'ten gelen crew/müzik satırlarını geri sızdırıyordu.
    if args.video_credits:
        try:
            _vc = json.loads(args.video_credits)
        except Exception:  # noqa: BLE001
            _vc = {}
        cast, crew = _apply_video_credits_authoritative(cast, crew, _vc, dizi=dizi)
    if ctr is not None:
        try:
            cast = ctr.filter_cast_by_raw_context(cast, ctr.load_raw_context_for_ocr(args.kunye))
        except Exception:  # noqa: BLE001 - context gate must never break PDF rendering
            pass
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
    orig = (args.original or "").strip()   # XML <TITLE> = BİRİNCİL orijinal-ad (temizlenmiş)
    poster_path = None
    poster_source = "not_found"
    try:
        poster_path = pf.fetch_poster(
            args.title, out / "afis.jpg",
            original=orig or None, year=args.year or None,
            cast=cast, crew=crew,
        )
        if poster_path:
            poster_source = "poster_fetch_primary"
    except Exception:  # noqa: BLE001
        poster_path = None
    # XML <TITLE> yok/bozuk → afiş tutmadı → KADRO-KONSENSÜS FALLBACK (kadrodan kimlik → orijinal ad + afiş).
    # Çağatay 2026-06-08: XML her zaman olmayabilir, çalışsın. SADECE KESİN; exception-safe (pipeline'ı ASLA bozmaz).
    if not poster_path:
        try:
            import credit_identity as _ci
            _director = None
            for _role, _names in (crew or []):
                if ("yönet" in str(_role).lower() or "director" in str(_role).lower()) and _names:
                    _director = _names[0]; break
            _ident = _ci.resolve(cast, _director, max_year=(args.year or None))
            if _ident and _ident.get("status") == "KESIN":
                _fb_orig = (_ident.get("original_title") or "").strip()
                _fb_poster = pf.fetch_poster(
                    args.title, out / "afis.jpg",
                    original=_fb_orig or None, year=args.year or None,
                    cast=cast, crew=crew, tmdb_id=_ident.get("tmdb_id"),
                )
                if _fb_poster:                      # afiş kadro-teyitli id ile tuttu → orijinal adı güncelle
                    poster_path = _fb_poster
                    poster_source = "credit_identity_cast_consensus_fallback"
                    if _fb_orig:
                        orig = _fb_orig
        except Exception:  # noqa: BLE001 — fallback pipeline'ı ASLA bozmaz
            pass

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

    # Title de büyük harfle gitsin (TR-İ, yabancı ASCII): args.title ham OCR/XML olabilir.
    title_norm = nn.tr_upper((args.title or "—")[:60]) if (args.title or "").strip() else "—"
    # Özet: Türkçe prose büyük harf, fakat yabancı kişi/karakter adı kökü ASCII kalmalı
    # (FREDDİE/SOPHİE değil FREDDIE/SOPHIE).
    _ozet_names = [n for n in (cast or []) if n and str(n).strip() and str(n).strip() != "—"]
    for _role, _names in (crew or []):
        for _nm in (_names if isinstance(_names, list) else [_names]):
            if _nm and str(_nm).strip() and str(_nm).strip() != "—":
                _ozet_names.append(str(_nm))
    ozet_norm = nn.tr_upper_prose(ozet, names=_ozet_names) if ozet else ozet
    d = {
        "profile": profile_label, "trt": args.trt_id, "title": title_norm,
        "res": args.resolution, "tur": args.tur, "dur": args.duration, "bolum": bolum or None,
        "cast": cast or ["—"], "crew": crew or [("Yapımcı", ["—"]), ("Yönetmen", ["—"])],
        "ozet": ozet_norm, "date": datetime.datetime.now().strftime("%d.%m.%Y · %H:%M"),
        **audio,
    }
    md_path = write_md(out, d)
    dbg.emit("pdf", "pdf_field_written",
             subject={"field": "kunye_teslim.md", "after": {
                 "title": d.get("title"), "cast": d.get("cast"), "crew": d.get("crew"),
                 "ana_dil": d.get("ana_dil"), "altyazi": d.get("altyazi"),
                 "poster": str(poster_path) if poster_path else None,
             }, "reason": "fields written to delivery markdown"},
             evidence={"poster_source": poster_source, "role_reconcile": reconcile_meta,
                       "video_credits_used": bool(args.video_credits),
                       "raw_line_count": len(raw)},
             source={"module": "scripts/_pipe_pdf.py",
                     "input_paths": [args.kunye],
                     "output_paths": [str(md_path)]})

    pdf_path = preview_path = None
    pdf_error = None
    try:
        mp = _load("mp", MAKE_PDF)
        import fitz
        pdf_dict = dict(
            profile=profile_label, date=d["date"], title=d["title"],
            subtitle=orig or None, bolum=d["bolum"], poster=poster_path,
            specs=[("ÇÖZÜNÜRLÜK", args.resolution), ("TÜR", args.tur),
                   ("TOPLAM SÜRE", args.duration), ("TRT KİMLİK", args.trt_id or "—")],
            keywords=" ; ".join(cast) if cast else "—", cast=cast or ["—"],
            crew=crew or [("Yapımcı", ["—"]), ("Yönetmen", ["—"])], ozet=ozet_norm,
            **audio,
        )
        pdf_path = out / "kunye.pdf"
        mp.build(str(pdf_path), pdf_dict)
        preview_path = out / "kunye_onizleme.png"
        fitz.open(str(pdf_path))[0].get_pixmap(dpi=150).save(str(preview_path))
    except Exception as exc:  # noqa: BLE001
        pdf_error = f"{type(exc).__name__}: {exc}"
        pdf_path = preview_path = None

    result = {
        "status": "done" if pdf_path else "partial",
        "pdf_path": str(pdf_path) if pdf_path else None,
        "preview_path": str(preview_path) if preview_path else None,
        "md_path": str(md_path),
        "profile": profile_label,
        "cast_count": len(cast),
        "cast": cast,                       # B-4: üretilen oyuncu İSİMLERİ (XML↔PDF kesişim kapısı için)
        "crew_roles": [r for r, _ in crew],
        "crew": [(r, (n if isinstance(n, list) else [n])) for r, n in crew],  # B-4: rol+isim listesi
        "role_reconcile": reconcile_meta,   # {moved, unverified, xml_used, kb_used} | None
        "altyazi": audio.get("altyazi"),
        "ana_dil": audio.get("ana_dil"),
        "ses_kanallari": audio.get("ses_kanallari"),
        "sesler_ic_ice": audio.get("sesler_ic_ice"),
        "ses_uyari": audio.get("ses_uyari"),
        "pdf_error": pdf_error,
    }
    dbg.emit("pdf", "stage_completed",
             status="ok" if pdf_path else "warn",
             subject={"field": "pdf", "after": result, "reason": "PDF render completed"},
             evidence={"poster_source": poster_source,
                       "poster_path": str(poster_path) if poster_path else None},
             source={"module": "scripts/_pipe_pdf.py",
                     "input_paths": [args.kunye, args.video or ""],
                     "output_paths": [str(pdf_path) if pdf_path else "",
                                      str(preview_path) if preview_path else "",
                                      str(md_path)]})
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
