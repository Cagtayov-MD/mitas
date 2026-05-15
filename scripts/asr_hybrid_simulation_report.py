from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_BENCHMARK_ROOT = Path("outputs") / "asr_archive_all_wav_benchmark"
DEFAULT_OUT_DIR = DEFAULT_BENCHMARK_ROOT / "hybrid_simulation_reports"
NO_SPEECH_THRESHOLD = 0.10
MAX_AUTO_SWAP_DURATION = 4.0
AUTO_SWAP_MARGIN = 0.10
MIN_OVERLAP_RATIO = 0.30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate conservative fast/quality hybrid arbitration from ASR archives.")
    parser.add_argument("--benchmark-root", type=Path, default=DEFAULT_BENCHMARK_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--no-speech-threshold", type=float, default=NO_SPEECH_THRESHOLD)
    parser.add_argument("--max-auto-swap-duration", type=float, default=MAX_AUTO_SWAP_DURATION)
    parser.add_argument("--auto-swap-margin", type=float, default=AUTO_SWAP_MARGIN)
    parser.add_argument("--min-overlap-ratio", type=float, default=MIN_OVERLAP_RATIO)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for sample_dir in discover_samples(args.benchmark_root):
        report = simulate_sample(
            sample_dir,
            no_speech_threshold=args.no_speech_threshold,
            max_auto_swap_duration=args.max_auto_swap_duration,
            auto_swap_margin=args.auto_swap_margin,
            min_overlap_ratio=args.min_overlap_ratio,
        )
        reports.append(report)
        write_sample_report(args.out_dir / f"{sample_dir.name}_hybrid_simulation.md", report)
        (args.out_dir / f"{sample_dir.name}_hybrid_simulation.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    aggregate = build_aggregate(reports, vars(args))
    write_aggregate_report(args.out_dir / "aggregate_hybrid_simulation.md", aggregate)
    (args.out_dir / "aggregate_hybrid_simulation.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.out_dir / "aggregate_hybrid_simulation.md")
    return 0


def discover_samples(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.iterdir())
        if path.is_dir() and (path / "fast" / "archive.json").exists() and (path / "quality" / "archive.json").exists()
    ]


def simulate_sample(
    sample_dir: Path,
    *,
    no_speech_threshold: float,
    max_auto_swap_duration: float,
    auto_swap_margin: float,
    min_overlap_ratio: float,
) -> dict[str, Any]:
    fast_archive = json.loads((sample_dir / "fast" / "archive.json").read_text(encoding="utf-8"))
    quality_archive = json.loads((sample_dir / "quality" / "archive.json").read_text(encoding="utf-8"))
    fast_segments = fast_archive.get("segments", [])
    quality_segments = quality_archive.get("segments", [])

    decisions = []
    for quality_index, quality_segment in enumerate(quality_segments):
        q_metrics = segment_metrics(quality_segment)
        overlaps = find_overlaps(quality_segment, fast_segments, min_overlap_ratio=min_overlap_ratio)
        f_metrics = aggregate_fast_metrics(overlaps)
        decision = decide(
            q_metrics,
            f_metrics,
            has_overlap=bool(overlaps),
            no_speech_threshold=no_speech_threshold,
            max_auto_swap_duration=max_auto_swap_duration,
            auto_swap_margin=auto_swap_margin,
        )
        if decision["kind"] == "keep_quality" and q_metrics["no_speech_prob"] <= no_speech_threshold:
            continue
        decisions.append(
            {
                "quality_index": quality_index,
                "decision": decision["kind"],
                "reason": decision["reason"],
                "quality": {
                    **q_metrics,
                    "text": quality_segment.get("text", ""),
                    "flags": quality_segment.get("flags", []),
                },
                "fast_replacements": [
                    {
                        **segment_metrics(segment),
                        "text": segment.get("text", ""),
                        "flags": segment.get("flags", []),
                    }
                    for segment in overlaps
                ],
                "fast_aggregate": f_metrics,
            }
        )

    auto_swaps = [item for item in decisions if item["decision"] == "auto_swap_to_fast"]
    review = [item for item in decisions if item["decision"] == "review_candidate"]
    keep_risky = [item for item in decisions if item["decision"] == "keep_quality"]
    audio_duration = float(quality_archive.get("audio_duration") or fast_archive.get("audio_duration") or 0.0)
    return {
        "sample_id": sample_dir.name,
        "source_name": read_source_name(sample_dir),
        "audio_duration": audio_duration,
        "audio_minutes": round(audio_duration / 60.0, 3),
        "quality_segment_count": len(quality_segments),
        "fast_segment_count": len(fast_segments),
        "decisions": decisions,
        "summary": {
            "risky_quality_segments": len(decisions),
            "auto_swaps": len(auto_swaps),
            "review_candidates": len(review),
            "kept_risky_quality": len(keep_risky),
            "auto_swap_quality_duration": round(sum(item["quality"]["duration"] for item in auto_swaps), 3),
            "review_quality_duration": round(sum(item["quality"]["duration"] for item in review), 3),
            "kept_risky_quality_duration": round(sum(item["quality"]["duration"] for item in keep_risky), 3),
        },
    }


def decide(
    q_metrics: dict[str, Any],
    f_metrics: dict[str, Any] | None,
    *,
    has_overlap: bool,
    no_speech_threshold: float,
    max_auto_swap_duration: float,
    auto_swap_margin: float,
) -> dict[str, str]:
    if q_metrics["no_speech_prob"] <= no_speech_threshold:
        return {"kind": "keep_quality", "reason": "quality_no_speech_below_threshold"}
    if not has_overlap or f_metrics is None:
        return {"kind": "review_candidate", "reason": "quality_risky_no_fast_overlap"}
    if q_metrics["duration"] > max_auto_swap_duration:
        return {"kind": "review_candidate", "reason": "quality_risky_but_segment_too_long"}
    if f_metrics["combined"] >= q_metrics["combined"] + auto_swap_margin:
        return {"kind": "auto_swap_to_fast", "reason": "quality_risky_fast_combined_clearly_better"}
    return {"kind": "review_candidate", "reason": "quality_risky_but_fast_not_clearly_better"}


def find_overlaps(
    quality_segment: dict[str, Any],
    fast_segments: list[dict[str, Any]],
    *,
    min_overlap_ratio: float,
) -> list[dict[str, Any]]:
    matches = []
    for fast_segment in fast_segments:
        overlap = overlap_seconds(quality_segment, fast_segment)
        if overlap <= 0:
            continue
        min_duration = max(min(duration(quality_segment), duration(fast_segment)), 0.001)
        if overlap / min_duration >= min_overlap_ratio:
            matches.append(fast_segment)
    return matches


def aggregate_fast_metrics(segments: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not segments:
        return None
    total_duration = sum(duration(segment) for segment in segments)
    if total_duration <= 0:
        total_duration = float(len(segments))
    avg_logprob = weighted_average(segments, "avg_logprob", total_duration)
    no_speech_prob = weighted_average(segments, "no_speech_prob", total_duration)
    return {
        "start": min(float(segment.get("start", 0.0)) for segment in segments),
        "end": max(float(segment.get("end", 0.0)) for segment in segments),
        "duration": round(sum(duration(segment) for segment in segments), 3),
        "segment_count": len(segments),
        "avg_logprob": round(avg_logprob, 4),
        "no_speech_prob": round(no_speech_prob, 4),
        "combined": round(avg_logprob - no_speech_prob, 4),
    }


def weighted_average(segments: list[dict[str, Any]], key: str, total_duration: float) -> float:
    return sum(float(segment.get(key, 0.0) or 0.0) * max(duration(segment), 0.001) for segment in segments) / total_duration


def segment_metrics(segment: dict[str, Any]) -> dict[str, Any]:
    start = float(segment.get("start", 0.0))
    end = float(segment.get("end", 0.0))
    avg_logprob = float(segment.get("avg_logprob", 0.0) or 0.0)
    no_speech_prob = float(segment.get("no_speech_prob", 0.0) or 0.0)
    return {
        "start": start,
        "end": end,
        "duration": round(end - start, 3),
        "avg_logprob": round(avg_logprob, 4),
        "no_speech_prob": round(no_speech_prob, 4),
        "combined": round(avg_logprob - no_speech_prob, 4),
    }


def overlap_seconds(left: dict[str, Any], right: dict[str, Any]) -> float:
    return max(0.0, min(float(left.get("end", 0.0)), float(right.get("end", 0.0))) - max(float(left.get("start", 0.0)), float(right.get("start", 0.0))))


def duration(segment: dict[str, Any]) -> float:
    return max(0.0, float(segment.get("end", 0.0)) - float(segment.get("start", 0.0)))


def read_source_name(sample_dir: Path) -> str:
    sample_path = sample_dir / "sample.json"
    if not sample_path.exists():
        return sample_dir.name
    data = json.loads(sample_path.read_text(encoding="utf-8"))
    return Path(data.get("source_path", sample_dir.name)).name


def build_aggregate(reports: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for report in reports:
        summary = report["summary"]
        rows.append(
            {
                "sample_id": report["sample_id"],
                "source_name": report["source_name"],
                "audio_minutes": report["audio_minutes"],
                **summary,
                "auto_swap_pct_audio": round(summary["auto_swap_quality_duration"] / max(report["audio_duration"], 0.001) * 100.0, 3),
                "review_pct_audio": round(summary["review_quality_duration"] / max(report["audio_duration"], 0.001) * 100.0, 3),
            }
        )
    return {
        "config": {
            "no_speech_threshold": config["no_speech_threshold"],
            "max_auto_swap_duration": config["max_auto_swap_duration"],
            "auto_swap_margin": config["auto_swap_margin"],
            "min_overlap_ratio": config["min_overlap_ratio"],
        },
        "sample_count": len(reports),
        "totals": {
            "audio_minutes": round(sum(report["audio_minutes"] for report in reports), 3),
            "risky_quality_segments": sum(row["risky_quality_segments"] for row in rows),
            "auto_swaps": sum(row["auto_swaps"] for row in rows),
            "review_candidates": sum(row["review_candidates"] for row in rows),
            "kept_risky_quality": sum(row["kept_risky_quality"] for row in rows),
            "auto_swap_quality_duration": round(sum(row["auto_swap_quality_duration"] for row in rows), 3),
            "review_quality_duration": round(sum(row["review_quality_duration"] for row in rows), 3),
            "kept_risky_quality_duration": round(sum(row["kept_risky_quality_duration"] for row in rows), 3),
        },
        "samples": rows,
    }


def write_sample_report(path: Path, report: dict[str, Any]) -> None:
    lines = [
        f"# Hybrid Simulation: {report['sample_id']}",
        "",
        f"- Source: `{report['source_name']}`",
        f"- Audio minutes: `{report['audio_minutes']}`",
        f"- Risky quality segments: `{report['summary']['risky_quality_segments']}`",
        f"- Auto swaps: `{report['summary']['auto_swaps']}`",
        f"- Review candidates: `{report['summary']['review_candidates']}`",
        "",
        "| Decision | Reason | Q time | Q ns | Q combined | Fast time | Fast combined | Q text | Fast replacement text |",
        "|---|---|---|---:|---:|---|---:|---|---|",
    ]
    for item in report["decisions"]:
        quality = item["quality"]
        fast_aggregate = item["fast_aggregate"] or {}
        fast_text = " ".join(replacement["text"] for replacement in item["fast_replacements"])
        lines.append(
            "| {decision} | {reason} | {q_time} | {q_ns} | {q_combined} | {f_time} | {f_combined} | {q_text} | {f_text} |".format(
                decision=item["decision"],
                reason=item["reason"],
                q_time=f"{quality['start']}-{quality['end']}",
                q_ns=quality["no_speech_prob"],
                q_combined=quality["combined"],
                f_time=format_time(fast_aggregate),
                f_combined=fast_aggregate.get("combined", "-"),
                q_text=escape_md(quality["text"]),
                f_text=escape_md(fast_text),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_aggregate_report(path: Path, aggregate: dict[str, Any]) -> None:
    totals = aggregate["totals"]
    lines = [
        "# Aggregate Hybrid Simulation",
        "",
        f"- Samples: `{aggregate['sample_count']}`",
        f"- Audio minutes: `{totals['audio_minutes']}`",
        f"- Risky quality segments: `{totals['risky_quality_segments']}`",
        f"- Auto swaps: `{totals['auto_swaps']}`",
        f"- Review candidates: `{totals['review_candidates']}`",
        f"- Kept risky quality: `{totals['kept_risky_quality']}`",
        f"- Auto-swap duration: `{totals['auto_swap_quality_duration']}` sec",
        f"- Review duration: `{totals['review_quality_duration']}` sec",
        "",
        "Config:",
        "",
        f"- no_speech_threshold: `{aggregate['config']['no_speech_threshold']}`",
        f"- max_auto_swap_duration: `{aggregate['config']['max_auto_swap_duration']}`",
        f"- auto_swap_margin: `{aggregate['config']['auto_swap_margin']}`",
        f"- min_overlap_ratio: `{aggregate['config']['min_overlap_ratio']}`",
        "",
        "| Sample | Min | Risky Q | Auto swaps | Review | Kept risky | Auto sec | Review sec | Auto % audio | Review % audio |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate["samples"]:
        lines.append(
            f"| {row['sample_id']} | {row['audio_minutes']} | {row['risky_quality_segments']} | {row['auto_swaps']} | "
            f"{row['review_candidates']} | {row['kept_risky_quality']} | {row['auto_swap_quality_duration']} | "
            f"{row['review_quality_duration']} | {row['auto_swap_pct_audio']} | {row['review_pct_audio']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_time(metrics: dict[str, Any]) -> str:
    if not metrics:
        return "-"
    return f"{metrics.get('start')}-{metrics.get('end')}"


def escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
