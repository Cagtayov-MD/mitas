"""Runtime adapters for CTranslate2-backed MT models."""

from __future__ import annotations

import re
from typing import Any

from core.pipelines.translate.models import load_translator


NLLB_LANGS = {
    "en": "eng_Latn",
    "eng_latn": "eng_Latn",
    "tr": "tur_Latn",
    "tur_latn": "tur_Latn",
    "ar": "arb_Arab",
    "arb_arab": "arb_Arab",
    "fr": "fra_Latn",
    "fra_latn": "fra_Latn",
    "de": "deu_Latn",
    "deu_latn": "deu_Latn",
    "it": "ita_Latn",
    "ita_latn": "ita_Latn",
    "es": "spa_Latn",
    "spa_latn": "spa_Latn",
}


def translate_text(
    *,
    model_id: str,
    source_text: str,
    source_lang: str,
    target_lang: str = "tr",
    device: str = "auto",
    beam_size: int = 4,
) -> str:
    loaded = load_translator(model_id, device=device)
    loaded.last_used = __import__("time").monotonic()
    if loaded.spec.kind == "opus":
        return _translate_opus(loaded.translator, loaded.tokenizer, source_text, source_lang, target_lang, beam_size)
    if loaded.spec.kind == "nllb":
        return _translate_nllb(loaded.translator, loaded.tokenizer, source_text, source_lang, target_lang, beam_size)
    raise ValueError(f"Unsupported translation model kind: {loaded.spec.kind}")


def _translate_opus(
    translator: Any,
    tokenizer: Any,
    source_text: str,
    source_lang: str,
    target_lang: str,
    beam_size: int,
) -> str:
    if _normalize_lang(source_lang) != "en" or _normalize_lang(target_lang) != "tr":
        raise ValueError("OPUS EN-TR model only supports en -> tr")
    source_tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(source_text))
    result = translator.translate_batch([source_tokens], beam_size=beam_size, max_batch_size=1)[0]
    target_ids = tokenizer.convert_tokens_to_ids(result.hypotheses[0])
    return clean_text(tokenizer.decode(target_ids, skip_special_tokens=True))


def _translate_nllb(
    translator: Any,
    tokenizer: Any,
    source_text: str,
    source_lang: str,
    target_lang: str,
    beam_size: int,
) -> str:
    source_code = _nllb_lang(source_lang)
    target_code = _nllb_lang(target_lang)
    tokenizer.src_lang = source_code
    source_tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(source_text))
    result = translator.translate_batch(
        [source_tokens],
        target_prefix=[[target_code]],
        beam_size=beam_size,
        max_batch_size=1,
    )[0]
    target_tokens = result.hypotheses[0][1:]
    target_ids = tokenizer.convert_tokens_to_ids(target_tokens)
    return clean_text(tokenizer.decode(target_ids, skip_special_tokens=True))


def clean_text(text: str) -> str:
    return re.sub(r"^>>\w+<<\s*", "", text).strip()


def _nllb_lang(lang: str) -> str:
    key = lang.casefold().replace("-", "_")
    try:
        return NLLB_LANGS[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported NLLB language code: {lang}") from exc


def _normalize_lang(lang: str) -> str:
    key = lang.casefold().replace("-", "_")
    if key in {"eng_latn", "english"}:
        return "en"
    if key in {"tur_latn", "turkish"}:
        return "tr"
    return key
