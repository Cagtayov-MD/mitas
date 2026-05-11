from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

from core.pipelines.asr.diarize import (
    DEFAULT_PYANNOTE_SNAPSHOT,
    configure_ffmpeg_shared_dll_directory,
    diarize_audio,
    load_pyannote_pipeline,
)
from core.pipelines.asr.normalize import normalize_audio
from core.pipelines.asr.vad import read_wav_duration_seconds


ROOT = Path(__file__).resolve().parents[1]
REAL_MEDIA = ROOT / "testklipler" / "trt_haber (3).mp4"


def _runtime_available() -> bool:
    return (
        shutil.which("ffmpeg") is not None
        and shutil.which("ffprobe") is not None
        and importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("pyannote.audio") is not None
        and DEFAULT_PYANNOTE_SNAPSHOT.exists()
    )


def _torchcodec_runtime_available() -> bool:
    return importlib.util.find_spec("torchcodec") is not None and REAL_MEDIA.exists()


class AsrDiarizeRealMediaTest(unittest.TestCase):
    @unittest.skipUnless(_runtime_available(), "ffmpeg, ffprobe, torch, pyannote.audio, and local pyannote snapshot are required")
    def test_pyannote_real_media_smoke(self) -> None:
        if not REAL_MEDIA.exists():
            self.skipTest(f"real media fixture is not available: {REAL_MEDIA}")

        pipeline = load_pyannote_pipeline()
        with tempfile.TemporaryDirectory() as temp_dir:
            normalized = normalize_audio(REAL_MEDIA, output_dir=Path(temp_dir) / "normalized")
            duration = read_wav_duration_seconds(normalized.output_path)
            result = diarize_audio(normalized.output_path, pipeline=pipeline)

        self.assertGreater(duration, 1.0)
        self.assertGreater(len(result.segments), 0)
        self.assertGreaterEqual(result.speaker_count, 1)
        self.assertEqual(result.speakers, sorted(result.speakers))

        for segment in result.segments:
            self.assertGreaterEqual(segment.start, 0.0)
            self.assertLessEqual(segment.end, duration)
            self.assertGreater(segment.duration, 0.0)
            self.assertTrue(segment.speaker_id.startswith("SPEAKER_"))

    @unittest.skipUnless(_torchcodec_runtime_available(), "torchcodec and real media fixture are required")
    def test_torchcodec_decodes_real_media_with_shared_ffmpeg(self) -> None:
        shared_bin = configure_ffmpeg_shared_dll_directory()
        if shared_bin is None:
            self.skipTest("FFmpeg full-shared DLL directory is not available")

        from torchcodec.decoders import AudioDecoder

        decoder = AudioDecoder(REAL_MEDIA, sample_rate=16_000, num_channels=1)
        samples = decoder.get_samples_played_in_range(0, 1)

        self.assertEqual(samples.sample_rate, 16_000)
        self.assertEqual(samples.data.shape[0], 1)
        self.assertGreater(samples.data.shape[1], 0)
        self.assertGreater(samples.duration_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
