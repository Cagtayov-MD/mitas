# -*- coding: utf-8 -*-
"""İzolasyon: kule başka kuleye / scripts/ / pdf-mitas/'a kod-iphiyle bağlanmaz
(MAP.md kule sınırı; kobe test_izolasyon kalıbı). Zemin (duckdb) VERİ okuma
yasak DEĞİL — salt-okunur paylaşım kuralı gereği."""
import re
import sys
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
SRC = KULE / "src"

# Metin-içi yasak ipuçları: kardeş kule adları ve mitas kod dizinleri.
_YASAK_IMPORT = re.compile(
    r"(import\s+(kobe|jordan|nash|shaq|lebron\w*|sheriff)\b"
    r"|from\s+(kobe|jordan|nash|shaq|lebron\w*|sheriff)\b"
    r"|\bscripts/|\bOCR-worktree\b|\bpdf-mitas\b|\bcore\.lexicon\b)")

# docstring'ler (üç-tırnak) provenans notu taşır — kod düzeyi denetiminden çıkarılır.
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
        assert not _YASAK_IMPORT.search(kod), f"{d.name}: dis bagimlilik ipi bulundu"


def test_ana_dosyalar_disa_ip_yok():
    for ad in ("main.py", "sozlesme.py"):
        kod = _kod_metni((KULE / ad).read_text(encoding="utf-8"))
        assert not _YASAK_IMPORT.search(kod), f"{ad}: dis bagimlilik ipi bulundu"


def test_kule_modulleri_import_edilebilir():
    # sys.path'e YALNIZ kule yolları eklenmiş durumda garble/web_cache/motor açılır.
    sys.path.insert(0, str(KULE))
    sys.path.insert(0, str(SRC))
    import garble      # noqa: F401
    import web_cache   # noqa: F401
    import motor       # noqa: F401
    import sozlesme    # noqa: F401


def test_poster_ok_kapisi_gecici_dosyalarla(tmp_path):
    from motor import _poster_ok
    from PIL import Image
    # küçük dosya → RED
    kucuk = tmp_path / "kucuk.jpg"
    kucuk.write_bytes(b"x" * 100)
    assert _poster_ok(str(kucuk))["gecerli"] is False
    # yatay → RED ("afiş yerine foto" tuzağı)
    yatay = tmp_path / "yatay.jpg"
    Image.new("RGB", (400, 200), "red").save(yatay)
    assert _poster_ok(str(yatay))["gecerli"] is False
    # portre + >5KB → GEÇER
    portre = tmp_path / "portre.jpg"
    im = Image.new("RGB", (200, 400))
    for i in range(0, 400, 4):            # >5KB olacak şekilde gürültü bas
        for j in range(0, 200, 4):
            im.putpixel((j, i), (i % 256, j % 256, (i * j) % 256))
    im.save(portre)
    assert portre.stat().st_size > 5000
    assert _poster_ok(str(portre))["gecerli"] is True
