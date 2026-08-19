"""Nash grounded OCR kaniti.

Varsayilan yolda tek DeepSeek cevabi hem metni hem bbox'i uretir. Olculmus
kalite kapisi gecmezse Free OCR birincil kalabilir; o durumda grounding yalniz
kabul edilmis satirlarin kaynak karelerinde hedefli ikinci gecistir.
"""
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

from satir_topla import topla as _satir_topla

GROUNDING_PROMPT = "<image>\n<|grounding|>Convert the document to markdown."
_PATTERN = re.compile(r"<\|ref\|>(.*?)<\|/ref\|>\s*<\|det\|>(.*?)<\|/det\|>", re.S)
_BOLGE_ETIKETLERI = {
    "text", "title", "sub_title", "subtitle", "header", "footer",
    "paragraph", "list", "caption", "formula", "table", "image", "figure",
}


def enabled() -> bool:
    return os.environ.get("MITAS_OKUMA_V2", "").lower() in {"1", "true", "yes"}


def fold_exact(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value or "").casefold().split())


def parse_grounding(text: str) -> list[dict[str, Any]]:
    output = []
    eslesmeler = list(_PATTERN.finditer(text or ""))
    for indeks, match in enumerate(eslesmeler):
        ref = match.group(1).strip()
        # DeepSeek-OCR'in gercek ciktisi:
        #   <|ref|>text<|/ref|><|det|>bbox<|/det|>\nASIL METIN
        # Eski proof sondaji ise ASIL METNI ref icinde bekliyordu. Ikisini de
        # geriye uyumlu oku; generic bolge etiketini asla OCR satiri sayma.
        bitis = eslesmeler[indeks + 1].start() if indeks + 1 < len(eslesmeler) else len(text or "")
        kuyruk = (text or "")[match.end():bitis].strip()
        label = kuyruk if ref.casefold() in _BOLGE_ETIKETLERI and kuyruk else ref
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
        if label and valid and label.casefold() not in _BOLGE_ETIKETLERI:
            output.append({"label": label, "boxes_999": valid})
    return output


def grounding_lines(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cok satirli bir ref etiketini okuyucunun satir sozlesmesine ac.

    DeepSeek bazen tek bbox icinde birden cok metin satiri dondurur. Bbox'i
    her satira kopyalamak kusursuz satir lokalizasyonu iddiasi degildir; ayni
    gorunur bolgenin kanitidir ve packet bunu ref/det kaniti olarak saklar.
    """
    satirlar = []
    for item in items:
        for ham in str(item.get("label", "")).splitlines():
            label = ham.strip()
            if label:
                satirlar.append({"label": label,
                                 "boxes_999": [list(b) for b in item.get("boxes_999", [])]})
    return satirlar


def grounding_bicimi_var(text: str) -> bool:
    """Cevap en az bir resmi ref/det bolgesi tasiyor mu?"""
    return _PATTERN.search(text or "") is not None


def ground_pages(paths: list[Path], ask: Callable) -> tuple[dict[str, list[dict]], list[dict]]:
    pages, failures = {}, []
    for path in paths:
        try:
            pages[path.name] = parse_grounding(ask(path, GROUNDING_PROMPT))
        except Exception as exc:  # proof failure must not rewrite primary OCR truth
            failures.append({"asset": path.name, "error": f"{type(exc).__name__}: {exc}"[:300]})
            pages[path.name] = []
    return pages, failures


def build_packet(*, film_id: str, section: str, legacy: dict[str, Any],
                 selected_paths: list[Path], accepted: list[dict[str, Any]],
                 rejected: list[dict[str, Any]], grounding: dict[str, list[dict]],
                 grounding_failures: list[dict]) -> dict[str, Any]:
    identity = _identity()
    frame_meta = _frame_manifest()
    assets, asset_ids = [], {}
    for index, path in enumerate(selected_paths, start=1):
        if not path.is_file():
            continue
        width, height = _png_size(path)
        meta = frame_meta.get(path.name, {})
        asset_id = f"nash-frame-{index:06d}"
        asset_ids[path.name] = asset_id
        assets.append(_asset(asset_id, path, width, height, meta))

    candidates: dict[str, list[dict]] = defaultdict(list)
    for filename, items in grounding.items():
        for item in items:
            candidates[filename].append(item)

    lines, unread = [], []
    for order, row in enumerate(accepted):
        raw = str(row.get("text", ""))
        filename = str(row.get("kaynak", ""))
        item = _take_match(candidates, filename, raw)
        evidence = []
        asset_id = asset_ids.get(filename)
        asset = next((a for a in assets if a["asset_id"] == asset_id), None)
        if item and asset:
            for box in item["boxes_999"]:
                bbox = _pixel_box(box, int(asset["width"]), int(asset["height"]))
                if bbox:
                    evidence.append({"asset_id": asset_id, "bbox": bbox,
                                     "coordinate_space": "pixel_xyxy",
                                     "match": "exact" if item["label"] == raw else "fold_exact",
                                     "engine": item.get("engine"),
                                     "confidence": item.get("score"),
                                     "frame_sequence": asset.get("frame_sequence"),
                                     "source_time_s": asset.get("source_time_s")})
        if not evidence:
            unread.append({"line_id": f"line-{order:06d}", "reason": "GROUNDING_EXACT_MATCH_YOK",
                           "source_label": filename})
        lines.append({"line_id": f"line-{order:06d}", "order": order,
                      "raw_text": raw, "normalized_text": fold_exact(raw),
                      "source_label": filename, "evidence": evidence})
    # Kutu parcalari gorsel satira toplanir; parca bbox'lari 'bilesenler'de
    # korunur. Bkz. satir_topla.py — uc okuyucunun birimini esitler.
    lines = _satir_topla(lines)
    execution = "FAILED" if legacy.get("durum") == "ARIZA" else "SUCCEEDED"
    content = {"OKUNDU": "READ", "METIN_YOK": "NO_TEXT"}.get(
        legacy.get("durum"), "UNKNOWN")
    localized = [any(
        evidence.get("bbox") is not None
        and (asset := next((a for a in assets
                            if a["asset_id"] == evidence.get("asset_id")), None)) is not None
        and asset.get("frame_sequence") is not None
        and asset.get("source_time_s") is not None
        for evidence in line["evidence"]) for line in lines]
    proof_status = ("COMPLETE" if lines and all(localized)
                    else "PARTIAL" if any(localized)
                    else "NONE")
    source_inputs = [{"path": str(path.resolve()), "sha256": _sha(path),
                      "kind": "selected_frame"} for path in selected_paths if path.is_file()]
    legacy_kanit = legacy.get("kanit") or {}
    okuma_modu = str(legacy_kanit.get("okuma_modu", "grounded"))
    tek_gecis = okuma_modu == "grounded"
    if okuma_modu == "hybrid":
        birincil_istem = "paddle-ocr:no-prompt"
        if legacy_kanit.get("deepseek_fallback_enabled") is False:
            script_tani = legacy_kanit.get("paddle_script_fallback") or {}
            script_kabul = script_tani.get("kabul") or (
                script_tani if int(script_tani.get("kabul_satir_n", 0) or 0) > 0
                else {})
            script_calisti = bool(script_kabul)
            strateji = ("text-run-paddle-multiscript" if script_calisti
                        else "text-run-paddle-latin")
            surum = "nash-paddle/v5"
            script_adi = str(script_kabul.get("script", "arabic"))
            model_adi = ("PP-OCRv6-medium-det + latin-PP-OCRv5-mobile-rec"
                         + (f" + {script_adi}-PP-OCRv5-mobile-rec"
                            if script_calisti else ""))
        else:
            strateji = "text-run-paddle-first+deepseek-fallback"
            surum = "nash-hybrid/v4"
            model_adi = ("PP-OCRv6-medium-det + latin-PP-OCRv5-mobile-rec "
                         "+ deepseek-ocr-fallback")
    else:
        strateji = ("text-run-grounded-ocr" if tek_gecis
                    else "text-run-free-ocr+targeted-grounding")
        surum = "nash-grounded/v2" if tek_gecis else "nash-free-fallback/v2"
        birincil_istem = GROUNDING_PROMPT if tek_gecis else "<image>\nFree OCR."
        model_adi = "deepseek-ocr"
    model_olcum = legacy_kanit.get("model_olcum") or {}
    peakler = [x for x in (model_olcum.get("vram_peak_mb"),
                           legacy_kanit.get("paddle_peak_vram_mb"))
               if isinstance(x, (int, float))]
    return {
        "schema_version": "mitas.okuma/v2", "packet_id": f"pkt-{uuid.uuid4().hex}",
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "film": {"film_id": film_id}, "section": section, "identity": identity,
        "producer": {"id": "nash", "tower_version": legacy.get("motor_surumu"),
                     "strategy": strateji,
                     "strategy_version": surum,
                     "model": model_adi, "prompt_digest": _digest(birincil_istem),
                     "prompt_digests": {"primary": _digest(birincil_istem),
                                        "grounding": _digest(GROUNDING_PROMPT)},
                     "runtime": {"kind": "tower-cli", "python": sys.version.split()[0]},
                     "independence_group": "frame-reader"},
        "lineage": {"parent_tasks": [], "inputs": source_inputs},
        "status": {"execution": execution, "content": content, "proof": proof_status},
        "assets": assets, "lines": lines, "rejected_lines": rejected,
        "unread_regions": unread,
        "diagnostics": {"legacy_result": legacy, "grounding_failures": grounding_failures,
                        "bbox_assignment": "exact_or_fold_exact_only; fuzzy_forbidden"},
        "resource_usage": {"duration_s": legacy.get("sure_sn"),
                           "cpu_peak_mb": None, "ram_peak_mb": None,
                           "vram_peak_mb": max(peakler) if peakler else None,
                           "subprocess_exit_code": None},
    }


def fallback_packet(film_id: str, section: str, legacy: dict[str, Any],
                    error: Exception) -> dict[str, Any]:
    execution = "FAILED" if legacy.get("durum") == "ARIZA" else "SUCCEEDED"
    content = {"OKUNDU": "READ", "METIN_YOK": "NO_TEXT"}.get(
        legacy.get("durum"), "UNKNOWN")
    lines = [{"line_id": f"line-{index:06d}", "order": index,
              "raw_text": str(row.get("text", "")),
              "normalized_text": fold_exact(str(row.get("text", ""))),
              "source_label": row.get("kaynak"), "evidence": []}
             for index, row in enumerate(legacy.get("satirlar") or [])]
    return {"schema_version": "mitas.okuma/v2", "packet_id": f"pkt-{uuid.uuid4().hex}",
            "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "film": {"film_id": film_id}, "section": section, "identity": _identity(),
            "producer": {"id": "nash", "tower_version": legacy.get("motor_surumu"),
                         "strategy": "selected-frame-free-ocr; proof-failed",
                         "strategy_version": "nash-primary/v1+grounding-proof/v1",
                         "model": "deepseek-ocr", "prompt_digest": _digest(GROUNDING_PROMPT),
                         "prompt_digests": {"primary": _digest("<image>\nFree OCR."),
                                            "grounding": _digest(GROUNDING_PROMPT)},
                         "runtime": {"kind": "tower-cli", "python": sys.version.split()[0]},
                         "independence_group": "frame-reader"},
            "lineage": {"parent_tasks": [], "inputs": []},
            "status": {"execution": execution, "content": content, "proof": "NONE"},
            "assets": [], "lines": lines, "rejected_lines": [],
            "unread_regions": [{"reason": "PROOF_BUILD_FAILED", "scope": "all_lines"}],
            "diagnostics": {"legacy_result": legacy,
                            "proof_error": f"{type(error).__name__}: {error}"[:500]},
            "resource_usage": {"duration_s": legacy.get("sure_sn"),
                               "subprocess_exit_code": None}}


def _take_match(candidates: dict, filename: str, text: str):
    items = candidates.get(filename) or []
    for exact in (True, False):
        for index, item in enumerate(items):
            matches = item["label"] == text if exact else (
                fold_exact(item["label"]) == fold_exact(text))
            if matches:
                return items.pop(index)
    return None


def _pixel_box(box: list[float], width: int, height: int) -> list[int] | None:
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


def _asset(asset_id: str, path: Path, width: int, height: int, meta: dict) -> dict:
    return {"asset_id": asset_id, "path": str(path.resolve()),
            "origin_path": str(path.resolve()), "sha256": _sha(path),
            "mime_type": "image/png", "bytes": path.stat().st_size,
            "width": width, "height": height, "frame_sequence": meta.get("sequence"),
            "source_time_s": meta.get("source_time_s")}


def _png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"bozuk PNG: {path}")
    return struct.unpack(">II", header[16:24])


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
