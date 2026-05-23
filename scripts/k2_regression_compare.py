"""K-2 regression smoke and Opus reference comparison."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil

from core.pipelines.ocr.credit_experiment import run_credit_experiment


DEFAULT_MANIFEST = Path("E:/MITAS/data/ocr_k2_regression_last3min_20260523.json")
DEFAULT_REFERENCE = Path("F:/REPO_GitHub/Cagatay_22.02/Project/test_outputs/pipeline_test/K-2/composite.png")
DEFAULT_OUTPUT_ROOT = Path("E:/MITAS/outputs/k2_compare")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run K-2 MITAS smoke and compare against the Opus composite.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--reference", default=str(DEFAULT_REFERENCE))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--tag", default=None)
    parser.add_argument("--with-ocr", action="store_true", help="Run configured OCR engines too. Default is row/composite only.")
    args = parser.parse_args(argv)

    tag = args.tag or datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_root) / tag
    run_dir = out_dir / "mitas_run"
    out_dir.mkdir(parents=True, exist_ok=True)

    engines = None if args.with_ocr else []
    result = run_credit_experiment(
        args.manifest,
        output_dir=run_dir,
        engines=engines,
        preprocess_mode="off",
    )
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    item = (summary.get("items") or [{}])[0]
    item_id = item.get("id")
    item_dir = run_dir / "items" / str(item_id)
    row_summary_path = item_dir / "text_layer_row_reconstruct" / "row_reconstruct_summary.json"
    row_summary = _read_json(row_summary_path)
    composite_path = Path(row_summary.get("composite_path") or "")
    reference_path = Path(args.reference)

    if composite_path.exists():
        shutil.copy2(composite_path, out_dir / "mitas_composite.png")
    if reference_path.exists():
        shutil.copy2(reference_path, out_dir / "opus_reference.png")
    contact_sheet = _build_contact_sheet(
        mitas_path=out_dir / "mitas_composite.png",
        reference_path=out_dir / "opus_reference.png",
        output_path=out_dir / "k2_compare_contact_sheet.png",
    )

    report = {
        "tag": tag,
        "manifest": str(Path(args.manifest)),
        "run_summary_path": str(result.summary_path),
        "item_id": item_id,
        "credit_segment_detection": item.get("credit_segment_detection"),
        "mitas": {
            "composite_path": str(out_dir / "mitas_composite.png") if composite_path.exists() else str(composite_path),
            "composite_size": row_summary.get("composite_size"),
            "input_frame_count": row_summary.get("input_frame_count"),
            "processed_frame_count": row_summary.get("processed_frame_count"),
            "displacement_range_px": ((row_summary.get("motion") or {}).get("displacement_range_px")),
            "row_count": row_summary.get("row_count"),
            "quality": row_summary.get("quality"),
        },
        "opus_reference": {
            "path": str(reference_path),
            "size": _image_size(reference_path),
        },
        "contact_sheet": str(contact_sheet) if contact_sheet else None,
    }
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(_report_md(report), encoding="utf-8")
    print(json.dumps({"report": str(out_dir / "report.json"), "contact_sheet": report["contact_sheet"]}, ensure_ascii=False))
    return 0


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _image_size(path: Path) -> list[int] | None:
    if not path.exists():
        return None
    try:
        import cv2

        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            return None
        height, width = image.shape[:2]
        return [int(width), int(height)]
    except Exception:
        return None


def _build_contact_sheet(*, mitas_path: Path, reference_path: Path, output_path: Path) -> Path | None:
    if not mitas_path.exists() or not reference_path.exists():
        return None
    try:
        import cv2
        import numpy as np

        left = cv2.imread(str(mitas_path), cv2.IMREAD_COLOR)
        right = cv2.imread(str(reference_path), cv2.IMREAD_COLOR)
        if left is None or right is None:
            return None
        target_h = 1400
        left = _resize_to_height(left, target_h, cv2)
        right = _resize_to_height(right, target_h, cv2)
        gap = np.full((target_h, 30, 3), 255, dtype=np.uint8)
        sheet = np.concatenate([left, gap, right], axis=1)
        cv2.imwrite(str(output_path), sheet)
        return output_path
    except Exception:
        return None


def _resize_to_height(image, height: int, cv2):
    h, w = image.shape[:2]
    if h == height:
        return image
    width = max(1, int(round(w * (height / max(1, h)))))
    return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)


def _report_md(report: dict) -> str:
    mitas = report.get("mitas") or {}
    opus = report.get("opus_reference") or {}
    segment = report.get("credit_segment_detection") or {}
    lines = [
        "# K-2 Regression Compare",
        "",
        f"- Tag: `{report.get('tag')}`",
        f"- MITAS composite: `{mitas.get('composite_path')}`",
        f"- Opus reference: `{opus.get('path')}`",
        f"- Contact sheet: `{report.get('contact_sheet')}`",
        "",
        "## Segment",
        "",
        f"- Status: `{segment.get('status')}`",
        f"- Effective: `{segment.get('effective_start_seconds')}` - `{segment.get('effective_end_seconds')}`",
        f"- Detector: `{segment.get('detected_type')}` confidence `{segment.get('detected_confidence')}`",
        "",
        "## Metrics",
        "",
        "| metric | MITAS | Opus/reference |",
        "| --- | ---: | ---: |",
        f"| composite_size | {mitas.get('composite_size')} | {opus.get('size')} |",
        f"| processed_frame_count | {mitas.get('processed_frame_count')} |  |",
        f"| displacement_range_px | {mitas.get('displacement_range_px')} |  |",
        f"| row_count | {mitas.get('row_count')} | 126 hedef |",
        f"| quality | {mitas.get('quality')} |  |",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
