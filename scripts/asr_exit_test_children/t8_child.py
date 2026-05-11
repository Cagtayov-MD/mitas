from __future__ import annotations

from common import emit


if __name__ == "__main__":
    emit(
        {
            "test_id": "T8",
            "scenario": "version_matrix",
            "status": "skipped",
            "skip_reason": "requires isolated temporary venv package installs; not run in no-package-change pass",
            "transcript_present": False,
            "notes": ["main ASR venv and project package files were not changed"],
        }
    )
    raise SystemExit(0)
