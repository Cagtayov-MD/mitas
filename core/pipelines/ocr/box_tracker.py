"""Adaptive OCR bbox tracker for credit segment POC.

This module only links OCR records into text tracks. It does not route the
production pipeline and it does not call OCR, row reconstruction, or fusion.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import math
import re
from typing import Any, Iterable, Mapping


BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class BoxTrackerConfig:
    max_gap_frames: int = 5
    velocity_ema: float = 0.70
    min_confidence: float = 0.40
    min_text_similarity: float = 0.55
    strong_text_similarity: float = 0.82
    min_match_score: float = 0.56
    initial_search_radius_px: float = 90.0
    adaptive_velocity_margin: float = 1.5


@dataclass(frozen=True)
class TextDetection:
    record_index: int
    frame_index: int
    frame: str
    timestamp_seconds: float | None
    bbox: BBox
    text: str
    normalized_text: str
    confidence: float | None
    engine: str
    record: Mapping[str, Any]

    @property
    def center_x(self) -> float:
        return self.bbox[0] + self.bbox[2] / 2.0

    @property
    def center_y(self) -> float:
        return self.bbox[1] + self.bbox[3] / 2.0

    @property
    def area(self) -> float:
        return max(0.0, self.bbox[2]) * max(0.0, self.bbox[3])


@dataclass(frozen=True)
class TextTrackObservation:
    record_index: int
    frame_index: int
    frame: str
    timestamp_seconds: float | None
    bbox: BBox
    text: str
    normalized_text: str
    confidence: float | None
    area: float

    @property
    def center_x(self) -> float:
        return self.bbox[0] + self.bbox[2] / 2.0

    @property
    def center_y(self) -> float:
        return self.bbox[1] + self.bbox[3] / 2.0


@dataclass
class _MutableTrack:
    track_id: str
    engine: str
    observations: list[TextTrackObservation]
    velocity_x_px_frame: float = 0.0
    velocity_y_px_frame: float = 0.0

    @property
    def last(self) -> TextTrackObservation:
        return self.observations[-1]

    @property
    def last_frame_index(self) -> int:
        return self.last.frame_index

    @property
    def normalized_text(self) -> str:
        for observation in reversed(self.observations):
            if observation.normalized_text:
                return observation.normalized_text
        return ""


@dataclass(frozen=True)
class TextTrack:
    track_id: str
    engine: str
    observations: tuple[TextTrackObservation, ...]
    velocity_x_px_frame: float
    velocity_y_px_frame: float

    @property
    def first_timestamp_seconds(self) -> float | None:
        return self.observations[0].timestamp_seconds if self.observations else None

    @property
    def last_timestamp_seconds(self) -> float | None:
        return self.observations[-1].timestamp_seconds if self.observations else None

    @property
    def first_frame_index(self) -> int | None:
        return self.observations[0].frame_index if self.observations else None

    @property
    def last_frame_index(self) -> int | None:
        return self.observations[-1].frame_index if self.observations else None

    @property
    def record_count(self) -> int:
        return len(self.observations)

    @property
    def median_area(self) -> float:
        return _median([observation.area for observation in self.observations])

    @property
    def median_bbox(self) -> list[float]:
        if not self.observations:
            return [0.0, 0.0, 0.0, 0.0]
        return [
            round(_median([observation.bbox[index] for observation in self.observations]), 3)
            for index in range(4)
        ]

    @property
    def winner_text(self) -> str:
        counts: dict[str, tuple[int, str]] = {}
        for observation in self.observations:
            key = observation.normalized_text
            if not key:
                continue
            count, text = counts.get(key, (0, observation.text))
            counts[key] = (count + 1, text)
        if not counts:
            return ""
        return max(counts.values(), key=lambda item: (item[0], len(item[1])))[1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "engine": self.engine,
            "record_count": self.record_count,
            "first_frame_index": self.first_frame_index,
            "last_frame_index": self.last_frame_index,
            "first_timestamp_seconds": self.first_timestamp_seconds,
            "last_timestamp_seconds": self.last_timestamp_seconds,
            "median_bbox": self.median_bbox,
            "median_area": round(self.median_area, 3),
            "winner_text": self.winner_text,
            "velocity_px_frame": [
                round(self.velocity_x_px_frame, 4),
                round(self.velocity_y_px_frame, 4),
            ],
            "observations": [
                {
                    "record_index": observation.record_index,
                    "frame_index": observation.frame_index,
                    "frame": observation.frame,
                    "timestamp_seconds": observation.timestamp_seconds,
                    "bbox": [round(value, 3) for value in observation.bbox],
                    "text": observation.text,
                    "normalized_text": observation.normalized_text,
                    "confidence": observation.confidence,
                    "area": round(observation.area, 3),
                }
                for observation in self.observations
            ],
        }


def build_text_tracks(
    records: Iterable[Mapping[str, Any]],
    *,
    frames: Iterable[str] | None = None,
    frame_size: tuple[int, int] | None = None,
    config: BoxTrackerConfig | None = None,
) -> list[TextTrack]:
    """Link OCR records into adaptive text tracks.

    Matching uses predicted position from per-track velocity, text similarity,
    temporal proximity, and IoU as a supporting signal. The velocity estimate is
    updated continuously with an EMA so fast scrolls can keep their identity
    even when consecutive boxes barely overlap.
    """

    cfg = config or BoxTrackerConfig()
    detections = _prepare_detections(records, frames=frames, config=cfg)
    frame_height = _infer_frame_height(detections, frame_size)
    tracks: list[_MutableTrack] = []
    next_track_id = 1

    detections_by_frame: dict[int, list[TextDetection]] = {}
    for detection in detections:
        detections_by_frame.setdefault(detection.frame_index, []).append(detection)

    for frame_index in sorted(detections_by_frame):
        frame_detections = sorted(
            detections_by_frame[frame_index],
            key=lambda item: (item.engine, item.center_y, item.center_x, item.record_index),
        )
        candidates: list[tuple[float, int, int]] = []
        for detection_index, detection in enumerate(frame_detections):
            for track_index, track in enumerate(tracks):
                gap = detection.frame_index - track.last_frame_index
                if gap <= 0 or gap > cfg.max_gap_frames:
                    continue
                if detection.engine and track.engine and detection.engine != track.engine:
                    continue
                score = _match_score(track, detection, frame_height=frame_height, config=cfg)
                if score >= cfg.min_match_score:
                    candidates.append((score, track_index, detection_index))

        matched_tracks: set[int] = set()
        matched_detections: set[int] = set()
        for _score, track_index, detection_index in sorted(candidates, reverse=True):
            if track_index in matched_tracks or detection_index in matched_detections:
                continue
            _append_detection(tracks[track_index], frame_detections[detection_index], cfg)
            matched_tracks.add(track_index)
            matched_detections.add(detection_index)

        for detection_index, detection in enumerate(frame_detections):
            if detection_index in matched_detections:
                continue
            tracks.append(
                _MutableTrack(
                    track_id=f"bt_{next_track_id:05d}",
                    engine=detection.engine,
                    observations=[_observation_from_detection(detection)],
                )
            )
            next_track_id += 1

    return [
        TextTrack(
            track_id=track.track_id,
            engine=track.engine,
            observations=tuple(track.observations),
            velocity_x_px_frame=track.velocity_x_px_frame,
            velocity_y_px_frame=track.velocity_y_px_frame,
        )
        for track in tracks
    ]


def tracks_to_dicts(tracks: Iterable[TextTrack]) -> list[dict[str, Any]]:
    return [track.to_dict() for track in tracks]


def _prepare_detections(
    records: Iterable[Mapping[str, Any]],
    *,
    frames: Iterable[str] | None,
    config: BoxTrackerConfig,
) -> list[TextDetection]:
    frame_order: dict[str, int] = {}
    if frames is not None:
        for index, frame in enumerate(frames):
            frame_order[str(frame)] = index

    raw_records = list(records)
    if not frame_order:
        ordered_frames = sorted(
            {
                str(record.get("frame") or record.get("source_frame") or "")
                for record in raw_records
                if str(record.get("frame") or record.get("source_frame") or "")
            },
            key=lambda frame: (
                _timestamp_for_frame(raw_records, frame),
                frame,
            ),
        )
        frame_order = {frame: index for index, frame in enumerate(ordered_frames)}

    detections: list[TextDetection] = []
    for record_index, record in enumerate(raw_records):
        bbox = _coerce_bbox(record.get("bbox"))
        if bbox is None:
            continue
        frame = str(record.get("frame") or record.get("source_frame") or "")
        if not frame:
            continue
        text = str(record.get("text") or "")
        normalized_text = str(record.get("normalized_text") or _normalize_text(text))
        if not normalized_text:
            continue
        confidence = _float_or_none(record.get("confidence"))
        if confidence is not None and confidence < config.min_confidence:
            continue
        timestamp = _float_or_none(record.get("timestamp_seconds"))
        detections.append(
            TextDetection(
                record_index=record_index,
                frame_index=frame_order.setdefault(frame, len(frame_order)),
                frame=frame,
                timestamp_seconds=timestamp,
                bbox=bbox,
                text=text,
                normalized_text=normalized_text,
                confidence=confidence,
                engine=str(record.get("engine") or ""),
                record=record,
            )
        )
    detections.sort(key=lambda item: (item.frame_index, item.engine, item.center_y, item.center_x, item.record_index))
    return detections


def _append_detection(track: _MutableTrack, detection: TextDetection, config: BoxTrackerConfig) -> None:
    previous = track.last
    gap = max(1, detection.frame_index - previous.frame_index)
    vx = (detection.center_x - previous.center_x) / gap
    vy = (detection.center_y - previous.center_y) / gap
    alpha = config.velocity_ema
    if len(track.observations) == 1:
        track.velocity_x_px_frame = vx
        track.velocity_y_px_frame = vy
    else:
        track.velocity_x_px_frame = alpha * vx + (1.0 - alpha) * track.velocity_x_px_frame
        track.velocity_y_px_frame = alpha * vy + (1.0 - alpha) * track.velocity_y_px_frame
    track.observations.append(_observation_from_detection(detection))


def _match_score(track: _MutableTrack, detection: TextDetection, *, frame_height: float, config: BoxTrackerConfig) -> float:
    gap = max(1, detection.frame_index - track.last_frame_index)
    predicted = _predict_bbox(track, gap)
    radius = _search_radius(track, frame_height=frame_height, config=config)
    dist = math.hypot(_bbox_center_x(predicted) - detection.center_x, _bbox_center_y(predicted) - detection.center_y)
    box_scale = max(detection.bbox[2], detection.bbox[3], predicted[2], predicted[3], 1.0)
    position_score = 1.0 - min(1.0, dist / max(radius + box_scale, 1.0))
    text_score = _text_similarity(track.normalized_text, detection.normalized_text)
    iou_score = _bbox_iou(predicted, detection.bbox)
    temporal_score = 1.0 - min(1.0, (gap - 1) / max(config.max_gap_frames, 1))

    # Static or card-like text must agree by text and position; this prevents
    # same-position card swaps from being linked as one long track.
    speed = math.hypot(track.velocity_x_px_frame, track.velocity_y_px_frame)
    if speed < 2.0 and len(track.observations) >= 2:
        if text_score < config.min_text_similarity or position_score < 0.35:
            return 0.0
    else:
        if text_score < config.min_text_similarity and iou_score < 0.20:
            return 0.0
        if position_score < 0.22 and text_score < config.strong_text_similarity:
            return 0.0

    return 0.40 * position_score + 0.32 * text_score + 0.18 * iou_score + 0.10 * temporal_score


def _predict_bbox(track: _MutableTrack, gap_frames: int) -> BBox:
    last = track.last.bbox
    return (
        last[0] + track.velocity_x_px_frame * gap_frames,
        last[1] + track.velocity_y_px_frame * gap_frames,
        last[2],
        last[3],
    )


def _search_radius(track: _MutableTrack, *, frame_height: float, config: BoxTrackerConfig) -> float:
    base = max(5.0, 0.005 * frame_height)
    speed = math.hypot(track.velocity_x_px_frame, track.velocity_y_px_frame)
    if len(track.observations) <= 1:
        return max(config.initial_search_radius_px, base + max(track.last.bbox[2], track.last.bbox[3]) * 2.0)
    return base + speed * config.adaptive_velocity_margin


def _observation_from_detection(detection: TextDetection) -> TextTrackObservation:
    return TextTrackObservation(
        record_index=detection.record_index,
        frame_index=detection.frame_index,
        frame=detection.frame,
        timestamp_seconds=detection.timestamp_seconds,
        bbox=detection.bbox,
        text=detection.text,
        normalized_text=detection.normalized_text,
        confidence=detection.confidence,
        area=detection.area,
    )


def _coerce_bbox(value: Any) -> BBox | None:
    if not isinstance(value, (list, tuple)) or len(value) < 4:
        return None
    try:
        x, y, width, height = [float(item) for item in value[:4]]
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return (x, y, width, height)


def _bbox_iou(a: BBox, b: BBox) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2 = ax1 + aw
    ay2 = ay1 + ah
    bx2 = bx1 + bw
    by2 = by1 + bh
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _bbox_center_x(bbox: BBox) -> float:
    return bbox[0] + bbox[2] / 2.0


def _bbox_center_y(bbox: BBox) -> float:
    return bbox[1] + bbox[3] / 2.0


def _text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _normalize_text(text: str) -> str:
    text = text.strip().upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _timestamp_for_frame(records: list[Mapping[str, Any]], frame: str) -> float:
    for record in records:
        record_frame = str(record.get("frame") or record.get("source_frame") or "")
        if record_frame == frame:
            timestamp = _float_or_none(record.get("timestamp_seconds"))
            if timestamp is not None:
                return timestamp
    return 0.0


def _infer_frame_height(detections: list[TextDetection], frame_size: tuple[int, int] | None) -> float:
    if frame_size and len(frame_size) >= 2:
        return float(frame_size[1])
    max_bottom = 0.0
    for detection in detections:
        max_bottom = max(max_bottom, detection.bbox[1] + detection.bbox[3])
    return max(max_bottom, 1.0)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) / 2.0)


# ---------------------------------------------------------------------------
# Public helpers for K-BoxTrack pipeline
# ---------------------------------------------------------------------------


def classify_track_motion(track: TextTrack, *, static_speed_threshold: float = 2.0) -> str:
    """Return 'static_text' if |velocity_y| < threshold and observation_count >= 3, else 'scrolling_text'.
    Single-observation tracks return 'unknown'."""
    if track.record_count < 2:
        return "unknown"
    if track.record_count >= 3 and abs(track.velocity_y_px_frame) < static_speed_threshold:
        return "static_text"
    if abs(track.velocity_y_px_frame) >= static_speed_threshold:
        return "scrolling_text"
    # 2 observations, below threshold — treat as static
    return "static_text"


def group_static_tracks_into_cards(
    tracks: list[TextTrack],
    *,
    max_time_gap_seconds: float = 1.5,
    max_y_overlap_ratio: float = 0.0,
    mode: str | None = None,
    min_window_overlap_ratio: float = 0.3,
) -> list[dict]:
    """Group static tracks into cards.

    mode:
      None/"gap"     → first_ts farkı > max_time_gap_seconds ise yeni kart (mevcut davranış).
      "overlap"      → yaşam pencereleri [first_ts, last_ts] overlap ediyorsa aynı kart;
                       ratio = overlap_duration / min(card_duration, track_duration);
                       ratio < min_window_overlap_ratio ise yeni kart.

    Aynı kartta birden fazla satır farklı stride frame'lerinde doğduğu için
    "gap" modu over-segment ediyor; "overlap" modu sahnede gerçekten birlikte
    olan track'leri tek kartta toplar.

    Returns list of {card_id, track_ids, first_timestamp, last_timestamp, y_range, member_count}.
    Only consumes tracks where classify_track_motion(...) == 'static_text'.
    """
    if mode is None:
        mode = _card_grouping_mode()

    static_tracks = [t for t in tracks if classify_track_motion(t) == "static_text"]
    if not static_tracks:
        return []

    if mode == "overlap":
        return _group_by_window_overlap(
            static_tracks,
            min_window_overlap_ratio=min_window_overlap_ratio,
            max_y_overlap_ratio=max_y_overlap_ratio,
        )
    # default "gap"
    return _group_by_first_ts_gap(
        static_tracks,
        max_time_gap_seconds=max_time_gap_seconds,
        max_y_overlap_ratio=max_y_overlap_ratio,
    )


def _card_grouping_mode() -> str:
    """Env var'dan mode oku. OCR_CARD_GROUPING: gap|overlap. Default gap."""
    import os
    value = os.environ.get("OCR_CARD_GROUPING", "gap").strip().lower()
    return value if value in {"gap", "overlap"} else "gap"


def _group_by_first_ts_gap(
    static_tracks: list[TextTrack],
    *,
    max_time_gap_seconds: float,
    max_y_overlap_ratio: float,
) -> list[dict]:
    """first_ts farkı > max_time_gap_seconds ise yeni kart (orijinal davranış)."""
    # Sort by first_timestamp then by median y
    def _sort_key(t: TextTrack) -> tuple[float, float]:
        ts = t.first_timestamp_seconds if t.first_timestamp_seconds is not None else 0.0
        y = t.median_bbox[1]
        return (ts, y)

    static_tracks = sorted(static_tracks, key=_sort_key)

    cards: list[dict] = []
    current_card_tracks: list[TextTrack] = []

    def _card_y_range(card_tracks: list[TextTrack]) -> tuple[float, float]:
        y_min = min(t.median_bbox[1] for t in card_tracks)
        y_max = max(t.median_bbox[1] + t.median_bbox[3] for t in card_tracks)
        return (y_min, y_max)

    def _y_overlap_ratio(y_range: tuple[float, float], track: TextTrack) -> float:
        card_y0, card_y1 = y_range
        track_y0 = track.median_bbox[1]
        track_y1 = track_y0 + track.median_bbox[3]
        inter = max(0.0, min(card_y1, track_y1) - max(card_y0, track_y0))
        union = max(card_y1, track_y1) - min(card_y0, track_y0)
        return inter / union if union > 0 else 0.0

    def _flush_card(card_tracks: list[TextTrack]) -> None:
        if not card_tracks:
            return
        card_id = f"card_{len(cards) + 1:03d}"
        first_ts = min(
            (t.first_timestamp_seconds for t in card_tracks if t.first_timestamp_seconds is not None),
            default=0.0,
        )
        last_ts = max(
            (t.last_timestamp_seconds for t in card_tracks if t.last_timestamp_seconds is not None),
            default=0.0,
        )
        y0, y1 = _card_y_range(card_tracks)
        cards.append(
            {
                "card_id": card_id,
                "track_ids": [t.track_id for t in card_tracks],
                "first_timestamp": first_ts,
                "last_timestamp": last_ts,
                "y_range": [y0, y1],
                "member_count": len(card_tracks),
            }
        )

    for track in static_tracks:
        if not current_card_tracks:
            current_card_tracks.append(track)
            continue

        # Time-gap between consecutive sorted track first_timestamps. Tracks are
        # sorted by first_ts, so this measures the spacing between adjacent track
        # birth events. A large gap signals a card boundary (the previous card
        # stopped spawning lines; a new card began).
        prev_first_ts = current_card_tracks[-1].first_timestamp_seconds
        this_first_ts = track.first_timestamp_seconds
        time_gap = 0.0
        if prev_first_ts is not None and this_first_ts is not None:
            time_gap = abs(this_first_ts - prev_first_ts)

        if time_gap > max_time_gap_seconds:
            _flush_card(current_card_tracks)
            current_card_tracks = [track]
            continue

        # Optional y-overlap gate (disabled by default; only enforced when ratio > 0)
        if max_y_overlap_ratio > 0:
            y_range = _card_y_range(current_card_tracks)
            overlap = _y_overlap_ratio(y_range, track)
            if overlap < max_y_overlap_ratio:
                _flush_card(current_card_tracks)
                current_card_tracks = [track]
                continue

        current_card_tracks.append(track)

    _flush_card(current_card_tracks)
    return cards


def _group_by_window_overlap(
    static_tracks: list[TextTrack],
    *,
    min_window_overlap_ratio: float,
    max_y_overlap_ratio: float,
) -> list[dict]:
    """Yaşam penceresi overlap'ine göre grupla.

    Track A [A.first, A.last] ile card'ın kümülatif penceresi [win_first, win_last]
    kesişme oranı >= min_window_overlap_ratio ise aynı kart; değilse yeni kart açılır.
    """
    def _sort_key(t: TextTrack) -> tuple[float, float]:
        ts = t.first_timestamp_seconds if t.first_timestamp_seconds is not None else 0.0
        y = t.median_bbox[1]
        return (ts, y)

    static_tracks = sorted(static_tracks, key=_sort_key)

    cards: list[dict] = []
    current_card_tracks: list[TextTrack] = []
    current_window: tuple[float, float] | None = None  # (first_ts_min, last_ts_max)

    def _track_window(t: TextTrack) -> tuple[float, float]:
        first = t.first_timestamp_seconds if t.first_timestamp_seconds is not None else 0.0
        last = t.last_timestamp_seconds if t.last_timestamp_seconds is not None else first
        return (first, last)

    def _window_overlap_ratio(window: tuple[float, float], track_window: tuple[float, float]) -> float:
        overlap = max(0.0, min(window[1], track_window[1]) - max(window[0], track_window[0]))
        card_dur = max(0.0, window[1] - window[0])
        track_dur = max(0.0, track_window[1] - track_window[0])
        min_dur = min(card_dur, track_dur)
        if min_dur <= 0.0:
            return 1.0 if overlap > 0 else 0.0
        return overlap / min_dur

    def _flush_card(card_tracks: list[TextTrack]) -> None:
        if not card_tracks:
            return
        card_id = f"card_{len(cards) + 1:03d}"
        first_ts = min(
            (t.first_timestamp_seconds for t in card_tracks if t.first_timestamp_seconds is not None),
            default=0.0,
        )
        last_ts = max(
            (t.last_timestamp_seconds for t in card_tracks if t.last_timestamp_seconds is not None),
            default=0.0,
        )
        y_min = min(t.median_bbox[1] for t in card_tracks)
        y_max = max(t.median_bbox[1] + t.median_bbox[3] for t in card_tracks)
        cards.append({
            "card_id": card_id,
            "track_ids": [t.track_id for t in card_tracks],
            "first_timestamp": first_ts,
            "last_timestamp": last_ts,
            "y_range": [y_min, y_max],
            "member_count": len(card_tracks),
        })

    def _y_overlap_ratio_helper(card_tracks: list[TextTrack], track: TextTrack) -> float:
        y_min = min(t.median_bbox[1] for t in card_tracks)
        y_max = max(t.median_bbox[1] + t.median_bbox[3] for t in card_tracks)
        track_y0 = track.median_bbox[1]
        track_y1 = track_y0 + track.median_bbox[3]
        inter = max(0.0, min(y_max, track_y1) - max(y_min, track_y0))
        union = max(y_max, track_y1) - min(y_min, track_y0)
        return inter / union if union > 0 else 0.0

    for track in static_tracks:
        tw = _track_window(track)
        if not current_card_tracks:
            current_card_tracks = [track]
            current_window = tw
            continue

        ratio = _window_overlap_ratio(current_window, tw)
        if ratio < min_window_overlap_ratio:
            _flush_card(current_card_tracks)
            current_card_tracks = [track]
            current_window = tw
            continue

        # Optional y-overlap gate (rare use; default 0.0 → kapalı)
        if max_y_overlap_ratio > 0:
            y_overlap = _y_overlap_ratio_helper(current_card_tracks, track)
            if y_overlap < max_y_overlap_ratio:
                _flush_card(current_card_tracks)
                current_card_tracks = [track]
                current_window = tw
                continue

        current_card_tracks.append(track)
        current_window = (
            min(current_window[0], tw[0]),
            max(current_window[1], tw[1]),
        )

    _flush_card(current_card_tracks)
    return cards


def select_best_frame_per_card(
    card: dict,
    tracks: list[TextTrack],
    frame_paths: list[str],
) -> dict:
    """For each card, pick the frame within card time-range that has the highest sum of confidences
    across the card's tracks at that frame. Returns {card_id, best_frame_path, best_frame_index, score,
    contributing_tracks}. Falls back to median-frame if no confidence data."""
    card_id = card["card_id"]
    track_ids = set(card["track_ids"])
    card_tracks = [t for t in tracks if t.track_id in track_ids]

    # Build frame_index -> total confidence
    frame_scores: dict[int, float] = {}
    frame_obs_map: dict[int, list[str]] = {}
    for track in card_tracks:
        for obs in track.observations:
            fi = obs.frame_index
            conf = obs.confidence if obs.confidence is not None else 0.0
            frame_scores[fi] = frame_scores.get(fi, 0.0) + conf
            frame_obs_map.setdefault(fi, []).append(track.track_id)

    if frame_scores:
        best_fi = max(frame_scores, key=lambda k: frame_scores[k])
        best_score = frame_scores[best_fi]
        contributing = frame_obs_map.get(best_fi, [])
    else:
        # Fallback: median frame index among all observations
        all_indices = [obs.frame_index for t in card_tracks for obs in t.observations]
        if all_indices:
            best_fi = int(_median([float(i) for i in all_indices]))
        else:
            best_fi = 0
        best_score = 0.0
        contributing = []

    best_frame_path: str | None = None
    if 0 <= best_fi < len(frame_paths):
        best_frame_path = frame_paths[best_fi]

    return {
        "card_id": card_id,
        "best_frame_path": best_frame_path,
        "best_frame_index": best_fi,
        "score": round(best_score, 4),
        "contributing_tracks": contributing,
    }
