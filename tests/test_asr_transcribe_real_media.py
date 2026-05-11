from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

from core.pipelines.asr.normalize import normalize_audio
from core.pipelines.asr.transcribe import DEFAULT_MODEL_PATH, transcribe_vad_segments
from core.pipelines.asr.vad import run_silero_vad


ROOT = Path(__file__).resolve().parents[1]
REAL_MEDIA = ROOT / "testklipler" / "trt_haber (1).mp4"


def _runtime_available() -> bool:
    return (
        shutil.which("ffmpeg") is not None
        and shutil.which("ffprobe") is not None
        and importlib.util.find_spec("silero_vad") is not None
        and importlib.util.find_spec("faster_whisper") is not None
        and DEFAULT_MODEL_PATH.exists()
    )


class AsrTranscribeRealMediaTest(unittest.TestCase):
    @unittest.skipUnless(_runtime_available(), "ffmpeg, ffprobe, silero_vad, faster_whisper, and local large-v3 are required")
    def test_transcribe_real_media_vad_segments_smoke(self) -> None:
        if not REAL_MEDIA.exists():
            self.skipTest(f"real media fixture is not available: {REAL_MEDIA}")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            normalized = normalize_audio(REAL_MEDIA, output_dir=temp_path / "normalized")
            vad_result = run_silero_vad(normalized.output_path)
            selected_vad_segments = [segment for segment in vad_result.speech_segments if segment.duration >= 2.0][:3]
            result = transcribe_vad_segments(
                normalized.output_path,
                selected_vad_segments,
                chunk_output_dir=temp_path / "chunks",
            )

        self.assertGreaterEqual(len(selected_vad_segments), 1)
        self.assertTrue(result.multilingual)
        self.assertEqual(result.vad_segments_count, len(selected_vad_segments))
        self.assertGreater(len(result.segments), 0)
        self.assertGreater(len(result.transcript), 5)
        self.assertGreater(sum(result.language_distribution.values()), 0)

        first_start = min(segment.start for segment in selected_vad_segments)
        last_end = max(segment.end for segment in selected_vad_segments)
        for segment in result.segments:
            self.assertGreaterEqual(segment.start, first_start)
            self.assertLessEqual(segment.end, last_end)
            self.assertLess(segment.start, segment.end)
            self.assertLess(segment.source_vad_index, len(selected_vad_segments))


if __name__ == "__main__":
    unittest.main()
