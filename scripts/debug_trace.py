# -*- coding: utf-8 -*-
"""Fail-safe per-clip debug provenance tracing for MITAS.

The tracer is intentionally best-effort: logging errors must never affect the
pipeline result. Subprocesses discover the active trace through environment
variables populated by mitas_pipeline.py.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

SCHEMA_VERSION = "mitas.debug_trace.v1"
TRACE_ENV = "MITAS_DEBUG_TRACE_DIR"
TRACE_ID_ENV = "MITAS_DEBUG_TRACE_ID"
RUN_ID_ENV = "MITAS_DEBUG_TRACE_RUN_ID"
CLIP_ID_ENV = "MITAS_DEBUG_TRACE_CLIP_ID"

_MAX_STRING = 8000
_MAX_LIST_ITEMS = 120
_MAX_DICT_ITEMS = 160


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str, default: str = "artifact") -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._-")
    return name[:120] or default


def _trace_dir() -> Path | None:
    raw = os.environ.get(TRACE_ENV, "").strip()
    if not raw:
        return None
    return Path(raw)


def _json_safe(value, depth: int = 0):
    if depth > 6:
        return repr(value)[:_MAX_STRING]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        value = value.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        if len(value) > _MAX_STRING:
            return value[:_MAX_STRING] + f"... [truncated {len(value) - _MAX_STRING} chars]"
        return value
    if isinstance(value, (list, tuple, set)):
        seq = list(value)
        out = [_json_safe(v, depth + 1) for v in seq[:_MAX_LIST_ITEMS]]
        if len(seq) > _MAX_LIST_ITEMS:
            out.append(f"... [truncated {len(seq) - _MAX_LIST_ITEMS} items]")
        return out
    if isinstance(value, dict):
        out = {}
        for idx, (k, v) in enumerate(value.items()):
            if idx >= _MAX_DICT_ITEMS:
                out["..."] = f"[truncated {len(value) - _MAX_DICT_ITEMS} keys]"
                break
            out[str(k)[:200]] = _json_safe(v, depth + 1)
        return out
    return repr(value)[:_MAX_STRING]


def start_trace(clip_dir: str | Path, *, clip_id: str, title: str = "", profile: str = "",
                video: str | Path = "", trt_id: str = "") -> dict:
    """Create debug_trace/ and export context to subprocess environment."""
    trace_dir = Path(clip_dir) / "debug_trace"
    artifacts = trace_dir / "artifacts"
    try:
        artifacts.mkdir(parents=True, exist_ok=True)
        trace_id = f"trace-{uuid4().hex[:16]}"
        run_id = f"run-{uuid4().hex[:12]}"
        os.environ[TRACE_ENV] = str(trace_dir)
        os.environ[TRACE_ID_ENV] = trace_id
        os.environ[RUN_ID_ENV] = run_id
        os.environ[CLIP_ID_ENV] = clip_id or ""
        meta = {
            "schema_version": SCHEMA_VERSION,
            "trace_id": trace_id,
            "run_id": run_id,
            "clip_id": clip_id,
            "title": title,
            "profile": profile,
            "trt_id": trt_id,
            "video": str(video) if video else "",
            "created_at": now_iso(),
            "trace_dir": str(trace_dir),
        }
        (trace_dir / "trace_meta.json").write_text(
            json.dumps(_json_safe(meta), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        emit(
            "pipeline",
            "stage_started",
            subject={"field": "clip", "after": title or clip_id, "reason": "trace initialized"},
            evidence={"profile": profile, "trt_id": trt_id, "video": str(video) if video else ""},
            source={"module": "scripts/mitas_pipeline.py", "input_paths": [str(video)] if video else []},
        )
        return meta
    except Exception:
        return {}


def emit(stage: str, event: str, *, status: str = "ok", duration_ms: int | float | None = None,
         source: dict | None = None, subject: dict | None = None, evidence: dict | None = None,
         summary: str | None = None, error: str | None = None) -> dict | None:
    """Append one JSONL trace event. No-op if tracing is not active."""
    trace_dir = _trace_dir()
    if trace_dir is None:
        return None
    try:
        trace_dir.mkdir(parents=True, exist_ok=True)
        ev = {
            "schema_version": SCHEMA_VERSION,
            "trace_id": os.environ.get(TRACE_ID_ENV, ""),
            "run_id": os.environ.get(RUN_ID_ENV, ""),
            "clip_id": os.environ.get(CLIP_ID_ENV, ""),
            "ts": now_iso(),
            "stage": stage,
            "event": event,
            "status": status if status in ("ok", "warn", "error", "skipped") else "ok",
            "source": source or {},
            "subject": subject or {},
            "evidence": evidence or {},
        }
        if duration_ms is not None:
            try:
                ev["duration_ms"] = int(round(float(duration_ms)))
            except Exception:
                ev["duration_ms"] = duration_ms
        if summary:
            ev["summary"] = str(summary)
        if error:
            ev["error"] = str(error)[:4000]
        with (trace_dir / "trace.jsonl").open("a", encoding="utf-8") as h:
            h.write(json.dumps(_json_safe(ev), ensure_ascii=False) + "\n")
        return ev
    except Exception:
        return None


def write_artifact_text(name: str, text: str, *, subdir: str = "") -> str | None:
    trace_dir = _trace_dir()
    if trace_dir is None:
        return None
    try:
        target_dir = trace_dir / "artifacts" / _safe_name(subdir, "") if subdir else trace_dir / "artifacts"
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / _safe_name(name, "artifact.txt")
        path.write_text(str(text or ""), encoding="utf-8", errors="replace")
        return str(path)
    except Exception:
        return None


def write_artifact_json(name: str, obj, *, subdir: str = "") -> str | None:
    return write_artifact_text(
        name,
        json.dumps(_json_safe(obj), ensure_ascii=False, indent=2),
        subdir=subdir,
    )


def copy_artifact(path: str | Path, *, name: str | None = None, subdir: str = "") -> str | None:
    trace_dir = _trace_dir()
    if trace_dir is None:
        return None
    try:
        src = Path(path)
        if not src.exists() or not src.is_file():
            return None
        target_dir = trace_dir / "artifacts" / _safe_name(subdir, "") if subdir else trace_dir / "artifacts"
        target_dir.mkdir(parents=True, exist_ok=True)
        dst = target_dir / _safe_name(name or src.name, src.name)
        shutil.copy2(src, dst)
        return str(dst)
    except Exception:
        return None


def finalize_trace(*, timings: dict | None = None, final_status: str = "", reasons: list | None = None,
                   outputs: dict | None = None) -> None:
    trace_dir = _trace_dir()
    if trace_dir is None:
        return
    try:
        trace_dir.mkdir(parents=True, exist_ok=True)
        if timings is not None:
            (trace_dir / "timings.json").write_text(
                json.dumps(_json_safe({
                    "schema_version": SCHEMA_VERSION,
                    "trace_id": os.environ.get(TRACE_ID_ENV, ""),
                    "run_id": os.environ.get(RUN_ID_ENV, ""),
                    "clip_id": os.environ.get(CLIP_ID_ENV, ""),
                    "timings_sec": timings,
                    "final_status": final_status,
                    "reasons": reasons or [],
                    "outputs": outputs or {},
                    "ts": now_iso(),
                }), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        events = _read_events(trace_dir / "trace.jsonl")
        (trace_dir / "trace_summary.md").write_text(
            _render_summary(events, timings=timings or {}, final_status=final_status,
                            reasons=reasons or [], outputs=outputs or {}),
            encoding="utf-8",
        )
    except Exception:
        return


def _read_events(path: Path) -> list[dict]:
    out = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        pass
    return out


def _brief(ev: dict) -> str:
    subject = ev.get("subject") or {}
    evidence = ev.get("evidence") or {}
    bits = []
    if subject.get("field"):
        bits.append(str(subject.get("field")))
    if subject.get("before") not in (None, "", [], {}):
        bits.append("önce=" + _short(subject.get("before")))
    if subject.get("after") not in (None, "", [], {}):
        bits.append("sonra=" + _short(subject.get("after")))
    if subject.get("reason"):
        bits.append("neden=" + _short(subject.get("reason")))
    for key in ("match_type", "model", "engine", "bucket", "ocr_source", "vl", "verdict", "kimlik_dogru"):
        if evidence.get(key) not in (None, "", [], {}):
            bits.append(f"{key}={_short(evidence.get(key))}")
    return "; ".join(bits) or _short(ev.get("summary") or "")


def _short(value, limit: int = 220) -> str:
    if isinstance(value, (list, tuple)):
        text = ", ".join(str(x) for x in list(value)[:8])
        if len(value) > 8:
            text += f", ...(+{len(value) - 8})"
    elif isinstance(value, dict):
        text = json.dumps(_json_safe(value), ensure_ascii=False)
    else:
        text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def _section(title: str, events: list[dict]) -> list[str]:
    lines = [f"## {title}"]
    if not events:
        lines.append("- Kayıt yok.")
        return lines
    for ev in events:
        ts = str(ev.get("ts", ""))[:19]
        dur = f" ({ev.get('duration_ms')} ms)" if ev.get("duration_ms") is not None else ""
        status = ev.get("status", "ok")
        lines.append(f"- {ts} `{ev.get('stage')}.{ev.get('event')}` [{status}]{dur}: {_brief(ev)}")
    return lines


def _render_summary(events: list[dict], *, timings: dict, final_status: str,
                    reasons: list, outputs: dict) -> str:
    by_stage = lambda names: [e for e in events if e.get("stage") in names]
    warn_events = [e for e in events if e.get("status") in ("warn", "error", "skipped")]
    missing_events = []
    for ev in events:
        subj = ev.get("subject") or {}
        reason = str(subj.get("reason") or ev.get("summary") or "").lower()
        if "bulunamad" in reason or "okunamad" in reason or "yok" in reason or "atlandı" in reason:
            missing_events.append(ev)

    lines = [
        "# MITAS Debug Trace",
        "",
        f"- Trace ID: `{os.environ.get(TRACE_ID_ENV, '')}`",
        f"- Run ID: `{os.environ.get(RUN_ID_ENV, '')}`",
        f"- Clip ID: `{os.environ.get(CLIP_ID_ENV, '')}`",
        f"- Final karar: **{final_status or 'bilinmiyor'}**",
    ]
    if reasons:
        lines.append("- Nedenler: " + "; ".join(str(r) for r in reasons))
    if outputs:
        lines.append("- Çıktılar: " + "; ".join(f"{k}={v}" for k, v in outputs.items() if v))
    lines.append("")
    lines.extend(_section("Zaman Çizelgesi", events))
    lines.append("")
    lines.extend(_section("OCR Ne Okudu", by_stage({"ocr"})))
    lines.append("")
    lines.extend(_section("Text/VL Ne Yaptı", by_stage({"credit_text", "qc1", "vl_fallback"})))
    lines.append("")
    lines.extend(_section("Fuzzy ve KB Kararları", by_stage({"fuzzy", "kb", "credit_validate", "v4"})))
    lines.append("")
    lines.extend(_section("Fallback Zinciri", [e for e in events if e.get("event") == "fallback_triggered"]))
    lines.append("")
    lines.extend(_section("PDF’ye Giden Alanlar", by_stage({"pdf", "v4"})))
    lines.append("")
    lines.extend(_section("QC1/QC Final", by_stage({"qc1", "qc_final", "routing"})))
    lines.append("")
    lines.append("## Süreler")
    if timings:
        for key, value in timings.items():
            lines.append(f"- {key}: {value} sn")
    else:
        lines.append("- Süre kaydı yok.")
    lines.append("")
    lines.extend(_section("Bulunamayanlar", warn_events + [e for e in missing_events if e not in warn_events]))
    lines.append("")
    return "\n".join(lines)
