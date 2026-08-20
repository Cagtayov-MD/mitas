"""Sıra-korumalı iki kanallı satır hizalaması."""
from __future__ import annotations

from dataclasses import dataclass

from .normalizasyon import near, normalize


@dataclass(frozen=True)
class Eslesme:
    a: dict | None
    b: dict | None
    sinif: str                 # ES, YAKIN, UZAK_ANCHOR, A_ONLY, B_ONLY


def _lcs_exact(a: list[dict], b: list[dict]) -> list[tuple[int, int]]:
    table = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) - 1, -1, -1):
        for j in range(len(b) - 1, -1, -1):
            equal = normalize(a[i]["text"]) == normalize(b[j]["text"]) and bool(normalize(a[i]["text"]))
            table[i][j] = (1 + table[i + 1][j + 1] if equal
                           else max(table[i + 1][j], table[i][j + 1]))
    pairs, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        if normalize(a[i]["text"]) and normalize(a[i]["text"]) == normalize(b[j]["text"]):
            pairs.append((i, j)); i += 1; j += 1
        elif table[i + 1][j] >= table[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs


def hizala(a: list[dict], b: list[dict], *, max_edits: int = 3) -> list[Eslesme]:
    """Exact LCS çapa, sonra dar yakın eşleşme.

    Uzak bir çift yalnız iki exact çapa arasındaki 1:1 boşluksa ilişkilendirilir;
    başta/sonda veya çoklu boşlukta zip yapılmaz.
    """
    a, b = sorted(a, key=lambda x: (x["order"], x["line_id"])), sorted(b, key=lambda x: (x["order"], x["line_id"]))
    anchors = _lcs_exact(a, b)
    output: list[Eslesme] = []

    def gap(ai: int, bi: int, an: int, bn: int, internal: bool) -> list[Eslesme]:
        ga, gb = a[ai + 1:an], b[bi + 1:bn]
        # Yakın eşleşmeler de LCS'tir; ilk boş B'yi seçmek çapraz çift kurar.
        table = [[0] * (len(gb) + 1) for _ in range(len(ga) + 1)]
        for i in range(len(ga) - 1, -1, -1):
            for j in range(len(gb) - 1, -1, -1):
                table[i][j] = (1 + table[i + 1][j + 1] if near(ga[i]["text"], gb[j]["text"], max_edits)
                               else max(table[i + 1][j], table[i][j + 1]))
        matched: list[tuple[int, int]] = []
        i = j = 0
        while i < len(ga) and j < len(gb):
            if near(ga[i]["text"], gb[j]["text"], max_edits):
                matched.append((i, j)); i += 1; j += 1
            elif table[i + 1][j] >= table[i][j + 1]:
                i += 1
            else:
                j += 1
        # Sonucu da monoton yaz: eslesenleri basa, eslesmeyenleri sona yığmak
        # okuma dosyasının satır sırasını bozuyordu.
        gap: list[Eslesme] = []
        cursor_a = cursor_b = 0
        for match_a, match_b in matched:
            gap.extend(Eslesme(left, None, "A_ONLY") for left in ga[cursor_a:match_a])
            gap.extend(Eslesme(None, right, "B_ONLY") for right in gb[cursor_b:match_b])
            gap.append(Eslesme(ga[match_a], gb[match_b], "YAKIN"))
            cursor_a, cursor_b = match_a + 1, match_b + 1
        gap.extend(Eslesme(left, None, "A_ONLY") for left in ga[cursor_a:])
        gap.extend(Eslesme(None, right, "B_ONLY") for right in gb[cursor_b:])
        # İki güçlü exact çapa arasındaki yalnız 1:1 uzak boşluk istisnası.
        if internal and len(ga) == len(gb) == 1 and gap == [Eslesme(ga[0], None, "A_ONLY"), Eslesme(None, gb[0], "B_ONLY")]:
            gap = [Eslesme(ga[0], gb[0], "UZAK_ANCHOR")]
        return gap

    ai = bi = -1
    for an, bn in anchors:
        output.extend(gap(ai, bi, an, bn, internal=(ai != -1)))
        output.append(Eslesme(a[an], b[bn], "ES"))
        ai, bi = an, bn
    output.extend(gap(ai, bi, len(a), len(b), internal=False))
    return output
