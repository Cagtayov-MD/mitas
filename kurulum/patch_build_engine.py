# _pipe_ocr.py build_engine'i platform-guard'la: Windows=OneOCR, Linux=Paddle-adapter (jenerik-refine).
# Cagatay 2026-07-12 rol-ayrimi: jenerik=Paddle, ham-OCR-oku=GLM (ayri yolda).
import sys

F = "/opt/mitas/scripts/_pipe_ocr.py"
src = open(F, encoding="utf-8").read()

OLD = '''def build_engine():
    """OneOCR motorunu kur; basarisizsa (None, hata)."""
    try:
        import oneocr  # type: ignore
        from PIL import Image  # noqa: F401
        eng = oneocr.OcrEngine()
        return eng, "oneocr", None
    except Exception as exc:  # noqa: BLE001
        return None, "yok", f"{type(exc).__name__}: {exc}"'''

NEW = '''class _PaddleReadEngine:
    """OneOCR recognize_pil arayuzunu PaddleOCR ile karsilar (Linux'ta oneocr yok).
    Jenerik OCR-refine icin (Cagatay 2026-07-12: jenerik=Paddle, ham-OCR-oku=GLM)."""

    _shared = None
    name = "paddle"

    def __init__(self):
        if _PaddleReadEngine._shared is None:
            from core.pipelines.ocr.credit_experiment import PaddleOcrEngine
            _PaddleReadEngine._shared = PaddleOcrEngine()
        self._eng = _PaddleReadEngine._shared

    def recognize_pil(self, pil_image):
        import os as _os
        import tempfile as _tf
        from pathlib import Path as _P
        fd, tmp = _tf.mkstemp(suffix=".png")
        _os.close(fd)
        try:
            pil_image.convert("RGB").save(tmp)
            recs = self._eng.recognize(_P(tmp), strategy="jenerik_refine")
        finally:
            try:
                _os.unlink(tmp)
            except OSError:
                pass
        lines = []
        for r in (recs or []):
            t = (r.get("text") if isinstance(r, dict) else str(r)) or ""
            t = t.strip()
            if t:
                lines.append({"text": t})
        return {"lines": lines, "text": "\\n".join(l_["text"] for l_ in lines)}


def build_engine():
    """OCR motoru kur. Windows: OneOCR. Linux/oneocr-yok: MITAS_JENERIK_OCR_ENGINE (default paddle).
    Cagatay 2026-07-12 rol-ayrimi: jenerik-refine=Paddle, ham-OCR-oku=GLM (ayri yolda)."""
    try:
        import oneocr  # type: ignore
        from PIL import Image  # noqa: F401
        eng = oneocr.OcrEngine()
        return eng, "oneocr", None
    except Exception as exc:  # noqa: BLE001
        _je = os.environ.get("MITAS_JENERIK_OCR_ENGINE", "paddle").strip().lower()
        if _je in ("paddle", "", "auto"):
            try:
                return _PaddleReadEngine(), "paddle", None
            except Exception as pexc:  # noqa: BLE001
                return None, "yok", f"oneocr:{type(exc).__name__} paddle:{type(pexc).__name__}: {pexc}"
        return None, "yok", f"{type(exc).__name__}: {exc}"'''

if "_PaddleReadEngine" in src:
    print("ZATEN yamali (atlaniyor)")
    sys.exit(0)
if OLD not in src:
    print("HATA: eski build_engine metni bulunamadi")
    sys.exit(1)
src = src.replace(OLD, NEW)
open(F, "w", encoding="utf-8").write(src)
print("YAMANDI: build_engine -> Paddle-adapter + platform-guard")
