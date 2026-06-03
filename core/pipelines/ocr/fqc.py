# -*- coding: utf-8 -*-
"""FQC — Frame Quality Control.

Frameleme sonrasında ÇALIŞAN İLK kapı (tüm filmler için). Jenerik karelerinin
metin BOYUTU ölçülür (stroke kalınlığı px + metin alanı %). Eşik altı → 'FQC RED'
(otomatik red; OCR/VLM'e GİRİLMEZ, kimlik-teyide yönlendirilir). Eşik üstü → süreç
otomatik devam eder. Sonuç HER ZAMAN raporlanır — bu kritik bir eşik.

Kalibrasyon (2026-06-02, ikisi de 512×288, scripts/_blur_metric.py):
  Ahlat Ağacı (okunur) : stroke 5.48 px, bright 10.6%  -> PASS
  Don Kişot   (okunmaz): stroke 1.91 px, bright  0.9%  -> FQC RED
Önemli: variance-of-Laplacian (blur) YANLIŞ metrik — hareketli/yoğun zeminde
ters döner (Don Kişot 1270 > Ahlat 259). Karar metin BOYUTUNA göre verilir.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Any

# --- Sabit eşik (şimdilik; Çağatay kalibrasyonu) ---
FQC_STROKE_PX_MIN = 3.0      # medyan stroke kalınlığı (Ahlat 5.48 ✓ / Don Kişot 1.9 ✗)
FQC_BRIGHT_PCT_MIN = 3.0     # metin alanı % (destekleyici)
FQC_SAMPLE_STEP = 5          # her N. kare


@dataclass
class FQCResult:
    verdict: str             # "pass" | "fqc_red"
    passed: bool
    stroke_px_median: float
    bright_pct_median: float
    lap_var_median: float    # referans (blur — KARAR İÇİN DEĞİL, ters dönebilir)
    frames_assessed: int
    threshold: dict[str, float] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def report_line(self) -> str:
        if self.passed:
            return (f"FQC PASS — stroke {self.stroke_px_median:.2f}px / "
                    f"metin %{self.bright_pct_median:.1f}  (eşik stroke≥{self.threshold.get('stroke_px_min')})  → süreç devam")
        return (f"FQC RED — stroke {self.stroke_px_median:.2f}px / metin %{self.bright_pct_median:.1f}  "
                f"(eşik stroke≥{self.threshold.get('stroke_px_min')})  → OKUNAMADI, OCR'a girilmedi, kimlik-teyide")


def _read_gray(path: Path):
    import cv2
    import numpy as np
    data = np.fromfile(str(path), dtype=np.uint8)  # unicode-safe (cv2 Türkçe-path tuzağı)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)


def _frame_metrics(gray) -> tuple[float, float, float]:
    """(stroke_px, bright_pct, lap_var) tek kare için."""
    import cv2
    import numpy as np

    lap = cv2.Laplacian(gray, cv2.CV_64F)
    lap_var = float(lap.var())
    thr = max(120.0, float(gray.mean()) + 1.5 * float(gray.std()))
    mask = gray > thr
    nbright = int(mask.sum())
    bright_pct = 100.0 * nbright / gray.size
    stroke = 0.0
    if nbright > 50:
        dt = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
        dv = dt[dt > 0]
        if dv.size:
            stroke = 2.0 * float(np.median(dv))
    return stroke, bright_pct, lap_var


def assess_frame_quality(
    frames: list[Path],
    *,
    step: int = FQC_SAMPLE_STEP,
    stroke_px_min: float = FQC_STROKE_PX_MIN,
    bright_pct_min: float = FQC_BRIGHT_PCT_MIN,
) -> FQCResult:
    """Karelerin metin-boyutu kalitesini ölç; PASS / FQC RED kararı ver.

    Karar BİRİNCİL stroke kalınlığına göre (Ahlat↔Don Kişot'u temiz ayıran metrik).
    """
    sample = frames[::max(1, step)]
    strokes: list[float] = []
    brights: list[float] = []
    laps: list[float] = []
    for f in sample:
        gray = _read_gray(Path(f))
        if gray is None:
            continue
        s, b, lv = _frame_metrics(gray)
        strokes.append(s)
        brights.append(b)
        laps.append(lv)

    n = len(strokes)
    s_med = float(median(strokes)) if strokes else 0.0
    b_med = float(median(brights)) if brights else 0.0
    l_med = float(median(laps)) if laps else 0.0

    passed = n > 0 and s_med >= stroke_px_min
    verdict = "pass" if passed else "fqc_red"
    if n == 0:
        reason = "kare okunamadı / boş"
    elif passed:
        reason = f"stroke_px {s_med:.2f} >= {stroke_px_min} eşik"
    else:
        reason = f"stroke_px {s_med:.2f} < {stroke_px_min} eşik (metin çok küçük → okunamaz)"

    return FQCResult(
        verdict=verdict,
        passed=passed,
        stroke_px_median=round(s_med, 2),
        bright_pct_median=round(b_med, 2),
        lap_var_median=round(l_med, 1),
        frames_assessed=n,
        threshold={"stroke_px_min": stroke_px_min, "bright_pct_min": bright_pct_min},
        reason=reason,
    )
