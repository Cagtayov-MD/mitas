"""ASR v1.0 production pipeline."""

from core.pipelines.asr.chunking import MergedChunk, build_merged_chunks
from core.pipelines.asr.channel_analysis import ChannelDecision, decide_channel_mode, measure_lr_correlation
from core.pipelines.asr.channel_merge import merge_channel_results, tag_result_channel
from core.pipelines.asr.diarize import (
    AudioDiarizeError,
    DiarizationResult,
    DiarizationSegment,
    PyannotePipelineConfig,
    configure_ffmpeg_shared_dll_directory,
    diarize_audio,
    load_pyannote_pipeline,
    segments_from_pyannote_output,
)
from core.pipelines.asr.models import FAST_MODEL, QUALITY_MODEL, ModelConfig, ProfileName, clear_model_cache
from core.pipelines.asr.normalize import AudioNormalizeError, AudioStreamInfo, NormalizeResult, normalize_audio, probe_audio_stream
from core.pipelines.asr.merge import (
    SpeakerMergeConfig,
    SpeakerMergeResult,
    merge_speakers_into_segments,
)
from core.pipelines.asr.pipeline import AsrPipelineRunResult, run_asr_pipeline
from core.pipelines.asr.profiles import (
    CONTENT_PROFILES,
    ContentProfile,
    ContentProfileName,
    get_content_profile,
    list_content_profiles,
)
from core.pipelines.asr.quality import (
    QualityConfig,
    ResultSafetyDecision,
    SegmentQualityDecision,
    detect_repetition_collapse,
    detect_word_density_anomaly,
    evaluate_result_safety,
    evaluate_segment,
    is_stock_artifact,
)
from core.pipelines.asr.result import ChannelDuplicateDrop, DropRecord, ProductionTranscribeResult, TranscriptSegment, TranscribeTiming
from core.pipelines.asr.transcribe import (
    AsrPipelineError,
    AudioTranscribeError,
    TranscribeChunk,
    TranscribeResult,
    WhisperModelConfig,
    build_transcribe_chunks,
    load_whisper_model,
    transcribe,
    transcribe_vad_segments,
)
from core.pipelines.asr.vad import AudioVadError, VadResult, VadSpeechSegment, run_silero_vad

__all__ = [
    "transcribe",
    "run_asr_pipeline",
    "ContentProfile",
    "ContentProfileName",
    "CONTENT_PROFILES",
    "get_content_profile",
    "list_content_profiles",
    "SpeakerMergeConfig",
    "SpeakerMergeResult",
    "merge_speakers_into_segments",
    "ProductionTranscribeResult",
    "AsrPipelineRunResult",
    "TranscriptSegment",
    "DropRecord",
    "ChannelDuplicateDrop",
    "TranscribeTiming",
    "ChannelDecision",
    "QualityConfig",
    "ProfileName",
    "ModelConfig",
    "QUALITY_MODEL",
    "FAST_MODEL",
    "clear_model_cache",
    "MergedChunk",
    "build_merged_chunks",
    "decide_channel_mode",
    "measure_lr_correlation",
    "merge_channel_results",
    "tag_result_channel",
    "evaluate_segment",
    "evaluate_result_safety",
    "is_stock_artifact",
    "detect_repetition_collapse",
    "detect_word_density_anomaly",
    "ResultSafetyDecision",
    "SegmentQualityDecision",
    "normalize_audio",
    "probe_audio_stream",
    "AudioStreamInfo",
    "NormalizeResult",
    "run_silero_vad",
    "VadSpeechSegment",
    "VadResult",
    "diarize_audio",
    "DiarizationResult",
    "DiarizationSegment",
    "PyannotePipelineConfig",
    "configure_ffmpeg_shared_dll_directory",
    "load_pyannote_pipeline",
    "segments_from_pyannote_output",
    "AsrPipelineError",
    "AudioNormalizeError",
    "AudioVadError",
    "AudioDiarizeError",
    "AudioTranscribeError",
    "WhisperModelConfig",
    "TranscribeChunk",
    "TranscribeResult",
    "build_transcribe_chunks",
    "load_whisper_model",
    "transcribe_vad_segments",
]
