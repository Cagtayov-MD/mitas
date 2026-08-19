#!/usr/bin/env python3
"""Bağımsız bbox -> crop -> 27B JSON -> deterministik derleyici deneyi.

Bu dosya Jordan üretim motoruna import edilmez ve onun ayarlarını değiştirmez.
Amaç crop-first fikrini, kayıp ihtimalini saklamadan ölçmektir:

1. PaddleOCR TextDetection yalnız poligon/bbox üretir; metnini kullanmaz.
2. Kaynak bbox genişletilip kanıt crop'u ve overlay'i yazılır.
3. Qwen3.6-27B yalnız crop'ları okur; llama.cpp JSON schema çıktıyı sınırlar.
4. Python derleyici sıralama ve exact tekrar elemeyi deterministik yapar.
5. İsteğe bağlı tam-frame transkriptiyle exact/near/missing karşılaştırılır.

Koşucunun tamamlanması `_TAMAM`; yarım/başarısız koşu ise `_TAMAM` içermez.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont


LLAMA = Path("/home/cagatay/Programlar/mitas/CagatayBox/llama.cpp/build/bin/llama-mtmd-cli")
MODEL = Path("/home/cagatay/Programlar/mitas/CagatayBox/models/Qwen3.6-27B-GGUF/Qwen3.6-27B-Q4_K_M.gguf")
MMPROJ = Path("/home/cagatay/Programlar/mitas/CagatayBox/models/Qwen3.6-27B-GGUF/mmproj-F16.gguf")

PROMPT_VERSION = "jordan-bbox-crop-27b/v1"
PROMPT = """You are a literal OCR engine. The input images are isolated crops from film-credit frames.

Return exactly one result for every input image, in the same order. Image numbering is 1-based.
- Read only characters visibly present inside that crop.
- Never correct, autocomplete, pluralize, translate, infer, or use film knowledge.
- Preserve spelling, punctuation, capitalization, and line breaks.
- If one character is unclear, use ? only for that character.
- If no text is visible, use status BLANK and an empty lines array.
- Do not merge information from different input images.
- Do not add headings, explanations, Markdown, or comments.

The response must conform exactly to the supplied JSON schema."""

PROTOCOL_LINES = {"[credits]", "[subtitles]", "[subtitle]", "[subtles]", "[subtites]"}
NATURAL_NUMBER = re.compile(r"(\d+)")


class ExperimentError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def natural_key(path: Path) -> list[Any]:
    return [int(piece) if piece.isdigit() else piece.casefold()
            for piece in NATURAL_NUMBER.split(path.name)]


def normalize_line(text: str) -> str:
    text = text.strip().casefold().replace("…", "")
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def append_jsonl(path: Path, value: Any) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def schema_for(count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["regions"],
        "properties": {
            "regions": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["image_index", "status", "lines"],
                    "properties": {
                        "image_index": {"type": "integer", "minimum": 1, "maximum": count},
                        "status": {"type": "string", "enum": ["READ", "BLANK", "UNCERTAIN"]},
                        "lines": {
                            "type": "array",
                            "minItems": 0,
                            "maxItems": 4,
                            "items": {"type": "string", "maxLength": 300},
                        },
                    },
                },
            }
        },
    }


def extract_json_object(output: str) -> dict[str, Any]:
    cleaned = output
    for marker in ("<|im_start|>assistant", "</think>"):
        if marker in cleaned:
            cleaned = cleaned.split(marker)[-1]
    decoder = json.JSONDecoder()
    candidates: list[tuple[int, dict[str, Any]]] = []
    for match in re.finditer(r"\{", cleaned):
        try:
            value, used = decoder.raw_decode(cleaned[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("regions"), list):
            candidates.append((used, value))
    if not candidates:
        raise ExperimentError("27B stdout icinde regions nesnesi bulunamadi")
    return max(candidates, key=lambda item: item[0])[1]


def validate_model_response(value: dict[str, Any], count: int) -> list[dict[str, Any]]:
    rows = value.get("regions")
    if not isinstance(rows, list) or len(rows) != count:
        raise ExperimentError(f"27B {count} yerine {len(rows) if isinstance(rows, list) else 'gecersiz'} kayit dondurdu")
    by_index: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ExperimentError("27B region kaydi nesne degil")
        index = row.get("image_index")
        status = row.get("status")
        lines = row.get("lines")
        if not isinstance(index, int) or not 1 <= index <= count or index in by_index:
            raise ExperimentError(f"27B image_index gecersiz/tekrar: {index!r}")
        if status not in {"READ", "BLANK", "UNCERTAIN"}:
            raise ExperimentError(f"27B status gecersiz: {status!r}")
        if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
            raise ExperimentError("27B lines string listesi degil")
        cleaned = [line.strip() for line in lines if line.strip()]
        if status == "BLANK" and cleaned:
            raise ExperimentError("BLANK region metin tasiyor")
        by_index[index] = {"image_index": index, "status": status, "lines": cleaned}
    if sorted(by_index) != list(range(1, count + 1)):
        raise ExperimentError("27B her input image icin tek kayit dondurmedi")
    return [by_index[index] for index in range(1, count + 1)]


def bbox_from_polygon(poly: np.ndarray, width: int, height: int,
                      pad_x_ratio: float, pad_y_ratio: float) -> tuple[list[int], list[int]]:
    points = np.asarray(poly, dtype=np.float64).reshape(-1, 2)
    raw = [int(np.floor(points[:, 0].min())), int(np.floor(points[:, 1].min())),
           int(np.ceil(points[:, 0].max())), int(np.ceil(points[:, 1].max()))]
    raw = [max(0, raw[0]), max(0, raw[1]), min(width, raw[2]), min(height, raw[3])]
    box_width = max(1, raw[2] - raw[0])
    box_height = max(1, raw[3] - raw[1])
    pad_x = max(6, round(box_width * pad_x_ratio))
    pad_y = max(4, round(box_height * pad_y_ratio))
    padded = [max(0, raw[0] - pad_x), max(0, raw[1] - pad_y),
              min(width, raw[2] + pad_x), min(height, raw[3] + pad_y)]
    return raw, padded


def make_contact_sheets(overlays: list[Path], output_dir: Path, columns: int = 3,
                        rows: int = 4) -> list[str]:
    result: list[str] = []
    per_page = columns * rows
    thumb_width, thumb_height = 360, 288
    for page_index in range(0, len(overlays), per_page):
        page_paths = overlays[page_index:page_index + per_page]
        canvas = Image.new("RGB", (columns * thumb_width, rows * thumb_height), "black")
        for index, path in enumerate(page_paths):
            with Image.open(path) as source:
                thumb = source.convert("RGB")
                thumb.thumbnail((thumb_width, thumb_height))
                x = (index % columns) * thumb_width + (thumb_width - thumb.width) // 2
                y = (index // columns) * thumb_height + (thumb_height - thumb.height) // 2
                canvas.paste(thumb, (x, y))
        name = f"overlay_contact_{page_index // per_page + 1:02d}.jpg"
        target = output_dir / name
        canvas.save(target, quality=92)
        result.append(name)
    return result


def detect_regions(frame_paths: list[Path], run_dir: Path, fps: float,
                   threshold: float, pad_x_ratio: float, pad_y_ratio: float,
                   detector_device: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    try:
        from paddleocr import TextDetection
    except Exception as exc:
        raise ExperimentError(
            "PaddleOCR TextDetection bulunamadi; bu dosyayi LeBron venv Python'i ile calistirin"
        ) from exc

    crop_dir = run_dir / "crops"
    overlay_dir = run_dir / "overlays"
    crop_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)
    # Detector GPU belleğini tutarsa 24 GB karttaki 27B yüklenemez. Deneyde iki
    # evre ardışık olduğundan varsayılan CPU'dur; bu ayrıca kaynak izolasyonunu
    # ölçülebilir ve deterministik kılar.
    detector_kwargs: dict[str, Any] = {"device": detector_device}
    if detector_device == "cpu":
        # Paddle 3.3/PIR + oneDNN bu modelde ArrayAttribute dönüşümünü
        # desteklemiyor; klasik CPU yürütücüsü kararlı çalışıyor.
        detector_kwargs["enable_mkldnn"] = False
    detector = TextDetection(**detector_kwargs)
    regions: list[dict[str, Any]] = []
    frames: list[dict[str, Any]] = []
    overlay_paths: list[Path] = []
    region_number = 0

    for frame_index, frame_path in enumerate(frame_paths, 1):
        with Image.open(frame_path) as opened:
            source = opened.convert("RGB")
        width, height = source.size
        prediction = detector.predict(str(frame_path))
        first = prediction[0] if prediction else {}
        polys = first.get("dt_polys", []) if hasattr(first, "get") else []
        scores = first.get("dt_scores", []) if hasattr(first, "get") else []
        overlay = source.copy()
        draw = ImageDraw.Draw(overlay)
        accepted = 0

        for candidate_index, poly in enumerate(polys):
            score = float(scores[candidate_index]) if candidate_index < len(scores) else None
            if score is not None and score < threshold:
                continue
            raw_bbox, bbox = bbox_from_polygon(np.asarray(poly), width, height,
                                               pad_x_ratio, pad_y_ratio)
            if raw_bbox[2] - raw_bbox[0] < 3 or raw_bbox[3] - raw_bbox[1] < 3:
                continue
            if (raw_bbox[2] - raw_bbox[0]) * (raw_bbox[3] - raw_bbox[1]) > width * height * 0.75:
                continue
            region_number += 1
            accepted += 1
            region_id = f"region-{region_number:06d}"
            crop_rel = Path("crops") / f"{region_id}__{frame_path.stem}.png"
            crop_path = run_dir / crop_rel
            crop = source.crop(tuple(bbox))
            crop.save(crop_path, format="PNG", optimize=False)
            edge_clipped = any((raw_bbox[0] == 0, raw_bbox[1] == 0,
                                raw_bbox[2] == width, raw_bbox[3] == height))
            regions.append({
                "region_id": region_id,
                "frame_sequence": frame_index,
                "source_time_s": round((frame_index - 1) / fps, 6),
                "frame_path": str(frame_path.resolve()),
                "frame_sha256": sha256_file(frame_path),
                "frame_width": width,
                "frame_height": height,
                "detector_polygon": np.asarray(poly).round(2).tolist(),
                "detector_score": round(score, 6) if score is not None else None,
                "raw_bbox_px_xyxy": raw_bbox,
                "bbox_px_xyxy": bbox,
                "edge_clipped": edge_clipped,
                "crop_path": crop_rel.as_posix(),
                "crop_width": crop.width,
                "crop_height": crop.height,
                "crop_sha256": sha256_file(crop_path),
            })
            draw.rectangle(tuple(bbox), outline=(0, 255, 0), width=2)
            draw.rectangle(tuple(raw_bbox), outline=(255, 64, 64), width=1)
            draw.text((bbox[0] + 2, max(0, bbox[1] - 12)), region_id.split("-")[-1],
                      fill=(255, 255, 0), font=ImageFont.load_default())

        overlay_rel = Path("overlays") / f"{frame_path.stem}.png"
        overlay_path = run_dir / overlay_rel
        overlay.save(overlay_path, format="PNG")
        overlay_paths.append(overlay_path)
        frame_record = {
            "frame_sequence": frame_index,
            "source_time_s": round((frame_index - 1) / fps, 6),
            "path": str(frame_path.resolve()),
            "sha256": sha256_file(frame_path),
            "width": width,
            "height": height,
            "detected_regions": accepted,
            "overlay_path": overlay_rel.as_posix(),
        }
        frames.append(frame_record)
        append_jsonl(run_dir / "events.jsonl", {"event": "frame_detected", **frame_record})
        print(f"[detector] {frame_index}/{len(frame_paths)} {frame_path.name}: {accepted} bbox", flush=True)

    try:
        detector.close()
    finally:
        del detector
        import gc
        gc.collect()
    contacts = make_contact_sheets(overlay_paths, run_dir)
    return regions, frames, contacts


def run_27b_batch(batch: list[dict[str, Any]], batch_number: int,
                  batch_total: int, run_dir: Path, timeout_s: int) -> list[dict[str, Any]]:
    schema = schema_for(len(batch))
    schema_text = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    prompt = (f"<|im_start|>user\n{PROMPT}\n\n"
              f"This batch contains exactly {len(batch)} crop images.<|im_end|>\n"
              "<|im_start|>assistant\n")
    max_tokens = max(1024, len(batch) * 80)
    command = [str(LLAMA), "-m", str(MODEL), "--mmproj", str(MMPROJ),
               "-p", prompt, "-ngl", "99", "-n", str(max_tokens),
               "--temp", "0", "--top-k", "1", "--top-p", "1",
               "--min-p", "0", "--repeat-penalty", "1", "--seed", "1",
               "--json-schema", schema_text]
    # Güncel llama.cpp aynı --image seçeneğinin tekrarında yalnız son yolu
    # kullanır. Çoklu görüntü tek, virgülle ayrılmış argüman olmalıdır.
    image_paths = [str((run_dir / region["crop_path"]).resolve()) for region in batch]
    if any("," in path for path in image_paths):
        raise ExperimentError("llama.cpp coklu-image protokolu virgullu yolu desteklemiyor")
    command.extend(["--image", ",".join(image_paths)])

    started = time.monotonic()
    completed = subprocess.run(command, capture_output=True, text=True,
                               timeout=timeout_s, check=False)
    elapsed = round(time.monotonic() - started, 3)
    raw_dir = run_dir / "raw_batches"
    raw_dir.mkdir(exist_ok=True)
    (raw_dir / f"batch_{batch_number:04d}.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (raw_dir / f"batch_{batch_number:04d}.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise ExperimentError(f"27B batch {batch_number} cikis kodu {completed.returncode}")
    parsed = extract_json_object(completed.stdout)
    rows = validate_model_response(parsed, len(batch))
    append_jsonl(run_dir / "events.jsonl", {
        "event": "model_batch_completed", "batch": batch_number,
        "batch_total": batch_total, "region_count": len(batch), "elapsed_s": elapsed,
        "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode("utf-8")).hexdigest(),
    })
    print(f"[27b] {batch_number}/{batch_total}: {len(batch)} crop, {elapsed:.1f} sn", flush=True)
    return rows


def read_all_regions(regions: list[dict[str, Any]], batch_size: int,
                     run_dir: Path, timeout_s: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    batches = [regions[index:index + batch_size]
               for index in range(0, len(regions), batch_size)]
    readings: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for batch_number, batch in enumerate(batches, 1):
        try:
            rows = run_27b_batch(batch, batch_number, len(batches), run_dir, timeout_s)
            for region, row in zip(batch, rows, strict=True):
                readings.append({
                    "region_id": region["region_id"],
                    "status": row["status"],
                    "lines": row["lines"],
                    "batch": batch_number,
                })
        except Exception as exc:
            failure = {"batch": batch_number, "region_ids": [r["region_id"] for r in batch],
                       "error_type": type(exc).__name__, "message": str(exc)}
            failures.append(failure)
            append_jsonl(run_dir / "events.jsonl", {"event": "model_batch_failed", **failure})
            print(f"[27b] {batch_number}/{len(batches)} BASARISIZ: {exc}", flush=True)
    return readings, failures


def spatial_rows(regions: list[dict[str, Any]], readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reading_map = {row["region_id"]: row for row in readings}
    by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for region in regions:
        reading = reading_map.get(region["region_id"])
        if not reading or not reading["lines"]:
            continue
        # Bir bbox normalde tek satirdir. Birden cok satir donerse bbox kaniti
        # korunur fakat satirlar ayni konuma baglanir; uydurma koordinat uretilmez.
        for line in reading["lines"]:
            if normalize_line(line) and normalize_line(line) not in PROTOCOL_LINES:
                by_frame[region["frame_sequence"]].append({**region, "text": line.strip()})

    rows: list[dict[str, Any]] = []
    for frame_sequence in sorted(by_frame):
        items = sorted(by_frame[frame_sequence],
                       key=lambda item: ((item["bbox_px_xyxy"][1] + item["bbox_px_xyxy"][3]) / 2,
                                         item["bbox_px_xyxy"][0]))
        clusters: list[list[dict[str, Any]]] = []
        for item in items:
            x0, y0, x1, y1 = item["raw_bbox_px_xyxy"]
            center = (y0 + y1) / 2
            height = max(1, y1 - y0)
            placed = False
            for cluster in clusters:
                centers = [(r["raw_bbox_px_xyxy"][1] + r["raw_bbox_px_xyxy"][3]) / 2
                           for r in cluster]
                heights = [max(1, r["raw_bbox_px_xyxy"][3] - r["raw_bbox_px_xyxy"][1])
                           for r in cluster]
                if abs(center - sum(centers) / len(centers)) <= 0.42 * max(height, max(heights)):
                    cluster.append(item)
                    placed = True
                    break
            if not placed:
                clusters.append([item])
        for cluster in clusters:
            cluster.sort(key=lambda item: item["raw_bbox_px_xyxy"][0])
            text = " ".join(item["text"] for item in cluster).strip()
            if not text:
                continue
            rows.append({
                "frame_sequence": frame_sequence,
                "source_time_s": cluster[0]["source_time_s"],
                "text": text,
                "normalized": normalize_line(text),
                "region_ids": [item["region_id"] for item in cluster],
                "bboxes_px_xyxy": [item["bbox_px_xyxy"] for item in cluster],
            })
    return rows


def exact_compile(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    first_by_normalized: dict[str, str] = {}
    for row in rows:
        normalized = row["normalized"]
        if not normalized:
            continue
        if normalized in first_by_normalized:
            duplicates.append({**row, "duplicate_of": first_by_normalized[normalized]})
            continue
        line_id = f"line-{len(kept) + 1:06d}"
        first_by_normalized[normalized] = line_id
        kept.append({"line_id": line_id, **row})
    return kept, duplicates


def baseline_lines(path: Path | None) -> list[str]:
    if path is None:
        return []
    lines: list[str] = []
    seen: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        normalized = normalize_line(line)
        if not line or line.startswith("#") or normalized in PROTOCOL_LINES or not normalized:
            continue
        if normalized not in seen:
            lines.append(line)
            seen.add(normalized)
    return lines


def compare_to_baseline(expected: list[str], compiled: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [(row["text"], row["normalized"], row["line_id"]) for row in compiled]
    results: list[dict[str, Any]] = []
    exact_count = near_count = 0
    matched_ids: set[str] = set()
    for expected_line in expected:
        normalized = normalize_line(expected_line)
        exact = next((item for item in candidates if item[1] == normalized), None)
        if exact:
            results.append({"baseline": expected_line, "status": "EXACT",
                            "crop_text": exact[0], "line_id": exact[2], "ratio": 1.0})
            exact_count += 1
            matched_ids.add(exact[2])
            continue
        ranked = sorted(((difflib.SequenceMatcher(None, normalized, item[1]).ratio(), item)
                         for item in candidates), reverse=True, key=lambda value: value[0])
        ratio, best = ranked[0] if ranked else (0.0, ("", "", ""))
        containment = (min(len(normalized), len(best[1])) >= 4 and
                       (normalized in best[1] or best[1] in normalized))
        if ratio >= 0.84 or containment:
            results.append({"baseline": expected_line, "status": "NEAR",
                            "crop_text": best[0], "line_id": best[2],
                            "ratio": round(ratio, 4)})
            near_count += 1
            matched_ids.add(best[2])
        else:
            results.append({"baseline": expected_line, "status": "MISSING",
                            "best_crop_text": best[0] or None,
                            "best_line_id": best[2] or None, "ratio": round(ratio, 4),
                            "interpretation": "DETECTOR_VEYA_CROP_OCR_KAYBI"})
    missing = [item for item in results if item["status"] == "MISSING"]
    extras = [{"line_id": row["line_id"], "text": row["text"]}
              for row in compiled if row["line_id"] not in matched_ids]
    denominator = len(expected)
    return {
        "baseline_line_count": denominator,
        "exact": exact_count,
        "near": near_count,
        "missing": len(missing),
        "recovery_rate_exact": round(exact_count / denominator, 4) if denominator else None,
        "recovery_rate_exact_or_near": round((exact_count + near_count) / denominator, 4)
        if denominator else None,
        "matches": results,
        "not_recovered": missing,
        "crop_only_extras": extras,
    }


def markdown_report(report: dict[str, Any]) -> str:
    detector = report["detector"]
    model = report["model_run"]
    comparison = report.get("baseline_comparison") or {}
    lines = [
        "# BBox → crop → 27B deneyi",
        "",
        f"- Durum: **{report['status']}**",
        f"- Frame: {detector['frame_count']}",
        f"- BBox/crop: {detector['region_count']}",
        f"- Sıfır bbox bulunan frame: {detector['zero_region_frame_count']}",
        f"- Kenara temas eden ham bbox: {detector['edge_clipped_region_count']}",
        f"- Başarılı 27B crop okuması: {model['read_region_count']}",
        f"- Boş crop: {model['blank_region_count']}",
        f"- Başarısız batch: {model['failed_batch_count']}",
        f"- Derlenmiş unique satır: {report['compiler']['unique_line_count']}",
    ]
    if comparison:
        lines.extend([
            "",
            "## Tam-frame 27B referansına göre",
            "",
            f"- Referans unique satır: {comparison['baseline_line_count']}",
            f"- Exact: {comparison['exact']}",
            f"- Near: {comparison['near']}",
            f"- Bulunamayan: {comparison['missing']}",
            f"- Exact + near kapsama: {comparison['recovery_rate_exact_or_near']}",
            "",
            "### Bulunamayan referans satırlar",
            "",
        ])
        missing = comparison["not_recovered"]
        lines.extend([f"- `{item['baseline']}` (en yakın: `{item.get('best_crop_text')}`; "
                      f"oran={item['ratio']})" for item in missing] or ["- Yok"])
    lines.extend([
        "",
        "## Kanıt yorumu",
        "",
        "Bir referans satırın bulunamaması tek başına detectorün kesin kaçırdığını kanıtlamaz; "
        "detector veya crop OCR aşamalarından biri kaybetmiş olabilir. Overlay ve crop artefaktları "
        "hangi aşamanın kaybettiğini insan gözüyle ayırmak için korunmuştur.",
        "",
    ])
    return "\n".join(lines)


def self_test() -> None:
    assert normalize_line("  STU—PHILLIPS… ") == "stu phillips"
    sample = '{"regions":[{"image_index":1,"status":"READ","lines":["A"]}]}'
    assert validate_model_response(extract_json_object("noise\n" + sample), 1)[0]["lines"] == ["A"]
    try:
        validate_model_response({"regions": [
            {"image_index": 1, "status": "READ", "lines": ["A"]},
            {"image_index": 1, "status": "READ", "lines": ["B"]},
        ]}, 2)
    except ExperimentError:
        pass
    else:
        raise AssertionError("tekrar image_index reddedilmedi")
    print("self-test OK")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--baseline-text", type=Path)
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--det-threshold", type=float, default=0.50)
    parser.add_argument("--detector-device", choices=("cpu", "gpu"), default="cpu")
    parser.add_argument("--pad-x-ratio", type=float, default=0.08)
    parser.add_argument("--pad-y-ratio", type=float, default=0.18)
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--timeout-s", type=int, default=600)
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--max-regions", type=int)
    parser.add_argument("--detector-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.frames_dir is None or args.output_dir is None:
        raise ExperimentError("--frames-dir ve --output-dir zorunlu")
    if args.fps <= 0 or not 0 <= args.det_threshold <= 1:
        raise ExperimentError("fps/det-threshold gecersiz")
    if args.batch_size < 1 or args.batch_size > 32:
        raise ExperimentError("batch-size 1..32 olmali")
    if args.output_dir.exists():
        raise ExperimentError(f"output-dir zaten var: {args.output_dir}")
    for required in (() if args.detector_only else (LLAMA, MODEL, MMPROJ)):
        if not required.is_file():
            raise ExperimentError(f"gerekli dosya yok: {required}")
    frame_paths = sorted(
        [path for path in args.frames_dir.iterdir()
         if path.is_file() and path.suffix.casefold() in {".jpg", ".jpeg", ".png"}],
        key=natural_key,
    )
    if args.max_frames:
        frame_paths = frame_paths[:args.max_frames]
    if not frame_paths:
        raise ExperimentError("hic frame bulunamadi")

    args.output_dir.mkdir(parents=True)
    started_wall = dt.datetime.now(dt.timezone.utc)
    started_mono = time.monotonic()
    append_jsonl(args.output_dir / "events.jsonl", {
        "event": "run_started", "at": started_wall.isoformat(),
        "frames_dir": str(args.frames_dir.resolve()), "frame_count": len(frame_paths),
        "prompt_version": PROMPT_VERSION,
    })

    regions, frames, contacts = detect_regions(
        frame_paths, args.output_dir, args.fps, args.det_threshold,
        args.pad_x_ratio, args.pad_y_ratio, args.detector_device,
    )
    detected_region_count = len(regions)
    if args.max_regions is not None:
        regions = regions[:args.max_regions]
    atomic_json(args.output_dir / "detections.json", {
        "schema": "jordan.bbox-detection-experiment/v1",
        "detector": "PaddleOCR TextDetection/PP-OCRv6_medium_det",
        "detector_text_used": False,
        "threshold": args.det_threshold,
        "padding": {"x_ratio": args.pad_x_ratio, "y_ratio": args.pad_y_ratio},
        "frames": frames,
        "regions": regions,
        "all_detected_region_count": detected_region_count,
        "model_input_region_count": len(regions),
    })

    readings: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    if not args.detector_only and regions:
        readings, failures = read_all_regions(regions, args.batch_size,
                                              args.output_dir, args.timeout_s)
    atomic_json(args.output_dir / "crop_readings.json", {
        "schema": "jordan.crop-reading-experiment/v1",
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(PROMPT.encode("utf-8")).hexdigest(),
        "model": str(MODEL), "mmproj": str(MMPROJ),
        "decoding": {"temperature": 0, "top_k": 1, "top_p": 1,
                     "min_p": 0, "repeat_penalty": 1, "seed": 1},
        "readings": readings, "batch_failures": failures,
    })

    rows = spatial_rows(regions, readings)
    compiled, duplicates = exact_compile(rows)
    atomic_json(args.output_dir / "compiled.json", {
        "schema": "jordan.crop-compiled-experiment/v1",
        "policy": "bbox-y-row+x-order; normalized-exact-dedup; no-fuzzy-correction",
        "lines": compiled, "exact_duplicates_removed": duplicates,
    })
    expected = baseline_lines(args.baseline_text)
    comparison = compare_to_baseline(expected, compiled) if expected else None
    if comparison is not None:
        atomic_json(args.output_dir / "baseline_comparison.json", comparison)

    read_count = sum(1 for row in readings if row["status"] in {"READ", "UNCERTAIN"}
                     and row["lines"])
    blank_count = sum(1 for row in readings if row["status"] == "BLANK" or not row["lines"])
    report = {
        "schema": "jordan.bbox-crop-27b-report/v1",
        "status": "DETECTOR_ONLY" if args.detector_only else ("PARTIAL" if failures else "SUCCEEDED"),
        "started_at": started_wall.isoformat(),
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "duration_s": round(time.monotonic() - started_mono, 3),
        "input": {"frames_dir": str(args.frames_dir.resolve()), "fps": args.fps,
                  "frame_hash_manifest_sha256": json_digest(
                      [{"path": f["path"], "sha256": f["sha256"]} for f in frames])},
        "detector": {
            "name": "PaddleOCR TextDetection/PP-OCRv6_medium_det",
            "text_used": False, "device": args.detector_device,
            "frame_count": len(frames),
            "region_count": detected_region_count,
            "model_input_region_count": len(regions),
            "zero_region_frame_count": sum(1 for frame in frames if frame["detected_regions"] == 0),
            "edge_clipped_region_count": sum(1 for region in regions if region["edge_clipped"]),
            "contact_sheets": contacts,
        },
        "model_run": {
            "model": str(MODEL), "batch_size": args.batch_size,
            "read_region_count": read_count, "blank_region_count": blank_count,
            "failed_batch_count": len(failures),
        },
        "compiler": {"spatial_row_count": len(rows), "unique_line_count": len(compiled),
                     "exact_duplicate_count": len(duplicates)},
        "baseline": str(args.baseline_text.resolve()) if args.baseline_text else None,
        "baseline_comparison": comparison,
        "limitations": [
            "MISSING sonucu detector veya crop OCR kaybini tek basina ayiramaz.",
            "Tam-frame 27B transkripti ground truth degildir; karsilastirma referansidir.",
            "BBox detector kaynaklidir; 27B koordinat uretmez.",
        ],
    }
    atomic_json(args.output_dir / "report.json", report)
    (args.output_dir / "REPORT.md").write_text(markdown_report(report), encoding="utf-8")
    (args.output_dir / "_TAMAM").write_text(
        json.dumps({"status": report["status"], "report_sha256": sha256_file(args.output_dir / "report.json")},
                   ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(args.output_dir),
                      "regions": detected_region_count, "compiled": len(compiled),
                      "comparison": comparison and {
                          "exact": comparison["exact"], "near": comparison["near"],
                          "missing": comparison["missing"],
                      }}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExperimentError as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        raise SystemExit(2)
