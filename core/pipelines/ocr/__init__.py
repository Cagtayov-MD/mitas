"""Lightweight OCR pipeline entry points."""

__all__ = ["OcrPipelineRunResult", "run_ocr_pipeline"]


def __getattr__(name: str):
    if name in __all__:
        from core.pipelines.ocr.simple import OcrPipelineRunResult, run_ocr_pipeline

        return {"OcrPipelineRunResult": OcrPipelineRunResult, "run_ocr_pipeline": run_ocr_pipeline}[name]
    raise AttributeError(name)
