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


def _iter_lines_reversed(path: Path, *, block_size: int = 64 * 1024) -> Any:
    """Yield raw text lines from ``path`` newest-first (son satirdan basa).

    Dosyayi SONDAN okur: yalnizca gereken kadar byte seek edilir, dosyanin
    tamami RAM'e alinmaz. Kucuk dosyada da dogru calisir (tek blok ile basa
    ulasilinca kalan ilk parca da satir olarak verilir). Bozuk/yarim son satir
    cagiranin json.loads'unda elenir.
    """
    with path.open("rb") as handle:
        handle.seek(0, 2)  # dosya sonu
        pos = handle.tell()
        carry = b""  # blok sinirinda kalan, henuz tamamlanmamis (en eski) parca
        while pos > 0:
            read_size = min(block_size, pos)
            pos -= read_size
            handle.seek(pos)
            chunk = handle.read(read_size) + carry
            parts = chunk.split(b"\n")
            # parts[0] bu blogun en basindaki parca; daha geride veri varsa
            # bir sonraki (daha eski) blokla birlesmesi gerek → carry'ye sakla.
            carry = parts[0]
            for raw in reversed(parts[1:]):
                yield raw.decode("utf-8", "replace")
        if carry:
            yield carry.decode("utf-8", "replace")


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

    Dosya SONDAN okunur (tail): append-only JSONL'in son satirlari en yeni
    olaylardir, bu yuzden newest-first sonuc icin tum dosyayi okumaya gerek
    yoktur. Filtreli sorgularda yeterli eslesme bulunana kadar geriye dogru
    okumaya devam edilir; sonuc (filtre + en yeni ``limit``, newest-first)
    eski tam-dosya okumasiyla AYNIDIR.
    """
    if not EVENTS_PATH.exists():
        return []
    cap = max(1, min(int(limit), 2000))
    out: list[dict[str, Any]] = []
    try:
        for line in _iter_lines_reversed(EVENTS_PATH):
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
            if len(out) >= cap:
                break
    except OSError:
        return []
    return out


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
