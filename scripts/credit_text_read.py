#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""credit_text_read.py — OneOCR+GLM HAM METNİNDEN rol-eşleme (VLM-okuma YERİNE).

KURAL (Çağatay 2026-06-08): Okuma OneOCR+GLM ile yapılır; isimler OCR METNİNDEN gelir.
LLM yalnız ROL-EŞLEME yapar (pikselden OKUMAZ) → halüsinasyon imkânsız: her çıktı ismi
OCR metninde token olarak bulunmazsa ATILIR (anti-halüsinasyon kalkanı).

read_credits_from_text(lines, title, model) -> {"yonetmen":[...],"yapimci":[...],"cast":[...],"guven":...,"ham":...}

Akış: ham OCR satırları → LLM (rol-eşleme JSON, isim-metinden) → KALKAN (token-doğrulama)
      → GARBLE KAPISI (looks_garble) → KB ROL-FİLTRESİ (crew-oyuncu ayırt) → çıktı.

2026-06-08 F1/F2/F3 düzeltmeleri:
  F1 — ENSEMBLE: read_credits_auto artık tüm zinciri koşar, ilk-doluda durmaz;
       credit_video_read.fuse() mantığıyla yönetmen mutabakatı/KB-seçimi.
  F2 — KB ROL-FİLTRESİ: credit_video_read.KB ile crew→cast sızıntısını keser.
  F3 — GARBLE KAPISI: outputs/garble_audit.looks_garble ile garble isimler atılır.
"""
from __future__ import annotations
import json
import os
import re
import sys
import unicodedata
import urllib.request

OLLAMA = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("MITAS_CREDIT_TEXT_MODEL", "gemma-4-31b-it-qat-vision:latest")
# FIX 3 (2026-06-22): cast garble-gate'i 8-cap'ten ÖNCE çalıştır — garble'lar 8-slot
# bütçesini doldurup gerçek adları (geç-sırada görünen seslendiren vb.) atmasın.
# Monotonik-güvenli (gate=alt-dizi; non-regresyon audit PASS). AKTİF (default ON).
# MITAS_EXTRACT_GATE_BEFORE_CAP=0 ile eski sıra (cap-sonra-filtre) geri gelir (kill-switch).
_GATE_BEFORE_CAP = os.environ.get("MITAS_EXTRACT_GATE_BEFORE_CAP", "1").strip().lower() in (
    "1", "true", "on", "yes")

# RENDER yanlış-pozitif kalkanı (2026-06-28): detect_script() oransızdır — tek latin-dışı
# karakter bile "latin değil" döndürür. TRT-logo OCR'ı '西' (CJK) / prop-tabela 'ا' (Arap)
# gibi tek-tük gürültü, tamamen Latin bir filmi (SUÇ MEVSİMİ, ŞERİF SHAUGNESSY) "latin-dışı
# kaynak" sanıp haksız KONTROL/RENDER'a yolluyordu. Gerçek latin-dışı jenerik yüksek-oranlıdır;
# gürültü <%2. Oranla ayır. MITAS_NONLATIN_MIN_RATIO=0 ile eski (oransız) davranış geri gelir.
_NONLATIN_MIN_RATIO = float(os.environ.get("MITAS_NONLATIN_MIN_RATIO", "0.02"))


def _nonlatin_ratio(s: str) -> float:
    """Metindeki latin-dışı harflerin TÜM harflere oranı (0..1). Rakam/noktalama sayılmaz."""
    alpha = [c for c in (s or "") if c.isalpha()]
    if not alpha:
        return 0.0
    nonlatin = 0
    for c in alpha:
        try:
            if "LATIN" not in unicodedata.name(c):
                nonlatin += 1
        except ValueError:
            continue
    return nonlatin / len(alpha)

_TR_FOLD = str.maketrans("ışğçöüİIÄ", "isgcouiia")


def _fold(s: str) -> str:
    s = (s or "").casefold().translate(_TR_FOLD)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s)


def _toks(s: str):
    return [t for t in _fold(s).split() if len(t) > 2]


_CREW_CONTEXT_KW = (
    "assistant art director", "art department", "art director", "set designer", "draftsman",
    "art department pa", "storyboard", "construction coordinator", "lead carpenter",
    "carpenter", "gimbal operator", "dolly grip", "key grip", "best boy", "gaffer",
    "production sound mixer", "boom operator", "sound mixer", "sound recordist",
    "camera", "assistant camera", "second unit camera", "director of photography",
    "cast editing assistant", "editing assistant", "extras casting", "casting assistant",
    "casting director", "unit production manager", "production coordinator",
    "production accountant", "assistant director", "modeler", "modelers", "animation",
    "animator", "supervisor", "operator", "buyer", "coordinator", "manager",
    "department", "assistant", "technician", "designer", "editor", "mixer",
    "performed by", "mixed by", "music", "song", "songs", "soundtrack",
    "visual effects", "courtesy of", "records", "licensing", "arrangement",
    # C5c genişletme — yapımcı/teşekkür/yabancı crew unvanları (2026-06-22)
    "producer", "producers", "yapimci", "yapımcı",
    "executive producer", "co producer", "associate producer",
    "line producer", "tesekkur", "teşekkür",
    "special thanks", "thanks to", "wrangler", "redaktion",
    "dialogue coach", "scenario", "scénario",
)
_CAST_CONTEXT_KW = (
    "starring", "co starring", "cast", "oyuncular", "oynayanlar",
)


def load_raw_context_for_ocr(ocr_path: str | os.PathLike | None) -> list[str]:
    """Load the raw frame OCR next to kunye.txt when available.

    kunye.txt is de-duplicated and may lose role adjacency. The raw files preserve enough
    neighborhood to tell "NAME near crew role" from a real cast block.
    """
    if not ocr_path:
        return []
    base = os.path.dirname(os.fspath(ocr_path))
    for fn in ("ocr_raw_all.txt", "ocr_ham.txt"):
        p = os.path.join(base, fn)
        try:
            if os.path.exists(p):
                lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
                if lines:
                    return lines
        except Exception:
            continue
    return []


def _read_ocr_sidecar_lines(base: str, filename: str) -> list[str]:
    p = os.path.join(base, filename)
    try:
        if os.path.exists(p):
            lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
            return [line for line in lines if str(line).strip()]
    except Exception:
        pass
    return []


def _compact_raw_lines_for_llm(lines: list[str], *, max_lines: int = 700) -> list[str]:
    """Keep raw OCR bounded for the LLM while preserving credit-role neighborhoods."""
    cleaned = [str(line).strip() for line in (lines or []) if str(line).strip()]
    if len(cleaned) <= max_lines:
        return cleaned

    hints = re.compile(
        r"\b(CAST|STARRING|IN ORDER OF APPEARANCE|DIRECTED BY|WRITTEN\s*&\s*DIRECTED|"
        r"PRODUCED BY|PRODUCER|YONETMEN|YÖNETMEN|YAPIMCI|OYUNCU|OYUNCULAR)\b",
        re.IGNORECASE,
    )
    keep: set[int] = set()
    for i, line in enumerate(cleaned):
        if hints.search(line):
            keep.update(range(max(0, i - 80), min(len(cleaned), i + 160)))

    if not keep:
        head = max_lines // 2
        tail = max_lines - head
        return cleaned[:head] + cleaned[-tail:]

    ordered = [cleaned[i] for i in sorted(keep)]
    if len(ordered) > max_lines:
        ordered = ordered[:max_lines]
    return ordered


def load_llm_lines_for_ocr(ocr_path: str | os.PathLike | None) -> tuple[list[str], str]:
    """Load the least-lossy OCR text that should be shown to the text model.

    `kunye.txt` is useful as a delivered/normalized artifact, but it can flatten
    credit cards such as `MAURA Sally Hawkins` into `MAURA SALLY HAWKINS`.
    The model should see the rawer OneOCR text first; deterministic cleanup runs
    after the model output.
    """
    if not ocr_path:
        return [], ""
    base = os.path.dirname(os.fspath(ocr_path))

    for filename in ("ocr_ham.txt", "ocr_raw_all.txt"):
        lines = _read_ocr_sidecar_lines(base, filename)
        if lines:
            lines = _compact_raw_lines_for_llm(lines, max_lines=500)  # 260→500: uzun/anahtar-kelimesiz jenerikte kadro-bloğu kaybını azalt (recall güvenliği)
            return lines, filename

    try:
        lines = open(ocr_path, encoding="utf-8", errors="ignore").read().splitlines()
        return [line for line in lines if str(line).strip()], os.path.basename(os.fspath(ocr_path))
    except Exception:
        return [], ""


def _name_hit_in_raw(name_fold: str, line_fold: str) -> bool:
    if not name_fold or not line_fold:
        return False
    if line_fold == name_fold:
        return True
    return bool(re.search(r"\b" + re.escape(name_fold) + r"\b", line_fold))


def _crew_context(window: str) -> bool:
    return any(k in window for k in _CREW_CONTEXT_KW)


def _cast_context(window: str) -> bool:
    return any(k in window for k in _CAST_CONTEXT_KW) and not _crew_context(window)


def filter_cast_by_raw_context(cast: list[str], raw_context_lines: list[str] | None) -> list[str]:
    """Drop cast candidates that only appear in raw OCR next to crew-role labels.

    This is a negative gate only: it never adds names. If crew-context sightings dominate
    and there is no explicit cast/starring context, the name is removed.
    """
    if not cast or not raw_context_lines:
        return cast or []
    folded = [_fold(x).strip() for x in raw_context_lines]
    out: list[str] = []
    for nm in cast:
        nf = _fold(nm).strip()
        hit_idxs = [i for i, line in enumerate(folded) if _name_hit_in_raw(nf, line)]
        if not hit_idxs:
            out.append(nm)
            continue
        crew_count = 0
        cast_seen = False
        for i in hit_idxs:
            win = " ".join(folded[max(0, i - 1): i + 1])
            if _cast_context(win):
                cast_seen = True
            if _crew_context(win):
                crew_count += 1
        if cast_seen or crew_count == 0 or (crew_count / len(hit_idxs)) < 0.60:
            out.append(nm)
    return out


# DUBLAJ markerları — HER ZAMAN uygula (dublaj-rolü ASLA film-yönetmeni değil, yüksek-isabet).
_DUB_MARKERS = ("seslendirme", "dublaj", "doblaje", "doublage", "synchron", "voice direct")
# YÖNETMEN-DIŞI diğer rol markerları — yalnız aday ŞÜPHELİYKEN (mutabakat-DIŞI) uygula. Temiz+mutabık
# yönetmene dokunma (3.GÖZ kanıtı: jenerik satır-sırası bozuk olabilir → agresifse gerçek yön'ü öldürür).
_NONFILM_MARKERS = (
    "yardimci", "assistant direct", "asst direct", "aiuto regista",     # asistan yönetmen
    "ayudante", "asistente", "assistente",                             # asistan (ES/IT/PT)
    "music direct", "muzik yon", "art direct", "casting direct", "technical direct",  # X-yönetmeni
    "director of photo", "director de foto", "directeur de la photo", "goruntu yon",
    "production assistant", "production manager", "asistentes de produc", "ayudante de direc",
    "yapim asistan", "yapim sorumlu", "yapim koordinator",             # yapım rolleri
)


def _drop_dubbing_directors(directors, raw_lines, high_consensus=False):
    """YÖNETMEN-DIŞI ROL DIŞLAMA (Çağatay 2026-06-20): ham OCR'da yönetmen adayının ±2 satır bağlamında
    YÖNETMEN-DIŞI rol etiketi (dublaj/asistan-yön/yapım-asistanı/X-yönetmeni...) varsa → DÜŞ (deterministik,
    LLM-bağımsız). ESRA TANAR=3.GÖZ seslendirme-yön.yard.→düşer; gerçek Sam Raimi KB cast-kilidiyle gelir.
    DUBLAJ markerları HER ZAMAN; diğer roller yalnız high_consensus=False (mutabakat-dışı=şüpheli) iken
    → temiz+mutabık gerçek yönetmeni öldürmez (yanlış>boş; OCR-otorite: isim eklemez/ezmez, yalnız düşürür).
    Döner (kalan, düşenler)."""
    if not directors or not raw_lines:
        return list(directors or []), []
    folded = [_fold(str(l)) for l in raw_lines]
    markers = _DUB_MARKERS if high_consensus else (_DUB_MARKERS + _NONFILM_MARKERS)
    kept, dropped = [], []
    for d in directors:
        df = _fold(d)
        is_nf = False
        if df and len(df) >= 5:
            # B3 FIX (2026-06-20): WORD-BOUNDARY (plain 'df in lf' substring → masum yönetmeni başka
            # satıra rastlantısal eşleştiriyordu) + ±1 bağlam (±2 fazla genişti → uzaktaki crew-etiketi
            # gerçek yönetmeni düşürüyordu). high_consensus guard zaten temiz+mutabık yönü koruyor.
            _df_re = re.compile(r"\b" + re.escape(df) + r"\b")
            for i, lf in enumerate(folded):
                if _df_re.search(lf):
                    ctx = " ".join(folded[max(0, i - 1):i + 1])
                    if any(m in ctx for m in markers):
                        is_nf = True
                        break
        (dropped if is_nf else kept).append(d)
    return kept, dropped


SCHEMA = {
    "type": "object",
    "properties": {
        "_reasoning": {"type": "string"},
        "yonetmen": {"type": "array", "items": {"type": "string"}},
        "yapimci": {"type": "array", "items": {"type": "string"}},
        "oyuncular": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["_reasoning", "yonetmen", "yapimci", "oyuncular"],
}

PROMPT = """Aşağıda bir filmin jeneriğinden (künye) OCR ile okunan satırlar var. Satırlar BOZUK/eksik olabilir.
GÖREVİN: bu satırlardan YÖNETMEN, YAPIMCI ve baş OYUNCULARI çıkarmak — YENİDEN OKUMAK ya da bilgiden EKLEMEK DEĞİL.

KESİN KURALLAR:
0. BİÇİM (EN ÖNEMLİ): her isim GERÇEK "Ad Soyad" olmalı — en az İKİ kelime, gerçek bir insan. TEK kelime (yalnız ad VEYA yalnız soyad) YAZMA. Marka/şirket/stüdyo/logo adı (ör. Warner Bros, Lucasfilm, Columbia Pictures), sıfat, rol/etiket sözcüğü İSİM DEĞİLDİR — YAZMA. Emin değilsen o ismi atla.
1. SADECE aşağıdaki satırlarda GEÇEN isimleri kullan. Kendi bilginden/hafızandan İSİM EKLEME, TAHMİN ETME. Bir alan satırlarda yoksa boş liste [] ver.
2. Bir satır "KARAKTER_ADI OYUNCU_ADI" biçimindeyse (ör. "CAL MORSE SAM WATERSTON", "FLETCHER REEDE JIM CARREY", "MARGARET THATCHER MERYL STREEP"), yalnız OYUNCU (gerçek kişi) adını al; KARAKTER adını KOYMA. Tek başına KARAKTER/ROL adı görünüyorsa (ör. yalnız "FLETCHER REEDE" veya "MARGARET THATCHER") onu LİSTEYE KOYMA — sadece gerçek oyuncu adlarını ver.
3. Rol etiketleri (DIRECTED BY, PRODUCED BY, YÖNETMEN, YAPIMCI, CAST, STARRING, THE END, MUSIC BY, WRITTEN BY...) ve şirket/kurum adları (FILM, FILMS, PRODUCTION, PICTURES, STUDIO, MEDIA, TV) İSİM DEĞİLDİR — listeye koyma.
4. YÖNETMEN — şu kalıplardan birinin YANINDAKİ/ALTINDAKİ GERÇEK kişi adı:
   - "DIRECTED BY <İSİM>", "A FILM BY <İSİM>", "A <İSİM> FILM" (ör. "A JOHN MCTIERNAN FILM" → John McTiernan), "AN <İSİM> FILM"
   - "YÖNETMEN", "YÖNETEN", "REJİSÖR", "UN FILM DE", "EIN FILM VON", "REGIE", "RÉALISÉ PAR"
   "A <İSİM> FILM" kalıbında "FILM" kelimesi ETİKETtir; içindeki KİŞİ adını AL (kural 3'e takılıp atlama).
   YÖNETMEN DEĞİLDİR — KOYMA: "ASSISTANT DIRECTOR / 1ST / 2ND / FIRST / SECOND ASSISTANT DIRECTOR", "DIRECTOR OF PHOTOGRAPHY", "ART DIRECTOR", "CASTING (BY)", "MUSIC DIRECTOR", yardımcı/görüntü/müzik/yapım yönetmeni.
   Bu kalıplardan hiçbiri NET değilse [] ver — ASLA oyuncu adı koyma, ASLA tahmin etme.
5. OYUNCULAR: jenerikte görünen GERÇEK oyuncu adları (gerçek insanlar; karakter/rol adları DEĞİL), en fazla 8, görünme sırasıyla. Besteci/müzik, kurgu, senaryo, görüntü yönetmeni, yapımcı gibi EKİP üyeleri OYUNCU DEĞİLDİR — cast'e koyma.
6. YAPIMCI: "PRODUCED BY / YAPIMCI / PRODUCER" yanındaki kişi(ler). Besteci/müzik (COMPOSER/MUSIC BY), kurgu, senaryo YAPIMCI DEĞİLDİR — koyma. "Executive/Associate/Line/Co-producer / Yürütücü / Ortak yapımcı" da GERÇEK yapımcı sayılmaz.

ÇIKTI: yalnız JSON:
{"_reasoning": "<her satırı kısaca etiketle: YÖNETMEN / YAPIMCI / OYUNCU / EKİP-DİĞER>", "yonetmen": [...], "yapimci": [...], "oyuncular": [...]}
_reasoning bölümünde önce her satırın hangi role ait olduğunu sınıflandır, SONRA alanları doldur.

SATIRLAR:
%s
"""


def _deepseek_json(model, prompt, timeout=120):
    """DeepSeek (API) JSON yanıtı — model adı 'deepseek*' ise. Anahtar yoksa {} (graceful)."""
    try:
        from _deepseek import deepseek_text
    except Exception:
        return {}
    txt = deepseek_text(prompt=prompt + "\n\nYALNIZ geçerli JSON döndür.",
                        model=model, temperature=0, max_tokens=1200,
                        fmt={"type": "json_object"}, timeout=timeout)
    if not txt:
        return {}
    try:
        return json.loads(txt)
    except Exception:
        i = txt.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(txt[i:])[0]
            except Exception:
                pass
    return {}


def _ollama_timeout(default=360) -> int:
    try:
        return max(60, int(os.environ.get("MITAS_OLLAMA_TIMEOUT", str(default)) or default))
    except Exception:
        return default


def _ollama_json(model, prompt, schema, timeout=None):
    timeout = _ollama_timeout() if timeout is None else timeout
    payload = {
        "model": model, "prompt": prompt, "format": schema, "stream": False,
        "options": {"temperature": 0, "num_ctx": 8192},
    }
    # Düşünme modeli (qwen3*, gemma-4) → think=False (zorunlu JSON `format` ile over-think çakışmasın).
    # gemma3 düşünme modeli DEĞİL → think gönderme (bazı sürümler 400 verir).
    _m = str(model).lower()
    if _m.startswith("qwen3") or _m.startswith(("gemma-4", "gemma4")):
        payload["think"] = False
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read().decode("utf-8"))
    txt = resp.get("response", "")
    try:
        return json.loads(txt)
    except Exception:
        i = txt.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(txt[i:])[0]
            except Exception:
                pass
    return {}


# ─── LATIN-DIŞI LLM ROMANİZASYON (2026-06-22, NAMUS DÜŞMANI) ─────────────────────────────────
# unidecode Arapça'yı sesli-harfsiz kabaya çevirir ("زكي آلاسيا"→"Zky Alsy") → extraction-LLM gibberish
# sanıp reddeder → cast boş kalır. ÇÖZÜM: çok-dilli qwen HAM non-Latin satırı DOĞRU Latin'e çevirsin
# ("Zeki Alasya"). Bu, OCR-otorite'nin İZİNLİ dönüşümü (kişi aynı, yalnız alfabe; credit_qc_block docstring).
# Sonuç DAİMA KONTROL'e gider (nonlatin_source gate) → human teyit eder (asla auto-ONAYLI). qwen başarısızsa
# çağıran taraf unidecode'a düşer (survival korunur). Fail-safe: hata → None.
_ROMANIZE_SCHEMA = {
    "type": "object",
    "properties": {"satirlar": {"type": "array", "items": {"type": "string"}}},
    "required": ["satirlar"],
}
_ROMANIZE_PROMPT = (
    "Aşağıdaki satırlar bir filmin jeneriğinden Latin-DIŞI alfabeyle (Arap/Kiril/Yunan) yazılmış "
    "metinlerdir; çoğu KİŞİ ADI (oyuncu/yönetmen/yapımcı). Her satırı DOĞRU LATİN-TÜRKÇE yazımına ÇEVİR "
    "(transkripsiyon): kişi/sözcük AYNI kalır, yalnız alfabe değişir. YENİ bilgi EKLEME, isim UYDURMA, "
    "satır ATLAMA, BİRLEŞTİRME. Her girdi satırı için TAM BİR çıktı satırı ver (sayı+sıra KORUNUR). "
    "Çıktı yalnız JSON: {\"satirlar\": [...]}.\n\nSATIRLAR:\n%s"
)


def _romanize_lines_llm(lines, model):
    """HAM non-Latin satırları çok-dilli qwen ile DOĞRU Latin'e çevir. Başarısızsa None (çağıran unidecode'a düşer).
    NOT (adversarial-doğrulama 2026-06-22): satır-sayısı KORUNMASI promptta istenir ama LLM garanti etmez →
    sapma sessiz isim kaybı/uydurma işareti olabilir; stderr'e uyarı yazılır (gözlemlenebilirlik). Romanizasyon
    halüsinasyonu (yanlış-isim ikamesi) içsel guard'larca SÜZÜLMEZ — nonlatin_source→KONTROL ile İNSANA devredilir
    (asla auto-ONAYLI). Çıktı yine de KORUNUR (kısmî > boş; insan teyit eder)."""
    lines = [str(l).strip() for l in (lines or []) if str(l).strip()]
    if not lines:
        return None
    try:
        raw = _ollama_json(model, _ROMANIZE_PROMPT % "\n".join(lines), _ROMANIZE_SCHEMA)
        out = raw.get("satirlar") if isinstance(raw, dict) else None
        if isinstance(out, list):
            out = [str(x).strip() for x in out if str(x).strip()]
            if out and len(out) != len(lines):    # satır-sayısı sapması → sessiz kayıp/uydurma şüphesi (gözlem)
                sys.stderr.write(f"[nonlatin-romanize] UYARI: satır sayısı sapması (girdi={len(lines)} "
                                 f"çıktı={len(out)}) → insan KONTROL teyidi şart\n")
            return out or None
    except Exception as e:  # noqa: BLE001 — fail-safe: romanizasyon başarısız → None → unidecode fallback
        sys.stderr.write(f"[nonlatin-romanize] {model} hata: {type(e).__name__}: {e}\n")
    return None


# Disclaimer/bağlaç/rol-etiketi kelimeleri — bir "isim"de geçiyorsa o cümle parçasıdır, isim DEĞİL.
# Deterministik junk-filtre (çok-dilli): LLM bazen "PELÍCULA SUBVENCİONADA POR EL" gibi disclaimer
# satırını cast'e koyuyor → exact-token eşleşmeyle düşür (alt-dize değil; "connery"≠"con").
_JUNK_WORDS = {
    "por", "the", "del", "della", "con", "apoyo", "subvencionada", "presenta", "presents",
    "presente", "avec", "mit", "und", "von", "par", "fund", "fondo", "support", "courtesy",
    "arrangement", "association", "produced", "directed", "production", "produccion", "pelicula",
    "film", "films", "colaboracion", "gracias", "thanks", "tarafindan", "destek", "katki", "sunar",
    "ile", "tarafından", "yapim", "yapimi", "music", "starring", "cast", "story", "screenplay",
    "written", "based", "company", "pictures", "studio", "media", "entertainment", "all", "rights",
    "performed", "mixed", "visual", "effects", "effect", "licensing", "license", "records",
    # TR rol-etiketi / ajans token'ları (bir "isim"de geçerse o etiket/kurum, kişi DEĞİL):
    "direktoru", "direktor", "yonetmeni", "yonetmen", "menajerlik", "menajer", "ajans", "ajansi",
    "ekibi", "amiri", "sefi", "sorumlusu", "operatoru", "koordinator", "kordinator", "muhendis",
    "teknisyen", "asistani", "yardimcisi", "supervisor", "coordinator", "manager", "designer",
    "casting", "editor", "mixer", "gaffer", "grip",
}


def _guard(names, ocr_fold_tokens, title_f):
    """Anti-halüsinasyon + junk-filtre: her ismin anlamlı tokenlarının TÜMÜ OCR metninde geçmeli;
    1-4 kelime; disclaimer/bağlaç kelimesi içermemeli. Aksi halde uydurma/çöp → atılır."""
    out, seen = [], set()
    for nm in names or []:
        nm = (nm or "").strip()
        if not nm:
            continue
        tk = _toks(nm)
        if not tk:
            continue
        # TÜM anlamlı tokenlar OCR metninde olmalı (halüsinasyon kalkanı)
        if not all(t in ocr_fold_tokens for t in tk):
            continue
        # isim 1-4 anlamlı kelime; daha uzunu cümle/disclaimer
        if len(tk) > 4:
            continue
        # disclaimer/bağlaç/etiket kelimesi içeren "isim" = cümle parçası → düş
        if any(t in _JUNK_WORDS for t in tk):
            continue
        if _fold(nm).strip() == title_f:  # film adının kendisi isim değil
            continue
        k = " ".join(tk)
        if k in seen:
            continue
        seen.add(k)
        out.append(nm)
    return out


# ─── F3: garble_audit.looks_garble import ───────────────────────────────────
# outputs/garble_audit.py script olarak yazılmıştır (if __name__== bloğu var).
# Sadece looks_garble + yardımcılarını yeniden tanımlamak en güvenli yol.
# (sys.path hack ile import etmek o dosyanın DB tarama kodunu çalıştırır → import-time yan etki)

import unicodedata as _uni

def _fold_ga(s: str) -> str:
    """garble_audit.fold() yerel kopyası (import-time yan etki yok)."""
    s = (s or "").replace("ı","i").replace("İ","i").replace("ş","s").replace("Ş","s")
    s = s.replace("ğ","g").replace("Ğ","g").replace("ç","c").replace("Ç","c")
    s = s.replace("ö","o").replace("Ö","o").replace("ü","u").replace("Ü","u")
    s = _uni.normalize("NFKD", s)
    s = "".join(c for c in s if not _uni.combining(c)).upper()
    s = re.sub(r"[^A-Z ]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def _lev_ga(a: str, b: str) -> int:
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        cur=[i]
        for j,cb in enumerate(b,1):
            cur.append(min(prev[j]+1, cur[j-1]+1, prev[j-1]+(ca!=cb)))
        prev=cur
    return prev[-1]

# garble_audit.ROLE_INST — tam eşleşme blocklist (folded)
_GA_ROLE_INST = {
 "KUVVETLERI","SILAHLI","MUSTEREKEN","CEVIRDIGI","CEVIRME","TARAFINDAN","ORDU","ORDUSU",
 "DESIGNER","DIRECTOR","PRODUCER","EDITOR","OPERATOR","SENATORS","SENATOR","CHORUS","IORUS",
 "MAKEUP","MAKSUP","BASIGNER","FILMI","FILMHI","SANAK","PIIMIM","SOMR","ARSUANL","THEBAN",
 "PRODUCED","DIRECTED","SCREENPLAY","CAMERA","MUSIC","SOUND","COSTUME","COMPANY","STUDIO",
 "PICTURES","PRESENTS","STARRING",
 # EK (2026-06-20 garble-routing): müzik-kredi / departman / şirket-lisans token'ları (kişi-adı DEĞİL).
 # OCR-okuma gate'i (F3) erken eler + nihai routing sinyalini güçlendirir. Hepsi exact-token (güvenli).
 # NOT: gerçek-oyuncu SOYADIYLA çakışan token'lar KASTEN dışarıda — DRIVER (Adam/Minnie Driver),
 # CRAFT (Christine Craft), FOLEY (Scott/Dave Foley), RUNNER. "CRAFT SERVICES" zaten SERVICES ile yakalanır.
 "PERFORMED","MIXED","ENGINEERED","ARRANGED","RECORDED","MASTERED","COMPOSED","CONDUCTED",
 "ORCHESTRATED","COURTESY","LICENSING","RECORDS","SOUNDTRACK","SERVICES","PRODUCTIONS",
 "ENTERTAINMENT","STUDIOS","RIGHTS","RESERVED","COORDINATOR","SECURITY",
 "CATERING","WRANGLER","GAFFER","TRANSPORTATION","TRANSPORT","DEPARTMENT","FACILITIES",
 "STANDBY","ACCOUNTANT","PUBLICIST","CASTING","WARDROBE","STUNTS","RERECORDING",
 "SUPERVISING","VISUAL","EFFECTS","COLORIST","COLOURIST","DUBBING","DISTRIBUTED","DISTRIBUTION",
}
# Türkçe fiil/cümle eki
_GA_VERB_SUFFIX = ("DIGI","DUGU","DIGINI","ERKEN","EREK","MEKTE","MAKTA","TIGI","TUGU","MISTIR","MUSTUR")
# garbled rol-etiketi fuzzy referansları
_GA_ROLE_REF = ["DESIGNER","DIRECTOR","PRODUCER","EDITOR","OPERATOR","CAMERAMAN","SUPERVISOR","ASSISTANT","COMPOSER"]


def _looks_garble(name: str) -> str | None:
    """garble_audit.looks_garble() yerel kopyası — SADECE YÜKSEK-İSABET sinyaller."""
    f = _fold_ga(name)
    toks = f.split()
    if not toks:
        return None
    # cümle eki
    for t in toks:
        if any(t.endswith(s) and len(t)>5 for s in _GA_VERB_SUFFIX):
            return f"cümle/fiil-eki ({t})"
    # rol/kurum/çöp token tam eşleşme
    hit = [t for t in toks if t in _GA_ROLE_INST]
    if hit:
        return f"rol/kurum/çöp token ({','.join(hit)})"
    # fuzzy garbled rol etiketi
    for t in toks:
        if len(t)>=6:
            for r in _GA_ROLE_REF:
                if 0 < _lev_ga(t,r) <= 2:
                    return f"garbled rol-etiketi ({t}~{r})"
    return None


def _sim_ga(a: str, b: str) -> float:
    a, b = _fold_ga(a), _fold_ga(b)
    m = max(len(a), len(b)) or 1
    return 1 - _lev_ga(a, b) / m


def _apply_garble_gate(names: list[str], kb=None) -> list[str]:
    """F3: garble olanı at; garble-varyant near-dup (VAVIZ KARAKAC ≈ YAVUZ KARAKAŞ) → garble'ı at temizi tut."""
    # 1. tek-isim garble taraması
    clean = []
    for nm in names:
        if _looks_garble(nm) is None:
            clean.append(nm)
    # 2. near-dup garble-varyant: sim ∈ [0.6, 0.97), aynı token sayısı, her token benzer ama eşit değil
    out = list(clean)
    removed = set()
    for i in range(len(clean)):
        if i in removed:
            continue
        for j in range(i+1, len(clean)):
            if j in removed:
                continue
            fa, fb = _fold_ga(clean[i]), _fold_ga(clean[j])
            if fa == fb:
                # tam dedup — birini kaldır (j)
                removed.add(j)
                continue
            s = _sim_ga(clean[i], clean[j])
            if s < 0.6 or s > 0.97:
                continue
            ta, tb = fa.split(), fb.split()
            # Aynı token sayısı + HER token bound içinde (fa!=fb zaten üstte garanti → ≥1 token farklı).
            # NOT: '0 <' KOYMA — bir token fold'da eşit olabilir (KARAKAŞ/KARAKAÇ→KARAKAC), diğeri garble.
            if (len(ta) == len(tb) and len(ta) >= 1
                    and all(_lev_ga(x, y) <= max(2, len(x)//2) for x, y in zip(ta, tb))):
                ga = _looks_garble(clean[i])
                gb = _looks_garble(clean[j])
                if ga and not gb:
                    removed.add(i)
                elif gb and not ga:
                    removed.add(j)
                else:
                    # İkisi de _looks_garble=None: saf harf-bozulması OCR ÇİFT-OKUMASI
                    # (VAVIZ KARAKAC ≈ YAVUZ KARAKAŞ). Türkçe diakritik SAYISI fazla olanı KORU
                    # (OCR garble diakritiği kaybeder/bozar); eşitse ikisini de tut.
                    # GÜVENLİK: düşülecek isim KB'de gerçek OYUNCU ise DÜŞME (iki ayrı kişi olabilir).
                    _dia = lambda s: sum(c in "şŞıİğĞçÇöÖüÜ" for c in (s or ""))
                    di, dj = _dia(clean[i]), _dia(clean[j])
                    drop = j if di > dj else (i if dj > di else None)
                    if drop is not None and not (kb and _kb_has_actor_prof(clean[drop], kb)):
                        removed.add(drop)
    out = [nm for idx, nm in enumerate(clean) if idx not in removed]
    return out


# ─── F3 YAPIMCI için ROLE_INST ayrımı ────────────────────────────────────────
# Kurumsal yapımcı (TÜRK SİLAHLI KUVVETLERİ) gerçek olabilir → YAPIMCI'da sadece
# fiil-eki ve garble-varyant (near-dup) blocklist'i uygula, kurum-token ile kırma.
_GA_YAPIMCI_GARBLE_ONLY_TOKS = {
    "CEVIRDIGI","CEVIRME","MUSTEREKEN","FILMI","FILMHI","SANAK","PIIMIM","SOMR","ARSUANL",
    "PRODUCED","DIRECTED","PRESENTS","STARRING",
}

def _looks_garble_yapimci(name: str) -> str | None:
    """Yapımcı için özel garble: fiil-eki + üretim-etiketi tokenleri; kurum adı geçerse AT DEĞİL."""
    f = _fold_ga(name)
    toks = f.split()
    if not toks:
        return None
    for t in toks:
        if any(t.endswith(s) and len(t)>5 for s in _GA_VERB_SUFFIX):
            return f"cümle/fiil-eki ({t})"
    hit = [t for t in toks if t in _GA_YAPIMCI_GARBLE_ONLY_TOKS]
    if hit:
        return f"garble üretim-token ({','.join(hit)})"
    # fuzzy garbled rol-etiketi — yapımcıda da uygula
    for t in toks:
        if len(t)>=6:
            for r in _GA_ROLE_REF:
                if 0 < _lev_ga(t,r) <= 2:
                    return f"garbled rol-etiketi ({t}~{r})"
    return None


def _apply_garble_gate_yapimci(names: list[str]) -> list[str]:
    """Yapımcı için garble kapısı — kurum adını korur."""
    clean = []
    for nm in names:
        if _looks_garble_yapimci(nm) is None:
            clean.append(nm)
    # near-dup
    out = list(clean)
    removed = set()
    for i in range(len(clean)):
        if i in removed:
            continue
        for j in range(i+1, len(clean)):
            if j in removed:
                continue
            fa, fb = _fold_ga(clean[i]), _fold_ga(clean[j])
            if fa == fb:
                removed.add(j)
                continue
            s = _sim_ga(clean[i], clean[j])
            if s < 0.6 or s > 0.97:
                continue
            ta, tb = fa.split(), fb.split()
            if (len(ta) == len(tb) and len(ta) >= 1
                    and all(_lev_ga(x, y) <= max(2, len(x)//2) for x, y in zip(ta, tb))):
                ga = _looks_garble_yapimci(clean[i])
                gb = _looks_garble_yapimci(clean[j])
                if ga and not gb:
                    removed.add(i)
                elif gb and not ga:
                    removed.add(j)
                # else: ikisi de None → ikisini de tut (yapımcıda diakritik-tiebreak YOK, temkinli)
    return [nm for idx, nm in enumerate(clean) if idx not in removed]


# ─── F2: KB rol-filtresi (credit_video_read.KB) ──────────────────────────────
# KB'yi lazy import et; hata → filtre no-op (KB() zaten graceful)
_KB_INSTANCE = None

def _get_kb():
    global _KB_INSTANCE
    if _KB_INSTANCE is None:
        try:
            _scripts_dir = os.path.dirname(os.path.abspath(__file__))
            if _scripts_dir not in sys.path:
                sys.path.insert(0, _scripts_dir)
            from credit_video_read import KB
            _KB_INSTANCE = KB()
        except Exception:
            _KB_INSTANCE = _NullKB()
    return _KB_INSTANCE


class _NullKB:
    """KB yoksa graceful no-op: her verify → 'kayit-yok' (filtre geçir)."""
    def verify(self, name, role):
        return "kayit-yok"


# Non-acting meslek kümeleri — KB bu mesleklerden birini dönüyor ve oyunculuk İÇERMİYORSA cast'ten at.
# KB sadece "crew kökeni belli" olanı eler; 0-kayıt = belirsiz → filtre geçir.
_NON_ACTOR_PROFS = frozenset({
    "sound_department", "camera_department", "art_department", "costume_department",
    "editorial_department", "music_department", "visual_effects", "make_up_department",
    "production_manager", "script_and_continuity_department", "transportation_department",
    "electrical_department", "stunts", "special_effects", "set_decorator",
    # Bazen KB'de yönetmen/yapımcı dönebilir; cast'e koyulmuşsa yine de at.
    # (Yönetmen-cast karışıklığı F1'deki edge-case ile ele alınır, burada KB ile de yakalıyoruz.)
})
_ACTOR_PROFS = frozenset({"actor", "actress"})


def _kb_is_crew_not_actor(name: str, kb) -> bool:
    """KB net 'oyunculuk içermeyen ekip üyesi' diyorsa True → cast'ten at.
    0-kayıt / meslek-bos / hata → False (filtre geçir)."""
    try:
        result = kb.verify(name, "actor")
        if result in ("kayit-yok", "meslek-bos", "?", "ONAY"):
            return False
        # result == "RED": KB bu kişiyi "actor" değil dedi.
        # Ancak KB primaryProfession "producer/director" da diyebilir → bu durumda cast'ten at.
        # Ek kontrol: KB'deki professions setini doğrudan kontrol etmeliyiz.
        # credit_video_read.KB.verify() sadece ONAY/RED döndürüyor; profession setini açmıyor.
        # Biz RED gelmesi = "oyunculuk onaylanmadı" → ama KB "director" için RED verebilir.
        # Güvenli strateji: RED + KB üzerinde profession lookup
        if not kb.con:
            return False
        import unicodedata as _unn
        rows = kb.con.execute(
            "SELECT primaryProfession FROM names "
            "WHERE UPPER(strip_accents(primaryName))=UPPER(strip_accents(?))", [name]).fetchall()
        if not rows:
            return False
        profs = set()
        for (p,) in rows:
            if p:
                profs.update(x.strip() for x in str(p).split(","))
        if not profs:
            return False
        # Oyunculuk var mı?
        if profs & _ACTOR_PROFS:
            return False  # oyuncu → geçir
        # Oyunculuk YOK ve non-actor meslek var → cast'ten at
        if profs & _NON_ACTOR_PROFS:
            return True
        return False
    except Exception:
        return False


def _kb_has_actor_prof(name: str, kb) -> bool:
    """KB primaryProfession actor/actress içeriyor mu? 0-kayıt/hata → False.
    (Başrol-yönetmen ayrımı + garble-varyant güvenliği için.)"""
    try:
        if not getattr(kb, "con", None):
            return False
        rows = kb.con.execute(
            "SELECT primaryProfession FROM names "
            "WHERE UPPER(strip_accents(primaryName))=UPPER(strip_accents(?))", [name]).fetchall()
        profs = set()
        for (p,) in rows:
            if p:
                profs.update(x.strip() for x in str(p).split(","))
        return bool(profs & _ACTOR_PROFS)
    except Exception:
        return False


def _apply_kb_cast_filter(cast: list[str], kb) -> list[str]:
    """F2: KB 'oyuncu değil ve ekip-meslekli' diyenleri at; 0-kayıt → geçir."""
    return [nm for nm in cast if not _kb_is_crew_not_actor(nm, kb)]


def _apply_kb_yapimci_filter(yapimci: list[str], kb) -> list[str]:
    """Yapımcı için: KB net 'yapımcı değil' diyorsa düşür; 0-kayıt → geçir."""
    out = []
    for nm in yapimci:
        try:
            r = kb.verify(nm, "producer")
            if r == "RED":
                # Ek kontrol: gerçekten hiç yapımcılık yok mu?
                if kb.con:
                    rows = kb.con.execute(
                        "SELECT primaryProfession FROM names "
                        "WHERE UPPER(strip_accents(primaryName))=UPPER(strip_accents(?))", [nm]).fetchall()
                    profs = set()
                    for (p,) in rows:
                        if p:
                            profs.update(x.strip() for x in str(p).split(","))
                    # Oyuncu olanı yapımcıdan at
                    if "actor" in profs or "actress" in profs:
                        continue
                    # Yapımcılık/yönetmenlik yok ama başka meslek de yok → geçir
                    if "producer" not in profs and "director" not in profs:
                        out.append(nm)  # belirsiz → geçir
                        continue
                    # Net yapımcı değil → at
                    continue
                else:
                    out.append(nm)  # KB yok → geçir
            else:
                out.append(nm)
        except Exception:
            out.append(nm)
    return out


# ─── F1: ENSEMBLE yönetmen fusion (credit_video_read.fuse() mantığı) ─────────

def _dedup_fold(seq: list[str]) -> list[str]:
    out: list[str] = []
    for x in seq:
        if not any(_fold(x) == _fold(y) for y in out):
            out.append(x)
    return out


def _fuse_yonetmen(per_model: dict[str, list[str]], kb) -> tuple[list[str], str]:
    """
    Tüm modellerin yönetmen adaylarını birleştir:
      1. ≥2 modelde aynı → mutabakat (YÜKSEK güven)
      2. Tek model + KB-ONAY → al (ORTA güven)
      3. Çelişki (farklı isimler), KB-ONAY olanı seç; çoklu ONAY → hepsini al
      4. Hiçbiri KB-ONAY değilse tek okuma varsa al (DÜŞÜK güven)
      5. Çelişki + ONAY yok → [] (OKUNAMADI)

    EDGE-CASE — başrolu-yönetmen sanma:
      Bir yönetmen adayı cast listesinde üst sıralarda görünüyorsa ŞÜPHELI.
      Mutabakat yoksa ve sadece tek-model sinyali ise düşür.
      (Ör: Robert Redford başroldür, George Roy Hill yönetmendir.)
    """
    flat = [n for lst in per_model.values() for n in lst]
    if not flat:
        return [], "OKUNAMADI"

    all_flat = _dedup_fold(flat)

    # mutabakat: ≥2 modelde geçen
    agreed = [n for n in all_flat
              if sum(1 for lst in per_model.values()
                     if any(_fold(n) == _fold(x) for x in lst)) >= 2]
    if agreed:
        # KB-RED olanları çıkar
        agreed_ok = [n for n in agreed if kb.verify(n, "director") != "RED"]
        return (agreed_ok or agreed), "YÜKSEK (mutabakat)"

    # Tek model veya çelişki: KB-ONAY olanı seç
    kb_ok = [n for n in all_flat if kb.verify(n, "director") == "ONAY"]
    if kb_ok:
        return kb_ok, "ORTA (KB-onay)"

    # Tek okuma AMA mutabakat yok + KB onayı yok → GÜVENİLMEZ → ABSTAIN.
    # (Eski "DÜŞÜK tek-okuma" KALDIRILDI: tek-model yanlış yönetmeni ONAYLI'ya koyup
    #  VL-fallback'i engelliyordu — Asi→"John Platt", Sessiz Ölüm→"A.M.Thompson". "yanlış>boş".)
    return [], "OKUNAMADI (tek-okuma, mutabakat/KB yok)"


# ── KESİN KURAL (Çağatay): yönetmen/yapımcı/cast'te YALNIZ gerçek "İsim Soyisim" ──
# ≥2 anlamlı token (isim+soyisim; orta-harf "E." serbest). TEK-TOKEN (sadece isim/soyisim) RED.
# Marka/logo/şirket/kurum/sıfat/rol-etiketi/garble RED. Aksi → liste dışı.
_NONPERSON_TOK = {
    "film", "films", "filmi", "filmleri", "production", "productions", "prod", "pictures", "picture",
    "studio", "studios", "media", "entertainment", "company", "co", "inc", "ltd", "llc", "gmbh", "srl",
    "tv", "yapim", "yapimi", "yapimevi", "yapimlari", "kuvvetleri", "silahli", "ordu", "ordusu",
    "kurumu", "vakfi", "dernegi", "bakanligi", "genel", "mudurlugu", "presents", "present", "sunar",
    "starring", "cast", "the", "and", "ile", "feat", "international", "group", "team", "pictures",
    "bros", "brothers", "sons", "enterprises", "enterprise", "corp", "corporation", "limited",
    "distribution", "releasing", "classics", "animation", "filmworks", "worldwide", "global",
    "networks", "network", "channel", "broadcasting", "partners", "associates",
    # kurum / vakıf / sendika / kuruluş (çok-dilli; gerçek "İsim Soyisim" token'ı değil)
    "foundation", "fondation", "fondazione", "stiftung", "agency", "agence",
    "association", "associazione", "guild", "union", "syndicate", "syndicat",
    "society", "societe", "societa", "institute", "institut", "instituto",
    "federation", "council", "conseil", "committee", "comite", "ministry",
    "ministere", "ministerio", "authority", "government", "gouvernement",
    "cinema", "cinematografica", "filmes", "filmproduktion", "produzione",
    "produktion", "telewizja", "presente", "presenta", "records", "rights", "reserved",
    # rol / sıfat / etiket
    "director", "directed", "producer", "produced", "executive", "associate", "yonetmen", "yapimci",
    "yoneten", "rejisor", "sunan", "anlatan", "music", "performed", "mixed", "visual", "effects",
    "effect", "licensing", "license", "records", "von", "der", "die",
}

# ── KAPI 1 — KARAKTER-ROL / TARİF ÇÖPÜ (2026-06-28) ─────────────────────────────
# Cast'e sızan karakter-tarifini ("GIRL AT DANCE", "SECOND GIRL", "IMMIGRATION OFFICER")
# OCR-otoritesini İHLAL ETMEDEN eler. TASARIM KARARI: token-bazlı rol-kelimesi reddi YASAK —
# birçok rol-kelimesi gerçek SOYADIDIR (Adam DRIVER, Mike JUDGE, Pat PRIEST, Gerard BUTLER).
# Yalnız YAPISAL olarak kesin desenler düşülür → hiçbir gerçek ada denk gelmez:
#   (1) situational edat ("at/in/on/of...") + ambiguous rol-ismi → "GIRL AT DANCE", "VOICE OF GOD"
#   (2) ordinal-önek ("FIRST/SECOND...") + ≥2 token → "SECOND GIRL", "FIRST POLICEMAN"
#   (3) tam-ifade çöp listesi (folded full-string; whack-a-mole ama %100 güvenli) → "FRENCH MAID"
# Flag MITAS_QC_ROLE_FILTER (modül-default OFF; _PROD_DEFAULTS + ps1'de ON). ADDITIVE: yalnız çöp
# düşürür, ad EZMEZ; kapatınca davranış birebir eskisi.
_ROLE_PREP = {"at", "in", "on", "of", "with", "near", "behind", "outside", "inside",
              "aboard", "atop", "beside", "among", "amongst", "to", "from"}
_ROLE_ORDINAL = {"first", "second", "third", "fourth", "fifth", "sixth", "seventh",
                 "eighth", "ninth", "tenth", "1st", "2nd", "3rd", "4th"}
# ambiguous rol-ismi: TEK BAŞINA red ETMEZ (Man Ho / Boy George korunur); yalnız edatla birleşince.
_AMBIG_ROLE_NOUN = {"man", "woman", "boy", "girl", "lady", "guy", "men", "women", "boys",
                    "girls", "kid", "child", "children", "people", "voice", "guard",
                    "officer", "soldier", "cop", "policeman", "policewoman", "maid",
                    "waiter", "waitress", "nurse", "driver", "doctor", "captain", "priest"}
# tam-ifade (folded) çöp: bare rol-etiketleri + kredi-konvansiyonları (exact match → gerçek ada çarpmaz).
_ROLE_PHRASE_EXACT = {
    "immigration officer", "police officer", "prison guard", "french maid",
    "night watchman", "himself", "herself", "themselves", "narrator",
}


def _role_filter_on() -> bool:
    return os.environ.get("MITAS_QC_ROLE_FILTER", "0").strip().lower() in ("1", "true", "on", "yes")


def _looks_character_role(name: str) -> bool:
    """True = karakter-tarifi/çöp (oyuncu ADI değil). Yalnız yapısal-kesin desen; gerçek ad düşürmez."""
    f = " ".join(_fold(name).split())
    if not f:
        return False
    if f in _ROLE_PHRASE_EXACT:                                              # (3) tam-ifade çöp
        return True
    toks = f.split()
    if any(t in _ROLE_PREP for t in toks) and any(t in _AMBIG_ROLE_NOUN for t in toks):  # (1)
        return True
    if toks[0] in _ROLE_ORDINAL and len(toks) >= 2:                          # (2) ordinal-önek
        return True
    return False


def _valid_person_name(name: str) -> bool:
    nm = (name or "").strip()
    if not nm or any(ch in nm for ch in "<>|/\\@&") or any(c.isdigit() for c in nm):
        return False
    toks = [t for t in _fold(nm).split() if t]
    real = [t for t in toks if len(t) >= 2]            # orta-harf (E.) serbest; ≥2 GERÇEK token şart
    if len(real) < 2 or len(toks) > 4:                 # tek-token RED, cümle RED
        return False
    if any(t in _NONPERSON_TOK for t in toks) or any(t in _JUNK_WORDS for t in toks):
        return False
    if _looks_garble(nm):
        return False
    if _role_filter_on() and _looks_character_role(nm):     # KAPI 1: karakter-rol/tarif çöpü (flag'li)
        return False
    return True

def _only_persons(names):
    """KESİN KURAL süzgeci: yalnız geçerli 'İsim Soyisim' kalır."""
    return [n for n in (names or []) if _valid_person_name(n)]


_CAST_HEADER_RE = re.compile(r"^\s*(CAST|STARRING|OYUNCULAR|OYUNCU|OYNAYANLAR)\s*$", re.IGNORECASE)
_CAST_SKIP_RE = re.compile(r"^\s*\(?\s*(IN ORDER OF APPEARANCE|ORDER OF APPEARANCE)\s*\)?\s*$", re.IGNORECASE)
_CHARACTER_PREFIX_TOK = {
    "captain", "father", "first", "second", "third", "inn", "landlord", "officer", "doctor",
    "mrs", "mr", "miss", "young", "old", "older", "oldest", "boy", "girl", "man", "woman",
}


def _suffix_actor_from_role_line(line: str) -> str | None:
    """Return actor suffix from `ROLE/CHARACTER Actor Name` mixed-case OCR lines."""
    parts = [p.strip(" ,:;") for p in str(line or "").split() if p.strip(" ,:;")]
    if len(parts) < 3:
        return None
    for i in range(1, len(parts) - 1):
        prefix = parts[:i]
        if any(p and p[0].islower() for p in prefix):
            continue
        suffix = parts[i:]
        if not all(p and p[0].isupper() and any(c.islower() for c in p) for p in suffix):
            continue
        cand = " ".join(suffix)
        if _valid_person_name(cand):
            return cand
    return None


def _cast_block_candidate(line: str) -> str | None:
    line = str(line or "").strip()
    if not line or _CAST_SKIP_RE.match(line):
        return None
    lf = _fold(line)
    if _crew_context(lf):
        return None
    suffix = _suffix_actor_from_role_line(line)
    if suffix:
        return suffix
    toks = [t for t in lf.split() if t]
    if toks and toks[0] in _CHARACTER_PREFIX_TOK:
        return None
    if "." in line or " . " in line or " / " in line:
        return None
    raw_parts = [p.strip(" ,:;") for p in line.split() if p.strip(" ,:;")]
    if any(p and p[0].islower() for p in raw_parts):
        return None
    if _valid_person_name(line):
        return line
    return None


def extract_cast_block_candidates(lines: list[str], *, limit: int = 8) -> list[str]:
    """Deterministic fallback for visible CAST blocks when the LLM times out/abstains."""
    cleaned = [str(line).strip() for line in (lines or []) if str(line).strip()]
    out: list[str] = []
    for i, line in enumerate(cleaned):
        if not _CAST_HEADER_RE.match(line):
            continue
        misses_after_hit = 0
        for nxt in cleaned[i + 1:i + 90]:
            nf = _fold(nxt)
            if _CAST_HEADER_RE.match(nxt) or _CAST_SKIP_RE.match(nxt):
                continue
            if _crew_context(nf) and len(out) >= 3:
                break
            cand = _cast_block_candidate(nxt)
            if cand:
                out.append(cand)
                out = _dedup_fold(out)
                misses_after_hit = 0
                if len(out) >= limit:
                    return out[:limit]
            elif out:
                misses_after_hit += 1
                if misses_after_hit >= 12 and len(out) >= 3:
                    break
        if out:
            return out[:limit]
    return []


# ── QC1 SATIR-ÖN-ELEMESİ (Çağatay 2026-06-15): gürültü PDF'e hiç girmesin ──
# Disclaimer/telif/courtesy/teşekkür/sendika/teknik-marka satırlarını LLM'e GÖNDERMEDEN at.
# Bunlar çok-kelimeli YASAL/TEKNİK kalıp — gerçek "İsim Soyisim" bu kalıplara girmez → SIFIR regresyon.
# (Tek-token marka isimleri DEĞİL; yalnız bariz kalıp-içeren satırlar. İsim satırına dokunmaz.)
_PREFILTER_PHRASES = (
    "COURTESY OF", "IN ASSOCIATION WITH", "EN ASSOCIATION", "AVEC LA PARTICIPATION",
    "WITH THE PARTICIPATION", "IN COLLABORATION WITH", "PROVIDED BY", "STOCK FOOTAGE",
    "ALL RIGHTS RESERVED", "TOUS DROITS", "COPYRIGHT", "SPECIAL THANKS", "THANKS TO",
    "DEDICATED TO", "IN MEMORY OF", "IN LOVING MEMORY", "NO ANIMALS WERE",
    "FILMED ON LOCATION", "SHOT ON LOCATION", "FILMED IN", "RECORDED AT",
    "DOLBY DIGITAL", "DOLBY STEREO", "DTS DIGITAL", "ULTRA STEREO",
    "BASED ON THE", "BASED UPON", "MOTION PICTURE ASSOCIATION",
)
_PREFILTER_MARK = ("©", "®", "™")


def _prefilter_lines(lines):
    """LLM'e girmeden bariz disclaimer/yasal/teknik satırları ele (kişi-adı DEĞİL)."""
    out = []
    for ln in (lines or []):
        u = _fold(ln).upper()
        if any(p in u for p in _PREFILTER_PHRASES):
            continue
        if any(s in ln for s in _PREFILTER_MARK):
            continue
        out.append(ln)
    return out


def read_credits_from_text(lines, title="", model=None, *, dizi=False):
    model = model or DEFAULT_MODEL
    lines = [l.strip() for l in (lines or []) if l and l.strip()]
    text = "\n".join(lines)
    ocr_tokens = set(_toks(text))
    title_f = _fold(title).strip()
    out = {"yonetmen": [], "yapimci": [], "cast": [], "guven": "OKUNAMADI", "model": model}
    if not lines:
        out["hata"] = "bos_metin"
        return out
    try:
        if str(model).startswith("deepseek"):
            raw = _deepseek_json(model, PROMPT % text)
        else:
            raw = _ollama_json(model, PROMPT % text, SCHEMA)
    except Exception as e:
        out["hata"] = f"{type(e).__name__}: {e}"
        return out
    out["ham"] = raw
    yon = _guard(raw.get("yonetmen"), ocr_tokens, title_f)
    yap = _guard(raw.get("yapimci"), ocr_tokens, title_f)
    cast = _guard(raw.get("oyuncular"), ocr_tokens, title_f)
    if not dizi:
        cast = cast[:8]
    # KESİN KURAL: yalnız gerçek "İsim Soyisim"
    out["yonetmen"], out["yapimci"], out["cast"] = _only_persons(yon), _only_persons(yap), _only_persons(cast)
    if out["cast"] or out["yonetmen"]:
        out["guven"] = "OKUNDU (metin-rol-eşleme)"
    return out


def model_chain():
    """Metin model zinciri.
    GEÇİŞ (Çağatay 2026-06-23): TEK MODEL **gemma-4-31b-it-qat-vision + think=False** (MULTIMODAL).
    Ayıklayıcı qwen3.6:35b-a3b → gemma-4-31b-it-qat-vision:latest (yerel GGUF+mmproj). text-only
    çağrıda mmproj girmez → metin text-only gemma ile BİREBİR aynı (aynı blob, +1GB VRAM), vision-hazır
    (paralel-VLM tek modelle). qwen DEVRE DIŞI
    ama silinmedi → MITAS_CREDIT_TEXT_MODEL=qwen3.6:35b-a3b ile anında geri dönülür.
    Tarihçe (2026-06-14, 20-film benchmark): qwen3.6:35b-a3b ayıklamada qwen3:8b'yi her eksende
    yenmişti; gemma'ya geçiş kalite-A/B ile doğrulanır (bkz E:\\QwenModels\\ayikla_bench\\).
    NOT: 31b≈17GB VRAM → CLIP/OCR ile aynı anda GPU'da dikkat; ayıklayıcı aşaması ollama'da paylaşır.
    _ollama_json gemma-4/qwen3* için think=False gönderir (JSON `format` ile over-think çakışmasın).
    Override: MITAS_CREDIT_TEXT_MODEL (virgüllü). DeepSeek opt-in: MITAS_CREDIT_TEXT_MODEL=deepseek-chat."""
    envm = os.environ.get("MITAS_CREDIT_TEXT_MODEL", "").strip()
    if envm:
        return [m.strip() for m in envm.split(",") if m.strip()]
    return ["gemma-4-31b-it-qat-vision:latest"]


def read_credits_auto(lines, title="", *, dizi=False, raw_context_lines=None):
    """F1: TÜM modelleri koş, ilk-doluda DURMA.
    Yönetmen: fuse() ile mutabakat/KB-seçimi.
    Cast: tüm modellerin birleşimi, dedup + F2 KB filtresi + F3 garble kapısı.
    Yapımcı: birleşim + F3 garble (yapımcı-özel) kapısı + F2 KB yapımcı filtresi.
    """
    chain = model_chain()
    lines = [l.strip() for l in (lines or []) if l and l.strip()]
    # ── LATIN-DIŞI ERKEN ROMANİZASYON (2026-06-22, NAMUS DÜŞMANI) ─────────────────────────────
    # Arap/Kiril/Yunan künyede _fold (re.sub r"[^a-z0-9 ]") TÜM harfleri siler → boş token → guard/
    # _valid_person_name ismi atar → %100 kadro kaybı (OCR mükemmel okusa bile). ÇÖZÜM: extraction'dan
    # ÖNCE Latin'e çevir → isim _fold'da ölmez. ÖNCE çok-dilli qwen (HAM Arapça→"Zeki Alasya" doğru
    # transkripsiyon; OCR-otorite'nin İZİNLİ dönüşümü — kişi aynı, alfabe değişir). qwen başarısızsa
    # unidecode'a düş (kaba "Zky Alsy" ama survival korunur; extraction-LLM reddedebilir). nonlatin_source:
    # romanizasyon OTORİTE DEĞİL → credit_qc_block KONTROL'e yollar (ASLA auto-ONAYLI, human teyit eder).
    # Bayraklar default-ON; Latin filmlerde HİÇ tetiklenmez (detect_script=='latin' → dokunulmaz, 0 regresyon).
    nonlatin_source = False
    translit_method = None
    if os.environ.get("MITAS_NONLATIN_TRANSLIT", "1").strip().lower() not in ("0", "false", "off", "no"):
        try:
            from translit_util import detect_script as _ds, transliterate_mixed as _tlm
        except Exception:  # noqa: BLE001 — translit_util yoksa kalkanı atla (mevcut davranış AYNEN)
            _ds = None
        _full_src = "\n".join(lines + [str(x) for x in (raw_context_lines or [])])
        # Oran kalkanı (bkz _nonlatin_ratio): tek-tük OCR gürültüsü (<%2) RENDER/KONTROL tetiklemesin.
        if _ds is not None and _ds(_full_src) != "latin" and _nonlatin_ratio(_full_src) >= _NONLATIN_MIN_RATIO:
            nonlatin_source = True
            _methods: set[str] = set()

            def _tl_line(s):                            # token-bazlı (kaba unidecode fallback; _fold'dan kurtarır)
                s = str(s or "")
                if not s.strip():
                    return s
                # transliterate_mixed: AZINLIK Latin-dışı token de iner (baskın 'latin' atlamaz),
                # Latin satır → asciify (Türkçe korunur), çevrilemezse HAM koru (sessiz silme yok)
                _o, _m = _tlm(s)
                _methods.update(_m)
                return _o

            # 1) ÖNCE LLM romanizasyon (DOĞRU isim kalitesi). Flag default-ON; kapalıysa direkt unidecode.
            _rmodel = (chain[0] if chain else DEFAULT_MODEL)   # birincil yerel ayıklayıcı modeli
            _rom = None
            if os.environ.get("MITAS_NONLATIN_LLM_ROMANIZE", "1").strip().lower() not in ("0", "false", "off", "no"):
                _rom = _romanize_lines_llm(lines, _rmodel)
            if _rom:
                lines = _rom
                if raw_context_lines:                   # bağlam da romanize (yoksa unidecode'a düş)
                    raw_context_lines = _romanize_lines_llm(
                        [str(x) for x in raw_context_lines], _rmodel) or [_tl_line(x) for x in raw_context_lines]
                translit_method = f"llm:{_rmodel}"
            else:                                       # 2) FALLBACK: unidecode (survival; qwen erişilemez/boş)
                lines = [_tl_line(l) for l in lines]
                if raw_context_lines:
                    raw_context_lines = [_tl_line(l) for l in raw_context_lines]
                translit_method = ",".join(sorted(_methods)) if _methods else "unidecode"
    lines = _prefilter_lines(lines)            # QC1: disclaimer/yasal/teknik satırları ele (LLM görmesin) — codex bunu kaldırmıştı (regresyon)
    text = "\n".join(lines)
    guard_lines = list(lines)
    if raw_context_lines:
        guard_lines.extend(str(l).strip() for l in raw_context_lines if str(l).strip())
    ocr_tokens = set(_toks("\n".join(guard_lines)))
    title_f = _fold(title).strip()

    kb = _get_kb()
    pre_cast = extract_cast_block_candidates(lines, limit=(99 if dizi else 8))
    cast_block_fast = os.environ.get("MITAS_CREDIT_CAST_BLOCK_FAST", "0").strip().lower() in (
        "1", "true", "on", "yes"
    )
    if cast_block_fast and len(pre_cast) >= 3:
        cast_fast = _apply_garble_gate(pre_cast, kb)
        cast_fast = _apply_kb_cast_filter(cast_fast, kb)
        cast_fast = filter_cast_by_raw_context(cast_fast, raw_context_lines)
        if not dizi:
            cast_fast = cast_fast[:8]
        if len(cast_fast) >= 3:
            return {
                "yonetmen": [],
                "yapimci": [],
                "cast": _only_persons(cast_fast),
                "guven": "OKUNDU (cast-block fallback; qwen atlandı)",
                "nonlatin_source": nonlatin_source,
                "translit_method": translit_method,
            }

    per_model_yon: dict[str, list[str]] = {}
    per_model_cast: dict[str, list[str]] = {}
    all_cast: list[str] = []
    all_yap: list[str] = []
    any_success = False

    for m in chain:
        try:
            if str(m).startswith("deepseek"):
                raw = _deepseek_json(m, PROMPT % text)
            else:
                raw = _ollama_json(m, PROMPT % text, SCHEMA)
        except Exception as e:
            sys.stderr.write(f"[credit_text_read] {m} hata: {type(e).__name__}: {e}\n")
            per_model_yon[m] = []
            per_model_cast[m] = []
            continue

        yon_raw = _guard(raw.get("yonetmen"), ocr_tokens, title_f)
        yap_raw = _guard(raw.get("yapimci"), ocr_tokens, title_f)
        cast_raw = _guard(raw.get("oyuncular"), ocr_tokens, title_f)

        per_model_yon[m] = yon_raw
        per_model_cast[m] = cast_raw
        all_yap.extend(yap_raw)
        all_cast.extend(cast_raw)
        if yon_raw or cast_raw or yap_raw:
            any_success = True

    # ── F1: Yönetmen fusion ──────────────────────────────────────────────────
    yon_fused, guven_yon = _fuse_yonetmen(per_model_yon, kb)

    # ── F3 + F2: Cast boru hattı ─────────────────────────────────────────────
    cast_merged = _dedup_fold(all_cast)
    if _GATE_BEFORE_CAP:
        # FIX 3: filtre cap'ten ÖNCE — garble'lar gerçek adları 8-slottan atmasın.
        cast_garble = _apply_garble_gate(cast_merged, kb)
        if not dizi:
            cast_garble = cast_garble[:8]
    else:
        if not dizi:
            cast_merged = cast_merged[:8]
        cast_garble = _apply_garble_gate(cast_merged, kb)

    # F1 edge-case (BAŞROL-YÖNETMEN ayrımı): MUTABAKAT YOKSA, cast'te de görünen yönetmen
    # adayı büyük olasılıkla BAŞROL oyuncudur (ör. Waldo Pepper'da Robert Redford başrol,
    # yönetmen George Roy Hill; Redford KB'de yönetmen olduğu için ONAY alıp sızıyordu).
    # → yönetmenden DÜŞÜR (cast'te kalsın), "yanlış > boş" (okunamadı). Mutabakat (≥2 model)
    # varsa gerçek oyuncu-yönetmen olabilir (Eastwood/Allen) → DOKUNMA.
    # AYRAÇ (KB-bağımsız, self-consistency): bir yönetmen adayını öneren modellerden biri
    # AYNI ismi KENDİ cast'ine de koyduysa → o model kendi içinde çelişiyor → büyük olasılıkla
    # BAŞROL (Redford: qwen hem yönetmen dedi hem cast'ine koydu). Buna karşılık Cimino'yu
    # qwen yönetmen dedi ama KENDİ cast'ine koymadı (cast'e koyan gemma'ydı, o Walken dedi) →
    # çelişki YOK → KORU. Mutabakat (≥2 model) varsa gerçek oyuncu-yönetmen → dokunma.
    if guven_yon != "YÜKSEK (mutabakat)" and yon_fused:
        _kept = []
        for n in yon_fused:
            nf = _fold(n)
            proposers = [m for m, lst in per_model_yon.items() if any(_fold(x) == nf for x in lst)]
            self_contradict = any(
                any(_fold(c) == nf for c in per_model_cast.get(m, [])) for m in proposers)
            if self_contradict:
                continue  # başrol-yönetmen → düş ("yanlış > boş")
            _kept.append(n)
        if _kept != yon_fused:
            yon_fused = _kept
            if not _kept:
                guven_yon = "OKUNAMADI (başrol-yönetmen şüphesi)"
    # DUBLAJ-ROL DIŞLAMA: Türkçe-dublaj "SESLENDİRME/DUBLAJ YÖNETMENİ(+yard.)" film-yönetmeni sanılmasın
    # (3.GÖZ: 'ESRA TANAR' = seslendirme yön. yard. → düşer; gerçek Sam Raimi KB cast-kilidiyle gelir).
    yon_fused, _nf_dropped = _drop_dubbing_directors(
        yon_fused, raw_context_lines or lines,
        high_consensus=(guven_yon == "YÜKSEK (mutabakat)"))
    if _nf_dropped:
        sys.stderr.write(f"[rol-atfı] yönetmenden düştü (yönetmen-dışı rol): {_nf_dropped}\n")
        if not yon_fused:
            guven_yon = "OKUNAMADI (yönetmen-dışı rol — film yönetmeni değil)"
    # Kesin yönetmen cast'te de görünüyorsa cast'ten at (cast↔yönetmen kontaminasyon)
    yon_fold_set = {_fold(n) for n in yon_fused}
    cast_garble = [n for n in cast_garble if _fold(n) not in yon_fold_set]

    cast_kb = _apply_kb_cast_filter(cast_garble, kb)
    cast_kb = filter_cast_by_raw_context(cast_kb, raw_context_lines)
    if len(cast_kb) < 3:
        fallback_cast = extract_cast_block_candidates(lines, limit=(99 if dizi else 8))
        if fallback_cast:
            fallback_cast = _apply_garble_gate(fallback_cast, kb)
            fallback_cast = _apply_kb_cast_filter(fallback_cast, kb)
            fallback_cast = filter_cast_by_raw_context(fallback_cast, raw_context_lines)
            cast_kb = _dedup_fold(list(cast_kb) + fallback_cast)
            if not dizi:
                cast_kb = cast_kb[:8]

    # ── F3 + F2: Yapımcı boru hattı ──────────────────────────────────────────
    yap_merged = _dedup_fold(all_yap)
    yap_garble = _apply_garble_gate_yapimci(yap_merged)
    yap_kb = _apply_kb_yapimci_filter(yap_garble, kb)

    # ── Güven skoru ──────────────────────────────────────────────────────────
    if cast_kb or yon_fused:
        guven = f"OKUNDU (ensemble/fallback; yön:{guven_yon})"
    elif not any_success:
        guven = "OKUNAMADI"
    else:
        guven = "KISMI (sadece yapımcı)"

    # KESİN KURAL (son süzgeç): yönetmen/yapımcı/cast'te yalnız gerçek "İsim Soyisim"
    return {
        "yonetmen": _only_persons(yon_fused),
        "yapimci": _only_persons(yap_kb),
        "cast": _only_persons(cast_kb),
        "guven": guven,
        "nonlatin_source": nonlatin_source,
        "translit_method": translit_method,
    }


def main():
    import argparse
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr", required=True, help="OneOCR+GLM kunye.txt yolu")
    ap.add_argument("--title", default="")
    ap.add_argument("--model", default=None)
    ap.add_argument("--dizi", action="store_true")
    a = ap.parse_args()
    lines = open(a.ocr, encoding="utf-8", errors="ignore").read().splitlines()
    if a.model:
        # tek model modu (eski compat)
        res = read_credits_from_text(lines, a.title, a.model, dizi=a.dizi)
    else:
        res = read_credits_auto(lines, a.title, dizi=a.dizi)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
