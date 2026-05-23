"""Smoke-test the active MITAS OCR engines and local model layout."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import subprocess
import traceback
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from core.pipelines.ocr.credit_experiment import (
    DEFAULT_ENGINES,
    OCR_MODELS_ROOT,
    PADDLE_DETECTION_MODEL_NAME,
    PADDLE_OFFICIAL_MODELS_ROOT,
    PADDLE_RECOGNITION_MODEL_NAME,
    PROJECT_ROOT,
    TESSERACT_TESSDATA_DIR,
    _build_engines,
    _resolve_oneocr_config_dir,
    build_default_engine_factories,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate MITAS OCR model installation")
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "outputs" / "ocr_model_healthcheck"))
    parser.add_argument("--engines", default=",".join(DEFAULT_ENGINES))
    parser.add_argument("--include-vlm", action="store_true", help="Also record local Ollama VLM inventory")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / "synthetic_tr_latin_ocr.png"
    _render_synthetic_image(image_path)

    engine_names = [part.strip() for part in args.engines.split(",") if part.strip()]
    factories = build_default_engine_factories(engine_names)
    active_engines, engine_status = _build_engines(engine_names, factories)

    checks: list[dict[str, Any]] = []
    for engine in active_engines:
        started = datetime.now(timezone.utc)
        try:
            records = engine.recognize(image_path, strategy="model_healthcheck", timestamp_seconds=0.0)
            confidences = [float(item["confidence"]) for item in records if item.get("confidence") is not None]
            checks.append(
                {
                    "engine": engine.name,
                    "status": "ok",
                    "started_at": started.isoformat(),
                    "record_count": len(records),
                    "mean_confidence": round(statistics.fmean(confidences), 4) if confidences else None,
                    "texts": [str(item.get("text") or "") for item in records[:25]],
                    "records": records,
                }
            )
        except Exception as exc:  # pragma: no cover - operational report path
            checks.append(
                {
                    "engine": engine.name,
                    "status": "failed",
                    "started_at": started.isoformat(),
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                }
            )

    inventory = _build_inventory(include_vlm=args.include_vlm)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir),
        "image_path": str(image_path),
        "requested_engines": engine_names,
        "engine_status": engine_status,
        "inventory": inventory,
        "checks": checks,
    }

    json_path = output_dir / "ocr_model_healthcheck.json"
    report_path = output_dir / "ocr_model_healthcheck.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_report(payload), encoding="utf-8")
    print(json.dumps({"json_path": str(json_path), "report_path": str(report_path)}, ensure_ascii=False))

    failed = [name for name, status in engine_status.items() if not status.get("available")]
    failed.extend(item["engine"] for item in checks if item.get("status") != "ok")
    return 1 if failed else 0


def _render_synthetic_image(path: Path) -> None:
    image = Image.new("RGB", (1280, 520), "white")
    draw = ImageDraw.Draw(image)
    font = _load_font(54)
    small_font = _load_font(42)
    lines = [
        "\u00c7A\u011eATAY \u0130\u015eLER",
        "MICHAEL DANTE",
        "G\u00d6R\u00dcNT\u00dc Y\u00d6NETMEN\u0130",
        "DIGITAL INTERMEDIATE BY EFILM",
    ]
    y = 52
    for line in lines:
        draw.text((72, y), line, fill="black", font=font if y < 230 else small_font)
        y += 98
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _build_inventory(*, include_vlm: bool) -> dict[str, Any]:
    inventory: dict[str, Any] = {
        "models_root": str(OCR_MODELS_ROOT),
        "paddle": {
            "models_root": str(PADDLE_OFFICIAL_MODELS_ROOT),
            "detection_model": _model_dir_status(PADDLE_OFFICIAL_MODELS_ROOT / PADDLE_DETECTION_MODEL_NAME),
            "recognition_model": _model_dir_status(PADDLE_OFFICIAL_MODELS_ROOT / PADDLE_RECOGNITION_MODEL_NAME),
            "extra_models": sorted(path.name for path in PADDLE_OFFICIAL_MODELS_ROOT.iterdir() if path.is_dir())
            if PADDLE_OFFICIAL_MODELS_ROOT.exists()
            else [],
        },
        "oneocr": _oneocr_status(),
        "tesseract": {
            "tessdata_dir": str(TESSERACT_TESSDATA_DIR),
            "langs": sorted(path.stem for path in TESSERACT_TESSDATA_DIR.glob("*.traineddata")) if TESSERACT_TESSDATA_DIR.exists() else [],
        },
    }
    if include_vlm:
        inventory["vlm"] = _ollama_status()
    return inventory


def _model_dir_status(path: Path) -> dict[str, Any]:
    required = ["inference.yml", "inference.json", "inference.pdiparams"]
    return {
        "path": str(path),
        "exists": path.exists(),
        "required_files": {name: (path / name).exists() for name in required},
        "size_mb": round(_directory_size(path) / 1024 / 1024, 2),
    }


def _oneocr_status() -> dict[str, Any]:
    try:
        config_dir = _resolve_oneocr_config_dir()
    except Exception as exc:  # pragma: no cover - operational report path
        return {"available": False, "error": str(exc)}
    required = ["oneocr.dll", "oneocr.onemodel", "onnxruntime.dll"]
    return {
        "available": True,
        "config_dir": str(config_dir),
        "required_files": {name: (config_dir / name).exists() for name in required},
        "size_mb": round(_directory_size(config_dir) / 1024 / 1024, 2),
    }


def _ollama_status() -> dict[str, Any]:
    ollama = Path("C:/Users/TRT03/AppData/Local/Programs/Ollama/ollama.exe")
    if not ollama.exists():
        return {"available": False, "error": "ollama.exe not found"}
    try:
        completed = subprocess.run([str(ollama), "list"], check=False, capture_output=True, text=True, timeout=15)
    except Exception as exc:  # pragma: no cover - operational report path
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    models = []
    for line in completed.stdout.splitlines()[1:]:
        parts = line.split()
        if parts:
            models.append(parts[0])
    return {"available": completed.returncode == 0, "models": models, "raw": completed.stdout.strip()}


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# MITAS OCR Model Healthcheck",
        "",
        f"- Created: {payload.get('created_at')}",
        f"- Output dir: {payload.get('output_dir')}",
        f"- Synthetic image: {payload.get('image_path')}",
        f"- Requested engines: {', '.join(payload.get('requested_engines') or [])}",
        "",
        "## Model Inventory",
        "",
        f"- Models root: {payload['inventory'].get('models_root')}",
        f"- Paddle det: {payload['inventory']['paddle']['detection_model']['path']}",
        f"- Paddle rec: {payload['inventory']['paddle']['recognition_model']['path']}",
        f"- OneOCR: {payload['inventory']['oneocr'].get('config_dir')}",
        f"- Tesseract langs: {', '.join(payload['inventory']['tesseract'].get('langs') or [])}",
        "",
        "## Engine Status",
        "",
        "| Engine | Available | Detail |",
        "| --- | --- | --- |",
    ]
    for engine, status in (payload.get("engine_status") or {}).items():
        detail = status.get("metadata") or status.get("error") or ""
        lines.append(f"| {engine} | {status.get('available')} | {_md_cell(json.dumps(detail, ensure_ascii=False))} |")

    lines.extend(["", "## Recognition Smoke", "", "| Engine | Status | Records | Mean Confidence | First Texts |", "| --- | --- | ---: | ---: | --- |"])
    for check in payload.get("checks") or []:
        texts = " / ".join(check.get("texts") or [])
        lines.append(
            f"| {check.get('engine')} | {check.get('status')} | {check.get('record_count', '')} | {check.get('mean_confidence', '')} | {_md_cell(texts)} |"
        )
    return "\n".join(lines) + "\n"


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
