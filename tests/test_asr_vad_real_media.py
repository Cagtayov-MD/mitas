from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
import wave

from core.pipelines.asr.normalize import normalize_audio
from core.pipelines.asr.vad import run_silero_vad


ROOT = Path(__file__).resolve().parents[1]
REAL_MEDIA = ROOT / "testklipler" / "trt_haber (1).mp4"


def _runtime_available() -> bool:
    return (
        shutil.which("ffmpeg") is not None
        and shutil.which("ffprobe") is not None
        and importlib.util.find_spec("silero_vad") is not None
    )


class AsrVadRealMediaTest(unittest.TestCase):
    @unittest.skipUnless(_runtime_available(), "ffmpeg, ffprobe, and silero_vad are required")
    def test_silero_vad_real_media_smoke(self) -> None:
        if not REAL_MEDIA.exists():
            self.skipTest(f"real media fixture is not available: {REAL_MEDIA}")

        with tempfile.TemporaryDirectory() as temp_dir:
            normalized = normalize_audio(REAL_MEDIA, output_dir=Path(temp_dir) / "normalized")
            result = run_silero_vad(normalized.output_path)

        self.assertFalse(normalized.reused_input)
        self.assertGreater(result.audio_duration, 1.0)
        self.assertGreater(len(result.speech_segments), 0)
        self.assertGreater(result.speech_seconds, 0.0)
        self.assertGreater(result.speech_ratio, 0.05)
        self.assertLessEqual(result.speech_ratio, 1.0)

        for segment in result.speech_segments:
            self.assertGreaterEqual(segment.start, 0.0)
            self.assertLessEqual(segment.end, result.audio_duration)
            self.assertGreater(segment.duration, 0.0)

    @unittest.skipUnless(_runtime_available(), "ffmpeg, ffprobe, and silero_vad are required")
    def test_silero_vad_silent_normalized_wav_returns_empty_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            silent_wav = Path(temp_dir) / "silent_16khz_mono.wav"
            _write_silent_wav(silent_wav, seconds=1.0)
            result = run_silero_vad(silent_wav)

        self.assertEqual(result.audio_duration, 1.0)
        self.assertEqual(result.speech_segments, [])
        self.assertEqual(result.speech_seconds, 0.0)
        self.assertEqual(result.speech_ratio, 0.0)


def _write_silent_wav(path: Path, *, seconds: float) -> None:
    sample_rate = 16_000
    frames = int(sample_rate * seconds)
    sample_width_bytes = 2
    silent_frame = b"\x00" * sample_width_bytes

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(sample_width_bytes)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silent_frame * frames)


if __name__ == "__main__":
    unittest.main()
