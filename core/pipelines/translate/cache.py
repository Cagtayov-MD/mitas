"""Append-only JSONL cache for translation results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def build_cache_key(*, source_text: str, source_lang: str, target_lang: str, model: str) -> str:
    payload = {
        "source_text": source_text,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "model": model,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class TranslationCache:
    """Small append-only cache indexed in memory per process."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.path = cache_dir / "cache.jsonl"
        self._items: dict[str, dict[str, Any]] | None = None

    def get(self, key: str) -> dict[str, Any] | None:
        return self._load().get(key)

    def put(self, key: str, result: dict[str, Any]) -> None:
        items = self._load()
        if key in items:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        record = {"key": key, "result": result}
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        items[key] = result

    def _load(self) -> dict[str, dict[str, Any]]:
        if self._items is not None:
            return self._items
        items: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                payload = json.loads(line)
                key = str(payload["key"])
                result = payload.get("result")
                if not isinstance(result, dict):
                    raise ValueError(f"Invalid cache result at {self.path}:{line_number}")
                items[key] = result
        self._items = items
        return items
