#!/usr/bin/env python3
"""Jordan config puanlayicisi — GT'ye karsi isim recall'u + Turkce harf sadakati.

Cagatay'in uc olcutu, uc sayi:
  recall     — GT'deki isimlerin kaci okundu (ISIM ATLAMA)
  tr_dogru   — Turkce harf tasiyan isimlerin kaci HARFI HARFINE dogru
  uydurma    — ciktida olup GT'de hic karsiligi olmayan satir orani

Kullanim:
  puanla.py <jordan.txt|jordan.json> --gt gt/26/gt.txt
  puanla.py --toplu out_dizini --gt gt/26/gt.txt      (kosu klasoru tarar)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

TR_HARF = set("çğıöşüÇĞİÖŞÜ")
# Turkce harflerin "bozulmus" ASCII karsiliklari — model bunlara dusuyorsa kaybediyoruz
DUSUS = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def norm(s: str) -> str:
    """Kiyas icin: bosluk sadelestir, buyut. Turkce harf KORUNUR."""
    s = unicodedata.normalize("NFC", s or "")
    s = re.sub(r"[^\w\sçğıöşüÇĞİÖŞÜ'.-]", " ", s, flags=re.U)
    return re.sub(r"\s+", " ", s).strip().upper()


def ascii_dus(s: str) -> str:
    """Turkce harfleri ASCII'ye dusur — 'bozulmus hali' kiyasi icin."""
    return norm(s).translate(DUSUS)


def gt_oku(yol: Path) -> tuple[list[str], list[str]]:
    """GT dosyasi → (tum_satirlar, turkce_harf_tasiyan_satirlar)."""
    satirlar = []
    for ham in yol.read_text(encoding="utf-8").splitlines():
        ham = ham.strip()
        if not ham or ham.startswith("#"):
            continue
        for parca in ham.split("\t"):
            parca = parca.strip()
            if parca:
                satirlar.append(parca)
    benzersiz = list(dict.fromkeys(satirlar))
    tr = [s for s in benzersiz if TR_HARF & set(s)]
    return benzersiz, tr


def cikti_oku(yol: Path) -> list[str]:
    if yol.suffix == ".json":
        d = json.loads(yol.read_text(encoding="utf-8"))
        return [s for b in d.get("bloklar", []) for s in b.get("satirlar", [])]
    return [s.strip() for s in yol.read_text(encoding="utf-8").splitlines() if s.strip()]


def en_iyi(hedef: str, havuz: list[str]) -> tuple[float, str]:
    n = norm(hedef)
    iyi, esles = 0.0, ""
    for c in havuz:
        r = SequenceMatcher(None, n, norm(c)).ratio()
        if r > iyi:
            iyi, esles = r, c
    return iyi, esles


def puanla(cikti: list[str], gt: list[str], gt_tr: list[str], esik=0.86) -> dict:
    bulunan, kacan = 0, []
    for g in gt:
        r, _ = en_iyi(g, cikti)
        if r >= esik:
            bulunan += 1
        else:
            kacan.append(g)

    # Turkce sadakat: harfi harfine dogru mu, yoksa ASCII'ye mi dusmus
    tr_tam, tr_dusuk, tr_kayip = 0, [], []
    ascii_havuz = [ascii_dus(c) for c in cikti]
    norm_havuz = [norm(c) for c in cikti]
    for g in gt_tr:
        if norm(g) in norm_havuz:
            tr_tam += 1
        elif ascii_dus(g) in ascii_havuz:
            tr_dusuk.append(g)          # okudu ama Turkce harfi bozdu
        else:
            r, _ = en_iyi(g, cikti)
            (tr_dusuk if r >= esik else tr_kayip).append(g)

    # Uydurma: ciktida olup GT'de karsiligi olmayan
    uydurma = [c for c in cikti if len(norm(c)) >= 3 and en_iyi(c, gt)[0] < 0.70]

    n_gt, n_tr = len(gt) or 1, len(gt_tr) or 1
    return {
        "gt_satir": len(gt), "okunan_satir": len(cikti),
        "bulunan": bulunan, "recall": round(bulunan / n_gt, 4),
        "tr_gt": len(gt_tr), "tr_tam": tr_tam,
        "tr_dogru": round(tr_tam / n_tr, 4),
        "tr_bozuk": len(tr_dusuk),
        "uydurma": len(uydurma),
        "uydurma_oran": round(len(uydurma) / (len(cikti) or 1), 4),
        "_kacan": kacan[:15], "_tr_bozuk": tr_dusuk[:15], "_uydurma": uydurma[:15],
    }


def skor(p: dict) -> float:
    """Tek sayi — Cagatay'in oncelik sirasi: atlamama > Turkce > uydurmama."""
    return round(0.5 * p["recall"] + 0.35 * p["tr_dogru"]
                 + 0.15 * (1 - min(p["uydurma_oran"], 1.0)), 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("hedef")
    ap.add_argument("--gt", required=True)
    ap.add_argument("--ayrinti", action="store_true")
    n = ap.parse_args()

    gt, gt_tr = gt_oku(Path(n.gt))
    p = puanla(cikti_oku(Path(n.hedef)), gt, gt_tr)
    p["skor"] = skor(p)
    if not n.ayrinti:
        p = {k: v for k, v in p.items() if not k.startswith("_")}
    print(json.dumps(p, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
