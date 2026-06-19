"""Standalone credit-boundary locator lab.

This script is intentionally not imported by the production MITAS pipeline.
It scans the first/last N minutes of videos, estimates opening/closing credit
start points from OCR bbox layout signals, and renders 50-frame review sheets.

Typical use:
    E:\\MITAS\\venvs\\ocr\\Scripts\\python.exe scripts\\credit_locator_lab.py scan ^
        --include-ground-truth --include-transformers --limit 3

Review aggregation:
    python scripts\\credit_locator_lab.py summarize-review ^
        --review outputs\\credit_locator_lab\\<run_id>\\review_template.csv
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime
import importlib.util
import json
import math
import re
import shutil
import sys
import time
import unicodedata
from pathlib import Path
from statistics import median
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUTPUT_ROOT = ROOT / "outputs" / "credit_locator_lab"
DEFAULT_GROUND_TRUTH_DIR = ROOT / "tests" / "data" / "ocr_ground_truth"
DEFAULT_JENERIK_METADATA = ROOT / "_jenerik_analysis" / "metadata.json"
TRANSFORMERS_CLIP_JSON = ROOT / "Database" / "TRANSFORMERS 3 2011-9181-1-0000-90-1" / "clip.json"
CLIP_PROBE = ROOT / "OCR-worktree" / "py" / "20260601_clip_probe.py"

FFMPEG_BIN = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin"
FFMPEG = FFMPEG_BIN / "ffmpeg.exe"

VIDEO_EXTENSIONS = {".mp4", ".mxf", ".mov", ".mkv", ".avi", ".ts"}

REVIEW_VERDICTS = ("hit", "early", "late", "miss", "false_positive", "no_credit_ok")

ROLE_TOKENS = (
    "directed by",
    "director",
    "a film by",
    "un film de",
    "regia",
    "yönetmen",
    "yonetmen",
    "produced by",
    "producer",
    "executive producer",
    "yapimci",
    "yapımcı",
    "cast",
    "starring",
    "oyuncular",
    "oyuncu",
    "screenplay",
    "written by",
    "writer",
    "senaryo",
    "scenariu",
    "cinematography",
    "director of photography",
    "görüntü",
    "goruntu",
    "imaginea",
    "edited by",
    "editor",
    "montaj",
    "kurgu",
    "music by",
    "music",
    "müzik",
    "muzik",
    "costume",
    "sound",
    "visual effects",
    "casting",
    "production designer",
    "art director",
    "assistant director",
)

_CLIP_CONTEXT: dict[str, Any] | None = None


@dataclass
class LabItem:
    item_id: str
    path: str
    name: str = ""
    source: str = ""
    duration_sec: float | None = None
    expected_segments: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["exists"] = path_exists(Path(self.path))
        return payload


@dataclass
class FrameMetric:
    timestamp_sec: float
    frame_name: str
    width: int
    height: int
    line_count: int
    significant_line_count: int
    above_subtitle_count: int
    lower_band_count: int
    role_hits: int
    avg_confidence: float | None
    vertical_span_ratio: float
    x_span_ratio: float
    subtitle_baseline_y: float | None
    clip_score: float | None
    role_card_flag: bool
    box_drop: int
    ocr_difficult: bool
    credit_score: float
    weak_score: float
    is_credit: bool
    reasons: list[str]
    text_samples: list[str]
    line_y_centers: list[float]
    line_heights: list[float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SidePrediction:
    side: str
    found: bool
    predicted_start_sec: float | None
    trigger_sec: float | None
    confidence: float
    score_threshold: float
    search_start_sec: float
    search_end_sec: float
    subtitle_baseline_y: float | None
    sheet_path: str | None
    sheet_anchor_sec: float | None
    sheet_anchor_reason: str
    run: dict[str, Any] | None
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone credit locator lab")
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="Run OCR-layout locator and render review sheets")
    scan.add_argument("--manifest", action="append", type=Path, default=[], help="JSON manifest/file/dir to include")
    scan.add_argument("--video", action="append", default=[], help="Direct video path to include")
    scan.add_argument("--include-ground-truth", action="store_true", help="Include tests/data/ocr_ground_truth/*.json")
    scan.add_argument("--ground-truth-dir", type=Path, default=DEFAULT_GROUND_TRUTH_DIR)
    scan.add_argument("--include-jenerik-analysis", action="store_true", help="Include _jenerik_analysis/metadata.json")
    scan.add_argument("--include-transformers", action="store_true", help="Include the Transformers 3 problem item")
    scan.add_argument("--out-dir", type=Path, default=None)
    scan.add_argument("--limit", type=int, default=None)
    scan.add_argument("--sample-step", type=float, default=2.0, help="Broad scan sample interval in seconds")
    scan.add_argument("--refine-step", type=float, default=1.0, help="Second pass interval around candidate")
    scan.add_argument("--opening-window-min", type=float, default=20.0)
    scan.add_argument("--closing-window-min", type=float, default=20.0)
    scan.add_argument("--scan-width", type=int, default=960, help="Width of OCR scan frames")
    scan.add_argument("--sheet-count", type=int, default=50)
    scan.add_argument("--sheet-step", type=float, default=1.0)
    scan.add_argument("--pre-roll-sec", type=float, default=15.0)
    scan.add_argument("--lookback-sec", type=float, default=45.0)
    scan.add_argument("--score-threshold", type=float, default=0.55)
    scan.add_argument("--skip-old-detector", action="store_true")
    scan.add_argument("--keep-scan-frames", action="store_true")
    scan.add_argument("--enable-clip", action="store_true", help="Optionally add CLIP credit probabilities to the score")
    scan.set_defaults(func=run_scan)

    summary = sub.add_parser("summarize-review", help="Summarize manually filled review_template.csv")
    summary.add_argument("--review", type=Path, required=True)
    summary.add_argument("--out-dir", type=Path, default=None)
    summary.set_defaults(func=summarize_review)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    return int(args.func(args))


def run_scan(args: argparse.Namespace) -> int:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.out_dir or (OUTPUT_ROOT / run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    items = resolve_items(args)
    if args.limit is not None:
        items = items[: max(0, int(args.limit))]

    manifest_payload = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "items": [item.to_dict() for item in items],
    }
    write_json(out_dir / "manifest_resolved.json", manifest_payload)

    existing_items = [item for item in items if path_exists(Path(item.path))]
    missing_items = [item for item in items if not path_exists(Path(item.path))]
    if missing_items:
        print(f"[manifest] missing path skipped: {len(missing_items)}")
    print(f"[manifest] runnable items: {len(existing_items)} | out={out_dir}")

    engine = None
    if existing_items:
        from core.pipelines.ocr.credit_experiment import PaddleOcrEngine

        print("[ocr] PaddleOCR init...")
        t0 = time.time()
        engine = PaddleOcrEngine()
        print(f"[ocr] ready in {time.time() - t0:.1f}s | device={getattr(engine, 'device', '?')}")

    old_detector_results: dict[str, Any] = {}
    results: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []

    for index, item in enumerate(existing_items, start=1):
        print(f"\n[{index}/{len(existing_items)}] {item.item_id}")
        item_out = out_dir / safe_name(item.item_id)
        item_out.mkdir(parents=True, exist_ok=True)
        duration, native_fps = probe_video(Path(item.path))
        item.duration_sec = duration or item.duration_sec
        if not duration or duration <= 0:
            result = {"item": item.to_dict(), "status": "failed", "reason": "duration_unavailable"}
            results.append(result)
            continue

        old_result = None
        if not args.skip_old_detector:
            old_result = run_old_detector(
                Path(item.path),
                opening_window_min=args.opening_window_min,
                closing_window_min=args.closing_window_min,
            )
            old_detector_results[item.item_id] = old_result

        side_results: dict[str, Any] = {}
        try:
            for side in ("opening", "closing"):
                if side == "opening":
                    start_sec = 0.0
                    end_sec = min(duration, args.opening_window_min * 60.0)
                else:
                    start_sec = max(0.0, duration - args.closing_window_min * 60.0)
                    end_sec = duration
                side_dir = item_out / side
                prediction, metrics = scan_side(
                    video_path=Path(item.path),
                    side=side,
                    out_dir=side_dir,
                    engine=engine,
                    search_start_sec=start_sec,
                    search_end_sec=end_sec,
                    sample_step=args.sample_step,
                    refine_step=args.refine_step,
                    scan_width=args.scan_width,
                    score_threshold=args.score_threshold,
                    pre_roll_sec=args.pre_roll_sec,
                    lookback_sec=args.lookback_sec,
                    sheet_count=args.sheet_count,
                    sheet_step=args.sheet_step,
                    keep_scan_frames=args.keep_scan_frames,
                    enable_clip=args.enable_clip,
                )
                side_results[side] = prediction.to_dict()
                old_side = old_result.get(side) if isinstance(old_result, dict) else None
                old_sheet = None
            if isinstance(old_side, dict) and old_side.get("found"):
                old_sheet = render_review_sheet(
                    video_path=Path(item.path),
                    output_path=item_out / f"{side}_old_50.jpg",
                    anchor_sec=float(old_side.get("start_sec") or 0.0),
                    duration_sec=duration,
                    frame_count=args.sheet_count,
                    step_sec=args.sheet_step,
                    metrics=[],
                    title=f"{item.item_id} | {side} | old detector",
                    anchor_label="OLD",
                )
                comparison_rows.append(
                    {
                        "film_id": item.item_id,
                        "side": side,
                        "duration_sec": round(duration, 3),
                        "new_found": prediction.found,
                        "new_predicted_start_sec": prediction.predicted_start_sec,
                        "new_confidence": round(prediction.confidence, 4),
                        "new_sheet": prediction.sheet_path,
                        "old_found": bool(isinstance(old_side, dict) and old_side.get("found")),
                        "old_predicted_start_sec": (old_side or {}).get("start_sec") if isinstance(old_side, dict) else None,
                        "old_confidence": (old_side or {}).get("confidence") if isinstance(old_side, dict) else None,
                        "old_sheet": str(old_sheet) if old_sheet else "",
                    }
                )
                review_rows.append(
                    {
                        "film_id": item.item_id,
                        "side": side,
                        "new_found": prediction.found,
                        "new_predicted_start_sec": prediction.predicted_start_sec if prediction.found else "",
                        "new_confidence": round(prediction.confidence, 4),
                        "new_sheet_anchor_reason": prediction.sheet_anchor_reason,
                        "old_predicted_start_sec": (old_side or {}).get("start_sec") if isinstance(old_side, dict) and old_side.get("found") else "",
                        "verdict_new": "",
                        "verdict_old": "",
                        "manual_start_sec": "",
                        "notes": "",
                        "new_sheet": prediction.sheet_path or "",
                        "old_sheet": str(old_sheet) if old_sheet else "",
                    }
                )
        except Exception as exc:
            cleanup_temp_frame_dirs(item_out)
            item_result = {
                "item": item.to_dict(),
                "status": "failed",
                "reason": f"{type(exc).__name__}: {exc}",
                "duration_sec": round(duration, 3),
                "native_fps": round(native_fps, 3) if native_fps else None,
                "sides": side_results,
            }
            results.append(item_result)
            write_json(item_out / "result.json", item_result)
            print(f"  failed: {item_result['reason']}")
            continue

        item_result = {
            "item": item.to_dict(),
            "status": "done",
            "duration_sec": round(duration, 3),
            "native_fps": round(native_fps, 3) if native_fps else None,
            "sides": side_results,
        }
        results.append(item_result)
        write_json(item_out / "result.json", item_result)

    write_json(out_dir / "results.json", {"items": results})
    write_json(out_dir / "baseline_old_detector.json", old_detector_results)
    write_csv(out_dir / "comparison.csv", comparison_rows)
    write_csv(out_dir / "review_template.csv", review_rows)

    print("\n[done]")
    print(f"  results: {out_dir / 'results.json'}")
    print(f"  review : {out_dir / 'review_template.csv'}")
    print(f"  compare: {out_dir / 'comparison.csv'}")
    return 0


def resolve_items(args: argparse.Namespace) -> list[LabItem]:
    items: list[LabItem] = []

    if args.include_ground_truth:
        items.extend(load_manifest_path(args.ground_truth_dir, source="ground_truth"))
    if args.include_jenerik_analysis:
        items.extend(load_manifest_path(DEFAULT_JENERIK_METADATA, source="jenerik_analysis"))
    if args.include_transformers:
        item = load_transformers_item()
        if item:
            items.append(item)
    for manifest in args.manifest:
        items.extend(load_manifest_path(manifest, source=str(manifest)))
    for video in args.video:
        path = remap_video_path(str(video))
        p = Path(path)
        items.append(LabItem(item_id=derive_item_id(p), path=str(p), name=p.name, source="direct_video"))

    return dedupe_items(items)


def load_manifest_path(path: Path, *, source: str) -> list[LabItem]:
    if path.is_dir():
        items: list[LabItem] = []
        for child in sorted(path.glob("*.json")):
            items.extend(load_manifest_path(child, source=source))
        return items
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[manifest] skip {path}: {type(exc).__name__}: {exc}")
        return []
    return items_from_payload(payload, source=source, fallback_name=path.stem)


def items_from_payload(payload: Any, *, source: str, fallback_name: str) -> list[LabItem]:
    if isinstance(payload, list):
        return [item for row in payload for item in items_from_payload(row, source=source, fallback_name=fallback_name)]
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("items"), list):
        return [
            item
            for row in payload["items"]
            for item in items_from_payload(row, source=source, fallback_name=fallback_name)
        ]

    raw_path = payload.get("source_path") or payload.get("path") or payload.get("video_path")
    if not raw_path:
        return []
    path = remap_video_path(str(raw_path))
    name = str(payload.get("name") or payload.get("filename") or Path(path).name)
    item_id = str(payload.get("video_id") or payload.get("id") or payload.get("clip_id") or "").strip()
    if not item_id:
        item_id = derive_item_id(Path(path), fallback=fallback_name)
    duration = float_or_none(payload.get("video_duration_sec") or payload.get("duration") or payload.get("duration_sec"))
    expected = payload.get("expected_segments") if isinstance(payload.get("expected_segments"), list) else []
    return [
        LabItem(
            item_id=item_id,
            path=str(Path(path)),
            name=name,
            source=source,
            duration_sec=duration,
            expected_segments=expected,
        )
    ]


def load_transformers_item() -> LabItem | None:
    if not TRANSFORMERS_CLIP_JSON.exists():
        return None
    try:
        payload = json.loads(TRANSFORMERS_CLIP_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None
    path = remap_video_path(str(payload.get("source_path") or ""))
    return LabItem(
        item_id="2011_9181_1_0000_90_1_transformers_3_problem",
        path=str(Path(path)),
        name=str(payload.get("filename") or Path(path).name),
        source="transformers_problem",
    )


def remap_video_path(raw_path: str) -> str:
    value = raw_path.strip().strip('"')
    # TRT Windows sessions often have W: mapped to this UNC share.
    if re.match(r"^[Ww]:\\", value):
        suffix = value[3:]
        unc = Path(r"\\depo01cifs.int.trt.net.tr\sas_h264") / suffix
        return str(unc)
    p = Path(value)
    if path_exists(p):
        return str(p)
    return value


def path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def dedupe_items(items: Iterable[LabItem]) -> list[LabItem]:
    out: list[LabItem] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item.item_id, str(Path(item.path)).lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def scan_side(
    *,
    video_path: Path,
    side: str,
    out_dir: Path,
    engine: Any,
    search_start_sec: float,
    search_end_sec: float,
    sample_step: float,
    refine_step: float,
    scan_width: int,
    score_threshold: float,
    pre_roll_sec: float,
    lookback_sec: float,
    sheet_count: int,
    sheet_step: float,
    keep_scan_frames: bool,
    enable_clip: bool,
) -> tuple[SidePrediction, list[FrameMetric]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    scan_frames_dir = out_dir / "scan_frames"
    scan_frames_dir.mkdir(parents=True, exist_ok=True)

    broad_times = sample_times(search_start_sec, search_end_sec, sample_step)
    broad_metrics = ocr_sample_times(
        video_path=video_path,
        times=broad_times,
        output_dir=scan_frames_dir,
        engine=engine,
        scan_width=scan_width,
        strategy=f"credit_locator_lab_{side}_broad",
        enable_clip=enable_clip,
    )
    baseline_y = learn_subtitle_baseline(broad_metrics)
    broad_metrics = rescore_metrics(broad_metrics, baseline_y=baseline_y, score_threshold=score_threshold)
    broad_run = choose_credit_run(broad_metrics, side=side, score_threshold=score_threshold, min_sustain_sec=3.5)

    metrics = broad_metrics
    selected_run = broad_run
    if broad_run:
        refine_start = max(search_start_sec, float(broad_run["trigger_sec"]) - 45.0)
        refine_end = min(search_end_sec, float(broad_run["trigger_sec"]) + 45.0)
        refine_dir = out_dir / "refine_frames"
        refine_dir.mkdir(parents=True, exist_ok=True)
        refine_metrics = ocr_sample_times(
            video_path=video_path,
            times=sample_times(refine_start, refine_end, refine_step),
            output_dir=refine_dir,
            engine=engine,
            scan_width=scan_width,
            strategy=f"credit_locator_lab_{side}_refine",
            enable_clip=enable_clip,
        )
        combined = merge_metrics(broad_metrics, refine_metrics)
        baseline_y = learn_subtitle_baseline(combined) or baseline_y
        metrics = rescore_metrics(combined, baseline_y=baseline_y, score_threshold=score_threshold)
        selected_run = choose_credit_run(metrics, side=side, score_threshold=score_threshold, min_sustain_sec=3.0) or broad_run

    write_json(out_dir / "frame_metrics.json", {"frames": [m.to_dict() for m in metrics]})
    write_csv(out_dir / "frame_metrics.csv", [flatten_metric(m) for m in metrics])

    if selected_run:
        trigger = float(selected_run["trigger_sec"])
        predicted = refine_start_time(
            metrics,
            trigger_sec=trigger,
            search_start_sec=search_start_sec,
            pre_roll_sec=pre_roll_sec,
            lookback_sec=lookback_sec,
        )
        confidence = float(selected_run["confidence"])
        reasons = list(selected_run.get("reasons") or [])
        found = True
        sheet_anchor = predicted
        sheet_anchor_reason = "prediction"
        sheet_anchor_label = "PRED"
        sheet_anchor_color = (255, 60, 60)
        sheet_markers = [(trigger, "TRIG", (80, 220, 80))] if trigger is not None else []
    else:
        trigger = None
        predicted = None
        confidence = 0.0
        reasons = ["no_sustained_credit_run"]
        found = False
        top_metric = max(metrics, key=lambda m: m.credit_score, default=None)
        sheet_anchor = top_metric.timestamp_sec if top_metric else search_start_sec
        sheet_anchor_reason = "top_score_no_prediction" if top_metric else "search_start_no_prediction"
        sheet_anchor_label = "DEBUG"
        sheet_anchor_color = (70, 150, 255)
        sheet_markers = []

    sheet_path = render_review_sheet(
        video_path=video_path,
        output_path=out_dir.parent / f"{side}_new_50.jpg",
        anchor_sec=float(sheet_anchor or search_start_sec),
        duration_sec=search_end_sec if side == "opening" else search_end_sec,
        frame_count=sheet_count,
        step_sec=sheet_step,
        metrics=metrics,
        title=build_sheet_title(
            video_path.name,
            side=side,
            found=found,
            predicted=predicted,
            trigger=trigger,
            anchor_reason=sheet_anchor_reason,
        ),
        anchor_label=sheet_anchor_label,
        anchor_color=sheet_anchor_color,
        markers=sheet_markers,
    )

    if not keep_scan_frames:
        for folder in (scan_frames_dir, out_dir / "refine_frames"):
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)

    prediction = SidePrediction(
        side=side,
        found=found,
        predicted_start_sec=round(predicted, 3) if predicted is not None else None,
        trigger_sec=round(trigger, 3) if trigger is not None else None,
        confidence=round(confidence, 6),
        score_threshold=score_threshold,
        search_start_sec=round(search_start_sec, 3),
        search_end_sec=round(search_end_sec, 3),
        subtitle_baseline_y=round(baseline_y, 3) if baseline_y is not None else None,
        sheet_path=str(sheet_path) if sheet_path else None,
        sheet_anchor_sec=round(float(sheet_anchor), 3) if sheet_anchor is not None else None,
        sheet_anchor_reason=sheet_anchor_reason,
        run=selected_run,
        reasons=reasons,
    )
    write_json(out_dir / "prediction.json", prediction.to_dict())
    print(
        f"  {side:<7} found={prediction.found} "
        f"start={prediction.predicted_start_sec} conf={prediction.confidence:.3f} "
        f"sheet={Path(prediction.sheet_path).name if prediction.sheet_path else '-'}"
    )
    return prediction, metrics


def cleanup_temp_frame_dirs(item_out: Path) -> None:
    for side in ("opening", "closing"):
        for folder_name in ("scan_frames", "refine_frames"):
            folder = item_out / side / folder_name
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)


def ocr_sample_times(
    *,
    video_path: Path,
    times: list[float],
    output_dir: Path,
    engine: Any,
    scan_width: int,
    strategy: str,
    enable_clip: bool = False,
) -> list[FrameMetric]:
    import cv2

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"video_not_opened: {video_path}")
    metrics: list[FrameMetric] = []
    for idx, timestamp in enumerate(times):
        image = read_frame_at(cap, cv2, timestamp)
        if image is None:
            continue
        image = resize_to_width(cv2, image, scan_width)
        height, width = image.shape[:2]
        frame_path = output_dir / f"f_{idx:05d}_{int(round(timestamp * 1000)):010d}.jpg"
        imwrite(frame_path, image)
        records = engine.recognize(frame_path, strategy=strategy, timestamp_seconds=timestamp)
        metrics.append(metric_from_records(timestamp, frame_path.name, width, height, records))
    cap.release()
    if enable_clip and metrics:
        metrics = attach_clip_scores(metrics, output_dir)
    return metrics


def attach_clip_scores(metrics: list[FrameMetric], frame_dir: Path) -> list[FrameMetric]:
    context = get_clip_context()
    if not context:
        return metrics
    frame_paths = [frame_dir / metric.frame_name for metric in metrics]
    existing = [path for path in frame_paths if path.exists()]
    if len(existing) != len(frame_paths):
        return metrics
    try:
        cp = context["module"]
        scores = cp.med_smooth(
            cp.score_frames(
                context["model"],
                context["preprocess"],
                [str(path) for path in frame_paths],
                context["credit_embed"],
                context["scene_embed"],
                context["logit_scale"],
            ),
            5,
        )
    except Exception as exc:
        print(f"[clip] disabled for this segment: {type(exc).__name__}: {exc}")
        return metrics

    out: list[FrameMetric] = []
    for metric, score in zip(metrics, scores):
        out.append(FrameMetric(**{**metric.to_dict(), "clip_score": round(float(score), 6)}))
    return out


def get_clip_context() -> dict[str, Any] | None:
    global _CLIP_CONTEXT
    if _CLIP_CONTEXT is not None:
        return _CLIP_CONTEXT
    if not CLIP_PROBE.exists():
        print(f"[clip] probe missing: {CLIP_PROBE}")
        _CLIP_CONTEXT = {}
        return None
    try:
        spec = importlib.util.spec_from_file_location("mitas_credit_locator_clip_probe", CLIP_PROBE)
        if spec is None or spec.loader is None:
            raise RuntimeError("spec_loader_missing")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print("[clip] loading CLIP model...")
        model, preprocess, tok = module.load_clip()
        credit_embed = module.class_embed(model, tok, module.CREDIT_PROMPTS)
        scene_embed = module.class_embed(model, tok, module.SCENE_PROMPTS)
        _CLIP_CONTEXT = {
            "module": module,
            "model": model,
            "preprocess": preprocess,
            "credit_embed": credit_embed,
            "scene_embed": scene_embed,
            "logit_scale": model.logit_scale.exp().item(),
        }
        return _CLIP_CONTEXT
    except Exception as exc:
        print(f"[clip] unavailable: {type(exc).__name__}: {exc}")
        _CLIP_CONTEXT = {}
        return None


def metric_from_records(timestamp: float, frame_name: str, width: int, height: int, records: list[dict[str, Any]]) -> FrameMetric:
    useful = []
    for record in records:
        text = str(record.get("text") or "").strip()
        bbox = record.get("bbox")
        if not text or not bbox or len(bbox) < 4:
            continue
        try:
            x, y, w, h = [float(v) for v in bbox[:4]]
        except (TypeError, ValueError):
            continue
        if w <= 0 or h <= 0:
            continue
        useful.append((text, x, y, w, h, float_or_none(record.get("confidence"))))

    significant = [row for row in useful if len(normalize_for_match(row[0])) >= 2]
    if significant:
        ys0 = [row[2] for row in significant]
        ys1 = [row[2] + row[4] for row in significant]
        xs0 = [row[1] for row in significant]
        xs1 = [row[1] + row[3] for row in significant]
        vertical_span = (max(ys1) - min(ys0)) / max(1.0, float(height))
        x_span = (max(xs1) - min(xs0)) / max(1.0, float(width))
    else:
        vertical_span = 0.0
        x_span = 0.0

    line_y_centers = [round(row[2] + row[4] / 2.0, 3) for row in significant]
    line_heights = [round(row[4], 3) for row in significant]
    lower = [row for row in significant if (row[2] + row[4] / 2.0) >= height * 0.70]
    confidences = [row[5] for row in significant if row[5] is not None]
    role_hits = count_role_hits(" ".join(row[0] for row in significant))
    role_card_flag = bool(1 <= len(significant) <= 3 and role_hits > 0)
    return FrameMetric(
        timestamp_sec=round(float(timestamp), 3),
        frame_name=frame_name,
        width=width,
        height=height,
        line_count=len(useful),
        significant_line_count=len(significant),
        above_subtitle_count=0,
        lower_band_count=len(lower),
        role_hits=role_hits,
        avg_confidence=round(sum(confidences) / len(confidences), 6) if confidences else None,
        vertical_span_ratio=round(vertical_span, 6),
        x_span_ratio=round(x_span, 6),
        subtitle_baseline_y=None,
        clip_score=None,
        role_card_flag=role_card_flag,
        box_drop=0,
        ocr_difficult=False,
        credit_score=0.0,
        weak_score=0.0,
        is_credit=False,
        reasons=[],
        text_samples=[row[0] for row in significant[:6]],
        line_y_centers=line_y_centers,
        line_heights=line_heights,
    )


def learn_subtitle_baseline(metrics: list[FrameMetric]) -> float | None:
    candidates: list[float] = []
    for metric in metrics:
        if not (1 <= metric.significant_line_count <= 3):
            continue
        if metric.vertical_span_ratio > 0.18:
            continue
        if metric.lower_band_count <= 0:
            continue
        lower_centers = [y for y in metric.line_y_centers if y >= metric.height * 0.62]
        if lower_centers:
            candidates.append(max(lower_centers))
    if len(candidates) < 3:
        return None
    candidates.sort()
    return candidates[len(candidates) // 2]


def rescore_metrics(metrics: list[FrameMetric], *, baseline_y: float | None, score_threshold: float) -> list[FrameMetric]:
    rescored: list[FrameMetric] = []
    previous_line_count: int | None = None
    for metric in sorted(metrics, key=lambda item: item.timestamp_sec):
        line_count = metric.significant_line_count
        box_drop = max(0, int(previous_line_count or 0) - int(line_count))
        previous_line_count = int(line_count)
        ocr_difficult = bool(box_drop >= 3 and line_count > 0)
        line_score = clamp((line_count - 1.5) / 5.0)
        span_score = clamp((metric.vertical_span_ratio - 0.08) / 0.34)
        x_score = clamp((metric.x_span_ratio - 0.22) / 0.55)
        role_score = clamp(metric.role_hits / 2.0)
        clip_score = clamp(metric.clip_score or 0.0)

        if baseline_y is not None:
            median_h = median(metric.line_heights) if metric.line_heights else metric.height * 0.035
            margin = max(24.0, median_h * 2.5, metric.height * 0.035)
            above_count = sum(1 for y in metric.line_y_centers if y < baseline_y - margin)
            baseline_score = clamp(above_count / 4.0)
        else:
            above_count = sum(1 for y in metric.line_y_centers if y < metric.height * 0.72)
            baseline_score = clamp(above_count / 4.0)

        subtitle_penalty = 0.35 if line_count <= 2 and metric.lower_band_count >= line_count and role_score == 0 else 0.0
        sparse_role_bonus = 0.35 if metric.role_card_flag else 0.0
        score = (
            0.28 * line_score
            + 0.22 * baseline_score
            + 0.18 * span_score
            + 0.14 * role_score
            + 0.08 * x_score
            + 0.10 * clip_score
            + sparse_role_bonus
            - subtitle_penalty
        )
        weak_score = max(
            score,
            0.22 * line_score
            + 0.24 * span_score
            + 0.26 * role_score
            + 0.18 * baseline_score
            + 0.10 * clip_score
            + sparse_role_bonus,
        )

        reasons = []
        if line_count >= 4:
            reasons.append("line_count>=4")
        if above_count >= 3:
            reasons.append("above_subtitle_text")
        if metric.vertical_span_ratio >= 0.20:
            reasons.append("vertical_spread")
        if metric.role_hits:
            reasons.append("role_token")
        if metric.role_card_flag:
            reasons.append("sparse_role_card")
        if ocr_difficult:
            reasons.append("ocr_difficult_box_drop")
        if clip_score >= 0.55:
            reasons.append("clip_credit")
        if subtitle_penalty:
            reasons.append("subtitle_penalty")

        is_credit = bool(score >= score_threshold and (line_count >= 3 or metric.role_hits > 0 or above_count >= 2))
        rescored.append(
            FrameMetric(
                **{
                    **metric.to_dict(),
                    "above_subtitle_count": above_count,
                    "subtitle_baseline_y": baseline_y,
                    "box_drop": box_drop,
                    "ocr_difficult": ocr_difficult,
                    "credit_score": round(clamp(score), 6),
                    "weak_score": round(clamp(weak_score), 6),
                    "is_credit": is_credit,
                    "reasons": reasons,
                }
            )
        )
    return sorted(rescored, key=lambda m: m.timestamp_sec)


def choose_credit_run(
    metrics: list[FrameMetric],
    *,
    side: str,
    score_threshold: float,
    min_sustain_sec: float,
) -> dict[str, Any] | None:
    runs = build_runs(metrics, max_gap_sec=8.0)
    valid: list[dict[str, Any]] = []
    for run_metrics in runs:
        start = run_metrics[0].timestamp_sec
        end = run_metrics[-1].timestamp_sec
        duration = max(0.0, end - start)
        max_line = max(m.significant_line_count for m in run_metrics)
        role_hits = sum(m.role_hits for m in run_metrics)
        role_card_frames = sum(1 for m in run_metrics if m.role_card_flag)
        avg_score = sum(m.credit_score for m in run_metrics) / len(run_metrics)
        max_score = max(m.credit_score for m in run_metrics)
        avg_above = sum(m.above_subtitle_count for m in run_metrics) / len(run_metrics)
        if duration < min_sustain_sec and len(run_metrics) < 2:
            continue
        if max_line < 3 and role_hits <= 0 and avg_above < 2:
            continue
        duration_score = clamp(duration / 45.0)
        line_score = clamp(max_line / 8.0)
        role_score = clamp(role_hits / 4.0)
        quality = 0.45 * avg_score + 0.22 * max_score + 0.18 * duration_score + 0.10 * line_score + 0.05 * role_score
        if quality < max(0.42, score_threshold - 0.12):
            continue
        reasons = sorted({reason for metric in run_metrics for reason in metric.reasons})
        run_type = "static_sequence" if role_card_frames >= 2 and max_line <= 3 else "layout_credit"
        valid.append(
            {
                "type": run_type,
                "start_sec": round(start, 3),
                "end_sec": round(end, 3),
                "trigger_sec": round(start, 3),
                "duration_sec": round(duration, 3),
                "frame_count": len(run_metrics),
                "confidence": round(clamp(quality), 6),
                "avg_score": round(avg_score, 6),
                "max_score": round(max_score, 6),
                "max_line_count": max_line,
                "role_hits": role_hits,
                "role_card_frames": role_card_frames,
                "avg_above_subtitle_count": round(avg_above, 3),
                "reasons": reasons,
            }
        )
    if not valid:
        return None
    if side == "opening":
        strong = [run for run in valid if run["confidence"] >= score_threshold - 0.05]
        return min(strong or valid, key=lambda r: (float(r["start_sec"]), -float(r["confidence"])))
    return max(valid, key=lambda r: (float(r["confidence"]), float(r["duration_sec"]), -float(r["start_sec"])))


def build_runs(metrics: list[FrameMetric], *, max_gap_sec: float) -> list[list[FrameMetric]]:
    runs: list[list[FrameMetric]] = []
    current: list[FrameMetric] = []
    for metric in metrics:
        flag = metric.is_credit
        if flag and not current:
            current = [metric]
            continue
        if flag and current:
            if metric.timestamp_sec - current[-1].timestamp_sec <= max_gap_sec:
                current.append(metric)
            else:
                runs.append(current)
                current = [metric]
            continue
        if current and metric.timestamp_sec - current[-1].timestamp_sec <= max_gap_sec and metric.weak_score >= 0.38:
            current.append(metric)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def refine_start_time(
    metrics: list[FrameMetric],
    *,
    trigger_sec: float,
    search_start_sec: float,
    pre_roll_sec: float,
    lookback_sec: float,
) -> float:
    base = max(search_start_sec, trigger_sec - pre_roll_sec)
    lookback_start = max(search_start_sec, trigger_sec - lookback_sec)
    weak = [
        metric.timestamp_sec
        for metric in metrics
        if lookback_start <= metric.timestamp_sec <= trigger_sec
        and is_credit_start_evidence(metric)
    ]
    if weak:
        return max(search_start_sec, min(base, min(weak)))
    return base


def is_credit_start_evidence(metric: FrameMetric) -> bool:
    """Return True only for weak evidence that is credit-like enough to pull start left.

    Scene props such as a phone screen can have several OCR boxes, but they do
    not have credit layout spread, role tokens, or persistent high weak score.
    Those frames should not move the review anchor earlier than the safe preroll.
    """
    if metric.role_hits > 0 or metric.role_card_flag:
        return True
    if metric.weak_score >= 0.48 and (metric.above_subtitle_count >= 2 or metric.vertical_span_ratio >= 0.16):
        return True
    if metric.significant_line_count >= 4 and metric.above_subtitle_count >= 3 and metric.vertical_span_ratio >= 0.18:
        return True
    return False


def merge_metrics(left: list[FrameMetric], right: list[FrameMetric]) -> list[FrameMetric]:
    by_time: dict[float, FrameMetric] = {}
    for metric in left + right:
        by_time[round(metric.timestamp_sec, 3)] = metric
    return [by_time[key] for key in sorted(by_time)]


def render_review_sheet(
    *,
    video_path: Path,
    output_path: Path,
    anchor_sec: float,
    duration_sec: float,
    frame_count: int,
    step_sec: float,
    metrics: list[FrameMetric],
    title: str,
    anchor_label: str = "PRED",
    anchor_color: tuple[int, int, int] = (255, 60, 60),
    markers: list[tuple[float, str, tuple[int, int, int]]] | None = None,
) -> Path | None:
    import cv2
    from PIL import Image, ImageDraw, ImageFont

    output_path.parent.mkdir(parents=True, exist_ok=True)
    before = min(20, max(0, frame_count // 2))
    start = max(0.0, anchor_sec - before * step_sec)
    times = [max(0.0, min(duration_sec, start + i * step_sec)) for i in range(frame_count)]
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    tiles: list[Image.Image] = []
    font = ImageFont.load_default()
    for timestamp in times:
        frame = read_frame_at(cap, cv2, timestamp)
        if frame is None:
            continue
        frame = resize_to_width(cv2, frame, 224)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        tile = Image.fromarray(rgb).resize((224, 126))
        draw = ImageDraw.Draw(tile)
        draw.rectangle((0, 0, 224, 28), fill=(0, 0, 0))
        nearest = nearest_metric(metrics, timestamp)
        score = f" s={nearest.credit_score:.2f}" if nearest else ""
        draw.text((4, 4), f"{format_time(timestamp)}{score}", fill=(255, 255, 0), font=font)
        if abs(timestamp - anchor_sec) <= step_sec / 2:
            draw.rectangle((1, 1, 222, 124), outline=anchor_color, width=3)
            draw.rectangle((2, 98, 74, 123), fill=(0, 0, 0))
            draw.text((6, 104), anchor_label[:12], fill=anchor_color, font=font)
        for marker_sec, marker_label, marker_color in markers or []:
            if abs(timestamp - marker_sec) <= step_sec / 2:
                draw.rectangle((6, 6, 217, 119), outline=marker_color, width=3)
                draw.rectangle((146, 98, 222, 123), fill=(0, 0, 0))
                draw.text((150, 104), marker_label[:12], fill=marker_color, font=font)
        tiles.append(tile)
    cap.release()
    if not tiles:
        return None

    cols = 5
    rows = math.ceil(len(tiles) / cols)
    header_h = 30
    canvas = Image.new("RGB", (cols * 224, header_h + rows * 126), (24, 24, 24))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 8), title[:160], fill=(230, 230, 230), font=font)
    for idx, tile in enumerate(tiles):
        row, col = divmod(idx, cols)
        canvas.paste(tile, (col * 224, header_h + row * 126))
    canvas.save(output_path, quality=92)
    return output_path


def build_sheet_title(
    video_name: str,
    *,
    side: str,
    found: bool,
    predicted: float | None,
    trigger: float | None,
    anchor_reason: str,
) -> str:
    if found:
        pred_text = format_time(float(predicted)) if predicted is not None else "-"
        trigger_text = format_time(float(trigger)) if trigger is not None else "-"
        return f"{video_name} | {side} | new locator | PRED={pred_text} TRIG={trigger_text}"
    return f"{video_name} | {side} | new locator | NO PREDICTION | debug={anchor_reason}"


def run_old_detector(video_path: Path, *, opening_window_min: float, closing_window_min: float) -> dict[str, Any]:
    try:
        from core.pipelines.ocr.credit_detector import OpusCreditDetector

        return OpusCreditDetector().detect_both(
            video_path,
            open_search_min=opening_window_min,
            close_search_min=closing_window_min,
        )
    except Exception as exc:
        no = {
            "found": False,
            "type": "none",
            "start_sec": 0.0,
            "end_sec": 0.0,
            "scroll_speed": 0.0,
            "confidence": 0.0,
            "strategy": "opus_credit_detector",
            "error": f"{type(exc).__name__}: {exc}",
        }
        return {"opening": no, "closing": no}


def summarize_review(args: argparse.Namespace) -> int:
    review_path = args.review
    rows = read_csv(review_path)
    out_dir = args.out_dir or review_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = build_review_summary(rows)
    write_json(out_dir / "review_summary.json", summary)
    (out_dir / "review_summary.md").write_text(render_review_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def build_review_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    filled = [row for row in rows if row.get("verdict_new") or row.get("verdict_old")]

    def count_for(prefix: str, side: str | None = None) -> dict[str, int]:
        counts = {verdict: 0 for verdict in REVIEW_VERDICTS}
        key = f"verdict_{prefix}"
        for row in filled:
            if side and row.get("side") != side:
                continue
            verdict = (row.get(key) or "").strip()
            if verdict in counts:
                counts[verdict] += 1
        return counts

    def rate(counts: dict[str, int]) -> float:
        total = sum(counts.values())
        good = counts.get("hit", 0) + counts.get("early", 0) + counts.get("no_credit_ok", 0)
        return round(good / total, 4) if total else 0.0

    by_side = {}
    for side in ("opening", "closing"):
        new_counts = count_for("new", side)
        old_counts = count_for("old", side)
        by_side[side] = {
            "new": {"counts": new_counts, "accept_rate": rate(new_counts)},
            "old": {"counts": old_counts, "accept_rate": rate(old_counts)},
        }

    gains = []
    regressions = []
    both_missed = []
    for row in filled:
        new_v = row.get("verdict_new", "")
        old_v = row.get("verdict_old", "")
        new_good = new_v in {"hit", "early", "no_credit_ok"}
        old_good = old_v in {"hit", "early", "no_credit_ok"}
        item = {"film_id": row.get("film_id"), "side": row.get("side"), "new": new_v, "old": old_v}
        if new_good and not old_good:
            gains.append(item)
        elif old_good and not new_good:
            regressions.append(item)
        elif new_v in {"late", "miss"} and old_v in {"late", "miss"}:
            both_missed.append(item)

    new_counts = count_for("new")
    old_counts = count_for("old")
    return {
        "review_path": str(Path(rows[0].get("_review_path", ""))) if rows else "",
        "rows_total": len(rows),
        "rows_filled": len(filled),
        "new": {"counts": new_counts, "accept_rate": rate(new_counts)},
        "old": {"counts": old_counts, "accept_rate": rate(old_counts)},
        "by_side": by_side,
        "new_gains_over_old": gains,
        "new_regressions_vs_old": regressions,
        "both_missed_or_late": both_missed,
    }


def render_review_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Credit Locator Lab Review Summary",
        "",
        f"- Rows filled: {summary.get('rows_filled')} / {summary.get('rows_total')}",
        f"- New accept rate: {summary.get('new', {}).get('accept_rate')}",
        f"- Old accept rate: {summary.get('old', {}).get('accept_rate')}",
        f"- New gains over old: {len(summary.get('new_gains_over_old') or [])}",
        f"- New regressions vs old: {len(summary.get('new_regressions_vs_old') or [])}",
        f"- Both missed/late: {len(summary.get('both_missed_or_late') or [])}",
        "",
        "## Counts",
        "",
        "| System | hit | early | late | miss | false_positive | no_credit_ok |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in ("new", "old"):
        counts = summary.get(label, {}).get("counts", {})
        lines.append(
            f"| {label} | {counts.get('hit',0)} | {counts.get('early',0)} | "
            f"{counts.get('late',0)} | {counts.get('miss',0)} | "
            f"{counts.get('false_positive',0)} | {counts.get('no_credit_ok',0)} |"
        )
    return "\n".join(lines) + "\n"


def probe_video(path: Path) -> tuple[float | None, float | None]:
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return None, None
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    cap.release()
    if fps > 0 and frames > 0:
        return frames / fps, fps
    return None, fps or None


def sample_times(start: float, end: float, step: float) -> list[float]:
    start = max(0.0, float(start))
    end = max(start, float(end))
    step = max(0.2, float(step))
    values = []
    t = start
    while t <= end + 0.001:
        values.append(round(t, 3))
        t += step
    return values


def read_frame_at(cap: Any, cv2: Any, timestamp_sec: float) -> Any | None:
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(timestamp_sec)) * 1000.0)
    ok, frame = cap.read()
    if not ok:
        return None
    return frame


def resize_to_width(cv2: Any, image: Any, width: int) -> Any:
    h, w = image.shape[:2]
    if width <= 0 or w == width:
        return image
    target_h = max(1, int(round(h * width / max(1, w))))
    interp = cv2.INTER_AREA if w > width else cv2.INTER_CUBIC
    return cv2.resize(image, (width, target_h), interpolation=interp)


def imwrite(path: Path, image: Any) -> None:
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(path.suffix or ".jpg", image)
    if not ok:
        raise RuntimeError(f"imencode_failed: {path}")
    buf.tofile(str(path))


def nearest_metric(metrics: list[FrameMetric], timestamp: float) -> FrameMetric | None:
    if not metrics:
        return None
    return min(metrics, key=lambda metric: abs(metric.timestamp_sec - timestamp))


def count_role_hits(text: str) -> int:
    normalized = normalize_for_match(text)
    hits = 0
    for token in ROLE_TOKENS:
        if normalize_for_match(token) in normalized:
            hits += 1
    return hits


def normalize_for_match(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^0-9a-z]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_name(value: str) -> str:
    value = normalize_for_match(value).replace(" ", "_")
    return value[:90] or "item"


def derive_item_id(path: Path, *, fallback: str | None = None) -> str:
    stem = path.stem if path.name else (fallback or "video")
    return safe_name(stem)


def format_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def flatten_metric(metric: FrameMetric) -> dict[str, Any]:
    payload = metric.to_dict()
    payload["reasons"] = ";".join(metric.reasons)
    payload["text_samples"] = " | ".join(metric.text_samples)
    payload["line_y_centers"] = ";".join(str(v) for v in metric.line_y_centers)
    payload["line_heights"] = ";".join(str(v) for v in metric.line_heights)
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["_review_path"] = str(path)
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
