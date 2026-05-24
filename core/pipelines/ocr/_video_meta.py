"""ffprobe helper — video metadata (Faz 2).

Lightweight: only `duration_seconds(path)` for now. Standalone module so
unified_credit_pipeline and credit_experiment can import without circular deps.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _resolve_ffprobe() -> str:
    """Find ffprobe; honors `FFPROBE_EXECUTABLE` env, then PATH, else "ffprobe"."""
    import os

    explicit = os.environ.get("FFPROBE_EXECUTABLE")
    if explicit:
        return explicit
    located = shutil.which("ffprobe")
    return located or "ffprobe"


def duration_seconds(path: str | Path, *, ffprobe_executable: str | None = None) -> float:
    """Return video duration in seconds via ffprobe.

    Raises:
        FileNotFoundError: if `path` doesn't exist.
        RuntimeError: if ffprobe fails or returns garbage.
    """
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"video not found: {src}")
    exe = ffprobe_executable or _resolve_ffprobe()
    cmd = [
        exe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nw=1:nk=1",
        str(src),
    ]
    try:
        proc = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffprobe failed for {src}: {exc.stderr.strip()}") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffprobe executable not found: {exe}") from exc
    raw = (proc.stdout or "").strip()
    if not raw:
        raise RuntimeError(f"ffprobe returned empty duration for {src}")
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"ffprobe returned non-numeric duration '{raw}' for {src}") from exc
