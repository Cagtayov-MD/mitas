"""Rol sözlüğü senkron bekçisi — sessiz çatallanma YASAK (2026-08-18).

Kobe rol tablosunun kendi kopyasını taşır (Allstar-içi bağımsızlaşma,
2026-08-18). İki kopya arasında otomatik senkron MEKANİZMASI yoktur —
bu test ayrışmayı GÖRÜNÜR kılar: içerik farklılaşınca kırmızıya düşer
ve hangi yönde geride kalındığını söyler:

  - core'da yeni satır var, Kobe'de yok → Kobe geri kalır: yeni rolü
    "kredi satırı" tanımaz, jenerik sınırı/havuzu o filmde sapar.
  - Kobe'de yeni satır var, core'da yok → okuma kuleleri geri kalır:
    senkron yönüne (kobe→core mu, tersi mi) insan karar verir.

Kule bağımsızlığı korunur: dış dosya yoksa test SKIP edilir — kule kendi
kopyasıyla tek başına çalışabilmelidir (KATALOG: "eski dış dosyalar
silinse de kule çalışabilir"). Bu test kule için bağımlılık DEĞİL,
iki taraf da varken dürüstlük taahhüdüdür.
"""
import difflib
import os
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
KOBE_KOPYA = KULE / "src" / "ortak" / "rol_tablosu.py"
ASIL = (Path(os.environ.get("MITAS_PROJECT_ROOT") or "/opt/mitas")
        / "core" / "lexicon" / "rol_tablosu.py")


def _icerik(p: Path) -> list[str]:
    """Kozmetik farklar (boş satır, satır-sonu boşluğu) dışarıda bırakılır —
    yalnız İÇERİK ayrışması kırmızıya düşürür."""
    return [satir.rstrip() for satir in p.read_text(encoding="utf-8").splitlines()
            if satir.strip()]


def test_rol_sozlugu_asilla_catallasmamis():
    if not KOBE_KOPYA.exists():
        pytest.fail("Kobe'nin rol sözlüğü kopyası yok — kule çalışamaz")
    if not ASIL.exists():
        pytest.skip("dış rol tablosu yok — kule kendi kopyasıyla bağımsız çalışır")
    kobe, asil = _icerik(KOBE_KOPYA), _icerik(ASIL)
    if kobe == asil:
        return
    sadece_asil = {s for s in asil if s not in set(kobe)}
    sadece_kobe = {s for s in kobe if s not in set(asil)}
    fark = "\n".join(list(difflib.unified_diff(asil, kobe,
                                               "core/lexicon (asil)",
                                               "kobe (kopya)"))[:25])
    pytest.fail(
        "Rol sözlüğü ÇATALLANDI — sessiz ayrışma yasak.\n"
        f"• core'da olup Kobe'de olmayan: {len(sadece_asil)} satır "
        "(Kobe GERİDE — yeni rolleri kredi tanımaz, jenerik sınırı sapar)\n"
        f"• Kobe'de olup core'da olmayan: {len(sadece_kobe)} satır "
        "(okuma kuleleri GERİDE — senkron yönüne karar ver)\n"
        f"Karar: hangisi doğrusa öbürüne taşı, ya da bilinçli çatallama ise "
        f"bu testte istisna belgele.\nİlk farklar:\n{fark}")
