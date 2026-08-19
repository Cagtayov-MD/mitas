"""LeBron additive grounding and master-to-source proof."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import struct
import sys
import unicodedata
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

GROUNDING_PROMPT = "<image>\n<|grounding|>Convert the document to markdown."
_PATTERN = re.compile(r"<\|ref\|>(.*?)<\|/ref\|>\s*<\|det\|>(.*?)<\|/det\|>", re.S)


def enabled() -> bool:
    return os.environ.get("MITAS_OKUMA_V2", "").lower() in {"1", "true", "yes"}


def fold_exact(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value or "").casefold().split())


def parse_grounding(text: str) -> list[dict[str, Any]]:
    output = []
    for match in _PATTERN.finditer(text or ""):
        label = match.group(1).strip()
        try:
            raw = ast.literal_eval(match.group(2).strip())
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            continue
        boxes = raw if isinstance(raw, (list, tuple)) else []
        if len(boxes) == 4 and all(isinstance(v, (int, float)) for v in boxes):
            boxes = [boxes]
        valid = []
        for box in boxes:
            if (isinstance(box, (list, tuple)) and len(box) == 4
                    and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                            for v in box)
                    and 0 <= box[0] < box[2] <= 999 and 0 <= box[1] < box[3] <= 999):
                valid.append([float(v) for v in box])
        if label and valid:
            output.append({"label": label, "boxes_999": valid})
    return output


def ground_bands(paths: list[Path], ask: Callable) -> tuple[dict[str, dict], list[dict]]:
    bands, failures = {}, []
    for path in paths:
        width, height = _png_size(path)
        try:
            items = parse_grounding(ask(path, GROUNDING_PROMPT))
        except Exception as exc:
            failures.append({"asset": path.name,
                             "error": f"{type(exc).__name__}: {exc}"[:300]})
            items = []
        bands[path.name] = {"width": width, "height": height, "items": items}
    return bands, failures


def build_packet(*, film_id: str, section: str, legacy: dict[str, Any],
                 master_path: Path | None, manifest: dict[str, Any] | None,
                 reading: dict[str, Any] | None, input_dir: Path,
                 output_dir: Path) -> dict[str, Any]:
    identity = _identity()
    manifest = manifest or {}
    reading = reading or {}
    layout_rows = [dict(row) for row in (manifest.get("layout_map") or [])]
    layout_path = output_dir / "layout_map.json"

    assets = []
    if master_path and master_path.is_file():
        width, height = _png_size(master_path)
        assets.append(_asset("lebron-master", master_path, "image/png", width, height))
    asset_by_source = {}
    frame_meta = _frame_manifest()
    for row in layout_rows:
        source_value = row.get("source_path")
        if not source_value or str(source_value).startswith("synthetic://"):
            continue
        source = Path(str(source_value))
        if not source.is_file():
            continue
        if str(source_value) not in asset_by_source:
            asset_id = f"lebron-source-{len(asset_by_source) + 1:06d}"
            width, height = _png_size(source)
            meta = frame_meta.get(source.name, {})
            record = _asset(asset_id, source, "image/png", width, height)
            record["frame_sequence"] = meta.get("sequence")
            record["source_time_s"] = meta.get("source_time_s")
            assets.append(record)
            asset_by_source[str(source_value)] = asset_id
        row["source_asset_id"] = asset_by_source[str(source_value)]
    if layout_rows:
        _atomic_json(layout_path, {
            "schema_version": "mitas.master-layout/v1", "film_id": film_id,
            "section": section, "coordinate_space": "pixel_rows_half_open",
            "master_size": manifest.get("size"), "rows": layout_rows})
        assets.append(_asset(
            "lebron-layout-map", layout_path, "application/json", None, None))

    grounding_candidates: dict[str, list[dict]] = defaultdict(list)
    for band_name, band in (reading.get("grounding") or {}).items():
        for item in band.get("items") or []:
            grounding_candidates[band_name].append(item)
    paddle_candidates: dict[str, list[dict]] = defaultdict(list)
    for band_name, band in (reading.get("paddle_satir_haritasi") or {}).items():
        for item in band.get("items") or []:
            paddle_candidates[band_name].append(dict(item))

    source_records = reading.get("satir_kaynaklari") or [
        {"text": text, "bant_index": None, "bant": None}
        for text in legacy.get("satirlar") or []]
    offsets = reading.get("bant_y0") or []
    lines, unread = [], []
    for order, source_record in enumerate(source_records):
        raw = str(source_record.get("text", ""))
        band_name = source_record.get("bant")
        band_index = source_record.get("bant_index")
        evidence = []
        reason = "SOURCE_FRAME_BBOX_YOK"
        paddle_band = (reading.get("paddle_satir_haritasi") or {}).get(band_name) or {}
        paddle_item, match = _take_unique_match(paddle_candidates, str(band_name), raw)
        if (paddle_item and master_path and master_path.is_file()
                and isinstance(band_index, int)):
            band_y0 = int(offsets[band_index]) if band_index < len(offsets) else 0
            local = _paddle_pixel_box(paddle_item.get("bbox"),
                                      int(paddle_band.get("width") or 0),
                                      int(paddle_band.get("height") or 0))
            if local:
                master_box = [local[0], local[1] + band_y0,
                              local[2], local[3] + band_y0]
                evidence.append({"asset_id": "lebron-master", "bbox": master_box,
                                 "coordinate_space": "pixel_xyxy", "kind": "master",
                                 "match": f"paddle_{match}",
                                 "paddle_confidence": paddle_item.get("confidence")})
                evidence.extend(_source_evidence(master_box, layout_rows, assets,
                                                 asset_by_source, frame_meta))
            else:
                reason = "PADDLE_BBOX_GECERSIZ"
        elif reading.get("paddle_satir_haritasi"):
            reason = "PADDLE_ESLESME_YOK" if match == "none" else "PADDLE_ESLESME_BELIRSIZ"
        else:
            # Açıkça satır-grounding yeteneği ilan eden eski test/arka uçler
            # için geriye dönük yol.  Görüntü-geneli ``image[[...]]`` bu
            # parserdan zaten geçemez ve asla satır kanıtı olmaz.
            band = (reading.get("grounding") or {}).get(band_name) or {}
            item = _take_match(grounding_candidates, str(band_name), raw)
            if item and master_path and master_path.is_file() and isinstance(band_index, int):
                band_y0 = int(offsets[band_index]) if band_index < len(offsets) else 0
                for box in item["boxes_999"]:
                    local = _pixel_box(box, int(band.get("width") or 0),
                                       int(band.get("height") or 0))
                    if not local:
                        continue
                    master_box = [local[0], local[1] + band_y0,
                                  local[2], local[3] + band_y0]
                    evidence.append({"asset_id": "lebron-master", "bbox": master_box,
                                     "coordinate_space": "pixel_xyxy", "kind": "master",
                                     "match": "exact" if item["label"] == raw else "fold_exact"})
                    evidence.extend(_source_evidence(master_box, layout_rows, assets,
                                                     asset_by_source, frame_meta))
        if not any(item.get("kind") == "source_frame" for item in evidence):
            unread.append({"line_id": f"line-{order:06d}",
                           "reason": reason,
                           "source_label": band_name})
        lines.append({"line_id": f"line-{order:06d}", "order": order,
                      "raw_text": raw, "normalized_text": fold_exact(raw),
                      "source_label": band_name, "evidence": evidence})

    execution = "FAILED" if legacy.get("durum") == "ARIZA" else "SUCCEEDED"
    content = {"OKUNDU": "READ", "METIN_YOK": "NO_TEXT"}.get(
        legacy.get("durum"), "UNKNOWN")
    asset_index = {asset["asset_id"]: asset for asset in assets}
    has_source = [any(
        item.get("kind") == "source_frame" and item.get("bbox") is not None
        and (asset := asset_index.get(item.get("asset_id"))) is not None
        and asset.get("frame_sequence") is not None
        and asset.get("source_time_s") is not None
        for item in line["evidence"]) for line in lines]
    proof_status = ("COMPLETE" if lines and all(has_source)
                    else "PARTIAL" if any(has_source) else "NONE")
    source_inputs = []
    for path in sorted(input_dir.glob("*.png")) if input_dir.is_dir() else []:
        source_inputs.append({"path": str(path.resolve()), "sha256": _sha(path),
                              "kind": "boundary_selected_frame"})
    return {
        "schema_version": "mitas.okuma/v2", "packet_id": f"pkt-{uuid.uuid4().hex}",
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "film": {"film_id": film_id}, "section": section, "identity": identity,
        "producer": {"id": "lebron", "tower_version": legacy.get("motor_surumu"),
                     "strategy": "lebron-master-free-ocr+paddle-exact-proof",
                     "strategy_version": "lebron/v2+private-ollama/v1+paddle-exact-proof/v1",
                     "model": "deepseek-ocr", "prompt_digest": _digest(GROUNDING_PROMPT),
                     "prompt_digests": {"primary": _digest("<image>\nFree OCR."),
                                        "grounding": _digest(GROUNDING_PROMPT)},
                     "runtime": {"kind": "tower-cli", "python": sys.version.split()[0]},
                     "independence_group": "master-reader"},
        "lineage": {"parent_tasks": [], "inputs": source_inputs},
        "status": {"execution": execution, "content": content, "proof": proof_status},
        "assets": assets, "lines": lines,
        "rejected_lines": reading.get("elenen") or [], "unread_regions": unread,
        "diagnostics": {"legacy_result": legacy,
                        "grounding_failures": reading.get("grounding_failures") or [],
                        "grounding_unsupported": reading.get("grounding_unsupported"),
                        "proof_strategy": reading.get("proof_strategy", "paddle_exact"),
                        "layout_map_version": manifest.get("layout_map_version"),
                        "layout_runs": len(layout_rows),
                        "bbox_assignment": "exact_or_fold_exact_only; fuzzy_forbidden"},
        "resource_usage": {"duration_s": legacy.get("sure_sn"),
                           "cpu_peak_mb": None, "ram_peak_mb": None,
                           "vram_peak_mb": None, "subprocess_exit_code": None},
    }


def fallback_packet(film_id: str, section: str, legacy: dict[str, Any],
                    error: Exception) -> dict[str, Any]:
    execution = "FAILED" if legacy.get("durum") == "ARIZA" else "SUCCEEDED"
    content = {"OKUNDU": "READ", "METIN_YOK": "NO_TEXT"}.get(
        legacy.get("durum"), "UNKNOWN")
    lines = [{"line_id": f"line-{index:06d}", "order": index,
              "raw_text": str(text), "normalized_text": fold_exact(str(text)),
              "source_label": None, "evidence": []}
             for index, text in enumerate(legacy.get("satirlar") or [])]
    return {"schema_version": "mitas.okuma/v2", "packet_id": f"pkt-{uuid.uuid4().hex}",
            "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "film": {"film_id": film_id}, "section": section, "identity": _identity(),
            "producer": {"id": "lebron", "tower_version": legacy.get("motor_surumu"),
                         "strategy": "lebron-master-free-ocr; proof-failed",
                         "strategy_version": "lebron/v2+private-ollama/v1+grounding-proof/v1",
                         "model": "deepseek-ocr", "prompt_digest": _digest(GROUNDING_PROMPT),
                         "prompt_digests": {"primary": _digest("<image>\nFree OCR."),
                                            "grounding": _digest(GROUNDING_PROMPT)},
                         "runtime": {"kind": "tower-cli", "python": sys.version.split()[0]},
                         "independence_group": "master-reader"},
            "lineage": {"parent_tasks": [], "inputs": []},
            "status": {"execution": execution, "content": content, "proof": "NONE"},
            "assets": [], "lines": lines, "rejected_lines": [],
            "unread_regions": [{"reason": "PROOF_BUILD_FAILED", "scope": "all_lines"}],
            "diagnostics": {"legacy_result": legacy,
                            "proof_error": f"{type(error).__name__}: {error}"[:500]},
            "resource_usage": {"duration_s": legacy.get("sure_sn"),
                               "subprocess_exit_code": None}}


def _source_evidence(master_box: list[int], rows: list[dict], assets: list[dict],
                     asset_by_source: dict[str, str], frame_meta: dict[str, dict]) -> list[dict]:
    output = []
    for row in rows:
        y0, y1 = max(master_box[1], int(row["master_y0"])), min(
            master_box[3], int(row["master_y1"]))
        source_value = row.get("source_path")
        if y0 >= y1 or not source_value or str(source_value).startswith("synthetic://"):
            continue
        source = Path(source_value)
        if not source.is_file():
            continue
        if source_value not in asset_by_source:
            asset_id = f"lebron-source-{len(asset_by_source) + 1:06d}"
            width, height = _png_size(source)
            meta = frame_meta.get(source.name, {})
            record = _asset(asset_id, source, "image/png", width, height)
            record["frame_sequence"] = meta.get("sequence")
            record["source_time_s"] = meta.get("source_time_s")
            assets.append(record)
            asset_by_source[source_value] = asset_id
        source_y0 = int(row["source_y0"]) + (y0 - int(row["master_y0"]))
        source_y1 = source_y0 + (y1 - y0)
        output.append({"asset_id": asset_by_source[source_value],
                       "bbox": [master_box[0], source_y0, master_box[2], source_y1],
                       "coordinate_space": "pixel_xyxy", "kind": "source_frame",
                       "master_y_range": [y0, y1],
                       "frame_sequence": frame_meta.get(source.name, {}).get("sequence"),
                       "source_time_s": frame_meta.get(source.name, {}).get("source_time_s")})
    return output


def _take_match(candidates: dict, band: str, text: str):
    items = candidates.get(band) or []
    for exact in (True, False):
        for index, item in enumerate(items):
            matches = item["label"] == text if exact else (
                fold_exact(item["label"]) == fold_exact(text))
            if matches:
                return items.pop(index)
    return None


def _take_unique_match(candidates: dict, band: str, text: str):
    """Tek açık Paddle satırını tüket; çoklu/fuzzy adayda kanıt üretme."""
    items = candidates.get(band) or []
    exact = [index for index, item in enumerate(items)
             if str(item.get("text", "")) == text]
    if len(exact) == 1:
        return items.pop(exact[0]), "exact"
    if len(exact) > 1:
        return None, "ambiguous"
    folded = [index for index, item in enumerate(items)
              if fold_exact(str(item.get("text", ""))) == fold_exact(text)]
    if len(folded) == 1:
        return items.pop(folded[0]), "fold_exact"
    return None, "ambiguous" if folded else "none"


def _paddle_pixel_box(box, width: int, height: int) -> list[int] | None:
    if (not isinstance(box, (list, tuple)) or len(box) != 4
            or not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                       for value in box)
            or width <= 0 or height <= 0):
        return None
    values = [int(box[0]), int(box[1]), int(box[2]), int(box[3])]
    values = [max(0, min(values[0], width - 1)), max(0, min(values[1], height - 1)),
              max(1, min(values[2], width)), max(1, min(values[3], height))]
    return values if values[0] < values[2] and values[1] < values[3] else None


def _pixel_box(box: list[float], width: int, height: int) -> list[int] | None:
    if width <= 0 or height <= 0:
        return None
    values = [round(box[0] * width / 999), round(box[1] * height / 999),
              round(box[2] * width / 999), round(box[3] * height / 999)]
    values = [max(0, min(values[0], width - 1)), max(0, min(values[1], height - 1)),
              max(1, min(values[2], width)), max(1, min(values[3], height))]
    return values if values[0] < values[2] and values[1] < values[3] else None


def _identity() -> dict[str, str]:
    return {"run_id": os.environ.get("MITAS_SHERIFF_RUN_ID", "standalone"),
            "task_id": os.environ.get("MITAS_SHERIFF_TASK_ID", "standalone"),
            "attempt_id": os.environ.get("MITAS_SHERIFF_ATTEMPT_ID", "standalone")}


def _frame_manifest() -> dict[str, dict]:
    path = Path(os.environ.get("MITAS_SHERIFF_FRAME_MANIFEST", ""))
    if not path.is_file():
        return {}
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            rows[row["filename"]] = row
        except (json.JSONDecodeError, KeyError):
            continue
    return rows


def _asset(asset_id: str, path: Path, mime: str, width, height) -> dict:
    return {"asset_id": asset_id, "path": str(path.resolve()),
            "origin_path": str(path.resolve()), "sha256": _sha(path),
            "mime_type": mime, "bytes": path.stat().st_size,
            "width": width, "height": height, "frame_sequence": None,
            "source_time_s": None}


def _png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"bozuk PNG: {path}")
    return struct.unpack(">II", header[16:24])


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temporary, path)
