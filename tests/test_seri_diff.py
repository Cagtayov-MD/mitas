# -*- coding: utf-8 -*-
"""test_seri_diff.py — dizi modu SAF diff motoru sözleşme testleri.

Sözleşme: scripts/dizi_SISTEM.md "Diff çıktı şeması" + "Diff politikası ve kuralları" (1-7).
Her kural ayrı test; KB/duckdb/ollama YOK (motor saf, IO'suz).
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from seri_diff import DiffPolitika, diffle, uygula  # noqa: E402


# ---------------------------------------------------------------- yapı taşları
# 5 AKTİF oyuncu + 1 TEKİL alan → FORMAT_KOPUSU paydası 6; tek eksikte oran 5/6
# kopus_esik=0.40 üstünde kalır (kopuş testleri HARİÇ kazara tetiklenmez).
FULL_CAST = ["POLAT ALEMDAR", "MERT FIRAT", "ELIF YILDIZ", "KEMAL SOYDERE", "AYSE KAYA"]
FULL_CREW = {"Yönetmen": ["SAMET POLAT"]}


def _taze_master():
    """LOCKED, 3-bölüm tohumlu minimal master (dizi_SISTEM.md şeması)."""
    oyuncular = {}
    for i, ad in enumerate(FULL_CAST):
        oyuncular[ad] = {
            "yazimlar": {ad: 3},
            "bolumler": [1, 2, 3], "sira": i,
            "kb_teyit": False, "durum": "AKTIF",
            "son_gorulme": 3, "ardisik_yok": 0, "ayrilma_bolumu": None,
        }
    # yazım-tanığı istisnası (kural 1): P0LAT rakamlı OCR-varyantı tanık olarak kayıtlı
    oyuncular["POLAT ALEMDAR"]["yazimlar"] = {"POLAT ALEMDAR": 2, "P0LAT ALEMDAR": 1}
    return {
        "surum_sema": 1,
        "seri_anahtar": "TEST_SERI_00000000",
        "seri_adi": "TEST SERİ",
        "kaynak_klasor": "D:\\GELEN\\TEST SERİ",
        "trt_on_ekler": ["1900-0138-0"],
        "durum": "LOCKED",
        "master_surum": 1,
        "kilit_bolumler": [1, 2, 3],
        "surum_gecmisi": [{"surum": 1, "olay": "kilit", "bolumler": [1, 2, 3],
                           "ts": "2026-07-09T12:00:00"}],
        "alanlar": {
            "Yönetmen": {
                "kanonik": ["SAMET POLAT"], "guven": "KESIN", "kb_teyit": False,
                "tanik": {"SAMET POLAT": {"bolumler": [1, 2, 3],
                                          "yazimlar": {"SAMET POLAT": 3}}},
            },
        },
        "oyuncular": oyuncular,
        "teknik_ekip": {},
        "aday_havuzu": {},
        "konuk_gecmisi": {},
        "bekleyen_degisimler": [],
        "format_kopusu": {"ardisik": 0, "ilk_bolum": None},
        "tanik_kayitlari": {},
        "guncelleme": {},
    }


def _okuma(bolum, cast=None, crew=None, konuk=None, vl=None):
    """BolumOkuma şeması (dizi_SISTEM.md) — cast konuk_acik-düşülmüş kabul edilir."""
    return {
        "bolum_no": bolum,
        "trt_id": "1900-0138-0-%04d-00-1" % bolum,
        "cast": list(cast or []),
        "crew": dict(crew if crew is not None else FULL_CREW),
        "konuk_acik": list(konuk or []),
        "kb_hatti": {"yonetmen": [], "yapimci": [], "cast": []},
        "vl": dict(vl or {"yonetmen": [], "oyuncular": [], "diger_roller": []}),
        "stop_kart_bolum_no": None,
        "kaynak": "master_dilim",
        "uyarilar": [],
    }


def test_politika_varsayilanlari_sozlesmeye_esit():
    p = DiffPolitika()
    assert (p.eksik_esik, p.kalici_esik, p.terfi_esik, p.konuk_max, p.kopus_esik) == \
        (3, 2, 3, 12, 0.40)


# ------------------------------------------------------------------- (a) eşleşen
def test_a_yazim_tanigi_fold_eslesir_kanonik_masterdan_ardisik_yok_sifirlanir():
    m = _taze_master()
    m["oyuncular"]["POLAT ALEMDAR"]["ardisik_yok"] = 1  # sıfırlanacak
    cast = ["P0LAT ALEMDAR"] + FULL_CAST[1:]  # rakamlı yazım — name_match DEĞİL, tanık-fold
    d = diffle(m, _okuma(4, cast=cast))
    esler = [e for e in d["eslesen"]["oyuncular"] if e["master"] == "POLAT ALEMDAR"]
    assert esler == [{"master": "POLAT ALEMDAR", "okunan": "P0LAT ALEMDAR"}]
    assert not [e for e in d["eksik"] if e["isim"] == "POLAT ALEMDAR"]
    m1, _ = uygula(m, d, simdi="2026-07-09T13:00:00")
    assert m1["oyuncular"]["POLAT ALEMDAR"]["ardisik_yok"] == 0
    assert m1["oyuncular"]["POLAT ALEMDAR"]["son_gorulme"] == 4
    # yazım tanığı sayacı arttı
    assert m1["oyuncular"]["POLAT ALEMDAR"]["yazimlar"]["P0LAT ALEMDAR"] == 2


# --------------------------------------------------------------------- (b) eksik
def test_b_eksik_ocr_kacak_uc_ardisik_yoklukta_ayrildi():
    m = _taze_master()
    eksik_cast = [ad for ad in FULL_CAST if ad != "MERT FIRAT"]
    # bölüm 4: 1. yokluk → OCR_KACAK (KONTROL YOK — isim kanondan yine basılır)
    d4 = diffle(m, _okuma(4, cast=eksik_cast))
    e4 = [e for e in d4["eksik"] if e["isim"] == "MERT FIRAT"]
    assert e4 == [{"alan": "oyuncular", "isim": "MERT FIRAT",
                   "ardisik_yok_yeni": 1, "karar": "OCR_KACAK"}]
    assert d4["kontrol_nedenleri"] == []
    m1, o1 = uygula(m, d4, simdi="t4")
    assert m1["oyuncular"]["MERT FIRAT"]["ardisik_yok"] == 1
    assert m1["oyuncular"]["MERT FIRAT"]["durum"] == "AKTIF"
    # bölüm 5: 2. yokluk → hâlâ OCR_KACAK
    d5 = diffle(m1, _okuma(5, cast=eksik_cast))
    assert [e["karar"] for e in d5["eksik"] if e["isim"] == "MERT FIRAT"] == ["OCR_KACAK"]
    m2, _ = uygula(m1, d5, simdi="t5")
    # bölüm 6: 3. ardışık yokluk → AYRILDI + olay
    d6 = diffle(m2, _okuma(6, cast=eksik_cast))
    e6 = [e for e in d6["eksik"] if e["isim"] == "MERT FIRAT"]
    assert e6[0]["ardisik_yok_yeni"] == 3 and e6[0]["karar"] == "AYRILDI"
    m3, o3 = uygula(m2, d6, simdi="t6")
    assert m3["oyuncular"]["MERT FIRAT"]["durum"] == "AYRILDI"
    assert m3["oyuncular"]["MERT FIRAT"]["ayrilma_bolumu"] == 6
    assert any(o.get("tip") == "ayrilma" and o.get("isim") == "MERT FIRAT" for o in o3)


# ----------------------------------------------------------------- (c) yeni cast
def test_c_yeni_cast_konuk_adayi_kontrol_yok():
    m = _taze_master()
    d = diffle(m, _okuma(4, cast=FULL_CAST + ["OKTAY DENER"]))
    assert d["yeni"] == [{"alan": "oyuncular", "isim": "OKTAY DENER",
                          "karar": "KONUK_ADAYI", "kaynak": "cast-diff"}]
    assert d["kontrol_nedenleri"] == []
    assert d["bolum_ozel"]["konuk_oyuncular"] == \
        [{"isim": "OKTAY DENER", "kaynak": "cast-diff", "kesin": False}]


def test_c_konuk_acik_kaynaklilar_kesin_true():
    m = _taze_master()
    d = diffle(m, _okuma(4, cast=FULL_CAST, konuk=["ALTAN ALKAN"]))
    girdi = [g for g in d["bolum_ozel"]["konuk_oyuncular"] if g["isim"] == "ALTAN ALKAN"]
    assert girdi == [{"isim": "ALTAN ALKAN", "kaynak": "jenerik-basligi", "kesin": True}]
    assert d["kontrol_nedenleri"] == []


def test_c_konuk_max_asiminda_kontrol():
    m = _taze_master()
    pol = DiffPolitika(konuk_max=2)
    yeniler = ["OKTAY DENER", "SELIM CAN", "FERIDE GUL"]  # 3 > konuk_max=2
    d = diffle(m, _okuma(4, cast=FULL_CAST + yeniler), pol)
    assert len([y for y in d["yeni"] if y["alan"] == "oyuncular"]) == 3
    assert any("yeni-isim" in s for s in d["kontrol_nedenleri"])


# ----------------------------------------------------------- (d) yeni TEKİL alan
def test_d_tekil_alan_garblesiz_override_ve_kontrol():
    m = _taze_master()
    d = diffle(m, _okuma(4, cast=FULL_CAST, crew={"Yönetmen": ["CEM DENIZ"]}))
    adaylar = [y for y in d["yeni"] if y["alan"] == "Yönetmen"]
    assert len(adaylar) == 1 and adaylar[0]["isim"] == "CEM DENIZ"
    assert adaylar[0]["karar"] == "DEGISIM_ADAYI"
    assert d["bolum_ozel"]["alan_override"] == {"Yönetmen": ["CEM DENIZ"]}
    assert len(d["kontrol_nedenleri"]) >= 1


def test_d_tekil_alan_garble_override_yok_kontrol_var():
    m = _taze_master()
    # "DIRECTED" _looks_garble rol/kurum blocklist'inde → garble sinyali
    d = diffle(m, _okuma(4, cast=FULL_CAST, crew={"Yönetmen": ["CEM DIRECTED"]}))
    adaylar = [y for y in d["yeni"] if y["alan"] == "Yönetmen"]
    assert len(adaylar) == 1 and adaylar[0]["karar"] == "DEGISIM_ADAYI"
    assert "Yönetmen" not in d["bolum_ozel"]["alan_override"]  # override YOK, master basılır
    assert len(d["kontrol_nedenleri"]) >= 1


# ------------------------------------------------------------ (e) kalıcı değişim
def _vl_cem():
    return {"yonetmen": ["CEM DENIZ"], "oyuncular": [], "diger_roller": []}


def test_e_kalici_degisim_vl_teyitli_iki_ardisik_bolum():
    m = _taze_master()
    # bölüm 13: fark ilk kez → bekleyen açılır, kalıcı YOK
    d13 = diffle(m, _okuma(13, cast=FULL_CAST, crew={"Yönetmen": ["CEM DENIZ"]}, vl=_vl_cem()))
    assert d13["kalici_degisim"] == []
    m1, _ = uygula(m, d13, simdi="t13")
    assert len(m1["bekleyen_degisimler"]) == 1
    p = m1["bekleyen_degisimler"][0]
    assert p["alan"] == "Yönetmen" and p["gorulen_bolumler"] == [13]
    assert p["vl_teyit_bolumler"] == [13] and p["ilk_bolum"] == 13
    # bölüm 14: aynı fark + VL-teyit → kalici_degisim
    d14 = diffle(m1, _okuma(14, cast=FULL_CAST, crew={"Yönetmen": ["CEM DENIZ"]}, vl=_vl_cem()))
    assert d14["kalici_degisim"] == \
        [{"alan": "Yönetmen", "yeni": ["CEM DENIZ"], "kanit_bolumler": [13, 14]}]
    m2, o2 = uygula(m1, d14, simdi="t14")
    assert m2["master_surum"] == 2
    assert m2["alanlar"]["Yönetmen"]["kanonik"] == ["CEM DENIZ"]
    assert m2["bekleyen_degisimler"] == []
    assert any(g["olay"] == "kalici_degisim" and g["surum"] == 2 for g in m2["surum_gecmisi"])
    assert any(o.get("tip") == "kalici_degisim" for o in o2)
    # bölüm 15: artık eşleşen + KONTROL YOK
    d15 = diffle(m2, _okuma(15, cast=FULL_CAST, crew={"Yönetmen": ["CEM DENIZ"]}, vl=_vl_cem()))
    assert d15["eslesen"]["alanlar"]["Yönetmen"]["master"] == ["CEM DENIZ"]
    assert not [y for y in d15["yeni"] if y["alan"] == "Yönetmen"]
    assert d15["kontrol_nedenleri"] == []


def test_e_vl_teyitsiz_kalici_bos_master_aday_beklemede():
    m = _taze_master()
    d13 = diffle(m, _okuma(13, cast=FULL_CAST, crew={"Yönetmen": ["CEM DENIZ"]}))  # VL boş
    m1, _ = uygula(m, d13, simdi="t13")
    assert m1["bekleyen_degisimler"][0]["vl_teyit_bolumler"] == []
    d14 = diffle(m1, _okuma(14, cast=FULL_CAST, crew={"Yönetmen": ["CEM DENIZ"]}))
    assert d14["kalici_degisim"] == []  # VL çapraz-tanık yok → master DEĞİŞMEZ
    assert len(d14["kontrol_nedenleri"]) >= 1  # KONTROL devam
    m2, _ = uygula(m1, d14, simdi="t14")
    assert m2["master_surum"] == 1  # sürüm atlamadı
    assert m2["bekleyen_degisimler"][0]["gorulen_bolumler"] == [13, 14]  # MASTER_ADAY beklemede


def test_e_araya_farksiz_bolum_girince_bekleyen_sifirlanir():
    m = _taze_master()
    d13 = diffle(m, _okuma(13, cast=FULL_CAST, crew={"Yönetmen": ["CEM DENIZ"]}, vl=_vl_cem()))
    m1, _ = uygula(m, d13, simdi="t13")
    assert len(m1["bekleyen_degisimler"]) == 1
    # bölüm 14: fark GÖRÜLMEDİ (master değeri okundu) → bekleyen kayıt düşer
    d14 = diffle(m1, _okuma(14, cast=FULL_CAST, crew={"Yönetmen": ["SAMET POLAT"]}))
    m2, _ = uygula(m1, d14, simdi="t14")
    assert m2["bekleyen_degisimler"] == []


# ---------------------------------------------------------------- (f) FORMAT_KOPUSU
def test_f_format_kopusu_diff_alan_alan_diff_yapilmaz_tek_kontrol():
    m = _taze_master()
    d = diffle(m, _okuma(4, cast=["TANIMSIZ KISI", "BASKA BIRI"], crew={}))
    assert d["format_kopusu"] is True
    assert d["eksik"] == [] and d["yeni"] == []
    assert d["eslesen"]["oyuncular"] == [] and d["eslesen"]["alanlar"] == {}
    assert len(d["kontrol_nedenleri"]) == 1


def test_f_format_kopusu_sayac_ve_iki_ardisikta_olay():
    m = _taze_master()
    # yama-madde 7 (BOS_OKUMA) sonrası tek-isimli okuma havuz-eşiğin ALTINDA kalır
    # (1 < min(8, ceil(0.3*6))=2) → kopuş yolunu tetiklemek için havuz eşik-üstü
    # (2 isim) ama master-eşleşme-oranı sıfır tutulur.
    d4 = diffle(m, _okuma(4, cast=["TANIMSIZ KISI", "BASKA BIRI"], crew={}))
    m1, o1 = uygula(m, d4, simdi="t4")
    assert m1["format_kopusu"] == {"ardisik": 1, "ilk_bolum": 4}
    assert not any(o.get("tip") == "format_kopusu" for o in o1)
    d5 = diffle(m1, _okuma(5, cast=["TANIMSIZ KISI", "BASKA BIRI"], crew={}))
    m2, o2 = uygula(m1, d5, simdi="t5")
    assert m2["format_kopusu"]["ardisik"] == 2
    assert any(o.get("tip") == "format_kopusu" for o in o2)
    # kopuş bölümünde üyeler cezalandırılmaz (eksik üretilmedi)
    assert m2["oyuncular"]["POLAT ALEMDAR"]["ardisik_yok"] == 0
    # araya normal bölüm girince sayaç sıfırlanır
    d6 = diffle(m2, _okuma(6, cast=FULL_CAST))
    m3, _ = uygula(m2, d6, simdi="t6")
    assert m3["format_kopusu"] == {"ardisik": 0, "ilk_bolum": None}


# --------------------------------------------------------------------- (g) terfi
def test_g_konuk_uc_farkli_bolumde_terfi_aktif_kadroya_sira_max_arti_bir():
    m = _taze_master()
    m["konuk_gecmisi"] = {"OKTAY DENER": {"bolumler": [5, 9], "yazimlar": {"OKTAY DENER": 2}}}
    d = diffle(m, _okuma(14, cast=FULL_CAST + ["OKTAY DENER"]))
    assert d["terfi"] == [{"isim": "OKTAY DENER", "bolumler": [5, 9, 14]}]
    # terfi eden isim konuk/yeni listelerinde TEKRARLANMAZ (cast'e taşınacak)
    assert not [y for y in d["yeni"] if y["isim"] == "OKTAY DENER"]
    assert not [g for g in d["bolum_ozel"]["konuk_oyuncular"] if g["isim"] == "OKTAY DENER"]
    m1, o1 = uygula(m, d, simdi="t14")
    kayit = m1["oyuncular"]["OKTAY DENER"]
    assert kayit["durum"] == "AKTIF" and kayit["sira"] == 5  # mevcut max(0..4)+1
    assert kayit["ardisik_yok"] == 0 and kayit["son_gorulme"] == 14
    assert "OKTAY DENER" not in m1["konuk_gecmisi"]
    assert any(o.get("tip") == "terfi" for o in o1)


# ---------------------------------------------------------- (h) AYRILDI'nın dönüşü
def test_h_ayrildi_uyenin_donusu_konuk_degil_yeniden_aktif():
    m = _taze_master()
    m["oyuncular"]["KEMAL SOYDERE"].update(
        {"durum": "AYRILDI", "ayrilma_bolumu": 8, "ardisik_yok": 3})
    d = diffle(m, _okuma(14, cast=FULL_CAST))  # KEMAL SOYDERE okumada VAR
    assert any(e["master"] == "KEMAL SOYDERE" for e in d["eslesen"]["oyuncular"])
    assert not [y for y in d["yeni"] if y["isim"] == "KEMAL SOYDERE"]  # konuk DEĞİL
    m1, _ = uygula(m, d, simdi="t14")
    kayit = m1["oyuncular"]["KEMAL SOYDERE"]
    assert kayit["durum"] == "AKTIF" and kayit["ayrilma_bolumu"] is None
    assert kayit["ardisik_yok"] == 0


# ------------------------------------------- (i) aynı bölümde benzer isimler ayrı
def test_i_ayni_bolumde_birlikte_gorulen_iki_benzer_isim_birlestirilmez():
    m = _taze_master()
    # İki yazım AYNI bölümde birlikte: exact olan eşleşir, diğeri AYRI kişi sayılır
    d = diffle(m, _okuma(4, cast=FULL_CAST + ["P0LAT ALEMDAR"]))
    esler = [e for e in d["eslesen"]["oyuncular"] if e["master"] == "POLAT ALEMDAR"]
    assert esler == [{"master": "POLAT ALEMDAR", "okunan": "POLAT ALEMDAR"}]
    assert [y["isim"] for y in d["yeni"]] == ["P0LAT ALEMDAR"]


# ------------------------------------------------------ (j) ZAYIF_UYE 5-bölüm kuralı
def test_j_zayif_uye_bes_bolumun_ikisinde_gorulmezse_konuk_gecmisine_duser():
    m = _taze_master()
    m["oyuncular"]["DENIZ ATLI"] = {
        "yazimlar": {"DENIZ ATLI": 2}, "bolumler": [1, 2], "sira": 5,
        "kb_teyit": False, "durum": "ZAYIF_UYE",
        "son_gorulme": 2, "ardisik_yok": 0, "ayrilma_bolumu": None,
    }
    # kilit sonu=3; pencere 4..8; DENIZ ATLI yalnız bölüm 6'da görülür (1/5 < 2)
    for b in (4, 5, 6, 7, 8):
        cast = FULL_CAST + (["DENIZ ATLI"] if b == 6 else [])
        d = diffle(m, _okuma(b, cast=cast))
        m, olaylar = uygula(m, d, simdi="t%d" % b)
    assert "DENIZ ATLI" not in m["oyuncular"]
    assert m["konuk_gecmisi"]["DENIZ ATLI"]["bolumler"] == [6]  # pencere görülmeleri
    assert any(o.get("tip") == "zayif_dusme" for o in olaylar)


# ------------------------------------------------------------------------- saflık
def test_saflik_diffle_ve_uygula_girdi_masteri_degistirmez():
    m = _taze_master()
    m["konuk_gecmisi"] = {"OKTAY DENER": {"bolumler": [5, 9], "yazimlar": {"OKTAY DENER": 2}}}
    kopya = copy.deepcopy(m)
    d = diffle(m, _okuma(14, cast=FULL_CAST + ["OKTAY DENER"],
                         crew={"Yönetmen": ["CEM DENIZ"]}, vl=_vl_cem()))
    m1, _ = uygula(m, d, simdi="t14")
    assert m == kopya          # girdi DEĞİŞMEDİ
    assert m1 is not m         # kopya üzerinde çalışıldı


def test_uygula_guncelleme_alani_yazilir():
    m = _taze_master()
    d = diffle(m, _okuma(4, cast=FULL_CAST))
    m1, _ = uygula(m, d, simdi="2026-07-09T14:00:00")
    assert m1["guncelleme"] == {"ts": "2026-07-09T14:00:00", "modul": "seri_diff", "bolum": 4}


# ===================================== PİLOT-ÖNCESİ YAMA SÖZLEŞMESİ (2026-07-09)
# dizi_SISTEM.md "PİLOT-ÖNCESİ YAMA SÖZLEŞMESİ" madde 2 / 5 / 7 testleri.


# ------------------------------------------------ (m2) terfi kanonik disiplini
def test_m2_terfi_kadro_anahtari_kanonik_sec_rakamli_defter_anahtari_tasinmaz():
    m = _taze_master()
    # legacy defter: anahtar rakamlı ilk-görülmeyle açılmış; çoğunluk rakamsız yazımda
    m["konuk_gecmisi"] = {"0KTAY DENER": {
        "bolumler": [5, 9], "yazimlar": {"0KTAY DENER": 1, "OKTAY DENER": 2}}}
    d = diffle(m, _okuma(14, cast=FULL_CAST + ["OKTAY DENER"]))
    assert d["terfi"] == [{"isim": "0KTAY DENER", "bolumler": [5, 9, 14]}]
    m1, o1 = uygula(m, d, simdi="t14")
    assert "OKTAY DENER" in m1["oyuncular"]       # kadro anahtarı = kanonik_sec seçimi
    assert "0KTAY DENER" not in m1["oyuncular"]   # rakamlı defter-anahtarı kadroya taşınmadı
    kayit = m1["oyuncular"]["OKTAY DENER"]
    assert kayit["durum"] == "AKTIF" and kayit["sira"] == 5
    assert kayit["bolumler"] == [5, 9, 14] and kayit["son_gorulme"] == 14
    # yazım defteri HAM yazımları korur (OCR-otorite; anahtar yalnız iç seçimdir)
    assert kayit["yazimlar"]["0KTAY DENER"] >= 1 and kayit["yazimlar"]["OKTAY DENER"] >= 2
    assert m1["konuk_gecmisi"] == {}
    assert any(o.get("tip") == "terfi" and o.get("isim") == "OKTAY DENER" for o in o1)
    assert any(g["olay"] == "terfi" and g["isim"] == "OKTAY DENER"
               for g in m1["surum_gecmisi"])


def test_m2_konuk_gecmisine_rakamli_yazim_yeni_anahtar_acamaz():
    m = _taze_master()
    d = diffle(m, _okuma(4, cast=FULL_CAST + ["0KTAY DENER"]))
    m1, _ = uygula(m, d, simdi="t4")
    assert "0KTAY DENER" not in m1["konuk_gecmisi"]    # rakamlı yazım anahtar OLAMAZ
    kayit = m1["konuk_gecmisi"]["OKTAY DENER"]         # rakamsız varyant anahtar oldu
    assert kayit["yazimlar"] == {"0KTAY DENER": 1}     # defter HAM yazımı tutar (OCR-otorite)
    assert kayit["bolumler"] == [4]
    # sonraki bölümdeki temiz yazım AYNI deftere birikir (ayrı anahtar açılmaz)
    d5 = diffle(m1, _okuma(5, cast=FULL_CAST + ["OKTAY DENER"]))
    m2, _ = uygula(m1, d5, simdi="t5")
    assert set(m2["konuk_gecmisi"]) == {"OKTAY DENER"}
    assert m2["konuk_gecmisi"]["OKTAY DENER"]["yazimlar"] == \
        {"0KTAY DENER": 1, "OKTAY DENER": 1}
    assert m2["konuk_gecmisi"]["OKTAY DENER"]["bolumler"] == [4, 5]


def test_m2_salt_rakam_token_varyantsiz_isim_aynen_anahtar_olur():
    m = _taze_master()
    d = diffle(m, _okuma(4, cast=FULL_CAST + ["MELIS 42"]))
    m1, _ = uygula(m, d, simdi="t4")
    # "42" salt-rakam token: harf uydurulamaz ("okunamadı > yanlış oku") → isim aynen
    assert "MELIS 42" in m1["konuk_gecmisi"]
    assert m1["konuk_gecmisi"]["MELIS 42"]["yazimlar"] == {"MELIS 42": 1}


# ------------------------------------------------------------- (m5a) telemetri
def test_m5a_bekleyen_dususte_bekleyen_dustu_olayi_uretilir():
    m = _taze_master()
    d13 = diffle(m, _okuma(13, cast=FULL_CAST, crew={"Yönetmen": ["CEM DENIZ"]}, vl=_vl_cem()))
    m1, _ = uygula(m, d13, simdi="t13")
    assert len(m1["bekleyen_degisimler"]) == 1
    # bölüm 14: fark görülmedi → kayıt düşer + telemetri olayı (sözleşme-literal şekil)
    d14 = diffle(m1, _okuma(14, cast=FULL_CAST, crew={"Yönetmen": ["SAMET POLAT"]}))
    m2, o2 = uygula(m1, d14, simdi="t14")
    assert m2["bekleyen_degisimler"] == []
    ev = [o for o in o2 if o.get("olay") == "bekleyen_dustu"]
    assert len(ev) == 1
    assert ev[0]["alan"] == "Yönetmen" and ev[0]["gorulen"] == [13]
    assert ev[0].get("tip") == "bekleyen_dustu"   # modül olay-geleneği de korunur
    assert ev[0].get("bolum") == 14


# ------------------------------------------------------------- (m5b) telemetri
def test_m5b_vl_uyusmazlik_eslesen_yazim_vl_birlesiminde_yoksa_dolar():
    m = _taze_master()
    cast = ["P0LAT ALEMDAR"] + FULL_CAST[1:]
    vl = {"yonetmen": ["BAMBASKA YONETMEN"],
          "oyuncular": ["POLAT ALEMDAR"] + FULL_CAST[1:], "diger_roller": []}
    d = diffle(m, _okuma(4, cast=cast, vl=vl))
    # P0LAT ALEMDAR tanık-fold ile eşleşir ama VL birleşiminde name_match YOK
    # (p0lat≠polat); Yönetmen okunanı SAMET POLAT da VL birleşiminde yok.
    assert {(u["alan"], u["isim"]) for u in d["vl_uyusmazlik"]} == \
        {("oyuncular", "P0LAT ALEMDAR"), ("Yönetmen", "SAMET POLAT")}
    assert len(d["vl_uyusmazlik"]) == 2   # temiz eşleşenler listeye GİRMEZ
    # basım/karar ETKİLENMEZ: eşleşme aynı, KONTROL nedeni üretilmez
    assert any(e["okunan"] == "P0LAT ALEMDAR" for e in d["eslesen"]["oyuncular"])
    assert d["eslesen"]["alanlar"]["Yönetmen"]["okunan"] == ["SAMET POLAT"]
    assert d["kontrol_nedenleri"] == []


def test_m5b_vl_tamamen_bos_ise_vl_uyusmazlik_dolmaz():
    m = _taze_master()
    d = diffle(m, _okuma(4, cast=FULL_CAST))   # _okuma varsayılanı: üç boş VL listesi
    assert d["vl_uyusmazlik"] == []            # kapsam yok ≠ uyuşmazlık


# --------------------------------------------------------------- (m7) BOS_OKUMA
def test_m7_bos_okuma_kaynak_yok_tetigi_diff_hukum_vermez():
    m = _taze_master()
    m["oyuncular"]["MERT FIRAT"]["ardisik_yok"] = 2   # bir yokluk daha = AYRILDI eşiği
    ok = _okuma(9, cast=[ad for ad in FULL_CAST if ad != "MERT FIRAT"])
    ok["kaynak"] = "yok"          # havuz eşik-üstü (5 isim) olsa da tek başına tetikler
    d = diffle(m, ok)
    assert d["bos_okuma"] is True
    assert d["kontrol_nedenleri"] == ["OKUMA_YOK: bölüm 9"]   # TEK neden
    assert d["eksik"] == [] and d["yeni"] == [] and d["terfi"] == []
    assert d["kalici_degisim"] == [] and d["format_kopusu"] is False
    assert d["eslesen"]["oyuncular"] == [] and d["eslesen"]["alanlar"] == {}
    assert d["bolum_ozel"] == {"konuk_oyuncular": [], "alan_override": {}}


def test_m7_bos_okuma_kisa_havuz_tetigi():
    m = _taze_master()
    # havuz benzersiz=1 < min(8, ceil(0.3*6))=2 → kopuş DEĞİL, BOS_OKUMA
    d = diffle(m, _okuma(9, cast=["POLAT ALEMDAR"], crew={}))
    assert d["bos_okuma"] is True and d["format_kopusu"] is False
    assert d["kontrol_nedenleri"] == ["OKUMA_YOK: bölüm 9"]


def test_m7_bos_okuma_uygula_sayaclara_ve_bekleyene_dokunmaz():
    m = _taze_master()
    m["oyuncular"]["MERT FIRAT"].update({"ardisik_yok": 2, "son_gorulme": 6})
    m["format_kopusu"] = {"ardisik": 1, "ilk_bolum": 8}
    m["bekleyen_degisimler"] = [{"tip": "alan_degisim", "alan": "Yönetmen",
                                 "yeni": ["CEM DENIZ"], "gorulen_bolumler": [8],
                                 "vl_teyit_bolumler": [8], "ilk_bolum": 8}]
    ok = _okuma(9, cast=[])
    ok["kaynak"] = "yok"
    d = diffle(m, ok)
    assert d["bos_okuma"] is True
    m1, o1 = uygula(m, d, simdi="t9")
    # üye sayaçları DEĞİŞMEDİ (kanıt yokluğu ceza değil)
    assert m1["oyuncular"]["MERT FIRAT"]["ardisik_yok"] == 2
    assert m1["oyuncular"]["MERT FIRAT"]["son_gorulme"] == 6
    assert m1["oyuncular"]["MERT FIRAT"]["durum"] == "AKTIF"
    # kopuş sayacına DOKUNULMADI (artmadı da, sıfırlanmadı da)
    assert m1["format_kopusu"] == {"ardisik": 1, "ilk_bolum": 8}
    # bekleyen SIFIRLANMADI (kanıt yokluğu ≠ fark yokluğu) → bekleyen_dustu olayı da YOK
    assert m1["bekleyen_degisimler"] == m["bekleyen_degisimler"]
    assert not any(o.get("olay") == "bekleyen_dustu" for o in o1)
    assert m1["guncelleme"] == {"ts": "t9", "modul": "seri_diff", "bolum": 9}
