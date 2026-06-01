from __future__ import annotations

from pathlib import Path
import wave

from core.pipelines.asr.language_intelligence import (
    LanguageCandidate,
    LanguageIntelligenceConfig,
    LanguagePrediction,
    config_from_env,
    run_language_intelligence,
    select_lid_windows,
)
from core.pipelines.asr.vad import VadResult, VadSpeechSegment


class FakeClassifier:
    model_name = "fake-lid"
    model_source = "test"

    def __init__(self, predictions: list[LanguagePrediction]) -> None:
        self.predictions = list(predictions)
        self.calls: list[Path] = []

    def classify_file(self, audio_path: Path) -> LanguagePrediction:
        self.calls.append(audio_path)
        return self.predictions.pop(0)


def test_config_from_env_defaults_to_off(monkeypatch) -> None:
    monkeypatch.delenv("MITAS_LANGUAGE_INTELLIGENCE", raising=False)
    assert config_from_env().mode == "off"


def test_config_from_env_accepts_shadow(monkeypatch) -> None:
    monkeypatch.setenv("MITAS_LANGUAGE_INTELLIGENCE", "shadow")
    assert config_from_env().mode == "shadow"


def test_select_lid_windows_uses_vad_min_duration_and_budget() -> None:
    cfg = LanguageIntelligenceConfig(mode="shadow", max_windows=3, max_sample_seconds=12.0, target_window_seconds=4.0)
    segments = [
        VadSpeechSegment(start=0.0, end=2.0, duration=2.0),
        VadSpeechSegment(start=10.0, end=16.0, duration=6.0),
        VadSpeechSegment(start=20.0, end=28.0, duration=8.0),
        VadSpeechSegment(start=40.0, end=48.0, duration=8.0),
        VadSpeechSegment(start=60.0, end=68.0, duration=8.0),
    ]

    windows = select_lid_windows(segments, config=cfg)

    assert len(windows) == 3
    assert windows[0].start == 10.0
    assert sum(window.duration for window in windows) <= cfg.max_sample_seconds
    assert all(window.duration >= cfg.min_region_seconds for window in windows)


def test_shadow_language_intelligence_builds_master_and_mixed_timeline(tmp_path) -> None:
    audio = tmp_path / "audio.wav"
    _write_silent_wav(audio, seconds=40.0)
    vad_result = VadResult(
        audio_path=audio,
        audio_duration=40.0,
        speech_segments=[
            VadSpeechSegment(start=1.0, end=9.0, duration=8.0),
            VadSpeechSegment(start=12.0, end=20.0, duration=8.0),
            VadSpeechSegment(start=24.0, end=32.0, duration=8.0),
        ],
        speech_seconds=24.0,
        speech_ratio=0.6,
        threshold=0.5,
    )
    classifier = FakeClassifier(
        [
            LanguagePrediction(
                language="ar",
                raw_score=0.91,
                top_candidates=(
                    LanguageCandidate("ar", 0.91),
                    LanguageCandidate("tr", 0.04),
                ),
            ),
            LanguagePrediction(
                language="ar",
                raw_score=0.88,
                top_candidates=(
                    LanguageCandidate("ar", 0.88),
                    LanguageCandidate("en", 0.08),
                ),
            ),
            LanguagePrediction(
                language="en",
                raw_score=0.49,
                top_candidates=(
                    LanguageCandidate("en", 0.49),
                    LanguageCandidate("ar", 0.43),
                ),
            ),
        ]
    )

    result = run_language_intelligence(
        audio,
        config=LanguageIntelligenceConfig(mode="shadow", max_windows=5),
        classifier=classifier,
        vad_runner=lambda _: vad_result,
        temp_dir=tmp_path,
    )

    payload = result.to_dict()
    assert result.status == "ok"
    assert result.master_language == "ar"
    assert result.master_raw_score and result.master_raw_score > 0.85
    assert result.mixed_window_count == 0
    assert result.low_confidence_window_count == 1
    assert payload["calibrated_confidence"] is None
    assert payload["routing"]["applied"] is False
    assert payload["eval_requirements"]["minimum_labeled_segments"] == 100
    assert len(classifier.calls) == 3


def test_shadow_language_intelligence_marks_low_margin_as_mixed(tmp_path) -> None:
    audio = tmp_path / "audio.wav"
    _write_silent_wav(audio, seconds=10.0)
    vad_result = VadResult(
        audio_path=audio,
        audio_duration=10.0,
        speech_segments=[VadSpeechSegment(start=1.0, end=7.0, duration=6.0)],
        speech_seconds=6.0,
        speech_ratio=0.6,
        threshold=0.5,
    )
    classifier = FakeClassifier(
        [
            LanguagePrediction(
                language="tr",
                raw_score=0.62,
                top_candidates=(
                    LanguageCandidate("tr", 0.62),
                    LanguageCandidate("az", 0.55),
                ),
            )
        ]
    )

    result = run_language_intelligence(
        audio,
        config=LanguageIntelligenceConfig(mode="shadow", min_margin=0.15),
        classifier=classifier,
        vad_runner=lambda _: vad_result,
        temp_dir=tmp_path,
    )

    assert result.windows[0].language == "mixed"
    assert result.windows[0].decision_reason == "low_margin_or_multiple_candidates"
    assert result.master_language is None


def test_disabled_language_intelligence_does_not_call_vad(tmp_path) -> None:
    audio = tmp_path / "audio.wav"
    _write_silent_wav(audio, seconds=3.0)

    def fail_vad(_: Path) -> VadResult:
        raise AssertionError("VAD should not run when Language Intelligence is off")

    result = run_language_intelligence(
        audio,
        config=LanguageIntelligenceConfig(mode="off"),
        vad_runner=fail_vad,
        temp_dir=tmp_path,
    )

    assert result.status == "disabled"
    assert result.enabled is False


def test_language_intelligence_failure_is_non_blocking(tmp_path) -> None:
    audio = tmp_path / "audio.wav"
    _write_silent_wav(audio, seconds=3.0)

    def fail_vad(_: Path) -> VadResult:
        raise RuntimeError("vad unavailable")

    result = run_language_intelligence(
        audio,
        config=LanguageIntelligenceConfig(mode="shadow"),
        vad_runner=fail_vad,
        temp_dir=tmp_path,
    )

    assert result.status == "failed"
    assert "vad unavailable" in (result.error or "")
    assert result.to_dict()["routing"]["applied"] is False


def _write_silent_wav(path: Path, *, seconds: float, sample_rate: int = 16_000) -> None:
    frames = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frames)
