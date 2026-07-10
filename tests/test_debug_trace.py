from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import debug_trace as dbg  # noqa: E402


def test_debug_trace_writes_jsonl_with_bad_unicode_and_large_payload(tmp_path, monkeypatch):
    clip = tmp_path / "Database" / "TEST CLIP"
    clip.mkdir(parents=True)

    dbg.start_trace(clip, clip_id="clip-1", title="TEST", profile="film", video="video.mp4", trt_id="1999-1")
    assert os.environ[dbg.TRACE_ENV] == str(clip / "debug_trace")

    bad = "ok\udcff" + ("x" * 9000)
    dbg.emit(
        "ocr",
        "candidate_read",
        subject={"field": "ocr_lines", "after": [bad]},
        evidence={"huge": bad, "items": list(range(200))},
        source={"module": "tests"},
    )

    lines = (clip / "debug_trace" / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 2
    event = json.loads(lines[-1])
    assert event["schema_version"] == dbg.SCHEMA_VERSION
    assert event["stage"] == "ocr"
    assert "truncated" in event["evidence"]["huge"]
    assert event["subject"]["after"][0].startswith("ok?")

    monkeypatch.delenv(dbg.TRACE_ENV, raising=False)


def test_debug_trace_finalize_writes_summary_and_timings(tmp_path):
    clip = tmp_path / "Database" / "TRACE CLIP"
    clip.mkdir(parents=True)

    dbg.start_trace(clip, clip_id="clip-2", title="TRACE", profile="film")
    dbg.emit(
        "qc1",
        "qc_decision",
        status="warn",
        subject={"field": "credit_quality", "reason": "QC1 RED; VL fallback will run"},
        evidence={"vl_fallback": True},
    )
    dbg.emit(
        "pdf",
        "pdf_field_written",
        subject={"field": "yonetmen", "after": ["JOHN DOE"], "reason": "fields written to PDF"},
    )
    dbg.finalize_trace(timings={"ocr": 1.2, "pdf": 0.7}, final_status="Kontrol", reasons=["QC1 başarısız"])

    trace_dir = clip / "debug_trace"
    assert (trace_dir / "timings.json").exists()
    summary = (trace_dir / "trace_summary.md").read_text(encoding="utf-8")
    for heading in [
        "Zaman Çizelgesi",
        "OCR Ne Okudu",
        "Text/VL Ne Yaptı",
        "Fuzzy ve KB Kararları",
        "Fallback Zinciri",
        "PDF’ye Giden Alanlar",
        "QC1/QC Final",
        "Süreler",
        "Bulunamayanlar",
    ]:
        assert heading in summary
    assert "VL fallback" in summary
    assert "JOHN DOE" in summary
