from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any


class Label(str, Enum):
    """VLM'in kareye verdigi semantik sinif.

    ``MISSING`` model/parse/transport hatasidir; FOOTAGE gibi ele alinmaz.
    """

    FOOTAGE = "FOOTAGE"
    DIEGETIC_TEXT = "DIEGETIC_TEXT"
    STORY_TEXT = "STORY_TEXT"
    CREDIT = "CREDIT"
    END_CARD = "END_CARD"
    BLANK = "BLANK"
    UNCERTAIN = "UNCERTAIN"
    MISSING = "MISSING"


class DetectionStatus(str, Enum):
    FOUND = "FOUND"
    LEFT_CENSORED = "LEFT_CENSORED"
    NOT_FOUND = "NOT_FOUND"
    REVIEW = "REVIEW"
    MODEL_ERROR = "MODEL_ERROR"


class WindowVerdict(str, Enum):
    PRE_ONLY = "PRE_ONLY"
    TRANSITION = "TRANSITION"
    ACTIVE_FROM_LEFT = "ACTIVE_FROM_LEFT"
    AMBIGUOUS = "AMBIGUOUS"
    MISSING = "MISSING"


class BoundaryKind(str, Enum):
    NONE = "NONE"
    CREDIT_SEQUENCE = "CREDIT_SEQUENCE"
    END_CARD_THEN_CREDITS = "END_CARD_THEN_CREDITS"
    TERMINAL_END_CARD = "TERMINAL_END_CARD"


class Continuity(str, Enum):
    NONE = "NONE"
    CONFIRMED = "CONFIRMED"
    UNVERIFIABLE = "UNVERIFIABLE"
    BROKEN = "BROKEN"


@dataclass
class WindowEvidence:
    stage: str
    positions: list[int]
    files: list[str]
    verdict: str
    first_cell: int = -1
    last_support_cell: int = -1
    first_pos: int | None = None
    last_support_pos: int | None = None
    kind: str = BoundaryKind.NONE.value
    continuity: str = Continuity.NONE.value
    reject: str = "NONE"
    at_stream_eof: bool = False
    call_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Observation:
    pos: int
    label: Label
    confidence: float = 1.0
    frame_no: int | None = None
    file: str | None = None
    stage: str = "synthetic"
    proposal: bool = False
    text_plane: str = "UNKNOWN"
    cue: str = "UNKNOWN"
    call_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["label"] = self.label.value
        return data


@dataclass
class DecoderConfig:
    fps: float = 1.5
    confirm_window_seconds: float = 12.0
    min_credit_hits: int = 6
    min_long_credit_seconds: float = 8.0
    max_gap_seconds: float = 4.0
    end_card_min_frames: int = 2
    end_card_follow_seconds: float = 15.0
    uncertain_review_seconds: float = 4.0
    min_credit_confidence: float = 0.60
    min_end_card_confidence: float = 0.65
    min_other_confidence: float = 0.55

    def validate(self) -> None:
        if self.fps <= 0:
            raise ValueError("fps must be > 0")
        if self.min_credit_hits < 1:
            raise ValueError("min_credit_hits must be >= 1")
        if self.confirm_window_seconds <= 0:
            raise ValueError("confirm_window_seconds must be > 0")
        if self.min_long_credit_seconds <= 0:
            raise ValueError("min_long_credit_seconds must be > 0")
        if self.max_gap_seconds < 0:
            raise ValueError("max_gap_seconds must be >= 0")
        if self.end_card_min_frames < 1:
            raise ValueError("end_card_min_frames must be >= 1")
        if self.end_card_follow_seconds < 0:
            raise ValueError("end_card_follow_seconds must be >= 0")
        if self.uncertain_review_seconds < 0:
            raise ValueError("uncertain_review_seconds must be >= 0")
        for name in (
            "min_credit_confidence",
            "min_end_card_confidence",
            "min_other_confidence",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in 0..1")


@dataclass
class TemporalDecision:
    status: str
    start_pos: int | None = None
    start_frame_no: int | None = None
    provisional_start: int | None = None
    earliest_credit_pos: int | None = None
    onset_kind: str | None = None
    needs_more_context: bool = False
    publishable: bool = False
    pool_may_be_replaced: bool = False
    candidate_starts: list[int] = field(default_factory=list)
    review_bracket: list[int] | None = None
    reason: str = ""
    timeline_states: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DetectionConfig:
    """Deney dedektorunun hiz/guvenlik ayarlari."""

    fps: float = 1.5
    model: str = "qwen3-vl:30b"
    ollama_host: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 300.0
    max_wall_seconds: float = 120.0
    keep_alive: str = "10m"
    # One VLM attachment is a row-major contact sheet, not N independent
    # images. This is the main latency control on a single RTX 3090.
    image_width: int = 384
    mosaic_columns: int = 4
    jpeg_quality: int = 85
    batch_size: int = 16
    fine_overlap: int = 8
    base_stride_seconds: float = 15.0
    dense_tail_seconds: float = 90.0
    dense_stride_seconds: float = 4.0
    max_cv_proposals: int = 16
    proposal_min_distance_seconds: float = 10.0
    fine_pre_seconds: float = 6.0
    fine_post_seconds: float = 12.0
    fine_extension_seconds: float = 24.0
    max_fine_frames: int = 144
    cv_width: int = 320
    num_ctx: int = 4096
    # The live protocol is one direct window-boundary decision. 64 tokens leave
    # ample JSON-grammar headroom while bounding a slow response.
    num_predict: int = 64
    seed: int = 42
    temperature: float = 0.0
    retry_count: int = 2
    decoder: DecoderConfig | None = None

    def __post_init__(self) -> None:
        if self.decoder is None:
            self.decoder = DecoderConfig(fps=self.fps)
        else:
            # Never mutate a caller-owned DecoderConfig shared by two runs.
            self.decoder = replace(self.decoder, fps=self.fps)

    def validate(self) -> None:
        if self.fps <= 0:
            raise ValueError("fps must be > 0")
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if not self.ollama_host.strip():
            raise ValueError("ollama_host must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if self.max_wall_seconds <= 0:
            raise ValueError("max_wall_seconds must be > 0")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if not 0 <= self.fine_overlap < self.batch_size:
            raise ValueError("fine_overlap must satisfy 0 <= overlap < batch_size")
        if self.image_width < 128:
            raise ValueError("image_width must be >= 128")
        if self.mosaic_columns < 1:
            raise ValueError("mosaic_columns must be >= 1")
        if not 1 <= self.jpeg_quality <= 100:
            raise ValueError("jpeg_quality must be 1..100")
        if self.base_stride_seconds <= 0:
            raise ValueError("base_stride_seconds must be > 0")
        if self.dense_tail_seconds < 0:
            raise ValueError("dense_tail_seconds must be >= 0")
        if self.dense_tail_seconds > 0 and self.dense_stride_seconds <= 0:
            raise ValueError("dense_stride_seconds must be > 0 when dense tail is enabled")
        if self.max_cv_proposals < 0:
            raise ValueError("max_cv_proposals must be >= 0")
        if self.proposal_min_distance_seconds < 0:
            raise ValueError("proposal_min_distance_seconds must be >= 0")
        if self.fine_pre_seconds < 0:
            raise ValueError("fine_pre_seconds must be >= 0")
        if self.fine_post_seconds < 0:
            raise ValueError("fine_post_seconds must be >= 0")
        if self.max_fine_frames < self.batch_size:
            raise ValueError("max_fine_frames must be >= batch_size")
        if self.fine_extension_seconds <= 0:
            raise ValueError("fine_extension_seconds must be > 0")
        if self.cv_width < 64:
            raise ValueError("cv_width must be >= 64")
        if self.num_ctx < 512:
            raise ValueError("num_ctx must be >= 512")
        if self.num_predict < 16:
            raise ValueError("num_predict must be >= 16")
        if self.retry_count < 1:
            raise ValueError("retry_count must be >= 1")
        assert self.decoder is not None
        self.decoder.validate()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DetectionResult:
    schema_version: str
    status: str
    frame_dir: str
    output_dir: str
    total_frames: int
    fps: float
    start_pos: int | None = None
    start_frame_no: int | None = None
    start_file: str | None = None
    start_time_seconds: float | None = None
    onset_kind: str | None = None
    confidence: float = 0.0
    publishable: bool = False
    pool_may_be_replaced: bool = False
    needs_more_context: bool = False
    provisional_start: int | None = None
    review_bracket: list[int] | None = None
    candidate_starts: list[int] = field(default_factory=list)
    reason: str = ""
    source_signature: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FrameRef:
    pos: int
    frame_no: int | None
    path: Path
    timestamp_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "pos": self.pos,
            "frame_no": self.frame_no,
            "file": self.path.name,
            "path": str(self.path),
            "timestamp_seconds": round(self.timestamp_seconds, 6),
        }
