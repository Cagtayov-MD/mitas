"""Code-version provenance helper for ASR pipeline outputs."""

from __future__ import annotations

import functools
import subprocess

from core.pipelines.asr.normalize import PROJECT_ROOT


@functools.lru_cache(maxsize=1)
def get_code_version() -> str:
    """Return short git SHA, appending '-dirty' if working tree is modified.

    Returns 'unknown' on any error (missing git, detached HEAD, etc.).
    """
    root = str(PROJECT_ROOT)
    try:
        sha = subprocess.check_output(
            ["git", "-C", root, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if not sha:
            return "unknown"
        status = subprocess.check_output(
            ["git", "-C", root, "status", "--porcelain"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return f"{sha}-dirty" if status else sha
    except Exception:  # noqa: BLE001
        return "unknown"
