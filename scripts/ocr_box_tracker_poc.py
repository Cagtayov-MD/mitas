from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.pipelines.ocr.box_tracker import build_text_tracks
from core.pipelines.ocr.credit_segment_dispatcher import SegmentDispatcherConfig, dispatch_credit_segments
from core.pipelines.ocr.text_track_state import classify_text_track_states


def run_poc(frame_ocr_path: Path, *, output_path: Path | None = None) -> dict[str, Any]:
    payload = json.loads(frame_ocr_path.read_text(encoding="utf-8"))
    records = list(payload.get("records") or [])
    frames = [str(frame) for frame in payload.get("frames") or []]
    frame_size = _frame_size_from_payload(payload)
    scene_profile = _load_sibling_scene_profile(frame_ocr_path)

    tracks = build_text_tracks(records, frames=frames, frame_size=frame_size)
    states = classify_text_track_states(tracks, frame_size=frame_size)
    result = dispatch_credit_segments(
        tracks,
        states,
        records=records,
        frame_size=frame_size,
        scene_profile=scene_profile,
        config=SegmentDispatcherConfig(min_records=80),
    )
    result["input_path"] = str(frame_ocr_path)
    result["frame_count"] = len(frames)

    destination = output_path or frame_ocr_path.with_name("box_tracker_poc_segments.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["output_path"] = str(destination)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OCR box-tracker segment POC on frame_ocr.json.")
    parser.add_argument("frame_ocr", type=Path, nargs="+", help="Path(s) to frame_ocr.json")
    parser.add_argument("--output-dir", type=Path, default=None, help="Optional directory for POC output JSON files")
    args = parser.parse_args()

    summaries = []
    for frame_ocr_path in args.frame_ocr:
        output_path = None
        if args.output_dir is not None:
            output_path = args.output_dir / f"{frame_ocr_path.parent.name}_box_tracker_poc_segments.json"
        result = run_poc(frame_ocr_path, output_path=output_path)
        summaries.append(
            {
                "input": str(frame_ocr_path),
                "output": result["output_path"],
                "status": result["status"],
                "segments": [
                    {
                        "type": segment.get("type"),
                        "start": segment.get("start_timestamp_seconds"),
                        "end": segment.get("end_timestamp_seconds"),
                    }
                    for segment in result.get("segments", [])
                ],
            }
        )
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0


def _frame_size_from_payload(payload: dict[str, Any]) -> tuple[int, int] | None:
    value = payload.get("frame_size") or payload.get("image_size")
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return int(value[0]), int(value[1])
        except (TypeError, ValueError):
            return None
    return None


def _load_sibling_scene_profile(frame_ocr_path: Path) -> dict[str, Any] | None:
    for name in ("scene_router_refined.json", "scene_router.json"):
        path = frame_ocr_path.with_name(name)
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        return payload if isinstance(payload, dict) else None
    return None


if __name__ == "__main__":
    raise SystemExit(main())
