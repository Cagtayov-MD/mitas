# -*- coding: utf-8 -*-
"""MITAS özet kalite kapısı + deterministik onarım.

testas (pdf-mitas) KAPALI-DÖNGÜ özet stratejisinin MITAS'a taşınan çekirdeği.
Kaynak (davranış BİREBİR portlanmıştır, golden testlerle sabitlenir → tests/test_ozet_kalite.py):
  • testas/pdf-mitas/pdf_auditor.py            → ascii_fold, canonical, summary_errors, BAD_SUMMARY_PATTERNS
  • testas/pdf-mitas/pilot10_xml_to_pdf.py     → repair_generated_summary + uzunluk/final yardımcıları

İki işi vardır:
  • summary_errors(text) -> list[str]  : KALİTE KAPISI. Liste boşsa özet geçerli. Doluysa
    kelime-sayısı / noktalama / noktalı-virgül / LLM-dolgu-artığı hatalarını döner.
  • repair_generated_summary(text)     : DETERMİNİSTİK ONARIM. <think>/etiket temizler,
    ';' -> '.', noktalama ile bitmeyen kesik son cümleyi atar, outcome-fiilli son cümleye
    'Finalde' önekler, SUMMARY_WORD_LIMIT kelime sınırını uygular.

ÇIKTI METNİNİ büyük harfe/Latin'e ÇEVİRMEZ — o iş çağıranda (_latin_only + nn.tr_upper_prose).
Buradaki ascii_fold/canonical YALNIZ iç kalıp-eşleşmesi içindir (outcome/bad-pattern taraması).
"""
from __future__ import annotations

import re
import unicodedata

# ── Uzunluk kapısı sabitleri (pdf_auditor.py) ────────────────────────────────
SUMMARY_WORD_MIN = 32
# 32 hedef; 24 mutlak alt sınır. 24-31 ancak anlamı tamamlayan, açık-sonuçlu ve tam-cümleli
# kısa format olarak kabul edilir. 10-20 kelimelik kırpıntılar geçmez.
SUMMARY_WORD_CONCISE_MIN = 24
SUMMARY_WORD_LIMIT = 65
SUMMARY_WORD_RE = re.compile(r"[0-9A-Za-zÇĞİÖŞÜçğıöşü]+(?:'[A-Za-zÇĞİÖŞÜçğıöşü]+)?")

FINAL_CUE_RE = re.compile(r"\b(SONUNDA|FILM|BITER|BITISINDE|FINALDE)\b")
OUTCOME_RE = re.compile(
    r"\b("
    r"OLDURUR|OLDURULUR|OLUR|VURULUR|VURUR|KURSUNA|DIZIL|KURTARIR|KURTULUR|"
    r"KAZANIR|YENILIR|YENER|ALT EDER|TESLIM OLUR|KABUL EDER|SECER|BIRAKIR|VERIR|"
    r"DONER|AYRILIR|BIRLESIR|KAVUSUR|IYILESIR|BASLAR|KALIR|KACAR|KACMASINI|"
    r"YAKALAR|YAKALANIR|SAGLAR|KURAR|GECER|FEDA EDER|FEDA|BULUNAMAZ|BULUNUR|"
    r"ENGELLER|ENGELLENIR|ONLER|ONLENIR|COKERTIR|COKER|YOK EDER|DUSER|DUSURUR|VAZGECER|"
    r"KAYBEDER|TUTUKLANIR|EVLENIR|ACIGA CIKARIR|ORTAYA CIKARIR|PAYLASIR|"
    r"ALIR|BULUR|ELDE EDER|BOMBALAR|BOMBALANIR|"
    r"KABUL EDILIR|KABUL GORUR|TAMAMLAR|BASARIR|"
    r"UZAKLASIR|GIDER|KACIR|KACIRIR|KURTARILIR|MAHKUM EDER|MAHKUM OLUR|"
    r"CEZALANDIRIR|DURDURUR|DURDURULUR|OLDUGU ANLASILIR|ANLASILIR|OGRENIR|OGRENILIR|"
    r"EDILIR|EDILIRKEN|ILERLER|ILERLIYOR|VARIR|SONA ERER|YURUR|"
    r"KAYBOLUR|BATAR|OLDUGUNU GOSTERIR|GOSTERIR|"
    r"KORU|HATIRLA|SEVER|TERK EDER|INTIHAR|ITIRAF EDER|PISMAN|KOVAR|ASILIR|IDAM|"
    r"KAVUSUR|GERI DONER|HAYATTA KALIR|PES EDER|BARISIR|VEDA EDER|INTIKAM"
    r")[A-Z]{0,4}\b"
)

# LLM-dolgu / uydurma sinyalleri — bunlar gerçekten kötü özeti gösterir (pdf_auditor.py).
BAD_SUMMARY_PATTERNS = (
    r"\bDIKKAT CEKICI\b",
    r"\bBEKLENTI ICERIYOR\b",
    r"\bHISSETMEK MUMKUN\b",
    r"\bDERIN BIR YOLCULUK\b",
    r"\bPLAN UYGULAMAK ZORUNDADIR\b",
    r"\bYARDIM ETMEYI KABUL EDER ANCAK\b",
    r"\bYETERSIZ KAYNAK\b",
)


# ── Metin normalizasyon / kalıp-eşleşme yardımcıları ─────────────────────────
def ascii_fold(text: str) -> str:
    special = {
        "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D",
        "þ": "th", "Þ": "Th", "ß": "ss", "æ": "ae", "Æ": "Ae",
        "œ": "oe", "Œ": "Oe", "ð": "d", "Ð": "D",
        "ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G",
        "ü": "u", "Ü": "U", "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
    }
    out: list[str] = []
    for ch in text or "":
        if ch in special:
            out.append(special[ch])
            continue
        dec = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        out.append(dec if dec.isascii() else ch)
    return "".join(out)


def canonical(text: str) -> str:
    """Türkçe/aksanlı metni ASCII BÜYÜK harfe katla — YALNIZ iç kalıp-eşleşmesi için."""
    text = ascii_fold(text or "")
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip().upper()


def normalize_summary_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\r", " ").replace("\n", " ")).strip()


def summary_word_count(text: str) -> int:
    return len(SUMMARY_WORD_RE.findall(text or ""))


def split_sentences(text: str) -> list[str]:
    text = normalize_summary_text(text)
    if not text:
        return []
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def has_spoiler_final(text: str) -> bool:
    """Son cümle somut sonuç taşıyor mu? 'Finalde/Sonunda' ipucu ya da outcome-fiil (öldürür,
    kazanır, feda eder…) → True. Beyaz-liste tek başına kırılgan, ipucu + fiil birlikte bakılır."""
    sentences = split_sentences(text)
    if not sentences:
        return False
    last = canonical(sentences[-1])
    return bool(FINAL_CUE_RE.search(last) or OUTCOME_RE.search(last))


def concise_summary_is_complete(text: str) -> bool:
    """24-31 kelimeyi YALNIZ yapısal olarak tam (2-4 tam cümle + spoiler final) olduğunda kabul et."""
    wc = summary_word_count(text)
    if not SUMMARY_WORD_CONCISE_MIN <= wc < SUMMARY_WORD_MIN:
        return False
    if ";" in text or text[-1:] not in ".!?":
        return False
    parts = split_sentences(text)
    if not 2 <= len(parts) <= 4:
        return False
    if any(part[-1:] not in ".!?" for part in parts):
        return False
    return has_spoiler_final(text)


def summary_length_ok(text: str) -> bool:
    wc = summary_word_count(text)
    if SUMMARY_WORD_MIN <= wc <= SUMMARY_WORD_LIMIT:
        return True
    return concise_summary_is_complete(text)


def enforce_summary_limit(text: str, limit: int = SUMMARY_WORD_LIMIT) -> str:
    """Sınırı aşan özeti ilk+son cümleyi koruyarak kırp; hâlâ aşıyorsa ValueError."""
    text = normalize_summary_text(text)
    if summary_word_count(text) <= limit:
        return text
    sentences = split_sentences(text)
    if len(sentences) >= 3:
        last = sentences[-1]
        kept = [sentences[0]]
        for middle in sentences[1:-1]:
            candidate = " ".join(kept + [middle, last])
            if summary_word_count(candidate) <= limit:
                kept.append(middle)
        text = " ".join(kept + [last])
    if summary_word_count(text) > limit:
        raise ValueError(f"Özet {limit} kelime sınırını aşıyor: {summary_word_count(text)}")
    return text


# ── Onarım ───────────────────────────────────────────────────────────────────
def strip_summary_output(text: str) -> str:
    text = normalize_summary_text(text)
    text = re.sub(r"(?is)<think>.*?</think>", " ", text)
    text = normalize_summary_text(text)
    text = re.sub(r"^(özet|ozet)\s*:\s*", "", text, flags=re.I)
    text = re.sub(r"\bKelime sayısı\s*:.*$", "", text, flags=re.I)
    text = re.sub(r"\bKullanılan karakter adları\s*:.*$", "", text, flags=re.I)
    return normalize_summary_text(text.strip(" \"'`"))


def repair_generated_summary(text: str) -> str:
    text = normalize_summary_text(strip_summary_output(text).replace(";", "."))
    # Kesik (noktalama ile bitmeyen) son cümleyi at — geriye yeterli tam-cümle kalıyorsa.
    if text and text[-1] not in ".!?":
        _sents = split_sentences(text)
        if len(_sents) >= 2:
            _trimmed = normalize_summary_text(" ".join(_sents[:-1]))
            if summary_length_ok(_trimmed):
                text = _trimmed
    sentences = split_sentences(text)
    if sentences:
        last = sentences[-1]
        c_last = canonical(last)
        if not FINAL_CUE_RE.search(c_last) and OUTCOME_RE.search(c_last):
            sentences[-1] = "Finalde " + last[0].lower() + last[1:] if last else last
            text = normalize_summary_text(" ".join(sentences))
    if summary_word_count(text) > SUMMARY_WORD_LIMIT:
        try:
            text = enforce_summary_limit(text)
        except Exception:  # noqa: BLE001 — kırpılamadıysa metni olduğu gibi bırak
            pass
    return text


# ── Kalite kapısı (public) ───────────────────────────────────────────────────
def summary_errors(summary: str) -> list[str]:
    """Özet kalite kapısı (testas summary_errors portu). Liste BOŞ ise özet geçerli.

    Somut final/spoiler ZORUNLU DEĞİL ('elimizdekinin en iyisi': kaynakta sonuç yoksa
    zorlanmaz → uydurma-final riski > eksik-final). Kapı word/punctuation/meta-artık ile sınırlı.
    """
    errors: list[str] = []
    text = normalize_summary_text(summary)
    c = canonical(text)
    wc = summary_word_count(text)
    if wc < SUMMARY_WORD_MIN and not concise_summary_is_complete(text):
        errors.append(
            f"Özet kısa-format kapısını geçemedi: {wc} kelime "
            f"({SUMMARY_WORD_CONCISE_MIN}-{SUMMARY_WORD_MIN - 1} kelime için 2-4 tam cümle ve açık sonuç gerekli)"
        )
    if wc > SUMMARY_WORD_LIMIT:
        errors.append(f"Özet {SUMMARY_WORD_LIMIT} kelime sınırını aşıyor: {wc}")
    if ";" in text:
        errors.append("Özet noktalı virgül içeriyor")
    if text and text[-1] not in ".!?":
        errors.append("Özet tamamlanmış noktalama ile bitmiyor")
    for pattern in BAD_SUMMARY_PATTERNS:
        if re.search(pattern, c):
            errors.append(f"Özet kaynak/metin artığı veya zayıf ifade içeriyor: {pattern}")
            break
    if not split_sentences(text):
        errors.append("Özet boş")
    return errors
