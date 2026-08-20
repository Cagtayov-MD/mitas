import metin_izleri


def _gozlem(kare, text, box, score=.95, crop_dhash=None, frame_luma=80.0):
    fold = "".join(c.lower() for c in text if c.isalnum() or c.isspace())
    return {"kare_sira": kare, "text": text, "fold": fold,
            "box": box, "score": score, "crop_dhash": crop_dhash,
            "frame_luma": frame_luma}


def test_bosluk_ve_turkce_isaret_sapmasi_ayni_ize_girer():
    box = [.1, .75, .9, .9]
    izler, tani = metin_izleri.izleri_kur([
        _gozlem(1, "ÜMİTYESİN", box),
        _gozlem(2, "ÜMIT YESIN", box),
        _gozlem(3, "ÜMİT YESİN", box),
    ])
    assert len(izler) == 1
    assert len(izler[0]["ogeler"]) == 3
    assert tani["iz_eslesme_n"] == 2


def test_ayni_karedeki_benzer_iki_ad_birbirini_yutmaz():
    izler, _ = metin_izleri.izleri_kur([
        _gozlem(1, "AHMET YILMAZ", [.1, .1, .8, .2]),
        _gozlem(1, "AHMET YILDIZ", [.1, .5, .8, .6]),
        _gozlem(2, "AHMET YILMAZ", [.1, .1, .8, .2]),
        _gozlem(2, "AHMET YILDIZ", [.1, .5, .8, .6]),
    ])
    assert len(izler) == 2
    assert sorted(len(x["ogeler"]) for x in izler) == [2, 2]


def test_kayan_satir_tahmin_edilen_hareketle_izlenir():
    izler, _ = metin_izleri.izleri_kur([
        _gozlem(1, "GORUNTU YONETMENI", [.2, .80, .8, .88]),
        _gozlem(2, "GORUNTU YONETMENI", [.2, .67, .8, .75]),
        _gozlem(3, "GORUNTU YONETMENİ", [.2, .54, .8, .62]),
    ])
    assert len(izler) == 1
    assert izler[0]["ilk_sira"] == 1 and izler[0]["son_sira"] == 3


def test_iki_fps_hizli_scroll_ocr_sapmasiyla_uc_ayri_iz_olmaz():
    izler, _ = metin_izleri.izleri_kur([
        _gozlem(1, "JOE NAGGER", [.08, .91, .38, .98]),
        _gozlem(2, "JOE NABBER", [.08, .67, .38, .74]),
        _gozlem(3, "JOE NASSER", [.08, .41, .38, .49]),
    ])
    assert len(izler) == 1
    assert len(izler[0]["ogeler"]) == 3


def test_uzak_zamandaki_ayni_rol_yeni_izdir():
    box = [.2, .7, .8, .8]
    izler, _ = metin_izleri.izleri_kur([
        _gozlem(1, "YONETMEN", box),
        _gozlem(2, "YONETMEN", box),
        _gozlem(40, "YONETMEN", box),
    ], {"paddle_iz_max_bosluk": 12})
    assert len(izler) == 2


def _iz(iz_id, bas, son, text, box, destek=3):
    return {"iz_id": iz_id, "ilk_sira": bas, "son_sira": son,
            "ogeler": [_gozlem(bas + min(i, son - bas), text, box)
                        for i in range(destek)]}


def test_guclu_acilis_dizisinden_sonraki_uzak_sahne_yazisi_kirpilir():
    izler = [
        _iz(i, 5 + i * 6, 8 + i * 6, f"KREDI SATIRI {i}",
            [.1, .75, .9, .90]) for i in range(10)
    ]
    izler.append(_iz(99, 160, 164, "SOKAK TABELASI", [.7, .1, .9, .16]))
    izin, tani = metin_izleri.kredi_penceresi(
        izler, 220, "giris", {"paddle_kredi_son_bosluk": 36})
    assert tani["uygulandi"] is True
    assert 99 not in izin
    assert tani["son"] < 160


def test_kredi_penceresi_suphede_hicbir_izi_silmez():
    izler = [_iz(1, 5, 8, "TEK KART", [.1, .7, .9, .9])]
    izin, tani = metin_izleri.kredi_penceresi(izler, 200, "giris")
    assert izin == {1}
    assert tani["uygulandi"] is False


def test_kucuk_ve_yalitilmis_sahne_tabelasi_baskin_fonttan_ayrilir():
    izler = [
        _iz(i, i * 5, i * 5 + 3, f"OYUNCU {i}", [.1, .76, .9, .90])
        for i in range(1, 10)
    ]
    izler += [
        _iz(20, 30, 34, "YONETMEN", [.25, .64, .75, .74]),
        _iz(21, 35, 38, "SAMSUN ORP", [.78, .54, .96, .59]),
    ]
    izin = {x["iz_id"] for x in izler}
    elenen = metin_izleri.kucuk_sahne_yazisi_izleri(izler, izin)
    assert 21 in elenen
    assert 20 not in elenen


def test_yogun_scroll_onfiltresi_ilgisiz_milyonlarca_cifti_acmaz():
    gozlemler = []
    for kare in range(20):
        for satir in range(60):
            # Her karede farkli içerik: eslesme yok ama ham aktif iz sayisi
            # hızla büyür. Bigram indeksi alakasiz çiftleri SequenceMatcher'a
            # göndermemelidir.
            gozlemler.append(_gozlem(
                kare, f"KREDI {kare:02d} SATIR {satir:02d} Q{kare * 61 + satir:04d}",
                [.1, satir / 70, .9, satir / 70 + .01]))
    _izler, tani = metin_izleri.izleri_kur(gozlemler)
    assert tani["iz_ham_cifti_n"] > 60_000
    assert tani["iz_onfiltre_cifti_n"] < tani["iz_ham_cifti_n"] / 4


def test_scroll_sirasi_ilk_gorunuse_degil_orta_cizgi_gecisine_bakar():
    ustte_baslayan = _iz(
        1, 1, 4, "ONCEKI SATIR", [.2, .10, .8, .18], destek=4)
    altta_baslayan = _iz(
        2, 1, 4, "SONRAKI SATIR", [.2, .50, .8, .58], destek=4)
    for no, oge in enumerate(ustte_baslayan["ogeler"]):
        oge["box"] = [.2, .10 - no * .08, .8, .18 - no * .08]
        oge["kare_sira"] = no + 1
    for no, oge in enumerate(altta_baslayan["ogeler"]):
        oge["box"] = [.2, .70 - no * .08, .8, .78 - no * .08]
        oge["kare_sira"] = no + 1
    a = metin_izleri.iz_sira_bilgisi(ustte_baslayan)
    b = metin_izleri.iz_sira_bilgisi(altta_baslayan)
    assert a["hareketli"] is True and b["hareketli"] is True
    assert a["zaman"] < b["zaman"]


def test_statik_kart_akis_sanilmaz():
    iz = _iz(1, 5, 8, "YONETMEN", [.2, .4, .8, .5], destek=4)
    bilgi = metin_izleri.iz_sira_bilgisi(iz)
    assert bilgi["hareketli"] is False
    assert bilgi["zaman"] == 5


def test_zayif_ve_yakin_kredi_kolonundan_uzak_plaka_elenir():
    izler = [
        _iz(1, 35, 39, "IMAM", [.51, .64, .61, .69], destek=4),
        _iz(2, 36, 40, "IBRAHIM UNEY", [.51, .70, .83, .77], destek=4),
        _iz(3, 38, 39, "06 A 7736", [.11, .82, .22, .89], destek=2),
        _iz(4, 38, 38, "HACER", [.52, .64, .65, .69], destek=1),
    ]
    izin = {x["iz_id"] for x in izler}
    elenen = metin_izleri.zayif_layout_disinda_izler(izler, izin)
    assert 3 in elenen
    assert 4 not in elenen


def test_hareketli_scroll_farkli_kolondaki_zayif_izi_silmez():
    izler = []
    for i in range(8):
        iz = _iz(i + 1, 1, 4, f"KREDI {i}", [.5, .7, .8, .76], destek=4)
        for no, oge in enumerate(iz["ogeler"]):
            oge["kare_sira"] = no + 1
            oge["box"] = [.5, .7 - no * .12, .8, .76 - no * .12]
        izler.append(iz)
    izler.append(_iz(99, 2, 2, "TEK KARE KOLON", [.05, .4, .25, .46],
                      destek=1))
    izin = {x["iz_id"] for x in izler}
    for iz in izler:
        for oge in iz["ogeler"]:
            oge["frame_luma"] = 20.0
    assert metin_izleri.zayif_layout_disinda_izler(izler, izin) == set()


def test_ayni_xte_ama_kredi_fontundan_cok_buyuk_tabela_elenir():
    izler = [
        _iz(1, 35, 39, "IMAM", [.50, .64, .62, .70], destek=4),
        _iz(2, 36, 40, "IBRAHIM UNEY", [.50, .70, .84, .77], destek=4),
        _iz(3, 38, 38, "POLIS", [.50, .55, .72, .75], destek=1),
    ]
    izin = {x["iz_id"] for x in izler}
    assert 3 in metin_izleri.zayif_layout_disinda_izler(izler, izin)
