"""OCR kutu parcalarini gorsel satira toplar.

NEDEN: DeepSeek grounding kutu basina metin dondurur — 'Audie' ve 'MURPHY'
ayri kutulardir. LeBron ve Jordan ise birlestirilmis satir uretir. Uc okuyucu
karsilastirilamaz birimdeydi; uzlastirma bu yuzden calisamiyordu (olculdu
2026-08-19: ham uzlasma %26,3, ama bu sayi birim uyusmazligini olcuyordu).

Toplama Nash'in ICINDE yapilir: kendi ciktisinin biriminden kule sorumludur.

DEGISMEZ: parca bbox'lari kaybolmaz, 'bilesenler' altinda korunur — kontrol
kuyrugu gerekirse parcaya inebilmeli.
"""
from __future__ import annotations

from typing import Any


def _kutu(satir: dict[str, Any]) -> tuple[str, list[int]] | None:
    """Satirin ilk gecerli (asset_id, bbox) ciftini dondur; yoksa None."""
    for kanit in satir.get("evidence") or []:
        bbox = kanit.get("bbox")
        asset = kanit.get("asset_id")
        if asset and isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            return str(asset), [int(v) for v in bbox]
    return None


def _dikey_ortusme(a: list[int], b: list[int]) -> float:
    """Iki kutunun dikey ortusmesi / KUCUK olanin yuksekligi."""
    ust, alt = max(a[1], b[1]), min(a[3], b[3])
    if alt <= ust:
        return 0.0
    kucuk = min(a[3] - a[1], b[3] - b[1])
    return (alt - ust) / kucuk if kucuk > 0 else 0.0


def topla(lines: list[dict[str, Any]], *, esik: float = 0.5) -> list[dict[str, Any]]:
    """Ayni asset uzerinde dikeyde ortusen kutulari tek satira topla.

    Bbox'i olmayan satir gruplanamaz ve OLDUGU GIBI gecer — dusurulmez.
    """
    gruplar: list[dict[str, Any]] = []
    for satir in lines:
        yer = _kutu(satir)
        if yer is None:
            gruplar.append({"asset": None, "uyeler": [satir], "kutu": None})
            continue
        asset, bbox = yer
        for grup in gruplar:
            if (grup["asset"] == asset and grup["kutu"] is not None
                    and _dikey_ortusme(grup["kutu"], bbox) >= esik):
                grup["uyeler"].append(satir)
                k = grup["kutu"]
                grup["kutu"] = [min(k[0], bbox[0]), min(k[1], bbox[1]),
                                max(k[2], bbox[2]), max(k[3], bbox[3])]
                break
        else:
            gruplar.append({"asset": asset, "uyeler": [satir], "kutu": list(bbox)})

    cikti: list[dict[str, Any]] = []
    for sira, grup in enumerate(gruplar):
        uyeler = grup["uyeler"]
        if len(uyeler) == 1:
            tek = dict(uyeler[0])
            tek["order"] = sira
            tek["line_id"] = f"line-{sira:06d}"
            cikti.append(tek)
            continue
        uyeler = sorted(uyeler, key=lambda s: (_kutu(s) or ("", [0, 0, 0, 0]))[1][0])
        metin = " ".join(u["raw_text"] for u in uyeler if u.get("raw_text"))
        ornek = dict(uyeler[0]["evidence"][0])
        ornek["bbox"] = grup["kutu"]
        cikti.append({"line_id": f"line-{sira:06d}", "order": sira,
                      "raw_text": metin, "normalized_text": metin.upper(),
                      "source_label": uyeler[0].get("source_label"),
                      "evidence": [ornek],
                      "bilesenler": [dict(u) for u in uyeler]})
    return cikti
