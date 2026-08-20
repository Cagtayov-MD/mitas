# -*- coding: utf-8 -*-
"""İzolasyon: kule başka kuleye / scripts/ / core/'ya kod-iphiyle bağlanmaz
(MAP.md kule sınırı; kobe/mcgrady test_izolasyon kalıbı)."""
import re
import sys
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
SRC = KULE / "src"

_YASAK = re.compile(
    r"(import\s+(kobe|jordan|nash|shaq|lebron\w*|sheriff|mcgrady)\b"
    r"|from\s+(kobe|jordan|nash|shaq|lebron\w*|sheriff|mcgrady)\b"
    r"|from\s+core\.|import\s+core\."
    r"|\bscripts/|\bOCR-worktree\b|\bvenvs/\w+)")

_DOCSTRING = re.compile(r'"""(?:.|\n)*?"""', re.DOTALL)


def _kod_metni(metin: str) -> str:
    temiz = _DOCSTRING.sub('""', metin)
    return "\n".join(l for l in temiz.splitlines()
                     if not l.strip().startswith("#"))


def test_src_disa_ip_yok():
    dosyalar = sorted(SRC.glob("*.py"))
    assert dosyalar, "src/ bos olmamaliydi"
    for d in dosyalar:
        kod = _kod_metni(d.read_text(encoding="utf-8"))
        assert not _YASAK.search(kod), d.name + ": dis bagimlilik ipi bulundu"


def test_ana_dosyalar_disa_ip_yok():
    for ad in ("main.py", "sozlesme.py"):
        kod = _kod_metni((KULE / ad).read_text(encoding="utf-8"))
        assert not _YASAK.search(kod), ad + ": dis bagimlilik ipi bulundu"


def test_kule_modulleri_import_edilebilir():
    sys.path.insert(0, str(KULE))
    sys.path.insert(0, str(SRC))
    import sozlesme    # noqa: F401
    import motor       # noqa: F401
    import channel_lang  # noqa: F401
    import sozlesme as s2
    assert "TRANSKRIPT" in s2.DURUMLAR and "ARIZA" in s2.DURUMLAR


def test_whisper_dil_kumesi_tutarli():
    from motor import _WHISPER_OK, _lang_unsupported
    assert "tr" in _WHISPER_OK and "en" in _WHISPER_OK
    assert "ku" not in _WHISPER_OK                 # Kürtçe-ailesi bilerek dışarıda
    assert _lang_unsupported("ku") is True
    assert _lang_unsupported("tr") is False
    assert _lang_unsupported(None) is True         # auto → whisper oto-tespit akışı
