"""Smoke test installed MITAS MT candidates with short EN->TR samples."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import gc
import json
import os
import re
from pathlib import Path
from time import perf_counter
from typing import Any

from transformers import AutoTokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TORCH_DLL_DIRS = (
    PROJECT_ROOT / "venvs" / "asr" / "Lib" / "site-packages" / "torch" / "lib",
    PROJECT_ROOT / "venvs" / "translate" / "Lib" / "site-packages" / "torch" / "lib",
)
_DLL_HANDLES = []
for _dll_dir in _TORCH_DLL_DIRS:
    if _dll_dir.exists():
        _DLL_HANDLES.append(os.add_dll_directory(str(_dll_dir)))
        os.environ["PATH"] = f"{_dll_dir}{os.pathsep}{os.environ.get('PATH', '')}"

import ctranslate2  # noqa: E402  (after DLL search path setup)


MODELS_ROOT = PROJECT_ROOT / "models" / "translate"
SNAPSHOT_ROOT = MODELS_ROOT / "_hf_snapshots"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "outputs" / "translate_smoke_report.json"

SAMPLES = [
    "Good morning.",
    "The press conference will start in five minutes.",
    "He scored a goal in the last minute of the match.",
    "Mr. Prime Minister, one minute please.",
]


@dataclass(frozen=True)
class SmokeModel:
    key: str
    kind: str
    hf_snapshot_dir: str
    ct2_dir: str


MODELS: dict[str, SmokeModel] = {
    "nllb_3b": SmokeModel(
        key="nllb_3b",
        kind="nllb",
        hf_snapshot_dir="nllb-200-3.3B-hf",
        ct2_dir="nllb-200-3.3B-ct2-int8",
    ),
    "nllb_1b": SmokeModel(
        key="nllb_1b",
        kind="nllb",
        hf_snapshot_dir="nllb-200-distilled-1.3B-hf",
        ct2_dir="nllb-200-distilled-1.3B-ct2-int8",
    ),
    "opus": SmokeModel(
        key="opus",
        kind="opus",
        hf_snapshot_dir="opus-mt-tc-big-en-tr-hf",
        ct2_dir="opus-mt-tc-big-en-tr-ct2-int8",
    ),
}


def detect_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def smoke_model(model: SmokeModel, *, device: str, samples: list[str]) -> dict[str, Any]:
    started = perf_counter()
    snapshot_path = SNAPSHOT_ROOT / model.hf_snapshot_dir
    ct2_path = MODELS_ROOT / model.ct2_dir
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Missing HF snapshot: {snapshot_path}")
    if not (ct2_path / "model.bin").exists():
        raise FileNotFoundError(f"Missing CT2 model.bin: {ct2_path / 'model.bin'}")

    translator = ctranslate2.Translator(str(ct2_path), device=device)
    try:
        if model.kind == "nllb":
            outputs = translate_nllb(translator, snapshot_path, samples)
        elif model.kind == "opus":
            outputs = translate_opus(translator, snapshot_path, samples)
        else:
            raise ValueError(f"Unsupported model kind: {model.kind}")
    finally:
        del translator
        gc.collect()

    return {
        "model": model.key,
        "device": device,
        "status": "passed",
        "seconds": round(perf_counter() - started, 3),
        "outputs": outputs,
    }


def translate_nllb(translator: ctranslate2.Translator, tokenizer_dir: Path, samples: list[str]) -> list[dict[str, Any]]:
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir), src_lang="eng_Latn", local_files_only=True)
    rows: list[dict[str, Any]] = []
    for source in samples:
        item_started = perf_counter()
        source_tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(source))
        result = translator.translate_batch(
            [source_tokens],
            target_prefix=[["tur_Latn"]],
            beam_size=4,
            max_batch_size=1,
        )[0]
        target_tokens = result.hypotheses[0][1:]
        target_ids = tokenizer.convert_tokens_to_ids(target_tokens)
        text = tokenizer.decode(target_ids, skip_special_tokens=True).strip()
        rows.append(
            {
                "src": source,
                "tr": clean_text(text),
                "latency_ms": round((perf_counter() - item_started) * 1000, 1),
            }
        )
    return rows


def translate_opus(translator: ctranslate2.Translator, tokenizer_dir: Path, samples: list[str]) -> list[dict[str, Any]]:
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir), local_files_only=True)
    rows: list[dict[str, Any]] = []
    for source in samples:
        item_started = perf_counter()
        source_tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(source))
        result = translator.translate_batch(
            [source_tokens],
            beam_size=4,
            max_batch_size=1,
        )[0]
        target_ids = tokenizer.convert_tokens_to_ids(result.hypotheses[0])
        text = tokenizer.decode(target_ids, skip_special_tokens=True).strip()
        rows.append(
            {
                "src": source,
                "tr": clean_text(text),
                "latency_ms": round((perf_counter() - item_started) * 1000, 1),
            }
        )
    return rows


def clean_text(text: str) -> str:
    text = re.sub(r"^>>\w+<<\s*", "", text)
    return text.strip()


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=[*MODELS.keys(), "all"], default="all")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    device = detect_device(args.device)
    targets = list(MODELS) if args.model == "all" else [args.model]
    payload: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "device": device,
        "samples": SAMPLES,
        "items": [],
    }
    for key in targets:
        print(f"[smoke] {key} on {device}", flush=True)
        item = smoke_model(MODELS[key], device=device, samples=SAMPLES)
        payload["items"].append(item)
        for output in item["outputs"]:
            print(f"[{key}] EN: {output['src']}", flush=True)
            print(f"[{key}] TR: {output['tr']} ({output['latency_ms']} ms)", flush=True)
    write_report(args.report, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
