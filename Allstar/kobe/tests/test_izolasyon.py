"""ÇIKIŞ GİRİŞİN İŞİNE KARIŞMAZ — Çağatay kuralı, 2026-08-13.

İki bölüm aynı kulede yaşar ama karar mantıkları AYRIDIR ve ayrı kalır.
Sebep somut: çıkışın temel ayracı `SON_ERISIM = 0.82` ("krediler pencerenin
sonuna kadar akar") giriş jeneriğinde TERS çalışır — girişte krediler biter ve
film devam eder. Bir bölümün eşiği diğerine sızarsa sessizce yanlış cevap
üretilir; patlamaz, yanlış olur. En kötü arıza türü.

İzin verilen tek paylaşım ALETLERDİR (`kutu.py` = Paddle det, `icerik.py` =
kredi metni testi). Bunlar karar vermez, ölçüm yapar.

Bu test kuralı kodda kilitler. Birleştirmek isteyen önce burayı silmek
zorunda kalsın — yanlışlıkla değil, bilerek yapsın.
"""
import ast
import sys
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
SRC = KULE / "src"
GIRIS = SRC / "giris"

# Karar veren, bölüme özgü modüller. Alet DEĞİLler.
CIKIS_MODULU = "motor"
GIRIS_MODULLERI = ("sinir", "havuz")

# Yalnız çıkışa ait, girişe sızarsa sessizce yanlış cevap üreten eşikler.
CIKIS_ESIKLERI = ("SON_ERISIM", "SON_ERISIM_GEVSEK")


def _import_adlari(yol: Path) -> set[str]:
    """Dosyanın import ettiği tepe-seviye modül adları (ast ile, çalıştırmadan)."""
    agac = ast.parse(yol.read_text(encoding="utf-8"), filename=str(yol))
    adlar: set[str] = set()
    for d in ast.walk(agac):
        if isinstance(d, ast.Import):
            for a in d.names:
                adlar.add(a.name.split(".")[0])
        elif isinstance(d, ast.ImportFrom) and d.module:
            adlar.add(d.module.split(".")[0])
    return adlar


def _giris_dosyalari() -> list[Path]:
    return sorted(p for p in GIRIS.glob("*.py") if p.name != "__init__.py")


def test_giris_dosyalari_var():
    """Bekçi: giriş bloğu silinip test sessizce boş geçmesin."""
    d = _giris_dosyalari()
    assert d, f"{GIRIS} altında modül yok — izolasyon testi boşa koşuyor"
    adlar = {p.stem for p in d}
    assert set(GIRIS_MODULLERI) <= adlar, f"beklenen {GIRIS_MODULLERI}, bulunan {adlar}"


@pytest.mark.parametrize("yol", _giris_dosyalari(), ids=lambda p: p.name)
def test_giris_motoru_import_etmez(yol):
    """Giriş, çıkışın karar motorunu çağıramaz."""
    assert CIKIS_MODULU not in _import_adlari(yol), (
        f"{yol.name} '{CIKIS_MODULU}' import ediyor — çıkış girişin işine karışıyor. "
        "Ortak ihtiyaç varsa alet olarak src/ altına çıkar, motoru çağırma."
    )


@pytest.mark.parametrize("yol", _giris_dosyalari(), ids=lambda p: p.name)
def test_cikis_esikleri_girise_sizmaz(yol):
    """`SON_ERISIM` girişte TERS çalışır — adı bile geçmemeli."""
    metin = yol.read_text(encoding="utf-8")
    for esik in CIKIS_ESIKLERI:
        assert esik not in metin, (
            f"{yol.name} içinde '{esik}' geçiyor. Bu eşik çıkışa özgüdür ve "
            "girişte ters çalışır (girişte krediler biter, film devam eder)."
        )


def test_motor_giris_blogunu_import_etmez():
    """Çıkış da girişi tanımaz — bağımlılık iki yönde de yok."""
    adlar = _import_adlari(SRC / f"{CIKIS_MODULU}.py")
    yasak = set(GIRIS_MODULLERI) | {"giris"}
    assert not (adlar & yasak), (
        f"motor.py {adlar & yasak} import ediyor — çıkış girişe bağlandı"
    )


def test_yonlendirme_main_de_kalir():
    """Hangi bölümün hangi kodu çalıştıracağını YALNIZ main.py bilir.

    Bölüm modülleri 'ben giriş miyim çıkış mıyım' diye dallanmaz; dallanırsa
    iki mantık tek dosyada birleşmeye başlamış demektir.
    """
    sys.path.insert(0, str(KULE))
    metin = (KULE / "main.py").read_text(encoding="utf-8")
    assert 'bolum == "giris"' in metin or "bolum == 'giris'" in metin, (
        "main.py bölüm yönlendirmesini yapmıyor — yönlendirme başka yere kaçmış olabilir"
    )
