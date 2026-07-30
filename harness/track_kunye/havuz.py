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


ESIK_TABAN = 24   # yalnız geri-düşüş: fark verisi yetersizse


def film_esigi(farklar: list[int]) -> int:
    """Film-bazlı eşik: 1D-Otsu; bimodallik zayıfsa p25+2 (kaçırmamak önceliği).
    Kanıt: sabit eşik hayat-agaci'da (fark dili 6-25) havuzu 4 sayfaya düşürdü;
    Otsu'ya geçiş 40 sayfa / Farsça 19→227 satır getirdi (2026-07-30)."""
    if len(farklar) < 8:
        return ESIK_TABAN
    f = np.array(sorted(farklar), dtype=np.float64)
    en_iyi_esik, en_iyi_var = None, -1.0
    for t in range(int(f.min()) + 1, int(f.max())):
        sol, sag = f[f <= t], f[f > t]
        if len(sol) < 3 or len(sag) < 3:
            continue
        arasi = len(sol) * len(sag) * (sol.mean() - sag.mean()) ** 2
        if arasi > en_iyi_var:
            en_iyi_var, en_iyi_esik = arasi, t
    if en_iyi_esik is None:
        return max(2, int(np.percentile(f, 25)) + 2)
    sol, sag = f[f <= en_iyi_esik], f[f > en_iyi_esik]
    ayrim = (sag.mean() - sol.mean()) / (f.std() + 1e-6)
    if ayrim < 0.8:
        return max(2, int(np.percentile(f, 25)) + 2)
    return int(en_iyi_esik)


def temporal_median(griler: list[np.ndarray], pencere: int = 3) -> list[np.ndarray]:
    """Zaman-medyanı: kar/grén/interlace gibi kare-bağımsız gürültüyü İMZADAN
    siler (konsey: 'bunu en başa alın — kirli veride eşik çöp üretir').
    Yalnız SİNYAL hesabında kullanılır; okumaya orijinal kare gider."""
    if pencere < 2 or len(griler) < 2:
        return list(griler)
    yarim = pencere // 2
    out = []
    for i in range(len(griler)):
        a, b = max(0, i - yarim), min(len(griler), i + yarim + 1)
        out.append(np.median(np.stack(griler[a:b]), axis=0).astype(np.uint8))
    return out
