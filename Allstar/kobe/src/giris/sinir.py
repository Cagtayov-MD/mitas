"""(a) SINIR — giriş jeneriğinin başlangıç/bitiş sınırı.

Mevcut motor ÇAĞRILIR, kopyalanmaz: `core/pipelines/ocr/jenerik_detector.py`
(921 satır, 9 üretim tüketicisi). Bkz. src/giris/TASARIM.md.

Güven kapısı, üretimin kuralıyla AYNI ŞEKİLDE (mitas_pipeline.py:1985-1990,
sadeleştirilmiş — uzun-scroll istisnası burada YOK, bkz. TASARIM.md):

    güven ≥ GUVEN_ESIK  →  bas = tespit start_sec,  bit = tespit end_sec
    güven <  GUVEN_ESIK →  bas = 0.0,                bit = PENCERE_SN (sabit)

Motor "found=False" derse (hiçbir aday koşu yok) → KREDI_YOK'a çevrilir
(main.py). Motor patlarsa istisna YUKARI bırakılır — main.py bunu
ARIZA(GIRIS_SINIR) yapar. Sessizce sabit pencereye düşmek YASAK.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

GUVEN_ESIK_VARSAYILAN = 0.60      # mitas_pipeline._DETECT_MINCONF ile aynı
PENCERE_SN_VARSAYILAN = 240.0     # MITAS_OCR_HEAD değeri — kare_cikar ile AYNI
_DETECT_FPS = 2.0                 # main.KARE_FPS ile aynı; kare numaraları böyle hizalanır


def _detect_from_frames():
    """Lazy import — repo kökü sys.path'e eklenir (TASARIM.md §a, doğrulanmış çağrı)."""
    kok = os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas")
    if kok not in sys.path:
        sys.path.insert(0, kok)
    from core.pipelines.ocr.jenerik_detector import detect_from_frames
    return detect_from_frames


def bul(dizin: str | Path, config: dict | None = None) -> dict:
    """Sınırı bul. Döner:

        {"bulundu": bool,
         "baslangic_kare": int|None, "baslangic_sn": float|None,
         "bitis_kare": int|None, "bitis_sn": float|None,
         "guven": float, "kanit": {"sinir_kaynagi": "tespit"|"sabit", ...}}

    İstisna fırlatırsa (motor çöktü) çağıran ARIZA yapar — burada yutulmaz.
    """
    g = (config or {}).get("giris", {})
    guven_esik = float(g.get("guven_esik", GUVEN_ESIK_VARSAYILAN))
    pencere_sn = float(g.get("pencere_sn", PENCERE_SN_VARSAYILAN))

    detect_from_frames = _detect_from_frames()
    bolge = detect_from_frames(str(dizin), fps=_DETECT_FPS, window_start_sec=0.0,
                               prefer="first")

    if not bolge.get("found"):
        return {"bulundu": False, "baslangic_kare": None, "baslangic_sn": None,
                "bitis_kare": None, "bitis_sn": None,
                "guven": round(float(bolge.get("confidence") or 0.0), 3),
                "kanit": {"tespit_ham": bolge}}

    guven = float(bolge.get("confidence") or 0.0)
    if guven >= guven_esik:
        kaynak = "tespit"
        bas_kare = int(bolge["start_frame"])
        bas_sn = float(bolge["start_sec"])
        ef = bolge.get("end_frame")
        es = bolge.get("end_sec")
        bit_kare = int(ef) if ef is not None else None
        bit_sn = float(es) if es is not None else None
    else:
        kaynak = "sabit"
        bas_kare, bas_sn = 0, 0.0
        bit_sn = pencere_sn
        bit_kare = int(round(pencere_sn * _DETECT_FPS))

    return {"bulundu": True, "baslangic_kare": bas_kare,
            "baslangic_sn": round(bas_sn, 2),
            "bitis_kare": bit_kare,
            "bitis_sn": round(bit_sn, 2) if bit_sn is not None else None,
            "guven": round(guven, 3),
            "kanit": {"sinir_kaynagi": kaynak, "tespit_ham": bolge}}
