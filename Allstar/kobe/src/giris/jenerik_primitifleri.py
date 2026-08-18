"""Jenerik görüntü-işleme primitifleri — jenerik_detector'un yapıtaşları.

GÖREVİ NE?
    Üretimdeki çıkış-jeneriği dedektörü (jenerik_detector.py) "bu karede yazı
    var mı, yazı dikey akıyor mu, kare ne kadar değişti" sorularını OCR'SIZ,
    saf görüntü-işlemeyle cevaplar. O cevapların beş yapıtaşı burada yaşar:

    - _build_tophat_mask : top-hat morfolojisi + bağlı-bileşen filtresiyle
      metin maskesi üretir (arka plan bağımsız; sahne bloblarını eler).
      Dönen (maske, hayatta_kalan_blob_sayısı) — blob sayısı azsa kare
      NO_TEXT sayılır.
    - _phase_corr        : iki maskelenmiş gri kare arasında faz korelasyonu
      → (dx, dy, response). dy = dikey metin hareketi (scroll tespiti).
    - _gdiff             : iki karenin ortalama mutlak gri farkı (cut/kart
      değişimi sinyali).
    - _masked_gray       : gri kareyi maskeyle sınırlar (faz korelasyonunu
      yalnız metin bölgesine odaklar).
    - _hann2d            : faz korelasyonu için 2D Hanning penceresi.

NEREDEN GELDİ?
    2026-06 dynamic_credit_mosaic (slitscan) prototipinde doğdular; prototip
    2026-07-30 tek-motor temizliğinde (İbrahimovic) emekli edildi, canlı kalan
    bu beş fonksiyon buraya taşındı. Davranış birebir korunmuştur.

KİM KULLANIYOR?
    core/pipelines/ocr/jenerik_detector.py (üretim çıkış-jeneriği tespiti).
    Yeni bir tüketici eklerken sabitlerin dedektör fps'ine göre kalibre
    edildiğini unutma (jenerik_detector.py'deki S_HI notuna bak).

cv2 Türkçe-İ tuzağı: imread/imwrite YERİNE her zaman fromfile+imdecode /
imencode+tofile (bu dosyada disk IO yok; tüketiciler için not).
"""

from __future__ import annotations

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Sabitler (kalibrasyon noktaları — dynamic_credit_mosaic v2 mirası)
# ---------------------------------------------------------------------------

# --- Metin maskesi ---
TOPHAT_KSIZE: int = 25          # Top-hat yapısal eleman boyutu (px); metnin kalınlığından büyük olmalı
MASK_DILATION: int = 6          # Maske dilatasyon (glifleri birleştir)

# --- Bağlı-bileşen filtresi (CC_FILTER) ---
# Jenerik satırları ince VE YATAY GENIŞ'tir (w >> h, aspect w/h >= 2.0).
# Film sahneleri: ya büyük bloblar (h>40) ya da küçük kare bloblar (aspect ~1).
# Bu filtrenin amacı: YALNIZca yatay geniş/ince "metin satırı" bloblarını tutmak.
CC_MIN_H: int = 6               # Blob minimum yüksekliği (px) — gürültüyü at
CC_MAX_H: int = 45              # Blob maximum yüksekliği (px) — büyük sahne nesnelerini at
CC_MIN_W: int = 50              # Blob minimum genişliği (px) — dar kare blobları at (sahneler)
CC_MIN_ASPECT: float = 1.8      # w/h >= bu değer → metin satırı; daha az → sahne blobu
CC_MAX_AREA_FRAC: float = 0.04  # Blob alanı kare toplam px'in bu oranından büyükse at
MIN_CC_BLOBS: int = 2           # Hayatta kalan blob sayısı bu altındaysa kare NO_TEXT


def _hann2d(h: int, w: int) -> np.ndarray:
    return (
        np.hanning(h).reshape(-1, 1).astype(np.float32)
        * np.hanning(w).reshape(1, -1).astype(np.float32)
    )


def _phase_corr(
    g1: np.ndarray,
    g2: np.ndarray,
    hann: np.ndarray,
) -> tuple[float, float, float]:
    """Maskelenmiş gri kareler arasında faz korelasyonu → (dx, dy, response)."""
    try:
        (dx, dy), rsp = cv2.phaseCorrelate(
            g1.astype(np.float32) * hann,
            g2.astype(np.float32) * hann,
        )
        return float(dx), float(dy), float(rsp)
    except Exception:
        return 0.0, 0.0, 0.0


def _gdiff(g1: np.ndarray, g2: np.ndarray) -> float:
    """Tüm kare ortalama mutlak gri farkı."""
    return float(np.mean(np.abs(g1.astype(np.float32) - g2.astype(np.float32))))


def _build_tophat_mask(gray: np.ndarray) -> tuple[np.ndarray, int]:
    """Top-hat morfolojisi + CC filtresi ile metin maskesi oluştur (OCR'sız, BG-agnostik).

    Bağlı bileşen analizi ile film sahnelerindeki büyük blob'lar elenir.
    Yalnızca metin-çizgisi şekline uyan bloblar (ince, dar yükseklikli) tutulur.

    Returns:
        (filtered_mask, n_surviving_blobs) — n_surviving_blobs < MIN_CC_BLOBS ise
        kare NO_TEXT sayılmalı.
    """
    # Yapısal eleman: geniş yatay + dikey dikdörtgen (metni değil arka planı modeller)
    k = max(3, TOPHAT_KSIZE | 1)  # tek sayı olsun
    se = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k // 3 + 1))

    # White top-hat = gray - morphological opening
    opened = cv2.morphologyEx(gray, cv2.MORPH_OPEN, se)
    tophat = cv2.subtract(gray, opened)

    # Otsu eşikleme
    _, mask = cv2.threshold(tophat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Dilatasyon: glifleri birleştir
    if MASK_DILATION > 0:
        dil_se = cv2.getStructuringElement(
            cv2.MORPH_RECT, (MASK_DILATION, MASK_DILATION // 2 + 1)
        )
        mask = cv2.dilate(mask, dil_se)

    # --- Bağlı bileşen filtresi ---
    # Yalnızca metin-çizgisi şekline uyan bloblar tutulur:
    #   - Yükseklik [CC_MIN_H, CC_MAX_H] px — çok kısa gürültü ve çok büyük nesneler elenir.
    #   - Genişlik >= CC_MIN_W px — dar kare bloblar (sahne kenarları) elenir.
    #   - Aspect w/h >= CC_MIN_ASPECT — metin satırları yatay uzundur.
    #   - Alan <= CC_MAX_AREA_FRAC * frame — dev bloblar elenir.
    total_px = gray.shape[0] * gray.shape[1]
    max_area_px = int(CC_MAX_AREA_FRAC * total_px)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    # stats sütunları: LEFT, TOP, WIDTH, HEIGHT, AREA
    filtered_mask = np.zeros_like(mask)
    n_surviving = 0
    for lbl in range(1, n_labels):  # 0 = arka plan
        h_blob = int(stats[lbl, cv2.CC_STAT_HEIGHT])
        w_blob = int(stats[lbl, cv2.CC_STAT_WIDTH])
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        aspect = w_blob / max(1, h_blob)
        if (CC_MIN_H <= h_blob <= CC_MAX_H
                and w_blob >= CC_MIN_W
                and aspect >= CC_MIN_ASPECT
                and area <= max_area_px):
            filtered_mask[labels == lbl] = 255
            n_surviving += 1

    return filtered_mask, n_surviving


def _masked_gray(gray: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    if mask is None:
        return gray
    out = np.zeros_like(gray)
    out[mask > 0] = gray[mask > 0]
    return out

