from olcum.jenerik_kabul import hizala, olc, taban


def test_turkce_ve_bosluk_taban_eslesmesinde_tolere_edilir():
    assert taban("ÜMİTYESİN", compact=True) == taban("ÜMIT YESIN", compact=True)


def test_siraya_duyarli_hizalama_fazla_satiri_precisionda_cezalandirir():
    rapor = olc(["EROL GÜNAYDIN", "GÜL GÖLGE", "ÜMİT YESİN"],
                ["EROL GUNAYDIN", "SAMSUN ORP", "GÜLGÖLGE", "ÜMIT YESIN"])
    assert rapor["matched_lines"] == 3
    assert rapor["recall"] == 1.0
    assert rapor["precision"] == 0.75
    assert rapor["extra"] == ["SAMSUN ORP"]


def test_tekrarlanan_satirlar_bire_bir_eslesir():
    eslesme = hizala(["YAPIM", "YAPIM"], ["YAPIM"])
    assert len(eslesme) == 1
