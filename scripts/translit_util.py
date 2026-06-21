# -*- coding: utf-8 -*-
"""translit_util — yabancı isim normalizasyonu (Kiril/Yunan/CJK→Latin + yabancı-aksan→ASCII).
Türkçe karakterler (ç ğ ı İ ö ş ü) KORUNUR. Latin-dışı çevrilemezse DOKUNULMAZ (sessiz silme yok).

Tek kaynak: hem erken-aşama (_pipe_ocr, sınıflandırmadan ÖNCE) hem son-net (credit_qc_block) bunu kullanır.
Böylece CEMİLE-tipi (Kiril rol-etiketi РЕЖИССЕР → REJISSOR) sınıflandırmaya Latin olarak girer."""
import re
import unicodedata

# Kiril → Latin (Rusça birincil + Ukraynaca/Sırpça). credit_qc_block ile BİREBİR aynı tablo.
_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ґ": "g", "д": "d", "е": "e", "ё": "yo",
    "є": "ye", "ж": "zh", "з": "z", "и": "i", "і": "i", "ї": "yi", "й": "y", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ђ": "dj", "ј": "j",
    "љ": "lj", "њ": "nj", "ћ": "c", "џ": "dz",
}
_GREEK = {
    "α": "a", "β": "v", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "i", "θ": "th",
    "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x", "ο": "o", "π": "p",
    "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "y", "φ": "f", "χ": "ch", "ψ": "ps",
    "ω": "o", "ά": "a", "έ": "e", "ή": "i", "ί": "i", "ό": "o", "ύ": "y", "ώ": "o", "ϊ": "i",
}
# Türkçe-özel harfler (yabancı-aksan fold ederken KORUNUR)
_TR_KEEP = set("çÇğĞıİöÖşŞüÜ")


def detect_script(text):
    """Baskın harf-sistemi: latin|cyrillic|greek|arabic|han|hangul|other."""
    counts = {}
    for ch in (text or ""):
        if not ch.isalpha():
            continue
        try:
            nm = unicodedata.name(ch)
        except ValueError:
            continue
        if "LATIN" in nm:
            s = "latin"
        elif "CYRILLIC" in nm:
            s = "cyrillic"
        elif "GREEK" in nm:
            s = "greek"
        elif "ARABIC" in nm:
            s = "arabic"
        elif "CJK" in nm or "HIRAGANA" in nm or "KATAKANA" in nm:
            s = "han"
        elif "HANGUL" in nm:
            s = "hangul"
        else:
            s = "other"
        counts[s] = counts.get(s, 0) + 1
    if not counts:
        return "latin"
    nonlatin = {k: v for k, v in counts.items() if k != "latin"}
    return "latin" if not nonlatin else max(nonlatin, key=nonlatin.get)


def _titlecase_tokens(s):
    return " ".join(t.capitalize() for t in s.split())


def transliterate(name, script=None):
    """Latin-dışı → Latin. Döner (latin, yontem). yontem: tablo|pypinyin|unidecode|FAILED."""
    sc = script or detect_script(name)
    if sc == "latin":
        return name, "latin"
    if sc == "cyrillic":
        out = "".join(_CYR.get(ch.lower(), ch if ch.isascii() else "") for ch in name)
        return _titlecase_tokens(out), "tablo"
    if sc == "greek":
        out = "".join(_GREEK.get(ch.lower(), ch if ch.isascii() else "") for ch in name)
        return _titlecase_tokens(out), "tablo"
    if sc == "han":
        try:
            from pypinyin import lazy_pinyin  # type: ignore
            return _titlecase_tokens(" ".join(lazy_pinyin(name))), "pypinyin"
        except Exception:
            pass
    try:
        from unidecode import unidecode  # type: ignore
        out = unidecode(name).strip()
        if out and any(c.isalpha() for c in out):
            return _titlecase_tokens(out), "unidecode"
    except Exception:
        pass
    return name, "FAILED"


def asciify_foreign(s):
    """Yabancı aksanlı Latin harfleri ASCII'ye indir; Türkçe (ç ğ ı İ ö ş ü) KORUNUR.
    Örn: José→Jose, Müller→Müller(ü Türkçe-uyumlu korunur), Peña→Pena."""
    res = []
    for ch in (s or ""):
        if ch.isascii() or ch in _TR_KEEP:
            res.append(ch)
        else:
            d = unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode()
            res.append(d if d else ch)
    return "".join(res)


def normalize_text(s):
    """Tek isim/satır normalize: Latin-dışı → Latin çevir, yabancı-aksan → ASCII, Türkçe korunur.
    Çevrilemezse (FAILED) DOKUNMA (sessiz silme yok → upstream KONTROL'e yollar)."""
    if not s:
        return s
    sc = detect_script(s)
    if sc == "latin":
        return asciify_foreign(s)
    out, yontem = transliterate(s, sc)
    if yontem == "FAILED":
        return s
    return asciify_foreign(out)
