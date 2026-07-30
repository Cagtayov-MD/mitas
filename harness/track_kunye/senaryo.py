"""Sentetik jenerik senaryoları — havuz testlerinin kare fabrikası.
Konsey patlama senaryoları (kar, fade, flaş, pan, konfeti, interlace) burada üretilir.
Kareler GRİ uint8, varsayılan 200x160 (hız için küçük)."""
from __future__ import annotations

import cv2
import numpy as np

RNG = np.random.default_rng(42)   # deterministik testler


def kart(metin: str, n: int, h: int = 160, w: int = 200,
         parlaklik: int = 255, zemin: int = 10) -> list[np.ndarray]:
    g = np.full((h, w), zemin, np.uint8)
    for i, satir in enumerate(metin.split("|")):
        cv2.putText(g, satir.strip(), (8, 40 + 34 * i),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, int(parlaklik), 1, cv2.LINE_AA)
    return [g.copy() for _ in range(n)]


def kar_ekle(kareler: list[np.ndarray], yogunluk: float = 0.02) -> list[np.ndarray]:
    out = []
    for g in kareler:
        g = g.copy()
        maske = RNG.random(g.shape) < yogunluk
        g[maske] = 255
        out.append(g)
    return out


def fade(a: np.ndarray, b: np.ndarray, adim: int) -> list[np.ndarray]:
    return [cv2.addWeighted(a, 1 - t, b, t, 0)
            for t in np.linspace(0.0, 1.0, adim)]


def flas(h: int = 160, w: int = 200) -> np.ndarray:
    return np.full((h, w), 255, np.uint8)


def scroll(metinler: list[str], toplam_kare: int, h: int = 160, w: int = 200) -> list[np.ndarray]:
    serit_h = 40 * len(metinler) + 2 * h
    serit = np.full((serit_h, w), 10, np.uint8)
    for i, m in enumerate(metinler):
        cv2.putText(serit, m, (8, h + 40 * i), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, 255, 1, cv2.LINE_AA)
    out = []
    for k in range(toplam_kare):
        y = int(k * (serit_h - h) / max(1, toplam_kare - 1))
        out.append(serit[y:y + h, :].copy())
    return out


def interlace_boz(kareler: list[np.ndarray]) -> list[np.ndarray]:
    out = []
    for i, g in enumerate(kareler):
        g = g.copy()
        if i % 2 == 1:
            g[1::2] = np.roll(g[1::2], 1, axis=1)   # tek satırlar 1px kayar
        out.append(g)
    return out


def konfeti_ekle(kareler: list[np.ndarray], n_nokta: int = 120) -> list[np.ndarray]:
    out = []
    for g in kareler:
        g = g.copy()
        ys = RNG.integers(0, g.shape[0], n_nokta)
        xs = RNG.integers(0, g.shape[1], n_nokta)
        g[ys, xs] = 255
        out.append(g)
    return out


def pan(metin: str, n: int, kaydirma_px: int = 4) -> list[np.ndarray]:
    taban = kart(metin, 1, w=200 + kaydirma_px * n)[0]
    return [taban[:, i * kaydirma_px:i * kaydirma_px + 200].copy() for i in range(n)]
