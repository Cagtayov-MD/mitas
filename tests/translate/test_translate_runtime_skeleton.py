from __future__ import annotations

from pathlib import Path

from core.pipelines.translate.cache import TranslationCache, build_cache_key
from core.pipelines.translate.router import NLLB_3B, OPUS_EN_TR, load_router
from core.pipelines.translate.service import translate_batch, translate_segment


def test_cache_roundtrip(tmp_path: Path) -> None:
    cache = TranslationCache(tmp_path)
    key = build_cache_key(source_text="hello", source_lang="en", target_lang="tr", model=OPUS_EN_TR)
    result = {
        "text": "merhaba",
        "model": OPUS_EN_TR,
        "source_lang": "en",
        "target_lang": "tr",
        "cache_hit": False,
        "latency_ms": 12,
        "created_at": "2026-05-15T00:00:00+00:00",
    }

    cache.put(key, result)

    assert cache.get(key) == result
    assert (tmp_path / "cache.jsonl").exists()


def test_default_router_routes_english_to_opus_and_fallback_to_nllb() -> None:
    router = load_router(config_path=Path("missing-router.yaml"))

    assert router.resolve(source_lang="en") == OPUS_EN_TR
    assert router.resolve(source_lang="eng_Latn") == OPUS_EN_TR
    assert router.resolve(source_lang="fr") == NLLB_3B


def test_translate_segment_uses_cache(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_translate_text(**kwargs: object) -> str:
        calls.append(str(kwargs["source_text"]))
        return "merhaba"

    monkeypatch.setattr("core.pipelines.translate.service.translate_text", fake_translate_text)

    first = translate_segment(
        segment_id="seg_1",
        source_text="hello",
        source_lang="en",
        cache_dir=tmp_path,
    )
    second = translate_segment(
        segment_id="seg_1",
        source_text="hello",
        source_lang="en",
        cache_dir=tmp_path,
    )

    assert first.text == "merhaba"
    assert first.cache_hit is False
    assert second.text == "merhaba"
    assert second.cache_hit is True
    assert second.latency_ms == 0
    assert calls == ["hello"]


def test_translate_batch_preserves_order(monkeypatch, tmp_path: Path) -> None:
    def fake_translate_text(**kwargs: object) -> str:
        return f"tr:{kwargs['source_text']}"

    monkeypatch.setattr("core.pipelines.translate.service.translate_text", fake_translate_text)
    results = translate_batch(
        [
            {"segment_id": "seg_1", "source_text": "hello", "source_lang": "en"},
            {"segment_id": "seg_2", "source_text": "world", "source_lang": "en"},
        ],
        cache_dir=tmp_path,
    )

    assert [result.text for result in results] == ["tr:hello", "tr:world"]
    assert [result.model for result in results] == [OPUS_EN_TR, OPUS_EN_TR]
