"""Faz 6 — Legacy opt-out env var contract.

Verifies the boundary semantics of ``_is_legacy_credit_pipeline()``:

* Default is text-first (no env).
* ``USE_LEGACY_CREDIT_PIPELINE=1`` opts into the legacy 8-stage path.
* ``USE_BOX_TRACK_PIPELINE=0`` keeps back-compat with the old env name.
* When both are set, the legacy trigger wins (explicit > implicit).
* The literal value contract is strict — typos do not re-enable legacy.
"""

from __future__ import annotations

import pytest

from core.pipelines.ocr.credit_experiment import _is_legacy_credit_pipeline


def test_default_uses_text_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env unset → text-first (legacy disabled)."""
    monkeypatch.delenv("USE_LEGACY_CREDIT_PIPELINE", raising=False)
    monkeypatch.delenv("USE_BOX_TRACK_PIPELINE", raising=False)
    assert _is_legacy_credit_pipeline() is False


def test_legacy_env_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """USE_LEGACY_CREDIT_PIPELINE=1 → legacy path enabled."""
    monkeypatch.setenv("USE_LEGACY_CREDIT_PIPELINE", "1")
    monkeypatch.delenv("USE_BOX_TRACK_PIPELINE", raising=False)
    assert _is_legacy_credit_pipeline() is True


def test_legacy_env_via_backcompat(monkeypatch: pytest.MonkeyPatch) -> None:
    """USE_BOX_TRACK_PIPELINE=0 still enables legacy (back-compat)."""
    monkeypatch.delenv("USE_LEGACY_CREDIT_PIPELINE", raising=False)
    monkeypatch.setenv("USE_BOX_TRACK_PIPELINE", "0")
    assert _is_legacy_credit_pipeline() is True


def test_legacy_env_priority_legacy_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """USE_LEGACY=1 AND USE_BOX_TRACK=1 → legacy still wins (explicit opt-in)."""
    monkeypatch.setenv("USE_LEGACY_CREDIT_PIPELINE", "1")
    monkeypatch.setenv("USE_BOX_TRACK_PIPELINE", "1")
    assert _is_legacy_credit_pipeline() is True


def test_legacy_env_normal_case_text_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """USE_BOX_TRACK_PIPELINE=1 (old, explicit text-first) → text-first."""
    monkeypatch.delenv("USE_LEGACY_CREDIT_PIPELINE", raising=False)
    monkeypatch.setenv("USE_BOX_TRACK_PIPELINE", "1")
    assert _is_legacy_credit_pipeline() is False


def test_legacy_env_invalid_value_defaults_to_text_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Garbage values do not silently re-enable the legacy path."""
    monkeypatch.setenv("USE_LEGACY_CREDIT_PIPELINE", "xyz")
    monkeypatch.delenv("USE_BOX_TRACK_PIPELINE", raising=False)
    assert _is_legacy_credit_pipeline() is False


def test_legacy_env_whitespace_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Surrounding whitespace must not defeat the literal-string check."""
    monkeypatch.setenv("USE_LEGACY_CREDIT_PIPELINE", "  1  ")
    monkeypatch.delenv("USE_BOX_TRACK_PIPELINE", raising=False)
    assert _is_legacy_credit_pipeline() is True


def test_legacy_env_empty_string_is_text_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty string env vars must not flip behaviour (explicit unset semantics)."""
    monkeypatch.setenv("USE_LEGACY_CREDIT_PIPELINE", "")
    monkeypatch.setenv("USE_BOX_TRACK_PIPELINE", "")
    assert _is_legacy_credit_pipeline() is False
