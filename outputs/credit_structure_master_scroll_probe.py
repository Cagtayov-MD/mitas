#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Master-PNG scroll retest for credit role extraction.

Independent diagnostic. It does not change the production pipeline.

Flow:
  frames/cikis_fb -> compose_hybrid master -> OCR master -> role parser -> report

Run:
  E:\MITAS\venvs\ocr\Scripts\python.exe -B outputs\credit_structure_master_scroll_probe.py --focus-scrolls
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT = Path(r"E:\MITAS")
DATABASE = ROOT / "Database"
PIPELINE100 = ROOT / "OCR-worktree" / "py" / "20260601_pipeline100.py"
DB_COMPOSE = ROOT / "OCR-worktree" / "py" / "db_compose_standalone.py"
DEFAULT_OUT = ROOT / "outputs" / "credit_structure_master_scroll"

# Folded title fragments. Kept ASCII on purpose.
DEFAULT_FOCUS_FOLDS = (
    "14 den 30 a yolculuk",
    "kuzeyde",
    "bill kendi basina",
    "vahsi sevgili",
    "gercek cesaret",
    "paris te bir amerikali",
)


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def fold(text: str) -> str:
    text = (text or "").replace("ı", "i").replace("İ", "i")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).casefold()
    return re.sub(r"\s+", " ", text).strip()


def frame_number(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else -1


def safe_name(text: str, limit: int = 90) -> str:
    out = re.sub(r"[^A-Za-z0-9._-]+", "_", fold(text)).strip("_")
    return (out or "film")[:limit]


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_year(name: str) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", name)
    return int(match.group(0)) if match else None


def title_from_folder(folder: Path) -> str:
    meta = read_json(folder / "clip.json")
    if meta.get("title"):
        return str(meta["title"])
    return re.sub(r"\s+\d{4}-.+$", "", folder.name).strip()


def case_from_folder(folder: Path) -> dict[str, Any]:
    meta = read_json(folder / "clip.json")
    frames_dir = folder / "frames" / "cikis_fb"
    frames = sorted(frames_dir.glob("*.png"), key=frame_number) if frames_dir.exists() else []
    return {
        "folder": folder,
        "frames_dir": frames_dir,
        "title": meta.get("title") or title_from_folder(folder),
        "trt_id": meta.get("trt_id") or "",
        "year": parse_year(folder.name),
        "tur": meta.get("tur") or "",
        "frame_total": len(frames),
    }


def discover_cases(args: argparse.Namespace) -> list[dict[str, Any]]:
    film_needles = [fold(x) for x in (args.film or []) if fold(x)]
    focus_needles = list(DEFAULT_FOCUS_FOLDS) if args.focus_scrolls else []
    needles = film_needles or focus_needles

    cases: list[dict[str, Any]] = []
    folders = sorted([p for p in DATABASE.iterdir() if p.is_dir()], key=lambda p: (parse_year(p.name) or 9999, p.name))
    for folder in folders:
        f_name = fold(folder.name)
        if needles and not any(n in f_name for n in needles):
            continue
        frames_dir = folder / "frames" / "cikis_fb"
        if not frames_dir.exists():
            continue
        frame_count = len(list(frames_dir.glob("*.png")))
        if frame_count < args.min_frames:
            continue
        cases.append(case_from_folder(folder))
        if args.limit and len(cases) >= args.limit:
            break
    return cases


def select_frames(args: argparse.Namespace, frames_dir: Path) -> list[Path]:
    frames = sorted(frames_dir.glob("*.png"), key=frame_number)
    out: list[Path] = []
    for idx, frame in enumerate(frames, start=1):
        n = frame_number(frame)
        if args.start is not None and n < args.start:
            continue
        if args.end is not None and n > args.end:
            continue
        if ((idx - 1) % max(1, args.stride)) == 0:
            out.append(frame)
    if args.max_frames and len(out) > args.max_frames:
        out = out[: args.max_frames]
    return out


def write_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"PNG encode failed: {path}")
    encoded.tofile(str(path))


def read_png(path: Path) -> np.ndarray | None:
    if not path.exists():
        return None
    data = np.fromfile(str(path), np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def clean_lines(records: list[tuple[str, str, int, int]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for folded, raw, *_ in records:
        text = (raw or "").strip()
        key = fold(text) or str(folded or "").strip()
        if not text or not key or len(key) <= 1:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def build_hybrid_master(pl: Any, frames: list[Path]) -> tuple[np.ndarray | None, list[str], dict[str, Any]]:
    frame_strings = [str(p) for p in frames]
    idx = list(range(len(frame_strings)))
    imgs: dict[int, np.ndarray] = {}
    ocr_pos: dict[int, list[tuple[str, str, int, int]]] = {}
    started = time.perf_counter()
    for pos, frame in enumerate(frame_strings):
        img = pl.fp.rd(frame)
        imgs[pos] = img
        ocr_pos[pos] = pl.read_pos(img)
        if (pos + 1) % 50 == 0 or (pos + 1) == len(frame_strings):
            print(f"      frame OCR {pos + 1}/{len(frame_strings)}", flush=True)
    master, stitched = pl.compose_hybrid(frame_strings, idx, imgs, ocr_pos)
    manifest = {
        "composer": "hybrid",
        "frames": len(frames),
        "per_frame_ocr_lines": sum(len(v) for v in ocr_pos.values()),
        "stitched_lines": len(stitched or []),
        "elapsed_sec": round(time.perf_counter() - started, 2),
    }
    return master, [str(x).strip() for x in (stitched or []) if str(x).strip()], manifest


def build_visual_master(comp: Any, frames: list[Path]) -> tuple[np.ndarray | None, list[str], dict[str, Any]]:
    started = time.perf_counter()
    master, manifest = comp.compose([str(p) for p in frames])
    return master, [], {
        "composer": "visual",
        "frames": len(frames),
        "runs": manifest,
        "elapsed_sec": round(time.perf_counter() - started, 2),
    }


ROLE_WORDS = {
    "actor",
    "actress",
    "and",
    "art",
    "assistant",
    "based",
    "book",
    "by",
    "camera",
    "cast",
    "casting",
    "cinematography",
    "color",
    "costume",
    "director",
    "directed",
    "dresser",
    "edited",
    "editor",
    "effects",
    "featuring",
    "gaffer",
    "grip",
    "hair",
    "lighting",
    "lyrics",
    "manager",
    "music",
    "photography",
    "producer",
    "produced",
    "production",
    "screenplay",
    "script",
    "ses",
    "seslend",
    "seslendiren",
    "seslendirenler",
    "seslendirme",
    "sound",
    "story",
    "supervisor",
    "thanks",
    "wardrobe",
    "with",
    "written",
}

ORG_WORDS = {
    "airlines",
    "association",
    "avenue",
    "bank",
    "beer",
    "board",
    "bros",
    "bureau",
    "center",
    "city",
    "coca",
    "cola",
    "commission",
    "company",
    "congregation",
    "corporation",
    "council",
    "department",
    "disney",
    "dolby",
    "enterprises",
    "festival",
    "foundation",
    "group",
    "hotel",
    "inc",
    "international",
    "laboratories",
    "lab",
    "labdratories",
    "labs",
    "limited",
    "london",
    "ltd",
    "miller",
    "museum",
    "network",
    "northwest",
    "oldsmobile",
    "panavision",
    "pictures",
    "playhouse",
    "productions",
    "railway",
    "road",
    "society",
    "state",
    "street",
    "school",
    "studio",
    "studios",
    "television",
    "theatre",
    "theatres",
    "treatment",
    "university",
    "vista",
}

OBJECT_WORDS = {
    "action",
    "aged",
    "ajence",
    "ambmet",
    "boxty",
    "candy",
    "classifying",
    "coverage",
    "cys",
    "france",
    "gum",
    "june",
    "killed",
    "miniskirts",
    "radio",
    "radios",
    "roller",
    "serdtry",
    "sertry",
    "shorts",
    "skateboards",
    "skates",
    "words",
}

HONORIFIC_WORDS = {"mr", "mrs", "ms", "miss", "dr"}

TARGET_ROLE_MARKERS = {
    "directed by": ("yonetmen",),
    "directed": ("yonetmen",),
    "yoneten": ("yonetmen",),
    "yonetmen": ("yonetmen",),
    "produced by": ("yapimci",),
    "producer": ("yapimci",),
    "yapimci": ("yapimci",),
    "screenplay by": ("senaryo_yazar",),
    "written by": ("senaryo_yazar",),
    "story by": ("senaryo_yazar",),
    "senaryo": ("senaryo_yazar",),
}

NON_TARGET_MARKERS = (
    "additional photography",
    "additional music",
    "additional musician",
    "apprentice sound",
    "art director",
    "based on",
    "based on the book",
    "assisan",
    "assistant camera",
    "assistant cameraman",
    "assistant director",
    "camera operator",
    "catering",
    "casting",
    "cinematographer",
    "color by",
    "continuity",
    "construction department",
    "costume",
    "director of photography",
    "distributed by",
    "dubbing",
    "edited by",
    "editor",
    "effects",
    "film finances",
    "first assistant camera",
    "foley",
    "gaffer",
    "hair",
    "key grip",
    "lamera",
    "lighting",
    "location",
    "location catering",
    "made at",
    "make up",
    "make-up",
    "music",
    "music consultant",
    "music produced",
    "negative",
    "on location",
    "original score",
    "photography",
    "processing",
    "production coordinator",
    "production manager",
    "property",
    "recorded",
    "re recorded",
    "re-recorded",
    "second unit",
    "set decorator",
    "sound",
    "special effects",
    "spesidi effects",
    "supplied by",
    "thanks",
    "titles and optical effects",
    "visual effects",
    "wardrobe",
)

TERMINAL_MARKERS = (
    "all rights",
    "any similarity",
    "characters",
    "copyright",
    "courtesy",
    "fictional",
    "filmed in",
    "footage supplied",
    "prerecorded footage",
    "special thanks",
    "supplied by",
    "thanks",
    "unauthorized",
    "with thanks",
)

CAST_START_MARKERS = (
    "cast",
    "starring",
    "co starring",
    "co-starring",
    "featuring",
    "seslend",
    "seslendirenler",
    "with",
    "oyuncular",
)


def line_has_org_marker(text: str) -> bool:
    words = set(fold(text).split())
    return bool(words & ORG_WORDS)


def line_has_object_marker(text: str) -> bool:
    words = set(fold(text).split())
    return bool(words & OBJECT_WORDS)


def line_has_role_word(text: str) -> bool:
    words = set(fold(text).split())
    return bool(words & ROLE_WORDS)


def target_roles_for(folded: str) -> tuple[str, ...]:
    if "produced and directed by" in folded:
        return ("yapimci", "yonetmen")
    if "director of photography" in folded or "assistant director" in folded or "music produced" in folded:
        return ()
    if "seslend" in folded and "yonetmen" in folded:
        return ()
    for marker, roles in TARGET_ROLE_MARKERS.items():
        if marker == "producer" and folded not in ("producer", "film producer"):
            continue
        if folded == marker or folded.startswith(marker + " ") or folded.endswith(" " + marker) or marker in folded:
            return roles
    return ()


def is_non_target_marker(folded: str) -> bool:
    if "seslend" in folded and "yonetmen" in folded:
        return True
    if "ses kayit" in folded or "ses kay" in folded:
        return True
    if "alt yazi" in folded or "altyazi" in folded:
        return True
    if "esleme" in folded:
        return True
    return any(marker in folded for marker in NON_TARGET_MARKERS)


def is_terminal_marker(folded: str) -> bool:
    return any(marker in folded for marker in TERMINAL_MARKERS)


def is_cast_marker(folded: str) -> bool:
    return any(marker == folded or marker in folded for marker in CAST_START_MARKERS)


def person_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:\.)?", text)


def is_upperish_name_token(token: str) -> bool:
    letters = [ch for ch in token if ch.isalpha()]
    if not letters:
        return False
    folded = fold(token).strip(".")
    if folded in {"jr", "ii", "iii", "iv"}:
        return True
    if len(letters) == 1:
        return True
    upper_letters = [ch for ch in letters if ch.upper() == ch and ch.lower() != ch]
    return len(upper_letters) / max(1, len(letters)) >= 0.68


def extract_inline_actor(text: str) -> str | None:
    raw = (text or "").strip()
    f = fold(raw)
    if not f or line_has_org_marker(raw) or line_has_object_marker(raw) or is_non_target_marker(f) or target_roles_for(f):
        return None
    if f.startswith("by ") or f.startswith("the "):
        return None
    parts = raw.split()
    if len(parts) < 3:
        return None
    suffix: list[str] = []
    for token in reversed(parts):
        if is_upperish_name_token(token):
            suffix.append(token.strip())
            continue
        break
    suffix.reverse()
    if len(suffix) >= len(parts):
        return None
    prefix = parts[: len(parts) - len(suffix)]
    prefix_words = set(fold(" ".join(prefix)).split())
    if prefix_words & {"and", "by", "of", "the", "with", "from", "to"}:
        return None
    for token in prefix:
        letters = [ch for ch in token if ch.isalpha()]
        if len(letters) > 1:
            upper_letters = [ch for ch in letters if ch.upper() == ch and ch.lower() != ch]
            if len(upper_letters) / max(1, len(letters)) > 0.50:
                return None
    core = [token for token in suffix if fold(token).strip(".") not in {"jr", "ii", "iii", "iv"}]
    if len(core) < 2:
        return None
    candidate = " ".join(suffix).strip(" ,")
    return candidate if is_strong_person_line(candidate) else None


def is_strong_person_line(text: str) -> bool:
    raw = (text or "").strip()
    f = fold(raw)
    if not f:
        return False
    if line_has_org_marker(raw) or line_has_object_marker(raw) or line_has_role_word(raw):
        return False
    if any(ch.isdigit() for ch in raw):
        return False
    tokens = [t for t in person_tokens(raw) if len(t.replace(".", "")) >= 1]
    word_tokens = [t for t in tokens if len(t.replace(".", "")) > 1]
    if len(tokens) < 2 or len(word_tokens) < 1 or len(tokens) > 5:
        return False
    if fold(tokens[0]).strip(".") in HONORIFIC_WORDS and len(tokens) < 3:
        return False
    letters = [ch for ch in raw if ch.isalpha()]
    if len(letters) < 5:
        return False
    upper_letters = [ch for ch in letters if ch.upper() == ch and ch.lower() != ch]
    upper_ratio = len(upper_letters) / max(1, len(letters))
    has_initial = any("." in t and len(t.replace(".", "")) <= 2 for t in tokens)
    return upper_ratio >= 0.68 or (has_initial and upper_ratio >= 0.45)


def is_character_like(text: str) -> bool:
    raw = (text or "").strip()
    f = fold(raw)
    if not f:
        return False
    if line_has_org_marker(raw) or line_has_object_marker(raw) or is_non_target_marker(f) or target_roles_for(f):
        return False
    if any(ch.isdigit() for ch in raw):
        return False
    toks = [t for t in person_tokens(raw) if len(t.replace(".", "")) > 0]
    if not toks or len(toks) > 5:
        return False
    if is_strong_person_line(raw):
        return False
    letters = [ch for ch in raw if ch.isalpha()]
    upper_letters = [ch for ch in letters if ch.upper() == ch and ch.lower() != ch]
    if letters and len(upper_letters) / max(1, len(letters)) >= 0.75:
        return False
    return True


def dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = value.strip()
        key = fold(value)
        if not value or not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def collect_names_after(lines: list[str], index: int, max_scan: int = 8) -> tuple[list[str], set[int]]:
    names: list[str] = []
    consumed: set[int] = set()
    for j in range(index + 1, min(len(lines), index + 1 + max_scan)):
        f = fold(lines[j])
        if target_roles_for(f) or is_non_target_marker(f):
            break
        if is_strong_person_line(lines[j]):
            names.append(lines[j].strip())
            consumed.add(j)
            continue
        if names:
            break
        if f and not is_character_like(lines[j]):
            break
    return names, consumed


def parse_roles_from_lines(lines: list[str]) -> dict[str, list[str]]:
    roles: dict[str, list[str]] = {"yonetmen": [], "yapimci": [], "senaryo_yazar": [], "oyuncular": [], "ignored": []}
    clean = [x.strip() for x in lines if str(x).strip()]
    folds = [fold(x) for x in clean]
    consumed: set[int] = set()
    ignored_indexes: set[int] = set()
    cast_zone = False

    for i, f in enumerate(folds):
        if is_terminal_marker(f):
            cast_zone = False
        target = target_roles_for(f)
        if target:
            names, used = collect_names_after(clean, i)
            for role in target:
                roles[role].extend(names)
            consumed.update(used)
            cast_zone = False
            continue
        if is_non_target_marker(f):
            names, used = collect_names_after(clean, i)
            roles["ignored"].extend(names)
            ignored_indexes.update(used)
            consumed.update(used)
            cast_zone = False
            continue
        if is_cast_marker(f):
            cast_zone = True

    cast_zone = False
    for i, text in enumerate(clean):
        if i in consumed or i in ignored_indexes:
            continue
        f = folds[i]
        if is_terminal_marker(f):
            cast_zone = False
            continue
        if target_roles_for(f) or is_non_target_marker(f):
            cast_zone = False if is_non_target_marker(f) else cast_zone
            continue
        if is_cast_marker(f):
            cast_zone = True
            continue
        inline_actor = extract_inline_actor(text)
        if inline_actor:
            roles["oyuncular"].append(inline_actor)
            cast_zone = True
            continue
        if not is_strong_person_line(text):
            continue
        prev_f = folds[i - 1] if i > 0 else ""
        next_f = folds[i + 1] if i + 1 < len(folds) else ""
        if target_roles_for(prev_f) or is_non_target_marker(prev_f) or is_non_target_marker(next_f):
            roles["ignored"].append(text)
            continue
        next_is_character = i + 1 < len(clean) and is_character_like(clean[i + 1])
        if cast_zone or next_is_character:
            roles["oyuncular"].append(text)

    return {key: dedupe(values) for key, values in roles.items()}


def merge_roles(*items: dict[str, list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"yonetmen": [], "yapimci": [], "senaryo_yazar": [], "oyuncular": [], "ignored": []}
    for roles in items:
        for key in out:
            out[key].extend(roles.get(key) or [])
    return {key: dedupe(values) for key, values in out.items()}


def official_names(roles: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for key in ("yonetmen", "yapimci", "senaryo_yazar", "oyuncular"):
        out.extend(roles.get(key) or [])
    return out


def is_single_token_name(name: str) -> bool:
    return len([x for x in fold(name).split() if x]) < 2


def technical_leak(name: str) -> bool:
    f = fold(name)
    return is_non_target_marker(f) or line_has_role_word(name)


def organization_leak(name: str) -> bool:
    return line_has_org_marker(name)


def summarize_case(
    case: dict[str, Any],
    frames: list[Path],
    master: np.ndarray | None,
    roles: dict[str, list[str]],
    roles_stitched: dict[str, list[str]],
    roles_master: dict[str, list[str]],
    stitched_lines: list[str],
    master_lines: list[str],
    manifest: dict[str, Any],
    role_source: str,
    elapsed: float,
) -> dict[str, Any]:
    names = official_names(roles)
    single = [n for n in names if is_single_token_name(n)]
    tech = [n for n in names if technical_leak(n)]
    org = [n for n in names if organization_leak(n)]
    flags: list[str] = []
    if not stitched_lines and not master_lines:
        flags.append("NO_TEXT")
    if master is None:
        flags.append("NO_MASTER")
    if not names:
        flags.append("NO_OFFICIAL_NAMES")
    if not roles.get("oyuncular"):
        flags.append("NO_CAST")
    if not roles.get("yonetmen"):
        flags.append("NO_DIRECTOR")
    if single:
        flags.append("SINGLE_TOKEN_OFFICIAL")
    if tech:
        flags.append("TECHNICAL_LEAK_OFFICIAL")
    if org:
        flags.append("ORG_OR_ADDRESS_LEAK_OFFICIAL")
    if len(roles.get("oyuncular") or []) > 35:
        flags.append("TOO_MANY_CAST")
    hard = {"NO_TEXT", "NO_MASTER", "SINGLE_TOKEN_OFFICIAL", "TECHNICAL_LEAK_OFFICIAL", "ORG_OR_ADDRESS_LEAK_OFFICIAL"}
    status = "FAIL" if any(f in hard for f in flags) else ("REVIEW" if flags else "OK")
    return {
        "status": status,
        "flags": flags,
        "folder": str(case["folder"]),
        "title": case["title"],
        "trt_id": case["trt_id"],
        "year": case["year"],
        "tur": case["tur"],
        "frame_total": case["frame_total"],
        "frames_used": len(frames),
        "master_size": [int(master.shape[1]), int(master.shape[0])] if master is not None else None,
        "stitched_line_count": len(stitched_lines),
        "master_ocr_line_count": len(master_lines),
        "role_source": role_source,
        "roles": roles,
        "roles_stitched": roles_stitched,
        "roles_master_ocr": roles_master,
        "director_count": len(roles.get("yonetmen") or []),
        "producer_count": len(roles.get("yapimci") or []),
        "writer_count": len(roles.get("senaryo_yazar") or []),
        "cast_count": len(roles.get("oyuncular") or []),
        "ignored_count": len(roles.get("ignored") or []),
        "single_token_names": single,
        "technical_leak_names": tech,
        "organization_or_address_leak_names": org,
        "manifest": manifest,
        "elapsed_sec": round(elapsed, 2),
    }


def write_case_outputs(
    film_dir: Path,
    summary: dict[str, Any],
    manifest: dict[str, Any],
    stitched_lines: list[str],
    master_lines: list[str],
) -> None:
    film_dir.mkdir(parents=True, exist_ok=True)
    (film_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (film_dir / "stitched_lines.txt").write_text("\n".join(stitched_lines), encoding="utf-8")
    (film_dir / "master_ocr_lines.txt").write_text("\n".join(master_lines), encoding="utf-8")
    (film_dir / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# {summary['title']} ({summary.get('year') or '-'})", ""]
    lines.append(f"- Status: {summary['status']}")
    lines.append(f"- Flags: {', '.join(summary['flags']) if summary['flags'] else '-'}")
    lines.append(f"- Frames: {summary['frames_used']} / {summary['frame_total']}")
    lines.append(f"- Master: {summary['master_size']}")
    lines.append(f"- Lines: stitched={summary['stitched_line_count']} master_ocr={summary['master_ocr_line_count']}")
    lines.append(f"- Role source: {summary['role_source']}")
    lines.append("")
    lines.append("## Roles Combined")
    for key, values in summary["roles"].items():
        lines.append(f"- {key}: {', '.join(values) if values else '-'}")
    lines.append("")
    lines.append("## Roles From Stitched")
    for key, values in summary["roles_stitched"].items():
        lines.append(f"- {key}: {', '.join(values) if values else '-'}")
    lines.append("")
    lines.append("## Roles From Master OCR")
    for key, values in summary["roles_master_ocr"].items():
        lines.append(f"- {key}: {', '.join(values) if values else '-'}")
    (film_dir / "result.md").write_text("\n".join(lines), encoding="utf-8")


def write_reports(out_dir: Path, summaries: list[dict[str, Any]], cases: list[dict[str, Any]]) -> None:
    payload = {
        "config": {"case_count": len(cases)},
        "summary_counts": {
            "films": len(summaries),
            "ok": sum(1 for s in summaries if s["status"] == "OK"),
            "review": sum(1 for s in summaries if s["status"] == "REVIEW"),
            "fail": sum(1 for s in summaries if s["status"] == "FAIL"),
        },
        "films": summaries,
    }
    (out_dir / "master_scroll_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Master Scroll Retest", ""]
    lines.append(f"- Films: {len(summaries)}")
    lines.append(f"- OK: {payload['summary_counts']['ok']}")
    lines.append(f"- REVIEW: {payload['summary_counts']['review']}")
    lines.append(f"- FAIL: {payload['summary_counts']['fail']}")
    lines.append("")
    lines.append("| status | year | title | roles | flags |")
    lines.append("|---|---:|---|---|---|")
    for s in summaries:
        roles = f"yon={s['director_count']} yap={s['producer_count']} sen={s['writer_count']} cast={s['cast_count']} ign={s['ignored_count']}"
        flags = ", ".join(s["flags"]) if s["flags"] else "-"
        lines.append(f"| {s['status']} | {s.get('year') or ''} | {s['title']} | {roles} | {flags} |")
    lines.append("")
    lines.append("## Details")
    for s in summaries:
        lines.append(f"### {s['status']} - {s['title']} ({s.get('year') or '-'})")
        lines.append(f"- Flags: {', '.join(s['flags']) if s['flags'] else '-'}")
        lines.append(f"- Master: {s['master_size']} lines stitched={s['stitched_line_count']} master_ocr={s['master_ocr_line_count']}")
        for key, values in s["roles"].items():
            lines.append(f"- {key}: {', '.join(values) if values else '-'}")
        lines.append("")
    (out_dir / "master_scroll_report.md").write_text("\n".join(lines), encoding="utf-8")

    try:
        from openpyxl import Workbook
    except Exception:
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    headers = [
        "status",
        "flags",
        "year",
        "title",
        "trt_id",
        "tur",
        "frames_used",
        "frame_total",
        "master_size",
        "stitched_line_count",
        "master_ocr_line_count",
        "role_source",
        "director_count",
        "producer_count",
        "writer_count",
        "cast_count",
        "ignored_count",
        "yonetmen",
        "yapimci",
        "senaryo_yazar",
        "oyuncular",
        "ignored",
        "single_token_names",
        "technical_leak_names",
        "organization_or_address_leak_names",
        "elapsed_sec",
        "folder",
    ]
    ws.append(headers)
    for s in summaries:
        row: list[Any] = []
        for header in headers:
            if header in ("yonetmen", "yapimci", "senaryo_yazar", "oyuncular", "ignored"):
                value = s["roles"].get(header) or []
            else:
                value = s.get(header)
            row.append(json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value)
        ws.append(row)
    wb.save(out_dir / "master_scroll_report.xlsx")


def process_case(args: argparse.Namespace, pl: Any, comp: Any | None, case: dict[str, Any], index: int) -> dict[str, Any]:
    started = time.perf_counter()
    frames = select_frames(args, case["frames_dir"])
    film_dir = args.out_dir / "films" / f"{index:02d}_{safe_name(case['title'])}"
    print(f"[{index}] {case['title']} frames={len(frames)}", flush=True)
    if not frames:
        summary = summarize_case(case, frames, None, {"yonetmen": [], "yapimci": [], "senaryo_yazar": [], "oyuncular": [], "ignored": []}, {}, {}, [], [], {"error": "no frames"}, args.role_source, time.perf_counter() - started)
        write_case_outputs(film_dir, summary, {"error": "no frames"}, [], [])
        return summary

    reused_existing = False
    if args.reuse_existing and (film_dir / "stitched_lines.txt").exists() and (film_dir / "master_ocr_lines.txt").exists():
        reused_existing = True
        master = read_png(film_dir / "master.png")
        stitched_lines = (film_dir / "stitched_lines.txt").read_text(encoding="utf-8", errors="ignore").splitlines()
        master_lines = (film_dir / "master_ocr_lines.txt").read_text(encoding="utf-8", errors="ignore").splitlines()
        manifest = read_json(film_dir / "manifest.json") or {"composer": args.composer, "reused": True}
        manifest["reused_existing"] = True
    elif args.composer == "visual":
        assert comp is not None
        master, stitched_lines, manifest = build_visual_master(comp, frames)
        master_lines = []
    else:
        master, stitched_lines, manifest = build_hybrid_master(pl, frames)
        master_lines = []

    if master is not None and not reused_existing:
        write_png(film_dir / "master.png", master)
        master_lines = clean_lines(pl.read_pos(master))

    roles_stitched = parse_roles_from_lines(stitched_lines)
    roles_master = parse_roles_from_lines(master_lines)
    if args.role_source == "combined":
        roles = merge_roles(roles_stitched, roles_master)
    elif args.role_source == "master":
        roles = roles_master
    elif args.role_source == "fallback":
        roles = roles_stitched if official_names(roles_stitched) else roles_master
    else:
        roles = roles_stitched
    summary = summarize_case(case, frames, master, roles, roles_stitched, roles_master, stitched_lines, master_lines, manifest, args.role_source, time.perf_counter() - started)
    write_case_outputs(film_dir, summary, manifest, stitched_lines, master_lines)
    print(
        f"    -> {summary['status']} flags={','.join(summary['flags']) or '-'} "
        f"cast={summary['cast_count']} dir={summary['director_count']} "
        f"lines={summary['stitched_line_count']}/{summary['master_ocr_line_count']} "
        f"elapsed={summary['elapsed_sec']}s",
        flush=True,
    )
    return summary


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--film", action="append", default=[], help="Folder/title substring. Can be repeated.")
    parser.add_argument("--focus-scrolls", action="store_true", help="Retest the known scroll/problem films from the batch probe.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--min-frames", type=int, default=80)
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--start", type=int, default=None)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--composer", choices=("hybrid", "visual"), default="hybrid")
    parser.add_argument("--role-source", choices=("stitched", "master", "combined", "fallback"), default="stitched")
    parser.add_argument("--reuse-existing", action="store_true", help="Reuse existing per-film master/line artifacts and only refresh parsing/reporting.")
    parser.add_argument("--textmask", action="store_true", help="Enable MITAS_TEXTMASK for compose_hybrid.")
    parser.add_argument("--framegate", action="store_true", help="Enable MITAS_FRAMEGATE for compose_hybrid.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if args.textmask:
        os.environ["MITAS_TEXTMASK"] = "1"
    if args.framegate:
        os.environ["MITAS_FRAMEGATE"] = "1"

    args.out_dir.mkdir(parents=True, exist_ok=True)
    pl = load_module("pl_master_scroll_probe", PIPELINE100)
    comp = load_module("db_compose_master_scroll_probe", DB_COMPOSE) if args.composer == "visual" else None
    cases = discover_cases(args)
    if not cases:
        raise SystemExit("No cases found.")

    summaries: list[dict[str, Any]] = []
    started = time.perf_counter()
    for index, case in enumerate(cases, start=1):
        try:
            summaries.append(process_case(args, pl, comp, case, index))
        except Exception as exc:
            summary = {
                "status": "FAIL",
                "flags": ["EXCEPTION"],
                "title": case["title"],
                "year": case.get("year"),
                "folder": str(case["folder"]),
                "error": repr(exc),
                "elapsed_sec": round(time.perf_counter() - started, 2),
                "roles": {"yonetmen": [], "yapimci": [], "senaryo_yazar": [], "oyuncular": [], "ignored": []},
                "director_count": 0,
                "producer_count": 0,
                "writer_count": 0,
                "cast_count": 0,
                "ignored_count": 0,
                "stitched_line_count": 0,
                "master_ocr_line_count": 0,
                "role_source": args.role_source,
                "master_size": None,
            }
            summaries.append(summary)
            print(f"    -> FAIL exception={repr(exc)[:180]}", flush=True)
    write_reports(args.out_dir, summaries, cases)
    print(args.out_dir / "master_scroll_report.md")
    print(args.out_dir / "master_scroll_report.xlsx")
    print(args.out_dir / "master_scroll_report.json")
    print(f"elapsed={time.perf_counter() - started:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
