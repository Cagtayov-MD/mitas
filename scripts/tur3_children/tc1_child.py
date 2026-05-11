from __future__ import annotations

from common import emit


if __name__ == "__main__":
    emit(
        {
            "test_id": "TC1",
            "status": "skipped",
            "skip_reason": "requires isolated temporary venv package installs; not run unless TB2 identifies ctranslate2.dll",
            "transcript_present": False,
            "transcripts_valid": False,
            "notes": ["main environment untouched"],
        }
    )
    raise SystemExit(0)
