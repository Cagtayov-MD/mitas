from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .util import append_jsonl, now_iso


class SheriffLogger:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = threading.Lock()

    def write(self, level: str, event_type: str, message: str, *,
              run_id: str | None = None, task_id: str | None = None,
              data: dict[str, Any] | None = None) -> None:
        event = {"time": now_iso(), "level": level, "event_type": event_type,
                 "message": message, "run_id": run_id, "task_id": task_id,
                 "data": data or {}}
        with self._lock:
            append_jsonl(self.root / "events.jsonl", event)
            self.root.mkdir(parents=True, exist_ok=True)
            with (self.root / "sheriff.log").open("a", encoding="utf-8") as handle:
                scope = "/".join(value for value in (run_id, task_id) if value)
                handle.write(f"{event['time']} {level:<5} {event_type:<22} "
                             f"{scope} {message}\n")
