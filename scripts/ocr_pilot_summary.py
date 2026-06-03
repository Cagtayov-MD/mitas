"""Summarize a credit_experiment pilot run into one compact table.

Per item: scene-router decision, recommended strategy, which strategies
actually ran, best-confidence strategy, and key output paths.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _best_confidence_strategy(evaluation: dict | None) -> tuple[str, float] | None:
    if not evaluation:
        return None
    rows = evaluation.get("rows") or []
    best: tuple[str, float, str] | None = None  # (strategy, conf, engine)
    for row in rows:
        conf = row.get("confidence_mean")
        if conf is None:
            continue
        strategy = str(row.get("strategy", "?"))
        engine = str(row.get("engine", "?"))
        if best is None or conf > best[1]:
            best = (strategy, float(conf), engine)
    if best is None:
        return None
    return f"{best[0]}/{best[2]}", best[1]


def _strategy_candidate_counts(evaluation: dict | None) -> dict[str, int]:
    if not evaluation:
        return {}
    counts: dict[str, int] = {}
    for row in evaluation.get("rows") or []:
        strategy = str(row.get("strategy", "?"))
        n = int(row.get("candidate_count") or 0)
        if strategy not in counts or n > counts[strategy]:
            counts[strategy] = n
    return counts


def summarize(run_dir: Path) -> str:
    items_dir = run_dir / "items"
    if not items_dir.exists():
        return f"No items/ in {run_dir}"

    lines: list[str] = []
    lines.append(f"# Pilot summary — {run_dir.name}\n")
    lines.append("| Item | scene_router (text_motion / bg) | recommended_temporal | row_reconstruct | temporal_fusion | best by confidence |")
    lines.append("|---|---|---|---|---|---|")

    for item_dir in sorted(items_dir.iterdir()):
        if not item_dir.is_dir():
            continue
        item_id = item_dir.name

        scene = _read_json(item_dir / "scene_router_refined.json") or _read_json(item_dir / "scene_router.json")
        text_motion = (scene or {}).get("text_motion", {}).get("type", "?") if scene else "?"
        background = (scene or {}).get("background", {}).get("type", "?") if scene else "?"
        recommendation = (scene or {}).get("recommended_pipeline", {}).get("temporal", "?") if scene else "?"

        row_rec = _read_json(item_dir / "row_reconstruct.json") or {}
        row_status = row_rec.get("status", "?")
        row_rows = row_rec.get("row_count", "-")
        row_summary = f"{row_status} ({row_rows} rows)" if row_status == "done" else row_status

        fusion = _read_json(item_dir / "temporal_fusion.json") or {}
        fusion_status = fusion.get("status", "?")
        fusion_strategy = fusion.get("strategy", "?")
        if fusion_status == "done":
            static_ratio = fusion.get("static_pixel_ratio")
            fusion_summary = f"{fusion_strategy}"
            if static_ratio is not None:
                fusion_summary += f" (static={static_ratio:.2f})"
        elif fusion_status == "skipped":
            fusion_summary = f"skip ({fusion.get('reason', '?')[:30]})"
        else:
            fusion_summary = f"{fusion_status}"

        evaluation = _read_json(item_dir / "evaluation.json")
        best = _best_confidence_strategy(evaluation)
        best_line = f"{best[0]} @ {best[1]:.3f}" if best else "—"

        lines.append(
            f"| {item_id[:48]} | {text_motion} / {background} | {recommendation} | {row_summary} | {fusion_summary} | {best_line} |"
        )

    # Per-item candidate count breakdown
    lines.append("\n## Candidate counts per strategy (per item)\n")
    lines.append("| Item | frame_ocr | preprocessed | temporal_voting | descroll_canvas | temporal_fusion (median/variance) |")
    lines.append("|---|---|---|---|---|---|")
    for item_dir in sorted(items_dir.iterdir()):
        if not item_dir.is_dir():
            continue
        evaluation = _read_json(item_dir / "evaluation.json")
        counts = _strategy_candidate_counts(evaluation)
        fusion_count = max(
            counts.get("temporal_median_fusion", 0),
            counts.get("temporal_variance_masking", 0),
            counts.get("temporal_fusion", 0),
        )
        lines.append(
            f"| {item_dir.name[:48]} | {counts.get('frame_ocr', 0)} | "
            f"{counts.get('preprocessed_frame_ocr', 0)} | {counts.get('temporal_voting', 0)} | "
            f"{counts.get('descroll_canvas_ocr', 0)} | {fusion_count} |"
        )

    # Output paths
    lines.append("\n## Composite / fused image paths (görsel kontrol için)\n")
    for item_dir in sorted(items_dir.iterdir()):
        if not item_dir.is_dir():
            continue
        item_id = item_dir.name
        candidates = []
        for path in [
            item_dir / "text_layer_row_reconstruct" / "row_composite.png",
            item_dir / "text_layer_row_reconstruct" / "row_composite_sharpened.png",
            item_dir / "temporal_fusion" / "fused.png",
            item_dir / "temporal_fusion" / "mask.png",
            item_dir / "canvases" / "descroll_canvas.png",
        ]:
            if path.exists():
                size_kb = path.stat().st_size // 1024
                candidates.append(f"{path.relative_to(item_dir)} ({size_kb}KB)")
        if candidates:
            lines.append(f"- **{item_id}**: {', '.join(candidates)}")
        else:
            lines.append(f"- **{item_id}**: (no composite/fused outputs)")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", default=None, help="Optional path to write report.md")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    summary = summarize(run_dir)
    print(summary)

    if args.output:
        Path(args.output).write_text(summary, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
