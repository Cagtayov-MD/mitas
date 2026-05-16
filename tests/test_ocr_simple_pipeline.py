from __future__ import annotations

import json
from pathlib import Path

from core.pipelines.ocr import simple as ocr_simple
from core.schemas.common import JobStatus


def test_run_ocr_pipeline_writes_done_outputs_with_recognized_text(tmp_path, monkeypatch) -> None:
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"fake-png")

    def fake_extract_frames(*args, **kwargs):
        return [frame]

    def fake_build_recognizer(engine: str):
        return lambda path: {"text": "TRT ARSIV", "lines": ["TRT ARSIV"], "engine": "fake"}, "fake"

    monkeypatch.setattr(ocr_simple, "_extract_frames", fake_extract_frames)
    monkeypatch.setattr(ocr_simple, "_build_recognizer", fake_build_recognizer)

    result = ocr_simple.run_ocr_pipeline(
        tmp_path / "input.mp4",
        output_dir=tmp_path / "ocr",
        media_id="media-1",
        job_id="job-1",
    )

    assert result.status == JobStatus.done
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    results = json.loads(result.results_path.read_text(encoding="utf-8"))
    assert summary["frames_with_text"] == 1
    assert summary["engine"] == "fake"
    assert results["frames"][0]["text"] == "TRT ARSIV"
    assert "TRT ARSIV" in result.review_path.read_text(encoding="utf-8")


def test_run_ocr_pipeline_records_partial_when_no_engine_is_available(tmp_path, monkeypatch) -> None:
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"fake-png")

    monkeypatch.setattr(ocr_simple, "_extract_frames", lambda *args, **kwargs: [frame])

    def missing_engine(engine: str):
        raise RuntimeError("No test OCR engine")

    monkeypatch.setattr(ocr_simple, "_build_recognizer", missing_engine)

    result = ocr_simple.run_ocr_pipeline(
        tmp_path / "input.mp4",
        output_dir=tmp_path / "ocr",
        media_id="media-1",
        job_id="job-1",
    )

    assert result.status == JobStatus.partial
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["frames"] == 1
    assert summary["frames_with_text"] == 0
    assert summary["error_msg"] == "No test OCR engine"
