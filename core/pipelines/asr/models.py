"""ASR model registry and profile configurations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from core.pipelines.asr.normalize import PROJECT_ROOT


ProfileName = Literal["quality", "fast", "fast_with_fallback"]


@dataclass(frozen=True)
class ModelConfig:
    """faster-whisper model configuration."""

    model_path: Path
    device: str = "cuda"
    compute_type: str = "float16"
    beam_size: int = 5
    name: str = ""


QUALITY_MODEL = ModelConfig(
    model_path=PROJECT_ROOT / "models" / "asr" / "faster-whisper" / "large-v3",
    name="large-v3",
)

FAST_MODEL = ModelConfig(
    model_path=PROJECT_ROOT / "models" / "asr" / "faster-whisper" / "large-v3-turbo",
    name="large-v3-turbo",
)


@dataclass(frozen=True)
class TranscribeParams:
    """faster-whisper transcribe() parameters."""

    language: str | None = "tr"
    multilingual: bool = False
    initial_prompt: str | None = None
    condition_on_previous_text: bool = True
    vad_filter: bool = False
    word_timestamps: bool = False
    temperature: tuple[float, ...] = (0.0, 0.2, 0.4)
    compression_ratio_threshold: float = 2.4
    log_prob_threshold: float = -1.0
    no_speech_threshold: float = 0.6


DEFAULT_TRANSCRIBE_PARAMS = TranscribeParams()

_MODEL_CACHE: dict[tuple[str, str, str], Any] = {}


def load_model(config: ModelConfig) -> Any:
    """Load a faster-whisper model with a small in-process cache."""
    cache_key = (str(config.model_path), config.device, config.compute_type)
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed") from exc

    model = WhisperModel(
        str(config.model_path),
        device=config.device,
        compute_type=config.compute_type,
        local_files_only=True,
    )
    _MODEL_CACHE[cache_key] = model
    return model


def clear_model_cache() -> None:
    """Clear cached model instances for tests or memory pressure."""
    _MODEL_CACHE.clear()
