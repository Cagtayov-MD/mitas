"""Public translation service API."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from core.pipelines.translate.cache import TranslationCache, build_cache_key
from core.pipelines.translate.post_edit import polish_turkish_broadcast
from core.pipelines.translate.router import load_router, normalize_lang
from core.pipelines.translate.runtime import translate_text


POST_EDIT_PROFILE = "broadcast_tr_v1"


@dataclass(frozen=True)
class TranslationResult:
    text: str
    model: str
    source_lang: str
    target_lang: str
    cache_hit: bool
    latency_ms: int
    created_at: str


def translate_segment(
    *,
    segment_id: str,
    source_text: str,
    source_lang: str,
    target_lang: str = "tr",
    model_override: str | None = None,
    cache_dir: Path,
) -> TranslationResult:
    if not segment_id:
        raise ValueError("segment_id is required")
    if not source_text.strip():
        raise ValueError("source_text is required")

    router = load_router()
    normalized_source = normalize_lang(source_lang)
    normalized_target = normalize_lang(target_lang)
    model_id = router.resolve(
        source_lang=normalized_source,
        target_lang=normalized_target,
        model_override=model_override,
    )
    key = build_cache_key(
        source_text=source_text,
        source_lang=normalized_source,
        target_lang=normalized_target,
        model=_cache_model_key(model_id, normalized_target),
    )
    cache = TranslationCache(cache_dir)
    cached = cache.get(key)
    if cached is not None:
        return _result_from_dict(cached, cache_hit=True, latency_ms=0)

    started = perf_counter()
    translated = translate_text(
        model_id=model_id,
        source_text=source_text,
        source_lang=normalized_source,
        target_lang=normalized_target,
    )
    if normalized_target == "tr":
        translated = polish_turkish_broadcast(
            translated,
            source_text=source_text,
            source_lang=normalized_source,
        )
    latency_ms = int(round((perf_counter() - started) * 1000))
    result = TranslationResult(
        text=translated,
        model=model_id,
        source_lang=normalized_source,
        target_lang=normalized_target,
        cache_hit=False,
        latency_ms=latency_ms,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    cache.put(key, asdict(result))
    return result


def translate_batch(
    items: list[dict[str, Any]],
    *,
    target_lang: str = "tr",
    cache_dir: Path,
    model_override: str | None = None,
) -> list[TranslationResult]:
    results: list[TranslationResult] = []
    for item in items:
        results.append(
            translate_segment(
                segment_id=str(item["segment_id"]),
                source_text=str(item["source_text"]),
                source_lang=str(item["source_lang"]),
                target_lang=target_lang,
                model_override=model_override,
                cache_dir=cache_dir,
            )
        )
    return results


def _result_from_dict(payload: dict[str, Any], *, cache_hit: bool, latency_ms: int | None = None) -> TranslationResult:
    return TranslationResult(
        text=str(payload["text"]),
        model=str(payload["model"]),
        source_lang=str(payload["source_lang"]),
        target_lang=str(payload["target_lang"]),
        cache_hit=cache_hit,
        latency_ms=int(payload["latency_ms"] if latency_ms is None else latency_ms),
        created_at=str(payload["created_at"]),
    )


def _cache_model_key(model_id: str, target_lang: str) -> str:
    if target_lang == "tr":
        return f"{model_id}:{POST_EDIT_PROFILE}"
    return model_id
