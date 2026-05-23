"""Track-level STATIC/MOVING/GONE classification for OCR bbox tracks."""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Any, Iterable

from core.pipelines.ocr.box_tracker import TextTrack


@dataclass(frozen=True)
class TrackStateConfig:
    min_observations: int = 3
    moving_entry_speed_px_s: float = 5.0
    moving_exit_speed_px_s: float = 2.0
    jitter_floor_px: float = 3.0
    jitter_frame_height_ratio: float = 0.005
    min_direction_consistency: float = 0.60


@dataclass(frozen=True)
class TextTrackState:
    track_id: str
    state: str
    confidence: float
    record_count: int
    first_timestamp_seconds: float | None
    last_timestamp_seconds: float | None
    first_frame_index: int | None
    last_frame_index: int | None
    duration_seconds: float | None
    displacement_px: tuple[float, float]
    median_speed_px_s: float
    median_velocity_px_s: tuple[float, float]
    direction_consistency: float
    median_area: float
    median_bbox: list[float]
    winner_text: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "state": self.state,
            "confidence": round(self.confidence, 4),
            "record_count": self.record_count,
            "first_timestamp_seconds": self.first_timestamp_seconds,
            "last_timestamp_seconds": self.last_timestamp_seconds,
            "first_frame_index": self.first_frame_index,
            "last_frame_index": self.last_frame_index,
            "duration_seconds": None if self.duration_seconds is None else round(self.duration_seconds, 4),
            "displacement_px": [round(self.displacement_px[0], 4), round(self.displacement_px[1], 4)],
            "median_speed_px_s": round(self.median_speed_px_s, 4),
            "median_velocity_px_s": [
                round(self.median_velocity_px_s[0], 4),
                round(self.median_velocity_px_s[1], 4),
            ],
            "direction_consistency": round(self.direction_consistency, 4),
            "median_area": round(self.median_area, 3),
            "median_bbox": self.median_bbox,
            "winner_text": self.winner_text,
            "reason": self.reason,
        }


def classify_text_track_states(
    tracks: Iterable[TextTrack],
    *,
    frame_size: tuple[int, int] | None = None,
    config: TrackStateConfig | None = None,
) -> list[TextTrackState]:
    cfg = config or TrackStateConfig()
    track_list = list(tracks)
    frame_height = float(frame_size[1]) if frame_size and len(frame_size) >= 2 else _infer_frame_height(track_list)
    return [_classify_track(track, frame_height=frame_height, config=cfg) for track in track_list]


def track_states_to_dicts(states: Iterable[TextTrackState]) -> list[dict[str, Any]]:
    return [state.to_dict() for state in states]


def _classify_track(track: TextTrack, *, frame_height: float, config: TrackStateConfig) -> TextTrackState:
    observations = list(track.observations)
    if not observations:
        return _empty_state(track, "GONE", "no_observations")

    duration = _duration_seconds(track)
    dx = observations[-1].center_x - observations[0].center_x
    dy = observations[-1].center_y - observations[0].center_y
    velocities = _instant_velocities(track)
    speeds = [math.hypot(vx, vy) for vx, vy in velocities]
    median_speed = float(median(speeds)) if speeds else 0.0
    median_vx = float(median([vx for vx, _vy in velocities])) if velocities else 0.0
    median_vy = float(median([vy for _vx, vy in velocities])) if velocities else 0.0
    direction_consistency = _direction_consistency(velocities)
    jitter_px = max(config.jitter_floor_px, config.jitter_frame_height_ratio * frame_height)
    displacement = math.hypot(dx, dy)

    if len(observations) < config.min_observations:
        state = "UNKNOWN"
        confidence = 0.25
        reason = f"low_track_support:{len(observations)}"
    elif displacement <= jitter_px and median_speed <= config.moving_entry_speed_px_s:
        state = "STATIC"
        confidence = 0.92
        reason = f"within_jitter:{round(displacement, 3)}<={round(jitter_px, 3)}"
    elif (
        median_speed >= config.moving_entry_speed_px_s
        and displacement >= jitter_px * 2.0
        and direction_consistency >= config.min_direction_consistency
    ):
        state = "MOVING"
        speed_score = min(1.0, median_speed / max(config.moving_entry_speed_px_s * 3.0, 1.0))
        consistency_score = direction_consistency
        displacement_score = min(1.0, displacement / max(jitter_px * 8.0, 1.0))
        confidence = 0.35 + 0.25 * speed_score + 0.25 * consistency_score + 0.15 * displacement_score
        reason = "speed_displacement_direction"
    elif median_speed <= config.moving_exit_speed_px_s or displacement < jitter_px * 2.0:
        state = "STATIC"
        confidence = 0.72
        reason = "below_moving_hysteresis"
    else:
        state = "UNKNOWN"
        confidence = 0.45
        reason = "ambiguous_motion"

    return TextTrackState(
        track_id=track.track_id,
        state=state,
        confidence=min(1.0, max(0.0, confidence)),
        record_count=track.record_count,
        first_timestamp_seconds=track.first_timestamp_seconds,
        last_timestamp_seconds=track.last_timestamp_seconds,
        first_frame_index=track.first_frame_index,
        last_frame_index=track.last_frame_index,
        duration_seconds=duration,
        displacement_px=(dx, dy),
        median_speed_px_s=median_speed,
        median_velocity_px_s=(median_vx, median_vy),
        direction_consistency=direction_consistency,
        median_area=track.median_area,
        median_bbox=track.median_bbox,
        winner_text=track.winner_text,
        reason=reason,
    )


def _empty_state(track: TextTrack, state: str, reason: str) -> TextTrackState:
    return TextTrackState(
        track_id=track.track_id,
        state=state,
        confidence=0.0,
        record_count=0,
        first_timestamp_seconds=None,
        last_timestamp_seconds=None,
        first_frame_index=None,
        last_frame_index=None,
        duration_seconds=None,
        displacement_px=(0.0, 0.0),
        median_speed_px_s=0.0,
        median_velocity_px_s=(0.0, 0.0),
        direction_consistency=0.0,
        median_area=0.0,
        median_bbox=[0.0, 0.0, 0.0, 0.0],
        winner_text="",
        reason=reason,
    )


def _instant_velocities(track: TextTrack) -> list[tuple[float, float]]:
    velocities: list[tuple[float, float]] = []
    observations = list(track.observations)
    for previous, current in zip(observations, observations[1:]):
        dt = _delta_time(previous.timestamp_seconds, current.timestamp_seconds)
        if dt <= 0:
            frame_gap = max(1, current.frame_index - previous.frame_index)
            dt = float(frame_gap)
        velocities.append(((current.center_x - previous.center_x) / dt, (current.center_y - previous.center_y) / dt))
    return velocities


def _direction_consistency(velocities: list[tuple[float, float]]) -> float:
    meaningful = [(vx, vy) for vx, vy in velocities if math.hypot(vx, vy) >= 1.0]
    if not meaningful:
        return 1.0
    vertical_votes = [1 if vy >= 0 else -1 for _vx, vy in meaningful if abs(vy) >= abs(_vx)]
    horizontal_votes = [1 if vx >= 0 else -1 for vx, vy in meaningful if abs(vx) > abs(vy)]
    votes = vertical_votes if len(vertical_votes) >= len(horizontal_votes) else horizontal_votes
    if not votes:
        return 1.0
    positive = sum(1 for vote in votes if vote > 0)
    negative = len(votes) - positive
    return max(positive, negative) / len(votes)


def _duration_seconds(track: TextTrack) -> float | None:
    first = track.first_timestamp_seconds
    last = track.last_timestamp_seconds
    if first is None or last is None:
        return None
    return max(0.0, float(last) - float(first))


def _delta_time(previous: float | None, current: float | None) -> float:
    if previous is None or current is None:
        return 0.0
    return max(0.0, float(current) - float(previous))


def _infer_frame_height(tracks: list[TextTrack]) -> float:
    max_bottom = 0.0
    for track in tracks:
        for observation in track.observations:
            max_bottom = max(max_bottom, observation.bbox[1] + observation.bbox[3])
    return max(max_bottom, 1.0)
