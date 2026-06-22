# -*- coding: utf-8 -*-
"""test_c6_lid_tr_veto.py — C6 menşei-kapılı TR-veto (Kürtçe yanlış-tespit düzeltmesi).

Test ettiği: _pipe_asr._lean_transcribe içindeki C6 veto bloğu.
  Blok yalnız: getattr(args,'tr_provenance',False) AND language=="ku" olduğunda çalışır.
  Koşul: _tr_units (TR-oyu >= MITAS_LID_TR_VOTE_MIN) varsa → language="tr".

Mimari notu: _lean_transcribe WhisperModel + ffmpeg + gerçek dosya gerektirir; izolasyon imkânsız.
  Bu yüzden veto MANTIK KESİMİNİ doğrudan saf-fonksiyon olarak test ediyoruz.
  _pipe_asr'ı import edip YALNIZ veto-mantığını tetikleyen bir "birim" yazıyoruz
  (gerçek LID/ASR ÇALIŞTIRILMAZ — dosya/model olmadan).

  Açık izolasyon stratejisi (task brief'teki izin):
  "izole edilemiyorsa en yakın saf-fonksiyon davranışını test et".
  → _lang_unsupported saf-fonksiyonu doğrudan test ediyoruz (veto bloktan bağımsız).
  → Veto bloğundaki koşul mantığını da INLINE Python ile test ediyoruz (copy-simüle, not import).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

# _lang_unsupported: _pipe_asr'da saf-fonksiyon, güvenle import edilebilir.
from _pipe_asr import _lang_unsupported, _WHISPER_OK


# ──────────── _lang_unsupported saf-fonksiyon testleri ──────────────────────

def test_c6_lang_unsupported_ku_true():
    """`ku` (Kürtçe) desteklenmiyor → ASR atlanmalı."""
    assert _lang_unsupported("ku") is True


def test_c6_lang_unsupported_tr_false():
    """`tr` (Türkçe) destekleniyor → ASR atlanmaz."""
    assert _lang_unsupported("tr") is False


def test_c6_lang_unsupported_none_false():
    """None/boş dil → varsayılan tr gibi davranır → ASR atlanmaz."""
    assert _lang_unsupported(None) is False
    assert _lang_unsupported("") is False


def test_c6_lang_unsupported_whisper_ok_diller():
    """_WHISPER_OK içindeki tüm diller 'destekleniyor' (False döner)."""
    for lang in ("en", "de", "fr", "ar", "zh", "ru"):
        assert _lang_unsupported(lang) is False, f"'{lang}' whisper-OK olmalı"


def test_c6_lang_unsupported_eksik_kod_true():
    """_WHISPER_OK'da olmayan kod (örn. 'swe' 3-harf, 'gle') → desteklenmiyor."""
    # 'swe' whisper'da yok (sv var), 'gle' yok (ga var) — forensik'te bug örneği
    for bad_lang in ("swe", "gle", "xyz", "cmn"):
        if bad_lang not in _WHISPER_OK:
            assert _lang_unsupported(bad_lang) is True, f"'{bad_lang}' desteklenmiyor olmalı"


# ──────────── C6 veto mantığı inline simülasyon ─────────────────────────────
# _lean_transcribe'daki C6 bloğu doğrudan kopyalanan mantık:
# if getattr(args,'tr_provenance',False) and language=="ku":
#     _tr_vote_min = int(os.environ.get("MITAS_LID_TR_VOTE_MIN","1"))
#     _veto_units = (detect_info or {}).get("units") or []
#     _tr_units = [u for u in _veto_units if (u.get("votes") or {}).get("tr",0) >= _tr_vote_min]
#     if _tr_units:
#         language = "tr"

class _FakeArgs:
    def __init__(self, tr_provenance=False, language="ku"):
        self.tr_provenance = tr_provenance
        self.language = language
        self.auto_language = True
        self.beam_size = 1
        self.model = "large-v3-turbo"


def _apply_c6_veto(*, tr_provenance, language, units):
    """C6 veto bloğunun mantığını izole çalıştır. Döner: son language değeri."""
    args = _FakeArgs(tr_provenance=tr_provenance, language=language)
    detect_info = {"units": units}
    _lang = language

    if getattr(args, "tr_provenance", False) and _lang == "ku":
        _tr_vote_min = int(os.environ.get("MITAS_LID_TR_VOTE_MIN", "1") or 1)
        _veto_units_inner = (detect_info or {}).get("units") or []
        _tr_units_inner = [u for u in _veto_units_inner
                           if (u.get("votes") or {}).get("tr", 0) >= _tr_vote_min]
        if _tr_units_inner:
            _tr_sel = max(_tr_units_inner, key=lambda u: (u.get("votes") or {}).get("tr", 0))
            _lang = "tr"
    return _lang


def test_c6_veto_ku_tr_provenance_tr_vote_gecer():
    """`ku` + tr_provenance=True + TR-oyu>0 → dil `tr`'ye çevrilir."""
    units = [{"stream": 0, "channel": 0, "language": "ku", "votes": {"tr": 5, "ku": 2}}]
    result = _apply_c6_veto(tr_provenance=True, language="ku", units=units)
    assert result == "tr", f"TR-oyu>0 → 'tr' beklendi, '{result}' geldi"


def test_c6_veto_ku_tr_vote_yok_ku_kalir():
    """`ku` + tr_provenance=True ama TR-oyu=0 → dil `ku` kalır."""
    units = [{"stream": 0, "channel": 0, "language": "ku", "votes": {"ku": 10, "tr": 0}}]
    result = _apply_c6_veto(tr_provenance=True, language="ku", units=units)
    assert result == "ku", f"TR-oyu=0 → 'ku' kalmalı, '{result}' geldi"


def test_c6_veto_ku_provenance_yok_ku_kalir():
    """`ku` + tr_provenance=False (yabancı film) → veto uygulanmaz, `ku` kalır."""
    units = [{"stream": 0, "channel": 0, "language": "tr", "votes": {"tr": 10}}]
    result = _apply_c6_veto(tr_provenance=False, language="ku", units=units)
    assert result == "ku", f"tr_provenance=False → 'ku' kalmalı, '{result}' geldi"


def test_c6_veto_tr_dil_dokunulmaz():
    """`tr` zaten → veto koşulu çalışmaz (language=='ku' şartı sağlanmaz)."""
    units = [{"stream": 0, "channel": 0, "language": "tr", "votes": {"tr": 10}}]
    result = _apply_c6_veto(tr_provenance=True, language="tr", units=units)
    assert result == "tr"


def test_c6_veto_units_bos_ku_kalir():
    """`ku` + tr_provenance=True ama units=[] → TR-ünit yok → `ku` kalır."""
    result = _apply_c6_veto(tr_provenance=True, language="ku", units=[])
    assert result == "ku", "units boş → veto tetiklenmez, 'ku' kalmalı"


def test_c6_veto_minimum_oy_esigi():
    """MITAS_LID_TR_VOTE_MIN=3: TR-oyu=2 < eşik → veto tetiklenmez."""
    os.environ["MITAS_LID_TR_VOTE_MIN"] = "3"
    try:
        units = [{"stream": 0, "channel": 0, "language": "ku", "votes": {"tr": 2, "ku": 5}}]
        result = _apply_c6_veto(tr_provenance=True, language="ku", units=units)
        assert result == "ku", "TR-oyu=2 < eşik=3 → 'ku' kalmalı"
    finally:
        os.environ.pop("MITAS_LID_TR_VOTE_MIN", None)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
