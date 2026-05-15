"""Download and CTranslate2-convert MITAS MT model candidates.

This script intentionally keeps raw Hugging Face snapshots under models/ so the
converted artifacts can be reproduced without touching the protected ASR venv.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

from ctranslate2.converters.transformers import TransformersConverter
from huggingface_hub import snapshot_download


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_ROOT = PROJECT_ROOT / "models" / "translate"
SNAPSHOT_ROOT = MODELS_ROOT / "_hf_snapshots"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "outputs" / "translate_model_install_report.json"


@dataclass(frozen=True)
class ModelSpec:
    key: str
    hf_id: str
    out_dir: str
    quantization: str
    copy_files: tuple[str, ...]


MODELS: dict[str, ModelSpec] = {
    "nllb_3b": ModelSpec(
        key="nllb_3b",
        hf_id="facebook/nllb-200-3.3B",
        out_dir="nllb-200-3.3B-ct2-int8",
        quantization="int8_float16",
        copy_files=(
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "sentencepiece.bpe.model",
        ),
    ),
    "nllb_1b": ModelSpec(
        key="nllb_1b",
        hf_id="facebook/nllb-200-distilled-1.3B",
        out_dir="nllb-200-distilled-1.3B-ct2-int8",
        quantization="int8_float16",
        copy_files=(
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "sentencepiece.bpe.model",
        ),
    ),
    "opus": ModelSpec(
        key="opus",
        hf_id="Helsinki-NLP/opus-mt-tc-big-en-tr",
        out_dir="opus-mt-tc-big-en-tr-ct2-int8",
        quantization="int8",
        copy_files=(
            "tokenizer_config.json",
            "special_tokens_map.json",
            "source.spm",
            "target.spm",
            "vocab.json",
        ),
    ),
}


def install_model(spec: ModelSpec, *, force: bool = False) -> dict[str, Any]:
    started = perf_counter()
    out_dir = MODELS_ROOT / spec.out_dir
    model_bin = out_dir / "model.bin"

    if model_bin.exists() and not force:
        return {
            "model": spec.key,
            "hf_id": spec.hf_id,
            "status": "skipped_existing",
            "out_dir": str(out_dir),
            "model_bin_size_bytes": model_bin.stat().st_size,
            "seconds": round(perf_counter() - started, 3),
        }

    snapshot_path = download_snapshot(spec)
    copied_files = [name for name in spec.copy_files if (snapshot_path / name).exists()]
    missing_copy_files = [name for name in spec.copy_files if name not in copied_files]

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    converter = CompatTransformersConverter(
        str(snapshot_path),
        copy_files=copied_files,
    )
    converter.convert(str(out_dir), quantization=spec.quantization, force=force)
    if not model_bin.exists():
        raise RuntimeError(f"CT2 conversion finished but model.bin is missing for {spec.key}: {model_bin}")

    return {
        "model": spec.key,
        "hf_id": spec.hf_id,
        "status": "converted",
        "snapshot_path": str(snapshot_path),
        "out_dir": str(out_dir),
        "quantization": spec.quantization,
        "copy_files": copied_files,
        "missing_copy_files": missing_copy_files,
        "model_bin_size_bytes": model_bin.stat().st_size,
        "seconds": round(perf_counter() - started, 3),
    }


class CompatTransformersConverter(TransformersConverter):
    """Compatibility shim for CTranslate2 4.7.1 + Transformers 4.46.x.

    CT2 4.7.1 passes ``dtype=`` to ``from_pretrained``. In the pinned
    Transformers 4.46.x stack, M2M100/NLLB still expects ``torch_dtype=``.
    Keeping the shim here avoids changing the isolated translate venv pins.
    """

    def load_model(self, model_class: Any, model_name_or_path: str, **kwargs: Any) -> Any:
        dtype = kwargs.pop("dtype", None)
        if dtype is not None:
            kwargs["torch_dtype"] = dtype
        return super().load_model(model_class, model_name_or_path, **kwargs)


def download_snapshot(spec: ModelSpec) -> Path:
    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    local_dir = SNAPSHOT_ROOT / spec.out_dir.replace("-ct2-int8", "-hf")
    path = snapshot_download(
        repo_id=spec.hf_id,
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
    )
    return Path(path)


def write_report(path: Path, items: list[dict[str, Any]]) -> None:
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "models_root": str(MODELS_ROOT),
        "items": items,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=[*MODELS.keys(), "all"], default="all")
    parser.add_argument("--force", action="store_true", help="Re-run conversion even when model.bin exists.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = list(MODELS) if args.model == "all" else [args.model]
    results: list[dict[str, Any]] = []
    try:
        for key in targets:
            print(f"[install] {key} ({MODELS[key].hf_id})", flush=True)
            result = install_model(MODELS[key], force=args.force)
            results.append(result)
            print(f"[{result['status']}] {key} -> {result['out_dir']}", flush=True)
    finally:
        write_report(args.report, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
