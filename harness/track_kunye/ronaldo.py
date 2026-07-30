"""RONALDO — İbrahimovic (master) × Messi (frame) çapraz-denetim ghost katmanı.

Spec: docs/superpowers/specs/2026-07-30-ronaldo-design.md
Gölge mod: üretim künyesine DOKUNMAZ; birleşik künye + fark raporu + güven
bandı yan dosya üretir. Saf metin-işlem — OCR çağırmaz.
"""
from __future__ import annotations

import unicodedata

_TR = str.maketrans({"ı": "i", "İ": "i", "I": "i"})


def fold_tr(s: str) -> str:
    """Türkçe-güvenli normalizasyon: ı/İ/I→i, aksan sök, küçült, boşluk tekle."""
    s = s.translate(_TR).lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join("".join(c if (c.isalnum() or c.isspace()) else " " for c in s).split())


def duzenle_mesafe(a: str, b: str, sinir: int) -> int:
    """Sınırlı Levenshtein; sınır aşılırsa erken çıkar (sinir+1 döner)."""
    if abs(len(a) - len(b)) > sinir:
        return sinir + 1
    onceki = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        simdiki = [i]
        en_az = i
        for j, cb in enumerate(b, 1):
            v = min(onceki[j] + 1, simdiki[-1] + 1, onceki[j - 1] + (ca != cb))
            simdiki.append(v)
            en_az = min(en_az, v)
        if en_az > sinir:
            return sinir + 1
        onceki = simdiki
    return onceki[-1]


def _max_edit(n: int) -> int:
    return 0 if n < 5 else max(1, n // 5)


def token_esle(a: str, b: str, kb_tok: set[str]) -> bool:
    """Uzunluk-ölçekli fuzzy + KB-çakışma kuralı (konsey)."""
    fa, fb = fold_tr(a), fold_tr(b)
    if fa == fb:
        return True
    if fa in kb_tok and fb in kb_tok:
        return False          # iki ayrı gerçek isim — birleştirme YOK
    sinir = min(_max_edit(len(fa)), _max_edit(len(fb)))
    if sinir == 0:
        return False
    return duzenle_mesafe(fa, fb, sinir) <= sinir


def ic_dedup(satirlar: list[str]) -> list[str]:
    """Kol içi fold-bazlı tekilleştirme; ilk görülen sıra korunur."""
    gorulen: set[str] = set()
    cikti = []
    for s in satirlar:
        f = fold_tr(s)
        if not f or f in gorulen:
            continue
        gorulen.add(f)
        cikti.append(s)
    return cikti


def garble_mi(satir: str) -> bool:
    """Slit çift-basımı / tekrar-desenli çöp satır tespiti (Nemotron #1)."""
    f = fold_tr(satir)
    kelimeler = f.split()
    # ardışık kelime-blok tekrarı: ilk yarı == ikinci yarı
    if len(kelimeler) >= 2 and len(kelimeler) % 2 == 0:
        yarim = len(kelimeler) // 2
        if kelimeler[:yarim] == kelimeler[yarim:]:
            return True
    # 40+ karakter ve baskın 3-gram tekrarı
    duz = f.replace(" ", "")
    if len(duz) > 40:
        gramlar: dict[str, int] = {}
        for i in range(len(duz) - 2):
            g = duz[i:i + 3]
            gramlar[g] = gramlar.get(g, 0) + 1
        if max(gramlar.values()) >= len(duz) // 6:
            return True
    return False


def halusinasyon_mu(satir: str, kb_tok: set[str]) -> bool:
    """deepseek sahne-betimleme/halüsinasyon adayı (konsey #6)."""
    s = satir.strip()
    if s.startswith("[") or s.startswith("("):
        return True
    kelimeler = fold_tr(s).split()
    if len(kelimeler) > 8 and not any(k in kb_tok for k in kelimeler):
        return True
    return False
