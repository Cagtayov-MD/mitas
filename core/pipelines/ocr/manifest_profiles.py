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
) -> list[dict[str, Any]]:
    """Build the list of (start_sec, end_sec) segments for this manifest item.

    Each returned segment is `{"segment_id": str, "start_sec": float, "end_sec": float}`.

    - `kind: end_credits` → single segment derived from `start_seconds` /
      `end_seconds` (LEGACY behavior; identical to pre-Faz2 path).
    - `kind: film_credits` → opening (0 .. opening_window_min*60) + closing
      (duration - closing_window_min*60 .. duration). If the windows overlap
      (short video), they are MERGED into one segment named `full` to avoid
      double-processing the same frames.
    - `kind: kj_scan` / `scene_text` / `full_scan` → NotImplementedError.

    NOTE: dynamic window extension (Faz 4) is NOT applied here. Windows are
    fixed even when `dynamic_window=True`. Faz 4 will extend `closing_window_min`
    (and `opening_window_min`) up to their `max_*_min` caps via tail-tracking.
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
        return [{"segment_id": "legacy", "start_sec": float(start), "end_sec": float(end)}]

    if kind == KIND_FILM_CREDITS:
        opening_min = float(norm["opening_window_min"])
        closing_min = float(norm["closing_window_min"])
        if opening_min < 0 or closing_min < 0:
            raise ValueError("opening/closing_window_min must be >= 0")

        opening_end = min(opening_min * 60.0, duration)
        closing_start = max(0.0, duration - closing_min * 60.0)

        # Overlap → single 'full' segment covers everything (avoids double work)
        if closing_start <= opening_end:
            return [{
                "segment_id": "full",
                "start_sec": 0.0,
                "end_sec": duration,
            }]

        segments: list[dict[str, Any]] = []
        if opening_min > 0 and opening_end > 0:
            segments.append({
                "segment_id": "opening",
                "start_sec": 0.0,
                "end_sec": opening_end,
            })
        if closing_min > 0 and duration > closing_start:
            segments.append({
                "segment_id": "closing",
                "start_sec": closing_start,
                "end_sec": duration,
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
