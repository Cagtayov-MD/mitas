# -*- coding: utf-8 -*-
"""Betik-farkında rol tablosu — çok-dilli yönetmen (ve alt-rol) kelime eşleşmesi.

Tasarım: docs/superpowers/specs/2026-08-12-betik-farkinda-rol-tanima-design.md

FAZ-1 (OCR ÖNCESİ, tahmin): karelerden dil tahmini yalnız Paddle'ın hangi OCR
modeliyle koşacağını belirler (bkz. harness/kunye_kiyas/kobe.py `detect_script_qwen`
+ `credit_content.get_aktif_dil`) — BU MODÜLÜ HİÇ İLGİLENDİRMEZ.

FAZ-2 (OCR SONRASI, kesinlik): metin elimizde olduğu için unicodedata ile satırın
betiği %100 kesin belirlenebilir. Rol eşleşmesi HER ZAMAN buna bakar, LLM'in Faz-1
tahminine ASLA bakmaz — `get_aktif_dil()` bu modülde KULLANILMAZ.

Bağımlılık: yalnız stdlib (`unicodedata`, `re`, `logging`). Başka hiçbir proje
modülünü import ETMEZ (üç ayrı sys.path ağacından — harness/kunye_kiyas,
scripts/, OCR-worktree/pdf-mitas — bağımlılıksız erişilebilmesi için).

Yeni dil eklemek = TABLO'ya satır eklemek, kod değişmez. Tek istisna: Latin-
genişletilmiş harfler (örn. Vietnamca 'đ' U+0111) NFKD ile ASCII'ye inmez — LATIN
dalının kendi normalizasyonu (`_norm_latin`) bunun için bir kerelik ek çeviri
taşır (§3.2).
"""
from __future__ import annotations

import logging
import re
import unicodedata

_log = logging.getLogger("rol_tablosu")

# ── LATIN.YONETMEN / LATIN.HARIC — credit_role_lexicon.py'nin DIRECTOR / EXCLUDE
# listelerinin BİREBİR KOPYASI (§4.1). Kelime EKLEME, ÇIKARMA, sıra değiştirme YOK.
# Kaynak: scripts/credit_role_lexicon.py DIRECTOR (satır 29-70) / EXCLUDE (94-121).
_LATIN_YONETMEN = [
    # TR
    "YONETMEN", "YONETEN", "REJISOR", "YONETMENI",
    # EN
    "DIRECTED BY", "A FILM BY", "FILM BY", "DIRECTOR", "DIRECTION",
    # Bileşik etiketler (AJAMİ doğruluk-denetimi 2026-07-03: "Written, Directed and Edited by
    # Scandar Copti, Yaron Shani" kartından eş-yönetmen düşmüştü)
    "WRITTEN AND DIRECTED", "DIRECTED AND EDITED", "PRODUCED AND DIRECTED", "WRITTEN, DIRECTED",
    # FR
    "REALISE PAR", "REALISATION", "REALISATEUR", "UN FILM DE", "MISE EN SCENE",
    "DIRIGE PAR",   # 117-film taraması 2026-07-03: ŞEYTAN RUHLU İNSANLAR (LES DIABOLIQUES) kanıtı
    # DE
    "EIN FILM VON", "REGIE", "INSZENIERUNG",
    # SV/DA/NO (İskandinav) — İNTİKAM (BECK) kanıtı 2026-07-03
    "REGISSOR", "INSTRUKTOR",
    # IT
    "DIRETTO DA", "UN FILM DI", "REGIA", "REGISTA",
    # ES
    "DIRIGIDA POR", "DIRIGIDO POR", "DIRECCION", "UNA PELICULA DE", "DIRECTOR",
    # PT
    "REALIZADO POR", "DIRIGIDO POR", "REALIZACAO", "DIRECAO",
    # ── ÇOK-DİLLİ GENİŞLEME (2026-07-06, Çağatay: "diller/sıfatlar/ihtimaller — DOLDUR") ──
    # Bileşik/varyant EN (BUZDAN/CENNETE kanıtları)
    "DIRECTED & PHOTOGRAPHED", "PRODUCED, WRITTEN & DIRECTED", "STORY AND DIRECTION",
    "SCREENPLAY AND DIRECTION", "STORY, SCREENPLAY AND DIRECTION", "FILM DIRECTED BY",
    # NL / PL / CZ-SK / HU / RO / EL(translit)
    "GEREGISSEERD DOOR", "REZYSERIA", "REZIE", "RENDEZTE", "RENDEZO", "REGIA", "SKINOTHESIA",
    # RU/UA/BG (Latin-translit — Kiril OCR'ı bazen translit döker)
    "REZHISSER", "REZHISSYOR", "REJISSER", "POSTANOVKA", "REZHYSER", "REZHISOR",
    # SR/HR/SL
    "REZIJA", "REDATELJ",
    # HI/UR (Hint kartları translit) + FA + AR (translit)
    "NIRDESHAK", "NIRDESHAN", "KARGARDAN", "IKHRAJ", "MUKHRIJ",
    # JA/ZH latin-kartlar (uluslararası kopyalarda İngilizce gelir; yine de pinyin/romaji nadir)
    "KANTOKU", "DAOYAN",
    # Bileşik başlıklar (2026-07-07 lexicon_anchor_misparse): FR/EN "üret VE yönet" birleşik
    # etiketi TEK SATIRDA gelince _match_head (en-uzun-önce) TAMAMINI yer → strip="" → isim
    # SONRAKİ satırdan alınır. (Kanıt: ŞEYTAN RUHLU 1955-0046 "PRODUIT ET DIRIGE PAR / H.G. CLOUZOT".)
    "PRODUIT ET DIRIGE PAR", "PRODUIT ET REALISE PAR", "ECRIT ET REALISE PAR",
    "ECRIT ET DIRIGE PAR", "PRODUCED AND DIRECTED BY", "WRITTEN AND DIRECTED BY",
    "DIRECTED AND PRODUCED BY", "PRODUCED WRITTEN AND DIRECTED BY",
]
_LATIN_HARIC = [
    # TR alt-roller
    "YARDIMCI", "SESLENDIRME", "MUZIK", "GORUNTU", "SANAT", "DUBLAJ", "CASTING",
    # EN alt-roller
    "ASSISTANT", "ASSOCIATE", "SECOND UNIT", "ART DIRECTOR", "CASTING DIRECTOR",
    "MUSIC DIRECTOR", "DIRECTOR OF PHOTOGRAPHY", "TECHNICAL DIRECTOR", "CO DIRECTOR",
    "PHOTOGRAPHY", "PRODUCTION ASSISTANT", "PRODUCTION MANAGER", "PRODUCTION COORDINATOR",
    "LINE PRODUCER",
    # FR/DE/IT/ES alt-roller
    "ASSISTANT REALISATEUR", "DIRECTEUR DE LA PHOTOGRAPHIE", "DIRECTEUR ARTISTIQUE",
    "REGIEASSISTENZ", "AIUTO REGISTA", "DIRETTORE DELLA FOTOGRAFIA",
    "AYUDANTE DE DIRECCION", "DIRECTOR DE FOTOGRAFIA", "DIRECTOR ARTISTICO",
    # SANAT-YÖNETİMİ tüm dillerde (2026-07-06 BAŞKAN VE MARI regresyon: "DIRECTION ARTISTIQUE"
    # → "DIRECTION" içerdiği için yönetmen sanılıp 'ARISTIQUE FRANCE' uydurdu). ART DIRECTION ≠ yönetmen.
    "ARTISTIQUE", "ARTISTICA", "ARTISTICO", "ARTISTICH", "DIRECTION ARTISTIQUE",
    "DIRECAO DE ARTE", "DIREZIONE ARTISTICA", "KUNSTLERISCHE LEITUNG", "SANAT YONETMENI",
    # cast/yapımcı doğruluk-denetimi 2026-07-04 — yapımcı YANLIŞ-ROL grubu (14 vaka):
    # bu alt-yapımcı unvanları düz "Yapımcı" değildir (KESİN-KURAL). Exec-Producer LİSTEDE YOK
    # (o gerçek yapımcı sayılır) — burada yalnız associate/co/line/uygulayıcı + yardımcı-üretim.
    "CO PRODUCER", "COPRODUCER", "CO-PRODUCER", "ASSOCIATE PRODUCER", "SUPERVISING PRODUCER",
    "CONSULTING PRODUCER", "PRODUCTION SUPERVISOR", "UYGULAYICI YAPIMCI", "ORTAK YAPIMCI",
    "YARDIMCI YAPIMCI", "DIRECTEUR DE PRODUCTION", "PRODUCTEUR ASSOCIE", "PRODUCTEUR EXECUTIF DELEGUE",
    "COPRODUZIONE", "PRODUTTORE ASSOCIATO", "PRODUCTOR ASOCIADO", "PRODUCTOR EJECUTIVO ASOCIADO",
    "PRODUKTIONSLEITUNG", "AUFNAHMELEITUNG",   # DE yapım-yönetimi
    # crew alt-rol garble/dil varyantları (cast CREW-SIZINTISI destek):
    "SESLENDIRME YONETMENI", "DUBLAJ YONETMENI", "COLLABORATEURS", "TRUCCATORE",
    "FIREARMS", "ISPOLNITELI", "STUNT COORDINATOR", "STUNT",
]

TABLO = {
    "LATIN":  {"YONETMEN": _LATIN_YONETMEN, "HARIC": _LATIN_HARIC},
    "KIRIL":  {"YONETMEN": ["РЕЖИСС", "ПОСТАНОВЩИК"],
               "HARIC":    ["АССИСТЕНТ", "ПОМОЩНИК", "ВТОРОЙ", "ХУДОЖНИК", "ОПЕРАТОР"]},
    "ARAP":   {"YONETMEN": ["کارگردان", "مخرج", "اخراج"],
               "HARIC":    ["دستیار", "مساعد", "فیلمبرداری"]},
    "IBRANI": {"YONETMEN": ["במאי", "בימוי"],
               "HARIC":    ["עוזר", "משנה", "צילום"]},
    "YUNAN":  {"YONETMEN": ["ΣΚΗΝΟΘΕΤ"],
               "HARIC":    ["ΒΟΗΘΟΣ", "ΦΩΤΟΓΡΑΦΙΑ"]},
    "HANGUL": {"YONETMEN": ["감독", "연출"],
               "HARIC":    ["조감독", "촬영감독", "미술감독", "음악감독"]},
    "CJK":    {"YONETMEN": ["导演", "導演", "監督"],
               "HARIC":    ["副导演", "助理导演", "执行导演", "撮影監督", "美術監督"]},
}

# unicodedata karakter adının İLK sözcüğü -> kanonik betik etiketi. TABLO'da olmayan
# bir betik de dönebilir (örn. "THAI") — rol_esles() bunu görünürlük olayıyla loglar (§3.5).
_BETIK_ESLE = {
    "LATIN": "LATIN",
    "CYRILLIC": "KIRIL",
    "ARABIC": "ARAP",
    "HEBREW": "IBRANI",
    "GREEK": "YUNAN",
    "HANGUL": "HANGUL",
    "CJK": "CJK",
    "KATAKANA": "CJK",
    "HIRAGANA": "CJK",
}


def _betik_karakter(ch: str) -> str:
    """Tek bir karakterin betiği (unicodedata karakter adının ilk sözcüğü). Harf
    değilse veya adlandırılamıyorsa boş string döner (sayıma katılmaz)."""
    if not ch.isalpha():
        return ""
    try:
        ad = unicodedata.name(ch)
    except ValueError:
        return ""
    ilk = ad.split(" ", 1)[0]
    return _BETIK_ESLE.get(ilk, ilk)


def betik_bul(s: str) -> str:
    """Satırın baskın betiği. Harf olmayan karakterler sayılmaz.
    Dönüş: LATIN | KIRIL | ARAP | IBRANI | YUNAN | HANGUL | CJK | BOS (bilinmeyen
    betikler için kendi Unicode etiketi, örn. 'THAI' — TABLO'da olması gerekmez)."""
    sayim: dict[str, int] = {}
    for ch in (s or ""):
        b = _betik_karakter(ch)
        if b:
            sayim[b] = sayim.get(b, 0) + 1
    if not sayim:
        return "BOS"
    return max(sayim.items(), key=lambda kv: kv[1])[0]


def _bosluk_logla(betik: str, ornek: str) -> None:
    _log.warning("rol_tablosu_bosluk %r", {"betik": betik, "ornek": ornek[:40]})


# ── LATIN eşleşmesi: credit_role_lexicon.norm()/_match_head()/_has_excl() ile
# AYNI algoritma (kelime-sınırlı: eşit / +" " ile başlar / " "+ ile biter — düz
# substring DEĞİL). §6.1 sıfır-regresyon güvencesi buradan gelir. Tek fark: Latin-
# genişletilmiş harfler (§3.2 istisnası) NFKD-öncesi ayrıca çevrilir.
_LATIN_EK_CEVIRI = str.maketrans({"đ": "D", "Đ": "D", "ð": "D", "Ð": "D"})


def _norm_latin(s: str) -> str:
    s = (s or "").replace("ı", "i").replace("İ", "i")
    s = s.translate(_LATIN_EK_CEVIRI)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    s = re.sub(r"[^A-Z ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _baslik_esles(n: str, basliklar: list[str]) -> bool:
    """Satır (norm'lu) bu başlıklardan biriyle EŞİT mi / BAŞLIYOR mu / BİTİYOR mu."""
    return any(n == b or n.startswith(b + " ") or n.endswith(" " + b) for b in basliklar)


# ── KIRIL/YUNAN: kök-önek eşleşme (bükünlü diller). Rusça ё/е katlaması + büyük
# harfe çevirme (Yunanca final sigma ς→Σ Python'da doğru çalışır, §3.3).
_KIRIL_YO_KATLA = str.maketrans({"ё": "е", "Ё": "Е"})


def _fold_kiril(s: str) -> str:
    return (s or "").translate(_KIRIL_YO_KATLA).upper()


def _fold_yunan(s: str) -> str:
    return (s or "").upper()


def rol_esles(s: str, tur: str = "YONETMEN", haric_uygula: bool = True) -> bool:
    """Satır bu rol türüne uyuyor mu. Betiği kendisi bulur (unicodedata, FAZ-2).
    haric_uygula=False → HARIC listesi atlanır (KOBE onset çapası için — 'yardımcı
    yönetmen' de jeneriktir). haric_uygula=True → isim çıkarma hattı (alt-roller
    yönetmen SAYILMAZ)."""
    betik = betik_bul(s)
    if betik == "BOS":
        return False
    grup = TABLO.get(betik)
    if grup is None:
        _bosluk_logla(betik, s or "")
        return False
    hedef = grup.get(tur, [])
    haric = grup.get("HARIC", [])

    if betik == "LATIN":
        n = _norm_latin(s)
        if not n:
            return False
        # HARIC: credit_role_lexicon._has_excl ile BİREBİR — tam-kelime DEĞİL, düz
        # substring ("GORUNTU" ⊂ "GORUNTU YONETMENI").
        if haric_uygula and any(h in n for h in haric):
            return False
        # YONETMEN: credit_role_lexicon._match_head ile BİREBİR — kelime-sınırlı
        # (eşit / +" " ile başlar / " "+ ile biter), düz substring DEĞİL.
        return _baslik_esles(n, hedef)

    if betik in ("KIRIL", "YUNAN"):
        n = _fold_kiril(s) if betik == "KIRIL" else _fold_yunan(s)
        if haric_uygula and any(h in n for h in haric):
            return False
        return any(h in n for h in hedef)

    # ARAP, IBRANI, HANGUL, CJK — alt-dize eşleşmesi, \b YOK (boşluksuz betikler
    # dahil), harf durumu YOK.
    n = s or ""
    if haric_uygula and any(h in n for h in haric):
        return False
    return any(h in n for h in hedef)

