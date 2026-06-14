# -*- coding: utf-8 -*-
"""MITAS pipeline — OCR kunye blok runner (venvs/ocr ile kosar).

Girdi: bir veya daha cok frame dizini (acilis/kapanis kredi pencereleri).
Cikti: <out>/kunye.txt (tek satir bir isim/rol) + <out>/ocr_summary.json.

UC AKIS VAR:
  1) "scroll-aware" pipeline100 zinciri (OCR-worktree/py): CLIP bekci ile kredi
     karelerini sec -> konumlu OneOCR oku -> OCR-uzayinda dik (stitch) -> temizle
     (clean). Akan jenerikte 900-garble cozumu; her satir tek temiz okuma.
  2) GLM-OCR consensus (2. motor, OPSIYONEL): pipeline100 ciktisina ek olarak
     secili credit karelerini GLM-OCR ile okur; GLM-only satirlari EKLER (hicbir
     stitch satiri silinmez). MITAS_OCR_GLM_CONSENSUS=0 ile kapanir. Herhangi
     bir hata (ollama kapali, GLM yok, timeout) durumunda stitch korunur, REGRESYON YOK.
  3) Eski kare-kare OneOCR akisi (FALLBACK): zincir importu/DB/CLIP cokerse
     buna duser. Asla cokmez; kunye.txt MUTLAKA uretilir (bosken BOS bucket).

NOT: downscale YOK; kareler native cozunurlukte gelir. Fidelity: ne okunduysa
aynen yazilir, isim DROP edilmez (stitch KEEP-ALL). stdout'a tek satir JSON
sonuc basar; sema (status/kunye_path/kunye_line_count/bucket/engine) DEGISMEZ.
"""
from __future__ import annotations
import os, sys, json, glob, time, unicodedata, argparse, importlib.util, threading
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# pipeline100 zincirinin sabit mutlak yollari (DEGISMEZ kaynak dosyalar).
PY_OCR_DIR = Path(r"E:\MITAS\OCR-worktree\py")
CLIP_PROBE = PY_OCR_DIR / "20260601_clip_probe.py"
PIPELINE100 = PY_OCR_DIR / "20260601_pipeline100.py"
STITCH = PY_OCR_DIR / "20260601_stitch.py"
CLEAN = PY_OCR_DIR / "20260601_clean.py"
# GLM-consensus POC (2. motor): gerekli fonksiyonlar bu dosyaya INLINE edildi (asagida);
# 20260601_consensus_glm.py runtime'da YUKLENMIYOR — olu referans kaldirildi.

# GLM consensus sabitleri (consensus_glm'den BURAYA tasindi; import edilmeden kullanilabilir).
_GLM_OLLAMA = "http://localhost:11434/api/generate"
_GLM_MODEL = "glm-ocr:latest"
_GLM_PROMPT = (
    "Transcribe the film-credit text in this image EXACTLY, top to bottom, one entry per line. "
    "Use '?' for unreadable characters. Do NOT guess, do NOT add names not visible. "
    "Preserve Turkish letters: ç ğ ı İ ö ş ü. "
    "Return JSON: {\"lines\":[\"...\",\"...\"]}"
)
# Kare ornekleme ust siniri (cok kare varsa esit-aralikli at-at sec).
_GLM_MAX_FRAMES = 16
# Ollama retry/timeout ayarlari (1.6).
_GLM_TIMEOUT = 120          # saniye; tek tile basi HTTP timeout
_GLM_RETRY = 2              # maksimum deneme sayisi (ilk + 1 tekrar)
_GLM_RETRY_BACKOFF = 2.0    # saniye; denemeler arasi bekleme

# Kare-secim KALICILIK esikleri (Cagatay yontemi): gercek jenerik = KESINTISIZ uzun blok.
# Acilis sahne-ustu kredi + altyazi KISA-aralikli bloklar verir -> elenir.
CREDIT_MIN_RUN = 10   # CLIP-kredi blogu en az bu kadar kare KESINTISIZ surmeli (fps2 -> ~5 sn)
CREDIT_RUN_GAP = 3    # blok ici tolere edilen bosluk (CLIP tek kare kacirsa blok kopmasin)


def _load(name: str, path: Path):
    """importlib mutlak-yol modul yukleyici (credit_parse/_pipe_pdf _load kalibi)."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", (s or "").casefold()) if not unicodedata.combining(c)).strip()


# ── GLM-consensus yardimci fonksiyonlari (consensus_glm POC'undan) ───────────

def _glm_extract_lines(text: str) -> list[str]:
    """GLM/VLM ham metin ciktisini temiz satir listesine donustur.

    GLM bazen JSON string icine gercek satir sonlari (literal LF) gomuyor
    (RFC-7159 ihlali). Bunu yakala: JSON parse once ham, sonra LF-sanitize ile dene.
    Basarisizsa satir-satir fallback."""
    import re
    if not text:
        return []
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I).strip()
    m = re.search(r"\{.*\"lines\".*\}", text, flags=re.S)
    if m:
        blob = m.group(0)
        # 1. Direkt parse dene (duzgun JSON).
        for attempt in (blob, re.sub(r'\n', r'\\n', blob)):
            try:
                obj = json.loads(attempt)
                if isinstance(obj.get("lines"), list):
                    # lines icinde gercek \n olabilir -> her birini satirlara bol.
                    out: list[str] = []
                    for entry in obj["lines"]:
                        for part in str(entry).splitlines():
                            part = part.strip()
                            if part:
                                out.append(part)
                    return out
            except Exception:
                pass
        # 2. JSON parse basarisiz; JSON blob icinden ciplak satir cek
        #    (GLM bazen { "lines": [ satir1\nsatir2 ] } formatinda dondurur).
        inner = re.sub(r'[{}\[\]"\']', " ", blob)
        candidate: list[str] = []
        for ln in inner.splitlines():
            t = ln.strip().strip("`").strip("-*•,:").strip()
            if not t or t.lower().startswith(("lines", "here", "sure", "json")):
                continue
            candidate.append(t)
        if candidate:
            return candidate
    # 3. JSON yok / eslesme yok -> satir-satir fallback.
    out2: list[str] = []
    for ln in text.splitlines():
        t = ln.strip().strip("`").strip("-*•").strip()
        if not t or t in ("{", "}", "[", "]"):
            continue
        if t.lower().startswith(("here", "sure", "```", "json")):
            continue
        if t.startswith('"') and t.endswith('",'):
            t = t[1:-2]
        out2.append(t)
    return out2


def _glm_read_img(img_bgr, tile: int = 1200, ov: int = 100, timeout: int = None) -> list[str]:
    """Bir cv2 BGR goruntusunu tile'layarak GLM-OCR ile okur; fold-dedup satir listesi dondurur.
    Herhangi bir network/encode hatasi susturulur (cagiran try/except ile yakalamali).

    1.6: _ollama.ollama_chat wrapper uzerinden (retry+timeout merkezi). Her tile icin
    _GLM_RETRY deneme + _GLM_TIMEOUT HTTP timeout uygulanir.
    Tum denemeler tukenir/HTTP hatasi -> tile atlanir (diger tile'lar devam eder).
    Cagiran tarafta butun tile'lar basar -> OllamaError yukselir: status="failed" yoluna duser."""
    import base64
    from _ollama import ollama_chat
    _timeout = _GLM_TIMEOUT if timeout is None else timeout
    try:
        import numpy as np
        import cv2
    except ImportError:
        return []

    H = img_bgr.shape[0]
    seen: dict[str, str] = {}
    order: list[str] = []
    step = tile - ov
    y = 0
    _any_ollama_err = False
    while y < H:
        tile_img = img_bgr[y: min(y + tile, H), :]
        if tile_img.shape[0] < 20:
            break
        ok, buf = cv2.imencode(".png", tile_img)
        if ok:
            b64 = base64.b64encode(buf.tobytes()).decode()
            host = _GLM_OLLAMA.rsplit("/api/", 1)[0]
            raw_response = ollama_chat(
                model=_GLM_MODEL,
                prompt=_GLM_PROMPT,
                images=[b64],
                timeout=_timeout,
                retries=_GLM_RETRY,
                host=host,
                think=False,
                keep_alive="10m",
                options={"temperature": 0},
            )
            if raw_response is not None:
                for ln in _glm_extract_lines(raw_response.get("response", "")):
                    fk = fold(ln)
                    if fk and fk not in seen:
                        seen[fk] = ln
                        order.append(ln)
            else:
                # ollama_chat None dondu: tum denemeler tukendi, merkezi hataya rapor et.
                _any_ollama_err = True
                print(
                    f"[glm-consensus] tile y={y} ollama basarisiz "
                    f"({_GLM_RETRY} deneme): ollama_chat None dondu",
                    file=sys.stderr,
                )
        y += step

    if _any_ollama_err and not order:
        # Hicbir tile basarili olmadi -> cagiran "failed" yoluna dusmeli.
        raise RuntimeError(
            f"ollama_unreachable_or_timeout: tum tile'lar basarisiz "
            f"(timeout={_timeout}s, retry={_GLM_RETRY})"
        )
    return order


def _glm_fuzzy_in(f: str, fset_list: list[str]) -> bool:
    """f ile fset_list icindeki herhangi bir string arasinda >= 0.85 benzerlik var mi?"""
    import difflib
    return any(difflib.SequenceMatcher(None, f, g).ratio() >= 0.85 for g in fset_list)


def _glm_imread(path: str):
    """Turkce-yol guvenli cv2 imread (numpy frombuffer ile)."""
    try:
        import numpy as np
        import cv2
        return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None


def alpha_ratio(s: str) -> float:
    nonsp = [c for c in s if not c.isspace()]
    if not nonsp:
        return 0.0
    return sum(c.isalpha() for c in nonsp) / len(nonsp)


def is_prose(s: str) -> bool:
    w = s.split()
    return len(w) >= 7 or s.count(",") >= 2


def is_noise(s: str) -> bool:
    t = s.strip()
    if len(t) < 2:
        return True
    if not any(c.isalpha() for c in t):  # tum rakam/noktalama
        return True
    if is_prose(t):  # tesekkur bloklari / cumleler
        return True
    return False


def _glm_garble(t: str) -> bool:
    """VLM-tarzi 'cop okuma' / garble mi? (glm_only icin EK guvenlik suzgeci).

    cl.classify isim-bicimine TOLERANSLI (OneOCR nadiren saf-cop uretir diye
    guvenir); ama GLM/VLM makul-gorunen rastgele token dizisi uydurabiliyor
    ("ASTTIUK MEE xq9 zzkq"). Gercek kunye isim/rol satirlarini ELEMEDEN bu tur
    gurultuyu yakalayacak DAR sinyaller:
      - harf+rakam KARISIK token (xq9, a1b)  -> gercek isimde olmaz
      - satirda hic harf yok / cogunluk harf-disi (alpha_ratio dusuk)
      - kisa, sesli-harfsiz harf-yiginlari cogunlukta (zzkq, xq) = telaffuz-disi
    Tutucu: supheliyse garble DEME (False) — eleme sadece net cop icin.
    """
    import re
    t = (t or "").strip()
    if not t:
        return True
    if alpha_ratio(t) < 0.55:        # harf-disi agirlikli
        return True
    toks = [w for w in re.split(r"\s+", t) if w]
    alpha_toks = [w for w in toks if any(c.isalpha() for c in w)]
    if not alpha_toks:
        return True
    # harf+rakam karisik token (gercek isim/rolde gorulmez) = cop sinyali
    for w in alpha_toks:
        if any(c.isalpha() for c in w) and any(c.isdigit() for c in w):
            return True
    # sesli-harfsiz, >=3 harfli token-yigini orani (zzkq/xq tipi telaffuz-disi)
    vowels = set("aeiouAEIOUâîûéüöıçşğAEIOUÂÎÛÉÜÖİÇŞĞ")
    def _voweless(w):
        letters = [c for c in w if c.isalpha()]
        return len(letters) >= 3 and not any(c in vowels for c in letters)
    if alpha_toks and sum(_voweless(w) for w in alpha_toks) / len(alpha_toks) >= 0.5:
        return True
    return False


def _glm_only_keep(line: str, classify_fn=None) -> bool:
    """GLM-only bir satir kunyeye GIRMELI mi? (B-2 fix: glm_only kalite-filtresi)

    GLM'in eklediği (stitch'te olmayan) satirlar HALUSINASYON/COP olabilir
    (rastgele harf dizisi, prose cumle, salt rakam, dağıtıcı/legal artigi).
    Kural: "okunamadi > yanlis oku" — sadece isim/rol gorunumlu GERCEK kunye
    satiri gecsin.

    IKI kademeli (belt-and-suspenders), HER IKISI de gecmeli:
      1) BIRINCIL = stitch tarafiyla AYNI proje filtresi: clean.classify(t).
         clean.clean() her satiri classify ile kovaliyor ve YALNIZ 'credit'
         bucket'i kunyeye aliyor (logo/legal/sentence/junk/company/frag ELENIR).
         Ayni esigi glm_only'ye uygulariz -> davranis stitch ile birebir tutarli.
      2) EK garble suzgeci (_glm_garble): classify isim-bicimine toleransli, ama
         GLM rastgele-token uydurabilir; net cop'u burada yakalariz.
    classify_fn None ise (proje classify yuklenemedi) VEYA cagri patlarsa:
    birincil yerine bu dosyadaki minimal guvenli filtreye duser; satir
    filtresiz ASLA gecmez.
    """
    t = (line or "").strip()
    if not t:
        return False
    if classify_fn is not None:
        try:
            if classify_fn(t) != "credit":   # proje filtresi: credit degilse at
                return False
            return not _glm_garble(t)        # credit gorunse de net-cop ise at
        except Exception:  # noqa: BLE001 - classify patlarsa minimal filtreye dus
            pass
    # Minimal guvenli fallback (proje classify'i yoksa): gurultu/prose/garble ele.
    if is_noise(t):
        return False
    if len(t.split()) < 2:  # tek-kelime satir kredi olamaz (isimler >=2 kelime)
        return False
    if _glm_garble(t):
        return False
    return True


def build_engine():
    """OneOCR motorunu kur; basarisizsa (None, hata)."""
    try:
        import oneocr  # type: ignore
        from PIL import Image  # noqa: F401
        eng = oneocr.OcrEngine()
        return eng, "oneocr", None
    except Exception as exc:  # noqa: BLE001
        return None, "yok", f"{type(exc).__name__}: {exc}"


def ocr_frame(eng, path: Path) -> list[str]:
    from PIL import Image
    res = eng.recognize_pil(Image.open(str(path)))
    out: list[str] = []
    for ln in (res.get("lines") or []):
        t = (ln.get("text") if isinstance(ln, dict) else str(ln)).strip()
        if t:
            out.append(t)
    if not out:
        txt = (res.get("text") or "")
        out = [x.strip() for x in txt.splitlines() if x.strip()]
    return out


# ── ESKI kare-kare OneOCR akisi (FALLBACK) ──────────────────────────────────
def run_oneocr_fallback(frames: list[Path], started: float, profile: str) -> dict:
    """Zincir/CLIP/DB yoksa: her kareyi ayri OneOCR oku, fold-dedup, gurultu ele.
    Mevcut (eski) davranis aynen korunur; engine alani 'oneocr-fallback'."""
    eng, engine_name, eng_err = build_engine()
    if engine_name == "oneocr":
        engine_name = "oneocr-fallback"

    seen: dict[str, str] = {}
    order: list[str] = []
    raw_count = 0
    read_err = 0
    if eng is not None:
        for fp_ in frames:
            try:
                for ln in ocr_frame(eng, fp_):
                    raw_count += 1
                    fk = fold(ln)
                    if fk and fk not in seen:
                        seen[fk] = ln
                        order.append(ln)
            except Exception:  # noqa: BLE001 - tek kare hatasi bloklamaz
                read_err += 1

    # gurultu/prose ele
    kunye = [s for s in order if not is_noise(s)]
    garble = [s for s in kunye if alpha_ratio(s) < 0.55]
    gf = (len(garble) / len(kunye)) if kunye else 0.0

    if eng is None:
        bucket = "MOTOR_YOK"
    elif not kunye:
        bucket = "BOS"
    elif gf > 0.5:
        bucket = "ZOR"
    elif len(kunye) < 3 or gf > 0.30 or len(kunye) > 300:
        # >300 satir = akan scroll'da kare-basi OCR fazla-uretimi (bloat) -> incele.
        bucket = "GOZDEN_GECIR"
    else:
        bucket = "GUVENILIR"

    return {
        "lines": kunye,
        "engine": engine_name,
        "engine_error": eng_err,
        "frame_read_errors": read_err,
        "raw_line_count": raw_count,
        "garble_frac": round(gf, 4),
        "bucket": bucket,
        # 1.7 telemetri: oneocr-fallback yolunda GLM hic denenmez
        "glm_attempted": False,
        "glm_status": "skipped",
        "glm_skip_reason": "oneocr_fallback",
    }


# ── YENI scroll-aware akis (pipeline100 zinciri) ────────────────────────────
def run_pipeline100(frames: list[Path], started: float, profile: str, ocr_out: "Path | None" = None) -> dict | None:
    """CLIP bekci -> konumlu OneOCR -> OCR-uzayinda dik -> temizle.
    Her adim try/except; herhangi biri coker (CLIP/duckdb/oneocr yok) -> None
    dondurur ve cagiran eski OneOCR akisina graceful duser.

    Donen dict basariliysa: lines (temiz kunye), engine='pipeline100', bucket,
    + tani alanlari. None ise import/CLIP cokmus demektir."""
    try:
        # Zincir modullerini yukle (pipeline100 orkestratoru cp/cl/sl/stx'i
        # kendi icinde zaten yukler; ondan re-export'lari aliriz).
        pl = _load("pl_pipeline100", PIPELINE100)
        cp = pl.cp          # clip_probe (load_clip / score_frames / med_smooth)
        cl = pl.cl          # clean (clean / tr_upper)
        stx = pl.stx        # stitch (stitch_kunye)
        cr = pl.cr          # credit_read_v1 (DB / kb_exact_batch)
        fp = pl.fp          # full_pipeline (rd: Turkce-yol guvenli imread)
        read_pos = pl.read_pos
        # runs_of pipeline100'de TOP-LEVEL degil (compose_hybrid icinde inline);
        # dogru kaynak stitch (stx.runs_of) -> idx listesini dogrudan run'lara boler.
        runs_of = stx.runs_of
        tr_upper = pl.tr_upper
    except Exception as exc:  # noqa: BLE001 - import zinciri cokerse fallback
        print(f"[pipeline100] import basarisiz, fallback: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None

    frame_paths = [str(p) for p in frames]

    # a) CLIP bekci: her kareye kredi-olasiligi -> esik>=0.5 kareler.
    #    CLIP yuklemesi pahali/coker -> bekciyi atla, TUM kareleri kullan.
    THR = 0.5
    clip_ok = True
    try:
        model, preprocess, tok = cp.load_clip()
        ls = model.logit_scale.exp().item()
        cred = cp.class_embed(model, tok, cp.CREDIT_PROMPTS)
        scene = cp.class_embed(model, tok, cp.SCENE_PROMPTS)
        ps = cp.med_smooth(cp.score_frames(model, preprocess, frame_paths, cred, scene, ls), 5)
        # KALICILIK (Cagatay): dağınık tek-tük yuksek kare DEGIL, KESINTISIZ uzun blok = jenerik.
        # Acilis sahne-ustu kredi+altyazi kisa-aralikli bloklar verir (elenir); gercek jenerik
        # (acilista uzun VEYA kapanista surekli) >=CREDIT_MIN_RUN kare suren blok = alinir.
        _runs = cp.runs_of(ps >= THR, gap=CREDIT_RUN_GAP, minlen=CREDIT_MIN_RUN)
        idx = [i for a, b in _runs for i in range(int(a), int(b) + 1)]
        if not idx:  # hicbir uzun blok yok (kisa-jenerikli/dip-kalite) -> eski davranisa dus, kapsama kaybetme
            idx = [i for i in range(len(ps)) if ps[i] >= THR]
    except Exception as exc:  # noqa: BLE001 - CLIP coker -> tum kareler
        print(f"[pipeline100] CLIP bekci atlandi: {type(exc).__name__}: {exc}", file=sys.stderr)
        clip_ok = False
        idx = list(range(len(frame_paths)))

    if not idx:
        # CLIP "hicbir kare kredi degil" dedi -> bos kunye, footage demek.
        return {
            "lines": [], "engine": "pipeline100", "engine_error": None,
            "frame_read_errors": 0, "raw_line_count": 0, "garble_frac": 0.0,
            "bucket": "BOS", "clip_used": clip_ok, "credit_frames": 0,
            "diegetik_frac": 0.0, "low_conf_frac": 0.0,
            # 1.7 telemetri: CLIP hicbir kare secmedi -> GLM denenmedi
            "glm_attempted": False,
            "glm_status": "skipped",
            "glm_skip_reason": "no_frames",
        }

    # b) Konumlu oku: secili karelerde read_pos -> ocr_pos[i] = [(fold,raw,y0,y1)]
    try:
        imgs = {i: fp.rd(frame_paths[i]) for i in idx}
        ocr_pos = {i: read_pos(imgs[i]) for i in idx}
    except Exception as exc:  # noqa: BLE001 - OneOCR/okuma coker -> fallback
        print(f"[pipeline100] konumlu okuma basarisiz, fallback: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None
    raw_count = sum(len(ocr_pos[i]) for i in idx)

    # c) Dik: runs_of(idx) -> stitch_kunye -> placed_raw (her satir tek temiz okuma)
    try:
        runs = runs_of(idx)
        placed_raw, low_conf, medconf = stx.stitch_kunye(runs, ocr_pos)
    except Exception as exc:  # noqa: BLE001
        print(f"[pipeline100] stitch basarisiz, fallback: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None

    # d) Temizle: DB (duckdb) baglanmaya calis; yoksa con=None ile kb bos calisir.
    con = None
    db_ok = False
    try:
        import duckdb  # type: ignore
        con = duckdb.connect(cr.DB, read_only=True)
        db_ok = True
    except Exception as exc:  # noqa: BLE001 - DB yok/kilitli -> KB'siz devam
        print(f"[pipeline100] DB baglanamadi, KB'siz devam: {type(exc).__name__}: {exc}", file=sys.stderr)
        con = None
    try:
        # asr_fold="" -> ASR-diyalog elemesi devre disi (zarar yok). con=None ise
        # clean icinde kb_exact_batch hic cagrilmaz (folds varsa cagrilir) -> guvenli.
        merged, buckets, asr_drop, dieg = cl.clean(placed_raw, con, "")
    except Exception as exc:  # noqa: BLE001 - clean coker -> ham placed_raw'a duser
        print(f"[pipeline100] clean basarisiz, ham stitch kullanildi: {type(exc).__name__}: {exc}", file=sys.stderr)
        merged = [(t, "raw", 1) for t in placed_raw]
        buckets, dieg = {}, 0.0
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:  # noqa: BLE001
                pass

    # e) kunye satirlari (mevcut formatla ayni: satir basina bir metin, # yok).
    #    clean Turkce-BUYUK yazimi tr_upper ile verir (pipeline100 ile ayni cikti).
    lines = [tr_upper(t) for t, _how, _votes in merged]

    # ── e.1) MASTER-PNG blogu: compose_hybrid -> master.png + additive OCR ────
    # Hedef mimari: lines hazirlandiktan sonra, return'den once.
    # TUM blok tek try/except: herhangi bir hata -> lines AYNEN korunur (REGRESYON YOK).
    # Cikti dict'ine master_png + master_lines_count alanlari eklenir.
    _master_png: str | None = None
    _master_lines_count: int = 0
    _master_error: str | None = None
    # BAYRAK: MITAS_MASTER_PNG (default KAPALI). Tesisat hazir+fail-safe ama uctan-uca
    # kunye kalitesi (LLM rol-eval + gercek-zemin) HENUZ olculmedi -> canliyi riske atma.
    # GPU bosalip 10-film altin sette olculunce default-acik yapilir.
    _master_on = os.environ.get("MITAS_MASTER_PNG", "").strip().lower() in ("1", "true", "on", "yes")
    if _master_on and ocr_out is not None and idx:
        try:
            # compose_hybrid -> (master_arr, stitch_text) — pipeline100 kanonik
            _compose = pl.compose_hybrid  # type: ignore[attr-defined]
            _read_pos_fn = pl.read_pos    # type: ignore[attr-defined]
            _master_arr, _stitch_text = _compose(frame_paths, idx, imgs, ocr_pos)
            if _master_arr is not None:
                _mpath = Path(ocr_out) / "master.png"
                fp.wr(_mpath, _master_arr)           # Turkce-path guvenli yazmak icin fp.wr
                _master_png = str(_mpath)
                # master PNG uzerinde OneOCR koş (dikey tile dongüsü)
                _master_ocr_res = _read_pos_fn(_master_arr)
                # additive: stitch fold-seti olustur; master-only satirlari ekle
                _stitch_folds = {cl.fold(l) for l in lines}
                _master_only: list[str] = []
                _master_seen: set[str] = set()
                for _mln in _master_ocr_res:
                    _fk = _mln[0]  # fold edilmis metin (tuple[0])
                    if not _fk:
                        continue
                    if _fk in _stitch_folds or _fk in _master_seen:
                        continue
                    _master_seen.add(_fk)
                    _master_only.append(_mln[1])  # raw metin
                # kalite filtresi: stitch ile ayni cl.classify esigi (GLM kalibina uygun)
                _master_only_clean = [x for x in _master_only if _glm_only_keep(x, cl.classify)]
                _master_only_upper = [tr_upper(x) for x in _master_only_clean]
                lines = lines + _master_only_upper   # stitch satirlari oncelikli; additive
                _master_lines_count = len(_master_only_upper)
                print(
                    f"[master-png] yazildi: {_mpath} | master-only eklendi: {_master_lines_count}",
                    file=sys.stderr,
                )
            else:
                print("[master-png] compose_hybrid None dondurdu (footage/bos?)", file=sys.stderr)
        except Exception as _exc:  # noqa: BLE001
            _master_error = f"{type(_exc).__name__}: {_exc}"
            print(f"[master-png] ATLANDI (lines korunuyor): {_master_error}", file=sys.stderr)
    # ── /MASTER-PNG blogu ─────────────────────────────────────────────────────

    # ── f) GLM-OCR consensus (2. motor, OPSIYONEL, ADDITIVE) ─────────────────
    # Sadece: lines bos degilse + env switch kapali degilse + idx var.
    # TUM blok try/except: herhangi bir hata -> lines AYNEN korunur (REGRESYON YOK).
    glm_used = False
    glm_lines_count = 0
    agree_count = 0
    glm_only_count = 0
    glm_only_filtered_count = 0
    final_engine = "pipeline100"

    # 1.7 telemetri alanlari: HER yolda yazilir (alan-YOK=eski kod, alan-VAR=neden acik).
    glm_attempted: bool = False
    glm_status: str = "skipped"         # "succeeded"|"skipped"|"failed"|"disabled"
    glm_skip_reason: str = ""

    # GLM ikinci-motor: env=0/false/no/"" KAPALI, diger durumlarda AÇIK (default "1").
    _glm_env = os.environ.get("MITAS_OCR_GLM_CONSENSUS", "1").strip().lower()
    _glm_enabled = _glm_env not in ("0", "false", "no", "off", "")
    if not _glm_enabled:
        glm_status = "disabled"
        glm_skip_reason = "env_disabled"
    elif not idx:
        glm_status = "skipped"
        glm_skip_reason = "no_frames"
    elif not lines:
        glm_status = "skipped"
        glm_skip_reason = "empty_stitch"

    if lines and idx and _glm_enabled:
        try:
            # Esit-aralikli ornekleme: en fazla _GLM_MAX_FRAMES kare sec.
            sample_idx = idx
            if len(idx) > _GLM_MAX_FRAMES:
                step_s = len(idx) / _GLM_MAX_FRAMES
                sample_idx = [idx[int(i * step_s)] for i in range(_GLM_MAX_FRAMES)]

            # Her secili kareyi GLM ile oku; fold-dedup ile GLM satir listesi olustur.
            glm_seen: dict[str, str] = {}
            glm_order: list[str] = []
            glm_t0 = time.perf_counter()
            for si in sample_idx:
                frame_path = frame_paths[si]
                img = _glm_imread(frame_path)
                if img is None:
                    continue
                for ln in _glm_read_img(img):
                    fk = fold(ln)
                    if fk and fk not in glm_seen:
                        glm_seen[fk] = ln
                        glm_order.append(ln)
            glm_elapsed = round(time.perf_counter() - glm_t0, 2)
            print(
                f"[glm-consensus] {len(sample_idx)} kare, {len(glm_order)} satir, "
                f"{glm_elapsed}s",
                file=sys.stderr,
            )

            # Uzlastir: fold karsilastirmasi + fuzzy match.
            fg = [fold(x) for x in glm_order]  # GLM fold listesi
            fl = [fold(x) for x in lines]       # stitch fold listesi
            fl_set = set(fl)

            agree_count = sum(
                1 for x in glm_order
                if fold(x) in fl_set or _glm_fuzzy_in(fold(x), fl)
            )

            # GLM-only: GLM'de olup stitch'te OLMAYAN (fold eslesmiyor + fuzzy yok).
            glm_only_raw: list[str] = []
            glm_only_seen: set[str] = set()
            for x in glm_order:
                fk = fold(x)
                if fk in fl_set or _glm_fuzzy_in(fk, fl):
                    continue  # stitch zaten biliyor
                if fk in glm_only_seen:
                    continue  # kendi icinde dedup
                glm_only_seen.add(fk)
                glm_only_raw.append(x)

            # Additive: stitch satirlari KORUNUR + GLM-only EKLENIR (tr_upper ile).
            # Ham JSON blob artiklari ({... ile baslayan satirlar) dogrudan atla.
            glm_only_nojson = [x for x in glm_only_raw if not x.strip().startswith("{")]

            # B-2 FIX: glm_only satirlarini stitch ile AYNI kalite-filtresinden gecir.
            # stitch satirlari cl.clean() -> classify ile 'credit' suzgecinden geciyor;
            # glm_only ise eskiden YALNIZ tr_upper'dan gecip dogrudan ekleniyordu ->
            # GLM halusinasyonu/cop kunyeye sizardi. Ayni cl.classify esigini uygula:
            # sadece 'credit' gorunumlu satir kalsin, gurultu/prose/garble/legal ELENSIN.
            glm_only_clean = [x for x in glm_only_nojson if _glm_only_keep(x, cl.classify)]
            glm_only_filtered_count = len(glm_only_nojson) - len(glm_only_clean)
            if glm_only_filtered_count:
                print(
                    f"[glm-consensus] glm_only kalite-filtresi: "
                    f"{glm_only_filtered_count}/{len(glm_only_nojson)} satir elendi (cop/garble/prose)",
                    file=sys.stderr,
                )

            glm_only_upper = [tr_upper(x) for x in glm_only_clean]
            lines = lines + glm_only_upper  # stitch satirlari oncelikli

            glm_used = True
            glm_lines_count = len(glm_order)
            glm_only_count = len(glm_only_clean)
            final_engine = "pipeline100+glm"
            # 1.7 telemetri — basarili yol
            glm_attempted = True
            glm_status = "succeeded"
            glm_skip_reason = ""

        except Exception as exc:  # noqa: BLE001 — her kosulda stitch korunur
            # 1.7 telemetri — hata yolu: denemis ama basarisiz.
            glm_attempted = True
            _is_ollama_err = "ollama" in str(exc).lower() or "timeout" in str(exc).lower() or "unreachable" in str(exc).lower()
            glm_status = "failed"
            glm_skip_reason = "ollama_unreachable_or_timeout" if _is_ollama_err else f"exception:{type(exc).__name__}"
            print(
                f"[glm-consensus] ATLANDI (stitch korunuyor): {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            # glm_used=False, final_engine="pipeline100" — zaten set edilmedi.
    # ── /GLM consensus ────────────────────────────────────────────────────────

    # bucket: yeni sinyallerle, mevcut degerler korunarak.
    low_frac = (len(low_conf) / len(placed_raw)) if placed_raw else 0.0
    if not lines:
        bucket = "BOS"
    elif dieg > 0.50 or low_frac > 0.5:
        # cumle/diegetik orani yuksek YA DA dusuk-guven cogunluk -> zor okuma.
        bucket = "ZOR"
    elif len(lines) < 3 or dieg > 0.30 or low_frac > 0.30:
        bucket = "GOZDEN_GECIR"
    else:
        bucket = "GUVENILIR"

    return {
        "lines": lines,
        "engine": final_engine,
        "engine_error": None,
        "frame_read_errors": 0,
        "raw_line_count": raw_count,
        "garble_frac": round(low_frac, 4),
        "bucket": bucket,
        "clip_used": clip_ok,
        "db_used": db_ok,
        "credit_frames": len(idx),
        "stitched_lines": len(placed_raw),
        "low_conf_frac": round(low_frac, 4),
        "diegetik_frac": round(dieg, 4),
        # GLM-consensus tani alanlari
        "glm_used": glm_used,
        "glm_lines": glm_lines_count,
        "agree_count": agree_count,
        "glm_only_count": glm_only_count,
        "glm_only_filtered_count": glm_only_filtered_count,
        # 1.7 telemetri: HER yolda yazilir (alan-YOK=eski kod)
        "glm_attempted": glm_attempted,
        "glm_status": glm_status,
        "glm_skip_reason": glm_skip_reason,
        # master-PNG alanlari (e.1 blogu)
        "master_png": _master_png,
        "master_lines_count": _master_lines_count,
        "master_error": _master_error,
        # HAM cikti (clean-oncesi): main bunlari diske doker -> kunye DEGIL ham yazi
        "placed_raw": list(placed_raw),                                  # stitch sonrasi, clean ONCESI
        "raw_reads": [tup[1] for i in sorted(idx) for tup in ocr_pos[i]],  # her karenin her okumasi (en ham)
    }


def _run_paddle_sidecar(frames: list[Path], out: Path) -> None:
    """PaddleOCR-GPU side-channel (paralel thread). FAIL-SAFE: hata = sessiz, paddle_kunye.txt yazilmaz.

    OneOCR ile ayni anda kosar; sonuc `out/paddle_kunye.txt`'ye kaydedilir.
    Zaman icinde OneOCR'in tokezdigi yerlerde karsilastirma icin kullanilir.
    head+tail ornekleme: ilk yarim + ikinci yarim (reader500.py basson ile ayni).
    """
    try:
        from paddleocr import PaddleOCR  # type: ignore
        paddle = PaddleOCR(
            lang="en", device="gpu",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        k = 16
        n = len(frames)
        if n <= k:
            sample = list(frames)
        else:
            h = k // 2
            sample = list(frames[:h]) + list(frames[max(h, n - k + h):])
        seen: dict[str, str] = {}
        lines: list[str] = []
        for fp in sample:
            try:
                result = paddle.predict(str(fp))
                # BUG-FIX: predict() LISTE doner (sayfa basina dict), dict DEGIL.
                # Eski kod result.get() cagiriyordu -> 'list' has no attribute 'get' -> her kare
                # AttributeError -> sessiz yutuluyor -> paddle hep BOS uretiyordu (2026-06-14 dogrulandi).
                for page in (result or []):
                    recs = page.get("rec_texts") if hasattr(page, "get") else None
                    for rec in (recs or []):
                        rec = (rec or "").strip()
                        if not rec:
                            continue
                        fk = fold(rec)
                        if fk and fk not in seen:
                            seen[fk] = rec
                            lines.append(rec)
            except Exception:  # noqa: BLE001 — tek kare hatasi bloklamaz
                pass
        paddle_path = out / "paddle_kunye.txt"
        paddle_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        print(f"[paddle] {len(lines)} satir -> {paddle_path}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — PaddleOCR yok / GPU hatasi -> sessiz atla
        print(f"[paddle] atlandi: {type(exc).__name__}: {exc}", file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", nargs="+", required=True, help="frame dizin(ler)i")
    ap.add_argument("--out", required=True)
    ap.add_argument("--profile", default="film")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    frames: list[Path] = []
    for d in args.frames:
        frames += sorted(Path(p) for p in glob.glob(str(Path(d) / "*.png")))

    # PaddleOCR side-channel: OneOCR ile paralel kostur (daemon thread).
    _paddle_thread: threading.Thread | None = None
    if frames:
        _paddle_thread = threading.Thread(
            target=_run_paddle_sidecar, args=(frames, out), daemon=True, name="paddle-sidecar"
        )
        _paddle_thread.start()

    # Once scroll-aware pipeline100 zincirini dene; coker/None -> eski OneOCR.
    res = None
    if frames:
        try:
            res = run_pipeline100(frames, started, args.profile, ocr_out=out)
        except Exception as exc:  # noqa: BLE001 - hicbir kosulda cokme
            print(f"[pipeline100] beklenmeyen hata, fallback: {type(exc).__name__}: {exc}", file=sys.stderr)
            res = None
    if res is None:
        res = run_oneocr_fallback(frames, started, args.profile)

    kunye = res["lines"]
    kunye_path = out / "kunye.txt"
    kunye_path.write_text("\n".join(kunye) + ("\n" if kunye else ""), encoding="utf-8")

    # HAM yazi dokumu (kunye DEGIL): clean-oncesi stitch + en-ham her-kare okuma.
    if res.get("placed_raw"):
        (out / "ocr_ham.txt").write_text("\n".join(res["placed_raw"]) + "\n", encoding="utf-8")
    if res.get("raw_reads"):
        (out / "ocr_raw_all.txt").write_text("\n".join(res["raw_reads"]) + "\n", encoding="utf-8")

    summary = {
        "engine": res["engine"],
        "engine_error": res.get("engine_error"),
        "frame_count": len(frames),
        "frame_read_errors": res.get("frame_read_errors", 0),
        "raw_line_count": res.get("raw_line_count", 0),
        "kunye_line_count": len(kunye),
        "garble_frac": res.get("garble_frac", 0.0),
        "bucket": res["bucket"],
        "profile": args.profile,
        "runtime_sec": round(time.perf_counter() - started, 3),
    }
    # pipeline100'e ozgu tani alanlari (varsa) ekle — sema icin zorunlu degil.
    for k in ("clip_used", "db_used", "credit_frames", "stitched_lines", "low_conf_frac", "diegetik_frac",
              "glm_used", "glm_lines", "agree_count", "glm_only_count", "glm_only_filtered_count"):
        if k in res:
            summary[k] = res[k]
    # 1.7 telemetri: HER yolda sabit yazilir (alan-YOK=eski kod, alan-VAR=neden acik).
    summary["glm_attempted"] = res.get("glm_attempted", False)
    summary["glm_status"] = res.get("glm_status", "skipped")
    summary["glm_skip_reason"] = res.get("glm_skip_reason", "")
    # master-PNG telemetrisi
    summary["master_png"] = res.get("master_png")
    summary["master_lines_count"] = res.get("master_lines_count", 0)
    summary["master_error"] = res.get("master_error")
    summary_path = out / "ocr_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # Paddle thread'ini bekle (en fazla 180s; daemon oldugu icin process bitse de olur).
    if _paddle_thread is not None:
        _paddle_thread.join(timeout=180)

    paddle_lines = 0
    _ppath = out / "paddle_kunye.txt"
    if _ppath.exists():
        try:
            paddle_lines = sum(1 for l in _ppath.read_text(encoding="utf-8").splitlines() if l.strip())
        except Exception:  # noqa: BLE001
            pass

    status = "done" if (res["bucket"] not in ("MOTOR_YOK",) and kunye) else "partial"
    print(json.dumps({
        "status": status,
        "kunye_path": str(kunye_path),
        "summary_path": str(summary_path),
        "kunye_line_count": len(kunye),
        "paddle_line_count": paddle_lines,
        "bucket": res["bucket"],
        "engine": res["engine"],
        "runtime_sec": summary["runtime_sec"],
        "error": res.get("engine_error"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
