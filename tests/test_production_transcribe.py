from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
from typing import Any
import wave

import pytest

from core.pipelines.asr import ProductionTranscribeResult, transcribe
from core.pipelines.asr.vad import VadSpeechSegment


asr_transcribe = importlib.import_module("core.pipelines.asr.transcribe")


@dataclass
class _FakeSegment:
    start: float
    end: float
    text: str
    avg_logprob: float = -0.2
    no_speech_prob: float = 0.01
    language: str | None = "tr"


@dataclass
class _FakeInfo:
    language: str | None = "tr"


class _FakeModel:
    def __init__(self, segments: list[_FakeSegment], calls: list[dict[str, Any]]) -> None:
        self.segments = segments
        self.calls = calls

    def transcribe(self, audio: str, **kwargs: Any) -> tuple[list[_FakeSegment], _FakeInfo]:
        self.calls.append({"audio": audio, **kwargs})
        return self.segments, _FakeInfo("tr")


@pytest.fixture
def normalized_wav(tmp_path: Path) -> Path:
    wav_path = tmp_path / "fixture_16000hz_mono_s16.wav"
    _write_silent_wav(wav_path, sample_rate=16_000, channels=1, seconds=4.0)
    return wav_path


@pytest.fixture
def vad_segments() -> list[VadSpeechSegment]:
    return [VadSpeechSegment(start=0.5, end=2.5, duration=2.0)]


class TestProductionInterface:
    def test_quality_profile_basic(
        self,
        normalized_wav: Path,
        vad_segments: list[VadSpeechSegment],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[dict[str, Any]] = []

        def fake_load_model(config: Any) -> _FakeModel:
            assert config.name == "large-v3"
            return _FakeModel([_FakeSegment(0.1, 0.8, "Tüm hazırlıklar tamamlandı")], calls)

        monkeypatch.setattr(asr_transcribe, "load_model", fake_load_model)

        result = transcribe(normalized_wav, profile="quality", vad_segments=vad_segments)

        assert isinstance(result, ProductionTranscribeResult)
        assert result.profile_used == "quality"
        assert result.model_name == "large-v3"
        assert not result.fallback_triggered
        assert len(result.clean_segments) == 1
        assert "İzlediğiniz için teşekkür ederim" not in result.clean_transcript
        assert calls[0]["initial_prompt"] is None
        # Karar 27 (2026-05-14): condition_on_previous_text=False default;
        # hallucination yayilimi engellemek + operasyonel scriptlerle uyum.
        assert calls[0]["condition_on_previous_text"] is False

    def test_fast_profile_drops_stock_artifacts(
        self,
        normalized_wav: Path,
        vad_segments: list[VadSpeechSegment],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_load_model(config: Any) -> _FakeModel:
            assert config.name == "large-v3-turbo"
            return _FakeModel(
                [
                    _FakeSegment(0.1, 0.5, "Altyazı M.K."),
                    _FakeSegment(0.6, 1.2, "Gerçek konuşma burada"),
                ],
                [],
            )

        monkeypatch.setattr(asr_transcribe, "load_model", fake_load_model)

        result = transcribe(normalized_wav, profile="fast", vad_segments=vad_segments)

        assert result.model_name == "large-v3-turbo"
        assert "Altyazı M.K." not in result.clean_transcript
        assert "Abone olmayı" not in result.clean_transcript
        assert result.clean_transcript == "Gerçek konuşma burada"
        assert result.quality_drops[0].reason.startswith("stock_artifact")

    def test_fallback_triggered_on_repetition_drop(
        self,
        normalized_wav: Path,
        vad_segments: list[VadSpeechSegment],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_load_model(config: Any) -> _FakeModel:
            if config.name == "large-v3-turbo":
                return _FakeModel([_FakeSegment(0.1, 2.0, "ben " * 30)], [])
            return _FakeModel([_FakeSegment(0.1, 1.0, "Kaliteli fallback metni")], [])

        monkeypatch.setattr(asr_transcribe, "load_model", fake_load_model)

        result = transcribe(normalized_wav, profile="fast_with_fallback", vad_segments=vad_segments)

        assert result.fallback_triggered
        assert result.model_name == "large-v3"
        assert result.profile_used == "quality"
        assert "repetition_collapse" in (result.fallback_reason or "")
        assert result.clean_transcript == "Kaliteli fallback metni"

    def test_tail_gap_triggers_fallback(
        self,
        normalized_wav: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_load_model(config: Any) -> _FakeModel:
            if config.name == "large-v3-turbo":
                return _FakeModel([_FakeSegment(0.1, 1.0, "Eksik turbo metni")], [])
            return _FakeModel([_FakeSegment(0.1, 3.8, "Tam kalite metni devam ediyor")], [])

        monkeypatch.setattr(asr_transcribe, "load_model", fake_load_model)

        result = transcribe(
            normalized_wav,
            profile="fast_with_fallback",
            vad_segments=[VadSpeechSegment(start=0.0, end=4.0, duration=4.0)],
        )

        assert result.fallback_triggered
        assert result.model_name == "large-v3"
        assert result.profile_used == "quality"
        assert "tail_gap_uncovered" in (result.fallback_reason or "")
        assert result.selection_reason
        assert result.selection_reason.startswith("selected_quality:fast_unsafe")
        assert result.clean_transcript == "Tam kalite metni devam ediyor"

    def test_internal_vad_gap_triggers_selective_fallback(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        wav_path = tmp_path / "fixture_three_chunks.wav"
        _write_silent_wav(wav_path, sample_rate=16_000, channels=1, seconds=40.0)
        calls: list[tuple[str, int]] = []

        monkeypatch.setattr(asr_transcribe, "load_model", lambda config: object())

        def fake_transcribe_chunk(
            audio_path: Path,
            chunk: Any,
            model: Any,
            model_config: Any,
            params: Any,
            *,
            ffmpeg_executable: str,
        ) -> list[Any]:
            calls.append((model_config.name, chunk.index))
            if model_config.name == "large-v3-turbo" and chunk.index == 1:
                return []
            text = (
                f"Kalite chunk {chunk.index}"
                if model_config.name == "large-v3"
                else f"Turbo chunk {chunk.index}"
            )
            return [
                asr_transcribe.TranscriptSegment(
                    index=0,
                    start=round(chunk.start + 0.1, 3),
                    end=round(chunk.end - 0.1, 3),
                    text=text,
                    language="tr",
                    avg_logprob=-0.2,
                    no_speech_prob=0.01,
                    source_chunk_index=chunk.index,
                )
            ]

        monkeypatch.setattr(asr_transcribe, "_transcribe_chunk", fake_transcribe_chunk)

        result = transcribe(
            wav_path,
            profile="fast_with_fallback",
            vad_segments=[
                VadSpeechSegment(start=0.5, end=5.0, duration=4.5),
                VadSpeechSegment(start=16.0, end=20.0, duration=4.0),
                VadSpeechSegment(start=31.0, end=35.0, duration=4.0),
            ],
        )

        assert result.fallback_triggered
        assert result.profile_used == "fast_selective_quality"
        assert result.model_name == "large-v3-turbo+large-v3"
        assert result.fallback_reason
        assert result.fallback_reason.startswith("vad_gap_uncovered")
        assert calls == [
            ("large-v3-turbo", 0),
            ("large-v3-turbo", 1),
            ("large-v3-turbo", 2),
            ("large-v3", 1),
        ]
        assert result.verbatim_transcript == "Turbo chunk 0 Kalite chunk 1 Turbo chunk 2"
        assert result.timing is not None
        assert result.timing.fallback_mode == "selective"
        assert result.timing.fallback_chunk_count == 1
        assert result.timing.fallback_total_chunk_count == 3
        assert result.fallback_report["repair_type"] == "vad_gap_repair"
        assert result.fallback_report["selected_chunk_indexes"] == [1]
        assert result.fallback_report["quality_chunk_indexes"] == [1]
        assert result.fallback_report["kept_fast_chunk_indexes"] == []
        assert result.fallback_report["uncovered_vad_ranges"]

    def test_selective_vad_gap_failure_escalates_to_full_quality(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        wav_path = tmp_path / "fixture_three_chunks.wav"
        _write_silent_wav(wav_path, sample_rate=16_000, channels=1, seconds=40.0)
        vad_segments = [
            VadSpeechSegment(start=0.5, end=5.0, duration=4.5),
            VadSpeechSegment(start=16.0, end=20.0, duration=4.0),
            VadSpeechSegment(start=31.0, end=35.0, duration=4.0),
        ]
        calls: list[tuple[str, tuple[int, ...]]] = []

        def evaluated(segments: list[Any], vad_for_run: list[VadSpeechSegment]) -> dict[str, Any]:
            return asr_transcribe._evaluate_run_segments(
                raw_segments=segments,
                quality_config=asr_transcribe.QualityConfig(),
                expected_speech_end=max(segment.end for segment in vad_segments),
                vad_segments=vad_for_run,
                safety_kwargs={},
                decode_time=1.0,
            )

        def fake_run_single_pass(
            audio_path: Path,
            chunks: list[Any],
            model_config: Any,
            quality_config: Any,
            *,
            expected_speech_end: float | None,
            vad_segments: list[VadSpeechSegment] | None = None,
            safety_kwargs: dict[str, Any],
            ffmpeg_executable: str,
            transcribe_params: Any = None,
        ) -> dict[str, Any]:
            chunk_indexes = tuple(chunk.index for chunk in chunks)
            calls.append((model_config.name, chunk_indexes))
            vad_for_run = list(vad_segments or [])
            if model_config.name == "large-v3-turbo":
                return evaluated(
                    [
                        _segment(0, 0.7, 4.8, "Turbo chunk 0"),
                        _segment(2, 31.2, 34.8, "Turbo chunk 2"),
                    ],
                    vad_for_run,
                )
            if len(chunks) == 1:
                return evaluated([], vad_for_run)
            return evaluated(
                [
                    _segment(0, 0.7, 4.8, "Full kalite chunk 0"),
                    _segment(1, 16.2, 19.8, "Full kalite chunk 1"),
                    _segment(2, 31.2, 34.8, "Full kalite chunk 2"),
                ],
                vad_for_run,
            )

        monkeypatch.setattr(asr_transcribe, "_run_single_pass", fake_run_single_pass)

        result = transcribe(wav_path, profile="fast_with_fallback", vad_segments=vad_segments)

        assert result.fallback_triggered
        assert result.safety and result.safety.safe
        assert result.profile_used == "quality"
        assert result.model_name == "large-v3"
        assert result.selection_reason
        assert "selective_escalated_to_full_quality" in result.selection_reason
        assert result.verbatim_transcript == "Full kalite chunk 0 Full kalite chunk 1 Full kalite chunk 2"
        assert result.timing is not None
        assert result.timing.fallback_mode == "full_after_selective"
        assert result.timing.fallback_chunk_count == 3
        assert result.timing.fallback_total_chunk_count == 3
        assert calls == [
            ("large-v3-turbo", (0, 1, 2)),
            ("large-v3", (1,)),
            ("large-v3", (0, 1, 2)),
        ]

    def test_fallback_keeps_fast_when_quality_coverage_is_worse(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # 30s VAD window so the duration-aware tail-gap floor (audit HIGH-3)
        # keeps the quality result SAFE despite its shorter coverage, which is
        # what lets the coverage_worse selection branch fire. WAV must match
        # the VAD window because _map_production_segments clamps to chunk.end.
        wav_path = tmp_path / "fixture_long.wav"
        _write_silent_wav(wav_path, sample_rate=16_000, channels=1, seconds=30.0)

        def fake_load_model(config: Any) -> _FakeModel:
            if config.name == "large-v3-turbo":
                return _FakeModel(
                    [
                        _FakeSegment(0.1, 29.5, "Turbo tam metni burada koruyor"),
                        _FakeSegment(0.2, 0.4, "ben " * 30),
                    ],
                    [],
                )
            return _FakeModel([_FakeSegment(0.1, 27.0, "Daha kısa kalite metni burada")], [])

        monkeypatch.setattr(asr_transcribe, "load_model", fake_load_model)

        result = transcribe(
            wav_path,
            profile="fast_with_fallback",
            vad_segments=[VadSpeechSegment(start=0.0, end=30.0, duration=30.0)],
        )

        assert result.fallback_triggered
        assert result.model_name == "large-v3-turbo"
        assert result.profile_used == "fast"
        assert "repetition_collapse" in (result.fallback_reason or "")
        assert result.selection_reason
        assert result.selection_reason.startswith("kept_fast:quality_coverage_worse")
        assert result.clean_transcript == "Turbo tam metni burada koruyor"

    def test_selective_fallback_reruns_only_failed_chunk(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        wav_path = tmp_path / "fixture_three_chunks.wav"
        _write_silent_wav(wav_path, sample_rate=16_000, channels=1, seconds=40.0)
        calls: list[tuple[str, int]] = []

        monkeypatch.setattr(asr_transcribe, "load_model", lambda config: object())

        def fake_transcribe_chunk(
            audio_path: Path,
            chunk: Any,
            model: Any,
            model_config: Any,
            params: Any,
            *,
            ffmpeg_executable: str,
        ) -> list[Any]:
            calls.append((model_config.name, chunk.index))
            start = round(chunk.start + 0.1, 3)
            end = round(chunk.end - 0.1, 3)
            if model_config.name == "large-v3-turbo" and chunk.index == 1:
                text = "ben " * 30
            elif model_config.name == "large-v3":
                text = f"Kalite chunk {chunk.index}"
            else:
                text = f"Turbo chunk {chunk.index}"
            return [
                asr_transcribe.TranscriptSegment(
                    index=0,
                    start=start,
                    end=end,
                    text=text,
                    language="tr",
                    avg_logprob=-0.2,
                    no_speech_prob=0.01,
                    source_chunk_index=chunk.index,
                )
            ]

        monkeypatch.setattr(asr_transcribe, "_transcribe_chunk", fake_transcribe_chunk)

        result = transcribe(
            wav_path,
            profile="fast_with_fallback",
            vad_segments=[
                VadSpeechSegment(start=0.5, end=5.0, duration=4.5),
                VadSpeechSegment(start=16.0, end=20.0, duration=4.0),
                VadSpeechSegment(start=31.0, end=35.0, duration=4.0),
            ],
        )

        assert result.fallback_triggered
        assert result.profile_used == "fast_selective_quality"
        assert result.model_name == "large-v3-turbo+large-v3"
        assert "repetition_collapse" in (result.fallback_reason or "")
        assert calls == [
            ("large-v3-turbo", 0),
            ("large-v3-turbo", 1),
            ("large-v3-turbo", 2),
            ("large-v3", 1),
        ]
        assert result.verbatim_transcript == "Turbo chunk 0 Kalite chunk 1 Turbo chunk 2"
        assert result.timing is not None
        assert result.timing.fallback_mode == "selective"
        assert result.timing.fallback_chunk_count == 1
        assert result.timing.fallback_total_chunk_count == 3
        assert result.fallback_report["repair_type"] == "quality_repair"
        assert result.fallback_report["selected_chunk_indexes"] == [1]
        assert result.fallback_report["quality_chunk_indexes"] == [1]
        assert result.fallback_report["final_profile"] == "fast_selective_quality"

    def test_phase2_hooks_empty_but_present(
        self,
        normalized_wav: Path,
        vad_segments: list[VadSpeechSegment],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            asr_transcribe,
            "load_model",
            lambda config: _FakeModel([_FakeSegment(0.1, 0.8, "Merhaba dünya")], []),
        )

        result = transcribe(normalized_wav, profile="quality", vad_segments=vad_segments)

        assert result.normalized_transcript is None
        assert result.speaker_segments == []
        assert result.normalized_entities == []
        assert result.clean_segments[0].speaker_id is None
        assert result.clean_segments[0].normalized_text is None

    def test_archive_dict_serializable(
        self,
        normalized_wav: Path,
        vad_segments: list[VadSpeechSegment],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            asr_transcribe,
            "load_model",
            lambda config: _FakeModel([_FakeSegment(0.1, 0.8, "Arşiv metni")], []),
        )

        result = transcribe(normalized_wav, profile="quality", vad_segments=vad_segments)
        archive = result.to_archive_dict()

        json.dumps(archive)
        assert "transcript" in archive
        assert "verbatim" in archive["transcript"]
        assert archive["transcript"]["normalized"] is None


def _segment(chunk_index: int, start: float, end: float, text: str) -> Any:
    from core.pipelines.asr.result import TranscriptSegment

    return TranscriptSegment(
        index=0,
        start=start,
        end=end,
        text=text,
        language="tr",
        avg_logprob=-0.2,
        no_speech_prob=0.01,
        source_chunk_index=chunk_index,
    )


def _run_result(segments: list[Any], decode_time: float = 1.0) -> dict[str, Any]:
    return {"raw_segments": list(segments), "clean_segments": list(segments), "decode_time": decode_time}


class TestSelectiveFallbackMerge:
    """Regression: a selected chunk whose quality re-pass yields nothing must
    keep the fast segments instead of leaving a mid-timeline hole."""

    def test_quality_empty_for_selected_chunk_keeps_fast(self) -> None:
        from core.pipelines.asr.quality import QualityConfig

        fast = _run_result(
            [
                _segment(0, 0.0, 1.6, "merhaba burada konusma var"),
                _segment(1, 2.2, 3.8, "net turkce cumle bu kisimda duyuluyor"),
            ]
        )
        quality_empty = _run_result([], decode_time=0.5)

        merged = asr_transcribe._merge_selective_fallback_result(
            fast,
            quality_empty,
            selected_chunk_indexes=(1,),
            quality_config=QualityConfig(),
            expected_speech_end=None,
            safety_kwargs={},
        )

        assert merged["selective_kept_fast_chunks"] == (1,)
        chunk_one = [s for s in merged["clean_segments"] if s.source_chunk_index == 1]
        assert chunk_one, "selected chunk must not become an empty hole"
        assert "net turkce cumle" in " ".join(s.text for s in chunk_one)

    def test_quality_good_for_selected_chunk_is_used(self) -> None:
        from core.pipelines.asr.quality import QualityConfig

        fast = _run_result(
            [
                _segment(0, 0.0, 1.6, "merhaba burada konusma var"),
                _segment(1, 2.2, 3.8, "fast modelin urettigi zayif metin"),
            ]
        )
        quality = _run_result([_segment(1, 2.2, 3.8, "kalite modeli duzeltilmis net metin")], decode_time=0.7)

        merged = asr_transcribe._merge_selective_fallback_result(
            fast,
            quality,
            selected_chunk_indexes=(1,),
            quality_config=QualityConfig(),
            expected_speech_end=None,
            safety_kwargs={},
        )

        assert merged["selective_kept_fast_chunks"] == ()
        chunk_one_text = " ".join(s.text for s in merged["clean_segments"] if s.source_chunk_index == 1)
        assert "kalite modeli duzeltilmis" in chunk_one_text
        assert "zayif metin" not in chunk_one_text

    def test_gap_repair_supplements_instead_of_replacing_fast_audio(self) -> None:
        from core.pipelines.asr.quality import QualityConfig

        fast = _run_result([_segment(1, 10.0, 12.0, "hizli modelin duydugu ara soz")])
        quality = _run_result([_segment(1, 12.0, 18.0, "onarim modelinin tamamladigi konusma")])

        merged = asr_transcribe._merge_selective_fallback_result(
            fast,
            quality,
            selected_chunk_indexes=(1,),
            quality_config=QualityConfig(),
            expected_speech_end=18.0,
            vad_segments=[VadSpeechSegment(start=10.0, end=18.0, duration=8.0)],
            safety_kwargs={},
            preserve_fast_selected_chunks=True,
        )

        merged_text = " ".join(segment.text for segment in merged["clean_segments"])
        assert "hizli modelin duydugu" in merged_text
        assert "onarim modelinin" in merged_text
        assert merged["safety"].safe


class TestVadCoverageGaps:
    def test_detects_vad_speech_between_clean_segments(self) -> None:
        gaps = asr_transcribe._detect_uncovered_vad_ranges(
            [
                _segment(0, 119.175, 124.535, "With apologies"),
                _segment(2, 145.1, 163.1, "Prime Minister"),
            ],
            [
                VadSpeechSegment(start=119.9, end=125.2, duration=5.3),
                VadSpeechSegment(start=125.5, end=127.5, duration=2.0),
                VadSpeechSegment(start=127.7, end=129.2, duration=1.5),
                VadSpeechSegment(start=130.1, end=131.3, duration=1.2),
                VadSpeechSegment(start=131.8, end=132.4, duration=0.6),
                VadSpeechSegment(start=132.9, end=134.5, duration=1.6),
                VadSpeechSegment(start=135.1, end=136.8, duration=1.7),
                VadSpeechSegment(start=137.5, end=139.3, duration=1.8),
                VadSpeechSegment(start=139.5, end=142.2, duration=2.7),
                VadSpeechSegment(start=142.6, end=143.4, duration=0.8),
                VadSpeechSegment(start=144.1, end=145.0, duration=0.9),
            ],
        )

        assert len(gaps) == 1
        assert gaps[0]["start"] == 125.035
        assert gaps[0]["end"] == 144.6
        assert gaps[0]["range_seconds"] == pytest.approx(19.565)
        assert gaps[0]["speech_seconds"] == pytest.approx(14.565)

    def test_ignores_silence_between_clean_segments(self) -> None:
        gaps = asr_transcribe._detect_uncovered_vad_ranges(
            [
                _segment(0, 0.0, 2.0, "ilk cumle"),
                _segment(1, 8.0, 10.0, "ikinci cumle"),
            ],
            [
                VadSpeechSegment(start=0.0, end=2.0, duration=2.0),
                VadSpeechSegment(start=8.0, end=10.0, duration=2.0),
            ],
        )

        assert gaps == []


class TestErdMidTimelineGapRegression:
    """Regression lock for the erd_test_video mid-timeline VAD gap bug.

    Reproduces the situation where turbo produced clean segments up to ~124.5s
    then nothing until ~145.1s while VAD detected speech in that window.
    No GPU, no model load — purely tests the gap-detection and safety logic.
    """

    # VAD segments that span the gap region (~125-145s), matching erd_test_video.
    _VAD_SEGMENTS = [
        VadSpeechSegment(start=119.9, end=125.2, duration=5.3),
        VadSpeechSegment(start=125.5, end=127.5, duration=2.0),
        VadSpeechSegment(start=127.7, end=129.2, duration=1.5),
        VadSpeechSegment(start=130.1, end=131.3, duration=1.2),
        VadSpeechSegment(start=131.8, end=132.4, duration=0.6),
        VadSpeechSegment(start=132.9, end=134.5, duration=1.6),
        VadSpeechSegment(start=135.1, end=136.8, duration=1.7),
        VadSpeechSegment(start=137.5, end=139.3, duration=1.8),
        VadSpeechSegment(start=139.5, end=142.2, duration=2.7),
        VadSpeechSegment(start=142.6, end=143.4, duration=0.8),
        VadSpeechSegment(start=144.1, end=145.0, duration=0.9),
    ]

    def test_detect_uncovered_vad_ranges_finds_125_to_145_gap(self) -> None:
        """_detect_uncovered_vad_ranges must surface the dropped 20-second window."""
        clean_segs = [
            _segment(0, 100.0, 124.5, "Önceki metin burada bitti"),
            _segment(2, 145.1, 160.0, "Sonraki metin başladı"),
        ]
        gaps = asr_transcribe._detect_uncovered_vad_ranges(clean_segs, self._VAD_SEGMENTS)

        assert len(gaps) == 1, f"expected 1 gap, got {gaps}"
        gap = gaps[0]
        assert 15.0 <= gap["range_seconds"] <= 25.0, f"range_seconds={gap['range_seconds']}"
        assert gap["speech_seconds"] >= 2.0, f"speech_seconds={gap['speech_seconds']}"

    def test_evaluate_run_segments_marks_unsafe_vad_gap_uncovered(self) -> None:
        """_evaluate_run_segments must yield safe=False with failure_reason starting 'vad_gap_uncovered'."""
        from core.pipelines.asr.quality import QualityConfig
        from core.pipelines.asr.result import TranscriptSegment

        clean_segs = [
            TranscriptSegment(
                index=0,
                start=100.0,
                end=124.5,
                text="Önceki metin burada bitti",
                language="tr",
                avg_logprob=-0.2,
                no_speech_prob=0.01,
                source_chunk_index=0,
            ),
            TranscriptSegment(
                index=1,
                start=145.1,
                end=160.0,
                text="Sonraki metin başladı",
                language="tr",
                avg_logprob=-0.2,
                no_speech_prob=0.01,
                source_chunk_index=2,
            ),
        ]
        result = asr_transcribe._evaluate_run_segments(
            raw_segments=clean_segs,
            quality_config=QualityConfig(),
            expected_speech_end=145.0,
            vad_segments=self._VAD_SEGMENTS,
            safety_kwargs={},
            decode_time=1.0,
        )

        safety = result["safety"]
        assert safety.safe is False, f"expected safe=False, got safety={safety}"
        assert (safety.failure_reason or "").startswith("vad_gap_uncovered"), (
            f"expected failure_reason to start with 'vad_gap_uncovered', got: {safety.failure_reason!r}"
        )


def _write_silent_wav(path: Path, *, sample_rate: int, channels: int, seconds: float) -> None:
    frames = int(sample_rate * seconds)
    sample_width_bytes = 2
    silent_frame = b"\x00" * sample_width_bytes * channels

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width_bytes)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silent_frame * frames)
