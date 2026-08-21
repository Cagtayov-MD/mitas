from __future__ import annotations

from pathlib import Path
from .modeller import Observation


class InputError(ValueError):
    pass


def read_source(source: str, path: str | Path) -> list[Observation]:
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise InputError(f"{source}: girdi dosyasi yok: {p}")
    text = p.read_text(encoding="utf-8", errors="replace")
    result: list[Observation] = []
    seq = 0
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        seq += 1
        result.append(Observation(f"{source}:{seq:06d}", source, seq, raw))
    return result
