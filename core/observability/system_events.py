"""System-wide event log for MITAS.

Cross-cutting append-only JSONL at ``outputs/system_events.jsonl``. Used by the
WebUI's LOG panel to render a single timeline of "what happened, when" across
modules (upload, ASR, translate, future OCR/face/tag/logo).

Per-module step logs (ASR's ``job_log.jsonl``, etc.) stay separate and are
linked by ``job_id``; the LOG panel uses ``job_id`` to drill from a system
event into the detailed steps.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.pipelines.asr.normalize import PROJECT_ROOT

EVENTS_PATH = PROJECT_ROOT / "outputs" / "system_events.jsonl"
_LOCK = threading.Lock()

KNOWN_LEVELS = {"info", "warn", "error"}


def log_event(
    kind: str,
    *,
    summary: str,
    level: str = "info",
    module: str | None = None,
    media_id: str | None = None,
    filename: str | None = None,
    job_id: str | None = None,
    duration_seconds: float | None = None,
    error: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a system event and return the persisted payload."""
    if level not in KNOWN_LEVELS:
        level = "info"
    event: dict[str, Any] = {
        "event_id": f"evt-{uuid4().hex[:12]}",
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "level": level,
        "summary": summary,
    }
    if module:
        event["module"] = module
    if media_id:
        event["media_id"] = media_id
    if filename:
        event["filename"] = filename
    if job_id:
        event["job_id"] = job_id
    if duration_seconds is not None:
        event["duration_seconds"] = round(float(duration_seconds), 3)
    if error:
        event["error"] = str(error)[:4000]
    if detail:
        event["detail"] = detail
    _append(event)
    return event


def _append(event: dict[str, Any]) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False) + "\n"
    with _LOCK:
        with EVENTS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line)


def read_events(
    *,
    limit: int = 200,
    since: str | None = None,
    kind: str | None = None,
    level: str | None = None,
    job_id: str | None = None,
    module: str | None = None,
    media_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return newest-first system events. Filters are AND-combined.

    ``since`` accepts an ISO-8601 timestamp; events with ``ts <= since`` are
    skipped (useful for polling). ``limit`` is clamped to [1, 2000].
    """
    if not EVENTS_PATH.exists():
        return []
    try:
        text = EVENTS_PATH.read_text(encoding="utf-8")
    except OSError:
        return []

    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if since and str(payload.get("ts") or "") <= since:
            continue
        if kind and payload.get("kind") != kind:
            continue
        if level and payload.get("level") != level:
            continue
        if job_id and payload.get("job_id") != job_id:
            continue
        if module and payload.get("module") != module:
            continue
        if media_id and payload.get("media_id") != media_id:
            continue
        out.append(payload)

    out.reverse()
    return out[: max(1, min(int(limit), 2000))]


def find_event(event_id: str) -> dict[str, Any] | None:
    """Return a single event by id, or None if not found."""
    if not event_id or not EVENTS_PATH.exists():
        return None
    try:
        text = EVENTS_PATH.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("event_id") == event_id:
            return payload
    return None
