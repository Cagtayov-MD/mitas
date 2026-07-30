"""Havuz v2 — maks-verim kare seçicisi (spec: docs/superpowers/specs/2026-07-30-havuz-v2-design.md).

Saf görüntü-işleme: OCR yok, ağ yok. Gri kare listesi girer, seçilen kare
indeksleri + istatistik çıkar. Kaçırmamak > az sayfa."""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


def imza(gri: np.ndarray, boyut: int = 16) -> int:
    k = cv2.resize(gri, (boyut + 1, boyut), interpolation=cv2.INTER_AREA)
    bits = (k[:, 1:] > k[:, :-1]).astype(np.uint8).ravel()
    h = 0
    for b in bits:
        h = (h << 1) | int(b)
    return h


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


@dataclass
class HavuzIstatistik:
    kare_sayisi: int
    fark_medyani: float
    fark_iqr: float
    esik: int
    birikim_esigi: int
    grup_sayisi: int
    alarm: bool


@dataclass
class HavuzSonucu:
    sayfalar: list[int] = field(default_factory=list)
    istatistik: HavuzIstatistik | None = None
