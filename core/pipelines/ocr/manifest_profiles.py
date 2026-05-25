"""Manifest profile system — Faz 2 (text-first mimari, madde 6).

Adds a `kind` field profile system on top of the existing manifest loader.
The legacy `kind: end_credits` continues to work byte-identical via a single
segment derived from `start_seconds`/`end_seconds` (full backward compatibility).

New `kind: film_credits` produces TWO segments (opening + closing) using
fixed windows (`opening_window_min`, `closing_window_min`). Dynamic window
extension is Faz 4 — for now the windows are STATIC.

The remaining kinds (`kj_scan`, `scene_text`, `full_scan`) are stubs that
raise `NotImplementedError` — they exist in the schema so callers know they
are planned but not yet implemented.

Reference: `core/pipelines/ocr/schemas/manifest_v2.schema.json`,
`docs/MITAS_OCR_TextFirst_Mimari_v1.md` §3, §5.
"""

from __future__ import annotations

from typing import Any, Callable

# --- Profile string constants (mirror schema enum) ---
KIND_END_CREDITS = "end_credits"          # LEGACY: single segment from start/end_seconds
KIND_FILM_CREDITS = "film_credits"        # NEW: opening + closing fixed windows
KIND_KJ_SCAN = "kj_scan"                  # STUB V1
KIND_SCENE_TEXT = "scene_text"            # STUB V1
KIND_FULL_SCAN = "full_scan"              # STUB V1

# Defaults mirror manifest_v2.schema.json defaults
_DEFAULT_OPENING_WINDOW_MIN = 3.0
_DEFAULT_CLOSING_WINDOW_MIN = 5.0
_DEFAULT_MAX_OPENING_MIN = 8.0
_DEFAULT_MAX_CLOSING_MIN = 15.0
_DEFAULT_DYNAMIC_WINDOW = True
_DEFAULT_FPS = 6
_DEFAULT_LANGUAGE = "tr"

_KNOWN_KINDS = {
    KIND_END_CREDITS,
    KIND_FILM_CREDITS,
    KIND_KJ_SCAN,
    KIND_SCENE_TEXT,
    KIND_FULL_SCAN,
}

_STUB_KINDS = {KIND_KJ_SCAN, KIND_SCENE_TEXT, KIND_FULL_SCAN}


def normalize_manifest_item(item: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `item` with profile defaults filled in.

    Schema compatibility: `core/pipelines/ocr/schemas/manifest_v2.schema.json`.
    Required upstream: `id`, `path`, `kind`.

    LEGACY (`kind: end_credits`): does NOT inject opening/closing windows — the
    legacy path uses `start_seconds`/`end_seconds` directly. Defaults for new
    fields are still set so the dict is uniform.

    Stubs (`kj_scan`, `scene_text`, `full_scan`): defaults filled, NotImplemented
    is raised later by `build_segments_for_item` / `dispatch_runner`.
    """
    if not isinstance(item, dict):
        raise TypeError(f"manifest item must be dict, got {type(item).__name__}")

    out: dict[str, Any] = dict(item)
    kind = str(out.get("kind") or "")
    if kind not in _KNOWN_KINDS:
        raise ValueError(
            f"unknown kind '{kind}' in manifest item id='{out.get('id', '?')}'. "
            f"Allowed: {sorted(_KNOWN_KINDS)}"
        )

    out.setdefault("expected_language", _DEFAULT_LANGUAGE)
    out.setdefault("fps", _DEFAULT_FPS)
    out.setdefault("opening_window_min", _DEFAULT_OPENING_WINDOW_MIN)
    out.setdefault("closing_window_min", _DEFAULT_CLOSING_WINDOW_MIN)
    out.setdefault("max_opening_min", _DEFAULT_MAX_OPENING_MIN)
    out.setdefault("max_closing_min", _DEFAULT_MAX_CLOSING_MIN)
    out.setdefault("dynamic_window", _DEFAULT_DYNAMIC_WINDOW)
    return out


def build_segments_for_item(
    item: dict[str, Any],
    video_duration_sec: float,
    *,
    paddle_engine: Any = None,
    ffmpeg_executable: str | None = None,
) -> list[dict[str, Any]]:
    """Build the list of (start_sec, end_sec) segments for this manifest item.

    Each returned segment is
    ``{"segment_id": str, "start_sec": float, "end_sec": float, "dynamic_window": dict|None}``.
    The optional ``dynamic_window`` key holds telemetry from
    :func:`core.pipelines.ocr.dynamic_window.find_dynamic_window` (iterations,
    extension_log, initial bounds, max_reached) when dynamic extension ran.

    - `kind: end_credits` → single segment derived from `start_seconds` /
      `end_seconds` (LEGACY behavior; identical to pre-Faz2 path).
    - `kind: film_credits` → opening (0 .. opening_window_min*60) + closing
      (duration - closing_window_min*60 .. duration). If `dynamic_window` is
      ``True`` (default per schema) and ``paddle_engine`` is supplied, each
      window's outer boundary is probed and extended in `step_sec` increments
      up to `max_opening_min` / `max_closing_min`. If the windows overlap after
      extension, they are MERGED into one segment named `full`.
    - `kind: kj_scan` / `scene_text` / `full_scan` → NotImplementedError.

    ``paddle_engine`` is optional. When ``dynamic_window=True`` but
    ``paddle_engine`` is not supplied, the function falls back to the static
    Faz 2 behavior and records that fact in the segment's ``dynamic_window``
    telemetry (``skipped_no_engine: True``).
    """
    if not isinstance(item, dict):
        raise TypeError(f"manifest item must be dict, got {type(item).__name__}")
    duration = float(video_duration_sec)
    if duration <= 0:
        raise ValueError(f"video_duration_sec must be positive, got {duration}")

    norm = normalize_manifest_item(item)
    kind = norm["kind"]

    if kind == KIND_END_CREDITS:
        start = norm.get("start_seconds")
        end = norm.get("end_seconds")
        if start is None or end is None:
            raise ValueError(
                f"kind=end_credits requires start_seconds + end_seconds "
                f"(item id='{norm.get('id', '?')}')"
            )
        return [{
            "segment_id": "legacy",
            "start_sec": float(start),
            "end_sec": float(end),
            "dynamic_window": None,
        }]

    if kind == KIND_FILM_CREDITS:
        opening_min = float(norm["opening_window_min"])
        closing_min = float(norm["closing_window_min"])
        max_opening_min = float(norm["max_opening_min"])
        max_closing_min = float(norm["max_closing_min"])
        dynamic_enabled = bool(norm["dynamic_window"])
        if opening_min < 0 or closing_min < 0:
            raise ValueError("opening/closing_window_min must be >= 0")

        video_path = norm.get("path")

        # --- Compute opening bounds (with optional dynamic extension) ---
        opening_telemetry: dict[str, Any] | None = None
        if opening_min > 0:
            base_opening_end = min(opening_min * 60.0, duration)
            opening_start = 0.0
            opening_end = base_opening_end
            if dynamic_enabled and video_path:
                opening_end, opening_telemetry = _extend_window(
                    video_path=str(video_path),
                    anchor_sec=0.0,
                    direction=1,
                    initial_window_min=opening_min,
                    max_window_min=max_opening_min,
                    duration_cap_sec=duration,
                    paddle_engine=paddle_engine,
                    ffmpeg_executable=ffmpeg_executable,
                )
        else:
            opening_start = 0.0
            opening_end = 0.0

        # --- Compute closing bounds (with optional dynamic extension) ---
        closing_telemetry: dict[str, Any] | None = None
        if closing_min > 0:
            base_closing_start = max(0.0, duration - closing_min * 60.0)
            closing_start = base_closing_start
            closing_end = duration
            if dynamic_enabled and video_path:
                closing_start, closing_telemetry = _extend_window(
                    video_path=str(video_path),
                    anchor_sec=duration,
                    direction=-1,
                    initial_window_min=closing_min,
                    max_window_min=max_closing_min,
                    duration_cap_sec=duration,
                    paddle_engine=paddle_engine,
                    ffmpeg_executable=ffmpeg_executable,
                )
        else:
            closing_start = duration
            closing_end = duration

        # Overlap (after extension) → single 'full' segment covers everything
        opening_active = opening_min > 0 and opening_end > 0
        closing_active = closing_min > 0 and duration > closing_start
        if opening_active and closing_active and closing_start <= opening_end:
            merged_telemetry: dict[str, Any] | None = None
            if opening_telemetry or closing_telemetry:
                merged_telemetry = {
                    "merged_from": ["opening", "closing"],
                    "opening": opening_telemetry,
                    "closing": closing_telemetry,
                }
            return [{
                "segment_id": "full",
                "start_sec": 0.0,
                "end_sec": duration,
                "dynamic_window": merged_telemetry,
            }]

        segments: list[dict[str, Any]] = []
        if opening_active:
            segments.append({
                "segment_id": "opening",
                "start_sec": opening_start,
                "end_sec": opening_end,
                "dynamic_window": opening_telemetry,
            })
        if closing_active:
            segments.append({
                "segment_id": "closing",
                "start_sec": closing_start,
                "end_sec": closing_end,
                "dynamic_window": closing_telemetry,
            })
        if not segments:
            raise ValueError(
                f"kind=film_credits item id='{norm.get('id', '?')}' produced "
                f"no segments (both windows are 0?)"
            )
        return segments

    if kind in _STUB_KINDS:
        raise NotImplementedError(
            f"Profile '{kind}' is stub in V1; planned for V2."
        )

    # Should be unreachable thanks to normalize_manifest_item
    raise ValueError(f"unhandled kind '{kind}'")


def _extend_window(
    *,
    video_path: str,
    anchor_sec: float,
    direction: int,
    initial_window_min: float,
    max_window_min: float,
    duration_cap_sec: float,
    paddle_engine: Any,
    ffmpeg_executable: str | None,
) -> tuple[float, dict[str, Any]]:
    """Run dynamic window probing and return (new_boundary_sec, telemetry).

    For direction=+1 (opening): returns the new ``end_sec``.
    For direction=-1 (closing): returns the new ``start_sec``.

    Always returns telemetry — including a `skipped_no_engine` flag when no
    paddle engine is available (so the static fallback is auditable).
    """
    # Local import keeps the cost of dynamic_window (ffmpeg/subprocess) out of
    # callers that never use film_credits.
    from core.pipelines.ocr.dynamic_window import find_dynamic_window

    if paddle_engine is None:
        # Faz 2-equivalent static behavior — still return a structured trace
        # so the caller knows dynamic was requested but skipped.
        if direction == 1:
            boundary = min(anchor_sec + initial_window_min * 60.0, duration_cap_sec)
        else:
            boundary = max(anchor_sec - initial_window_min * 60.0, 0.0)
        return boundary, {
            "skipped_no_engine": True,
            "initial_window_min": initial_window_min,
            "max_window_min": max_window_min,
            "iterations": 0,
            "extension_log": ["paddle_engine=None → static fallback"],
            "max_reached": False,
        }

    result = find_dynamic_window(
        video_path,
        anchor_sec=anchor_sec,
        direction=direction,  # type: ignore[arg-type]
        initial_window_min=initial_window_min,
        max_window_min=max_window_min,
        paddle_engine=paddle_engine,
        ffmpeg_executable=ffmpeg_executable,
    )

    if direction == 1:
        boundary = min(result.end_sec, duration_cap_sec)
    else:
        boundary = max(result.start_sec, 0.0)

    telemetry = {
        "skipped_no_engine": False,
        "initial_window_min": initial_window_min,
        "max_window_min": max_window_min,
        "iterations": result.iterations,
        "extension_log": list(result.extension_log),
        "initial_start_sec": result.initial_start_sec,
        "initial_end_sec": result.initial_end_sec,
        "final_start_sec": result.start_sec,
        "final_end_sec": result.end_sec,
        "max_reached": result.max_reached,
    }
    return boundary, telemetry


def dispatch_runner(
    item: dict[str, Any],
    video_duration_sec: float,  # noqa: ARG001  (kept for future kinds)
) -> Callable[..., Any]:
    """Pick the per-segment runner for this manifest item.

    All implemented kinds currently use the same K-BoxTrack pipeline
    (`run_unified_credit_pipeline`); only the segment list differs. Stub kinds
    raise NotImplementedError.
    """
    if not isinstance(item, dict):
        raise TypeError(f"manifest item must be dict, got {type(item).__name__}")
    kind = str(item.get("kind") or "")
    if kind not in _KNOWN_KINDS:
        raise ValueError(f"unknown kind '{kind}'")
    if kind in _STUB_KINDS:
        raise NotImplementedError(
            f"Profile '{kind}' is stub in V1; planned for V2."
        )
    # end_credits + film_credits → same runner
    from core.pipelines.ocr.unified_credit_pipeline import run_unified_credit_pipeline
    return run_unified_credit_pipeline
