import metin_uzlastirici as u


def test_v6_boslugu_v5_turkce_isaretleri_birlesir():
    sonuc, karar = u.uzlastir("ÜMİTYESİN", "ÜMIT YESIN")
    assert sonuc == "ÜMİT YESİN"
    assert karar == "consensus"


def test_v6_taban_harfi_v5_diyakritigi_korunur():
    sonuc, _ = u.uzlastir("CENGİZ KÜGÜKAYVAZ", "CENGIZ KÜÇÜKAYVAZ")
    assert sonuc == "CENGİZ KÜÇÜKAYVAZ"


def test_tesseract_yalniz_uyumlu_diyakritigi_tasir():
    sonuc, _ = u.uzlastir("ESREF KOLÇAK", "ESREFKOLÇAK", "EŞREF: KOLÇAK")
    assert sonuc == "EŞREF KOLÇAK"


def test_v5_nokta_ve_kelime_sablonu_kaybolmaz():
    sonuc, _ = u.uzlastir("ZEYNEP S. AGIN", "ZEYNEPS.AGİN")
    assert sonuc == "ZEYNEP S. AGİN"


def test_uyusmayan_ikinci_okuma_birincili_ezmez():
    sonuc, karar = u.uzlastir("TUNA ARMAN", "BAMBAŞKA YAZI")
    assert sonuc == "TUNA ARMAN"
    assert karar == "conflict"


def test_dusuk_skorlu_v6_taban_harfi_dogru_v5i_ezmez():
    sonuc, _ = u.uzlastir(
        "ışık şefi", "usik sefi", primary_score=.86, secondary_score=.83)
    assert sonuc == "ışık şefi"


def test_ekstra_harfli_tesseract_diyakritigi_kaydirmasi_engellenir():
    sonuc, _ = u.uzlastir(
        "FUNDA GÜRDAĞ", "FUNDA GÜRDAG", "İFUNDAĞGURDAĞ",
        primary_score=.97, secondary_score=.99)
    assert sonuc == "FUNDA GÜRDAĞ"


def test_birlesik_i_nfc_olarak_yazilir():
    sonuc, _ = u.uzlastir("ALİ CENGİZ", "ALi CENGiZ", "ALİ CENGİZ")
    assert sonuc == "ALİ CENGİZ"
    assert "i\u0307" not in sonuc


def test_tek_tesseract_oo_dizisini_cift_o_umlaut_yapamaz():
    sonuc, _ = u.uzlastir(
        "genel koordinatör", "genel koordinatör", "genel köördinatör")
    assert sonuc == "genel koordinatör"


def test_tesseract_kelime_siniri_iki_paddle_bitisigini_ayirir():
    sonuc, _ = u.uzlastir("GÜLGÖLGE", "GÜLGÖLGE", "GÜL GÖLGE")
    assert sonuc == "GÜL GÖLGE"


def test_farkli_uzunluktaki_iskelet_tum_bosluklari_silemez():
    sonuc, _ = u.uzlastir(
        "Performed by GROUP HOME", "Pedarmed by GROUP HOME",
        primary_score=.96, secondary_score=.89)
    assert sonuc == "Performed by GROUP HOME"


def test_turkce_kanit_yokken_tesseract_ingilizce_i_harfini_degistiremez():
    sonuc, _ = u.uzlastir(
        "G. SCHIRMER INC. (ASCAP)", "G. SCHIRMER INC. (ASCAP)",
        "G. SCHIRMER İNC. (ASCAP)")
    assert sonuc == "G. SCHIRMER INC. (ASCAP)"


def test_coklu_kirpim_tek_yuksek_skorlu_sapmaya_degildir():
    kayitlar = [
        {"id": "bulanık", "secondary_text": "MELDA ARAT MUTU",
         "secondary_score": .99, "secondary_sharp_text": "",
         "secondary_sharp_score": 0.0},
        {"id": "temiz-1", "secondary_text": "MELDA ARAT MUTLU",
         "secondary_score": .96, "secondary_sharp_text": "",
         "secondary_sharp_score": 0.0},
        {"id": "temiz-2", "secondary_text": "MELDA ARAT MUTLU",
         "secondary_score": .95, "secondary_sharp_text": "",
         "secondary_sharp_score": 0.0},
    ]
    metin, _skor, kayit = u._coklu_ikincil_sec(
        kayitlar, "MELDA ARAT MUTLU")
    assert metin == "MELDA ARAT MUTLU"
    assert kayit["id"].startswith("temiz")


def test_yuksek_skorlu_v6_harf_kelimesine_rakam_sokamaz():
    sonuc, _ = u.uzlastir(
        "ışık şefi", "1s1k sefi", "»ışık şefi.",
        primary_score=.90, secondary_score=.94)
    assert sonuc == "ışık şefi"


def test_uc_kirpimin_ayni_ikincil_okumasi_oybirligidir():
    kayitlar = [
        {"secondary_text": "JOE NASSER", "secondary_score": .97,
         "secondary_sharp_text": "", "secondary_sharp_score": 0.0},
        {"secondary_text": "JOE NASSER", "secondary_score": .99,
         "secondary_sharp_text": "", "secondary_sharp_score": 0.0},
        {"secondary_text": "JOE NASSER", "secondary_score": .98,
         "secondary_sharp_text": "", "secondary_sharp_score": 0.0},
    ]
    assert u._coklu_oy_orani(kayitlar, "JOE NABBER", "JOE NASSER") == 1.0
    sonuc, karar = u.uzlastir(
        "JOE NABBER", "JOE NASSER", min_benzerlik=.74,
        primary_score=.98, secondary_score=.99)
    assert sonuc == "JOE NASSER"
    assert karar == "consensus"
