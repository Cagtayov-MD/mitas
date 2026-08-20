#!/usr/bin/env python3
"""Nash dökümünü elle doğrulanmış jenerik satırlarıyla sıraya duyarlı ölç."""
from __future__ import annotations

import argparse
import difflib
import json
import unicodedata
from pathlib import Path


def satirlari_oku(yol: Path) -> list[str]:
    if yol.suffix.lower() == ".json":
        belge = json.loads(yol.read_text(encoding="utf-8"))
        return [str(x.get("text", "")).strip()
                for x in belge.get("satirlar") or [] if str(x.get("text", "")).strip()]
    return [satir.strip() for satir in yol.read_text(encoding="utf-8").splitlines()
            if satir.strip() and not satir.lstrip().startswith("#")]


def taban(metin: str, *, compact: bool = False) -> str:
    ceviri = str.maketrans({"ı": "i", "İ": "i"})
    s = unicodedata.normalize("NFKD", (metin or "").translate(ceviri).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = " ".join("".join(c if (c.isalnum() or c.isspace()) else " "
                          for c in s).split())
    return s.replace(" ", "") if compact else s


def benzerlik(a: str, b: str) -> float:
    aa, bb = taban(a, compact=True), taban(b, compact=True)
    return difflib.SequenceMatcher(None, aa, bb).ratio() if aa and bb else 0.0


def hizala(gt: list[str], aday: list[str], esik: float = 0.78) -> list[dict]:
    """Sırayı bozmadan en yüksek toplam benzerlikli satır eşleşmesi."""
    n, m = len(gt), len(aday)
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    karar = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            secenek = [(dp[i - 1][j], "gt_atla"),
                       (dp[i][j - 1], "aday_atla")]
            oran = benzerlik(gt[i - 1], aday[j - 1])
            if oran >= esik:
                # Önce eşleşme sayısı, sonra yazım kalitesi: her eşleşme 2
                # puan; oran aynı sayıda eşleşme içindeki kaliteyi ayırır.
                secenek.append((dp[i - 1][j - 1] + 2.0 + oran, "esle"))
            dp[i][j], karar[i][j] = max(secenek, key=lambda x: x[0])
    sonuc = []
    i, j = n, m
    while i and j:
        k = karar[i][j]
        if k == "esle":
            sonuc.append({"gt_index": i - 1, "candidate_index": j - 1,
                          "gt": gt[i - 1], "candidate": aday[j - 1],
                          "similarity": round(benzerlik(
                              gt[i - 1], aday[j - 1]), 6)})
            i -= 1
            j -= 1
        elif k == "gt_atla":
            i -= 1
        else:
            j -= 1
    return list(reversed(sonuc))


def olc(gt: list[str], aday: list[str], esik: float = 0.78) -> dict:
    eslesmeler = hizala(gt, aday, esik)
    gt_eslesen = {x["gt_index"] for x in eslesmeler}
    aday_eslesen = {x["candidate_index"] for x in eslesmeler}
    kati = sum(gt[x["gt_index"]].casefold() == aday[x["candidate_index"]].casefold()
               for x in eslesmeler)
    taban_esit = sum(taban(gt[x["gt_index"]]) == taban(aday[x["candidate_index"]])
                     for x in eslesmeler)
    return {
        "gt_lines": len(gt), "candidate_lines": len(aday),
        "matched_lines": len(eslesmeler),
        "recall": round(len(eslesmeler) / len(gt), 6) if gt else None,
        "precision": round(len(eslesmeler) / len(aday), 6) if aday else None,
        "strict_equal": kati, "base_equal": taban_esit,
        "mean_similarity": round(sum(x["similarity"] for x in eslesmeler)
                                 / len(eslesmeler), 6) if eslesmeler else None,
        "missing": [satir for i, satir in enumerate(gt) if i not in gt_eslesen],
        "extra": [satir for i, satir in enumerate(aday) if i not in aday_eslesen],
        "matches": eslesmeler,
        "threshold": esik,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True, type=Path)
    ap.add_argument("--candidate", required=True, type=Path)
    ap.add_argument("--threshold", type=float, default=0.78)
    ap.add_argument("--output", type=Path)
    a = ap.parse_args(argv)
    rapor = olc(satirlari_oku(a.gt), satirlari_oku(a.candidate), a.threshold)
    metin = json.dumps(rapor, ensure_ascii=False, indent=2)
    if a.output:
        a.output.write_text(metin + "\n", encoding="utf-8")
    print(metin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
