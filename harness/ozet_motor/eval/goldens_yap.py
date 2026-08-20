# -*- coding: utf-8 -*-
"""ozet_motor altin-set uretici.

Database'deki her filmden (transkripti VE gercek Sonnet ozeti olan) bir golden satiri cikarir.
Referans = uretimde Sonnet'in ayni transkriptten urettigi ozet (_log.jsonl: ozet_completed).
Cikti: eval/goldens.jsonl  — versiyonlanir, kos.py bunu okur, ASLA calisma-ciktisi yazilmaz.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DB = Path("/home/cagatay/Programlar/mitas/Database")
OUT = Path(__file__).resolve().parent / "goldens.jsonl"
MIN_KELIME = 800   # bunun altindaki transkript = ASR basarisiz, motor sinavi degil

_OZET_BAS = re.compile(r"^-+\s*Özet\s*-+\s*$", re.MULTILINE)
_PLACEHOLDER = re.compile(r"placeholder|Ham transcript|çıkarılamadı|bulunamadı", re.IGNORECASE)


def _kunye_ozet(kunye: Path) -> str | None:
    """Kunye .txt'inin '--- Özet ---' bolumunu dondur (yoksa/placeholder ise None)."""
    try:
        metin = kunye.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001 — okunamayan kunye = golden degil
        return None
    parca = _OZET_BAS.split(metin)
    if len(parca) < 2:
        return None
    ozet = " ".join(parca[-1].split())
    if len(ozet.split()) < 20 or _PLACEHOLDER.search(ozet):
        return None
    return ozet


def _sonnet_mi(film: Path) -> bool:
    """_log.jsonl'de ozet_completed olayi var mi (= transkriptten uretildi, internetten degil)."""
    log = film / "_log.jsonl"
    if not log.exists():
        return False
    try:
        return '"ozet_completed"' in log.read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return False


def topla() -> list[dict]:
    satirlar = []
    for film in sorted(DB.iterdir()):
        if not film.is_dir():
            continue
        tr = next(iter(film.glob("asr/*/run/transcript_plain.txt")), None)
        if tr is None:
            continue
        kunye = next((p for p in film.glob("*.txt") if "teknik" not in p.name), None)
        if kunye is None:
            continue
        ref = _kunye_ozet(kunye)
        if not ref or not _sonnet_mi(film):
            continue
        metin = tr.read_text(encoding="utf-8", errors="ignore")
        # Cok kisa transkript = ASR cikarilamamis / kopya bozuk (bir filmde 4 kelime cikti).
        # Boyle bir kayittan ozet beklemek motoru degil veriyi olcer → altin-set disi.
        if len(metin.split()) < MIN_KELIME:
            continue
        satirlar.append({
            "id": film.name,
            "baslik": film.name.rsplit(" ", 1)[0],
            "transcript": str(tr),
            "transcript_kelime": len(metin.split()),
            "transcript_karakter": len(metin),
            "referans_sonnet": ref,
        })
    return satirlar


if __name__ == "__main__":
    g = topla()
    g.sort(key=lambda s: s["transcript_kelime"])
    OUT.write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in g) + "\n",
                   encoding="utf-8")
    kel = [s["transcript_kelime"] for s in g]
    print(f"{len(g)} golden → {OUT}")
    print(f"transkript kelime: min {min(kel)} · medyan {kel[len(kel)//2]} · max {max(kel)}")
