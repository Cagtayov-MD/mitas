# -*- coding: utf-8 -*-
"""Kişi-adı eşleştirmesinde kullanılan ortak Latin→ASCII temel katlama.

NFKD bazı Latin harflerini (özellikle ð/þ/ø/ł) ASCII karşılığına ayırmaz;
``encode(..., 'ignore')`` bu harfleri tamamen düşürür.  Bu modül, ilgili
okuyucu ve KB çapraz-kontrol yollarının aynı ön-eşlemeyi kullanmasını sağlar.
"""
from __future__ import annotations

import unicodedata


_SPECIAL_LATIN = str.maketrans({
    "ð": "d", "Ð": "D",
    "þ": "th", "Þ": "TH",
    "ø": "o", "Ø": "O",
    "ł": "l", "Ł": "L",
    "đ": "d", "Đ": "D",
    "æ": "ae", "Æ": "AE",
    "œ": "oe", "Œ": "OE",
    "ß": "ss", "ẞ": "SS",
})


def latin_ascii(value) -> str:
    """Metni kayıpsız-öngörülebilir biçimde küçük ASCII Latin metne katla.

    Noktalama/boşluk politikası çağırana aittir; burada yalnız karakter
    dönüşümü yapılır. Böylece farklı tüketiciler aynı ad katlamasını kullanır.
    """
    text = str(value or "").translate(_SPECIAL_LATIN)
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
