"""Run the ASR v0.1 pipeline on the chosen TRT smoke clip (001_h1).

Writes archive.json, summary.json, module_run.json, transcript_review.md,
and timeline_events.json into outputs/asr_v0_1_demo/.

Invoked with the asr venv:

    E:\\MITAS\\venvs\\asr\\Scripts\\python.exe scripts\\asr_v0_1_demo.py

The source audio is the prepared 16 kHz mono PCM WAV from the archive benchmark:
    outputs/asr_archive_all_wav_benchmark/001_h1/audio_16000hz_mono_s16.wav

Source acquisition (already done): \\\\depo01cifs.int.trt.net.tr\\sas_h264\\testset\\wav\\H1.wav
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.pipelines.asr.pipeline import run_asr_pipeline


SMOKE_CLIP_ID = "001_h1"
SMOKE_AUDIO = (
    PROJECT_ROOT
    / "outputs"
    / "asr_archive_all_wav_benchmark"
    / SMOKE_CLIP_ID
    / "audio_16000hz_mono_s16.wav"
)
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "asr_v0_1_demo"


def main() -> int:
    if not SMOKE_AUDIO.exists():
        print(f"Smoke audio not found: {SMOKE_AUDIO}", file=sys.stderr)
        return 1

    print(f"Running ASR v0.1 pipeline on {SMOKE_AUDIO}")
    result = run_asr_pipeline(
        SMOKE_AUDIO,
        profile="fast_with_fallback",
        channel_mode="mono",
        output_dir=OUTPUT_DIR,
        media_id=SMOKE_CLIP_ID,
        job_id=f"v0_1_demo-{SMOKE_CLIP_ID}",
        module_run_id=f"asr-{SMOKE_CLIP_ID}-v0_1_demo",
    )

    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    print()
    print(f"output_dir:         {result.output_dir}")
    print(f"profile_used:       {summary['profile_used']}")
    print(f"model_name:         {summary['model_name']}")
    print(f"fallback_triggered: {summary['fallback_triggered']}")
    print(f"fallback_reason:    {summary['fallback_reason']}")
    print(f"selection_reason:   {summary['selection_reason']}")
    print(f"audio_duration:     {summary['audio_duration']}")
    print(f"clean_segments:     {summary['clean_segments']}")
    print(f"clean_words:        {summary['clean_words']}")
    print(f"quality_drops:      {summary['quality_drops']}")
    print(f"timeline_events:    {summary['timeline_event_count']}")
    print(f"vad_speech_ratio:   {summary['vad']['speech_ratio']}")
    print(f"safety_passed:      {summary['safety']['safe']}")
    print(f"safety_failure:     {summary['safety']['failure_reason']}")
    print()
    print("Artifacts:")
    for label, path in (
        ("archive", result.archive_path),
        ("summary", result.summary_path),
        ("module_run", result.module_run_path),
        ("transcript_review", result.transcript_review_path),
        ("timeline_events", result.timeline_events_path),
    ):
        size_kb = path.stat().st_size / 1024 if path.exists() else 0.0
        print(f"  {label:18s} {path.name} ({size_kb:.1f} KB)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
