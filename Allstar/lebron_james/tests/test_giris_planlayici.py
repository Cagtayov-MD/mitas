import json

import cv2
import numpy as np

import derleyici
from giris_planlayici import master_uret, planla


H, W = 40, 60


def _im(n):
    return np.full((H, W, 3), n, dtype=np.uint8)


def _a(text="", conf=0.99, bbox=(5, 10, 50, 25), kutu_n=1):
    satirlar = [] if not text else [
        {"text": text, "confidence": conf, "bbox": list(bbox)}]
    return {"kutu_n": kutu_n, "satirlar": satirlar, "width": W, "height": H}


def _coklu(*texts, conf=0.99):
    return {"kutu_n": len(texts), "satirlar": [
        {"text": text, "confidence": conf, "bbox": [5, 3 + i * 4, 55, 6 + i * 4]}
        for i, text in enumerate(texts)
    ], "width": W, "height": H}


def _paths(n):
    return [f"/ham/g_{i + 1:04d}.png" for i in range(n)]


def test_ayni_statik_kart_tek_tam_kare_olur():
    ims = [_im(10), _im(20), _im(30)]
    analiz = [_a("EROL GUNAYDIN", 0.70), _a("EROL GUNAYDIN", 0.99),
              _a("EROL GUNAYDIN", 0.80)]
    kanvas, m = master_uret("x", ims, _paths(3), analiz, 1000)

    assert m["text_only"] is True
    assert m["giris_plan"]["surum"] == "giris-text-only/v1"
    assert m["giris_plan"]["grup"] == 1
    assert m["giris_plan"]["secili_kare"] == 1
    assert m["giris_plan"]["ilk_yazi_kare"] == 1
    assert m["giris_plan"]["bitis_kare"] == 3
    assert m["giris_plan"]["son_secili_kare"] == 2
    assert kanvas.shape == (H, W, 3)
    assert int(kanvas[0, 0, 0]) == 20


def test_farkli_kartlar_zaman_sirasiyla_korunur():
    ims = [_im(10), _im(11), _im(20), _im(21)]
    analiz = [_a("EROL GUNAYDIN"), _a("EROL GUNAYDIN"),
              _a("UMIT YESIN"), _a("UMIT YESIN")]
    kanvas, m = master_uret("x", ims, _paths(4), analiz, 1000)

    assert m["segment"] == 2
    assert m["giris_plan"]["secili_kare_nolari"] == [1, 3]
    assert int(kanvas[0, 0, 0]) == 10
    assert int(kanvas[H, 0, 0]) == 20


def test_ayni_kart_ascii_turkce_bosluk_ve_eksik_harfle_bolunmez():
    ims = [_im(10), _im(20), _im(30), _im(40)]
    analiz = [_a("PARMAK DAMGASI", 0.80), _a("ARMAK DAMGASI", 0.75),
              _a("PARMAK DAMGASI", 0.99), _a("PARMAK DAMGASI", 0.90)]
    plan = planla(ims, _paths(4), analiz)

    assert plan["grup"] == 1
    assert plan["secili_kare"] == 1

    analiz = [_a("GÜL GÖLGE", 0.80), _a("GULGOLGE", 0.99)]
    plan = planla(ims[:2], _paths(2), analiz)
    assert plan["grup"] == 1
    assert plan["secili_kare"] == 1


def test_benzer_ama_farkli_kartlar_birlesmez():
    ims = [_im(10), _im(11), _im(20), _im(21)]
    analiz = [_a("BIRINCI KART"), _a("BIRINCI KART"),
              _a("IKINCI KART"), _a("IKINCI KART")]
    plan = planla(ims, _paths(4), analiz)

    assert plan["grup"] == 2
    assert plan["secili_kare"] == 2


def test_dissolve_eksik_ocr_ayni_kartta_tek_temsilci_olur():
    ims = [_im(10), _im(20), _im(21), _im(22)]
    analiz = [_a("MAHM AYTA", 0.80), _a("MAHMUT AYTAÇ ARMAN", 0.90),
              _a("MAHMUT AYTAÇ ARMAN", 0.99), _a("MAHMUT AYTAÇ ARMAN", 0.90)]
    plan = planla(ims, _paths(4), analiz)

    assert plan["grup"] == 1
    assert plan["secili_kare"] == 1


def test_hareketli_fonda_iki_saglam_uc_aradaki_ocr_gurultusunu_kopruler():
    ims = [_im(10), _im(11), _im(20), _im(21), _im(30), _im(31)]
    analiz = [_a("TAMER COKSAL"), _a("TAMER COKSAL"),
              _a("EAPINAL SERNSKSAL"), _a("USPIMAL DERNNOESAL"),
              _a("TAMER COKSAL"), _a("TAMER COKSAL")]
    plan = planla(ims, _paths(6), analiz)

    assert plan["grup"] == 1
    assert plan["secili_kare"] == 1


def test_satir_baslariyla_okunan_fade_tam_karttan_ayrilmaz():
    ims = [_im(10), _im(20), _im(21), _im(22)]
    analiz = [
        _coklu("Meh", "UGU", "Osm", "YAS"),
        _coklu("Mehmet", "UGUR BALCI", "Osman", "YASAR URASLI"),
        _coklu("Mehmet", "UGUR BALCI", "Osman", "YASAR URASLI"),
        _coklu("Mehmet", "UGUR BALCI", "Osman", "YASAR URASLI"),
    ]
    plan = planla(ims, _paths(4), analiz)

    assert plan["grup"] == 1
    assert plan["secili_kare"] == 1


def test_rec_gurultusu_arkasindaki_tek_devam_karesi_asil_karta_baglanir():
    ims = [_im(i) for i in range(8)]
    analiz = [_a("eser YILDIAIM ONAL"), _a("eser YILDIAIM ONAL"),
              _a("eser YILDIAIM ONAL"), _a(kutu_n=0),
              _a("", kutu_n=1), _a("THUOLCLILICE"),
              _a("BILDIAIM ONAL"), _a(kutu_n=0)]
    plan = planla(ims, _paths(8), analiz)

    assert plan["grup"] == 1
    assert plan["secili_kare"] == 1


def test_yazisiz_ve_tek_kare_kisa_sahte_ocr_mastera_girmez():
    ims = [_im(1), _im(2), _im(3)]
    analiz = [_a(kutu_n=0), _a("NO", bbox=(20, 5, 58, 35)), _a(kutu_n=0)]
    kanvas, m = master_uret("x", ims, _paths(3), analiz, 1000)

    assert kanvas is None
    assert m["durum"] == "kare_yok"


def test_kisa_yazi_iki_kare_suruyorsa_korunur():
    ims = [_im(1), _im(2)]
    analiz = [_a("IT"), _a("IT")]
    plan = planla(ims, _paths(2), analiz)

    assert plan["grup"] == 1
    assert plan["secili_kare"] == 1


def test_alt_bant_cumlesi_altyazi_olarak_elenir():
    ims = [_im(1), _im(2)]
    bbox = (2, 28, 58, 39)
    analiz = [_a("Bugun eve biraz gec gelecegim.", bbox=bbox),
              _a("Bugun eve biraz gec gelecegim.", bbox=bbox)]
    plan = planla(ims, _paths(2), analiz)

    assert plan["altyazi_elenen"] == 2
    assert plan["secili_kare"] == 0


def test_layout_her_secili_kareyi_tam_satira_baglar():
    ims = [_im(10), _im(11), _im(20), _im(21)]
    analiz = [_a("BIRINCI KART"), _a("BIRINCI KART"),
              _a("IKINCI KART"), _a("IKINCI KART")]
    _, m = master_uret("x", ims, _paths(4), analiz, 1000)

    assert [(r["master_y0"], r["master_y1"], r["source_y0"], r["source_y1"])
            for r in m["layout_map"]] == [(0, 40, 0, 40), (40, 80, 0, 40)]


def test_boy_asimi_kotu_master_yerine_gorunur_ariza_verir():
    ims = [_im(10), _im(11), _im(20), _im(21)]
    analiz = [_a("BIRINCI KART"), _a("BIRINCI KART"),
              _a("IKINCI KART"), _a("IKINCI KART")]
    kanvas, m = master_uret("x", ims, _paths(4), analiz, H)

    assert kanvas is None
    assert m["durum"] == "boy_asimi"
    assert m["boy"] == 2 * H


def test_derleyici_ardisik_havuzu_giris_motoruna_yonlendirir(tmp_path, monkeypatch):
    havuz = tmp_path / "giris" / "kareler"
    havuz.mkdir(parents=True)
    cv2.imwrite(str(havuz / "g_0001.png"), _im(10))
    cv2.imwrite(str(havuz / "g_0002.png"), _im(20))
    (havuz / "_sinif.json").write_text(json.dumps({
        "surum": 1, "mod": "ardisik_aralik", "ilk_kare": 1, "son_kare": 2,
    }), encoding="utf-8")
    monkeypatch.setattr(derleyici, "paddle_satir_kaniti",
                        lambda _im: _a("EROL GUNAYDIN"))

    kanvas, m = derleyici.derle("x", str(havuz))

    assert kanvas is not None
    assert m["mode"] == "lebron_giris_text_only"
    assert m["girdi_modu"] == "ardisik_aralik"
    assert m["text_only"] is True
    assert m["giris_plan"]["surum"] == "giris-text-only/v1"
