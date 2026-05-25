"""Experimental OCR strategies for credits, KJ, and moving text.

This module is intentionally separate from ``core.pipelines.ocr.simple``.
It is a research/measurement runner: it extracts a short segment, runs the
available OCR engines, compares frame-wise OCR with temporal grouping, measures
text-layer motion, and builds a first-pass de-scroll canvas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import types
from time import perf_counter
from typing import Any, Callable, Protocol


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_VERSION = "ocr_credit_experiment_v0_1"
DEFAULT_ENGINES = ["paddle", "oneocr", "tesseract"]
OCR_MODELS_ROOT = PROJECT_ROOT / "models" / "ocr"
PADDLE_OFFICIAL_MODELS_ROOT = OCR_MODELS_ROOT / "paddle" / "official_models"
PADDLE_DETECTION_MODEL_NAME = "PP-OCRv5_server_det"
PADDLE_RECOGNITION_MODEL_NAME = "latin_PP-OCRv5_mobile_rec"
TESSERACT_TESSDATA_DIR = OCR_MODELS_ROOT / "tesseract" / "tessdata"
DEFAULT_SCROLL_FPS = 6.0
DEFAULT_KJ_FPS = 2.0
DEFAULT_STATIC_FPS = 1.0
DEFAULT_UNKNOWN_FPS = 2.0
NORMALIZATION_POLICY = {
    "case": "upper",
    "diacritics": "Turkish/Latin OCR confusions are folded before grouping and scoring",
    "folds": {"İ": "I", "İ": "I", "ı": "I", "i": "I", "Ş": "S", "ş": "S", "Ğ": "G", "ğ": "G", "Ü": "U", "ü": "U", "Ö": "O", "ö": "O", "Ç": "C", "ç": "C"},
    "punctuation": "non-alphanumeric characters collapse to single spaces",
}


class OcrEngine(Protocol):
    name: str

    def recognize(self, image_path: Path, *, strategy: str, timestamp_seconds: float | None = None) -> list[dict[str, Any]]:
        ...


@dataclass(frozen=True)
class CreditExperimentItem:
    id: str
    path: Path
    kind: str
    layout_type: str
    motion_type: str
    expected_language: str | None
    start_seconds: float
    end_seconds: float
    fps: float | None
    roi: tuple[int, int, int, int] | None
    column_count: int
    ground_truth: tuple[str, ...]
    notes: str
    scroll_auto_detect: bool = False
    # Faz 2: ham manifest dict'i saklıyoruz (opening_window_min vb. yeni
    # profil alanları load_manifest'in dataclass'ına eklemeden geçer).
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CreditExperimentManifest:
    items: list[CreditExperimentItem]


@dataclass(frozen=True)
class CreditExperimentRunResult:
    output_dir: Path
    summary_path: Path
    report_path: Path
    item_dirs: list[Path]
    summary: dict[str, Any]


EngineFactory = Callable[[], OcrEngine]


def load_manifest(path: str | Path) -> CreditExperimentManifest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("Manifest must contain a non-empty 'items' list")

    items: list[CreditExperimentItem] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            raise ValueError(f"Manifest item {index} must be an object")
        item_id = _require_nonempty_string(raw, "id", index)
        if item_id in seen_ids:
            raise ValueError(f"Duplicate manifest item id: {item_id}")
        seen_ids.add(item_id)

        # Faz 2: start/end_seconds zorunlu yalnız LEGACY `kind: end_credits` için.
        # `kind: film_credits` (+ stub kinds) duration'ı ffprobe ile çalışma anında
        # alır ve pencereyi opening/closing_window_min'den türetir.
        item_kind = str(raw.get("kind") or "unknown")
        if item_kind == "end_credits" or "start_seconds" in raw or "end_seconds" in raw:
            start = _require_number(raw, "start_seconds", index)
            end = _require_number(raw, "end_seconds", index)
            if start < 0:
                raise ValueError(f"Manifest item {item_id}: start_seconds must be >= 0")
            if end <= start:
                raise ValueError(f"Manifest item {item_id}: end_seconds must be greater than start_seconds")
            start_value = float(start)
            end_value = float(end)
        else:
            # Yeni profiller: pencere runtime'da hesaplanacak; placeholder.
            start_value = 0.0
            end_value = 0.0

        items.append(
            CreditExperimentItem(
                id=item_id,
                path=Path(_require_nonempty_string(raw, "path", index)),
                kind=item_kind,
                layout_type=str(raw.get("layout_type") or raw.get("kind") or "unknown"),
                motion_type=str(raw.get("motion_type") or "unknown"),
                expected_language=_optional_string(raw.get("expected_language") or raw.get("language")),
                start_seconds=start_value,
                end_seconds=end_value,
                fps=_optional_positive_number(raw.get("fps"), item_id, "fps"),
                roi=_parse_roi(raw.get("roi"), item_id),
                column_count=_parse_column_count(raw.get("column_count") or raw.get("columns"), item_id),
                ground_truth=tuple(_parse_ground_truth(raw, Path(path).parent, item_id)),
                notes=str(raw.get("notes") or ""),
                scroll_auto_detect=_optional_bool(raw.get("scroll_auto_detect"), default=False),
                raw=dict(raw),
            )
        )
    return CreditExperimentManifest(items=items)


def run_credit_experiment(
    manifest_path: str | Path,
    *,
    output_dir: str | Path,
    engines: list[str] | None = None,
    fps: float | None = None,
    max_frames: int | None = None,
    preprocess_mode: str = "auto",
    allow_model_download: bool = False,
    ffmpeg_executable: str | None = None,
    engine_factories: dict[str, EngineFactory] | None = None,
) -> CreditExperimentRunResult:
    started_at = datetime.now(timezone.utc)
    started = perf_counter()
    manifest = load_manifest(manifest_path)
    run_dir = Path(output_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    preprocess_mode = _normalize_preprocess_mode(preprocess_mode)

    requested_engines = _normalize_engine_names(DEFAULT_ENGINES if engines is None else engines)
    if allow_model_download:
        os.environ["MITAS_OCR_ALLOW_MODEL_DOWNLOAD"] = "1"
    factories = engine_factories or build_default_engine_factories(requested_engines)
    active_engines, engine_status = _build_engines(requested_engines, factories)

    item_summaries: list[dict[str, Any]] = []
    item_dirs: list[Path] = []
    for item in manifest.items:
        item_dir = run_dir / "items" / item.id
        item_dirs.append(item_dir)
        item_summary = _run_item(
            item,
            item_dir=item_dir,
            engines=active_engines,
            fps=fps,
            max_frames=max_frames,
            preprocess_mode=preprocess_mode,
            ffmpeg_executable=ffmpeg_executable,
        )
        item_summaries.append(item_summary)

    summary = {
        "experiment_version": EXPERIMENT_VERSION,
        "manifest_path": str(Path(manifest_path)),
        "output_dir": str(run_dir),
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "runtime_sec": round(perf_counter() - started, 3),
        "requested_engines": requested_engines,
        "allow_model_download": allow_model_download,
        "preprocess_mode": preprocess_mode,
        "normalization_policy": NORMALIZATION_POLICY,
        "engine_status": engine_status,
        "items": item_summaries,
        "category_rollups": _category_rollups(item_summaries),
    }
    summary_path = run_dir / "run_summary.json"
    report_path = run_dir / "run_report.md"
    _write_json(summary_path, summary)
    report_path.write_text(_build_run_report(summary), encoding="utf-8")
    return CreditExperimentRunResult(
        output_dir=run_dir,
        summary_path=summary_path,
        report_path=report_path,
        item_dirs=item_dirs,
        summary=summary,
    )


def build_default_engine_factories(engine_names: list[str]) -> dict[str, EngineFactory]:
    factories: dict[str, EngineFactory] = {}
    for name in engine_names:
        if name == "paddle":
            factories[name] = PaddleOcrEngine
        elif name == "oneocr":
            factories[name] = OneOcrEngine
        elif name == "tesseract":
            factories[name] = TesseractUnavailableEngine
    return factories


def normalize_text(text: str) -> str:
    text = text.strip()
    for old, new in NORMALIZATION_POLICY["folds"].items():
        text = text.replace(old, new)
    text = text.upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def group_temporal_records(
    records: list[dict[str, Any]],
    *,
    similarity_threshold: float = 0.82,
    max_time_gap_seconds: float = 2.0,
    max_center_distance_px: float = 180.0,
) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    enriched: list[dict[str, Any]] = []
    sorted_records = sorted(records, key=lambda item: (str(item.get("engine") or ""), float(item.get("timestamp_seconds") or 0.0)))

    for record in sorted_records:
        text = str(record.get("text") or "")
        normalized = str(record.get("normalized_text") or normalize_text(text))
        enriched_record = dict(record)
        enriched_record["normalized_text"] = normalized
        if not normalized:
            enriched_record["line_group_id"] = None
            enriched.append(enriched_record)
            continue

        best_group: dict[str, Any] | None = None
        best_score = 0.0
        for group in groups:
            if group["engine"] != enriched_record.get("engine"):
                continue
            if abs(float(enriched_record.get("timestamp_seconds") or 0.0) - group["last_timestamp_seconds"]) > max_time_gap_seconds:
                continue
            if not _bbox_centers_close(enriched_record.get("bbox"), group.get("last_bbox"), max_center_distance_px):
                continue
            score = SequenceMatcher(None, normalized, group["winner_normalized_text"]).ratio()
            if score >= similarity_threshold and score > best_score:
                best_group = group
                best_score = score

        if best_group is None:
            group_id = f"lg_{len(groups) + 1:04d}"
            best_group = {
                "line_group_id": group_id,
                "engine": enriched_record.get("engine"),
                "records": [],
                "texts": {},
                "winner_text": text,
                "winner_normalized_text": normalized,
                "first_timestamp_seconds": float(enriched_record.get("timestamp_seconds") or 0.0),
                "last_timestamp_seconds": float(enriched_record.get("timestamp_seconds") or 0.0),
                "last_bbox": enriched_record.get("bbox"),
                "mean_confidence": None,
                "stable_count": 0,
            }
            groups.append(best_group)

        enriched_record["line_group_id"] = best_group["line_group_id"]
        best_group["records"].append(enriched_record)
        best_group["texts"][normalized] = best_group["texts"].get(normalized, 0) + 1
        best_group["last_timestamp_seconds"] = float(enriched_record.get("timestamp_seconds") or best_group["last_timestamp_seconds"])
        best_group["last_bbox"] = enriched_record.get("bbox")
        _refresh_group_winner(best_group)
        enriched.append(enriched_record)

    compact_groups = []
    for group in groups:
        confidences = [float(item["confidence"]) for item in group["records"] if _is_number(item.get("confidence"))]
        compact_groups.append(
            {
                "line_group_id": group["line_group_id"],
                "engine": group["engine"],
                "winner_text": group["winner_text"],
                "winner_normalized_text": group["winner_normalized_text"],
                "first_timestamp_seconds": round(group["first_timestamp_seconds"], 3),
                "last_timestamp_seconds": round(group["last_timestamp_seconds"], 3),
                "record_count": len(group["records"]),
                "mean_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
                "variants": [{"normalized_text": key, "count": count} for key, count in sorted(group["texts"].items(), key=lambda x: (-x[1], x[0]))],
            }
        )

    return {
        "strategy": "temporal_voting",
        "records": enriched,
        "groups": compact_groups,
        "stable_groups": sum(1 for group in compact_groups if group["record_count"] >= 2),
        "unique_lines": len(compact_groups),
    }


def analyze_text_motion(
    frame_paths: list[Path],
    records: list[dict[str, Any]],
    *,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    cv2, np = _import_cv2_numpy()
    images = [_read_gray(cv2, path) for path in frame_paths]
    if len(images) < 2:
        result = {
            "strategy": "text_mask_motion",
            "frame_count": len(images),
            "shifts": [],
            "mean_text_shift": [0.0, 0.0],
            "mean_global_shift": [0.0, 0.0],
            "phase_quality": {"status": "insufficient_frames", "mean_response": None, "mean_peak_to_second_peak_ratio": None},
        }
        if output_path is not None:
            _write_json(Path(output_path), result)
        return result

    by_frame = _records_by_frame(records)
    shifts: list[dict[str, Any]] = []
    for index in range(1, len(images)):
        prev = images[index - 1]
        cur = images[index]
        prev_mask = _build_text_mask(cv2, np, prev, by_frame.get(str(frame_paths[index - 1]), []))
        cur_mask = _build_text_mask(cv2, np, cur, by_frame.get(str(frame_paths[index]), []))
        text_shift = _phase_shift(cv2, np, prev, cur, mask_a=prev_mask, mask_b=cur_mask)
        global_shift = _phase_shift(cv2, np, prev, cur)
        shifts.append(
            {
                "from_frame": str(frame_paths[index - 1]),
                "to_frame": str(frame_paths[index]),
                "dx": round(text_shift[0], 4),
                "dy": round(text_shift[1], 4),
                "response": round(text_shift[2], 6),
                "peak_to_second_peak_ratio": text_shift[3],
                "global_dx": round(global_shift[0], 4),
                "global_dy": round(global_shift[1], 4),
                "global_response": round(global_shift[2], 6),
                "global_peak_to_second_peak_ratio": global_shift[3],
            }
        )

    mean_text = _mean_shift(shifts, "dx", "dy")
    mean_global = _mean_shift(shifts, "global_dx", "global_dy")
    phase_quality = _phase_quality_gate(shifts)
    result = {
        "strategy": "text_mask_motion",
        "frame_count": len(images),
        "shifts": shifts,
        "mean_text_shift": [round(mean_text[0], 4), round(mean_text[1], 4)],
        "mean_global_shift": [round(mean_global[0], 4), round(mean_global[1], 4)],
        "background_motion_warning": _background_motion_warning(mean_text, mean_global),
        "phase_quality": phase_quality,
    }
    if output_path is not None:
        _write_json(Path(output_path), result)
    return result


def build_descroll_canvas(
    frame_paths: list[Path],
    motion: dict[str, Any],
    *,
    output_path: str | Path,
) -> dict[str, Any]:
    cv2, np = _import_cv2_numpy()
    if not frame_paths:
        result = {
            "strategy": "descroll_canvas",
            "frame_count": 0,
            "canvas_path": None,
            "canvas_size": [0, 0],
            "estimated_orientation": "unknown",
            "motion_shifts": [],
            "warnings": ["no_frames"],
        }
        _write_json(Path(output_path).with_suffix(".json"), result)
        return result

    frames = [_cv2_imread(cv2, np, path, cv2.IMREAD_COLOR) for path in frame_paths]
    if any(frame is None for frame in frames):
        raise RuntimeError("Could not read one or more frames for de-scroll canvas")

    shifts = motion.get("shifts") or []
    positions: list[tuple[float, float]] = [(0.0, 0.0)]
    x, y = 0.0, 0.0
    for shift in shifts[: max(0, len(frames) - 1)]:
        x += float(shift.get("dx") or 0.0)
        y += float(shift.get("dy") or 0.0)
        positions.append((x, y))

    orientation = _orientation_from_positions(positions)
    h, w = frames[0].shape[:2]
    min_x = math.floor(min(px for px, _ in positions))
    min_y = math.floor(min(py for _, py in positions))
    max_x = math.ceil(max(px for px, _ in positions))
    max_y = math.ceil(max(py for _, py in positions))
    canvas_w = max(1, w + max_x - min_x)
    canvas_h = max(1, h + max_y - min_y)
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

    for frame, (px, py) in zip(frames, positions):
        left = int(round(px - min_x))
        top = int(round(py - min_y))
        patch = canvas[top : top + h, left : left + w]
        np.maximum(patch, frame, out=patch)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _cv2_imwrite(cv2, out, canvas)
    result = {
        "strategy": "descroll_canvas",
        "frame_count": len(frames),
        "canvas_path": str(out),
        "canvas_size": [int(canvas_w), int(canvas_h)],
        "estimated_orientation": orientation,
        "motion_shifts": shifts,
        "phase_quality": motion.get("phase_quality"),
        "warnings": [] if len(frames) > 1 else ["single_frame_canvas"],
    }
    _write_json(out.with_suffix(".json"), result)
    return result


class PaddleOcrEngine:
    name = "paddle"

    def __init__(self) -> None:
        os.environ.setdefault("FLAGS_json_format_model", "0")
        os.environ.setdefault("FLAGS_enable_pir_api", "0")
        _disable_modelscope_torch_import()
        from paddleocr import PaddleOCR

        det_model_name = os.environ.get("MITAS_PADDLEOCR_TEXT_DET_MODEL_NAME", PADDLE_DETECTION_MODEL_NAME)
        rec_model_name = os.environ.get("MITAS_PADDLEOCR_TEXT_REC_MODEL_NAME", PADDLE_RECOGNITION_MODEL_NAME)
        det_model_dir = _resolve_paddle_model_dir("MITAS_PADDLEOCR_TEXT_DET_MODEL_DIR", det_model_name)
        rec_model_dir = _resolve_paddle_model_dir("MITAS_PADDLEOCR_TEXT_REC_MODEL_DIR", rec_model_name)
        allow_download = os.environ.get("MITAS_OCR_ALLOW_MODEL_DOWNLOAD", "").strip().lower() in {"1", "true", "yes"}
        if not allow_download and (det_model_dir is None or rec_model_dir is None):
            raise RuntimeError(
                "PaddleOCR local model dirs are not configured. Set "
                "MITAS_PADDLEOCR_TEXT_DET_MODEL_DIR and MITAS_PADDLEOCR_TEXT_REC_MODEL_DIR, "
                f"or install models under {PADDLE_OFFICIAL_MODELS_ROOT}. "
                "Set MITAS_OCR_ALLOW_MODEL_DOWNLOAD=1 for an explicit first-run download."
            )

        self.device = _select_paddle_device()
        self.det_model_name = det_model_name
        self.rec_model_name = rec_model_name
        self.det_model_dir = det_model_dir
        self.rec_model_dir = rec_model_dir
        self._ocr = PaddleOCR(
            text_detection_model_name=det_model_name,
            text_detection_model_dir=str(det_model_dir) if det_model_dir else None,
            text_recognition_model_name=rec_model_name,
            text_recognition_model_dir=str(rec_model_dir) if rec_model_dir else None,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device=self.device,
            enable_mkldnn=False,
        )

    def recognize(self, image_path: Path, *, strategy: str, timestamp_seconds: float | None = None) -> list[dict[str, Any]]:
        if hasattr(self._ocr, "predict"):
            raw = self._ocr.predict(str(image_path))
        else:
            raw = self._ocr.ocr(str(image_path), cls=False)
        return _records_from_paddle(raw, image_path, self.name, strategy, timestamp_seconds)

    def metadata(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "detection_model": self.det_model_name,
            "detection_model_dir": str(self.det_model_dir) if self.det_model_dir else None,
            "recognition_model": self.rec_model_name,
            "recognition_model_dir": str(self.rec_model_dir) if self.rec_model_dir else None,
        }


class OneOcrEngine:
    name = "oneocr"

    def __init__(self) -> None:
        import oneocr

        config_dir = _resolve_oneocr_config_dir()
        self._dll_directory_handle = None
        if hasattr(os, "add_dll_directory"):
            self._dll_directory_handle = os.add_dll_directory(str(config_dir))
        oneocr.CONFIG_DIR = str(config_dir)
        self.config_dir = config_dir
        self._engine = oneocr.OcrEngine()

    def recognize(self, image_path: Path, *, strategy: str, timestamp_seconds: float | None = None) -> list[dict[str, Any]]:
        from PIL import Image

        raw = self._engine.recognize_pil(Image.open(image_path))
        return _records_from_oneocr(raw, image_path, self.name, strategy, timestamp_seconds)

    def metadata(self) -> dict[str, Any]:
        return {"config_dir": str(self.config_dir), "model": str(self.config_dir / "oneocr.onemodel")}


class _LazyOneOcrProxy:
    """V2.1 fallback için lazy OneOCR proxy.

    Pipeline `oneocr_engine` parametresi `None` değilse fallback enabled
    sayar; ama gerçek init `recognize()` çağrılana kadar ertelenir. Decision
    False'da init hiç olmaz (DLL load ~2-4sn tasarruf).

    Factory `() -> OneOcrEngine | None` döner. None dönerse `.recognize()`
    sessizce boş liste verir (fallback skip edilir).
    """

    def __init__(self, factory: Any) -> None:
        self._factory = factory

    def recognize(self, image_path: Path, *, strategy: str, timestamp_seconds: float | None = None) -> list[dict[str, Any]]:
        engine = self._factory()
        if engine is None:
            return []
        return engine.recognize(image_path, strategy=strategy, timestamp_seconds=timestamp_seconds)


class TesseractUnavailableEngine:
    name = "tesseract"

    def __init__(self) -> None:
        import pytesseract

        cmd = _resolve_tesseract()
        if cmd is None:
            raise RuntimeError("tesseract binary is not on PATH and was not found in Program Files")
        self._pytesseract = pytesseract
        self._pytesseract.pytesseract.tesseract_cmd = cmd
        self.cmd = cmd
        self.tessdata_dir = _resolve_tesseract_tessdata_dir()
        available_langs = _available_tesseract_langs(self.tessdata_dir)
        default_lang = "eng+tur" if {"eng", "tur"}.issubset(available_langs) else "eng"
        self.lang = os.environ.get("MITAS_TESSERACT_LANG", default_lang)
        self.config = f"--tessdata-dir {self.tessdata_dir}" if self.tessdata_dir else ""

    def recognize(self, image_path: Path, *, strategy: str, timestamp_seconds: float | None = None) -> list[dict[str, Any]]:
        from PIL import Image

        output = self._pytesseract.image_to_data(Image.open(image_path), lang=self.lang, config=self.config, output_type=self._pytesseract.Output.DICT)
        records: list[dict[str, Any]] = []
        for index, text in enumerate(output.get("text", [])):
            text = str(text or "").strip()
            if not text:
                continue
            confidence = _float_or_none(output.get("conf", [None])[index])
            if confidence is not None:
                confidence = confidence / 100.0
            bbox = [
                float(output.get("left", [0])[index]),
                float(output.get("top", [0])[index]),
                float(output.get("width", [0])[index]),
                float(output.get("height", [0])[index]),
            ]
            records.append(_ocr_record(self.name, strategy, image_path, timestamp_seconds, bbox, text, confidence))
        return records

    def metadata(self) -> dict[str, Any]:
        return {
            "cmd": self.cmd,
            "lang": self.lang,
            "tessdata_dir": str(self.tessdata_dir) if self.tessdata_dir else None,
            "available_langs": sorted(_available_tesseract_langs(self.tessdata_dir)),
        }


def _select_paddle_device() -> str:
    explicit = os.environ.get("MITAS_PADDLEOCR_DEVICE", "").strip()
    if explicit:
        return explicit
    try:
        import paddle

        if paddle.device.is_compiled_with_cuda():
            return "gpu:0"
    except Exception:
        pass
    return "cpu"


def _disable_modelscope_torch_import() -> None:
    """Keep PaddleOCR import independent from a broken optional torch install.

    PaddleX imports ModelScope eagerly while building its model-source registry.
    ModelScope imports torch during logger setup, even when the runner does not
    use ModelScope as a download source. The OCR venv currently has a broken
    torch DLL chain, so we provide a minimal process-local ModelScope module and
    let PaddleOCR use the other model hosts or explicit local model dirs.
    """
    if os.environ.get("MITAS_PADDLEOCR_USE_REAL_MODELSCOPE", "").strip().lower() in {"1", "true", "yes"}:
        return
    if "modelscope" in sys.modules:
        return

    modelscope = types.ModuleType("modelscope")

    def snapshot_download(*_: Any, **__: Any) -> None:
        raise RuntimeError("ModelScope is disabled in MITAS OCR runner; use HuggingFace/AIStudio/BOS/local models instead.")

    hub = types.ModuleType("modelscope.hub")
    errors = types.ModuleType("modelscope.hub.errors")

    class ModelScopeNotExistError(Exception):
        pass

    class ModelScopeHTTPError(Exception):
        pass

    errors.NotExistError = ModelScopeNotExistError
    errors.HTTPError = ModelScopeHTTPError
    hub.errors = errors
    modelscope.snapshot_download = snapshot_download
    modelscope.hub = hub
    sys.modules["modelscope"] = modelscope
    sys.modules["modelscope.hub"] = hub
    sys.modules["modelscope.hub.errors"] = errors


def _run_item_profile_dispatch(
    item: CreditExperimentItem,
    *,
    item_dir: Path,
    engines: list[OcrEngine],
    fps: float | None,  # noqa: ARG001  (effective_fps already resolved)
    max_frames: int | None,
    ffmpeg_executable: str | None,
    effective_fps: float,
    item_started: float,
    warnings: list[str],
) -> dict[str, Any]:
    """Faz 2 dispatch: profil bazlı segment listesi → segment başı unified pipeline.

    Şu an yalnız `kind=film_credits` için çağrılır. `end_credits` LEGACY path
    `_run_item` içinde (geri uyum için byte-identical) kalır.

    Çıktı yapısı (kind=film_credits):
        item_dir/unified/<segment_id>/cards/...
        item_dir/unified/<segment_id>/scroll/...
        item_dir/unified/<segment_id>/summary.json
        item_dir/unified/<segment_id>/events.json
        item_dir/unified/events.json          ← merged (tüm segment'lerin events'i)
        item_dir/unified/summary.json         ← merged summary
    """
    from core.pipelines.ocr import manifest_profiles
    from core.pipelines.ocr._video_meta import duration_seconds
    from core.pipelines.ocr.unified_credit_pipeline import run_unified_credit_pipeline

    item_unified_dir = item_dir / "unified"
    item_unified_dir.mkdir(parents=True, exist_ok=True)
    frames_root = item_dir / "frames"

    # 1) Video duration (ffprobe) — pencere hesabı için zorunlu
    try:
        duration = duration_seconds(item.path)
    except Exception as exc:
        summary = {
            "id": item.id,
            "status": "failed",
            "kind": item.kind,
            "pipeline": "box_track_unified_profile",
            "error_msg": f"ffprobe failed: {exc}",
            "runtime_sec": round(perf_counter() - item_started, 3),
        }
        _write_json(item_dir / "item_summary.json", summary)
        return summary

    # 2) Segment listesi — Faz 4: dinamik pencere uzantısı (paddle_engine DI)
    #    `dynamic_window=True` (manifest default) + paddle_engine verilirse
    #    boundary frame'lerde "yazı var mı?" probe edilir, varsa pencere uzar.
    #    `dynamic_window=False` ya da engine yoksa Faz 2 sabit davranış korunur.
    primary_engine = engines[0] if engines else None
    ffmpeg_exe = ffmpeg_executable or _resolve_ffmpeg()
    try:
        segments = manifest_profiles.build_segments_for_item(
            item.raw,
            duration,
            paddle_engine=primary_engine,
            ffmpeg_executable=ffmpeg_exe,
        )
    except Exception as exc:
        summary = {
            "id": item.id,
            "status": "failed",
            "kind": item.kind,
            "pipeline": "box_track_unified_profile",
            "error_msg": f"segment_build_failed: {type(exc).__name__}: {exc}",
            "runtime_sec": round(perf_counter() - item_started, 3),
        }
        _write_json(item_dir / "item_summary.json", summary)
        return summary

    # 3) Her segment için frames extract + unified pipeline
    seg_results: list[dict[str, Any]] = []
    # V2.1: OneOCR fallback için lazy singleton — ilk fallback ihtiyacı
    # gelene kadar init etmiyoruz (DLL load pahalı). `_lazy_oneocr` closure
    # state'i tek instance üretir, sonraki çağrılarda yeniden kullanır.
    oneocr_holder: dict[str, Any] = {"engine": None, "init_failed": False}

    def _lazy_oneocr() -> Any:
        # Caller (run_unified_credit_pipeline) decision'ı içeriden veriyor;
        # decision False olduğunda bu closure çağrılmadığı için engine init
        # edilmez. Test çevrelerinde OneOCR yoksa init bir kez başarısız
        # olur (init_failed=True), sonraki çağrılar None döner.
        if oneocr_holder["init_failed"]:
            return None
        if oneocr_holder["engine"] is None:
            try:
                # `OneOcrEngine` zaten bu modülde tanımlı (line 507)
                oneocr_holder["engine"] = OneOcrEngine()
            except Exception as exc:
                oneocr_holder["init_failed"] = True
                warnings.append(f"oneocr_fallback_init_failed:{type(exc).__name__}:{exc}")
                return None
        return oneocr_holder["engine"]

    # V2.1: Fallback'i tamamen kapatmak için env var
    from core.pipelines.ocr.fallback_strategy import fallback_enabled_from_env
    fallback_enabled = fallback_enabled_from_env()
    for seg in segments:
        seg_id = str(seg["segment_id"])
        seg_start = float(seg["start_sec"])
        seg_end = float(seg["end_sec"])
        seg_frames_dir = frames_root / seg_id
        seg_frames_dir.mkdir(parents=True, exist_ok=True)
        seg_output_dir = item_unified_dir / seg_id
        seg_output_dir.mkdir(parents=True, exist_ok=True)

        try:
            seg_frames = _extract_segment_frames(
                item.path,
                seg_frames_dir,
                start_seconds=seg_start,
                end_seconds=seg_end,
                fps=effective_fps,
                max_frames=max_frames,
                ffmpeg_executable=ffmpeg_exe,
            )
        except Exception as exc:
            warnings.append(f"segment_extract_failed:{seg_id}:{type(exc).__name__}:{exc}")
            seg_results.append({
                "segment_id": seg_id,
                "status": "failed",
                "start_sec": seg_start,
                "end_sec": seg_end,
                "error_msg": f"extract: {exc}",
                "dynamic_window": seg.get("dynamic_window"),
            })
            continue

        try:
            # V2.1: fallback için lazy OneOCR proxy — pipeline içinde
            # decision False ise `.recognize()` hiç çağrılmaz, init olmaz.
            oneocr_for_pipeline = _LazyOneOcrProxy(_lazy_oneocr) if fallback_enabled else None
            unified = run_unified_credit_pipeline(
                frames=seg_frames,
                output_dir=seg_output_dir,
                paddle_engine=primary_engine,
                source_fps=effective_fps,
                oneocr_engine=oneocr_for_pipeline,
            )
        except Exception as exc:
            warnings.append(f"segment_pipeline_failed:{seg_id}:{type(exc).__name__}:{exc}")
            seg_results.append({
                "segment_id": seg_id,
                "status": "failed",
                "start_sec": seg_start,
                "end_sec": seg_end,
                "error_msg": f"pipeline: {exc}",
                "dynamic_window": seg.get("dynamic_window"),
            })
            continue

        seg_results.append({
            "segment_id": seg_id,
            "status": "done",
            "start_sec": seg_start,
            "end_sec": seg_end,
            "runtime_sec": unified.runtime_sec,
            "unified_summary": unified.summary,
            "events_count": unified.events_count,
            "events_path": str(unified.events_path) if unified.events_path else None,
            "summary_path": str(unified.summary_path),
            "cards_dir": str(unified.cards_dir),
            "dynamic_window": seg.get("dynamic_window"),
        })

    # 4) Merge events.json (her segment'in events'lerini tek listede topla)
    merged_events: list[dict[str, Any]] = []
    merged_by_type: dict[str, int] = {}
    total_events = 0
    any_fallback = False  # eski A-fb (scroll_track_observation_fallback)
    fallback_reasons: list[str] = []
    # V2.1: OneOCR fallback telemetrisi
    any_oneocr_fallback = False
    oneocr_fallback_total_events = 0
    oneocr_fallback_segments: list[str] = []
    oneocr_fallback_reasons: list[str] = []
    for seg_result in seg_results:
        if seg_result.get("status") != "done":
            continue
        evt_path_str = seg_result.get("events_path")
        if not evt_path_str:
            continue
        evt_path = Path(evt_path_str)
        if not evt_path.exists():
            continue
        try:
            payload = json.loads(evt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"merge_events_read_failed:{seg_result['segment_id']}:{exc}")
            continue
        seg_events = payload.get("events") or []
        for ev in seg_events:
            ev_copy = dict(ev)
            ev_copy["segment_id"] = seg_result["segment_id"]
            merged_events.append(ev_copy)
            ev_type = str(ev_copy.get("type") or "unknown")
            merged_by_type[ev_type] = merged_by_type.get(ev_type, 0) + 1
            total_events += 1
        seg_summary = payload.get("summary") or {}
        if seg_summary.get("fallback_used"):
            any_fallback = True
            reason = seg_summary.get("fallback_reason")
            if reason:
                fallback_reasons.append(f"{seg_result['segment_id']}:{reason}")
        # V2.1: OneOCR fallback telemetrisini ROLL UP et
        if seg_summary.get("fallback_triggered"):
            any_oneocr_fallback = True
            oneocr_fallback_total_events += int(seg_summary.get("fallback_event_count") or 0)
            oneocr_fallback_segments.append(seg_result["segment_id"])
            r = seg_summary.get("fallback_decision_reason") or seg_summary.get("fallback_reason")
            if r:
                oneocr_fallback_reasons.append(f"{seg_result['segment_id']}:{r}")

    # Renumber event_ids so the merged list has unique IDs
    for idx, ev in enumerate(merged_events, start=1):
        ev["event_id"] = f"evt_{idx:04d}"

    runtime_total = round(perf_counter() - item_started, 3)

    # Read SCHEMA_VERSION lazily so we don't have a hard dep at import time
    try:
        from core.pipelines.ocr.text_event import SCHEMA_VERSION
    except Exception:
        SCHEMA_VERSION = "1.0.0"

    merged_events_payload = {
        "schema_version": SCHEMA_VERSION,
        "video_id": item.id,
        "source_path": str(item.path),
        "events": merged_events,
        "summary": {
            "engine": "k_box_track_unified_profile",
            "kind": item.kind,
            "version": SCHEMA_VERSION,
            "total_events": total_events,
            "by_type": merged_by_type,
            "segments": [
                {
                    "segment_id": r["segment_id"],
                    "start_sec": r["start_sec"],
                    "end_sec": r["end_sec"],
                    "status": r.get("status"),
                    "events_count": r.get("events_count", 0),
                }
                for r in seg_results
            ],
            "runtime_sec": runtime_total,
            "low_confidence_count": 0,  # Faz 5
            "fallback_used": any_fallback,
            "fallback_reason": ",".join(fallback_reasons) if fallback_reasons else None,
            # V2.1: OneOCR akıllı fallback roll-up
            "fallback_triggered": any_oneocr_fallback,
            "fallback_engine": "oneocr" if any_oneocr_fallback else None,
            "fallback_event_count": oneocr_fallback_total_events,
            "fallback_segments": oneocr_fallback_segments,
            "fallback_decision_reasons": oneocr_fallback_reasons,
        },
    }
    _write_json(item_unified_dir / "events.json", merged_events_payload)

    # 5) Merged summary
    item_summary = {
        "id": item.id,
        "status": "done",
        "kind": item.kind,
        "pipeline": "box_track_unified_profile",
        "input_path": str(item.path),
        "video_duration_sec": duration,
        "segments": [
            {k: v for k, v in r.items() if k not in {"unified_summary"}}
            for r in seg_results
        ],
        "merged_event_count": total_events,
        "merged_by_type": merged_by_type,
        "runtime_sec": runtime_total,
        # V2.1: OneOCR fallback telemetrisi item düzeyinde
        "fallback_triggered": any_oneocr_fallback,
        "fallback_engine": "oneocr" if any_oneocr_fallback else None,
        "fallback_event_count": oneocr_fallback_total_events,
        "fallback_segments": oneocr_fallback_segments,
        "fallback_decision_reasons": oneocr_fallback_reasons,
        "warnings": warnings,
    }
    _write_json(item_dir / "item_summary.json", item_summary)

    # Also dump merged unified summary for parity with end_credits flow
    _write_json(item_unified_dir / "summary.json", {
        "kind": item.kind,
        "video_duration_sec": duration,
        "segments": [
            {
                "segment_id": r["segment_id"],
                "start_sec": r["start_sec"],
                "end_sec": r["end_sec"],
                "status": r.get("status"),
                "unified_summary": r.get("unified_summary"),
            }
            for r in seg_results
        ],
        "merged_event_count": total_events,
        "runtime_sec": runtime_total,
    })

    return item_summary


def _is_legacy_credit_pipeline() -> bool:
    """Whether the legacy 8-stage credit pipeline should run instead of the
    text-first (K-BoxTrack unified) pipeline.

    Default: ``False`` (yeni text-first mimari). The legacy 8-stage path is kept
    for regression/comparison only and must be opted into explicitly.

    Trigger'lar (herhangi biri True ise eski yol açılır):
      - ``USE_LEGACY_CREDIT_PIPELINE=1`` (yeni, önerilen)
      - ``USE_BOX_TRACK_PIPELINE=0`` (eski, geri uyum — Çağatay'ın eski
        kullanımı bozulmasın)

    Only the literal string ``"1"`` (resp. ``"0"``) is recognized — typos like
    ``"true"`` / ``"yes"`` / ``"xyz"`` deliberately fall back to the text-first
    default so a mistyped env var cannot silently re-enable the legacy path.
    """
    if os.environ.get("USE_LEGACY_CREDIT_PIPELINE", "").strip() == "1":
        return True
    # Geri uyum: eski env var explicitly disabled the box-track pipeline.
    if os.environ.get("USE_BOX_TRACK_PIPELINE", "").strip() == "0":
        return True
    return False


def _run_item(
    item: CreditExperimentItem,
    *,
    item_dir: Path,
    engines: list[OcrEngine],
    fps: float | None,
    max_frames: int | None,
    preprocess_mode: str,
    ffmpeg_executable: str | None,
) -> dict[str, Any]:
    # Text-first (K-BoxTrack unified) pipeline default ON since commit bf2c047
    # (D-split landed) and reaffirmed by Faz 6. The legacy 8-stage path is kept
    # for regression/comparison only — opt in with ``USE_LEGACY_CREDIT_PIPELINE=1``
    # (preferred) or the legacy ``USE_BOX_TRACK_PIPELINE=0`` (back-compat).
    # See ``_is_legacy_credit_pipeline()`` for the exact trigger semantics.
    USE_BOX_TRACK = not _is_legacy_credit_pipeline()
    item_started = perf_counter()
    timings: dict[str, float] = {}
    warnings: list[str] = []
    gpu_before = _gpu_snapshot()
    effective_fps, sampling_policy = _effective_fps(item, fps)
    item_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = item_dir / "frames"
    crops_dir = item_dir / "crops"
    canvases_dir = item_dir / "canvases"
    preprocess_dir = item_dir / "preprocessed"
    crops_dir.mkdir(parents=True, exist_ok=True)
    canvases_dir.mkdir(parents=True, exist_ok=True)
    preprocess_dir.mkdir(parents=True, exist_ok=True)

    if not item.path.exists():
        summary = {
            "id": item.id,
            "status": "failed",
            "error_msg": f"Input file does not exist: {item.path}",
            "runtime_sec": round(perf_counter() - item_started, 3),
        }
        _write_json(item_dir / "item_summary.json", summary)
        (item_dir / "comparison.md").write_text(_build_item_comparison(summary, {}, {}, {}, {}), encoding="utf-8")
        return summary

    _write_json(item_dir / "item_summary.json", {"id": item.id, "status": "in_progress", "started_at": datetime.now(timezone.utc).isoformat()})
    try:
        # --- Faz 2: profil dispatch ---
        # `kind: film_credits` (ve gelecekteki yeni profiller) USE_BOX_TRACK
        # zorunlu — eski 8-stage path bunlara uygun değil. End_credits LEGACY
        # davranışı tamamen korunuyor (geri uyum).
        if USE_BOX_TRACK and item.kind in {"film_credits"}:
            return _run_item_profile_dispatch(
                item,
                item_dir=item_dir,
                engines=engines,
                fps=fps,
                max_frames=max_frames,
                ffmpeg_executable=ffmpeg_executable,
                effective_fps=effective_fps,
                item_started=item_started,
                warnings=warnings,
            )

        segment_detection = _detect_effective_credit_segment(item)
        _write_json(item_dir / "credit_segment_detection.json", segment_detection)
        segment_start_seconds = float(segment_detection.get("effective_start_seconds") or item.start_seconds)
        segment_end_seconds = float(segment_detection.get("effective_end_seconds") or item.end_seconds)
        if segment_detection.get("status") == "applied":
            warnings.append(
                "credit_detector_applied:"
                f"{segment_start_seconds:.3f}-{segment_end_seconds:.3f}:"
                f"{segment_detection.get('detected_type')}"
            )
        elif segment_detection.get("reason"):
            warnings.append(f"credit_detector_fallback:{segment_detection.get('reason')}")

        step_started = perf_counter()
        frames = _extract_segment_frames(
            item.path,
            frames_dir,
            start_seconds=segment_start_seconds,
            end_seconds=segment_end_seconds,
            fps=effective_fps,
            max_frames=max_frames,
            ffmpeg_executable=ffmpeg_executable or _resolve_ffmpeg(),
        )
        scroll_reconstruct_frames = list(frames)
        timings["extract_frames_sec"] = round(perf_counter() - step_started, 3)

        if USE_BOX_TRACK:
            from core.pipelines.ocr.unified_credit_pipeline import run_unified_credit_pipeline
            unified_result = run_unified_credit_pipeline(
                frames=frames,
                output_dir=item_dir / "unified",
                paddle_engine=engines[0] if engines else None,
                source_fps=effective_fps,
            )
            summary = {
                "id": item.id,
                "status": "done",
                "pipeline": "box_track_unified",
                "input_path": str(item.path),
                "start_seconds": segment_start_seconds,
                "end_seconds": segment_end_seconds,
                "runtime_sec": unified_result.runtime_sec,
                "unified_summary": unified_result.summary,
            }
            _write_json(item_dir / "item_summary.json", summary)
            return summary
        # else: eski yol devam eder (mevcut kod aynen)
        applied_roi = item.roi
        roi_strategy = "full_frame"
        auto_roi_info: dict[str, Any] | None = None
        auto_roi: tuple[int, int, int, int] | None = None
        refined_auto_roi_info: dict[str, Any] | None = None
        refined_auto_roi: tuple[int, int, int, int] | None = None
        first_pass_frame_ocr: dict[str, Any] | None = None
        if item.roi is not None:
            frames = _crop_frames(frames, crops_dir, item.roi)
            roi_strategy = "manifest"
            warnings.append("manifest_roi_applied")
        else:
            auto_roi_info = _infer_text_roi_info(frames, item)
            auto_roi = _roi_tuple(auto_roi_info.get("roi") if auto_roi_info else None)
            _write_json(item_dir / "auto_roi_detection.json", auto_roi_info or {"status": "unavailable"})
            if auto_roi is not None:
                applied_roi = auto_roi
                frames = _crop_frames(frames, crops_dir / "auto_roi", auto_roi)
                roi_strategy = "auto"
                warnings.append(f"auto_roi_applied:{list(auto_roi)}:{(auto_roi_info or {}).get('strategy')}")
        ocr_samples = _expand_frames_for_columns(frames, crops_dir / "columns", item.column_count)
        if item.column_count > 1:
            warnings.append("two_column_or_multi_column_split_enabled")

        step_started = perf_counter()
        scene_profile = _analyze_scene_profile(scroll_reconstruct_frames, item)
        scene_profile["effective_time_range"] = [segment_start_seconds, segment_end_seconds]
        scene_profile["manifest_time_range"] = [item.start_seconds, item.end_seconds]
        scene_profile["analysis_frame_scope"] = "pre_roi_full_frame"
        timings["scene_router_sec"] = round(perf_counter() - step_started, 3)
        _write_json(item_dir / "scene_router.json", scene_profile)

        step_started = perf_counter()
        frame_ocr = _run_frame_ocr(ocr_samples, engines, start_seconds=segment_start_seconds, fps=effective_fps, strategy="frame_ocr")
        timings["frame_ocr_sec"] = round(perf_counter() - step_started, 3)

        step_started = perf_counter()
        if item.roi is None and item.column_count <= 1:
            refined_auto_roi_info = _infer_second_pass_roi_info(frames, frame_ocr.get("records", []), item)
            refined_auto_roi = _roi_tuple(refined_auto_roi_info.get("roi") if refined_auto_roi_info else None)
            _write_json(item_dir / "refined_auto_roi_detection.json", refined_auto_roi_info or {"status": "unavailable"})
            if refined_auto_roi is not None:
                first_pass_frame_ocr = frame_ocr
                _write_json(item_dir / "frame_ocr_first_pass.json", first_pass_frame_ocr)
                frames = _crop_frames(frames, crops_dir / "refined_auto_roi", refined_auto_roi)
                applied_roi = _compose_roi(applied_roi, refined_auto_roi)
                roi_strategy = "auto_refined" if roi_strategy == "auto" else "ocr_refined"
                warnings.append(f"second_pass_roi_applied:{list(refined_auto_roi)}:{(refined_auto_roi_info or {}).get('strategy')}")
                ocr_samples = _expand_frames_for_columns(frames, crops_dir / "columns_refined", item.column_count)

                scene_started = perf_counter()
                refined_scene_profile = _analyze_scene_profile(frames, item)
                refined_scene_profile["effective_time_range"] = [segment_start_seconds, segment_end_seconds]
                refined_scene_profile["manifest_time_range"] = [item.start_seconds, item.end_seconds]
                refined_scene_profile["analysis_frame_scope"] = "ocr_refined_roi"
                timings["scene_router_after_refined_roi_sec"] = round(perf_counter() - scene_started, 3)
                _write_json(item_dir / "scene_router_after_refined_roi.json", refined_scene_profile)

                rerun_started = perf_counter()
                frame_ocr = _run_frame_ocr(ocr_samples, engines, start_seconds=segment_start_seconds, fps=effective_fps, strategy="frame_ocr")
                timings["frame_ocr_after_refined_roi_sec"] = round(perf_counter() - rerun_started, 3)
            elif refined_auto_roi_info is not None:
                warnings.append(f"second_pass_roi_skipped:{refined_auto_roi_info.get('reason') or refined_auto_roi_info.get('status')}")
        elif item.roi is not None:
            refined_auto_roi_info = {"status": "skipped", "strategy": "ocr_bbox_second_pass", "roi": None, "reason": "manifest_roi_present"}
            _write_json(item_dir / "refined_auto_roi_detection.json", refined_auto_roi_info)
        elif item.column_count > 1:
            refined_auto_roi_info = {"status": "skipped", "strategy": "ocr_bbox_second_pass", "roi": None, "reason": "multi_column_manifest_split"}
            _write_json(item_dir / "refined_auto_roi_detection.json", refined_auto_roi_info)
        timings["refined_auto_roi_sec"] = round(perf_counter() - step_started, 3)

        step_started = perf_counter()
        run_preprocess, preprocess_reason = _should_run_preprocess(item, frame_ocr, preprocess_mode)
        if run_preprocess:
            preprocessed_samples, preprocess_warnings = _preprocess_frame_samples(ocr_samples, preprocess_dir)
            warnings.extend(preprocess_warnings)
            preprocessed_ocr = _run_frame_ocr(
                preprocessed_samples,
                engines,
                start_seconds=segment_start_seconds,
                fps=effective_fps,
                strategy="preprocessed_frame_ocr",
            )
        else:
            preprocessed_samples = []
            preprocessed_ocr = _empty_ocr_result("preprocessed_frame_ocr", f"preprocess_skipped:{preprocess_reason}")
            warnings.append(f"preprocess_skipped:{preprocess_reason}")
        timings["preprocessed_frame_ocr_sec"] = round(perf_counter() - step_started, 3)

        step_started = perf_counter()
        temporal = group_temporal_records(frame_ocr["records"])
        preprocessed_temporal = group_temporal_records(preprocessed_ocr["records"])
        timings["temporal_voting_sec"] = round(perf_counter() - step_started, 3)

        step_started = perf_counter()
        scene_profile = _refine_scene_profile_with_ocr(scene_profile, temporal["records"])
        timings["scene_router_refine_sec"] = round(perf_counter() - step_started, 3)
        _write_json(item_dir / "scene_router_refined.json", scene_profile)

        step_started = perf_counter()
        motion = analyze_text_motion(frames, temporal["records"])
        timings["text_motion_sec"] = round(perf_counter() - step_started, 3)

        step_started = perf_counter()
        row_reconstruct = _run_row_reconstruct_hook(item_dir, scroll_reconstruct_frames, scene_profile)
        timings["row_reconstruct_sec"] = round(perf_counter() - step_started, 3)

        step_started = perf_counter()
        temporal_fusion = _run_temporal_fusion_hook(item_dir, scroll_reconstruct_frames, scene_profile)
        timings["temporal_fusion_sec"] = round(perf_counter() - step_started, 3)
        if temporal_fusion.get("status") == "done" and temporal_fusion.get("output_path"):
            step_started_fuse_ocr = perf_counter()
            temporal_fusion["ocr_records"] = _run_canvas_ocr(Path(temporal_fusion["output_path"]), engines)
            timings["temporal_fusion_ocr_sec"] = round(perf_counter() - step_started_fuse_ocr, 3)

        step_started = perf_counter()
        row_ocr = _run_row_crop_ocr(row_reconstruct, engines)
        timings["row_crop_ocr_sec"] = round(perf_counter() - step_started, 3)

        step_started = perf_counter()
        canvas = build_descroll_canvas(frames, motion, output_path=canvases_dir / "descroll_canvas.png")
        timings["descroll_canvas_sec"] = round(perf_counter() - step_started, 3)

        step_started = perf_counter()
        canvas_ocr_records = _run_canvas_ocr(Path(canvas["canvas_path"]), engines) if canvas.get("canvas_path") else []
        timings["canvas_ocr_sec"] = round(perf_counter() - step_started, 3)
        canvas["ocr_records"] = canvas_ocr_records
        canvas["canvas_advantage"] = _canvas_advantage(frame_ocr["records"], temporal, canvas_ocr_records, item.ground_truth)

        evaluation = _evaluate_item_strategies(
            item,
            frame_ocr,
            preprocessed_ocr,
            temporal,
            preprocessed_temporal,
            canvas_ocr_records,
            temporal_fusion=temporal_fusion,
        )

        _write_json(item_dir / "frame_ocr.json", frame_ocr)
        _write_json(item_dir / "preprocessed_frame_ocr.json", preprocessed_ocr)
        _write_json(item_dir / "temporal_voting.json", temporal)
        _write_json(item_dir / "preprocessed_temporal_voting.json", preprocessed_temporal)
        _write_json(item_dir / "text_motion.json", motion)
        _write_json(item_dir / "row_reconstruct.json", row_reconstruct)
        _write_json(item_dir / "temporal_fusion.json", temporal_fusion)
        _write_json(item_dir / "row_crop_ocr.json", row_ocr)
        (item_dir / "row_crop_ocr.md").write_text(_build_row_crop_ocr_report(row_ocr), encoding="utf-8")
        _write_json(item_dir / "descroll_canvas.json", canvas)
        _write_json(item_dir / "evaluation.json", evaluation)
        quality_police = _assess_generated_png_outputs(item_dir, row_reconstruct, temporal_fusion, canvas)

        timings["total_item_sec"] = round(perf_counter() - item_started, 3)
        costs = {
            "timings_sec": timings,
            "disk_bytes": _directory_size_bytes(item_dir),
            "gpu_snapshot_before": gpu_before,
            "gpu_snapshot_after": _gpu_snapshot(),
            "engine_call_costs": {
                "frame_ocr": frame_ocr.get("costs", {}),
                "frame_ocr_first_pass": first_pass_frame_ocr.get("costs", {}) if first_pass_frame_ocr else {},
                "preprocessed_frame_ocr": preprocessed_ocr.get("costs", {}),
                "row_crop_ocr": row_ocr.get("costs", {}),
                "descroll_canvas_ocr": _engine_call_costs(canvas_ocr_records),
            },
        }
        costs["gpu_peak_observed"] = _gpu_peak_from_snapshots(costs["gpu_snapshot_before"], costs["gpu_snapshot_after"])
        costs["strategy_cost_rates"] = _strategy_cost_rates(costs["engine_call_costs"], max(0.001, segment_end_seconds - segment_start_seconds))
        _write_json(item_dir / "costs.json", costs)

        total_ocr_records = len(frame_ocr["records"]) + len(preprocessed_ocr["records"]) + len(canvas_ocr_records) + int(row_ocr.get("record_count") or 0)
        summary = {
            "id": item.id,
            "status": "done" if engines and total_ocr_records > 0 else "partial",
            "kind": item.kind,
            "layout_type": item.layout_type,
            "motion_type": item.motion_type,
            "expected_language": item.expected_language,
            "input_path": str(item.path),
            "start_seconds": segment_start_seconds,
            "end_seconds": segment_end_seconds,
            "manifest_start_seconds": item.start_seconds,
            "manifest_end_seconds": item.end_seconds,
            "credit_segment_detection": segment_detection,
            "fps": effective_fps,
            "sampling_policy": sampling_policy,
            "preprocess_mode": preprocess_mode,
            "preprocess_reason": preprocess_reason,
            "preprocess_triggered": run_preprocess,
            "preprocess_trigger_rate": 1.0 if run_preprocess else 0.0,
            "scroll_auto_detect": item.scroll_auto_detect,
            "roi": list(item.roi) if item.roi else None,
            "applied_roi": list(applied_roi) if applied_roi else None,
            "auto_roi": list(auto_roi) if auto_roi else None,
            "auto_roi_info": _auto_roi_summary(auto_roi_info),
            "refined_auto_roi": list(refined_auto_roi) if refined_auto_roi else None,
            "refined_auto_roi_info": _auto_roi_summary(refined_auto_roi_info),
            "roi_strategy": roi_strategy,
            "column_count": item.column_count,
            "ground_truth_count": len(item.ground_truth),
            "notes": item.notes,
            "warnings": warnings,
            "scene_profile": _scene_profile_summary(scene_profile),
            "frames": len(frames),
            "scroll_reconstruct_frames": len(scroll_reconstruct_frames),
            "ocr_images": len(ocr_samples),
            "frame_ocr_first_pass_records": len(first_pass_frame_ocr.get("records", [])) if first_pass_frame_ocr else 0,
            "frame_ocr_records": len(frame_ocr["records"]),
            "preprocessed_ocr_records": len(preprocessed_ocr["records"]),
            "temporal_unique_lines": temporal["unique_lines"],
            "temporal_stable_groups": temporal["stable_groups"],
            "preprocessed_temporal_unique_lines": preprocessed_temporal["unique_lines"],
            "preprocessed_temporal_stable_groups": preprocessed_temporal["stable_groups"],
            "row_reconstruct": _row_reconstruct_summary(row_reconstruct),
            "row_crop_ocr": _row_crop_ocr_summary(row_ocr),
            "quality_police": quality_police,
            "canvas_size": canvas["canvas_size"],
            "canvas_ocr_records": len(canvas_ocr_records),
            "evaluation": evaluation.get("summary", {}),
            "costs": costs,
            "runtime_sec": round(perf_counter() - item_started, 3),
        }
        _write_json(item_dir / "item_summary.json", summary)
        (item_dir / "comparison.md").write_text(
            _build_item_comparison(summary, frame_ocr, temporal, motion, canvas, preprocessed_ocr, preprocessed_temporal, evaluation),
            encoding="utf-8",
        )
        return summary
    except BaseException as exc:
        summary = {
            "id": item.id,
            "status": "failed",
            "error_msg": str(exc),
            "layout_type": item.layout_type,
            "motion_type": item.motion_type,
            "expected_language": item.expected_language,
            "ground_truth_count": len(item.ground_truth),
            "fps": effective_fps,
            "sampling_policy": sampling_policy,
            "preprocess_mode": preprocess_mode,
            "runtime_sec": round(perf_counter() - item_started, 3),
        }
        _write_json(item_dir / "item_summary.json", summary)
        (item_dir / "comparison.md").write_text(_build_item_comparison(summary, {}, {}, {}, {}), encoding="utf-8")
        return summary


def _detect_effective_credit_segment(item: CreditExperimentItem) -> dict[str, Any]:
    """Trim broad manifest windows to a detected credit subsegment.

    The manifest remains the safety rail. The detector can only replace the
    time range when its result overlaps the manifest window, so KJ and ad-hoc
    clips do not jump to unrelated end credits elsewhere in the video.
    """
    manifest_start = float(item.start_seconds)
    manifest_end = float(item.end_seconds)
    manifest_duration = max(0.001, manifest_end - manifest_start)
    payload: dict[str, Any] = {
        "strategy": "opus_credit_detector",
        "status": "skipped" if not item.scroll_auto_detect else "fallback",
        "manifest_start_seconds": manifest_start,
        "manifest_end_seconds": manifest_end,
        "effective_start_seconds": manifest_start,
        "effective_end_seconds": manifest_end,
    }
    if not item.scroll_auto_detect:
        payload["reason"] = "scroll_auto_detect_not_requested"
        return payload
    try:
        from core.pipelines.ocr.credit_detector import OpusCreditDetector

        detected = OpusCreditDetector().detect(item.path, verbose=False)
    except Exception as exc:
        payload["reason"] = f"detector_error:{exc}"
        return payload

    payload["detector_result"] = detected
    if not detected.get("found"):
        payload["reason"] = str(detected.get("reason") or "not_found")
        return payload

    detected_start = float(detected.get("start_sec") or 0.0)
    detected_end = float(detected.get("end_sec") or 0.0)
    overlap_start = max(manifest_start, detected_start)
    overlap_end = min(manifest_end, detected_end)
    overlap = max(0.0, overlap_end - overlap_start)
    min_overlap = min(manifest_duration, max(30.0, manifest_duration * 0.45))
    detected_duration = max(0.0, detected_end - detected_start)
    fraction_detected_covered = overlap / max(1.0, detected_duration)
    payload.update(
        {
            "detected_start_seconds": detected_start,
            "detected_end_seconds": detected_end,
            "detected_type": detected.get("type"),
            "detected_confidence": detected.get("confidence"),
            "overlap_seconds": round(overlap, 3),
            "min_overlap_seconds": round(min_overlap, 3),
            "fraction_detected_covered": round(fraction_detected_covered, 4),
        }
    )
    if detected_duration < 5.0:
        payload["reason"] = "detected_segment_too_short"
        return payload
    # Accept if manifest coverage is met, OR detected segment is mostly within manifest (≥65%).
    # This prevents rejecting high-confidence short-segment detections that fall fully inside
    # a broad manifest window (e.g. 80s credit in a 180s safety window).
    if overlap < min_overlap and fraction_detected_covered < 0.65:
        payload["reason"] = "detected_segment_too_small_or_outside_manifest_window"
        return payload
    if overlap_end - overlap_start < 1.0:
        payload["reason"] = "effective_segment_too_short"
        return payload

    payload["status"] = "applied"
    payload["reason"] = "detector_overlap_with_manifest"
    payload["effective_start_seconds"] = round(overlap_start, 3)
    payload["effective_end_seconds"] = round(overlap_end, 3)
    return payload


def _run_row_reconstruct_hook(item_dir: Path, frames: list[Path], scene_profile: dict[str, Any]) -> dict[str, Any]:
    recommendation = scene_profile.get("recommended_pipeline") if isinstance(scene_profile, dict) else {}
    temporal = str((recommendation or {}).get("temporal") or "")
    should_run = temporal in {"row_reconstruct", "best_frame_selection", "segment_then_route"}
    if not should_run:
        return {
            "status": "skipped",
            "reason": f"recommended_temporal:{temporal or 'unknown'}",
            "strategy": "text_layer_row_reconstruct_v1",
        }
    try:
        from core.pipelines.ocr.text_layer_row_reconstruct import run_text_layer_row_reconstruct

        result = run_text_layer_row_reconstruct(
            frame_paths=frames,
            output_dir=item_dir / "text_layer_row_reconstruct",
            max_frames=None,
            scale_for_rows=2,
        )
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
        summary["status"] = "done"
        summary["summary_path"] = str(result.summary_path)
        summary["report_path"] = str(result.report_path)
        return summary
    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "strategy": "text_layer_row_reconstruct_v1",
        }


def _run_temporal_fusion_hook(item_dir: Path, frames: list[Path], scene_profile: dict[str, Any]) -> dict[str, Any]:
    recommendation = scene_profile.get("recommended_pipeline") if isinstance(scene_profile, dict) else {}
    temporal = str((recommendation or {}).get("temporal") or "")
    if temporal not in {"temporal_median_fusion", "temporal_variance_masking"}:
        return {
            "status": "skipped",
            "reason": f"recommended_temporal:{temporal or 'unknown'}",
            "strategy": "temporal_fusion_v1",
        }
    try:
        from core.pipelines.ocr.temporal_fusion import (
            run_temporal_median_fusion,
            run_temporal_variance_masking,
        )
        runner = run_temporal_median_fusion if temporal == "temporal_median_fusion" else run_temporal_variance_masking
        result = runner(frame_paths=frames, output_dir=item_dir / "temporal_fusion", max_frames=None)
        summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
        summary["status"] = "done"
        summary["summary_path"] = str(result.summary_path)
        summary["output_path"] = str(result.output_path)
        return summary
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "strategy": temporal}


def _row_reconstruct_summary(row_reconstruct: dict[str, Any]) -> dict[str, Any]:
    auto_split = row_reconstruct.get("auto_split") or {}
    motion = row_reconstruct.get("motion") or {}
    return {
        "status": row_reconstruct.get("status"),
        "row_count": row_reconstruct.get("row_count"),
        "composite_size": row_reconstruct.get("composite_size"),
        "auto_split_status": auto_split.get("status"),
        "auto_split_x": auto_split.get("split_x"),
        "auto_split_confidence": auto_split.get("confidence"),
        "motion_status": motion.get("status"),
        "median_dy_per_frame": motion.get("median_dy_per_frame"),
    }


def _assess_generated_png_outputs(
    item_dir: Path,
    row_reconstruct: dict[str, Any],
    temporal_fusion: dict[str, Any],
    canvas: dict[str, Any],
) -> dict[str, Any]:
    try:
        from core.pipelines.ocr.image_quality_police import assess_output
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc), "outputs": {}}

    outputs: dict[str, tuple[Path | None, Path | None, str]] = {
        "row_canvas": (
            _existing_output_path(row_reconstruct.get("sharpened_path"))
            or _existing_output_path(row_reconstruct.get("composite_path")),
            item_dir / "row_crop_ocr.json",
            "row_canvas",
        ),
        "temporal_fusion": (
            _existing_output_path(temporal_fusion.get("output_path")),
            item_dir / "temporal_fusion.json",
            "fused",
        ),
        "descroll_canvas": (
            _existing_output_path(canvas.get("canvas_path")),
            item_dir / "descroll_canvas.json",
            "row_canvas",
        ),
    }
    checks: dict[str, Any] = {}
    for name, (png_path, json_path, expected_kind) in outputs.items():
        if png_path is None:
            continue
        try:
            checks[name] = assess_output(
                png_path,
                json_path if json_path.exists() else None,
                expected_kind=expected_kind,  # type: ignore[arg-type]
            )
        except Exception as exc:
            checks[name] = {
                "status": "SUSPICIOUS_NEEDS_REVIEW",
                "reasons": ["quality_police_error"],
                "metrics": {"png_path": str(png_path), "ocr_json_path": str(json_path), "error": str(exc)},
                "suggested_fallback": None,
            }
    return {"status": "done", "outputs": checks}


def _existing_output_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path if path.exists() else None


def _run_row_crop_ocr(row_reconstruct: dict[str, Any], engines: list[OcrEngine], *, max_rows: int = 120) -> dict[str, Any]:
    if row_reconstruct.get("status") != "done":
        return {
            "status": "skipped",
            "reason": f"row_reconstruct_status:{row_reconstruct.get('status')}",
            "strategy": "row_crop_ocr",
            "records": [],
            "pairs": [],
            "record_count": 0,
            "costs": {"engine_runtime_sec": {}, "engine_calls": {}, "engine_records": {}},
        }
    rows = list(row_reconstruct.get("rows") or [])
    if not rows:
        return {
            "status": "skipped",
            "reason": "no_rows",
            "strategy": "row_crop_ocr",
            "records": [],
            "pairs": [],
            "record_count": 0,
            "costs": {"engine_runtime_sec": {}, "engine_calls": {}, "engine_records": {}},
        }
    if not engines:
        return {
            "status": "skipped",
            "reason": "no_engines",
            "strategy": "row_crop_ocr",
            "records": [],
            "pairs": [],
            "record_count": 0,
            "costs": {"engine_runtime_sec": {}, "engine_calls": {}, "engine_records": {}},
        }

    costs = {"engine_runtime_sec": {}, "engine_calls": {}, "engine_records": {}}
    all_records: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    warnings: list[str] = []
    for row in rows[:max_rows]:
        row_index = int(row.get("index") or len(pairs) + 1)
        role_path = Path(row["role_crop_path"]) if row.get("role_crop_path") and Path(row["role_crop_path"]).exists() else None
        name_path = Path(row["name_crop_path"]) if row.get("name_crop_path") and Path(row["name_crop_path"]).exists() else None
        row_path = Path(row["row_path"]) if row.get("row_path") and Path(row["row_path"]).exists() else None
        for engine in engines:
            if role_path and name_path:
                role = _recognize_crop_text(engine, role_path, "row_role_ocr", row_index, "role", costs)
                name = _recognize_crop_text(engine, name_path, "row_name_ocr", row_index, "name", costs)
                all_records.extend(role["records"])
                all_records.extend(name["records"])
                pair_conf = _mean_optional([role.get("confidence"), name.get("confidence")])
                pairs.append(
                    {
                        "engine": engine.name,
                        "row_index": row_index,
                        "role_text": role.get("text") or "",
                        "name_text": name.get("text") or "",
                        "confidence": pair_conf,
                        "role_confidence": role.get("confidence"),
                        "name_confidence": name.get("confidence"),
                        "role_crop_path": str(role_path),
                        "name_crop_path": str(name_path),
                        "warnings": [*role.get("warnings", []), *name.get("warnings", [])],
                    }
                )
            elif row_path:
                row_text = _recognize_crop_text(engine, row_path, "row_line_ocr", row_index, "row", costs)
                all_records.extend(row_text["records"])
                pairs.append(
                    {
                        "engine": engine.name,
                        "row_index": row_index,
                        "row_text": row_text.get("text") or "",
                        "confidence": row_text.get("confidence"),
                        "row_crop_path": str(row_path),
                        "warnings": row_text.get("warnings", []),
                    }
                )
            else:
                warnings.append(f"row_{row_index}:no_crop_path")
    if len(rows) > max_rows:
        warnings.append(f"rows_truncated:{len(rows)}>{max_rows}")
    return {
        "status": "done",
        "strategy": "row_crop_ocr",
        "rows_seen": len(rows),
        "rows_processed": min(len(rows), max_rows),
        "records": all_records,
        "pairs": pairs,
        "record_count": len(all_records),
        "pair_count": len(pairs),
        "costs": costs,
        "warnings": warnings,
    }


def _recognize_crop_text(
    engine: OcrEngine,
    crop_path: Path,
    strategy: str,
    row_index: int,
    crop_part: str,
    costs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    started = perf_counter()
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    try:
        records = engine.recognize(crop_path, strategy=strategy, timestamp_seconds=None)
        for record in records:
            record["row_index"] = row_index
            record["crop_part"] = crop_part
        costs["engine_records"][engine.name] = int(costs["engine_records"].get(engine.name, 0)) + len(records)
    except Exception as exc:
        warnings.append(str(exc))
        records = [_ocr_record(engine.name, strategy, crop_path, None, None, "", None, [str(exc)])]
        records[0]["row_index"] = row_index
        records[0]["crop_part"] = crop_part
    finally:
        costs["engine_calls"][engine.name] = int(costs["engine_calls"].get(engine.name, 0)) + 1
        costs["engine_runtime_sec"][engine.name] = round(float(costs["engine_runtime_sec"].get(engine.name, 0.0)) + (perf_counter() - started), 3)
    text, confidence = _joined_text_and_confidence(records)
    if not text:
        warnings.append("empty_ocr")
    return {"text": text, "confidence": confidence, "records": records, "warnings": warnings}


def _joined_text_and_confidence(records: list[dict[str, Any]]) -> tuple[str, float | None]:
    useful = [record for record in records if str(record.get("text") or "").strip()]
    if not useful:
        return "", None
    useful.sort(key=lambda record: _bbox_sort_key(record.get("bbox")))
    text = " ".join(str(record.get("text") or "").strip() for record in useful if str(record.get("text") or "").strip())
    confidences = [float(record["confidence"]) for record in useful if _is_number(record.get("confidence"))]
    return text.strip(), round(sum(confidences) / len(confidences), 4) if confidences else None


def _bbox_sort_key(bbox: Any) -> tuple[float, float]:
    if isinstance(bbox, list) and len(bbox) >= 2 and _is_number(bbox[0]) and _is_number(bbox[1]):
        return (float(bbox[1]), float(bbox[0]))
    return (0.0, 0.0)


def _mean_optional(values: list[Any]) -> float | None:
    numbers = [float(value) for value in values if _is_number(value)]
    return round(sum(numbers) / len(numbers), 4) if numbers else None


def _row_crop_ocr_summary(row_ocr: dict[str, Any]) -> dict[str, Any]:
    pairs = row_ocr.get("pairs") or []
    nonempty_pairs = [
        pair
        for pair in pairs
        if str(pair.get("role_text") or pair.get("name_text") or pair.get("row_text") or "").strip()
    ]
    return {
        "status": row_ocr.get("status"),
        "rows_processed": row_ocr.get("rows_processed"),
        "pair_count": row_ocr.get("pair_count"),
        "record_count": row_ocr.get("record_count"),
        "nonempty_pair_count": len(nonempty_pairs),
        "warnings": row_ocr.get("warnings") or [],
    }


def _build_row_crop_ocr_report(row_ocr: dict[str, Any]) -> str:
    lines = [
        "# Row Crop OCR",
        "",
        f"- Status: {row_ocr.get('status')}",
        f"- Rows processed: {row_ocr.get('rows_processed')}",
        f"- Pair count: {row_ocr.get('pair_count')}",
        f"- Record count: {row_ocr.get('record_count')}",
        "",
        "| row | engine | role | name / row text | confidence | warnings |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]
    for pair in row_ocr.get("pairs") or []:
        role = _md_cell(pair.get("role_text") or "")
        name = _md_cell(pair.get("name_text") or pair.get("row_text") or "")
        warnings = _md_cell(", ".join(pair.get("warnings") or []))
        confidence = pair.get("confidence")
        lines.append(f"| {pair.get('row_index')} | {_md_cell(pair.get('engine') or '')} | {role} | {name} | {confidence if confidence is not None else ''} | {warnings} |")
    return "\n".join(lines) + "\n"


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _run_frame_ocr(samples: list[Any], engines: list[OcrEngine], *, start_seconds: float, fps: float, strategy: str) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    engine_errors: list[dict[str, str]] = []
    costs = {"engine_runtime_sec": {}, "engine_calls": {}, "engine_records": {}}
    for fallback_index, sample in enumerate(samples):
        frame = _sample_path(sample)
        source_index = _sample_source_index(sample, fallback_index)
        timestamp = round(start_seconds + (source_index / max(fps, 0.001)), 3)
        for engine in engines:
            call_started = perf_counter()
            try:
                engine_records = engine.recognize(frame, strategy=strategy, timestamp_seconds=timestamp)
                for record in engine_records:
                    record.update(_sample_metadata(sample))
                records.extend(engine_records)
                costs["engine_records"][engine.name] = int(costs["engine_records"].get(engine.name, 0)) + len(engine_records)
            except Exception as exc:
                engine_errors.append({"engine": engine.name, "frame": str(frame), "error": str(exc)})
            finally:
                costs["engine_calls"][engine.name] = int(costs["engine_calls"].get(engine.name, 0)) + 1
                costs["engine_runtime_sec"][engine.name] = round(float(costs["engine_runtime_sec"].get(engine.name, 0.0)) + (perf_counter() - call_started), 3)
    return {
        "strategy": strategy,
        "frames": [str(_sample_path(sample)) for sample in samples],
        "records": records,
        "engine_errors": engine_errors,
        "costs": costs,
    }


def _run_canvas_ocr(canvas_path: Path, engines: list[OcrEngine]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for engine in engines:
        started = perf_counter()
        try:
            engine_records = engine.recognize(canvas_path, strategy="descroll_canvas_ocr", timestamp_seconds=None)
            for record in engine_records:
                record["engine_runtime_sec"] = round(perf_counter() - started, 3)
            records.extend(engine_records)
        except Exception as exc:
            records.append(_ocr_record(engine.name, "descroll_canvas_ocr", canvas_path, None, None, "", None, [str(exc)]))
    return records


def _empty_ocr_result(strategy: str, warning: str) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "frames": [],
        "records": [],
        "engine_errors": [],
        "costs": {"engine_runtime_sec": {}, "engine_calls": {}, "engine_records": {}},
        "warnings": [warning],
    }


def _analyze_scene_profile(frames: list[Path], item: CreditExperimentItem) -> dict[str, Any]:
    try:
        from core.pipelines.ocr.credit_scene_router import analyze_credit_scene

        profile = analyze_credit_scene(
            frames,
            segment_id=item.id,
            time_range=(float(item.start_seconds), float(item.end_seconds)),
            max_frames=48,
        )
        return profile.to_dict()
    except Exception as exc:
        return {
            "segment_id": item.id,
            "time_range": [item.start_seconds, item.end_seconds],
            "status": "unavailable",
            "error": str(exc),
            "recommended_pipeline": {
                "temporal": "temporal_voting",
                "fallback_pipelines": ["frame_ocr"],
                "why": ["scene router unavailable"],
            },
        }


def _refine_scene_profile_with_ocr(profile: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        from core.pipelines.ocr.credit_scene_router import refine_credit_scene_with_ocr

        return refine_credit_scene_with_ocr(profile, records)
    except Exception as exc:
        refined = dict(profile)
        refined["ocr_refinement_error"] = str(exc)
        return refined


def _scene_profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    def _kind(key: str) -> str | None:
        value = profile.get(key)
        return value.get("type") if isinstance(value, dict) else None

    difficulty = profile.get("difficulty") if isinstance(profile.get("difficulty"), dict) else {}
    pipeline = profile.get("recommended_pipeline") if isinstance(profile.get("recommended_pipeline"), dict) else {}
    return {
        "background": _kind("background"),
        "text_motion": _kind("text_motion"),
        "layout": _kind("layout"),
        "difficulty_labels": difficulty.get("labels") or [],
        "difficulty_score": difficulty.get("score"),
        "recommended_temporal": pipeline.get("temporal"),
        "recommended_preprocess": pipeline.get("preprocess") or [],
        "recommended_parser": pipeline.get("parser"),
    }


def _normalize_preprocess_mode(mode: str) -> str:
    normalized = (mode or "auto").strip().lower()
    if normalized not in {"auto", "off", "always"}:
        raise ValueError("preprocess_mode must be one of: auto, off, always")
    return normalized


def _should_run_preprocess(item: CreditExperimentItem, frame_ocr: dict[str, Any], mode: str) -> tuple[bool, str]:
    mode = _normalize_preprocess_mode(mode)
    if mode == "always":
        return True, "mode_always"
    if mode == "off":
        return False, "mode_off"

    records = [record for record in frame_ocr.get("records", []) if str(record.get("text") or "").strip()]
    if not records:
        return True, "no_frame_ocr_records"

    confidences = [float(record["confidence"]) for record in records if _is_number(record.get("confidence"))]
    if confidences and _median(confidences) < 0.75:
        return True, "low_median_confidence"

    heights = [float(record["bbox"][3]) for record in records if record.get("bbox") and len(record["bbox"]) >= 4]
    if heights and _median(heights) < 18:
        return True, "small_text_height"

    low_contrast_ratio = _low_contrast_ratio(records)
    if low_contrast_ratio is not None and low_contrast_ratio > 0.3:
        return True, f"low_contrast_ratio:{low_contrast_ratio:.3f}"

    hints = f"{item.kind} {item.layout_type} {item.motion_type} {item.notes}".lower()
    if any(token in hints for token in ("small", "tiny", "lowres", "low_res", "küçük", "kucuk", "minik", "ince")):
        return True, "manifest_small_text_hint"
    return False, "auto_not_needed"


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _low_contrast_ratio(records: list[dict[str, Any]], *, contrast_threshold: float = 0.12) -> float | None:
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return None

    checked = 0
    low = 0
    for record in records:
        bbox = record.get("bbox")
        frame = record.get("frame")
        if not bbox or len(bbox) < 4 or not frame:
            continue
        try:
            x, y, w, h = [int(round(float(value))) for value in bbox[:4]]
            if w <= 0 or h <= 0:
                continue
            with Image.open(frame) as image:
                gray = image.convert("L")
                crop = gray.crop((max(0, x), max(0, y), max(0, x + w), max(0, y + h)))
                if crop.width <= 1 or crop.height <= 1:
                    continue
                contrast = float(ImageStat.Stat(crop).stddev[0]) / 255.0
            checked += 1
            if contrast < contrast_threshold:
                low += 1
        except Exception:
            continue
    if not checked:
        return None
    return low / checked


def _effective_fps(item: CreditExperimentItem, cli_fps: float | None) -> tuple[float, str]:
    if cli_fps is not None:
        return cli_fps, "cli_override"
    if item.fps is not None:
        return item.fps, "manifest_override"
    motion = f"{item.motion_type} {item.kind} {item.layout_type}".lower()
    if any(token in motion for token in ("scroll", "rolling", "crawl", "kayan", "akan")):
        return DEFAULT_SCROLL_FPS, "adaptive_scroll"
    if any(token in motion for token in ("kj", "lower_third", "overlay", "alt bilgi")):
        return DEFAULT_KJ_FPS, "adaptive_kj"
    if any(token in motion for token in ("static", "sabit", "fade", "page")):
        return DEFAULT_STATIC_FPS, "adaptive_static"
    return DEFAULT_UNKNOWN_FPS, "adaptive_unknown"


def _expand_frames_for_columns(frames: list[Path], columns_dir: Path, column_count: int) -> list[dict[str, Any]]:
    samples = [{"path": frame, "source_frame": str(frame), "source_index": index, "column_index": None, "preprocess_variant": "raw"} for index, frame in enumerate(frames)]
    if column_count <= 1:
        return samples

    from PIL import Image

    columns_dir.mkdir(parents=True, exist_ok=True)
    expanded: list[dict[str, Any]] = []
    for index, frame in enumerate(frames):
        with Image.open(frame) as image:
            width, height = image.size
            for column_index in range(column_count):
                left = round(width * column_index / column_count)
                right = round(width * (column_index + 1) / column_count)
                out = columns_dir / f"{frame.stem}_col{column_index + 1:02d}{frame.suffix}"
                image.crop((left, 0, right, height)).save(out)
                expanded.append(
                    {
                        "path": out,
                        "source_frame": str(frame),
                        "source_index": index,
                        "column_index": column_index + 1,
                        "preprocess_variant": "raw",
                    }
                )
    return expanded


def _infer_credit_roi(frames: list[Path], item: CreditExperimentItem) -> tuple[int, int, int, int] | None:
    info = _infer_text_roi_info(frames, item)
    return _roi_tuple(info.get("roi"))


def _infer_text_roi_info(frames: list[Path], item: CreditExperimentItem) -> dict[str, Any]:
    if not frames:
        return {"status": "no_frames", "roi": None}
    hints = f"{item.kind} {item.layout_type} {item.motion_type} {item.notes}".lower()
    text_roi = _text_density_roi(frames, hints)
    if text_roi is not None and text_roi.get("roi"):
        return text_roi
    fallback = _fallback_hint_roi(frames, hints)
    if fallback is not None:
        return fallback
    motion_roi = _motion_density_roi(frames)
    if motion_roi is not None:
        return {
            "status": "detected",
            "strategy": "motion_density_fallback",
            "roi": list(motion_roi),
            "confidence": 0.35,
            "evidence": {"reason": "text_mask_unavailable_or_sparse"},
        }
    return {"status": "not_detected", "strategy": "none", "roi": None, "confidence": 0.0}


def _infer_second_pass_roi_info(frames: list[Path], records: list[dict[str, Any]], item: CreditExperimentItem) -> dict[str, Any]:
    if not frames:
        return {"status": "no_frames", "strategy": "ocr_bbox_second_pass", "roi": None, "confidence": 0.0}
    try:
        from PIL import Image
    except ImportError:
        return {"status": "unavailable", "strategy": "ocr_bbox_second_pass", "roi": None, "confidence": 0.0, "reason": "PIL_missing"}
    try:
        with Image.open(frames[0]) as image:
            width, height = image.size
    except Exception as exc:
        return {"status": "unavailable", "strategy": "ocr_bbox_second_pass", "roi": None, "confidence": 0.0, "reason": f"frame_size_unreadable:{exc}"}

    hints = f"{item.kind} {item.layout_type} {item.motion_type} {item.notes}".lower()
    mode = _roi_hint_mode(hints)
    boxes: list[tuple[float, float, float, float, float | None]] = []
    frame_count = len({str(record.get("frame") or "") for record in records if record.get("frame")})
    for record in records:
        text = str(record.get("text") or "").strip()
        bbox = record.get("bbox")
        if not text or not bbox or len(bbox) < 4:
            continue
        confidence = _float_or_none(record.get("confidence"))
        if confidence is not None and confidence < 0.22:
            continue
        if _text_alpha_ratio(text) < 0.28 and len(normalize_text(text)) < 4:
            continue
        try:
            x, y, w, h = [float(value) for value in bbox[:4]]
        except (TypeError, ValueError):
            continue
        if w <= 1 or h <= 1:
            continue
        if w > width * 0.92 or h > height * 0.45:
            continue
        x0 = max(0.0, min(float(width - 1), x))
        y0 = max(0.0, min(float(height - 1), y))
        x1 = max(x0 + 1.0, min(float(width), x + w))
        y1 = max(y0 + 1.0, min(float(height), y + h))
        boxes.append((x0, y0, x1, y1, confidence))

    min_boxes = 2 if mode == "lower_third" else 4
    if len(boxes) < min_boxes:
        mask_roi = _infer_mask_track_second_pass_roi_info(frames, item, width, height, mode=mode, prior_reason="too_few_ocr_boxes")
        if mask_roi.get("status") == "detected":
            mask_roi.setdefault("evidence", {})
            mask_roi["evidence"].update({"ocr_box_count": len(boxes), "ocr_min_boxes": min_boxes, "ocr_frame_count": frame_count})
            return mask_roi
        return _second_pass_skip(
            "too_few_ocr_boxes",
            {"box_count": len(boxes), "min_boxes": min_boxes, "frame_count": frame_count, "mask_track": mask_roi},
        )

    scroll_like = mode == "credit" and _is_explicit_scroll_hint(hints)
    if scroll_like and len(boxes) >= 8:
        x0 = _quantile([box[0] for box in boxes], 0.08)
        x1 = _quantile([box[2] for box in boxes], 0.92)
        y0 = 0.0
        y1 = float(height)
    else:
        x0 = min(box[0] for box in boxes)
        y0 = min(box[1] for box in boxes)
        x1 = max(box[2] for box in boxes)
        y1 = max(box[3] for box in boxes)
    box_widths = [box[2] - box[0] for box in boxes]
    box_heights = [box[3] - box[1] for box in boxes]
    pad_x = max(24, int(width * (0.055 if mode == "credit" else 0.04)), int(_median(box_widths) * 0.35))
    pad_y = max(18, int(height * (0.055 if mode == "credit" else 0.045)), int(_median(box_heights) * 1.25))
    if mode == "lower_third":
        pad_y = max(pad_y, int(height * 0.075))
    rx0 = max(0, int(math.floor(x0 - pad_x)))
    ry0 = max(0, int(math.floor(y0 - pad_y)))
    rx1 = min(width, int(math.ceil(x1 + pad_x)))
    ry1 = min(height, int(math.ceil(y1 + pad_y)))
    if mode == "lower_third":
        ry0 = max(0, min(ry0, int(height * 0.48)))
        ry1 = min(height, max(ry1, int(height * 0.72)))
    roi = _clamp_roi_min_size((rx0, ry0, rx1 - rx0, ry1 - ry0), width, height, mode=mode)
    if roi is None:
        mask_roi = _infer_mask_track_second_pass_roi_info(frames, item, width, height, mode=mode, prior_reason="invalid_ocr_roi_after_padding")
        if mask_roi.get("status") == "detected":
            return mask_roi
        return _second_pass_skip("invalid_roi_after_padding", {"box_count": len(boxes), "mask_track": mask_roi})

    area_ratio = (roi[2] * roi[3]) / max(1, width * height)
    width_ratio = roi[2] / max(1, width)
    height_ratio = roi[3] / max(1, height)
    if area_ratio > 0.88 and not (scroll_like and width_ratio < 0.86):
        evidence = {
            "box_count": len(boxes),
            "area_ratio": round(float(area_ratio), 4),
            "width_ratio": round(float(width_ratio), 4),
            "height_ratio": round(float(height_ratio), 4),
            "frame_count": frame_count,
            "scroll_like": scroll_like,
        }
        if len(boxes) < 16 or frame_count < 4:
            mask_roi = _infer_mask_track_second_pass_roi_info(frames, item, width, height, mode=mode, prior_reason="ocr_bbox_union_too_broad")
            if mask_roi.get("status") == "detected":
                mask_roi.setdefault("evidence", {})
                mask_roi["evidence"]["ocr_bbox_rejected"] = evidence
                return mask_roi
            evidence["mask_track"] = mask_roi
        else:
            evidence["mask_track"] = {
                "status": "skipped",
                "strategy": "text_mask_track_second_pass",
                "reason": "ocr_boxes_sufficient_do_not_override",
            }
        return _second_pass_skip("bbox_union_too_broad", evidence)
    if area_ratio < 0.012:
        mask_roi = _infer_mask_track_second_pass_roi_info(frames, item, width, height, mode=mode, prior_reason="ocr_bbox_union_too_tiny")
        if mask_roi.get("status") == "detected":
            return mask_roi
        return _second_pass_skip(
            "bbox_union_too_tiny",
            {"box_count": len(boxes), "area_ratio": round(float(area_ratio), 4), "frame_count": frame_count, "mask_track": mask_roi},
        )

    confidences = [box[4] for box in boxes if box[4] is not None]
    mean_confidence = sum(confidences) / len(confidences) if confidences else 0.55
    coverage_score = min(0.25, len(boxes) / 80.0) + min(0.15, frame_count / 20.0)
    tightness_score = max(0.0, min(0.20, (0.88 - area_ratio) * 0.32))
    confidence = min(0.95, 0.34 + min(0.26, mean_confidence * 0.26) + coverage_score + tightness_score)
    return {
        "status": "detected",
        "strategy": "ocr_bbox_second_pass",
        "roi": [int(roi[0]), int(roi[1]), int(roi[2]), int(roi[3])],
        "confidence": round(float(confidence), 4),
        "evidence": {
            "box_count": len(boxes),
            "frame_count": frame_count,
            "mean_ocr_confidence": round(float(mean_confidence), 4),
            "area_ratio": round(float(area_ratio), 4),
            "width_ratio": round(float(width_ratio), 4),
            "height_ratio": round(float(height_ratio), 4),
            "mode": mode,
            "scroll_like": scroll_like,
        },
    }


def _second_pass_skip(reason: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "skipped",
        "strategy": "ocr_bbox_second_pass",
        "roi": None,
        "confidence": 0.0,
        "reason": reason,
        "evidence": evidence or {},
    }


def _infer_mask_track_second_pass_roi_info(
    frames: list[Path],
    item: CreditExperimentItem,
    width: int,
    height: int,
    *,
    mode: str,
    prior_reason: str,
) -> dict[str, Any]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {
            "status": "skipped",
            "strategy": "text_mask_track_second_pass",
            "roi": None,
            "confidence": 0.0,
            "reason": "cv2_or_numpy_missing",
            "evidence": {"prior_reason": prior_reason},
        }

    hints = f"{item.kind} {item.layout_type} {item.motion_type} {item.notes}".lower()
    scroll_like = mode == "credit" and _is_explicit_scroll_hint(hints)
    sample_paths = _evenly_sample_paths(frames, min(len(frames), 18))
    if not sample_paths:
        return _mask_track_skip(prior_reason, "no_frames")

    lefts: list[float] = []
    rights: list[float] = []
    tops: list[float] = []
    bottoms: list[float] = []
    densities: list[float] = []
    component_counts: list[int] = []
    hit_frames = 0
    for path in sample_paths:
        image = _cv2_imread(cv2, np, path, cv2.IMREAD_COLOR)
        if image is None:
            continue
        if image.shape[:2] != (height, width):
            image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
        mask, count = _ocr_text_roi_mask(image, cv2, np)
        if mode == "lower_third":
            gate = np.zeros_like(mask)
            gate[int(height * 0.40) :, :] = 255
            mask = cv2.bitwise_and(mask, gate)
        active = int((mask > 0).sum())
        densities.append(active / max(1, width * height))
        component_counts.append(int(count))
        if active < max(20, int(width * height * 0.0006)):
            continue
        ys, xs = np.where(mask > 0)
        if len(xs) < 20:
            continue
        hit_frames += 1
        lefts.append(_quantile([float(value) for value in xs.tolist()], 0.03))
        rights.append(_quantile([float(value) for value in xs.tolist()], 0.97))
        tops.append(_quantile([float(value) for value in ys.tolist()], 0.04))
        bottoms.append(_quantile([float(value) for value in ys.tolist()], 0.96))

    min_hit_frames = 1 if mode == "lower_third" else 2
    if hit_frames < min_hit_frames or not lefts or not rights:
        return _mask_track_skip(
            prior_reason,
            "too_few_mask_hits",
            {
                "hit_frames": hit_frames,
                "sample_count": len(sample_paths),
                "mean_density": round(float(sum(densities) / max(1, len(densities))), 6),
                "mean_component_count": round(float(sum(component_counts) / max(1, len(component_counts))), 3),
            },
        )

    x0 = _quantile(lefts, 0.12)
    x1 = _quantile(rights, 0.88)
    if scroll_like:
        y0 = 0.0
        y1 = float(height)
    else:
        y0 = _quantile(tops, 0.10)
        y1 = _quantile(bottoms, 0.90)

    pad_x = max(24, int(width * (0.055 if mode == "credit" else 0.04)))
    pad_y = max(18, int(height * (0.055 if mode == "credit" else 0.060)))
    rx0 = max(0, int(math.floor(x0 - pad_x)))
    rx1 = min(width, int(math.ceil(x1 + pad_x)))
    ry0 = max(0, int(math.floor(y0 - pad_y)))
    ry1 = min(height, int(math.ceil(y1 + pad_y)))
    if mode == "lower_third":
        ry0 = max(0, min(ry0, int(height * 0.48)))
        ry1 = min(height, max(ry1, int(height * 0.70)))

    roi = _clamp_roi_min_size((rx0, ry0, rx1 - rx0, ry1 - ry0), width, height, mode=mode)
    if roi is None:
        return _mask_track_skip(prior_reason, "invalid_mask_roi", {"hit_frames": hit_frames, "sample_count": len(sample_paths)})

    area_ratio = (roi[2] * roi[3]) / max(1, width * height)
    width_ratio = roi[2] / max(1, width)
    height_ratio = roi[3] / max(1, height)
    mean_density = sum(densities) / max(1, len(densities))
    if mean_density > 0.32:
        return _mask_track_skip(
            prior_reason,
            "mask_density_too_high",
            {"hit_frames": hit_frames, "mean_density": round(float(mean_density), 6), "area_ratio": round(float(area_ratio), 4)},
        )
    if area_ratio > 0.90 and not (scroll_like and width_ratio < 0.88):
        return _mask_track_skip(
            prior_reason,
            "mask_roi_too_broad",
            {
                "hit_frames": hit_frames,
                "area_ratio": round(float(area_ratio), 4),
                "width_ratio": round(float(width_ratio), 4),
                "height_ratio": round(float(height_ratio), 4),
                "scroll_like": scroll_like,
            },
        )
    if area_ratio < 0.012:
        return _mask_track_skip(prior_reason, "mask_roi_too_tiny", {"hit_frames": hit_frames, "area_ratio": round(float(area_ratio), 4)})

    confidence = min(
        0.86,
        0.28
        + min(0.22, hit_frames / max(1, len(sample_paths)) * 0.30)
        + min(0.20, sum(component_counts) / max(1, len(component_counts)) / 110.0)
        + max(0.0, min(0.16, (0.90 - area_ratio) * 0.25))
        + min(0.12, mean_density * 1.4),
    )
    return {
        "status": "detected",
        "strategy": "text_mask_track_second_pass",
        "roi": [int(roi[0]), int(roi[1]), int(roi[2]), int(roi[3])],
        "confidence": round(float(confidence), 4),
        "reason": None,
        "evidence": {
            "prior_reason": prior_reason,
            "hit_frames": hit_frames,
            "sample_count": len(sample_paths),
            "mean_density": round(float(mean_density), 6),
            "mean_component_count": round(float(sum(component_counts) / max(1, len(component_counts))), 3),
            "area_ratio": round(float(area_ratio), 4),
            "width_ratio": round(float(width_ratio), 4),
            "height_ratio": round(float(height_ratio), 4),
            "mode": mode,
            "scroll_like": scroll_like,
        },
    }


def _mask_track_skip(prior_reason: str, reason: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"prior_reason": prior_reason}
    payload.update(evidence or {})
    return {
        "status": "skipped",
        "strategy": "text_mask_track_second_pass",
        "roi": None,
        "confidence": 0.0,
        "reason": reason,
        "evidence": payload,
    }


def _compose_roi(parent: tuple[int, int, int, int] | None, child: tuple[int, int, int, int] | None) -> tuple[int, int, int, int] | None:
    if child is None:
        return parent
    if parent is None:
        return child
    return (int(parent[0] + child[0]), int(parent[1] + child[1]), int(child[2]), int(child[3]))


def _clamp_roi_min_size(roi: tuple[int, int, int, int], width: int, height: int, *, mode: str) -> tuple[int, int, int, int] | None:
    x, y, w, h = roi
    if w <= 0 or h <= 0:
        return None
    min_w = int(width * (0.22 if mode == "lower_third" else 0.16))
    min_h = int(height * (0.10 if mode == "lower_third" else 0.12))
    x0 = max(0, min(width - 1, x))
    y0 = max(0, min(height - 1, y))
    x1 = max(x0 + 1, min(width, x + w))
    y1 = max(y0 + 1, min(height, y + h))
    if x1 - x0 < min_w:
        center = (x0 + x1) // 2
        x0 = max(0, center - min_w // 2)
        x1 = min(width, x0 + min_w)
        x0 = max(0, x1 - min_w)
    if y1 - y0 < min_h:
        center = (y0 + y1) // 2
        y0 = max(0, center - min_h // 2)
        y1 = min(height, y0 + min_h)
        y0 = max(0, y1 - min_h)
    return (int(x0), int(y0), int(x1 - x0), int(y1 - y0))


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) / 2.0)


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = max(0.0, min(1.0, q)) * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction)


def _text_alpha_ratio(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    alpha = sum(1 for char in stripped if char.isalpha())
    return alpha / max(1, len(stripped))


def _fallback_hint_roi(frames: list[Path], hints: str) -> dict[str, Any] | None:
    try:
        from PIL import Image
    except ImportError:
        return None

    first = frames[min(1, len(frames) - 1)]
    try:
        with Image.open(first) as image:
            width, height = image.size
    except Exception:
        return None

    if any(token in hints for token in ("kj", "lower_third", "overlay", "alt bilgi", "subtitle")):
        y = int(height * 0.54)
        return {
            "status": "fallback",
            "strategy": "hint_lower_band",
            "roi": [0, y, width, height - y],
            "confidence": 0.25,
            "evidence": {"reason": "kj_hint_no_text_mask"},
        }
    if any(token in hints for token in ("logo", "bug", "watermark")):
        return None
    if any(token in hints for token in ("scroll", "rolling", "crawl", "jenerik", "credit", "akan", "kayan")):
        x = int(width * 0.07)
        y = int(height * 0.04)
        return {
            "status": "fallback",
            "strategy": "hint_credit_safe_center_crop",
            "roi": [x, y, width - (2 * x), height - (2 * y)],
            "confidence": 0.22,
            "evidence": {"reason": "credit_hint_no_text_mask"},
        }
    return None


def _text_density_roi(frames: list[Path], hints: str) -> dict[str, Any] | None:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    sample_paths = _evenly_sample_paths(frames, min(len(frames), 12))
    images = []
    for path in sample_paths:
        image = _cv2_imread(cv2, np, path, cv2.IMREAD_COLOR)
        if image is not None:
            images.append(image)
    if not images:
        return None
    height, width = images[0].shape[:2]
    masks = []
    component_counts = []
    for image in images:
        if image.shape[:2] != (height, width):
            image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
        mask, count = _ocr_text_roi_mask(image, cv2, np)
        masks.append(mask)
        component_counts.append(count)
    if not masks:
        return None
    union = np.zeros_like(masks[0])
    for mask in masks:
        union = cv2.bitwise_or(union, mask)

    mode = _roi_hint_mode(hints)
    if mode == "lower_third":
        lower_gate = np.zeros_like(union)
        lower_gate[int(height * 0.42) :, :] = 255
        gated = cv2.bitwise_and(union, lower_gate)
        if int((gated > 0).sum()) >= 24:
            union = gated
    roi = _roi_from_mask(union, width, height, mode=mode)
    density = float((union > 0).sum() / max(1, union.size))
    if roi is None:
        return None
    x, y, w, h = roi
    area_ratio = (w * h) / max(1, width * height)
    if mode != "lower_third" and (density > 0.22 or area_ratio > 0.82):
        return None
    confidence = min(0.92, 0.34 + min(0.30, density * 18.0) + min(0.18, sum(component_counts) / max(1, len(component_counts)) / 90.0) + min(0.10, area_ratio))
    return {
        "status": "detected",
        "strategy": f"text_density_{mode}",
        "roi": [int(x), int(y), int(w), int(h)],
        "confidence": round(float(confidence), 4),
        "evidence": {
            "frame_count": len(images),
            "text_pixel_density": round(float(density), 6),
            "mean_component_count": round(float(sum(component_counts) / max(1, len(component_counts))), 3),
            "area_ratio": round(float(area_ratio), 4),
            "mode": mode,
        },
    }


def _roi_hint_mode(hints: str) -> str:
    if any(token in hints for token in ("kj", "lower_third", "overlay", "alt bilgi", "subtitle")):
        return "lower_third"
    if any(token in hints for token in ("logo", "bug", "watermark")):
        return "logo"
    if any(token in hints for token in ("scroll", "rolling", "crawl", "jenerik", "credit", "akan", "kayan")):
        return "credit"
    return "generic"


def _evenly_sample_paths(paths: list[Path], limit: int) -> list[Path]:
    if len(paths) <= limit:
        return list(paths)
    if limit <= 1:
        return [paths[len(paths) // 2]]
    step = (len(paths) - 1) / (limit - 1)
    return [paths[round(index * step)] for index in range(limit)]


def _ocr_text_roi_mask(image: Any, cv2: Any, np: Any) -> tuple[Any, int]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    blur = cv2.GaussianBlur(gray, (0, 0), 3)
    local = cv2.absdiff(gray, blur)
    local_threshold = max(6.0, float(local.mean()) + float(local.std()) * 0.95)
    bright_gate = gray > max(52.0, float(gray.mean()) + float(gray.std()) * 0.18)
    bright = ((local > local_threshold) & bright_gate).astype(np.uint8) * 255
    saturated = ((hsv[:, :, 1] > 65) & (hsv[:, :, 2] > 70) & (local > max(5.0, local_threshold * 0.50))).astype(np.uint8) * 255
    edges = cv2.Canny(gray, 60, 160)
    mask = cv2.bitwise_or(bright, saturated)
    mask = cv2.bitwise_or(mask, cv2.bitwise_and(cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1), cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=1)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    return _filter_roi_components(mask, cv2, np)


def _filter_roi_components(mask: Any, cv2: Any, np: Any) -> tuple[Any, int]:
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=8)
    if count <= 1:
        return mask, 0
    height, width = mask.shape[:2]
    filtered = np.zeros_like(mask)
    kept = 0
    max_area = max(60, int(width * height * 0.012))
    for label in range(1, count):
        x, y, w, h, area = stats[label]
        if area < 3 or area > max_area:
            continue
        if w > width * 0.70 or h > height * 0.16:
            continue
        aspect = w / max(1, h)
        if aspect > 40 or aspect < 0.03:
            continue
        filtered[labels == label] = 255
        kept += 1
    filtered = cv2.dilate(filtered, np.ones((7, 9), np.uint8), iterations=1)
    return filtered, kept


def _roi_from_mask(mask: Any, width: int, height: int, *, mode: str) -> tuple[int, int, int, int] | None:
    import cv2
    import numpy as np

    ys, xs = np.where(mask > 0)
    if len(xs) < 16:
        return None
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    pad_x = max(18, int(width * (0.025 if mode != "lower_third" else 0.035)))
    pad_y = max(12, int(height * (0.030 if mode != "lower_third" else 0.045)))
    if mode == "credit":
        pad_x = max(pad_x, int(width * 0.04))
        pad_y = max(pad_y, int(height * 0.04))
    x0 = max(0, x0 - pad_x)
    y0 = max(0, y0 - pad_y)
    x1 = min(width - 1, x1 + pad_x)
    y1 = min(height - 1, y1 + pad_y)
    if mode == "lower_third":
        y0 = max(0, min(y0, int(height * 0.42)))
        y1 = min(height - 1, max(y1, int(height * 0.70)))
    w = x1 - x0 + 1
    h = y1 - y0 + 1
    min_w = int(width * (0.20 if mode == "lower_third" else 0.16))
    min_h = int(height * (0.08 if mode == "lower_third" else 0.10))
    if w < min_w:
        center = (x0 + x1) // 2
        x0 = max(0, center - min_w // 2)
        x1 = min(width - 1, x0 + min_w)
        x0 = max(0, x1 - min_w)
    if h < min_h:
        center = (y0 + y1) // 2
        y0 = max(0, center - min_h // 2)
        y1 = min(height - 1, y0 + min_h)
        y0 = max(0, y1 - min_h)
    w = x1 - x0 + 1
    h = y1 - y0 + 1
    if w * h < width * height * 0.015:
        return None
    return (int(x0), int(y0), int(w), int(h))


def _roi_tuple(value: Any) -> tuple[int, int, int, int] | None:
    if isinstance(value, (list, tuple)) and len(value) == 4:
        try:
            x, y, w, h = [int(round(float(part))) for part in value]
        except (TypeError, ValueError):
            return None
        if w > 0 and h > 0:
            return (x, y, w, h)
    return None


def _auto_roi_summary(info: dict[str, Any] | None) -> dict[str, Any] | None:
    if not info:
        return None
    return {
        "status": info.get("status"),
        "strategy": info.get("strategy"),
        "roi": info.get("roi"),
        "confidence": info.get("confidence"),
        "reason": info.get("reason"),
        "evidence": info.get("evidence"),
    }


def _motion_density_roi(frames: list[Path]) -> tuple[int, int, int, int] | None:
    if len(frames) < 3:
        return None
    try:
        from PIL import Image, ImageChops, ImageStat
    except ImportError:
        return None
    sample_paths = frames[: min(len(frames), 8)]
    try:
        grays = [Image.open(path).convert("L").resize((160, 90)) for path in sample_paths]
    except Exception:
        return None
    if len(grays) < 2:
        return None
    diff = Image.new("L", grays[0].size, 0)
    for prev, cur in zip(grays, grays[1:]):
        diff = ImageChops.lighter(diff, ImageChops.difference(prev, cur))
    stat = ImageStat.Stat(diff)
    if not stat.mean or stat.mean[0] < 4.0:
        return None
    # Text credits usually live away from overscan; use a broad center crop as
    # a safe first-pass ROI rather than a fragile tiny box.
    with Image.open(sample_paths[0]) as image:
        width, height = image.size
    x = int(width * 0.04)
    y = int(height * 0.08)
    return (x, y, width - (2 * x), int(height * 0.86))


def _preprocess_frame_samples(samples: list[Any], preprocess_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    except ImportError as exc:
        return [], [f"preprocess_unavailable:{exc}"]

    preprocess_dir.mkdir(parents=True, exist_ok=True)
    out_samples: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, sample in enumerate(samples):
        path = _sample_path(sample)
        try:
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image.convert("RGB"))
                base = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
                variants = _preprocess_variants(base, ImageEnhance, ImageFilter, ImageOps)
                for variant, variant_image in variants.items():
                    out = preprocess_dir / f"{path.stem}_{variant}.png"
                    variant_image.save(out)
                    out_samples.append(
                        {
                            "path": out,
                            "source_frame": _sample_metadata(sample).get("source_frame") or str(path),
                            "source_index": _sample_source_index(sample, index),
                            "column_index": _sample_metadata(sample).get("column_index"),
                            "preprocess_variant": variant,
                        }
                    )
        except Exception as exc:
            warnings.append(f"preprocess_failed:{path.name}:{exc}")
    return out_samples, warnings


def _preprocess_variants(base: Any, ImageEnhance: Any, ImageFilter: Any, ImageOps: Any) -> dict[str, Any]:
    variants: dict[str, Any] = {"upscale2x": base}
    variants["clahe2x"] = _clahe_variant(base, ImageOps, ImageEnhance)
    variants["sharpen2x"] = base.filter(ImageFilter.SHARPEN)
    variants["unsharp_glow_reduction2x"] = base.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=4))
    variants["adaptive_threshold2x"] = _adaptive_threshold_variant(base)
    variants["light_on_dark2x"] = base
    variants["dark_on_light_inverted2x"] = ImageOps.invert(base)
    variants["deinterlace_blend2x"] = _deinterlace_blend_variant(base)
    return variants


def _clahe_variant(image: Any, ImageOps: Any, ImageEnhance: Any) -> Any:
    try:
        import cv2
        import numpy as np
        from PIL import Image

        rgb = np.array(image.convert("RGB"))
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_l = clahe.apply(l_channel)
        enhanced = cv2.merge((enhanced_l, a_channel, b_channel))
        enhanced_rgb = cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)
        return ImageOps.autocontrast(Image.fromarray(enhanced_rgb), cutoff=1)
    except Exception:
        autocontrast = ImageOps.autocontrast(image, cutoff=1)
        return ImageEnhance.Contrast(autocontrast).enhance(1.35)


def _adaptive_threshold_variant(image: Any) -> Any:
    from PIL import Image, ImageOps

    gray = image.convert("L")
    try:
        import cv2
        import numpy as np

        array = np.array(gray)
        threshold = cv2.adaptiveThreshold(array, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 5)
        return ImageOps.colorize(Image.fromarray(threshold), black="black", white="white")
    except Exception:
        return gray.point(lambda value: 255 if value > 150 else 0).convert("RGB")


def _deinterlace_blend_variant(image: Any) -> Any:
    # Field blending softens line twitter on interlaced SD credits without
    # changing geometry as aggressively as a full video deinterlace pass.
    from PIL import Image

    even = image.copy()
    odd = image.copy()
    width, height = image.size
    for y in range(1, height, 2):
        source_y = max(0, y - 1)
        row = even.crop((0, source_y, width, source_y + 1))
        odd.paste(row, (0, y))
    return Image.blend(image, odd, 0.35)


def _sample_path(sample: Any) -> Path:
    if isinstance(sample, dict):
        return Path(sample["path"])
    return Path(sample)


def _sample_source_index(sample: Any, fallback_index: int) -> int:
    if isinstance(sample, dict):
        return int(sample.get("source_index", fallback_index))
    return fallback_index


def _sample_metadata(sample: Any) -> dict[str, Any]:
    if not isinstance(sample, dict):
        return {}
    return {
        "source_frame": sample.get("source_frame"),
        "column_index": sample.get("column_index"),
        "preprocess_variant": sample.get("preprocess_variant"),
    }


def _engine_call_costs(records: list[dict[str, Any]]) -> dict[str, Any]:
    costs: dict[str, dict[str, Any]] = {}
    for record in records:
        engine = str(record.get("engine") or "unknown")
        entry = costs.setdefault(engine, {"records": 0, "runtime_sec": 0.0})
        if str(record.get("text") or "").strip():
            entry["records"] += 1
        entry["runtime_sec"] = round(max(float(entry["runtime_sec"]), float(record.get("engine_runtime_sec") or 0.0)), 3)
    return costs


def _extract_segment_frames(
    input_path: Path,
    frames_dir: Path,
    *,
    start_seconds: float,
    end_seconds: float,
    fps: float,
    max_frames: int | None,
    ffmpeg_executable: str,
) -> list[Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    for existing in frames_dir.glob("frame_*.png"):
        existing.unlink()

    pattern = frames_dir / "frame_%05d.png"
    duration = max(0.001, end_seconds - start_seconds)
    command = [
        ffmpeg_executable,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(start_seconds),
        "-t",
        str(duration),
        "-i",
        str(input_path),
        "-vf",
        f"yadif=mode=send_frame:parity=auto:deint=interlaced,fps={max(fps, 0.001)}",
    ]
    if max_frames is not None:
        command.extend(["-frames:v", str(max(1, max_frames))])
    command.append(str(pattern))
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "ffmpeg frame extraction failed").strip())
    return sorted(frames_dir.glob("frame_*.png"))


def _crop_frames(frames: list[Path], crops_dir: Path, roi: tuple[int, int, int, int]) -> list[Path]:
    from PIL import Image

    crops_dir.mkdir(parents=True, exist_ok=True)
    x, y, w, h = roi
    cropped: list[Path] = []
    for frame in frames:
        out = crops_dir / frame.name
        with Image.open(frame) as image:
            image.crop((x, y, x + w, y + h)).save(out)
        cropped.append(out)
    return cropped


def _build_engines(engine_names: list[str], factories: dict[str, EngineFactory]) -> tuple[list[OcrEngine], dict[str, Any]]:
    active: list[OcrEngine] = []
    status: dict[str, Any] = {}
    for name in engine_names:
        factory = factories.get(name)
        if factory is None:
            status[name] = {"available": False, "error": "No engine factory configured"}
            continue
        started = perf_counter()
        try:
            engine = factory()
            active.append(engine)
            status[name] = {"available": True, "runtime_sec": round(perf_counter() - started, 3)}
            metadata = getattr(engine, "metadata", None)
            if callable(metadata):
                status[name]["metadata"] = metadata()
        except Exception as exc:
            status[name] = {"available": False, "error": str(exc), "runtime_sec": round(perf_counter() - started, 3)}
    return active, status


def _ocr_record(
    engine: str,
    strategy: str,
    image_path: Path,
    timestamp_seconds: float | None,
    bbox: list[float] | None,
    text: str,
    confidence: float | None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "engine": engine,
        "strategy": strategy,
        "frame": str(image_path),
        "timestamp_seconds": timestamp_seconds,
        "bbox": bbox,
        "text": text,
        "confidence": confidence,
        "normalized_text": normalize_text(text),
        "line_group_id": None,
        "warnings": warnings or [],
    }


def _records_from_paddle(raw: Any, image_path: Path, engine: str, strategy: str, timestamp_seconds: float | None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in _flatten_paddle_items(raw):
        bbox, text, conf = item
        if text:
            records.append(_ocr_record(engine, strategy, image_path, timestamp_seconds, bbox, text, conf))
    return records


def _flatten_paddle_items(raw: Any) -> list[tuple[list[float] | None, str, float | None]]:
    items: list[tuple[list[float] | None, str, float | None]] = []
    if raw is None:
        return items
    if isinstance(raw, dict):
        texts = raw.get("rec_texts") or raw.get("texts") or []
        scores = raw.get("rec_scores") or raw.get("scores") or []
        boxes = raw.get("dt_polys") or raw.get("rec_polys") or raw.get("boxes") or []
        for index, text in enumerate(texts):
            items.append((_bbox_from_any(boxes[index] if index < len(boxes) else None), str(text), _float_or_none(scores[index] if index < len(scores) else None)))
        return items
    if isinstance(raw, list):
        for element in raw:
            if isinstance(element, dict):
                items.extend(_flatten_paddle_items(element))
            elif isinstance(element, list):
                if len(element) == 2 and isinstance(element[1], (tuple, list)) and len(element[1]) >= 1 and isinstance(element[1][0], str):
                    text = str(element[1][0])
                    conf = _float_or_none(element[1][1] if len(element[1]) > 1 else None)
                    items.append((_bbox_from_any(element[0]), text, conf))
                else:
                    items.extend(_flatten_paddle_items(element))
    return items


def _records_from_oneocr(raw: Any, image_path: Path, engine: str, strategy: str, timestamp_seconds: float | None) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        lines = raw.get("lines") or []
        if lines:
            records = []
            for line in lines:
                if isinstance(line, dict):
                    records.append(
                        _ocr_record(
                            engine,
                            strategy,
                            image_path,
                            timestamp_seconds,
                            _bbox_from_any(line.get("bounding_rect") or line.get("bbox") or line.get("box")),
                            str(line.get("text") or ""),
                            _float_or_none(line.get("confidence")) or _mean_oneocr_word_confidence(line),
                        )
                    )
                else:
                    records.append(_ocr_record(engine, strategy, image_path, timestamp_seconds, None, str(line), None))
            return [record for record in records if record["text"].strip()]
        text = str(raw.get("text") or "")
        return [_ocr_record(engine, strategy, image_path, timestamp_seconds, None, text, None)] if text.strip() else []
    text = str(raw or "")
    return [_ocr_record(engine, strategy, image_path, timestamp_seconds, None, text, None)] if text.strip() else []


def _mean_oneocr_word_confidence(line: dict[str, Any]) -> float | None:
    values = []
    for word in line.get("words") or []:
        if isinstance(word, dict) and _float_or_none(word.get("confidence")) is not None:
            values.append(float(word["confidence"]))
    return round(sum(values) / len(values), 6) if values else None


def _bbox_from_any(value: Any) -> list[float] | None:
    if value is None:
        return None
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, dict):
        keys = ["x", "y", "width", "height"]
        if all(key in value for key in keys):
            return [float(value["x"]), float(value["y"]), float(value["width"]), float(value["height"])]
        keys = ["left", "top", "right", "bottom"]
        if all(key in value for key in keys):
            return [float(value["left"]), float(value["top"]), float(value["right"]) - float(value["left"]), float(value["bottom"]) - float(value["top"])]
        corner_keys = ["x1", "y1", "x2", "y2", "x3", "y3", "x4", "y4"]
        if all(key in value for key in corner_keys):
            value = [
                [value["x1"], value["y1"]],
                [value["x2"], value["y2"]],
                [value["x3"], value["y3"]],
                [value["x4"], value["y4"]],
            ]
    if isinstance(value, (tuple, list)) and len(value) == 4 and all(_float_or_none(part) is not None for part in value):
        left, top, right, bottom = [float(part) for part in value]
        return [round(left, 3), round(top, 3), round(max(0.0, right - left), 3), round(max(0.0, bottom - top), 3)]
    points: list[tuple[float, float]] = []
    try:
        for point in value:
            if hasattr(point, "tolist"):
                point = point.tolist()
            try:
                if len(point) >= 2:
                    points.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                continue
    except TypeError:
        return None
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return [round(min(xs), 3), round(min(ys), 3), round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)]


def _records_by_frame(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_frame: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_frame.setdefault(str(record.get("frame") or ""), []).append(record)
    return by_frame


def _build_text_mask(cv2: Any, np: Any, gray: Any, records: list[dict[str, Any]]) -> Any:
    mask = np.zeros(gray.shape, dtype=np.uint8)
    h, w = gray.shape[:2]
    for record in records:
        bbox = record.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        x, y, bw, bh = [int(round(float(v))) for v in bbox[:4]]
        x = max(0, min(w - 1, x))
        y = max(0, min(h - 1, y))
        bw = max(1, min(w - x, bw))
        bh = max(1, min(h - y, bh))
        cv2.rectangle(mask, (x, y), (x + bw, y + bh), 255, thickness=-1)

    median = float(np.median(gray))
    std = float(np.std(gray))
    contrast = np.abs(gray.astype(np.float32) - median)
    contrast_mask = (contrast > max(25.0, std * 1.25)).astype(np.uint8) * 255
    if mask.max() > 0:
        mask = cv2.bitwise_or(mask, contrast_mask)
    else:
        mask = contrast_mask
    kernel = np.ones((3, 3), dtype=np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def _phase_shift(cv2: Any, np: Any, gray_a: Any, gray_b: Any, *, mask_a: Any | None = None, mask_b: Any | None = None) -> tuple[float, float, float, float | None]:
    a = gray_a.astype(np.float32)
    b = gray_b.astype(np.float32)
    if mask_a is not None:
        a = a * (mask_a.astype(np.float32) / 255.0)
    if mask_b is not None:
        b = b * (mask_b.astype(np.float32) / 255.0)
    if float(np.std(a)) < 1e-6 or float(np.std(b)) < 1e-6:
        return 0.0, 0.0, 0.0, None
    (dx, dy), response = cv2.phaseCorrelate(a, b)
    if not np.isfinite(dx) or not np.isfinite(dy):
        return 0.0, 0.0, 0.0, None
    return float(dx), float(dy), float(response), _phase_peak_ratio(np, a, b)


def _phase_peak_ratio(np: Any, a: Any, b: Any) -> float | None:
    try:
        fa = np.fft.fft2(a)
        fb = np.fft.fft2(b)
        cross_power = fa * np.conj(fb)
        cross_power /= np.abs(cross_power) + 1e-9
        corr = np.abs(np.fft.ifft2(cross_power))
        peak_index = np.unravel_index(np.argmax(corr), corr.shape)
        peak = float(corr[peak_index])
        y, x = peak_index
        y0, y1 = max(0, y - 4), min(corr.shape[0], y + 5)
        x0, x1 = max(0, x - 4), min(corr.shape[1], x + 5)
        corr[y0:y1, x0:x1] = 0
        second = float(np.max(corr))
        if second <= 1e-12:
            return None
        return round(peak / second, 4)
    except Exception:
        return None


def _read_gray(cv2: Any, path: Path) -> Any:
    _, np = _import_cv2_numpy()
    image = _cv2_imread(cv2, np, path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not read frame: {path}")
    return image


def _cv2_imread(cv2: Any, np: Any, path: Path, flags: int) -> Any:
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size > 0:
            image = cv2.imdecode(data, flags)
            if image is not None:
                return image
    except Exception:
        pass
    return cv2.imread(str(path), flags)


def _cv2_imwrite(cv2: Any, path: Path, image: Any) -> None:
    ok = cv2.imwrite(str(path), image)
    if ok:
        return
    ext = path.suffix or ".png"
    success, encoded = cv2.imencode(ext, image)
    if not success:
        raise RuntimeError(f"Could not write image: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded.tofile(str(path))


def _import_cv2_numpy() -> tuple[Any, Any]:
    import cv2
    import numpy as np

    return cv2, np


def _mean_shift(shifts: list[dict[str, Any]], x_key: str, y_key: str) -> tuple[float, float]:
    if not shifts:
        return 0.0, 0.0
    return (
        sum(float(shift.get(x_key) or 0.0) for shift in shifts) / len(shifts),
        sum(float(shift.get(y_key) or 0.0) for shift in shifts) / len(shifts),
    )


def _background_motion_warning(text_shift: tuple[float, float], global_shift: tuple[float, float]) -> bool:
    diff = math.hypot(text_shift[0] - global_shift[0], text_shift[1] - global_shift[1])
    return diff > 2.0 and math.hypot(global_shift[0], global_shift[1]) > 1.0


def _phase_quality_gate(shifts: list[dict[str, Any]]) -> dict[str, Any]:
    responses = [float(shift["response"]) for shift in shifts if _is_number(shift.get("response"))]
    ratios = [float(shift["peak_to_second_peak_ratio"]) for shift in shifts if _is_number(shift.get("peak_to_second_peak_ratio"))]
    mean_response = sum(responses) / len(responses) if responses else None
    mean_ratio = sum(ratios) / len(ratios) if ratios else None
    passed = bool(mean_response is not None and mean_response >= 0.2 and (mean_ratio is None or mean_ratio >= 1.15))
    return {
        "status": "pass" if passed else "review",
        "mean_response": round(mean_response, 6) if mean_response is not None else None,
        "mean_peak_to_second_peak_ratio": round(mean_ratio, 4) if mean_ratio is not None else None,
        "rule": "review if mean phase response < 0.2 or peak/second-peak ratio < 1.15",
    }


def _orientation_from_positions(positions: list[tuple[float, float]]) -> str:
    if len(positions) < 2:
        return "unknown"
    xs = [x for x, _ in positions]
    ys = [y for _, y in positions]
    spread_x = max(xs) - min(xs)
    spread_y = max(ys) - min(ys)
    if spread_y > spread_x * 1.5 and spread_y > 1:
        return "vertical"
    if spread_x > spread_y * 1.5 and spread_x > 1:
        return "horizontal"
    return "mixed_or_static"


def _canvas_advantage(frame_records: list[dict[str, Any]], temporal: dict[str, Any], canvas_records: list[dict[str, Any]], ground_truth: tuple[str, ...] = ()) -> dict[str, Any]:
    frame_lines = set(_dedupe_record_texts(frame_records))
    canvas_lines = set(_dedupe_record_texts(canvas_records))
    confidences = [float(record["confidence"]) for record in canvas_records if _is_number(record.get("confidence"))]
    truth = set(_normalized_truth(ground_truth))
    frame_truth_hits = frame_lines & truth
    canvas_truth_hits = canvas_lines & truth
    notes = []
    if len(canvas_lines) > len(frame_lines):
        notes.append("canvas_produced_more_unique_lines")
    if not canvas_lines:
        notes.append("canvas_ocr_empty_or_unavailable")
    return {
        "unique_lines": len(canvas_lines),
        "frame_unique_lines": len(frame_lines),
        "unique_lines_recovered": max(0, len(canvas_lines - frame_lines)),
        "ground_truth_recovered_delta": len(canvas_truth_hits - frame_truth_hits) if truth else None,
        "stable_groups": temporal.get("stable_groups", 0),
        "mean_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
        "manual_review_notes": notes or ["review_canvas_against_frame_ocr"],
    }


def _evaluate_item_strategies(
    item: CreditExperimentItem,
    frame_ocr: dict[str, Any],
    preprocessed_ocr: dict[str, Any],
    temporal: dict[str, Any],
    preprocessed_temporal: dict[str, Any],
    canvas_records: list[dict[str, Any]],
    *,
    temporal_fusion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    truth = _normalized_truth(item.ground_truth)
    rows: list[dict[str, Any]] = []

    fusion_records: list[dict[str, Any]] = []
    fusion_strategy_label = "temporal_fusion"
    if isinstance(temporal_fusion, dict) and temporal_fusion.get("status") == "done":
        fusion_records = list(temporal_fusion.get("ocr_records") or [])
        fusion_strategy_label = str(temporal_fusion.get("strategy") or "temporal_fusion")

    strategy_candidates = {
        "frame_ocr": _candidate_lines_by_engine(frame_ocr.get("records", [])),
        "preprocessed_frame_ocr": _candidate_lines_by_engine(preprocessed_ocr.get("records", [])),
        "temporal_voting": _candidate_lines_from_groups_by_engine(temporal.get("groups", [])),
        "preprocessed_temporal_voting": _candidate_lines_from_groups_by_engine(preprocessed_temporal.get("groups", [])),
        "descroll_canvas_ocr": _candidate_lines_by_engine(canvas_records),
        fusion_strategy_label: _candidate_lines_by_engine(fusion_records),
    }
    confidence_by_strategy = {
        "frame_ocr": _mean_confidence_by_engine(frame_ocr.get("records", [])),
        "preprocessed_frame_ocr": _mean_confidence_by_engine(preprocessed_ocr.get("records", [])),
        "descroll_canvas_ocr": _mean_confidence_by_engine(canvas_records),
        fusion_strategy_label: _mean_confidence_by_engine(fusion_records),
    }
    for strategy, by_engine in strategy_candidates.items():
        for engine, candidates in by_engine.items():
            row = {
                "engine": engine,
                "strategy": strategy,
                "candidate_count": len(candidates),
                "candidates": candidates[:200],
                "confidence_mean": confidence_by_strategy.get(strategy, {}).get(engine),
                "vlm_fallback_candidate_count": _low_confidence_count_for_strategy(strategy, engine, frame_ocr, preprocessed_ocr, canvas_records),
            }
            row.update(_score_candidates(candidates, truth))
            rows.append(row)

    rows = _add_strategy_deltas(rows)
    return {
        "ground_truth_count": len(truth),
        "ground_truth_available": bool(truth),
        "normalization_policy": NORMALIZATION_POLICY,
        "rows": rows,
        "summary": _evaluation_summary(rows, truth),
    }


def _score_candidates(candidates: list[str], truth: list[str], *, threshold: float = 0.86) -> dict[str, Any]:
    candidates = _dedupe_texts(candidates)
    truth = _dedupe_texts(truth)
    if not truth:
        return {
            "metric_status": "no_ground_truth",
            "true_positives": None,
            "false_positives": None,
            "false_negatives": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "matched": [],
            "missed_truth": [],
            "extra_candidates": candidates,
        }

    pairs: list[tuple[float, str, str]] = []
    for candidate in candidates:
        for expected in truth:
            score = SequenceMatcher(None, candidate, expected).ratio()
            if score >= threshold:
                pairs.append((score, candidate, expected))
    pairs.sort(reverse=True)
    used_candidates: set[str] = set()
    used_truth: set[str] = set()
    matched = []
    for score, candidate, expected in pairs:
        if candidate in used_candidates or expected in used_truth:
            continue
        used_candidates.add(candidate)
        used_truth.add(expected)
        matched.append({"candidate": candidate, "ground_truth": expected, "similarity": round(score, 4)})

    tp = len(matched)
    fp = len(candidates) - tp
    fn = len(truth) - tp
    precision = tp / len(candidates) if candidates else 0.0
    recall = tp / len(truth) if truth else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    total_chars = sum(len(item["ground_truth"]) for item in matched)
    edits = sum(_edit_distance(item["candidate"], item["ground_truth"]) for item in matched)
    return {
        "metric_status": "scored",
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "character_error_rate": round(edits / total_chars, 4) if total_chars else None,
        "matched": matched,
        "missed_truth": [item for item in truth if item not in used_truth],
        "extra_candidates": [item for item in candidates if item not in used_candidates],
    }


def _edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (0 if left_char == right_char else 1),
                )
            )
        previous = current
    return previous[-1]


def _normalized_truth(lines: tuple[str, ...] | list[str]) -> list[str]:
    return _dedupe_texts([normalize_text(line) for line in lines if normalize_text(line)])


def _dedupe_record_texts(records: list[dict[str, Any]]) -> list[str]:
    return _dedupe_texts([str(record.get("normalized_text") or normalize_text(str(record.get("text") or ""))) for record in records if str(record.get("text") or "").strip()])


def _dedupe_texts(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        normalized = normalize_text(line)
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def _candidate_lines_by_engine(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_engine: dict[str, list[str]] = {}
    for record in records:
        text = str(record.get("normalized_text") or normalize_text(str(record.get("text") or "")))
        if not text:
            continue
        by_engine.setdefault(str(record.get("engine") or "unknown"), []).append(text)
    return {engine: _dedupe_texts(lines) for engine, lines in by_engine.items()}


def _candidate_lines_from_groups_by_engine(groups: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_engine: dict[str, list[str]] = {}
    for group in groups:
        text = str(group.get("winner_normalized_text") or normalize_text(str(group.get("winner_text") or "")))
        if not text:
            continue
        by_engine.setdefault(str(group.get("engine") or "unknown"), []).append(text)
    return {engine: _dedupe_texts(lines) for engine, lines in by_engine.items()}


def _mean_confidence_by_engine(records: list[dict[str, Any]]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for record in records:
        if _is_number(record.get("confidence")):
            buckets.setdefault(str(record.get("engine") or "unknown"), []).append(float(record["confidence"]))
    return {engine: round(sum(values) / len(values), 4) for engine, values in buckets.items() if values}


def _low_confidence_count_for_strategy(
    strategy: str,
    engine: str,
    frame_ocr: dict[str, Any],
    preprocessed_ocr: dict[str, Any],
    canvas_records: list[dict[str, Any]],
    *,
    threshold: float = 0.7,
) -> int:
    if strategy == "frame_ocr":
        records = frame_ocr.get("records", [])
    elif strategy == "preprocessed_frame_ocr":
        records = preprocessed_ocr.get("records", [])
    elif strategy == "descroll_canvas_ocr":
        records = canvas_records
    else:
        return 0
    return sum(
        1
        for record in records
        if record.get("engine") == engine and str(record.get("text") or "").strip() and _is_number(record.get("confidence")) and float(record["confidence"]) < threshold
    )


def _add_strategy_deltas(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline_by_engine = {(row["engine"]): row for row in rows if row.get("strategy") == "frame_ocr"}
    out = []
    for row in rows:
        enriched = dict(row)
        baseline = baseline_by_engine.get(str(row.get("engine")))
        if baseline and row.get("metric_status") == "scored" and baseline.get("metric_status") == "scored":
            enriched["delta_vs_frame_ocr"] = {
                "precision": _metric_delta(row.get("precision"), baseline.get("precision")),
                "recall": _metric_delta(row.get("recall"), baseline.get("recall")),
                "f1": _metric_delta(row.get("f1"), baseline.get("f1")),
            }
        else:
            enriched["delta_vs_frame_ocr"] = None
        out.append(enriched)
    return out


def _metric_delta(value: Any, baseline: Any) -> float | None:
    if value is None or baseline is None:
        return None
    return round(float(value) - float(baseline), 4)


def _evaluation_summary(rows: list[dict[str, Any]], truth: list[str]) -> dict[str, Any]:
    scored = [row for row in rows if row.get("metric_status") == "scored"]
    if not truth:
        return {"metric_status": "no_ground_truth", "best_by_f1": None}
    if not scored:
        return {"metric_status": "no_scored_rows", "best_by_f1": None}
    best = max(scored, key=lambda row: (float(row.get("f1") or 0.0), float(row.get("recall") or 0.0), float(row.get("precision") or 0.0)))
    return {
        "metric_status": "scored",
        "best_by_f1": {
            "engine": best.get("engine"),
            "strategy": best.get("strategy"),
            "precision": best.get("precision"),
            "recall": best.get("recall"),
            "f1": best.get("f1"),
        },
    }


def _category_rollups(items: list[dict[str, Any]]) -> dict[str, Any]:
    rollups: dict[str, Any] = {}
    for key in ("kind", "layout_type", "motion_type"):
        buckets: dict[str, dict[str, Any]] = {}
        for item in items:
            value = str(item.get(key) or "unknown")
            bucket = buckets.setdefault(value, {"items": 0, "done": 0, "ground_truth_items": 0, "mean_runtime_sec": 0.0, "mean_best_f1": None})
            bucket["items"] += 1
            if item.get("status") == "done":
                bucket["done"] += 1
            if int(item.get("ground_truth_count") or 0) > 0:
                bucket["ground_truth_items"] += 1
            bucket["mean_runtime_sec"] += float(item.get("runtime_sec") or 0.0)
        for value, bucket in buckets.items():
            count = max(1, int(bucket["items"]))
            bucket["mean_runtime_sec"] = round(float(bucket["mean_runtime_sec"]) / count, 3)
            f1s = []
            for item in items:
                if str(item.get(key) or "unknown") != value:
                    continue
                best = ((item.get("evaluation") or {}).get("best_by_f1") or {})
                if _is_number(best.get("f1")):
                    f1s.append(float(best["f1"]))
            bucket["mean_best_f1"] = round(sum(f1s) / len(f1s), 4) if f1s else None
        rollups[key] = buckets
    return rollups


def _build_run_report(summary: dict[str, Any]) -> str:
    lines = [
        "# MITAS OCR Credit Experiment",
        "",
        "## Summary",
        "",
        f"- Version: {summary['experiment_version']}",
        f"- Runtime: {summary['runtime_sec']} sec",
        f"- Manifest: {summary['manifest_path']}",
        f"- Normalization: {summary.get('normalization_policy', {}).get('diacritics')}",
        "",
        "## Engines",
        "",
    ]
    for engine, status in summary.get("engine_status", {}).items():
        state = "available" if status.get("available") else f"unavailable: {status.get('error')}"
        lines.append(f"- {engine}: {state}")
    lines.extend(["", "## Items", ""])
    for item in summary.get("items", []):
        lines.append(
            f"- {item.get('id')}: {item.get('status')} | kind={item.get('kind')} | motion={item.get('motion_type')} | fps={item.get('fps')} | frames={item.get('frames', 0)} "
            f"| frame_records={item.get('frame_ocr_records', 0)} | stable_groups={item.get('temporal_stable_groups', 0)} "
            f"| canvas_records={item.get('canvas_ocr_records', 0)} | gt={item.get('ground_truth_count', 0)}"
        )
        best = ((item.get("evaluation") or {}).get("best_by_f1") or {})
        if best:
            lines.append(f"  Best F1: {best.get('engine')} / {best.get('strategy')} = {best.get('f1')}")
        if item.get("error_msg"):
            lines.append(f"  Error: {item['error_msg']}")
    lines.extend(["", "## Category Rollups", "", "```json", json.dumps(summary.get("category_rollups", {}), ensure_ascii=False, indent=2), "```"])
    lines.append("")
    return "\n".join(lines)


def _build_item_comparison(
    summary: dict[str, Any],
    frame_ocr: dict[str, Any],
    temporal: dict[str, Any],
    motion: dict[str, Any],
    canvas: dict[str, Any],
    preprocessed_ocr: dict[str, Any] | None = None,
    preprocessed_temporal: dict[str, Any] | None = None,
    evaluation: dict[str, Any] | None = None,
) -> str:
    lines = [
        f"# OCR Comparison: {summary.get('id')}",
        "",
        "## Item Summary",
        "",
        "```json",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    if summary.get("status") != "done":
        return "\n".join(lines)

    lines.extend(
        [
            "## Strategy Metrics",
            "",
            f"- Frame OCR records: {len(frame_ocr.get('records', []))}",
            f"- Preprocessed frame OCR records: {len((preprocessed_ocr or {}).get('records', []))}",
            f"- Temporal unique lines: {temporal.get('unique_lines')}",
            f"- Temporal stable groups: {temporal.get('stable_groups')}",
            f"- Preprocessed temporal unique lines: {(preprocessed_temporal or {}).get('unique_lines')}",
            f"- Preprocessed temporal stable groups: {(preprocessed_temporal or {}).get('stable_groups')}",
            f"- Mean text shift: {motion.get('mean_text_shift')}",
            f"- Mean global shift: {motion.get('mean_global_shift')}",
            f"- Phase quality: {(motion.get('phase_quality') or {}).get('status')}",
            f"- De-scroll canvas size: {canvas.get('canvas_size')}",
            f"- De-scroll orientation: {canvas.get('estimated_orientation')}",
            f"- Canvas OCR records: {len(canvas.get('ocr_records', []))}",
            "",
            "## Temporal Winners",
            "",
        ]
    )
    for group in temporal.get("groups", [])[:30]:
        lines.append(f"- {group.get('engine')} {group.get('line_group_id')}: {group.get('winner_text')} ({group.get('record_count')} hits)")
    lines.extend(["", "## Canvas Advantage", "", "```json", json.dumps(canvas.get("canvas_advantage", {}), ensure_ascii=False, indent=2), "```", ""])
    lines.extend(["", "## Evaluation", "", "```json", json.dumps(evaluation or {}, ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_engine_names(engines: list[str]) -> list[str]:
    normalized: list[str] = []
    aliases = {"paddleocr": "paddle", "one": "oneocr"}
    for engine in engines:
        name = aliases.get(engine.strip().lower(), engine.strip().lower())
        if name and name not in normalized:
            normalized.append(name)
    return normalized


def _require_nonempty_string(raw: dict[str, Any], key: str, index: int) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Manifest item {index}: '{key}' must be a non-empty string")
    return value.strip()


def _require_number(raw: dict[str, Any], key: str, index: int) -> float:
    value = raw.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Manifest item {index}: '{key}' must be a number")
    return float(value)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _optional_positive_number(value: Any, item_id: str, key: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) <= 0:
        raise ValueError(f"Manifest item {item_id}: {key} must be a positive number when provided")
    return float(value)


def _parse_roi(value: Any, item_id: str) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 4 or not all(isinstance(v, int) and not isinstance(v, bool) for v in value):
        raise ValueError(f"Manifest item {item_id}: roi must be null or [x, y, width, height] integers")
    x, y, w, h = value
    if x < 0 or y < 0 or w <= 0 or h <= 0:
        raise ValueError(f"Manifest item {item_id}: roi values must be non-negative and width/height > 0")
    return x, y, w, h


def _parse_column_count(value: Any, item_id: str) -> int:
    if value is None:
        return 1
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"Manifest item {item_id}: column_count must be a positive integer")
    return value


def _parse_ground_truth(raw: dict[str, Any], manifest_dir: Path, item_id: str) -> list[str]:
    lines: list[str] = []
    inline = raw.get("ground_truth") or raw.get("ground_truth_lines") or raw.get("expected_lines")
    if inline is not None:
        if not isinstance(inline, list) or not all(isinstance(item, str) for item in inline):
            raise ValueError(f"Manifest item {item_id}: ground_truth must be a list of strings")
        lines.extend(item.strip() for item in inline if item.strip())

    truth_path = raw.get("ground_truth_path")
    if truth_path:
        if not isinstance(truth_path, str):
            raise ValueError(f"Manifest item {item_id}: ground_truth_path must be a string")
        path = Path(truth_path)
        if not path.is_absolute():
            path = manifest_dir / path
        if not path.exists():
            raise ValueError(f"Manifest item {item_id}: ground_truth_path does not exist: {path}")
        if path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload = payload.get("lines") or payload.get("ground_truth") or []
            if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
                raise ValueError(f"Manifest item {item_id}: JSON ground truth must be a string list or object with lines")
            lines.extend(item.strip() for item in payload if item.strip())
        else:
            lines.extend(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return _dedupe_texts(lines)


def _resolve_ffmpeg() -> str:
    configured = os.environ.get("MITAS_FFMPEG", "").strip()
    if configured:
        return configured
    candidates = [
        PROJECT_ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe",
    ]
    for parent in PROJECT_ROOT.parents:
        candidates.append(parent / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe")
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "ffmpeg"


def _resolve_tesseract() -> str | None:
    configured = os.environ.get("MITAS_TESSERACT_CMD", "").strip()
    if configured and Path(configured).exists():
        return configured
    found = shutil.which("tesseract")
    if found:
        return found
    candidates = [
        Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
        Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _resolve_oneocr_config_dir() -> Path:
    candidates = []
    configured = os.environ.get("MITAS_ONEOCR_CONFIG_DIR", "").strip()
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        [
            PROJECT_ROOT / "tools" / "oneocr",
            Path(os.path.expanduser("~")) / ".config" / "oneocr",
        ]
    )
    required = ("oneocr.dll", "oneocr.onemodel")
    missing_by_dir: list[str] = []
    for candidate in candidates:
        missing = [name for name in required if not (candidate / name).exists()]
        if not missing:
            return candidate
        missing_by_dir.append(f"{candidate}: missing {', '.join(missing)}")
    raise RuntimeError("OneOCR DLL/model is not configured. Expected oneocr.dll and oneocr.onemodel. Checked: " + " | ".join(missing_by_dir))


def _resolve_paddle_model_dir(env_name: str, model_name: str) -> Path | None:
    configured = _existing_env_path(env_name)
    if configured is not None:
        return configured
    candidates = [
        PADDLE_OFFICIAL_MODELS_ROOT / model_name,
        Path(os.path.expanduser("~")) / ".paddlex" / "official_models" / model_name,
    ]
    for candidate in candidates:
        if _looks_like_paddle_model_dir(candidate):
            return candidate
    return None


def _looks_like_paddle_model_dir(path: Path) -> bool:
    required = ("inference.yml", "inference.pdiparams")
    return path.exists() and all((path / name).exists() for name in required)


def _resolve_tesseract_tessdata_dir() -> Path | None:
    configured = _existing_env_path("MITAS_TESSERACT_TESSDATA_DIR")
    if configured is not None:
        return configured
    candidates = [
        TESSERACT_TESSDATA_DIR,
        Path("C:/Program Files/Tesseract-OCR/tessdata"),
        Path("C:/Program Files (x86)/Tesseract-OCR/tessdata"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _available_tesseract_langs(tessdata_dir: Path | None) -> set[str]:
    if tessdata_dir is None or not tessdata_dir.exists():
        return set()
    return {path.stem for path in tessdata_dir.glob("*.traineddata")}


def _directory_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return total


def _strategy_cost_rates(engine_call_costs: dict[str, Any], duration_seconds: float) -> dict[str, Any]:
    rates: dict[str, Any] = {}
    for strategy, payload in engine_call_costs.items():
        if strategy in {"frame_ocr", "preprocessed_frame_ocr"}:
            runtimes = payload.get("engine_runtime_sec", {}) if isinstance(payload, dict) else {}
        else:
            runtimes = {engine: data.get("runtime_sec", 0.0) for engine, data in payload.items() if isinstance(data, dict)}
        rates[strategy] = {
            engine: {
                "runtime_sec": round(float(runtime), 3),
                "runtime_per_video_second": round(float(runtime) / duration_seconds, 4),
            }
            for engine, runtime in runtimes.items()
        }
    return rates


def _gpu_snapshot() -> dict[str, Any]:
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        return {"available": False, "reason": "nvidia-smi not found"}
    command = [
        nvidia_smi,
        "--query-gpu=name,utilization.gpu,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=5)
    except Exception as exc:
        return {"available": False, "reason": str(exc)}
    if completed.returncode != 0:
        return {"available": False, "reason": (completed.stderr or completed.stdout).strip()}
    gpus = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 4:
            gpus.append(
                {
                    "name": parts[0],
                    "utilization_gpu_percent": _float_or_none(parts[1]),
                    "memory_used_mb": _float_or_none(parts[2]),
                    "memory_total_mb": _float_or_none(parts[3]),
                }
            )
    return {"available": bool(gpus), "gpus": gpus}


def _gpu_peak_from_snapshots(*snapshots: dict[str, Any]) -> dict[str, Any]:
    peaks: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        for gpu in snapshot.get("gpus") or []:
            name = str(gpu.get("name") or "unknown")
            used = _float_or_none(gpu.get("memory_used_mb"))
            total = _float_or_none(gpu.get("memory_total_mb"))
            entry = peaks.setdefault(name, {"peak_memory_used_mb": None, "memory_total_mb": total})
            if used is not None and (entry["peak_memory_used_mb"] is None or used > entry["peak_memory_used_mb"]):
                entry["peak_memory_used_mb"] = used
            if total is not None:
                entry["memory_total_mb"] = total
    return {"available": bool(peaks), "gpus": [{"name": name, **values} for name, values in peaks.items()]}


def _existing_env_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    path = Path(value)
    if not path.exists():
        raise RuntimeError(f"{name} points to a missing path: {path}")
    return path


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


_SCROLL_HINT_KEYWORDS = (
    "scroll",
    "rolling",
    "credit roll",
    "vertical",
    "akan",
    "kayar",
    "kayan",
    "kayma",
)


def _is_explicit_scroll_hint(hints: str) -> bool:
    if not hints:
        return False
    text = hints if hints == hints.lower() else hints.lower()
    return any(keyword in text for keyword in _SCROLL_HINT_KEYWORDS)


def _bbox_centers_close(a: Any, b: Any, max_distance: float) -> bool:
    if not a or not b or len(a) < 4 or len(b) < 4:
        return True
    ax, ay, aw, ah = [float(v) for v in a[:4]]
    bx, by, bw, bh = [float(v) for v in b[:4]]
    return math.hypot((ax + aw / 2.0) - (bx + bw / 2.0), (ay + ah / 2.0) - (by + bh / 2.0)) <= max_distance


def _refresh_group_winner(group: dict[str, Any]) -> None:
    best_normalized = max(group["texts"].items(), key=lambda item: (item[1], len(item[0])))[0]
    group["winner_normalized_text"] = best_normalized
    for record in group["records"]:
        if record["normalized_text"] == best_normalized:
            group["winner_text"] = record["text"]
            return
