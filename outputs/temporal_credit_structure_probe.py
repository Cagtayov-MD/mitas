#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Temporal credit structure probe.

Independent diagnostic for testing a structured video-credit representation:
frame OCR -> static_card/scroll_block events -> simple deterministic roles.

Run with the OCR venv:
  E:\MITAS\venvs\ocr\Scripts\python.exe -B outputs\temporal_credit_structure_probe.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import statistics
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


ROOT = Path(r"E:\MITAS")
DEFAULT_FRAMES = ROOT / "Database" / "VAHŞİ SEVGİLİ 1972-0342-1-0000-00-1" / "frames" / "cikis_fb"
DEFAULT_OUT = ROOT / "outputs" / "temporal_credit_structure_probe"
PIPELINE100 = ROOT / "OCR-worktree" / "py" / "20260601_pipeline100.py"


def _load_pipeline100() -> Any:
    spec = importlib.util.spec_from_file_location("pl_temporal_probe", str(PIPELINE100))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pl_temporal_probe"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def frame_number(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else -1


def fold(text: str) -> str:
    text = (text or "").replace("ı", "i").replace("İ", "i")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).casefold()
    return re.sub(r"\s+", " ", text).strip()


def clean_ocr_lines(records: list[tuple[str, str, int, int]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for folded, raw, y0, y1 in records:
        raw = (raw or "").strip()
        f = fold(raw) or folded
        if not raw or not f:
            continue
        if len(f) <= 1:
            continue
        if f in seen:
            continue
        seen.add(f)
        out.append({"text": raw, "fold": f, "y0": int(y0), "y1": int(y1), "cy": (int(y0) + int(y1)) / 2.0})
    return out


def frame_signature(lines: list[dict[str, Any]]) -> str:
    return " | ".join(line["fold"] for line in lines)


def line_set(lines: list[dict[str, Any]]) -> set[str]:
    return {line["fold"] for line in lines if line.get("fold")}


def frame_similarity(a: dict[str, Any], b: dict[str, Any]) -> tuple[float, float]:
    sig_a = a.get("signature", "")
    sig_b = b.get("signature", "")
    seq = SequenceMatcher(None, sig_a, sig_b).ratio() if sig_a or sig_b else 1.0
    set_a = set(a.get("line_set", []))
    set_b = set(b.get("line_set", []))
    if not set_a and not set_b:
        jac = 1.0
    elif not set_a or not set_b:
        jac = 0.0
    else:
        jac = len(set_a & set_b) / len(set_a | set_b)
    return seq, jac


GENERIC_LINE_FOLDS = {"and", "with", "as"}


def comparable_line_set(row: dict[str, Any]) -> set[str]:
    """Line set used for static-card plateau splitting.

    Generic connector words are useful for the final OCR payload, but they make
    adjacent credit cards look falsely similar during dissolves.
    """
    values = set(row.get("line_set", []))
    return {value for value in values if len(value) > 1 and value not in GENERIC_LINE_FOLDS}


def set_similarity(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def ocr_frames(pl: Any, frames: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, path in enumerate(frames, start=1):
        img = pl.fp.rd(str(path))
        recs = pl.read_pos(img)
        lines = clean_ocr_lines(recs)
        row = {
            "frame": path.name,
            "frame_path": str(path),
            "frame_number": frame_number(path),
            "lines": lines,
            "line_texts": [line["text"] for line in lines],
            "line_set": sorted(line_set(lines)),
            "signature": frame_signature(lines),
        }
        rows.append(row)
        print(f"OCR {idx}/{len(frames)} {path.name}: {len(lines)} lines", flush=True)
    return rows


def segment_frames(
    frame_rows: list[dict[str, Any]],
    seq_threshold: float = 0.58,
    jaccard_threshold: float = 0.30,
    anchor_threshold: float = 0.36,
    max_blank_gap: int = 4,
    min_stable_frames: int = 2,
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_anchor: set[str] = set()
    blank_gap = 0

    def flush() -> None:
        nonlocal current, current_anchor
        if current:
            segments.append({"frames": current})
            current = []
            current_anchor = set()

    for row in frame_rows:
        if not row["lines"]:
            blank_gap += 1
            if blank_gap > max_blank_gap:
                flush()
                blank_gap = 0
            continue
        blank_gap = 0
        if not current:
            current = [row]
            current_anchor = comparable_line_set(row)
            continue
        seq, jac = frame_similarity(current[-1], row)
        anchor_jac = set_similarity(current_anchor, comparable_line_set(row))
        if anchor_jac < anchor_threshold or (seq < seq_threshold and jac < jaccard_threshold):
            flush()
            current = [row]
            current_anchor = comparable_line_set(row)
        else:
            current.append(row)
    flush()
    return [summarize_segment(seg, idx, min_stable_frames) for idx, seg in enumerate(segments, start=1)]


def estimate_vertical_motion(frames: list[dict[str, Any]]) -> dict[str, Any]:
    shifts: list[float] = []
    for prev, cur in zip(frames, frames[1:]):
        prev_by_fold = {line["fold"]: line for line in prev["lines"]}
        cur_by_fold = {line["fold"]: line for line in cur["lines"]}
        common = sorted(set(prev_by_fold) & set(cur_by_fold))
        if not common:
            continue
        local = [cur_by_fold[f]["cy"] - prev_by_fold[f]["cy"] for f in common]
        if local:
            shifts.append(statistics.median(local))
    if not shifts:
        return {"median_shift": 0.0, "matched_pairs": 0, "motion": "unknown"}
    med = float(statistics.median(shifts))
    abs_med = abs(med)
    return {
        "median_shift": round(med, 3),
        "matched_pairs": len(shifts),
        "motion": "scroll_like" if abs_med >= 2.5 else "static_like",
    }


def representative_frame(frames: list[dict[str, Any]]) -> dict[str, Any]:
    # In dissolve transitions, the max-line frame is often the wrong frame
    # because old and new cards are visible together. Use the stable middle.
    return frames[len(frames) // 2]


def summarize_segment(segment: dict[str, Any], segment_id: int, min_stable_frames: int) -> dict[str, Any]:
    frames = segment["frames"]
    best = representative_frame(frames)
    motion = estimate_vertical_motion(frames)
    if len(frames) < min_stable_frames:
        event_type = "transition_or_noise"
    else:
        event_type = "scroll_block" if motion["motion"] == "scroll_like" else "static_card"
    return {
        "event_id": f"event_{segment_id:03d}",
        "type": event_type,
        "frame_start": frames[0]["frame"],
        "frame_end": frames[-1]["frame"],
        "frame_count": len(frames),
        "best_frame": best["frame"],
        "motion": motion,
        "lines": best["line_texts"],
        "all_frame_line_counts": {row["frame"]: len(row["lines"]) for row in frames},
    }


ROLE_WORDS = {
    "produced",
    "producer",
    "directed",
    "director",
    "screenplay",
    "story",
    "based",
    "book",
    "photography",
    "assistant",
    "manager",
    "consultant",
    "attendant",
    "mayor",
    "and",
    "featuring",
    "casting",
    "ltd",
    "limited",
    "inc",
    "studios",
    "studio",
    "road",
    "street",
    "london",
    "england",
    "company",
    "group",
    "productions",
    "corporation",
    "laboratories",
    "museum",
    "university",
    "railway",
    "city",
    "television",
}

NON_TARGET_ROLE_MARKERS = (
    "casting by",
    "location casting",
    "unit production manager",
    "production manager",
    "field production supervisor",
    "production supervisor",
    "production coordinator",
    "production sound",
    "associate producer",
    "original music",
    "costumes designed",
    "costume designed",
    "costume designer",
    "key costumers",
    "sets designed",
    "set designer",
    "set decorator",
    "set dresser",
    "art director",
    "property master",
    "director of photography",
    "assistant director",
    "camera operator",
    "assistant cameraman",
    "photography",
    "camera",
    "editor",
    "edited by",
    "music by",
    "music editing",
    "composed by",
    "lyrics by",
    "sound editing",
    "sound mixer",
    "sound recordist",
    "dubbing",
    "wardrobe",
    "make up",
    "make-up",
    "hairdresser",
    "hair stylist",
    "continuity",
    "visual effects",
    "special effects",
    "distributed by",
    "made at",
    "on location by",
    "our thanks",
    "thanks to",
    "lighting contractors",
    "production processing",
    "re recorded",
    "re-recorded",
    "lenses",
    "color by",
    "all rights reserved",
    "artist",
)


def is_upper_person_line(text: str) -> bool:
    stripped = text.strip()
    f = fold(stripped)
    if not f:
        return False
    if any(word in f.split() for word in ROLE_WORDS):
        return False
    letters = [ch for ch in stripped if ch.isalpha()]
    if len(letters) < 5:
        return False
    upper_letters = [ch for ch in letters if ch.upper() == ch and ch.lower() != ch]
    upper_ratio = len(upper_letters) / max(1, len(letters))
    words = [w for w in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", stripped) if len(w) > 1]
    if len(words) < 2:
        return False
    if "." in stripped and len(stripped) <= 10:
        return False
    return upper_ratio >= 0.75


def first_person_after(lines: list[str], start_idx: int, stop_words: tuple[str, ...] = ()) -> list[str]:
    names: list[str] = []
    for text in lines[start_idx + 1 :]:
        f = fold(text)
        if any(stop in f for stop in stop_words):
            break
        if is_upper_person_line(text):
            names.append(text.strip())
        elif names:
            break
    return names


def dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = fold(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def is_non_target_role_card(folds: list[str]) -> bool:
    joined = " | ".join(folds)
    return any(marker in joined for marker in NON_TARGET_ROLE_MARKERS)


def parse_roles(events: list[dict[str, Any]]) -> dict[str, list[str]]:
    roles = {"yonetmen": [], "yapimci": [], "senaryo_yazar": [], "oyuncular": [], "ignored": []}
    credit_started = False
    for event in events:
        if event.get("type") == "transition_or_noise":
            continue
        lines = [str(x).strip() for x in event.get("lines", []) if str(x).strip()]
        folds = [fold(x) for x in lines]
        handled = False
        for i, f in enumerate(folds):
            if "produced and directed by" in f:
                names = first_person_after(lines, i)
                roles["yapimci"].extend(names)
                roles["yonetmen"].extend(names)
                handled = True
                credit_started = True
                break
            if f == "directed by" or f.endswith(" directed by"):
                roles["yonetmen"].extend(first_person_after(lines, i))
                handled = True
                credit_started = True
                break
            if f == "produced by" or f.endswith(" produced by"):
                roles["yapimci"].extend(first_person_after(lines, i))
                handled = True
                credit_started = True
                break
            if "screenplay by" in f or "written by" in f or f == "story by":
                roles["senaryo_yazar"].extend(first_person_after(lines, i, stop_words=("based on", "book by")))
                handled = True
                credit_started = True
                break
            if "director of photography" in f or "assistant director" in f:
                roles["ignored"].extend([name for name in first_person_after(lines, i)])
                handled = True
                credit_started = True
                break
        if handled:
            continue
        if is_non_target_role_card(folds):
            roles["ignored"].extend([line for line in lines if is_upper_person_line(line)])
            continue
        cast_names = [line for line in lines if is_upper_person_line(line)]
        if credit_started and cast_names:
            roles["oyuncular"].extend(cast_names)
    return {key: dedupe(value) for key, value in roles.items()}


def write_outputs(out_dir: Path, frame_rows: list[dict[str, Any]], events: list[dict[str, Any]], roles: dict[str, list[str]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"frame_count": len(frame_rows), "events": events, "roles": roles, "frame_ocr": frame_rows}
    (out_dir / "temporal_credit_structure_probe.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = ["# Temporal Credit Structure Probe", ""]
    lines.append(f"- Frames OCR'd: {len(frame_rows)}")
    lines.append(f"- Events: {len(events)}")
    lines.append("- Representative frame policy: stable middle frame, not max-line transition frame")
    lines.append("")
    lines.append("## Roles")
    for key, values in roles.items():
        lines.append(f"- {key}: {', '.join(values) if values else '-'}")
    lines.append("")
    lines.append("## Events")
    for event in events:
        lines.append(f"### {event['event_id']} {event['type']} {event['frame_start']}..{event['frame_end']}")
        lines.append(f"- Best frame: {event['best_frame']}")
        lines.append(f"- Frame count: {event['frame_count']}")
        lines.append(f"- Motion: {event['motion']}")
        for text in event["lines"]:
            lines.append(f"  - {text}")
        lines.append("")
    (out_dir / "temporal_credit_structure_probe.md").write_text("\n".join(lines), encoding="utf-8")
    print(out_dir / "temporal_credit_structure_probe.json")
    print(out_dir / "temporal_credit_structure_probe.md")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames-dir", type=Path, default=DEFAULT_FRAMES)
    parser.add_argument("--start", type=int, default=201)
    parser.add_argument("--end", type=int, default=320)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seq-threshold", type=float, default=0.58)
    parser.add_argument("--jaccard-threshold", type=float, default=0.30)
    parser.add_argument("--anchor-threshold", type=float, default=0.36)
    parser.add_argument("--min-stable-frames", type=int, default=2)
    args = parser.parse_args()

    frames = [
        p
        for p in sorted(args.frames_dir.glob("*.png"), key=frame_number)
        if args.start <= frame_number(p) <= args.end
    ]
    if not frames:
        raise SystemExit("No frames selected.")
    pl = _load_pipeline100()
    frame_rows = ocr_frames(pl, frames)
    events = segment_frames(
        frame_rows,
        args.seq_threshold,
        args.jaccard_threshold,
        args.anchor_threshold,
        min_stable_frames=args.min_stable_frames,
    )
    roles = parse_roles(events)
    write_outputs(args.out_dir, frame_rows, events, roles)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
