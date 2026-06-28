# -*- coding: utf-8 -*-
"""test_pdf_lang_fallback_20260628.py — SAĞLAM DİL aktarımı (_pipe_pdf).

Test ettiği:
  • DECOUPLE: konuşma dili tespit edildiyse, kanal-listesi (der[0]) boş olsa bile
    "ana_dil" PDF bloğuna yazılır (eskiden der[0]'a bağlıydı → düşüyordu).
  • ASR FALLBACK: chlang dil vermediyse, --asr-lang (whisper'ın dili) ana_dil olur.
  • EZMEME: chlang dili varsa, asr-lang fallback onu EZMEZ.

NOT: _pipe_pdf import'u sys.stdout.reconfigure çağırır → pytest'i -s ile koş (capture kapalı)
veya doğrudan `python tests/test_pdf_lang_fallback_20260628.py`.
"""
import os
import sys
import json
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import _pipe_pdf as P  # noqa: E402


def _args(**kw):
    base = dict(chlang="", subtitle="", video="", asr_lang="")
    base.update(kw)
    return SimpleNamespace(**base)


def _chlang_file(obj):
    fd, p = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return p


def test_decouple_lang_without_channels():
    """Dil var ama konuşma-kanalı listesi boş → ana_dil YİNE yazılır (decouple fix)."""
    p = _chlang_file({"summary_language": "Türkçe", "units": []})
    try:
        blk = P.audio_subtitle_block(_args(chlang=p))
        assert blk.get("ana_dil") == P._lang_code("Türkçe"), blk
        assert blk.get("ana_dil") not in (None, "", "—"), blk
    finally:
        os.remove(p)


def test_asr_lang_fallback_when_no_chlang_lang():
    """chlang dil vermedi (summary_language None) + --asr-lang en → ana_dil = EN."""
    p = _chlang_file({"summary_language": None, "units": []})
    try:
        blk = P.audio_subtitle_block(_args(chlang=p, asr_lang="en"))
        assert blk.get("ana_dil") == "EN", blk
    finally:
        os.remove(p)


def test_asr_lang_does_not_override_detected():
    """chlang dili TR ise, --asr-lang en fallback onu EZMEZ (mevcut tespit korunur)."""
    p = _chlang_file({"summary_language": "Türkçe", "units": []})
    try:
        blk = P.audio_subtitle_block(_args(chlang=p, asr_lang="en"))
        assert blk.get("ana_dil") == P._lang_code("Türkçe"), blk
        assert blk.get("ana_dil") != "EN", blk
    finally:
        os.remove(p)


def test_no_chlang_no_asr_lang_empty():
    """Ne chlang ne asr-lang → ana_dil set edilmez (yanlış dil uydurma yok)."""
    blk = P.audio_subtitle_block(_args())
    assert not blk.get("ana_dil"), blk


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "-s"]))
