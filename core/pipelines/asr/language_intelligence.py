from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
import inspect
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, Literal, Protocol
import wave

from core.pipelines.asr.normalize import PROJECT_ROOT, TARGET_SAMPLE_RATE
from core.pipelines.asr.vad import VadResult, VadSpeechSegment, run_silero_vad


LanguageIntelligenceMode = Literal["off", "shadow"]
LanguageDecision = Literal["language", "mixed", "unknown"]

DEFAULT_PILOT_LANGUAGES = ("tr", "en", "ar", "az")
DEFAULT_UNSUPPORTED_ASR_LANGUAGES = ("ku", "kmr", "ckb", "sdh")
DEFAULT_MODEL_SOURCE = "speechbrain/lang-id-voxlingua107-ecapa"
DEFAULT_MODEL_NAME = "speechbrain-voxlingua107-ecapa"


@dataclass(frozen=True)
class LanguageIntelligenceConfig:
    mode: LanguageIntelligenceMode = "off"
    pilot_languages: tuple[str, ...] = DEFAULT_PILOT_LANGUAGES
    unsupported_asr_languages: tuple[str, ...] = DEFAULT_UNSUPPORTED_ASR_LANGUAGES
    model_name: str = DEFAULT_MODEL_NAME
    model_source: str = DEFAULT_MODEL_SOURCE
    model_savedir: Path = PROJECT_ROOT / "models" / "lid" / "speechbrain-lang-id-voxlingua107-ecapa"
    device: str = "cuda"
    min_region_seconds: float = 3.0
    target_window_seconds: float = 8.0
    max_windows: int = 20
    max_sample_seconds: float = 90.0
    max_runtime_seconds: float = 90.0
    max_runtime_ratio: float = 0.10
    min_runtime_seconds: float = 15.0
    min_raw_score: float = 0.55
    min_margin: float = 0.15
    master_min_share: float = 0.50


@dataclass(frozen=True)
class LanguageCandidate:
    language: str
    raw_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "raw_score": _round_score(self.raw_score),
            "calibrated_confidence": None,
            "calibration_version": None,
        }


@dataclass(frozen=True)
class LanguagePrediction:
    language: str | None
    raw_score: float | None
    top_candidates: tuple[LanguageCandidate, ...] = ()


@dataclass(frozen=True)
class LanguageTimelineWindow:
    start: float
    end: float
    duration: float
    language: str
    decision: LanguageDecision
    raw_score: float | None
    margin: float | None
    calibrated_confidence: float | None
    calibration_version: str | None
    top_candidates: tuple[LanguageCandidate, ...]
    decision_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
            "language": self.language,
            "decision": self.decision,
            "raw_score": _round_score(self.raw_score),
            "margin": _round_score(self.margin),
            "calibrated_confidence": self.calibrated_confidence,
            "calibration_version": self.calibration_version,
            "top_candidates": [candidate.to_dict() for candidate in self.top_candidates],
            "decision_reason": self.decision_reason,
        }


@dataclass(frozen=True)
class LanguageIntelligenceResult:
    enabled: bool
    mode: LanguageIntelligenceMode
    status: str
    model_name: str
    model_source: str
    pilot_languages: tuple[str, ...]
    unsupported_asr_languages: tuple[str, ...]
    timeline_granularity: str
    min_region_seconds: float
    max_windows: int
    max_sample_seconds: float
    runtime_budget_seconds: float | None
    runtime_sec: float
    audio_duration: float | None = None
    vad_segment_count: int | None = None
    eligible_vad_segment_count: int | None = None
    sampled_speech_seconds: float = 0.0
    master_language: str | None = None
    master_raw_score: float | None = None
    calibrated_confidence: float | None = None
    calibration_version: str | None = None
    language_distribution: dict[str, float] = field(default_factory=dict)
    windows: tuple[LanguageTimelineWindow, ...] = ()
    mixed_window_count: int = 0
    low_confidence_window_count: int = 0
    unsupported_asr: bool = False
    pilot_language: bool = False
    decision_reason: str | None = None
    skipped_reason: str | None = None
    error: str | None = None
    notes: tuple[str, ...] = ()

    @classmethod
    def disabled(cls, config: LanguageIntelligenceConfig | None = None) -> "LanguageIntelligenceResult":
        cfg = config or LanguageIntelligenceConfig()
        return cls(
            enabled=False,
            mode="off",
            status="disabled",
            model_name=cfg.model_name,
            model_source=cfg.model_source,
            pilot_languages=cfg.pilot_languages,
            unsupported_asr_languages=cfg.unsupported_asr_languages,
            timeline_granularity=f"vad_region_min_{cfg.min_region_seconds:g}s",
            min_region_seconds=cfg.min_region_seconds,
            max_windows=cfg.max_windows,
            max_sample_seconds=cfg.max_sample_seconds,
            runtime_budget_seconds=None,
            runtime_sec=0.0,
            decision_reason="feature_flag_off",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "status": self.status,
            "model_name": self.model_name,
            "model_source": self.model_source,
            "pilot_languages": list(self.pilot_languages),
            "unsupported_asr_languages": list(self.unsupported_asr_languages),
            "timeline_granularity": self.timeline_granularity,
            "min_region_seconds": self.min_region_seconds,
            "max_windows": self.max_windows,
            "max_sample_seconds": self.max_sample_seconds,
            "runtime_budget_seconds": _round_score(self.runtime_budget_seconds),
            "runtime_sec": round(self.runtime_sec, 3),
            "audio_duration": self.audio_duration,
            "vad_segment_count": self.vad_segment_count,
            "eligible_vad_segment_count": self.eligible_vad_segment_count,
            "sampled_speech_seconds": round(self.sampled_speech_seconds, 3),
            "master_language": self.master_language,
            "master_raw_score": _round_score(self.master_raw_score),
            "calibrated_confidence": self.calibrated_confidence,
            "calibration_version": self.calibration_version,
            "calibration": {
                "status": "not_calibrated",
                "method": None,
                "version": self.calibration_version,
            },
            "language_distribution": dict(self.language_distribution),
            "windows": [window.to_dict() for window in self.windows],
            "mixed_window_count": self.mixed_window_count,
            "low_confidence_window_count": self.low_confidence_window_count,
            "unsupported_asr": self.unsupported_asr,
            "pilot_language": self.pilot_language,
            "decision_reason": self.decision_reason,
            "skipped_reason": self.skipped_reason,
            "error": self.error,
            "routing": {
                "enabled": False,
                "applied": False,
                "reason": "shadow_mode" if self.mode == "shadow" else "feature_flag_off",
                "guardrails": {
                    "az": "routing_disabled_pending_az_tr_eval_and_secondary_signals",
                    "ku_kmr_ckb": "detect_only_or_unsupported_asr_until_dedicated_pilot",
                },
            },
            "eval_requirements": {
                "minimum_labeled_segments": 100,
                "az_tr_pair_segments_before_routing": 50,
                "code_switching_category_required": True,
            },
            "notes": list(self.notes),
        }


class LanguageWindowClassifier(Protocol):
    model_name: str
    model_source: str

    def classify_file(self, audio_path: Path) -> LanguagePrediction:
        ...


VadRunner = Callable[[Path], VadResult]


def config_from_env(mode: str | None = None) -> LanguageIntelligenceConfig:
    value = (mode if mode is not None else os.environ.get("MITAS_LANGUAGE_INTELLIGENCE", "off")).strip().lower()
    if value in {"1", "true", "yes", "on", "shadow"}:
        resolved: LanguageIntelligenceMode = "shadow"
    else:
        resolved = "off"

    device = os.environ.get("MITAS_LANGUAGE_INTELLIGENCE_DEVICE", "cuda").strip() or "cuda"
    return LanguageIntelligenceConfig(mode=resolved, device=device)


def run_language_intelligence(
    audio_path: str | Path,
    *,
    config: LanguageIntelligenceConfig | None = None,
    classifier: LanguageWindowClassifier | None = None,
    vad_runner: VadRunner | None = None,
    temp_dir: str | Path | None = None,
) -> LanguageIntelligenceResult:
    cfg = config or config_from_env()
    if cfg.mode == "off":
        return LanguageIntelligenceResult.disabled(cfg)

    started = perf_counter()
    path = Path(audio_path)
    runtime_budget = _runtime_budget_seconds(cfg, None)
    try:
        vad = (vad_runner or run_silero_vad)(path)
        runtime_budget = _runtime_budget_seconds(cfg, vad.audio_duration)
        eligible = [segment for segment in vad.speech_segments if segment.duration >= cfg.min_region_seconds]
        windows = select_lid_windows(eligible, config=cfg)
        if not windows:
            return _result_from_windows(
                cfg,
                status="skipped",
                started=started,
                runtime_budget=runtime_budget,
                audio_duration=vad.audio_duration,
                vad_segment_count=len(vad.speech_segments),
                eligible_vad_segment_count=0,
                windows=(),
                skipped_reason="no_vad_region_meets_min_duration",
                decision_reason="no_eligible_speech",
            )

        lid = classifier or SpeechBrainLanguageIdentifier(config=cfg)
        classified: list[LanguageTimelineWindow] = []
        with TemporaryDirectory(dir=str(temp_dir) if temp_dir is not None else None) as scratch:
            scratch_dir = Path(scratch)
            for index, segment in enumerate(windows):
                if perf_counter() - started > runtime_budget:
                    return _result_from_windows(
                        cfg,
                        status="budget_exceeded",
                        started=started,
                        runtime_budget=runtime_budget,
                        audio_duration=vad.audio_duration,
                        vad_segment_count=len(vad.speech_segments),
                        eligible_vad_segment_count=len(eligible),
                        windows=tuple(classified),
                        skipped_reason="runtime_budget_exceeded",
                        decision_reason="partial_language_timeline",
                    )
                sample_path = scratch_dir / f"lid_window_{index:03d}.wav"
                write_wav_window(path, sample_path, segment.start, segment.end)
                prediction = lid.classify_file(sample_path)
                classified.append(_window_from_prediction(segment, prediction, cfg))

        return _result_from_windows(
            cfg,
            status="ok",
            started=started,
            runtime_budget=runtime_budget,
            audio_duration=vad.audio_duration,
            vad_segment_count=len(vad.speech_segments),
            eligible_vad_segment_count=len(eligible),
            windows=tuple(classified),
            skipped_reason=None,
            decision_reason=None,
            model_name=getattr(lid, "model_name", cfg.model_name),
            model_source=getattr(lid, "model_source", cfg.model_source),
        )
    except Exception as exc:  # pragma: no cover - guarded behavior, detailed paths covered by tests.
        return LanguageIntelligenceResult(
            enabled=True,
            mode=cfg.mode,
            status="failed",
            model_name=cfg.model_name,
            model_source=cfg.model_source,
            pilot_languages=cfg.pilot_languages,
            unsupported_asr_languages=cfg.unsupported_asr_languages,
            timeline_granularity=f"vad_region_min_{cfg.min_region_seconds:g}s",
            min_region_seconds=cfg.min_region_seconds,
            max_windows=cfg.max_windows,
            max_sample_seconds=cfg.max_sample_seconds,
            runtime_budget_seconds=runtime_budget,
            runtime_sec=perf_counter() - started,
            error=f"{type(exc).__name__}: {exc}",
            decision_reason="language_intelligence_failed_non_blocking",
            notes=("ASR routing is disabled; transcription output was not changed.",),
        )


class SpeechBrainLanguageIdentifier:
    model_name = DEFAULT_MODEL_NAME

    def __init__(self, *, config: LanguageIntelligenceConfig) -> None:
        self.model_source = config.model_source
        source = str(config.model_savedir) if config.model_savedir.exists() else config.model_source
        savedir = str(config.model_savedir)
        # SpeechBrain on this Windows ASR venv can trip over optional k2 lazy
        # imports while inspect.getmodule() walks frames. Keep the workaround
        # local to loading, mirroring the pyannote diarization loader.
        with _safe_inspect_getmodule():
            try:
                from speechbrain.inference.classifiers import EncoderClassifier
            except ImportError:  # pragma: no cover - compatibility with older SpeechBrain.
                from speechbrain.pretrained import EncoderClassifier  # type: ignore

            run_opts = {"device": config.device} if config.device else None
            kwargs: dict[str, Any] = {"source": source, "savedir": savedir}
            if run_opts is not None:
                kwargs["run_opts"] = run_opts
            self._classifier = EncoderClassifier.from_hparams(**kwargs)

    def classify_file(self, audio_path: Path) -> LanguagePrediction:
        with _safe_inspect_getmodule():
            prediction = self._classifier.classify_file(audio_path.resolve().as_posix())
        language = _normalize_label(_first_label(prediction[3] if len(prediction) > 3 else None))
        raw_score = _tensor_scalar_to_float(prediction[1] if len(prediction) > 1 else None)
        top_candidates = _top_candidates_from_speechbrain_prediction(prediction, self._classifier)
        if language and not top_candidates:
            top_candidates = (LanguageCandidate(language=language, raw_score=raw_score if raw_score is not None else 0.0),)
        return LanguagePrediction(language=language, raw_score=raw_score, top_candidates=top_candidates)


def select_lid_windows(
    speech_segments: Sequence[VadSpeechSegment],
    *,
    config: LanguageIntelligenceConfig,
) -> tuple[VadSpeechSegment, ...]:
    eligible = [segment for segment in speech_segments if segment.duration >= config.min_region_seconds]
    if not eligible or config.max_windows <= 0 or config.max_sample_seconds <= 0.0:
        return ()

    count = min(len(eligible), config.max_windows)
    selected = [eligible[index] for index in _evenly_spaced_indices(len(eligible), count)]
    windows: list[VadSpeechSegment] = []
    remaining = config.max_sample_seconds
    for segment in selected:
        if remaining < config.min_region_seconds:
            break
        duration = min(segment.duration, config.target_window_seconds, remaining)
        if duration < config.min_region_seconds:
            continue
        start = segment.start
        end = min(segment.end, start + duration)
        windows.append(VadSpeechSegment(start=round(start, 3), end=round(end, 3), duration=round(end - start, 3)))
        remaining -= duration
    return tuple(windows)


def write_wav_window(source: Path, target: Path, start: float, end: float) -> None:
    with wave.open(str(source), "rb") as wav_in:
        channels = wav_in.getnchannels()
        sample_width = wav_in.getsampwidth()
        frame_rate = wav_in.getframerate()
        if channels != 1 or sample_width != 2 or frame_rate != TARGET_SAMPLE_RATE:
            raise ValueError(
                "Language Intelligence expects normalized 16 kHz mono PCM WAV; "
                f"got channels={channels}, sample_width={sample_width}, frame_rate={frame_rate}"
            )
        start_frame = max(0, int(start * frame_rate))
        end_frame = max(start_frame, int(end * frame_rate))
        wav_in.setpos(min(start_frame, wav_in.getnframes()))
        frames = wav_in.readframes(max(0, min(end_frame, wav_in.getnframes()) - start_frame))

    with wave.open(str(target), "wb") as wav_out:
        wav_out.setnchannels(1)
        wav_out.setsampwidth(2)
        wav_out.setframerate(TARGET_SAMPLE_RATE)
        wav_out.writeframes(frames)


def _window_from_prediction(
    segment: VadSpeechSegment,
    prediction: LanguagePrediction,
    config: LanguageIntelligenceConfig,
) -> LanguageTimelineWindow:
    candidates = prediction.top_candidates
    language = _normalize_label(prediction.language) or (candidates[0].language if candidates else None)
    raw_score = prediction.raw_score
    if raw_score is None and candidates:
        raw_score = candidates[0].raw_score

    sorted_candidates = tuple(sorted(candidates, key=lambda item: item.raw_score, reverse=True))
    if sorted_candidates:
        language = sorted_candidates[0].language
        raw_score = sorted_candidates[0].raw_score
    second_score = sorted_candidates[1].raw_score if len(sorted_candidates) > 1 else None
    margin = (raw_score - second_score) if raw_score is not None and second_score is not None else None

    if language is None or raw_score is None:
        final_language = "unknown"
        decision: LanguageDecision = "unknown"
        reason = "missing_language_prediction"
    elif raw_score < config.min_raw_score:
        final_language = "unknown"
        decision = "unknown"
        reason = "low_raw_score"
    elif margin is not None and margin < config.min_margin:
        final_language = "mixed"
        decision = "mixed"
        reason = "low_margin_or_multiple_candidates"
    else:
        final_language = language
        decision = "language"
        reason = "top_candidate"

    return LanguageTimelineWindow(
        start=segment.start,
        end=segment.end,
        duration=segment.duration,
        language=final_language,
        decision=decision,
        raw_score=raw_score,
        margin=margin,
        calibrated_confidence=None,
        calibration_version=None,
        top_candidates=sorted_candidates,
        decision_reason=reason,
    )


def _result_from_windows(
    config: LanguageIntelligenceConfig,
    *,
    status: str,
    started: float,
    runtime_budget: float | None,
    audio_duration: float | None,
    vad_segment_count: int | None,
    eligible_vad_segment_count: int | None,
    windows: tuple[LanguageTimelineWindow, ...],
    skipped_reason: str | None,
    decision_reason: str | None,
    model_name: str | None = None,
    model_source: str | None = None,
) -> LanguageIntelligenceResult:
    sampled = sum(window.duration for window in windows)
    distribution = _language_distribution(windows)
    master_language, master_raw_score, master_reason = _master_language(windows, distribution, config)
    unsupported = master_language in set(config.unsupported_asr_languages) if master_language else False
    pilot = master_language in set(config.pilot_languages) if master_language else False
    notes = ["ASR routing is disabled; transcription output was not changed."]
    if master_language == "az":
        notes.append("AZ routing remains disabled until AZ-TR eval and secondary signals pass.")
    if master_language and not pilot:
        notes.append("Master language is outside the v0 pilot set.")
    if unsupported:
        notes.append("Detected master language is marked unsupported for ASR routing.")

    return LanguageIntelligenceResult(
        enabled=True,
        mode=config.mode,
        status=status,
        model_name=model_name or config.model_name,
        model_source=model_source or config.model_source,
        pilot_languages=config.pilot_languages,
        unsupported_asr_languages=config.unsupported_asr_languages,
        timeline_granularity=f"vad_region_min_{config.min_region_seconds:g}s",
        min_region_seconds=config.min_region_seconds,
        max_windows=config.max_windows,
        max_sample_seconds=config.max_sample_seconds,
        runtime_budget_seconds=runtime_budget,
        runtime_sec=perf_counter() - started,
        audio_duration=audio_duration,
        vad_segment_count=vad_segment_count,
        eligible_vad_segment_count=eligible_vad_segment_count,
        sampled_speech_seconds=sampled,
        master_language=master_language,
        master_raw_score=master_raw_score,
        calibrated_confidence=None,
        calibration_version=None,
        language_distribution=distribution,
        windows=windows,
        mixed_window_count=sum(1 for window in windows if window.decision == "mixed"),
        low_confidence_window_count=sum(1 for window in windows if window.decision == "unknown"),
        unsupported_asr=unsupported,
        pilot_language=pilot,
        decision_reason=decision_reason or master_reason,
        skipped_reason=skipped_reason,
        notes=tuple(notes),
    )


def _language_distribution(windows: Sequence[LanguageTimelineWindow]) -> dict[str, float]:
    total = sum(window.duration for window in windows)
    if total <= 0.0:
        return {}
    totals: dict[str, float] = {}
    for window in windows:
        totals[window.language] = totals.get(window.language, 0.0) + window.duration
    return {language: round(value / total, 6) for language, value in sorted(totals.items())}


def _master_language(
    windows: Sequence[LanguageTimelineWindow],
    distribution: dict[str, float],
    config: LanguageIntelligenceConfig,
) -> tuple[str | None, float | None, str]:
    candidates = {language: share for language, share in distribution.items() if language not in {"mixed", "unknown"}}
    if not candidates:
        return None, None, "no_confident_language_windows"
    language, share = max(candidates.items(), key=lambda item: item[1])
    if share < config.master_min_share:
        return None, None, "no_dominant_language"
    scores = [window.raw_score for window in windows if window.language == language and window.raw_score is not None]
    score = sum(scores) / len(scores) if scores else None
    return language, score, "dominant_language"


def _runtime_budget_seconds(config: LanguageIntelligenceConfig, audio_duration: float | None) -> float:
    if audio_duration is None or audio_duration <= 0.0:
        return config.max_runtime_seconds
    ratio_budget = max(config.min_runtime_seconds, audio_duration * config.max_runtime_ratio)
    return min(config.max_runtime_seconds, ratio_budget)


def _evenly_spaced_indices(length: int, count: int) -> list[int]:
    if count <= 0 or length <= 0:
        return []
    if count == 1:
        return [0]
    if count >= length:
        return list(range(length))
    return sorted({round(index * (length - 1) / (count - 1)) for index in range(count)})


def _top_candidates_from_speechbrain_prediction(prediction: Any, classifier: Any) -> tuple[LanguageCandidate, ...]:
    if not prediction:
        return ()
    try:
        import torch
    except ImportError:
        return ()

    try:
        scores = prediction[0]
        scores = scores.reshape(-1)
        if scores.numel() == 0:
            return ()
        if float(scores.min().item()) >= 0.0 and float(scores.max().item()) <= 1.0:
            probabilities = scores
        else:
            probabilities = torch.softmax(scores, dim=-1)
        values, indices = torch.topk(probabilities, k=min(3, probabilities.shape[-1]), dim=-1)
        label_encoder = classifier.hparams.label_encoder
        candidates: list[LanguageCandidate] = []
        for value, index in zip(values.tolist(), indices.tolist()):
            label = _normalize_label(_label_from_encoder(label_encoder, int(index)))
            if label:
                candidates.append(LanguageCandidate(language=label, raw_score=float(value)))
        return tuple(candidates)
    except Exception:
        return ()


def _label_from_encoder(label_encoder: Any, index: int) -> str | None:
    ind2lab = getattr(label_encoder, "ind2lab", None)
    if callable(ind2lab):
        return str(ind2lab(index))
    if isinstance(ind2lab, dict):
        value = ind2lab.get(index) or ind2lab.get(str(index))
        return str(value) if value is not None else None
    return None


def _first_label(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, Sequence) and value:
        return str(value[0])
    return str(value)


def _normalize_label(label: str | None) -> str | None:
    if not label:
        return None
    value = label.strip().lower()
    if ":" in value:
        value = value.split(":", 1)[0].strip()
    if not value:
        return None
    aliases = {
        "iw": "he",
        "jw": "jv",
        "arb": "ar",
        "ara": "ar",
        "aze": "az",
        "azj": "az",
        "tur": "tr",
        "eng": "en",
    }
    return aliases.get(value, value)


def _tensor_scalar_to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if hasattr(value, "exp"):
            value = value.exp()
        if hasattr(value, "item"):
            return float(value.item())
        return float(value)
    except Exception:
        return None


def _round_score(value: float | None) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        return None
    return round(float(value), 6)


@contextmanager
def _safe_inspect_getmodule() -> Any:
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
