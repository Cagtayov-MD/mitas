"""Batch runner for last-minute OCR credit experiments.

This is intentionally a thin wrapper around ``run_credit_experiment``. It runs
one video item per experiment directory so a single failure does not stop the
overnight queue.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import traceback
from typing import Any

from core.pipelines.ocr.credit_experiment import DEFAULT_ENGINES, run_credit_experiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run OCR experiments item-by-item from a manifest")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--engines", default=",".join(DEFAULT_ENGINES))
    parser.add_argument("--fps", type=float, default=None)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--preprocess-mode", choices=["auto", "off", "always"], default="auto")
    parser.add_argument("--allow-model-download", action="store_true")
    parser.add_argument("--status-path", default=None)
    parser.add_argument("--report-path", default=None)
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)
    manifests_dir = output_dir / "manifests"
    runs_dir = output_dir / "runs"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = manifest.get("items") or []
    engines = [part.strip() for part in args.engines.split(",") if part.strip()]
    status_path = Path(args.status_path) if args.status_path else output_dir / "batch_status.json"
    report_path = Path(args.report_path) if args.report_path else output_dir / "batch_report.md"

    batch: dict[str, Any] = {
        "started_at": _now(),
        "completed_at": None,
        "source_manifest": str(manifest_path),
        "output_dir": str(output_dir),
        "requested_engines": engines,
        "preprocess_mode": args.preprocess_mode,
        "allow_model_download": args.allow_model_download,
        "fps_override": args.fps,
        "max_frames": args.max_frames,
        "total_items": len(items),
        "completed_items": 0,
        "failed_items": 0,
        "items": [],
    }
    _write_status(status_path, report_path, batch)

    for index, item in enumerate(items, 1):
        item_id = str(item.get("id") or f"item_{index:03d}")
        single_manifest = {"items": [item]}
        single_manifest_path = manifests_dir / f"{_safe_name(item_id)}.json"
        single_manifest_path.write_text(json.dumps(single_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        item_output_dir = runs_dir / _safe_name(item_id)
        record: dict[str, Any] = {
            "index": index,
            "id": item_id,
            "path": item.get("path"),
            "started_at": _now(),
            "completed_at": None,
            "status": "running",
            "manifest_path": str(single_manifest_path),
            "output_dir": str(item_output_dir),
            "summary_path": None,
            "report_path": None,
            "error": None,
            "summary_item": None,
        }
        batch["items"].append(record)
        _write_status(status_path, report_path, batch)
        try:
            result = run_credit_experiment(
                single_manifest_path,
                output_dir=item_output_dir,
                engines=engines,
                fps=args.fps,
                max_frames=args.max_frames,
                preprocess_mode=args.preprocess_mode,
                allow_model_download=args.allow_model_download,
            )
            summary_items = result.summary.get("items") or []
            summary_item = summary_items[0] if summary_items else None
            item_status = str((summary_item or {}).get("status") or "done")
            record.update(
                {
                    "completed_at": _now(),
                    "status": item_status,
                    "summary_path": str(result.summary_path),
                    "report_path": str(result.report_path),
                    "summary_item": summary_item,
                    "engine_status": result.summary.get("engine_status"),
                    "runtime_sec": result.summary.get("runtime_sec"),
                }
            )
            if item_status in {"done", "partial"}:
                batch["completed_items"] += 1
            else:
                batch["failed_items"] += 1
        except Exception as exc:  # pragma: no cover - operational safety path
            record.update(
                {
                    "completed_at": _now(),
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                }
            )
            batch["failed_items"] += 1
        _write_status(status_path, report_path, batch)

    batch["completed_at"] = _now()
    _write_status(status_path, report_path, batch)
    return 0 if batch["failed_items"] == 0 else 1


def _write_status(status_path: Path, report_path: Path, batch: dict[str, Any]) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_report(batch), encoding="utf-8")


def _build_report(batch: dict[str, Any]) -> str:
    lines = [
        "# OCR Filmtest Last 3 Minute Batch",
        "",
        f"- Started: {batch.get('started_at')}",
        f"- Completed: {batch.get('completed_at')}",
        f"- Source manifest: {batch.get('source_manifest')}",
        f"- Output dir: {batch.get('output_dir')}",
        f"- Engines: {', '.join(batch.get('requested_engines') or [])}",
        f"- Preprocess: {batch.get('preprocess_mode')}",
        f"- Items: {batch.get('completed_items')}/{batch.get('total_items')} done, {batch.get('failed_items')} failed",
        "",
        "| # | Item | Status | Frames | Frame OCR | Preproc OCR | Stable | Canvas OCR | Runtime sec | Notes |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for record in batch.get("items") or []:
        summary = record.get("summary_item") or {}
        notes = record.get("error") or summary.get("preprocess_reason") or ""
        lines.append(
            "| {index} | {item} | {status} | {frames} | {frame_records} | {pre_records} | {stable} | {canvas} | {runtime} | {notes} |".format(
                index=record.get("index"),
                item=_md_cell(str(record.get("id") or "")),
                status=record.get("status"),
                frames=summary.get("frames", ""),
                frame_records=summary.get("frame_ocr_records", ""),
                pre_records=summary.get("preprocessed_ocr_records", ""),
                stable=summary.get("temporal_stable_groups", ""),
                canvas=summary.get("canvas_ocr_records", ""),
                runtime=record.get("runtime_sec") or summary.get("runtime_sec") or "",
                notes=_md_cell(str(notes)),
            )
        )
    return "\n".join(lines) + "\n"


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)[:120]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
