"""Model registry and lazy CTranslate2 loader for MITAS translation."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import gc
import os
from pathlib import Path
from time import monotonic
from typing import Any

from core.pipelines.translate.router import NLLB_1B, NLLB_3B, OPUS_EN_TR, canonical_model_id


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODELS_ROOT = PROJECT_ROOT / "models" / "translate"
SNAPSHOT_ROOT = MODELS_ROOT / "_hf_snapshots"
DEFAULT_IDLE_UNLOAD_SECONDS = 600.0


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    kind: str
    ct2_dir: Path
    tokenizer_dir: Path


@dataclass
class LoadedTranslator:
    spec: ModelSpec
    translator: Any
    tokenizer: Any
    device: str
    loaded_at: float
    last_used: float


MODEL_SPECS = {
    OPUS_EN_TR: ModelSpec(
        model_id=OPUS_EN_TR,
        kind="opus",
        ct2_dir=MODELS_ROOT / "opus-mt-tc-big-en-tr-ct2-int8",
        tokenizer_dir=SNAPSHOT_ROOT / "opus-mt-tc-big-en-tr-hf",
    ),
    NLLB_3B: ModelSpec(
        model_id=NLLB_3B,
        kind="nllb",
        ct2_dir=MODELS_ROOT / "nllb-200-3.3B-ct2-int8",
        tokenizer_dir=SNAPSHOT_ROOT / "nllb-200-3.3B-hf",
    ),
    NLLB_1B: ModelSpec(
        model_id=NLLB_1B,
        kind="nllb",
        ct2_dir=MODELS_ROOT / "nllb-200-distilled-1.3B-ct2-int8",
        tokenizer_dir=SNAPSHOT_ROOT / "nllb-200-distilled-1.3B-hf",
    ),
}

_DLL_HANDLES: list[Any] = []
_DLL_DIRS_ADDED: set[str] = set()
_LOADED: OrderedDict[tuple[str, str], LoadedTranslator] = OrderedDict()


def get_model_spec(model_id: str) -> ModelSpec:
    canonical = canonical_model_id(model_id)
    try:
        return MODEL_SPECS[canonical]
    except KeyError as exc:
        raise ValueError(f"Unknown translation model id: {model_id}") from exc


def load_translator(model_id: str, *, device: str = "auto", max_loaded: int = 2) -> LoadedTranslator:
    setup_dll_search_path()
    ctranslate2 = _import_ctranslate2()
    from transformers import AutoTokenizer

    spec = get_model_spec(model_id)
    resolved_device = resolve_device(device, ctranslate2=ctranslate2)
    cache_key = (spec.model_id, resolved_device)
    now = monotonic()
    loaded = _LOADED.get(cache_key)
    if loaded is not None:
        loaded.last_used = now
        _LOADED.move_to_end(cache_key)
        return loaded

    validate_model_files(spec)
    tokenizer_kwargs = {"local_files_only": True}
    if spec.kind == "nllb":
        tokenizer_kwargs["src_lang"] = "eng_Latn"
    tokenizer = AutoTokenizer.from_pretrained(str(spec.tokenizer_dir), **tokenizer_kwargs)
    translator = ctranslate2.Translator(str(spec.ct2_dir), device=resolved_device)
    loaded = LoadedTranslator(
        spec=spec,
        translator=translator,
        tokenizer=tokenizer,
        device=resolved_device,
        loaded_at=now,
        last_used=now,
    )
    _LOADED[cache_key] = loaded
    _LOADED.move_to_end(cache_key)
    enforce_max_loaded(max_loaded)
    return loaded


def unload_idle(*, max_idle_seconds: float = DEFAULT_IDLE_UNLOAD_SECONDS) -> int:
    now = monotonic()
    removed = 0
    for key, loaded in list(_LOADED.items()):
        if now - loaded.last_used >= max_idle_seconds:
            del _LOADED[key]
            removed += 1
    if removed:
        gc.collect()
    return removed


def unload_all() -> None:
    _LOADED.clear()
    gc.collect()


def enforce_max_loaded(max_loaded: int) -> None:
    while len(_LOADED) > max_loaded:
        _LOADED.popitem(last=False)
    gc.collect()


def resolve_device(device: str, *, ctranslate2: Any | None = None) -> str:
    if device != "auto":
        return device
    ctranslate2 = ctranslate2 or _import_ctranslate2()
    try:
        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def validate_model_files(spec: ModelSpec) -> None:
    if not (spec.ct2_dir / "model.bin").exists():
        raise FileNotFoundError(f"Missing CT2 model.bin: {spec.ct2_dir / 'model.bin'}")
    if not spec.tokenizer_dir.exists():
        raise FileNotFoundError(f"Missing tokenizer snapshot: {spec.tokenizer_dir}")


def setup_dll_search_path() -> None:
    dll_dirs = (
        PROJECT_ROOT / "venvs" / "asr" / "Lib" / "site-packages" / "torch" / "lib",
        PROJECT_ROOT / "venvs" / "translate" / "Lib" / "site-packages" / "torch" / "lib",
    )
    for dll_dir in dll_dirs:
        if not dll_dir.exists():
            continue
        path_text = str(dll_dir)
        if path_text not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{path_text}{os.pathsep}{os.environ.get('PATH', '')}"
        if hasattr(os, "add_dll_directory") and path_text not in _DLL_DIRS_ADDED:
            _DLL_HANDLES.append(os.add_dll_directory(path_text))
            _DLL_DIRS_ADDED.add(path_text)


def _import_ctranslate2() -> Any:
    setup_dll_search_path()
    import ctranslate2

    return ctranslate2
