# -*- coding: utf-8 -*-
"""Parallel jenerik provenance/debug runner.

This script does not feed the production OCR/PDF decision.  It writes durable
evidence under Database/<film>/jenerik_debug:
  - oneocr raw/final line logs from the normal OCR output
  - GLM OCR reads from frames/cikis_jenerik
  - master PNG from frames/cikis_jenerik
  - shadow VL reads from frames/cikis_jenerik
  - line-level comparison report
"""
from __future__ import annotations

import argparse
from base64 import b64encode
from datetime import datetime, timezone
import difflib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import types
import urllib.request

import cv2
import numpy as np


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = Path(r"E:\MITAS")
HERE = PROJECT_ROOT / "scripts"
DCM_PATH = PROJECT_ROOT / "OCR-worktree" / "db_compose_master.py"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _read_text_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _norm(text: str) -> str:
    text = str(text or "").casefold()
    text = re.sub(r"[^0-9a-zçğıöşü\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _ratio(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _ratio_norm(na: str, nb: str) -> float:
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _best_match(line: str, candidates: list[str]) -> tuple[str, float]:
    best, score = "", 0.0
    for cand in candidates:
        r = _ratio(line, cand)
        if r > score:
            best, score = cand, r
    return best, score


def _build_match_index(candidates: list[str]) -> list[dict]:
    index: list[dict] = []
    seen: set[str] = set()
    for cand in candidates:
        norm = _norm(cand)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        index.append({
            "text": cand,
            "norm": norm,
            "len": len(norm),
            "tokens": {tok for tok in norm.split() if len(tok) > 1},
        })
    return index


def _best_match_indexed(line: str, index: list[dict], *, limit: int = 120) -> tuple[str, float]:
    norm = _norm(line)
    if not norm or not index:
        return "", 0.0

    tokens = {tok for tok in norm.split() if len(tok) > 1}
    n_len = len(norm)
    scored: list[tuple[float, dict]] = []
    for item in index:
        c_norm = item["norm"]
        c_len = item["len"]
        if c_norm == norm:
            return item["text"], 1.0

        contains = norm in c_norm or c_norm in norm
        shared = len(tokens & item["tokens"]) if tokens else 0
        length_ratio = c_len / max(1, n_len)
        if not contains and shared == 0 and (length_ratio < 0.45 or length_ratio > 2.2):
            continue
        if not contains and tokens and shared == 0:
            continue

        length_score = 1.0 - (abs(c_len - n_len) / max(c_len, n_len, 1))
        pre_score = (3.0 if contains else 0.0) + (2.0 * shared) + length_score
        scored.append((pre_score, item))

    if not scored:
        scored = [
            (1.0 - (abs(item["len"] - n_len) / max(item["len"], n_len, 1)), item)
            for item in index
        ]

    best, score = "", 0.0
    for _, item in sorted(scored, key=lambda x: x[0], reverse=True)[:limit]:
        r = _ratio_norm(norm, item["norm"])
        if r > score:
            best, score = item["text"], r
            if score >= 0.995:
                break
    return best, score


def _list_pool_frames(pool_dir: Path) -> list[Path]:
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

    def key(path: Path):
        nums = re.findall(r"\d+", path.stem)
        return (int(nums[-1]) if nums else -1, path.name.lower())

    if not pool_dir.is_dir():
        return []
    return sorted([p for p in pool_dir.iterdir() if p.suffix.lower() in exts], key=key)


def write_oneocr_debug(clip_dir: Path, ocr_out: Path | None, debug_root: Path) -> dict:
    one_dir = debug_root / "oneocr"
    if not ocr_out or not ocr_out.exists():
        summary = {"status": "missing_ocr_out", "ocr_out": str(ocr_out) if ocr_out else ""}
        _write_json(one_dir / "summary.json", summary)
        _write_jsonl(one_dir / "raw_reads.jsonl", [])
        _write_jsonl(one_dir / "normalization_log.jsonl", [])
        return summary

    sources = [
        ("raw_all", ocr_out / "ocr_raw_all.txt"),
        ("stitched_raw", ocr_out / "ocr_ham.txt"),
        ("final_kunye", ocr_out / "kunye.txt"),
    ]
    rows: list[dict] = []
    source_lines: dict[str, list[str]] = {}
    raw_detail_path = ocr_out / "ocr_raw_reads.jsonl"
    raw_detail_rows = _read_jsonl(raw_detail_path)

    for stage, path in sources:
        if stage == "raw_all" and raw_detail_rows:
            lines = [str(r.get("text") or "").strip() for r in raw_detail_rows if str(r.get("text") or "").strip()]
        else:
            lines = _read_text_lines(path)
        source_lines[stage] = lines
        if stage == "raw_all" and raw_detail_rows:
            for i, raw_row in enumerate(raw_detail_rows, start=1):
                line = str(raw_row.get("text") or "").strip()
                if not line:
                    continue
                row = {
                    "ts": _now(),
                    "engine": "oneocr",
                    "stage": "raw_frame",
                    "source_file": str(raw_detail_path),
                    "line_no": i,
                    "text": line,
                    "fold": raw_row.get("fold"),
                    "frame_file": raw_row.get("frame_file"),
                    "frame_path": raw_row.get("frame_path"),
                    "segment": raw_row.get("segment"),
                    "frame_index": raw_row.get("frame_index"),
                    "selected_rank": raw_row.get("selected_rank"),
                    "bbox": raw_row.get("bbox") or {},
                    "source_stage": raw_row.get("source_stage") or "oneocr_raw_frame",
                }
                rows.append(row)
        else:
            for i, line in enumerate(lines, start=1):
                rows.append({
                    "ts": _now(),
                    "engine": "oneocr",
                    "stage": stage,
                    "source_file": str(path),
                    "line_no": i,
                    "text": line,
                    "frame_file": None,
                    "note": "frame-level source unavailable; rerun _pipe_ocr.py to generate ocr_raw_reads.jsonl",
                })
    _write_jsonl(one_dir / "raw_reads.jsonl", rows)

    raw_candidates = source_lines.get("raw_all") or []
    stitched = source_lines.get("stitched_raw") or []
    final = source_lines.get("final_kunye") or []
    final_index = _build_match_index(final)
    raw_stitched_index = _build_match_index(raw_candidates + stitched)
    if raw_detail_rows:
        raw_source_records = [r for r in raw_detail_rows if str(r.get("text") or "").strip()]
    else:
        raw_source_records = [{"text": line} for line in raw_candidates]
    norm_rows: list[dict] = []
    for raw_source in raw_source_records:
        line = str(raw_source.get("text") or "").strip()
        if not line:
            continue
        best_final, score = _best_match_indexed(line, final_index)
        if score >= 0.985:
            action = "kept_exact"
        elif score >= 0.82:
            action = "fuzzy_matched_or_normalized"
        else:
            action = "deleted_by_clean_dedup_or_filter"
        norm_rows.append({
            "engine": "oneocr",
            "stage": "raw_to_final",
            "raw_text": line,
            "best_final_text": best_final,
            "fuzzy_score": round(score, 4),
            "action": action,
            "source_frame_file": raw_source.get("frame_file"),
            "source_frame_path": raw_source.get("frame_path"),
            "source_segment": raw_source.get("segment"),
            "source_frame_index": raw_source.get("frame_index"),
            "source_selected_rank": raw_source.get("selected_rank"),
            "source_bbox": raw_source.get("bbox") or {},
        })
    for final_line_no, line in enumerate(final, start=1):
        best_raw, score = _best_match_indexed(line, raw_stitched_index)
        if score < 0.82:
            norm_rows.append({
                "engine": "oneocr",
                "stage": "final_backtrace",
                "raw_text": None,
                "final_text": line,
                "final_line_no": final_line_no,
                "best_raw_text": best_raw,
                "fuzzy_score": round(score, 4),
                "action": "final_line_without_clear_raw_match",
            })
    _write_jsonl(one_dir / "normalization_log.jsonl", norm_rows)

    summary_path = ocr_out / "ocr_summary.json"
    ocr_summary = {}
    if summary_path.exists():
        try:
            ocr_summary = json.loads(summary_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            ocr_summary = {}
    summary = {
        "status": "ok",
        "ocr_out": str(ocr_out),
        "raw_all_lines": len(raw_candidates),
        "stitched_raw_lines": len(stitched),
        "final_kunye_lines": len(final),
        "raw_frame_provenance": bool(raw_detail_rows),
        "raw_frame_provenance_path": str(raw_detail_path) if raw_detail_rows else "",
        "ocr_summary": ocr_summary,
        "clip_dir": str(clip_dir),
    }
    _write_json(one_dir / "summary.json", summary)
    return summary


def _imread_unicode(path: Path) -> np.ndarray | None:
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _tile_image(img: np.ndarray, tile_h: int, overlap: int) -> list[tuple[int, int, np.ndarray]]:
    h = img.shape[0]
    if h <= tile_h:
        return [(0, h, img)]
    step = max(1, tile_h - overlap)
    out: list[tuple[int, int, np.ndarray]] = []
    y = 0
    while y < h:
        y2 = min(h, y + tile_h)
        if y2 - y < 20:
            break
        out.append((y, y2, img[y:y2, :]))
        if y2 >= h:
            break
        y += step
    return out


def _glm_read_tile(tile: np.ndarray, *, model: str, timeout: int, max_side: int, num_predict: int) -> str:
    if max_side > 0:
        h, w = tile.shape[:2]
        side = max(h, w)
        if side > max_side:
            scale = max_side / float(side)
            tile = cv2.resize(
                tile,
                (max(1, int(w * scale)), max(1, int(h * scale))),
                interpolation=cv2.INTER_AREA,
            )
    ok, buf = cv2.imencode(".png", tile)
    if not ok:
        raise RuntimeError("cv2.imencode failed")
    body = {
        "model": model,
        "prompt": "Read ALL visible credit text exactly as written, line by line. Output only text.",
        "images": [b64encode(buf.tobytes()).decode("ascii")],
        "stream": False,
        "options": {"temperature": 0, "num_predict": num_predict},
    }
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    return str(payload.get("response") or "").strip()


def run_glm_debug(pool_dir: Path, debug_root: Path) -> dict:
    out_dir = debug_root / "glm"
    frames = _list_pool_frames(pool_dir)
    max_frames = int(os.environ.get("MITAS_JENERIK_GLM_MAX_FRAMES", "16") or 16)
    tile_h = int(os.environ.get("MITAS_JENERIK_GLM_TILE", "1200") or 1200)
    overlap = int(os.environ.get("MITAS_JENERIK_GLM_OV", "100") or 100)
    timeout = int(os.environ.get("MITAS_JENERIK_GLM_TIMEOUT", "45") or 45)
    max_side = int(os.environ.get("MITAS_JENERIK_GLM_MAX_SIDE", "960") or 960)
    num_predict = int(os.environ.get("MITAS_JENERIK_GLM_NUM_PREDICT", "768") or 768)
    model = os.environ.get("MITAS_JENERIK_GLM_MODEL", "glm-ocr:latest")

    if not frames:
        summary = {"status": "empty_pool", "pool_dir": str(pool_dir), "model": model}
        _write_json(out_dir / "summary.json", summary)
        _write_jsonl(out_dir / "raw_reads.jsonl", [])
        return summary

    if len(frames) > max_frames:
        step = len(frames) / max_frames
        sample = [frames[int(i * step)] for i in range(max_frames)]
    else:
        sample = frames

    started = time.perf_counter()
    rows: list[dict] = []
    for sample_index, frame in enumerate(sample):
        img = _imread_unicode(frame)
        if img is None:
            rows.append({"engine": "glm", "status": "read_error", "frame_file": frame.name, "text": ""})
            continue
        for tile_index, (y1, y2, tile) in enumerate(_tile_image(img, tile_h, overlap)):
            try:
                text = _glm_read_tile(
                    tile,
                    model=model,
                    timeout=timeout,
                    max_side=max_side,
                    num_predict=num_predict,
                )
                status = "ok"
                error = None
            except Exception as exc:  # noqa: BLE001
                text = ""
                status = "error"
                error = f"{type(exc).__name__}: {exc}"
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            rows.append({
                "ts": _now(),
                "engine": "glm",
                "model": model,
                "status": status,
                "error": error,
                "sample_index": sample_index,
                "frame_file": frame.name,
                "frame_path": str(frame),
                "tile_index": tile_index,
                "tile_box": [0, y1, int(img.shape[1]), y2],
                "text": text,
                "lines": lines,
            })
    _write_jsonl(out_dir / "raw_reads.jsonl", rows)
    summary = {
        "status": "ok" if any(r.get("status") == "ok" for r in rows) else "error",
        "model": model,
        "pool_dir": str(pool_dir),
        "pool_frames": len(frames),
        "sampled_frames": len(sample),
        "tiles": len(rows),
        "lines": sum(len(r.get("lines") or []) for r in rows),
        "max_side": max_side,
        "num_predict": num_predict,
        "duration_sec": round(time.perf_counter() - started, 3),
    }
    _write_json(out_dir / "summary.json", summary)
    return summary


def _load_dcm():
    spec = importlib.util.spec_from_file_location("jenerik_debug_dcmaster", str(DCM_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {DCM_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_master_debug(pool_dir: Path, debug_root: Path) -> dict:
    out_dir = debug_root / "master_png"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_png = out_dir / "cikis_jenerik.png"
    frames = [str(p) for p in _list_pool_frames(pool_dir)]
    if not frames:
        if out_png.exists():
            out_png.unlink()
        manifest = {"status": "no_frames", "pool_dir": str(pool_dir), "frames": 0}
        _write_json(out_dir / "manifest.json", manifest)
        return manifest
    try:
        dc = _load_dcm()
        args = types.SimpleNamespace(
            mode="master", seg=None, hash_names=False, overwrite=True, flat_out=None,
            deinterlace=False, no_card_split=False, card_same_thr=6, card_min_hold=5,
            polarity="auto", no_dedup=False, luma_key=False, text_only=False, debug=False,
            flip=False, tht=22, min_hold=5, cut_resp=0.05,
        )
        first = dc.first_readable(frames)
        if first is None:
            raise RuntimeError("no readable frame")
        h, w = first.shape[:2]
        p = dc.derive_params(h, w, args)
        runs = dc.split_runs(frames, p, args)
        static_frames = sum(int(r[1]) - int(r[0]) + 1 for r in runs if r[2] == "S")
        scroll_frames = sum(int(r[1]) - int(r[0]) + 1 for r in runs if r[2] == "R")
        scroll_frac = scroll_frames / max(1, static_frames + scroll_frames)
        slit_master, _, _ = dc.compose_slit(frames, p, args)
        canon, mode = dc.select_master(slit_master)  # mosaic retired 2026-06-28 (slit-only)
        if canon is None:
            raise RuntimeError("composer returned no master")
        dc.wr(out_png, canon)
        manifest = {
            "status": "ok",
            "pool_dir": str(pool_dir),
            "output_png": str(out_png),
            "frames": len(frames),
            "mode": mode,
            "scroll_frac": round(scroll_frac, 4),
            "runs": [[int(a), int(b), str(t)] for a, b, t in runs],
            "size": [int(canon.shape[1]), int(canon.shape[0])],
        }
    except Exception as exc:  # noqa: BLE001
        manifest = {
            "status": "error",
            "pool_dir": str(pool_dir),
            "frames": len(frames),
            "error": f"{type(exc).__name__}: {exc}",
        }
        if out_png.exists():
            out_png.unlink()
    _write_json(out_dir / "manifest.json", manifest)
    return manifest


def run_vl_debug(clip_dir: Path, pool_dir: Path, debug_root: Path) -> dict:
    out_dir = debug_root / "vl"
    out_json = out_dir / "gemma_kunye.json"
    timeout = int(os.environ.get("MITAS_JENERIK_VL_TIMEOUT", "180") or 180)
    cmd = [
        sys.executable,
        str(HERE / "_pipe_shadow_vl.py"),
        "--clip", str(clip_dir),
        "--out", str(out_json),
        "--source-dir", str(pool_dir),
        "--debug-root", str(out_dir),
    ]
    started = time.perf_counter()
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            killed_tree = False
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                killed_tree = True
            else:
                proc.kill()
            try:
                stdout, stderr = proc.communicate(timeout=15)
            except Exception:
                stdout, stderr = "", ""
            summary = {
                "status": "error",
                "out": str(out_json),
                "source_dir": str(pool_dir),
                "error": f"TimeoutExpired: command timed out after {timeout} seconds",
                "pid": proc.pid,
                "killed_tree": killed_tree,
                "stdout_tail": (stdout or "")[-500:],
                "stderr_tail": (stderr or "")[-500:],
                "duration_sec": round(time.perf_counter() - started, 3),
            }
            _write_json(out_dir / "summary.json", summary)
            return summary
        status = "ok" if out_json.exists() else "empty"
        summary = {
            "status": status,
            "returncode": proc.returncode,
            "out": str(out_json),
            "source_dir": str(pool_dir),
            "stdout_tail": (stdout or "")[-500:],
            "stderr_tail": (stderr or "")[-500:],
            "duration_sec": round(time.perf_counter() - started, 3),
        }
    except Exception as exc:  # noqa: BLE001
        summary = {
            "status": "error",
            "out": str(out_json),
            "source_dir": str(pool_dir),
            "error": f"{type(exc).__name__}: {exc}",
            "duration_sec": round(time.perf_counter() - started, 3),
        }
    _write_json(out_dir / "summary.json", summary)
    return summary


def _collect_glm_records(debug_root: Path) -> list[dict]:
    rows: list[dict] = []
    p = debug_root / "glm" / "raw_reads.jsonl"
    if p.exists():
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            lines = obj.get("lines") or []
            if not lines and obj.get("text"):
                lines = [x.strip() for x in str(obj["text"]).splitlines() if x.strip()]
            for line in lines:
                rows.append({
                    "engine": "glm",
                    "text": str(line),
                    "frame_file": obj.get("frame_file"),
                    "frame_path": obj.get("frame_path"),
                    "tile_index": obj.get("tile_index"),
                    "tile_box": obj.get("tile_box"),
                    "model": obj.get("model"),
                })
    return rows


def _collect_vl_records(debug_root: Path) -> list[dict]:
    rows: list[dict] = []
    for path in [debug_root / "vl" / "raw_reads.jsonl", debug_root / "vl" / "gemma_kunye.json"]:
        if not path.exists():
            continue
        if path.suffix == ".jsonl":
            for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    obj = json.loads(ln)
                except Exception:
                    continue
                rec_lines = obj.get("lines") or []
                if obj.get("text"):
                    rec_lines.extend([x.strip() for x in str(obj["text"]).splitlines() if x.strip()])
                for line in rec_lines:
                    rows.append({
                        "engine": "vl",
                        "text": str(line),
                        "frame_file": obj.get("src_frame") or obj.get("frame_file"),
                        "frame_path": obj.get("file") or obj.get("frame_path"),
                        "tile_index": obj.get("tile_index"),
                        "tile_box": obj.get("tile_box"),
                        "model": obj.get("model"),
                    })
        else:
            try:
                obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                obj = {}
            for key in ("yonetmen", "oyuncular", "candidate_names"):
                for item in obj.get(key) or []:
                    rows.append({"engine": "vl", "text": str(item), "source_file": str(path), "field": key})
            for role in obj.get("diger_roller") or []:
                for item in role.get("isimler") or []:
                    rows.append({
                        "engine": "vl",
                        "text": str(item),
                        "source_file": str(path),
                        "field": role.get("rol") or "diger_roller",
                    })
    return rows


def _best_match_record(line: str, records: list[dict]) -> tuple[dict, float]:
    best: dict = {}
    score = 0.0
    for record in records:
        r = _ratio(line, str(record.get("text") or ""))
        if r > score:
            best, score = record, r
    return best, score


def _build_record_match_index(records: list[dict]) -> list[dict]:
    index: list[dict] = []
    seen: set[str] = set()
    for record in records:
        text = str(record.get("text") or "")
        norm = _norm(text)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        index.append({
            "record": record,
            "text": text,
            "norm": norm,
            "len": len(norm),
            "tokens": {tok for tok in norm.split() if len(tok) > 1},
        })
    return index


def _best_match_record_indexed(line: str, index: list[dict], *, limit: int = 120) -> tuple[dict, float]:
    norm = _norm(line)
    if not norm or not index:
        return {}, 0.0

    tokens = {tok for tok in norm.split() if len(tok) > 1}
    n_len = len(norm)
    scored: list[tuple[float, dict]] = []
    for item in index:
        c_norm = item["norm"]
        c_len = item["len"]
        if c_norm == norm:
            return item["record"], 1.0

        contains = norm in c_norm or c_norm in norm
        shared = len(tokens & item["tokens"]) if tokens else 0
        length_ratio = c_len / max(1, n_len)
        if not contains and shared == 0 and (length_ratio < 0.45 or length_ratio > 2.2):
            continue
        if not contains and tokens and shared == 0:
            continue

        length_score = 1.0 - (abs(c_len - n_len) / max(c_len, n_len, 1))
        pre_score = (3.0 if contains else 0.0) + (2.0 * shared) + length_score
        scored.append((pre_score, item))

    if not scored:
        scored = [
            (1.0 - (abs(item["len"] - n_len) / max(item["len"], n_len, 1)), item)
            for item in index
        ]

    best: dict = {}
    score = 0.0
    for _, item in sorted(scored, key=lambda x: x[0], reverse=True)[:limit]:
        r = _ratio_norm(norm, item["norm"])
        if r > score:
            best, score = item["record"], r
            if score >= 0.995:
                break
    return best, score


def write_compare(debug_root: Path) -> dict:
    one_final = _read_text_lines(debug_root / "oneocr" / "summary_missing_never.txt")
    oneocr_raw: list[str] = []
    oneocr_final: list[str] = []
    oneocr_raw_records: list[dict] = []
    oneocr_final_records: list[dict] = []
    one_path = debug_root / "oneocr" / "raw_reads.jsonl"
    if one_path.exists():
        for ln in one_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            if obj.get("stage") == "final_kunye":
                oneocr_final.append(obj.get("text") or "")
                oneocr_final_records.append(obj)
            else:
                oneocr_raw.append(obj.get("text") or "")
                oneocr_raw_records.append(obj)
    one_final = [x for x in oneocr_final if x]
    glm_records = _collect_glm_records(debug_root)
    vl_records = _collect_vl_records(debug_root)
    raw_index = _build_record_match_index(oneocr_raw_records)
    final_index = _build_record_match_index(oneocr_final_records)

    rows: list[dict] = []
    for engine, records in (("glm", glm_records), ("vl", vl_records)):
        for record in records:
            line = str(record.get("text") or "")
            best_raw_record, raw_score = _best_match_record_indexed(line, raw_index)
            best_final_record, final_score = _best_match_record_indexed(line, final_index)
            rows.append({
                "engine": engine,
                "text": line,
                "engine_frame_file": record.get("frame_file"),
                "engine_frame_path": record.get("frame_path"),
                "engine_tile_index": record.get("tile_index"),
                "engine_tile_box": record.get("tile_box"),
                "engine_model": record.get("model"),
                "best_oneocr_raw": best_raw_record.get("text") or "",
                "best_oneocr_raw_score": round(raw_score, 4),
                "best_oneocr_raw_frame_file": best_raw_record.get("frame_file"),
                "best_oneocr_raw_frame_path": best_raw_record.get("frame_path"),
                "best_oneocr_raw_segment": best_raw_record.get("segment"),
                "best_oneocr_raw_bbox": best_raw_record.get("bbox") or {},
                "best_oneocr_final": best_final_record.get("text") or "",
                "best_oneocr_final_score": round(final_score, 4),
                "decision": "same_or_fuzzy" if max(raw_score, final_score) >= 0.82 else "engine_only_or_disagreement",
            })
    _write_jsonl(debug_root / "compare" / "line_comparison.jsonl", rows)
    summary = {
        "oneocr_raw_lines": len(oneocr_raw),
        "oneocr_final_lines": len(one_final),
        "glm_lines": len(glm_records),
        "vl_lines": len(vl_records),
        "comparisons": len(rows),
        "engine_only_or_disagreement": sum(1 for r in rows if r["decision"] == "engine_only_or_disagreement"),
    }
    _write_json(debug_root / "compare" / "summary.json", summary)
    return summary


def write_analysis(debug_root: Path, summaries: dict) -> None:
    detector = {}
    det_path = debug_root / "detector" / "result.json"
    if det_path.exists():
        try:
            detector = json.loads(det_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            detector = {}
    lines = [
        "# Jenerik Paralel Debug Analizi",
        "",
        f"- Zaman: {_now()}",
        f"- Detector status: {detector.get('status', 'yok')}",
        f"- Detector start: {detector.get('start_file') or 'yok'}",
        f"- Detector first text: {detector.get('first_text_file') or 'yok'}",
        f"- Confidence: {detector.get('confidence', 'yok')}",
        "",
        "## OneOCR",
        f"- Normal havuzdan okudu. Final satır: {summaries.get('oneocr', {}).get('final_kunye_lines', 0)}",
        f"- Ham satır: {summaries.get('oneocr', {}).get('raw_all_lines', 0)}",
        f"- Frame provenance: {'var' if summaries.get('oneocr', {}).get('raw_frame_provenance') else 'yok'}",
        "",
        "## GLM",
        f"- Kaynak: frames/cikis_jenerik",
        f"- Durum: {summaries.get('glm', {}).get('status')}",
        f"- Satır: {summaries.get('glm', {}).get('lines', 0)}",
        "",
        "## Master PNG",
        f"- Kaynak: frames/cikis_jenerik",
        f"- Durum: {summaries.get('master', {}).get('status')}",
        f"- Çıktı: {summaries.get('master', {}).get('output_png', 'yok')}",
        "",
        "## VL",
        f"- Kaynak: frames/cikis_jenerik",
        f"- Durum: {summaries.get('vl', {}).get('status')}",
        f"- Çıktı: {summaries.get('vl', {}).get('out', 'yok')}",
        "",
        "## Karşılaştırma",
        f"- Karşılaştırılan satır: {summaries.get('compare', {}).get('comparisons', 0)}",
        f"- Ayrışan/engine-only satır: {summaries.get('compare', {}).get('engine_only_or_disagreement', 0)}",
        "",
        "Detay dosyaları:",
        "- oneocr/raw_reads.jsonl",
        "- oneocr/normalization_log.jsonl",
        "- glm/raw_reads.jsonl",
        "- vl/raw_reads.jsonl",
        "- master_png/manifest.json",
        "- compare/line_comparison.jsonl",
    ]
    (debug_root / "analysis_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MITAS parallel jenerik debug jobs")
    parser.add_argument("--clip", required=True, help="Database/<film> directory")
    parser.add_argument("--ocr-out", default="", help="Normal OneOCR output directory")
    parser.add_argument("--skip-glm", action="store_true")
    parser.add_argument("--skip-master", action="store_true")
    parser.add_argument("--skip-vl", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    clip_dir = Path(args.clip)
    debug_root = clip_dir / "jenerik_debug"
    pool_dir = clip_dir / "frames" / "cikis_jenerik"
    summaries: dict = {}
    try:
        summaries["oneocr"] = write_oneocr_debug(clip_dir, Path(args.ocr_out) if args.ocr_out else None, debug_root)
        summaries["glm"] = {"status": "skipped"} if args.skip_glm else run_glm_debug(pool_dir, debug_root)
        summaries["master"] = {"status": "skipped"} if args.skip_master else run_master_debug(pool_dir, debug_root)
        summaries["vl"] = {"status": "skipped"} if args.skip_vl else run_vl_debug(clip_dir, pool_dir, debug_root)
        summaries["compare"] = write_compare(debug_root)
        write_analysis(debug_root, summaries)
        _append_jsonl(debug_root / "events.jsonl", {"ts": _now(), "stage": "parallel_debug", "status": "ok", "summaries": summaries})
        print(json.dumps({"status": "ok", "debug_root": str(debug_root), "summaries": summaries}, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 - never break the pipeline
        err = {"ts": _now(), "stage": "parallel_debug", "status": "error", "error": f"{type(exc).__name__}: {exc}"}
        _append_jsonl(debug_root / "errors.jsonl", err)
        print(json.dumps(err, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    _code = main()
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os._exit(int(_code))
