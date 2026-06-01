from __future__ import annotations

import json
from pathlib import Path
import wave

import core.pipelines.asr.align as asr_align
from core.pipelines.asr.quality import ResultSafetyDecision
from core.pipelines.asr.result import ProductionTranscribeResult, TranscriptSegment, TranscribeTiming


def test_whisperx_alignment_attaches_real_word_timestamps(tmp_path, monkeypatch) -> None:
    wav_path = tmp_path / "normalized.wav"
    _write_silent_wav(wav_path)
    fake_python = tmp_path / "python.exe"
    fake_script = tmp_path / "alignment_subprocess.py"
    fake_python.write_text("", encoding="utf-8")
    fake_script.write_text("", encoding="utf-8")

    def fake_subprocess(**kwargs) -> None:
        segments = json.loads(Path(kwargs["segments_path"]).read_text(encoding="utf-8"))["segments"]
        aligned_segments = []
        word_segments = []
        for segment in segments:
            words = []
            for index, word in enumerate(segment["text"].split()):
                start = round(segment["start"] + (index * 0.25), 3)
                end = round(start + 0.2, 3)
                item = {"word": word, "start": start, "end": end, "score": 0.9}
                words.append(item)
                word_segments.append(item)
            aligned_segments.append({**segment, "words": words})
        payload = {
            "status": "success",
            "input_segments_count": len(segments),
            "aligned_segments_count": len(aligned_segments),
            "word_segments_count": len(word_segments),
            "runtime_sec": 0.1,
            "result": {"segments": aligned_segments, "word_segments": word_segments},
        }
        Path(kwargs["output_path"]).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(asr_align, "_run_alignment_subprocess", fake_subprocess)

    updated, outcome = asr_align.align_word_timestamps(
        _fake_result(wav_path),
        normalized_outputs={"mono": wav_path},
        run_dir=tmp_path / "run",
        mode="whisperx",
        python_executable=fake_python,
        script_path=fake_script,
    )

    assert outcome.status == "ok"
    assert outcome.method == "whisperx"
    assert outcome.coverage == 1.0
    assert outcome.aligned_words == 3
    assert updated.clean_segments[0].word_timestamps[0]["source"] == "whisperx"
    assert updated.clean_segments[0].word_timestamps[0]["word"] == "Merhaba"


def test_whisperx_failure_is_reported_and_interpolated_timestamps_are_kept(tmp_path) -> None:
    wav_path = tmp_path / "normalized.wav"
    _write_silent_wav(wav_path)

    updated, outcome = asr_align.align_word_timestamps(
        _fake_result(wav_path),
        normalized_outputs={"mono": wav_path},
        run_dir=tmp_path / "run",
        mode="whisperx",
        python_executable=tmp_path / "missing-python.exe",
    )

    assert outcome.status == "failed"
    assert outcome.method == "whisperx"
    assert outcome.fallback_method == "segment_interpolated"
    assert outcome.success is False
    assert updated.clean_segments[0].word_timestamps[0]["source"] == "segment_interpolated"


def test_whisperx_low_coverage_retries_missing_segments(tmp_path, monkeypatch) -> None:
    wav_path = tmp_path / "normalized.wav"
    _write_silent_wav(wav_path, seconds=3.0)
    fake_python = tmp_path / "python.exe"
    fake_script = tmp_path / "alignment_subprocess.py"
    fake_python.write_text("", encoding="utf-8")
    fake_script.write_text("", encoding="utf-8")

    def fake_subprocess(**kwargs) -> None:
        segments = json.loads(Path(kwargs["segments_path"]).read_text(encoding="utf-8"))["segments"]
        is_retry = "retry" in Path(kwargs["output_path"]).stem
        word_segments = []
        aligned_segments = []
        for segment in segments:
            if not is_retry and segment["index"] == 1:
                aligned_segments.append({**segment, "words": []})
                continue
            words = []
            for index, word in enumerate(segment["text"].split()):
                start = round(segment["start"] + (index * 0.2), 3)
                item = {"word": word, "start": start, "end": round(start + 0.15, 3), "score": 0.9}
                words.append(item)
                word_segments.append(item)
            aligned_segments.append({**segment, "words": words})
        payload = {
            "status": "success",
            "runtime_sec": 0.1,
            "result": {"segments": aligned_segments, "word_segments": word_segments},
        }
        Path(kwargs["output_path"]).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(asr_align, "_run_alignment_subprocess", fake_subprocess)

    updated, outcome = asr_align.align_word_timestamps(
        _fake_result(wav_path, texts=("ilk segment", "ikinci segment")),
        normalized_outputs={"mono": wav_path},
        run_dir=tmp_path / "run",
        mode="whisperx",
        python_executable=fake_python,
        script_path=fake_script,
    )

    assert outcome.status == "ok"
    assert outcome.coverage == 1.0
    assert any(detail.get("retry") is True for detail in outcome.details)
    assert updated.clean_segments[1].word_timestamps[0]["source"] == "whisperx"
    assert updated.clean_segments[1].word_timestamps[0]["word"] == "ikinci"


def _fake_result(audio_path: Path, *, texts: tuple[str, ...] = ("Merhaba temiz dünya",)) -> ProductionTranscribeResult:
    segments = [
        TranscriptSegment(
            index=index,
            start=round(0.1 + index, 3),
            end=round(1.1 + index, 3),
            text=text,
            language="tr",
            avg_logprob=-0.2,
            no_speech_prob=0.01,
            source_chunk_index=0,
        )
        for index, text in enumerate(texts)
    ]
    return ProductionTranscribeResult(
        audio_path=audio_path,
        audio_duration=2.0,
        profile_requested="fast_with_fallback",
        profile_used="fast",
        model_name="large-v3-turbo",
        fallback_triggered=False,
        fallback_reason=None,
        raw_segments=segments,
        clean_segments=segments,
        verbatim_transcript=" ".join(segment.text for segment in segments),
        clean_transcript=" ".join(segment.text for segment in segments),
        quality_drops=[],
        safety=ResultSafetyDecision(safe=True, failure_reason=None, diagnostics={}),
        timing=TranscribeTiming(total_seconds=1.0, chunk_count=1, decode_seconds=0.5),
    )


def _write_silent_wav(path: Path, *, sample_rate: int = 16_000, seconds: float = 1.0) -> None:
    frames = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frames)
