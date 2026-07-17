#!/usr/bin/env python3
"""ATLAS Faz F: OneOCR -> Paddle platform-guard (K-A3). kj_ocr.py TEK degisiklik
noktasi (scan_clip_fast.py + jenerik.py BULMA ikisi de KjOCR uzerinden gecer,
plan sS3-A dogrulandi: jenerik.py:250-251 de KjOCR() kullaniyor). Cagirici kod
DEGISMEZ (ayni read(image_bgr)->list[OcrResult] imzasi); yalniz motor secimi
platform-guard'lanir. Idempotent."""
from __future__ import annotations

ROOT = "/opt/atlas"

OLD_INIT = '''    def __init__(self, oneocr_dir: Path | None = None) -> None:
        self._dir = oneocr_dir or ONEOCR_DIR
        self._engine = None

    def _ensure_engine(self) -> None:
        if self._engine is not None:
            return

        # DLL yolunu ekle (Windows gereksinimi)
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(self._dir))

        import oneocr  # type: ignore[import-untyped]
        oneocr.CONFIG_DIR = str(self._dir)
        self._engine = oneocr.OcrEngine()

    def read(self, image_bgr: np.ndarray) -> list[OcrResult]:
        """BGR crop'tan OcrResult listesi döndür (OneOCR satır ayırır)."""
        self._ensure_engine()

        # BGR → RGB PIL
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        result = self._engine.recognize_pil(pil_img)  # type: ignore[union-attr]'''

NEW_INIT = '''    def __init__(self, oneocr_dir: Path | None = None) -> None:
        self._dir = oneocr_dir or ONEOCR_DIR
        self._engine = None
        self._backend: str | None = None

    def _ensure_engine(self) -> None:
        if self._engine is not None:
            return

        try:
            # DLL yolunu ekle (Windows gereksinimi)
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(str(self._dir))

            import oneocr  # type: ignore[import-untyped]
            oneocr.CONFIG_DIR = str(self._dir)
            self._engine = oneocr.OcrEngine()
            self._backend = "oneocr"
        except Exception as exc:  # noqa: BLE001 - Windows-only bagimlilik; Linux'ta HER ZAMAN dusecek
            _want = os.environ.get("ATLAS_OCR_ENGINE", "paddle").strip().lower()
            if _want in ("paddle", "", "auto"):
                from atlas.ocr.paddle_backend import PaddleKjBackend
                self._engine = PaddleKjBackend.shared()
                self._backend = "paddle"
            else:
                raise RuntimeError(
                    f"OCR motoru kurulamadi (oneocr basarisiz: {type(exc).__name__}: {exc}; "
                    f"ATLAS_OCR_ENGINE={_want!r})"
                ) from exc

    def read(self, image_bgr: np.ndarray) -> list[OcrResult]:
        """BGR crop'tan OcrResult listesi döndür (OneOCR/Paddle motoruna göre)."""
        self._ensure_engine()

        if self._backend == "paddle":
            return self._engine.read(image_bgr)  # type: ignore[union-attr]

        # BGR → RGB PIL
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        result = self._engine.recognize_pil(pil_img)  # type: ignore[union-attr]'''

path = f"{ROOT}/src/atlas/ocr/kj_ocr.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

if "self._backend" in src:
    print("kj_ocr.py: ZATEN yamali, atlandi")
elif OLD_INIT not in src:
    print("HATA: kj_ocr.py OLD_INIT metni bulunamadi (elle bak)")
    raise SystemExit(1)
else:
    src = src.replace(OLD_INIT, NEW_INIT, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("kj_ocr.py: YAMANDI (platform-guard: oneocr -> paddle fallback)")

print("FAZ_F_PATCH_DONE_OK")
