"""PaddleOCR tabanli KJ/saat-ROI okuma - OneOCR'in Linux ikamesi (Faz F, K1-GATE).

OneOCR yalniz Windows'ta calisir. ATLAS'ta scan_clip_fast.py + KjOCR TEK motor
olarak OneOCR'e bagimliydi (saat-capasi + KJ satir OCR). Bu modul ayni
`OcrBackend` protokolunu (atlas.ocr.base: read(image_bgr)->list[OcrResult])
PaddleOCR (PP-OCRv5) ile karsilar - cagiran kod (kj_ocr.py, scan_clip_fast.py)
DEGISMEZ, yalnizca motor platform-guard'landiginda devreye girer.

Desen MITAS'in kanitlanmis core/pipelines/ocr/credit_experiment.py::PaddleOcrEngine
adaptasyonu (00_ATLAS_TASIMA_PLANI.md K-A3). Model adlari ayni (PP-OCRv5_server_det +
latin_PP-OCRv5_mobile_rec - Latin/TR metin icin dogrulugu iyi). ATLAS icin (MITAS'tan
farkli) yerel model-dizini ZORUNLU DEGIL - paddlex ilk kullanimda otomatik indirir
(plan sS5.2: "Linux'ta TAZE indir").
"""
from __future__ import annotations

import os
import sys
import types
from typing import Any

import numpy as np

from atlas.ocr.base import OcrResult

DET_MODEL_NAME = os.environ.get("ATLAS_PADDLEOCR_TEXT_DET_MODEL_NAME", "PP-OCRv5_server_det")
REC_MODEL_NAME = os.environ.get("ATLAS_PADDLEOCR_TEXT_REC_MODEL_NAME", "latin_PP-OCRv5_mobile_rec")


def _select_paddle_device() -> str:
    explicit = os.environ.get("ATLAS_PADDLEOCR_DEVICE", "").strip()
    if explicit:
        return explicit
    try:
        import paddle
        if paddle.device.is_compiled_with_cuda():
            return "gpu:0"
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


def _disable_modelscope_torch_import() -> None:
    """paddlex bazen modelscope'u eagerly import eder, o da torch'u yukler.
    ATLAS'in ocr venv'inde torch YOK (yalniz asr/visual/face/nlp'de) - bu yuzden
    MITAS'ta kanitlanan sahte-modul guard'i burada da uygulaniyor (ucuz sigorta)."""
    if os.environ.get("ATLAS_PADDLEOCR_USE_REAL_MODELSCOPE", "").strip().lower() in {"1", "true", "yes"}:
        return
    if "modelscope" in sys.modules:
        return
    modelscope = types.ModuleType("modelscope")

    def snapshot_download(*_: Any, **__: Any) -> None:
        raise RuntimeError("ModelScope ATLAS OCR runner'da devre disi; HF/local model kullan.")

    hub = types.ModuleType("modelscope.hub")
    errors = types.ModuleType("modelscope.hub.errors")

    class ModelScopeNotExistError(Exception):
        pass

    class ModelScopeHTTPError(Exception):
        pass

    errors.NotExistError = ModelScopeNotExistError
    errors.HTTPError = ModelScopeHTTPError
    hub.errors = errors
    modelscope.snapshot_download = snapshot_download
    modelscope.hub = hub
    sys.modules["modelscope"] = modelscope
    sys.modules["modelscope.hub"] = hub
    sys.modules["modelscope.hub.errors"] = errors


class PaddleKjBackend:
    """OneOCR'in Linux ikamesi: KjOCR.read() ile ayni imza (image_bgr -> list[OcrResult])."""

    name = "paddle"
    _shared: "PaddleKjBackend | None" = None

    def __init__(self) -> None:
        os.environ.setdefault("FLAGS_json_format_model", "0")
        os.environ.setdefault("FLAGS_enable_pir_api", "0")
        _disable_modelscope_torch_import()
        from paddleocr import PaddleOCR

        self.device = _select_paddle_device()
        self._ocr = PaddleOCR(
            text_detection_model_name=DET_MODEL_NAME,
            text_recognition_model_name=REC_MODEL_NAME,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device=self.device,
            enable_mkldnn=False,
        )

    @classmethod
    def shared(cls) -> "PaddleKjBackend":
        """Worker-basina TEK ornek (scan_clip_fast multiprocessing worker'i icin)."""
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

    def read(self, image_bgr: np.ndarray) -> list[OcrResult]:
        rgb = image_bgr[:, :, ::-1] if image_bgr.ndim == 3 else image_bgr
        if hasattr(self._ocr, "predict"):
            raw = self._ocr.predict(rgb)
        else:
            raw = self._ocr.ocr(rgb, cls=False)
        return _records_from_paddle(raw)


def _records_from_paddle(raw: Any) -> list[OcrResult]:
    out: list[OcrResult] = []
    for text, conf in _flatten_paddle_items(raw):
        if text and text.strip():
            out.append(OcrResult(text=text.strip(), conf=float(conf) if conf is not None else 1.0))
    return out


def _flatten_paddle_items(raw: Any) -> list[tuple[str, float | None]]:
    items: list[tuple[str, float | None]] = []
    if raw is None:
        return items
    if isinstance(raw, dict):
        texts = raw.get("rec_texts") or raw.get("texts") or []
        scores = raw.get("rec_scores") or raw.get("scores") or []
        for i, text in enumerate(texts):
            conf = scores[i] if i < len(scores) else None
            items.append((str(text), float(conf) if conf is not None else None))
        return items
    if isinstance(raw, list):
        for element in raw:
            if isinstance(element, dict):
                items.extend(_flatten_paddle_items(element))
            elif isinstance(element, list):
                if len(element) == 2 and isinstance(element[1], (tuple, list)) and len(element[1]) >= 1 and isinstance(element[1][0], str):
                    text = str(element[1][0])
                    conf = element[1][1] if len(element[1]) > 1 else None
                    items.append((text, float(conf) if conf is not None else None))
                else:
                    items.extend(_flatten_paddle_items(element))
    return items
