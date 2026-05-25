"""Dynamic window detection — Faz 4 (text-first mimari, madde 2).

Replaces the static manifest windows from Faz 2 with a tail-tracking extension:
start from a manifest-provided initial window (e.g. `opening_window_min=3`),
then probe the boundary frame with PaddleOCR detection. If text is present at
the boundary, extend the window by `step_sec` (default 60s) and probe again.
Stop when the boundary is text-free OR the maximum window is hit.

Designed for the `kind: film_credits` profile — opening (anchor=0, direction=+1)
and closing (anchor=duration, direction=-1) windows independently.

Use case that motivated this module:
    - POROROCA (2017): `opus_credit_detector` cut window to 8403-8594, but real
      scroll runs to ~8643+. Static window misses everything.
    - FRANNY (2003): detector cut to 500-542, but voice-actor card at t=683.

The implementation reuses the *existing* `paddle_engine` (PaddleOcrEngine)
instance via DI — no new init, no extra GPU session. Mirrors the pattern from
`unified_credit_pipeline.run_unified_credit_pipeline(... paddle_engine=...)`.

PaddleEngine does not currently expose a detection-only mode, so we call the
full `recognize(...)` method and treat "any record returned" as "text present".
This is slightly slower than pure detection but adds ~50-200ms per probe,
which is acceptable for the 1-5 probes per window we expect.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal


@dataclass
class DynamicWindowResult:
    """Outcome of one dynamic window search (opening or closing).

    Fields
    ------
    start_sec, end_sec
        Final window bounds (in seconds, absolute video time).
    iterations
        Number of extension probes performed (0 means initial window was kept).
    extension_log
        Human-readable per-probe entries — e.g.
        ``["t=180.0 text_present", "t=240.0 text_present", "t=300.0 boundary_clean"]``.
    initial_start_sec, initial_end_sec
        Pre-extension window (what Faz 2's static path would have used).
    max_reached
        True if the maximum window length was hit while text was still present.
    """

    start_sec: float
    end_sec: float
    iterations: int
    extension_log: list[str] = field(default_factory=list)
    initial_start_sec: float = 0.0
    initial_end_sec: float = 0.0
    max_reached: bool = False


def find_dynamic_window(
    video_path: str | Path,
    *,
    anchor_sec: float,
    direction: Literal[1, -1],
    initial_window_min: float,
    max_window_min: float,
    paddle_engine: Any,
    step_sec: float = 60.0,
    stride_sec: float = 2.0,
    has_text_fn: Callable[..., bool] | None = None,
    ffmpeg_executable: str | None = None,
) -> DynamicWindowResult:
    """Probe the boundary of an initial window and extend until text disappears.

    Parameters
    ----------
    video_path
        Source video file.
    anchor_sec
        Anchor time (sec). For openings pass ``0``, for closings pass video
        duration.
    direction
        ``+1`` extends forward (opening), ``-1`` extends backward (closing).
    initial_window_min, max_window_min
        Window sizes in **minutes**. The function starts at
        ``initial_window_min`` and grows by ``step_sec`` per iteration, capped
        at ``max_window_min``.
    paddle_engine
        Live ``PaddleOcrEngine`` instance (DI from caller). Reused across
        probes — no extra init, no GPU re-allocation. If ``None``, the search
        returns the initial window unchanged with a single log entry.
    step_sec
        Extension step in seconds. Default 60s (one minute per probe).
    stride_sec
        Gap between the two confirmation frames at a probe point. Default 2s.
    has_text_fn
        Optional override for the boundary text test (test-only injection).
        Signature: ``fn(video_path, t_sec, *, paddle_engine, stride_sec) -> bool``.
    ffmpeg_executable
        Optional ffmpeg binary path; defaults to `_resolve_ffmpeg()` resolution.

    Returns
    -------
    DynamicWindowResult
        Final bounds plus telemetry log.

    Notes
    -----
    * The "text present" test requires TWO consecutive frames (``t`` and
      ``t + stride_sec``) to both yield ≥1 OCR record. This blocks single-frame
      false positives from sub-title flashes / sparkles.
    * For closing windows (``direction=-1``), we probe at the *left* boundary
      (``start_sec``) and extend left.
    * For opening windows (``direction=+1``), we probe at the *right* boundary
      (``end_sec``) and extend right.
    """
    if direction not in (1, -1):
        raise ValueError(f"direction must be +1 or -1, got {direction!r}")
    if initial_window_min < 0:
        raise ValueError(f"initial_window_min must be >= 0, got {initial_window_min}")
    if max_window_min < initial_window_min:
        raise ValueError(
            f"max_window_min ({max_window_min}) must be >= "
            f"initial_window_min ({initial_window_min})"
        )
    if step_sec <= 0:
        raise ValueError(f"step_sec must be positive, got {step_sec}")

    initial_window_sec = float(initial_window_min) * 60.0
    max_window_sec = float(max_window_min) * 60.0
    anchor = float(anchor_sec)

    # Compute initial window
    if direction == 1:
        initial_start = anchor
        initial_end = anchor + initial_window_sec
    else:
        initial_start = anchor - initial_window_sec
        initial_end = anchor

    current_start = initial_start
    current_end = initial_end
    extension_log: list[str] = []
    iterations = 0
    max_reached = False

    probe_fn = has_text_fn if has_text_fn is not None else _has_text_at

    # Short-circuit: no engine, no probing — keep initial window
    if paddle_engine is None and has_text_fn is None:
        extension_log.append("paddle_engine=None → skip dynamic extension")
        return DynamicWindowResult(
            start_sec=current_start,
            end_sec=current_end,
            iterations=0,
            extension_log=extension_log,
            initial_start_sec=initial_start,
            initial_end_sec=initial_end,
            max_reached=False,
        )

    while True:
        # Boundary point we test next: the *outer* edge of current window
        if direction == 1:
            probe_t = current_end
        else:
            probe_t = current_start

        # Check that probing this point would not exceed max window
        current_window_sec = current_end - current_start
        if current_window_sec >= max_window_sec:
            extension_log.append(f"t={probe_t:.1f} max_reached(window={current_window_sec:.1f}s)")
            max_reached = True
            break

        try:
            present = probe_fn(
                video_path,
                probe_t,
                paddle_engine=paddle_engine,
                stride_sec=stride_sec,
                ffmpeg_executable=ffmpeg_executable,
            )
        except TypeError:
            # Fallback for injected test fns with simpler signature
            present = probe_fn(video_path, probe_t, paddle_engine=paddle_engine, stride_sec=stride_sec)

        if not present:
            extension_log.append(f"t={probe_t:.1f} boundary_clean")
            break

        # Extend
        extension_log.append(f"t={probe_t:.1f} text_present")
        iterations += 1
        if direction == 1:
            current_end = min(current_end + step_sec, initial_start + max_window_sec)
        else:
            current_start = max(current_start - step_sec, initial_end - max_window_sec)

        # After clamping, if we landed exactly at the cap, mark and stop next loop
        new_window_sec = current_end - current_start
        if new_window_sec >= max_window_sec - 1e-6:
            # We've reached the cap. Loop will detect on next iteration; bail now.
            extension_log.append(
                f"window={new_window_sec:.1f}s >= max({max_window_sec:.1f}s) → max_reached"
            )
            max_reached = True
            break

    return DynamicWindowResult(
        start_sec=current_start,
        end_sec=current_end,
        iterations=iterations,
        extension_log=extension_log,
        initial_start_sec=initial_start,
        initial_end_sec=initial_end,
        max_reached=max_reached,
    )


def _has_text_at(
    video_path: str | Path,
    t_sec: float,
    *,
    paddle_engine: Any,
    stride_sec: float = 2.0,
    ffmpeg_executable: str | None = None,
) -> bool:
    """Return True if both ``t_sec`` and ``t_sec + stride_sec`` show OCR text.

    Extracts two frames from the video, runs the paddle engine on each, and
    requires *both* to yield ≥1 record. Two-frame confirmation blocks single-
    frame false positives (sparkles, sub-title flashes, motion blur edge cases).

    On any extraction/recognition error the function returns False (fail safe:
    if we can't see, don't extend).
    """
    if paddle_engine is None:
        return False
    if t_sec < 0:
        return False

    ffmpeg_bin = ffmpeg_executable or _resolve_ffmpeg_for_dynamic_window()
    for probe_t in (float(t_sec), float(t_sec) + float(stride_sec)):
        present = _probe_single_frame(video_path, probe_t, paddle_engine, ffmpeg_bin)
        if not present:
            return False
    return True


def _probe_single_frame(
    video_path: str | Path,
    t_sec: float,
    paddle_engine: Any,
    ffmpeg_bin: str,
) -> bool:
    """Extract one frame at ``t_sec`` and return whether OCR returns ≥1 record."""
    if t_sec < 0:
        return False
    tmp_path: Path | None = None
    try:
        # Use mkstemp so we control cleanup explicitly (NamedTemporaryFile +
        # Windows + subprocess doesn't play well — file is locked while open).
        fd, tmp_name = tempfile.mkstemp(suffix=".jpg", prefix="dynwin_")
        os.close(fd)
        tmp_path = Path(tmp_name)

        command = [
            ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{t_sec:.3f}",
            "-i",
            str(video_path),
            "-vframes",
            "1",
            "-q:v",
            "2",
            str(tmp_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0 or not tmp_path.exists() or tmp_path.stat().st_size == 0:
            return False

        try:
            records = paddle_engine.recognize(
                tmp_path,
                strategy="dynamic_window_probe",
                timestamp_seconds=t_sec,
            )
        except Exception:
            return False
        return bool(records)
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _resolve_ffmpeg_for_dynamic_window() -> str:
    """Local ffmpeg lookup mirroring credit_experiment._resolve_ffmpeg().

    Keeps this module dependency-free of credit_experiment.py to avoid an
    import cycle (credit_experiment imports manifest_profiles which would
    import dynamic_window).
    """
    here = Path(__file__).resolve()
    # core/pipelines/ocr/dynamic_window.py → repo root
    project_root = here.parents[3]
    candidate = (
        project_root
        / "tools"
        / "ffmpeg-shared"
        / "ffmpeg-8.1.1-full_build-shared"
        / "bin"
        / "ffmpeg.exe"
    )
    if candidate.exists():
        return str(candidate)
    override = os.environ.get("FFMPEG_EXECUTABLE")
    if override:
        return override
    return "ffmpeg"
