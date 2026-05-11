from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ALIGNMENT_PYTHON = ROOT / "venvs" / "alignment" / "Scripts" / "python.exe"
VARIANTS = (
    ("tools.asr_ab.transcribe_v0", None),
    ("tools.asr_ab.transcribe_v1", None),
    ("tools.asr_ab.transcribe_v2", None),
    ("tools.asr_ab.transcribe_v3", None),
    ("tools.asr_ab.transcribe_v4", None),
    ("tools.asr_ab.transcribe_v5", None),
    ("tools.asr_ab.transcribe_v6", None),
    ("tools.asr_ab.transcribe_v7", None),
    ("tools.asr_ab.transcribe_v8", None),
    ("tools.asr_ab.transcribe_v9", ALIGNMENT_PYTHON),
    ("tools.asr_ab.transcribe_v10", None),
)


def main() -> None:
    for module, python_path in VARIANTS:
        print(f"RUN {module}", flush=True)
        executable = str(python_path) if python_path is not None else sys.executable
        subprocess.run([executable, "-m", module], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "tools.asr_ab.compare_variants"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
