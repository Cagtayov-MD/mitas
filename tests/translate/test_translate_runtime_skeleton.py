from __future__ import annotations

from pathlib import Path

from core.pipelines.translate.cache import TranslationCache, build_cache_key
from core.pipelines.translate.dialect import detect_arabic_variant, normalize_arabic_dialect_text
from core.pipelines.translate.router import NLLB_3B, OPUS_EN_TR, load_router, normalize_lang
from core.pipelines.translate.runtime import _nllb_lang
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


def test_arabic_language_aliases_normalize_for_nllb() -> None:
    assert normalize_lang("Arabic") == "ar"
    assert normalize_lang("arb_Arab") == "ar"
    assert _nllb_lang("ar") == "arb_Arab"
    assert _nllb_lang("arabic") == "arb_Arab"


def test_levantine_arabic_is_detected_and_normalized_for_mt() -> None:
    source = "هلأ أنا ليش بد نروح لعندي على البيت يعني"

    assert detect_arabic_variant(source) == "ar-levantine"
    normalized = normalize_arabic_dialect_text(source, "ar-levantine")

    assert "الآن" in normalized
    assert "لماذا" in normalized
    assert "أنا لماذا يجب أن ن" not in normalized
    assert "يجب أن نذهب" in normalized
    assert "إلى بيتي" in normalized


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


def test_translate_segment_prepares_levantine_source_before_runtime(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_translate_text(**kwargs: object) -> str:
        captured.update(kwargs)
        return "Yani şimdi neden benim eve gitmemiz gerekiyor?"

    monkeypatch.setattr("core.pipelines.translate.service.translate_text", fake_translate_text)

    result = translate_segment(
        segment_id="seg_1",
        source_text="هلأ أنا ليش بد نروح لعندي على البيت يعني",
        source_lang="ar",
        cache_dir=tmp_path,
    )

    assert result.source_variant == "ar-levantine"
    assert result.text == "Yani şimdi neden benim eve gitmemiz gerekiyor?"
    assert captured["source_lang"] == "ar"
    assert "يجب أن نذهب" in str(captured["source_text"])


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


def test_translate_segment_applies_broadcast_post_edit(monkeypatch, tmp_path: Path) -> None:
    def fake_translate_text(**kwargs: object) -> str:
        return "Başbakan, tartışmayı tekrar başlatamayız, lütfen, sadece zamanımız yok."

    monkeypatch.setattr("core.pipelines.translate.service.translate_text", fake_translate_text)

    result = translate_segment(
        segment_id="seg_1",
        source_text="Prime Minister, we can't start the debate again, please, we just don't have time.",
        source_lang="en",
        cache_dir=tmp_path,
    )

    assert result.text == "Sayın Başbakan, tartışmayı yeniden açamayız, lütfen; buna zamanımız yok."
