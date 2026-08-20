from pathlib import Path

import hibrit


def _analiz(*, score=0.97, text="YONETMEN AHMET", boxes=True):
    box = [0.2, 0.2, 0.8, 0.4]
    return {"boxes": [box] if boxes else [],
            "lines": ([{"text": text, "score": score, "box": box}]
                      if text is not None else [])}


def test_paddle_guvenilir_satiri_bbox_ile_kabul_eder_fallback_acmaz():
    yollar = [Path("a.png")]
    satirlar, kanit, fallback, grounding = hibrit.paddle_oku(
        yollar, {"a.png": _analiz()}, {})
    assert [x["text"] for x in satirlar] == ["YONETMEN AHMET"]
    assert fallback == []
    assert grounding["a.png"][0]["engine"] == "paddle"
    assert grounding["a.png"][0]["boxes_999"] == [[199.8, 199.8, 799.2, 399.6]]
    assert kanit["paddle_skor_medyan"] == 0.97


def test_scroll_satirlari_ilk_kare_dolu_olsa_da_akis_sirasinda_cikar():
    yollar = [Path(f"{i}.png") for i in range(1, 7)]
    analizler = {}
    for no, yol in enumerate(yollar):
        once_y = .10 - no * .08
        sonra_y = .70 - no * .08
        satirlar = []
        kutular = []
        for text, y in (("ONCEKI SATIR", once_y), ("SONRAKI SATIR", sonra_y)):
            box = [.2, y, .8, y + .06]
            if box[1] < 0 or box[3] > 1:
                continue
            kutular.append(box)
            satirlar.append({"text": text, "score": .98, "box": box})
        analizler[yol.name] = {"boxes": kutular, "lines": satirlar}
    satirlar, _, _, _ = hibrit.paddle_oku(
        yollar, analizler,
        {"bolum": "cikis", "paddle_iz_max_bosluk": 2,
         "paddle_uzlasma_penceresi": 2})
    assert [x["text"] for x in satirlar] == [
        "ONCEKI SATIR", "SONRAKI SATIR"]


def test_cikistaki_statik_kart_gec_algilanan_rolu_y_sirasina_alir():
    satirlar = [
        {"sayfa_sira": 10, "satir_sira": 7000, "text": "AD",
         "_akis_zamani": 10.0, "_akis_hareketli": False,
         "_akis_x": .5, "_akis_y": .7},
        {"sayfa_sira": 11, "satir_sira": 3000, "text": "ROL",
         "_akis_zamani": 11.0, "_akis_hareketli": False,
         "_akis_x": .5, "_akis_y": .3},
    ]
    sonuc = hibrit._zamansal_sirala(satirlar, kart_toleransi=2)
    assert [x["text"] for x in sonuc] == ["ROL", "AD"]


def test_tek_ad_tekrari_silinmez_ama_ardisik_kart_tekrari_silinir():
    def row(text, sayfa, score=.98):
        return {"kaynak": f"{sayfa}.png", "sayfa_sira": sayfa,
                "satir_sira": 0, "text": text, "score": score,
                "support": 4, "motor": "paddle"}
    satirlar = [
        row("YÖNETMEN", 1, .99),
        row("DOĞAN ÜMİT KARACA", 2, .99),
        row("YAPIMCI", 3, .99),
        row("MEHMET CANPOLAT", 4, .99),
        row("SADİ CANPOLAT", 5, .98),
        row("Yönetmen", 6, .98),
        row("DOĞAN OMİT KARACA", 7, .97),
        row("Yapimei", 8, .92),
        row("MEHMET CANPOLAT", 9, .99),
        row("SADI CANPOLAT", 10, .99),
        row("YÖNETMEN", 20, .99),
    ]
    sonuc, tani = hibrit.tekrar_bloklarini_ayikla(satirlar)
    assert [x["text"] for x in sonuc[:5]] == [
        "YÖNETMEN", "DOĞAN ÜMİT KARACA", "YAPIMCI",
        "MEHMET CANPOLAT", "SADİ CANPOLAT"]
    assert sonuc[-1]["text"] == "YÖNETMEN"
    assert tani["removed_n"] == 5
    assert tani["blocks"][0]["kept"] == "earlier"


def test_tekrar_blokta_belirgin_daha_iyi_olan_sonraki_kalir():
    def row(text, sayfa, score):
        return {"kaynak": f"{sayfa}.png", "sayfa_sira": sayfa,
                "satir_sira": 0, "text": text, "score": score}
    satirlar = [
        row("YONETMEN", 1, .75), row("ALI VELI", 2, .76),
        row("YAPIMCI", 3, .77),
        row("YÖNETMEN", 10, .99), row("ALİ VELİ", 11, .99),
        row("YAPIMCI", 12, .99),
    ]
    sonuc, tani = hibrit.tekrar_bloklarini_ayikla(satirlar)
    assert [x["sayfa_sira"] for x in sonuc] == [10, 11, 12]
    assert tani["blocks"][0]["kept"] == "later"


def test_guclu_izin_yanindaki_tek_kare_ayni_baslik_tekrari_silinir():
    satirlar = [
        {"kaynak": "c_0050.png", "sayfa_sira": 1, "satir_sira": 0,
         "text": "DOSYASI", "score": .92, "support": 1},
        {"kaynak": "c_0052.png", "sayfa_sira": 2, "satir_sira": 0,
         "text": "DOSYASI", "score": .98, "support": 5},
        {"kaynak": "c_0090.png", "sayfa_sira": 3, "satir_sira": 0,
         "text": "DOSYASI", "score": .99, "support": 5},
    ]
    sonuc, tani = hibrit.tekrar_bloklarini_ayikla(satirlar)
    assert [x["kaynak"] for x in sonuc] == ["c_0052.png", "c_0090.png"]
    assert tani["near_removed_n"] == 1


def test_dusuk_guvenli_paddle_satiri_korunur_ve_deepseek_fallback_acilir():
    yollar = [Path("a.png")]
    satirlar, kanit, fallback, _ = hibrit.paddle_oku(
        yollar, {"a.png": _analiz(score=0.82)},
        {"paddle_kabul_esigi": 0.7, "deepseek_fallback_esigi": 0.88})
    assert [x["text"] for x in satirlar] == ["YONETMEN AHMET"]
    assert fallback == yollar
    assert kanit["deepseek_fallback_nedenleri"] == {"a.png": "dusuk_guven"}


def test_kutu_var_metin_yok_deepseek_fallback_nedenidir():
    yollar = [Path("a.png")]
    _, _, fallback, _ = hibrit.paddle_oku(
        yollar, {"a.png": _analiz(text=None)}, {})
    assert fallback == yollar


def test_tam_kare_segmentasyon_lekesi_fallback_acmaz():
    yollar = [Path("a.png")]
    analiz = {"a.png": {"boxes": [[0.0, 0.0, 1.0, 1.0]],
                            "lines": [{"text": "", "score": 0.0,
                                       "box": [0.0, 0.0, 1.0, 1.0]}]}}
    _, _, fallback, _ = hibrit.paddle_oku(yollar, analiz, {})
    assert fallback == []


def test_yalniz_yapisal_cop_okunursa_fallback_acmaz():
    yollar = [Path("a.png")]
    _, kanit, fallback, _ = hibrit.paddle_oku(
        yollar, {"a.png": _analiz(text="M")}, {})
    assert fallback == []
    assert kanit["elenme_sebepleri"]["cok_kisa"] == 1


def test_altta_duran_kredi_altyazi_sanilip_elenmez():
    yollar = [Path("a.png")]
    kredi = [0.2, 0.2, 0.8, 0.4]
    altyazi = [0.2, 0.85, 0.8, 0.95]
    analiz = {"a.png": {"boxes": [kredi, altyazi], "lines": [
        {"text": "YONETMEN AHMET", "score": 0.99, "box": kredi},
        {"text": "buraya gel", "score": 0.99, "box": altyazi},
    ]}}
    satirlar, kanit, _, _ = hibrit.paddle_oku(yollar, analiz, {})
    assert [x["text"] for x in satirlar] == ["YONETMEN AHMET", "buraya gel"]
    assert kanit["elenme_sebepleri"].get("altyazi", 0) == 0


def test_bolum_ozel_altyazi_y_giris_icin_kapatilabilir():
    # Çiçek Taksi 2026-08-19: dizi açılış jeneriğinde her oyuncu adı tek
    # satır alt banttadır — varsayılan kural satırı eler (EROL GÜNAYDIN,
    # skor 0.97, 'sebep': 'altyazi'). ham_tavan deseni gibi bölme sözlüğü.
    yollar = [Path("a.png")]
    alt_bant = [0.2, 0.85, 0.8, 0.95]
    analiz = {"a.png": {"boxes": [alt_bant], "lines": [
        {"text": "EROL GUNAYDIN", "score": 0.97, "box": alt_bant},
    ]}}
    satirlar, _, _, _ = hibrit.paddle_oku(
        yollar, analiz,
        {"altyazi_y": {"giris": 2.0, "cikis": 0.80}, "bolum": "giris"})
    assert [x["text"] for x in satirlar] == ["EROL GUNAYDIN"]


def test_bolum_ozel_altyazi_y_sozlukte_bolum_yoksa_eleme_kalir():
    yollar = [Path("a.png")]
    alt_bant = [0.2, 0.85, 0.8, 0.95]
    analiz = {"a.png": {"boxes": [alt_bant], "lines": [
        {"text": "buraya gel", "score": 0.99, "box": alt_bant},
    ]}}
    _, kanit, _, _ = hibrit.paddle_oku(
        yollar, analiz,
        {"altyazi_y": {"giris": 2.0}, "bolum": "cikis"})
    assert kanit["elenme_sebepleri"].get("altyazi", 0) == 1


def test_karelerin_yuzde_seksenindeki_kucuk_kose_logosu_cikmaz():
    yollar = [Path(f"{i:03d}.png") for i in range(10)]
    logo = [0.01, 0.01, 0.12, 0.08]
    analizler = {p.name: {"boxes": [logo], "lines": [
        {"text": "KANAL", "score": 0.99, "box": logo}]}
        for p in yollar}
    satirlar, kanit, fallback, _ = hibrit.paddle_oku(yollar, analizler, {})
    assert satirlar == [] and fallback == []
    assert kanit["elenme_sebepleri"]["kalici_logo"] == 10


def test_fallback_tavani_bolume_gore_zorlanir():
    yollar = [Path(f"{i:03d}.png") for i in range(8)]
    analizler = {p.name: _analiz(score=0.5) for p in yollar}
    _, kanit, fallback, _ = hibrit.paddle_oku(
        yollar, analizler,
        {"paddle_kabul_esigi": 0.4, "deepseek_fallback_esigi": 0.88,
         "deepseek_fallback_tavan": {"giris": 3, "cikis": 5}, "bolum": "giris",
         "paddle_uzlasma_penceresi": 0,
         "paddle_film_kabul_min_satir": 99})
    assert len(fallback) == 3
    assert kanit["deepseek_fallback_aday_n"] == 8


def test_filmde_yeterli_paddle_satiri_varsa_kare_dusuk_deepseek_acmaz():
    yollar = [Path(f"{i:03d}.png") for i in range(8)]
    analizler = {p.name: _analiz(
        score=0.82, text=f"YONETMEN KREDI SATIRI {i}")
        for i, p in enumerate(yollar)}
    satirlar, kanit, fallback, _ = hibrit.paddle_oku(
        yollar, analizler,
        {"paddle_uzlasma_penceresi": 0,
         "paddle_film_kabul_min_satir": 8})
    assert len(satirlar) == 8 and fallback == []
    assert kanit["paddle_film_kapisi_gecti"] is True
    assert kanit["deepseek_fallback_film_kapisi_kapatti_n"] == 8


def test_config_fallbacki_kapattiginda_zayif_paddle_deepseek_acmaz():
    yollar = [Path("a.png")]
    _, kanit, fallback, _ = hibrit.paddle_oku(
        yollar, {"a.png": _analiz(score=0.5)},
        {"paddle_kabul_esigi": 0.4,
         "deepseek_fallback_enabled": False,
         "paddle_film_kabul_min_satir": 99})
    assert fallback == []
    assert kanit["deepseek_fallback_enabled"] is False
    assert kanit["deepseek_fallback_config_kapatti_n"] == 1


def test_script_fallback_yalniz_arap_alfabeli_satiri_kabul_eder():
    satirlar = [
        {"kaynak": "a.png", "text": "محسن عبد الوهاب", "motor": "paddle"},
        {"kaynak": "a.png", "text": "YONETMEN AHMET", "motor": "paddle"},
    ]
    grounding = {"a.png": [
        {"label": "محسن عبد الوهاب", "boxes_999": [[1, 2, 3, 4]],
         "engine": "paddle"},
        {"label": "YONETMEN AHMET", "boxes_999": [[5, 6, 7, 8]],
         "engine": "paddle"},
    ]}
    secilen, kanitlar, tani = hibrit.script_satirlarini_sec(
        satirlar, grounding)
    assert [x["text"] for x in secilen] == ["محسن عبد الوهاب"]
    assert secilen[0]["motor"] == "paddle_arabic"
    assert kanitlar["a.png"][0]["engine"] == "paddle_arabic"
    assert tani["kabul_satir_n"] == 1


def test_script_fallback_eslav_yalniz_kiril_satirini_kabul_eder():
    satirlar = [
        {"kaynak": "a.png", "text": "РЕЖИССЕР ИВАН ПЕТРОВ",
         "motor": "paddle", "box": [0.1, 0.1, 0.9, 0.2]},
        {"kaynak": "a.png", "text": "DIRECTOR IVAN PETROV",
         "motor": "paddle", "box": [0.1, 0.3, 0.9, 0.4]},
    ]
    grounding = {"a.png": [
        {"label": "РЕЖИССЕР ИВАН ПЕТРОВ", "boxes_999": [[1, 2, 3, 4]],
         "engine": "paddle"},
        {"label": "DIRECTOR IVAN PETROV", "boxes_999": [[5, 6, 7, 8]],
         "engine": "paddle"},
    ]}
    secilen, kanitlar, tani = hibrit.script_satirlarini_sec(
        satirlar, grounding, script="eslav")
    assert [x["text"] for x in secilen] == ["РЕЖИССЕР ИВАН ПЕТРОВ"]
    assert secilen[0]["motor"] == "paddle_eslav"
    assert kanitlar["a.png"][0]["engine"] == "paddle_eslav"
    assert tani["kabul_satir_n"] == 1


def test_script_takeover_ayni_bbox_copunu_atip_ayri_cift_dilli_satiri_korur():
    birincil = [
        {"kaynak": "a.png", "sayfa_sira": 1, "satir_sira": 0,
         "text": "PEKHCCEP", "score": 0.96, "support": 3,
         "box": [0.1, 0.1, 0.9, 0.2]},
        {"kaynak": "a.png", "sayfa_sira": 1, "satir_sira": 1,
         "text": "DIRECTOR IVAN PETROV", "score": 0.97, "support": 2,
         "box": [0.1, 0.4, 0.9, 0.5]},
        {"kaynak": "b.png", "sayfa_sira": 2, "satir_sira": 0,
         "text": "TEK KARE COP", "score": 0.99, "support": 1,
         "box": [0.1, 0.4, 0.9, 0.5]},
    ]
    script = [{"kaynak": "a.png", "sayfa_sira": 1, "satir_sira": 0,
               "text": "РЕЖИССЕР", "score": 0.88, "support": 3,
               "box": [0.1, 0.1, 0.9, 0.2], "motor": "paddle_eslav"}]
    birincil_kanit = {"a.png": [
        {"label": "PEKHCCEP", "boxes_999": [[100, 100, 900, 200]]},
        {"label": "DIRECTOR IVAN PETROV", "boxes_999": [[100, 400, 900, 500]]},
    ], "b.png": [{"label": "TEK KARE COP", "boxes_999": [[1, 2, 3, 4]]}]}
    script_kanit = {"a.png": [
        {"label": "РЕЖИССЕР", "boxes_999": [[100, 100, 900, 200]]}]}
    sonuc, kanit, tani = hibrit.script_birlestir(
        birincil, birincil_kanit, script, script_kanit,
        script_ham_satirlari=[
            *script,
            {"kaynak": "a.png", "sayfa_sira": 1, "satir_sira": 1,
             "text": "DIRECTOR IVAN PETROV", "score": 0.94,
             "support": 2, "box": [0.1, 0.4, 0.9, 0.5]},
        ])
    assert [x["text"] for x in sonuc] == [
        "РЕЖИССЕР", "DIRECTOR IVAN PETROV"]
    assert sonuc[1]["motor"] == "paddle_latin_preserved"
    assert tani["latin_korunan_n"] == 1
    assert tani["latin_elenen_n"] == 2
    assert {x["label"] for x in kanit["a.png"]} == {
        "РЕЖИССЕР", "DIRECTOR IVAN PETROV"}


def test_script_takeover_ikinci_taniyici_dogrulamayan_latin_homoglifi_atilir():
    birincil = [{
        "kaynak": "a.png", "sayfa_sira": 1, "satir_sira": 0,
        "text": "KAPEH-TERUPKGH", "score": 0.98, "support": 4,
        "box": [0.1, 0.1, 0.9, 0.2],
    }]
    script = [{
        "kaynak": "a.png", "sayfa_sira": 1, "satir_sira": 0,
        "text": "КАРЕН ТЕРУКЯН", "score": 0.92, "support": 4,
        "box": [0.1, 0.1, 0.9, 0.2], "motor": "paddle_eslav",
    }]
    sonuc, _kanit, tani = hibrit.script_birlestir(
        birincil, {}, script, {}, script_ham_satirlari=script)
    assert [x["text"] for x in sonuc] == ["КАРЕН ТЕРУКЯН"]
    assert tani["latin_korunan_n"] == 0
    assert tani["elenen"][0]["capraz_dogrulama"] is False


def test_arabic_takeover_ayri_kutudaki_gercek_latin_krediyi_korur():
    birincil = [{
        "kaynak": "a.png", "sayfa_sira": 1, "satir_sira": 0,
        "text": "CPR", "score": 0.97, "support": 30,
        "box": [0.1, 0.4, 0.2, 0.5],
    }]
    script = [{
        "kaynak": "a.png", "sayfa_sira": 1, "satir_sira": 1,
        "text": "بازيكران", "score": 0.95, "support": 10,
        "box": [0.5, 0.4, 0.7, 0.5], "motor": "paddle_arabic",
    }]
    sonuc, _kanit, tani = hibrit.script_birlestir(
        birincil, {}, script, {}, script_ham_satirlari=script,
        target_script="arabic")
    assert [x["text"] for x in sonuc] == ["CPR", "بازيكران"]
    assert tani["latin_korunan_n"] == 1
    assert tani["latin_corroboration_required"] is False


def test_temporal_uzlasma_crossfade_bilesigini_atip_temiz_satiri_korur():
    yollar = [Path(f"{i:03d}.png") for i in range(4)]
    analizler = {
        "000.png": _analiz(text="MUZIK"),
        "001.png": _analiz(text="MUZIK"),
        "002.png": _analiz(text="GORUNIMUZIK"),
        "003.png": _analiz(text="GORUNTU YONETMENI"),
    }
    satirlar, kanit, _, _ = hibrit.paddle_oku(yollar, analizler, {})
    assert "MUZIK" in [x["text"] for x in satirlar]
    assert "GORUNIMUZIK" not in [x["text"] for x in satirlar]
    assert kanit["elenme_sebepleri"]["gecis_bilesik"] == 1


def test_kararli_kartin_tek_karelik_eksik_parcasi_elenir():
    yollar = [Path(f"{i:03d}.png") for i in range(3)]
    analizler = {
        "000.png": _analiz(text="TAK"),
        "001.png": _analiz(text="TAKSI"),
        "002.png": _analiz(text="TAKSI"),
    }
    satirlar, kanit, _, _ = hibrit.paddle_oku(yollar, analizler, {})
    assert [x["text"] for x in satirlar] == ["TAKSI"]
    assert kanit["elenme_sebepleri"]["gecis_parcasi"] == 1


def test_iki_harfli_ama_cok_kareli_gercek_kredi_korunur():
    yollar = [Path("000.png"), Path("001.png"), Path("002.png")]
    analizler = {p.name: _analiz(text="VE") for p in yollar}
    satirlar, _, _, _ = hibrit.paddle_oku(yollar, analizler, {})
    assert [x["text"] for x in satirlar] == ["VE"]


def test_uzaktaki_benzer_satir_tek_karelik_krediyi_elemez():
    yollar = [Path(f"{i:03d}.png") for i in range(20)]
    analizler = {p.name: {"boxes": [], "lines": []} for p in yollar}
    analizler["000.png"] = _analiz(text="YAPIMCI AYSE")
    analizler["001.png"] = _analiz(text="YAPIMCI AYSE")
    analizler["019.png"] = _analiz(text="YAPIMCI AYSEL")
    satirlar, _, _, _ = hibrit.paddle_oku(yollar, analizler, {})
    assert [x["text"] for x in satirlar] == ["YAPIMCI AYSE", "YAPIMCI AYSEL"]


def test_yogun_kayan_jenerikte_tek_karelik_blur_varyanti_elenir():
    yollar = [Path(f"{i:03d}.png") for i in range(3)]
    analizler = {}
    for i, p in enumerate(yollar):
        lines = []
        boxes = []
        for j in range(8):
            box = [0.1, 0.05 + j * 0.08, 0.9, 0.1 + j * 0.08]
            boxes.append(box)
            lines.append({"text": f"KREDI SATIRI {j}", "score": 0.99,
                          "box": box})
        if i == 1:
            box = [0.1, 0.72, 0.9, 0.77]
            boxes.append(box)
            lines.append({"text": "MERI RURAMAZ", "score": 0.99, "box": box})
        analizler[p.name] = {"boxes": boxes, "lines": lines}
    satirlar, kanit, _, _ = hibrit.paddle_oku(yollar, analizler, {})
    assert "MERI RURAMAZ" not in [x["text"] for x in satirlar]
    assert kanit["elenme_sebepleri"]["yogun_akista_tek_kare"] == 1


def test_benzer_metin_farkli_kutudaysa_ayri_kredi_kalir():
    yollar = [Path("000.png"), Path("001.png")]
    ust = [0.1, 0.1, 0.9, 0.2]
    alt = [0.1, 0.5, 0.9, 0.6]
    analizler = {p.name: {"boxes": [ust, alt], "lines": [
        {"text": "AHMET YILMAZ", "score": 0.99, "box": ust},
        {"text": "AHMET YILDIZ", "score": 0.99, "box": alt},
    ]} for p in yollar}
    satirlar, _, _, _ = hibrit.paddle_oku(yollar, analizler, {})
    assert [x["text"] for x in satirlar] == ["AHMET YILMAZ", "AHMET YILDIZ"]


def test_komsuda_ayni_kutu_kararliysa_deepseek_fallback_acilmaz():
    yollar = [Path(f"{i:03d}.png") for i in range(3)]
    analizler = {
        "000.png": _analiz(text="YAPIMCI AYSE"),
        "001.png": _analiz(text=None),
        "002.png": _analiz(text="YAPIMCI AYSE"),
    }
    _, kanit, fallback, _ = hibrit.paddle_oku(
        yollar, analizler, {}, fallback_yollari=[yollar[1]])
    assert fallback == []
    assert kanit["deepseek_fallback_temporal_cozuldu_n"] == 1


def test_eslesmeyen_tek_kare_kutusu_deepseek_fallback_olarak_kalir():
    yollar = [Path(f"{i:03d}.png") for i in range(3)]
    analizler = {
        "000.png": _analiz(text="YAPIMCI AYSE"),
        "001.png": {"boxes": [[0.05, 0.7, 0.3, 0.8]], "lines": []},
        "002.png": _analiz(text="YAPIMCI AYSE"),
    }
    _, _, fallback, _ = hibrit.paddle_oku(
        yollar, analizler, {}, fallback_yollari=[yollar[1]])
    assert fallback == [yollar[1]]


def test_birlestirme_paddle_eslesmesini_korur_yalniz_yeni_deepseek_satiri_ekler():
    paddle = [{"kaynak": "a.png", "sayfa_sira": 1, "satir_sira": 0,
               "text": "UČUR UZUNOK"}]
    deep = [{"kaynak": "a.png", "sayfa_sira": 1, "satir_sira": 0,
             "text": "UGUR UZUNOK"},
            {"kaynak": "a.png", "sayfa_sira": 1, "satir_sira": 1,
             "text": "YAPIMCI AYSE"}]
    sonuc, kanit = hibrit.birlestir(paddle, deep, [Path("a.png")])
    assert [x["text"] for x in sonuc] == ["UČUR UZUNOK", "YAPIMCI AYSE"]
    assert sonuc[0]["motor"] == "paddle"
    assert sonuc[1]["motor"] == "deepseek_fallback"
    assert kanit["deepseek_yeni_satir_n"] == 1
    assert kanit["deepseek_paddle_eslesme_n"] == 1


def test_deepseek_kisa_parcali_ve_asiri_uzun_copu_birlesime_girmez():
    deep = [
        {"kaynak": "a.png", "text": "in"},
        {"kaynak": "a.png", "text": "A N S A L I M I S"},
        {"kaynak": "a.png", "text": "X" * 181},
        {"kaynak": "a.png", "text": "YAPIMCI AYSE YILMAZ"},
    ]
    sonuc, kanit = hibrit.birlestir([], deep, [Path("a.png")])
    assert [x["text"] for x in sonuc] == ["YAPIMCI AYSE YILMAZ"]
    assert kanit["deepseek_birlesim_elendi_n"] == 3
