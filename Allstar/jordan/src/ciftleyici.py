"""Geçiş 2 — bloklardan rol→isim çiftleri. GÖRÜNTÜ GÖRMEZ.

Neden ayrı geçiş: tek istekte model rolü tutturmak için metni "düzeltmeye"
başlar; o an okuma hatasıyla eşleme hatası birbirine karışır ve hangisinin
bozuk olduğu ayrılamaz. Burada modele yalnız geçiş 1'in METNİ verilir.

SIZDIRMAZLIK KAPISI: çıkan her rol ve her isim, geçiş 1'in satırlarında
GERÇEKTEN geçmek zorundadır. Geçmiyorsa atılır ve sayılır. Model bu geçişte
yeni metin uyduramaz — uydurursa sessizce çıktıya değil, sayaca gider.

Bu dosya sözleşmeyi BİLMEZ.
"""
from __future__ import annotations

import re

from model import CiktiBozuk


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().upper()


def _metin(bloklar: list[dict]) -> str:
    parcalar = []
    for b in bloklar:
        parcalar.append("\n".join(b.get("satirlar", [])))
    return "\n\n".join(parcalar)


def _ayristir(ham: str) -> list[tuple[str, str]]:
    """`ROL<TAB>İSİM` satırlarını çöz. Sekme yoksa iki-nokta da kabul."""
    ciftler = []
    for satir in ham.splitlines():
        satir = satir.strip()
        if not satir:
            continue
        if "\t" in satir:
            rol, _, isim = satir.partition("\t")
        elif ":" in satir:
            rol, _, isim = satir.partition(":")
        else:
            continue
        rol, isim = rol.strip(), isim.strip()
        if rol and isim:
            ciftler.append((rol, isim))
    return ciftler


def ciftle(motor, bloklar: list[dict], cfg: dict) -> tuple[list[dict], dict]:
    """(ciftler, kanit) — kaynağı doğrulanmamış çift çıktıya giremez."""
    if not bloklar:
        return [], {"cift_sayisi": 0, "cift_eleme": 0}

    istem = cfg.get("istem", {}).get("ciftleme", "")
    try:
        ham = motor.sor(f"{istem}\n\n---\n{_metin(bloklar)}\n---")
    except CiktiBozuk:
        # Geçiş 2 çökerse geçiş 1'in metnini ÇÖPE ATMAYIZ: bloklar gerçek
        # okumadır, çiftler türev veridir. Boş çift + görünür sayaç.
        return [], {"cift_sayisi": 0, "cift_eleme": 0, "cift_ariza": 1}

    # satır -> blok no dizini (isim hangi blokta geçiyorsa oraya bağlanır)
    dizin: list[tuple[str, int]] = []
    for b in bloklar:
        for s in b.get("satirlar", []):
            dizin.append((_norm(s), b.get("no", 0)))
    havuz = " \n ".join(n for n, _ in dizin)

    ciftler, elenen = [], 0
    for rol, isim in _ayristir(ham):
        nrol, nisim = _norm(rol), _norm(isim)
        if nrol not in havuz or nisim not in havuz:
            elenen += 1                 # geçiş 1'de yoktu → uydurma, atılır
            continue
        blok = next((no for n, no in dizin if nisim in n), 0)
        ciftler.append({"rol": rol, "isim": isim, "blok": blok})

    return ciftler, {"cift_sayisi": len(ciftler), "cift_eleme": elenen}
