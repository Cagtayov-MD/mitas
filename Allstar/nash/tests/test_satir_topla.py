"""Kutu -> satir toplama. Bbox'lar piksel xyxy: [x0, y0, x1, y1]."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from satir_topla import topla


def _satir(no, metin, asset, bbox):
    return {"line_id": f"line-{no:06d}", "order": no, "raw_text": metin,
            "normalized_text": metin.upper(), "source_label": "f.png",
            "evidence": [{"asset_id": asset, "bbox": bbox,
                          "coordinate_space": "pixel_xyxy"}]}


def test_ayni_satirdaki_kutular_birlesir():
    """Aynı asset, dikeyde ortusen iki kutu -> tek satir, soldan saga."""
    gelen = [_satir(0, "MURPHY", "a1", [300, 100, 400, 130]),
             _satir(1, "Audie", "a1", [100, 102, 280, 132])]
    cikan = topla(gelen)
    assert len(cikan) == 1
    assert cikan[0]["raw_text"] == "Audie MURPHY"


def test_birlesik_bbox_bilesenleri_kapsar():
    gelen = [_satir(0, "Audie", "a1", [100, 102, 280, 132]),
             _satir(1, "MURPHY", "a1", [300, 100, 400, 130])]
    kutu = topla(gelen)[0]["evidence"][0]["bbox"]
    assert kutu == [100, 100, 400, 132]


def test_parca_bboxlari_KORUNUR():
    """Kontrol kuyrugu parcaya inebilmeli; bilesenler kaybolmaz."""
    gelen = [_satir(0, "Audie", "a1", [100, 102, 280, 132]),
             _satir(1, "MURPHY", "a1", [300, 100, 400, 130])]
    bilesen = topla(gelen)[0]["bilesenler"]
    assert len(bilesen) == 2
    assert [b["raw_text"] for b in bilesen] == ["Audie", "MURPHY"]


def test_ayri_satirlar_birlesmez():
    """Dikeyde ortusmeyen kutular ayri kalir."""
    gelen = [_satir(0, "Audie MURPHY", "a1", [100, 100, 400, 130]),
             _satir(1, "Scott BRADY", "a1", [100, 200, 400, 230])]
    assert len(topla(gelen)) == 2


def test_farkli_asset_birlesmez():
    """Ayni y'de olsalar bile farkli kareler birlestirilemez."""
    gelen = [_satir(0, "Audie", "a1", [100, 100, 280, 130]),
             _satir(1, "MURPHY", "a2", [300, 100, 400, 130])]
    assert len(topla(gelen)) == 2


def test_bboxsuz_satir_oldugu_gibi_gecer():
    """Koordinati olmayan satir gruplanamaz; ASLA dusurulmez."""
    yalin = {"line_id": "line-000000", "order": 0, "raw_text": "PRESENTS",
             "normalized_text": "PRESENTS", "source_label": "f.png",
             "evidence": []}
    cikan = topla([yalin])
    assert len(cikan) == 1
    assert cikan[0]["raw_text"] == "PRESENTS"
    assert "bilesenler" not in cikan[0]


def test_tek_kutu_bilesen_almaz():
    """Tek basina kalan kutu toplanmis sayilmaz."""
    cikan = topla([_satir(0, "PRESENTS", "a1", [100, 100, 400, 130])])
    assert len(cikan) == 1
    assert "bilesenler" not in cikan[0]


def test_order_yeniden_numaralanir():
    gelen = [_satir(0, "Audie", "a1", [100, 100, 280, 130]),
             _satir(1, "MURPHY", "a1", [300, 100, 400, 130]),
             _satir(2, "Scott BRADY", "a1", [100, 200, 400, 230])]
    cikan = topla(gelen)
    assert [c["order"] for c in cikan] == [0, 1]


def test_paket_satir_birimli_cikar(tmp_path, monkeypatch):
    """build_packet artik kutu degil satir birimi yazmali."""
    import proof

    monkeypatch.setattr(proof, "_identity", lambda: {"tool": "test"})
    monkeypatch.setattr(proof, "_frame_manifest", lambda: {})
    monkeypatch.setattr(proof, "_png_size", lambda p: (1000, 1000))
    monkeypatch.setattr(proof, "_asset", lambda aid, p, w, h, m: {
        "asset_id": aid, "path": str(p), "width": w, "height": h,
        "frame_sequence": 1, "source_time_s": 0.5})
    monkeypatch.setattr(proof, "_sha", lambda p: "0" * 64)

    kare = tmp_path / "f.png"
    kare.write_bytes(b"x")
    grounding = {"f.png": [
        {"label": "Audie", "boxes_999": [[100, 102, 280, 132]], "engine": "t", "score": 1.0},
        {"label": "MURPHY", "boxes_999": [[300, 100, 400, 130]], "engine": "t", "score": 1.0}]}
    paket = proof.build_packet(
        film_id="F", section="cikis", legacy={"durum": "OKUNDU"},
        selected_paths=[kare],
        accepted=[{"text": "Audie", "kaynak": "f.png"},
                  {"text": "MURPHY", "kaynak": "f.png"}],
        rejected=[], grounding=grounding, grounding_failures=[])

    assert len(paket["lines"]) == 1
    assert paket["lines"][0]["raw_text"] == "Audie MURPHY"
    assert len(paket["lines"][0]["bilesenler"]) == 2
