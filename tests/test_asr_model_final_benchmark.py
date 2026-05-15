import subprocess
from pathlib import Path

from scripts.asr_model_final_benchmark import (
    Sample,
    build_review_packet,
    char_error_rate,
    clean_review_text,
    is_reference_ready,
    reference_hygiene_issues,
    run_predictions,
    word_error_rate,
)


def test_word_error_rate_counts_insertions_deletions_and_substitutions() -> None:
    assert word_error_rate("bir iki uc", "bir dort uc bes") == 2 / 3


def test_char_error_rate_ignores_case_and_spaces() -> None:
    assert char_error_rate("TRT Haber", "trthaber") == 0.0


def test_reference_ready_rejects_todo_placeholders() -> None:
    assert is_reference_ready("TODO: fill me") is False
    assert is_reference_ready("Duzeltilmis referans metin") is True


def test_reference_ready_rejects_timestamp_markers() -> None:
    assert is_reference_ready("(3:40) Duzeltilmis referans metin") is False
    assert reference_hygiene_issues("(3:40) metin") == ["timestamp_markers_present"]


def test_clean_review_text_removes_comments_and_timestamps() -> None:
    text = "# Draft reference\n(3:40) Merhaba dunya.\n\n(3:42) Devam."
    assert clean_review_text(text) == "Merhaba dunya.\n\nDevam."


def test_run_predictions_passes_custom_manifest_to_child_process(tmp_path, monkeypatch) -> None:
    sample = Sample(
        sample_id="custom_sample",
        category="archive",
        source_path=Path("source.wav"),
        start_sec=None,
        end_sec=None,
        reference_path=Path("reference.txt"),
        review_priority="high",
        notes="custom manifest regression",
    )
    audio_path = tmp_path / "custom_sample" / "audio_16000hz_mono_s16.wav"
    audio_path.parent.mkdir()
    audio_path.write_bytes(b"RIFF")

    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("scripts.asr_model_final_benchmark.subprocess.run", fake_run)

    run_predictions([sample], tmp_path, manifest_path=Path("custom_manifest.yaml"), ffprobe="ffprobe")

    assert commands
    assert all("--manifest" in command for command in commands)
    assert all(command[command.index("--manifest") + 1] == "custom_manifest.yaml" for command in commands)


def test_build_review_packet_prefers_cleaned_current_reference_and_lists_diffs(tmp_path) -> None:
    sample = Sample(
        sample_id="sample_one",
        category="archive",
        source_path=Path("source.wav"),
        start_sec=100.0,
        end_sec=110.0,
        reference_path=tmp_path / "reference.txt",
        review_priority="high",
        notes="review packet regression",
    )
    sample.reference_path.write_text("(1:40) Dogru aday metin.", encoding="utf-8")
    sample_dir = tmp_path / "sample_one"
    (sample_dir / "fast").mkdir(parents=True)
    (sample_dir / "quality").mkdir(parents=True)
    (sample_dir / "audio_16000hz_mono_s16.wav").write_bytes(b"RIFF")
    (sample_dir / "fast" / "archive.json").write_text(
        '{"segments":[{"start":0.0,"end":3.0,"text":"yanlis kelime","flags":[],"avg_logprob":-0.1,"no_speech_prob":0.0}]}',
        encoding="utf-8",
    )
    (sample_dir / "quality" / "archive.json").write_text(
        '{"segments":[{"start":0.0,"end":3.0,"text":"dogru kelime","flags":["low_confidence"],"avg_logprob":-0.9,"no_speech_prob":0.5}]}',
        encoding="utf-8",
    )

    packet = build_review_packet(sample, tmp_path)

    assert packet["candidate_text"] == "Dogru aday metin."
    assert packet["reference_status"] == "needs_cleanup"
    assert "fast_quality_diff" in packet["packet_markdown"]
    assert "01:40" in packet["packet_markdown"]
