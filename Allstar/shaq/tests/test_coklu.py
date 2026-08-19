"""N-kanal uzlastirma. Karar tablosunun ALTI satiri da burada."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coklu import uzlastir


def _paket(*metinler):
    return {"lines": [{"raw_text": m} for m in metinler]}


def test_uc_kanal_birebir_ayni_yuksek_guven():
    sonuc = uzlastir({"nash": _paket("AUDIE MURPHY"),
                      "lebron": _paket("AUDIE MURPHY"),
                      "jordan": _paket("AUDIE MURPHY")})
    assert len(sonuc) == 1
    assert sonuc[0]["durum"] == "GECTI"
    assert sonuc[0]["guven"] == "yuksek"


def test_iki_kanal_ayni_ucuncu_yok_orta_guven():
    sonuc = uzlastir({"nash": _paket("AUDIE MURPHY"),
                      "lebron": _paket("AUDIE MURPHY")})
    assert sonuc[0]["durum"] == "GECTI"
    assert sonuc[0]["guven"] == "orta"


def test_iki_ayni_ucuncu_farkli_muhalif_SAKLANIR():
    sonuc = uzlastir({"nash": _paket("AUDIE MURPHY"),
                      "lebron": _paket("AUDIE MURPHY"),
                      "jordan": _paket("AUDIE MURPHYY")})
    kabul = [s for s in sonuc if s["metin"] == "AUDIE MURPHY"][0]
    assert kabul["guven"] == "orta"
    assert kabul["muhalif"] == {"jordan": "AUDIE MURPHYY"}


def test_yalniz_diakritikte_ayrisma_kontrole_gider():
    """UMIT vs UMIT(noktali) — fuzzy yakin ama biri YANLIS. Ayni sayilmaz."""
    sonuc = uzlastir({"nash": _paket("ÜMİT YESİN"),
                      "lebron": _paket("ÜMIT YESIN")})
    assert sonuc[0]["durum"] == "KONTROL_BEKLIYOR"
    assert sonuc[0]["guven"] == "dusuk"


def test_metinde_ayrisma_kontrole_gider():
    sonuc = uzlastir({"nash": _paket("AUDIE MURPHY"),
                      "lebron": _paket("SCOTT BRADY")})
    assert all(s["durum"] == "KONTROL_BEKLIYOR" for s in sonuc)


def test_tek_kanal_dusuk_guvenle_TUTULUR():
    sonuc = uzlastir({"nash": _paket("AUDIE MURPHY")})
    assert sonuc[0]["durum"] == "GECTI"
    assert sonuc[0]["guven"] == "dusuk"


def test_hicbir_satir_SILINMEZ():
    """Her kanaldaki her benzersiz metin ciktida bulunmali."""
    sonuc = uzlastir({"nash": _paket("A ISMI", "B ISMI"),
                      "lebron": _paket("B ISMI", "C ISMI")})
    metinler = {s["metin"] for s in sonuc}
    assert metinler == {"A ISMI", "B ISMI", "C ISMI"}


def test_nash_yoksa_cozumsuz():
    """Nash zorunlu: bbox yoksa kontrol kuyrugu kurulamaz."""
    sonuc = uzlastir({"lebron": _paket("AUDIE MURPHY")})
    assert sonuc[0]["durum"] == "COZUMSUZ"
