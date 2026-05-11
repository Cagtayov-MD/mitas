from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import inspect
import os
from pathlib import Path
from typing import Any, Callable, Iterator

from core.pipelines.asr.normalize import TARGET_SAMPLE_RATE, probe_audio_stream
from core.pipelines.asr.vad import read_normalized_wav_tensor


DEFAULT_PYANNOTE_SNAPSHOT = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--pyannote--speaker-diarization-3.1"
    / "snapshots"
    / "84fd25912480287da0247647c3d2b4853cb3ee5d"
)
DEFAULT_PYANNOTE_MODEL_ID = "pyannote/speaker-diarization-3.1"
DEFAULT_DEVICE = "cuda"
PYANNOTE_TOKEN_ENV = "PYANNOTE_TOKEN"


class AudioDiarizeError(RuntimeError):
    """Raised when speaker diarization cannot run."""


@dataclass(frozen=True)
class PyannotePipelineConfig:
    checkpoint: Path | str = DEFAULT_PYANNOTE_SNAPSHOT
    device: str = DEFAULT_DEVICE
    token_env: str = PYANNOTE_TOKEN_ENV


@dataclass(frozen=True)
class DiarizationSegment:
    start: float
    end: float
    duration: float
    speaker_id: str


@dataclass(frozen=True)
class DiarizationResult:
    audio_path: Path
    model_id: str
    device: str
    segments: list[DiarizationSegment]
    speaker_count: int
    speakers: list[str]


def load_pyannote_pipeline(config: PyannotePipelineConfig | None = None) -> Any:
    pipeline_config = config or PyannotePipelineConfig()

    try:
        import torch
        from pyannote.audio import Pipeline
        from pyannote.audio.pipelines import speaker_diarization as speaker_diarization_module
    except ImportError as exc:
        raise AudioDiarizeError("pyannote.audio and torch are required for diarization") from exc

    checkpoint = _resolve_checkpoint(pipeline_config.checkpoint)
    token = os.environ.get(pipeline_config.token_env) or None

    # pyannote/speechbrain on this Windows ASR venv can trip over optional k2
    # lazy imports during inspect.stack(). Keep the workarounds local to loading.
    with _patched_pyannote_get_plda(speaker_diarization_module), _safe_inspect_getmodule():
        pipeline = Pipeline.from_pretrained(checkpoint, token=token)

    if pipeline is None:
        raise AudioDiarizeError(f"Failed to load pyannote pipeline from: {checkpoint}")

    return pipeline.to(torch.device(pipeline_config.device))


def diarize_audio(
    audio_path: str | Path,
    *,
    pipeline: Any | None = None,
    config: PyannotePipelineConfig | None = None,
    waveform_loader: Callable[[str | Path], Any] = read_normalized_wav_tensor,
) -> DiarizationResult:
    pipeline_config = config or PyannotePipelineConfig()
    path = Path(audio_path)
    stream = probe_audio_stream(path)
    if not stream.is_target_wav:
        raise AudioDiarizeError(
            "pyannote diarization expects normalized 16 kHz mono PCM WAV input; "
            f"got codec={stream.codec_name}, sample_rate={stream.sample_rate}, "
            f"channels={stream.channels}, sample_fmt={stream.sample_fmt}"
        )

    diarization_pipeline = pipeline if pipeline is not None else load_pyannote_pipeline(pipeline_config)
    waveform = waveform_loader(path).unsqueeze(0)
    output = diarization_pipeline({"waveform": waveform, "sample_rate": TARGET_SAMPLE_RATE})
    segments = segments_from_pyannote_output(output)
    speakers = sorted({segment.speaker_id for segment in segments})

    return DiarizationResult(
        audio_path=path,
        model_id=str(_resolve_checkpoint(pipeline_config.checkpoint)),
        device=pipeline_config.device,
        segments=segments,
        speaker_count=len(speakers),
        speakers=speakers,
    )


def segments_from_pyannote_output(output: Any) -> list[DiarizationSegment]:
    annotation = output.speaker_diarization if hasattr(output, "speaker_diarization") else output
    segments: list[DiarizationSegment] = []

    for turn, _, speaker in annotation.itertracks(yield_label=True):
        start = round(float(turn.start), 3)
        end = round(float(turn.end), 3)
        if end <= start:
            continue
        segments.append(
            DiarizationSegment(
                start=start,
                end=end,
                duration=round(end - start, 3),
                speaker_id=str(speaker),
            )
        )

    return sorted(segments, key=lambda segment: (segment.start, segment.end, segment.speaker_id))


def _resolve_checkpoint(checkpoint: Path | str) -> Path | str:
    path = Path(checkpoint)
    if path.exists():
        return path
    if str(checkpoint) == str(DEFAULT_PYANNOTE_SNAPSHOT):
        return DEFAULT_PYANNOTE_MODEL_ID
    return checkpoint


@contextmanager
def _patched_pyannote_get_plda(speaker_diarization_module: Any) -> Iterator[None]:
    original_get_plda = speaker_diarization_module.get_plda
    speaker_diarization_module.get_plda = lambda *args, **kwargs: None
    try:
        yield
    finally:
        speaker_diarization_module.get_plda = original_get_plda


@contextmanager
def _safe_inspect_getmodule() -> Iterator[None]:
    original_getmodule = inspect.getmodule

    def safe_getmodule(obj: Any, filename: str | None = None) -> Any:
        try:
            return original_getmodule(obj, filename)
        except ImportError:
            return None

    inspect.getmodule = safe_getmodule
    try:
        yield
    finally:
        inspect.getmodule = original_getmodule
