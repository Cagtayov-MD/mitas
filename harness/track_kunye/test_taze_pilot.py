import taze_pilot as tp


def test_xml_kimlik(tmp_path):
    x = tmp_path / "a.xml"
    x.write_text("<r><MEDIAID>1995-0401-1-0000-00-1</MEDIAID><TITLE>MAGIC FLUTE</TITLE></r>",
                 encoding="utf-8")
    k = tp.xml_kimlik(x)
    assert k == {"media_id": "1995-0401-1-0000-00-1", "title": "MAGIC FLUTE"}


def test_skor_tablosu_uc_kolon():
    satir = tp.skor_satiri("test", {"f1": 0.5}, {"f1": 0.6}, {"f1": 0.7})
    assert satir == "test\t0.5\t0.6\t0.7"
