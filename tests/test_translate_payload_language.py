from __future__ import annotations


def test_translate_payload_detects_arabic_script_even_when_declared_english() -> None:
    from core.api.asr_server import _prepare_translate_payload

    payload = _prepare_translate_payload(
        {
            "items": [
                {
                    "segment_id": "seg_0001",
                    "source_text": "هلأ أنا ليش بد نروح لعندي على البيت يعني",
                    "source_lang": "en",
                }
            ]
        }
    )

    assert payload["items"][0]["source_lang"] == "ar"
    assert payload["items"][0]["source_variant"] == "ar-levantine"


def test_translate_payload_preserves_explicit_arabic_variant() -> None:
    from core.api.asr_server import _prepare_translate_payload

    payload = _prepare_translate_payload(
        {
            "items": [
                {
                    "segment_id": "seg_0001",
                    "source_text": "دلوقتي عايز أروح البيت",
                    "source_lang": "ar",
                    "source_variant": "egyptian",
                }
            ]
        }
    )

    assert payload["items"][0]["source_lang"] == "ar"
    assert payload["items"][0]["source_variant"] == "ar-egyptian"
