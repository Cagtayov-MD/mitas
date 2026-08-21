"""tests/test_izolasyon.py — giriş/çıkış eşik izolasyonu kilidi.

docs/PLAN.md §1: "bölüm yönlendirmesi YALNIZ main.py'de olacak; eşikler
bölüm-özel sözlükte tutulacak... bölüm modülleri 'ben giriş miyim' diye
dallanmaz." Gerekçe (aynı belge): "bir bölümün eşiği diğerine sızarsa kod
patlamaz — SESSİZCE YANLIŞ CEVAP üretir."

Bu test src/ altındaki her .py dosyasını AST ile tarar (regex DEĞİL — yorum
satırı/docstring içindeki düz metin yanlış pozitif üretmesin diye):

1. `bolum == "giris"` tarzı karşılaştırma → src/ İÇİNDE YASAK.
2. Hem "giris": hem "cikis": anahtarlı bir sözlük literali → src/ İÇİNDE
   YASAK (main.py'nin ESIK_GIRIS/ESIK_CIKIS ayrımını tekrarlıyor demektir).

src/ altında henüz bölüm-hassas modül yoksa (yalnız __init__.py, ya da hiç
dosya yok) test SKIP olur — FAZ 0'da bu beklenen durumdur. Modül belirdiğinde
otomatik olarak taranmaya başlar; dosya adı sabitlenmiş DEĞİLDİR.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
SRC = KOK / "src"


def _taranacak_dosyalar() -> list[Path]:
    if not SRC.is_dir():
        return []
    return sorted(p for p in SRC.rglob("*.py") if p.name != "__init__.py")


@pytest.fixture(scope="module")
def dosyalar() -> list[Path]:
    d = _taranacak_dosyalar()
    if not d:
        pytest.skip("src/ altinda henuz bolum-hassas modul yok (FAZ 0)")
    return d


def _agaç(dosya: Path) -> ast.AST | None:
    try:
        return ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))
    except SyntaxError:
        return None  # yarim/WIP dosya olabilir — bu testin sorumlulugu degil


def _bolum_karsilastirmasi_var_mi(dugum: ast.Compare) -> bool:
    taraflar = [dugum.left, *dugum.comparators]
    isimli = any(
        isinstance(t, (ast.Name, ast.Attribute))
        and "bolum" in getattr(t, "id", getattr(t, "attr", "")).lower()
        for t in taraflar)
    sabitli = any(
        isinstance(t, ast.Constant) and t.value in ("giris", "cikis")
        for t in taraflar)
    return isimli and sabitli


def test_src_modulleri_bolume_gore_dallanmaz(dosyalar):
    """'ben giriş miyim / çıkış mıyım' karşılaştırması src/ içinde YASAK —
    bu karar main.py'nin (özellikle _esik()) tekelinde olmalı."""
    ihlaller = []
    for p in dosyalar:
        agac = _agaç(p)
        if agac is None:
            continue
        for dugum in ast.walk(agac):
            if isinstance(dugum, ast.Compare) and _bolum_karsilastirmasi_var_mi(dugum):
                ihlaller.append(f"{p.relative_to(KOK)}:{dugum.lineno}: "
                                f"{ast.unparse(dugum)}")
    assert not ihlaller, (
        "src/ altinda bolum karsilastirmasi bulundu — yonlendirme YALNIZ "
        "main.py'de olmali (docs/PLAN.md §1, Kobe kanunu):\n" + "\n".join(ihlaller))


def test_src_modulleri_iki_bolumun_esigini_birden_tasimaz(dosyalar):
    """Bir src/ modülü HEM 'giris': HEM 'cikis': anahtarlı bir sözlük
    taşıyorsa, main.py'nin ESIK_GIRIS/ESIK_CIKIS ayrımını kendi içinde
    tekrarlıyor demektir — bölüm bilgisi sızmış."""
    ihlaller = []
    for p in dosyalar:
        agac = _agaç(p)
        if agac is None:
            continue
        for dugum in ast.walk(agac):
            if not isinstance(dugum, ast.Dict):
                continue
            anahtarlar = {k.value for k in dugum.keys
                          if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            if {"giris", "cikis"} <= anahtarlar:
                ihlaller.append(f"{p.relative_to(KOK)}:{dugum.lineno}")
    assert not ihlaller, (
        "src/ modulu iki bolumun esik anahtarini birden taniyor — bolum-ozel "
        "sozluk YALNIZ main.py'de olmali:\n" + "\n".join(ihlaller))


def test_main_py_esikleri_bolum_ozel_tutar():
    """İzolasyonun pozitif kanıt tarafı: main.py, ESIK_GIRIS ve ESIK_CIKIS'i
    AYRI sözlükler olarak tutmalı ve bölüm→eşik çözümü tek bir fonksiyonda
    olmalı (src/ tarafının değil, main.py'nin bu sorumluluğu gerçekten
    üstlendiğini doğrular — her zaman çalışır, src/ boş olsa bile)."""
    metin = (KOK / "main.py").read_text(encoding="utf-8")
    assert "ESIK_GIRIS" in metin and "ESIK_CIKIS" in metin, (
        "main.py bolum-ozel esik sozluklerini kaybetmis olabilir")
    agac = ast.parse(metin, filename=str(KOK / "main.py"))
    fonksiyonlar = {d.name for d in ast.walk(agac) if isinstance(d, ast.FunctionDef)}
    assert "_esik" in fonksiyonlar, (
        "bolum -> esik cozumu main.py icinde ayri bir fonksiyon olmali (_esik)")
