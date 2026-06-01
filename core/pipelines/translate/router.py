"""Language-to-model routing for translation requests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "translation_router.yaml"

OPUS_EN_TR = "opus-mt-tc-big-en-tr"
NLLB_3B = "nllb-200-3.3b"
NLLB_1B = "nllb-200-distilled-1.3b"

MODEL_ALIASES = {
    OPUS_EN_TR: OPUS_EN_TR,
    "opus": OPUS_EN_TR,
    "opus-mt-tc-big-en-tr-ct2-int8": OPUS_EN_TR,
    NLLB_3B: NLLB_3B,
    "nllb_3b": NLLB_3B,
    "nllb-200-3.3B-ct2-int8": NLLB_3B,
    "nllb-200-3.3b-ct2-int8": NLLB_3B,
    NLLB_1B: NLLB_1B,
    "nllb_1b": NLLB_1B,
    "nllb-200-distilled-1.3B-ct2-int8": NLLB_1B,
    "nllb-200-distilled-1.3b-ct2-int8": NLLB_1B,
}

LANG_ALIASES = {
    "eng_latn": "en",
    "eng-latn": "en",
    "english": "en",
    "en": "en",
    "tur_latn": "tr",
    "tur-latn": "tr",
    "turkish": "tr",
    "tr": "tr",
    "ara": "ar",
    "arabic": "ar",
    "arb": "ar",
    "arb_arab": "ar",
    "arb-arab": "ar",
    "ar": "ar",
}

DEFAULT_ROUTER_CONFIG = {
    "default_target": "tr",
    "routes": {
        "en": OPUS_EN_TR,
        "*": NLLB_3B,
    },
    "fallback": [NLLB_3B],
}


@dataclass(frozen=True)
class TranslationRouter:
    default_target: str
    routes: dict[str, str]
    fallback: tuple[str, ...]

    def resolve(self, *, source_lang: str, target_lang: str = "tr", model_override: str | None = None) -> str:
        if target_lang != self.default_target:
            raise ValueError(f"Unsupported translation target: {target_lang}")
        if model_override:
            return canonical_model_id(model_override)
        normalized_source = normalize_lang(source_lang)
        model = self.routes.get(normalized_source) or self.routes.get("*")
        if model is None and self.fallback:
            model = self.fallback[0]
        if model is None:
            raise ValueError(f"No translation route for source language: {source_lang}")
        return canonical_model_id(model)


def load_router(config_path: str | Path | None = None) -> TranslationRouter:
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        data = DEFAULT_ROUTER_CONFIG
    if not isinstance(data, dict):
        raise ValueError(f"Translation router config must be a mapping: {path}")
    routes_raw = data.get("routes") or {}
    if not isinstance(routes_raw, dict):
        raise ValueError("Translation router routes must be a mapping")
    routes = {normalize_lang(str(lang)): canonical_model_id(str(model)) for lang, model in routes_raw.items()}
    fallback_raw = data.get("fallback") or []
    if not isinstance(fallback_raw, list):
        raise ValueError("Translation router fallback must be a list")
    return TranslationRouter(
        default_target=normalize_lang(str(data.get("default_target") or "tr")),
        routes=routes,
        fallback=tuple(canonical_model_id(str(model)) for model in fallback_raw),
    )


def normalize_lang(lang: str | None) -> str:
    raw = (lang or "unknown").strip()
    key = raw.casefold().replace("-", "_")
    return LANG_ALIASES.get(key, raw.casefold())


def canonical_model_id(model: str) -> str:
    try:
        return MODEL_ALIASES[model]
    except KeyError as exc:
        raise ValueError(f"Unknown translation model id: {model}") from exc
