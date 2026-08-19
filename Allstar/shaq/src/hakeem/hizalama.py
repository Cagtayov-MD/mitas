"""Exact capalar + agirlikli yakin esleme ile conflict-group olusturma."""
from __future__ import annotations

from typing import Any, Callable

from src.normalizasyon import distance, near


def _ordered_matches(a: list[dict[str, Any]], b: list[dict[str, Any]],
                     score: Callable[[dict[str, Any], dict[str, Any]], int]) -> list[tuple[int, int]]:
    table = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) - 1, -1, -1):
        for j in range(len(b) - 1, -1, -1):
            pair_score = score(a[i], b[j])
            take = pair_score + table[i + 1][j + 1] if pair_score > 0 else -1
            table[i][j] = max(take, table[i + 1][j], table[i][j + 1])
    result: list[tuple[int, int]] = []
    i = j = 0
    while i < len(a) and j < len(b):
        pair_score = score(a[i], b[j])
        take = pair_score + table[i + 1][j + 1] if pair_score > 0 else -1
        if pair_score > 0 and table[i][j] == take:
            result.append((i, j)); i += 1; j += 1
        elif table[i + 1][j] >= table[i][j + 1]:
            i += 1
        else:
            j += 1
    return result


def _center_y(line: dict[str, Any]) -> float | None:
    evidence = line.get("evidence") or []
    if not evidence:
        return None
    bbox = evidence[0].get("bbox", {})
    height = evidence[0].get("_asset_height")
    if not height:
        return None
    return (bbox["y0"] + bbox["y1"]) / (2.0 * height)


def _exact_score(left: dict[str, Any], right: dict[str, Any]) -> int:
    return 100 if left.get("normalized") and left["normalized"] == right.get("normalized") else 0


def _near_score(left: dict[str, Any], right: dict[str, Any], max_edits: int) -> int:
    if not near(left.get("text", ""), right.get("text", ""), max_edits):
        return 0
    score = 100 - 10 * distance(left["normalized"], right["normalized"])
    if left.get("resolved_role") == right.get("resolved_role") != "ROL_BELIRSIZ":
        score += 8
    ly, ry = _center_y(left), _center_y(right)
    if ly is not None and ry is not None and abs(ly - ry) <= 0.15:
        score += 4
    return max(1, score)


def _kind(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> str:
    nonempty = [line for line in a + b if line.get("normalized")]
    if not nonempty:
        return "UNREAD"
    if a and b and len(a) == len(b) == 1:
        return "FAR_CONFLICT"
    if a and b:
        return "STRUCTURAL_CONFLICT"
    return "SINGLE_CHANNEL"


def hizala(a: list[dict[str, Any]], b: list[dict[str, Any]], *, max_edits: int = 3) -> list[dict[str, Any]]:
    """Her belirsiz bolgeyi tek karar birimi yapar; A_ONLY/B_ONLY'e bolmez."""
    anchors = _ordered_matches(a, b, _exact_score)
    groups: list[dict[str, Any]] = []

    def add(kind: str, left: list[dict[str, Any]], right: list[dict[str, Any]]) -> None:
        if left or right:
            groups.append({"kind": kind, "a": left, "b": right})

    def add_unmatched(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> None:
        # Metinsiz bölgelerin her biri ayrı karar birimidir. A/B'deki aynı sıra
        # iki görünüm olarak eşlenir; farklı okunursa kontrol zaten çözümlemez.
        if left or right:
            all_blank = all(not line.get("normalized") for line in left + right)
            if all_blank:
                common = min(len(left), len(right))
                for index in range(common):
                    add("UNREAD", [left[index]], [right[index]])
                for line in left[common:]:
                    add("UNREAD", [line], [])
                for line in right[common:]:
                    add("UNREAD", [], [line])
                return
        add(_kind(left, right), left, right)

    def gap(ga: list[dict[str, Any]], gb: list[dict[str, Any]]) -> None:
        matches = _ordered_matches(ga, gb, lambda x, y: _near_score(x, y, max_edits))
        ai = bi = 0
        for an, bn in matches:
            add_unmatched(ga[ai:an], gb[bi:bn])
            add("NEAR_CONFLICT", [ga[an]], [gb[bn]])
            ai, bi = an + 1, bn + 1
        add_unmatched(ga[ai:], gb[bi:])

    ai = bi = 0
    for an, bn in anchors:
        gap(a[ai:an], b[bi:bn])
        add("CONSENSUS", [a[an]], [b[bn]])
        ai, bi = an + 1, bn + 1
    gap(a[ai:], b[bi:])
    return groups
