"""Tests for the content-profile-aware summary prompt builder.

`_summary_messages` lives in `core.api.asr_server`, which imports FastAPI.
The `core` venv does not always have FastAPI installed, so the whole module
is skipped when the import is unavailable (same gating as the live-STT API
tests).
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from core.api.asr_server import _clean_model_output, _summary_messages  # noqa: E402


TRANSCRIPT = "Fenerbahçe Galatasaray maçı 2-1 sona erdi. Hakem ikinci yarıda kırmızı kart gösterdi."
NEUTRAL_TRANSCRIPT = "Bugün hava çok güzeldi ve sabahki toplantı oldukça verimli geçti."


def _user_content(messages: list[dict[str, str]]) -> str:
    return next(m["content"] for m in messages if m["role"] == "user")


def _system_content(messages: list[dict[str, str]]) -> str:
    return next(m["content"] for m in messages if m["role"] == "system")


def test_spor_profile_uses_sports_question_set() -> None:
    messages = _summary_messages(
        {"content_profile": "spor", "filename": "mac.mp4"}, TRANSCRIPT
    )
    user = _user_content(messages)
    system = _system_content(messages)

    assert "spor müsabakası" in user
    assert "FUTBOL" in user
    # Güncel prompt "futbol / DİĞER BRANŞLAR" yapısına geçti; BASKETBOL başlığı yok.
    assert "DİĞER BRANŞLAR" in user
    # Skor başlığı "Maç Sonucu" yerine "Skor:" olarak güncellendi.
    assert "Skor:" in user
    assert "kırmızı kart" in user
    # Anti-halüsinasyon sözleşmesi: "transkriptte belirtilmemiş" değil,
    # "geçmeyeni hiç yazma" talimatı kullanılıyor.
    assert "geçmeyeni hiç yazma" in user
    assert TRANSCRIPT in user
    # Anti-hallucination contract must be stated to the model.
    assert "halüsinasyon" in system or "tahmin" in system


def test_clean_model_output_strips_think_blocks() -> None:
    raw = "<think>önce planlıyorum\nçok satır</think>\n\nNihai Türkçe özet."
    assert _clean_model_output(raw) == "Nihai Türkçe özet."


def test_clean_model_output_truncates_chat_control_and_prompt_echo() -> None:
    raw = "## Maç Sonucu\n- Skor: 2-1<|endoftext|><|im_start|>user\nAşağıdaki transkript..."
    assert _clean_model_output(raw) == "## Maç Sonucu\n- Skor: 2-1"


def test_clean_model_output_is_noop_for_clean_text() -> None:
    clean = "## Maç Bilgisi\n- Takımlar: A - B"
    assert _clean_model_output(clean) == clean


def test_clean_model_output_falls_back_when_emptied() -> None:
    # Unbalanced/truncated reasoning with no real answer must not return blank.
    assert _clean_model_output("<think>only reasoning, no answer").strip() != ""


@pytest.mark.parametrize("content_profile", ["bulten_haber", None])
def test_non_sports_profile_keeps_generic_prompt(content_profile: str | None) -> None:
    job: dict[str, object] = {"filename": "haber.mp4"}
    if content_profile is not None:
        job["content_profile"] = content_profile

    messages = _summary_messages(job, NEUTRAL_TRANSCRIPT)
    user = _user_content(messages)

    # Original generic instruction is preserved verbatim.
    assert "Aşağıdaki medya transkriptini Türkçe olarak özetle." in user
    assert NEUTRAL_TRANSCRIPT in user
    # Sports-only markers must NOT leak into the generic path.
    assert "kırmızı kart" not in user
    assert "Maç Sonucu" not in user
