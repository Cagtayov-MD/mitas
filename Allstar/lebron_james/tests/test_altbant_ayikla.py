"""Alt-bant kurtarmaları LeBron'un birleştirmesinden çıkarılır (2026-08-20).

Kobe giriş havuzu artık alt bantta yazan kareleri de alıyor (oyuncu isimleri
orada yazıyor; eskiden "altyazı" sanılıp eleniyordu ve isim kayboluyordu).
Ama o kareler aynı DURAN kartın neredeyse aynı kopyaları — LeBron'un kayma
ölçümünü sulandırıyorlar.

ÖLÇÜLDÜ (Çiçek Taksi b2 girişi): havuz 93 → 127 kareye çıkınca master
6087 px / 21 segment yerine 449 px / 1 segment'e çöktü ve kule ARIZA verdi.

Karar: kareler havuzda KALIR (Nash ve Jordan onları tek tek okur), yalnız
LeBron'un listesinden düşer. Manifesto yoksa eski davranış aynen sürer.
"""
import sys
from pathlib import Path

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE / "src"))

import json  # noqa: E402

from yukleyici import kareler  # noqa: E402


def _havuz(tmp_path, adlar, siniflar=None):
    for a in adlar:
        (tmp_path / a).write_bytes(b"x")
    if siniflar is not None:
        (tmp_path / "_sinif.json").write_text(
            json.dumps(siniflar, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_alt_bant_kareleri_elenir(tmp_path):
    d = _havuz(tmp_path, ["g_0027.png", "g_0030.png", "g_0037.png"],
               {"g_0027.png": "icerik", "g_0030.png": "recall_altbant",
                "g_0037.png": "icerik"})
    assert [p.name for p in kareler(d)] == ["g_0027.png", "g_0037.png"]


def test_manifesto_yoksa_ESKI_davranis(tmp_path):
    """Geriye uyum: eski havuzlarda manifesto yok, hicbir sey elenmemeli."""
    d = _havuz(tmp_path, ["g_0027.png", "g_0030.png"])
    assert [p.name for p in kareler(d)] == ["g_0027.png", "g_0030.png"]


def test_bozuk_manifesto_sessizce_gecer(tmp_path):
    """Manifesto bozuksa kule DURMAZ — eleme yapmaz, kareler korunur."""
    d = _havuz(tmp_path, ["g_0027.png", "g_0030.png"])
    (d / "_sinif.json").write_text("{bozuk", encoding="utf-8")
    assert len(kareler(d)) == 2


def test_manifesto_kare_olarak_sayilmaz(tmp_path):
    """_sinif.json bir kare degildir; DESEN png/jpg oldugu icin zaten girmez."""
    d = _havuz(tmp_path, ["g_0027.png"], {"g_0027.png": "icerik"})
    assert [p.name for p in kareler(d)] == ["g_0027.png"]


def test_dogal_sira_korunur(tmp_path):
    d = _havuz(tmp_path, ["g_0009.png", "g_0010.png", "g_0002.png"],
               {"g_0009.png": "icerik", "g_0010.png": "icerik",
                "g_0002.png": "icerik"})
    assert [p.name for p in kareler(d)] == ["g_0002.png", "g_0009.png",
                                            "g_0010.png"]
