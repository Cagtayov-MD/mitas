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
    d4 = diffle(m, _okuma(4, cast=["TANIMSIZ KISI"], crew={}))
    m1, o1 = uygula(m, d4, simdi="t4")
    assert m1["format_kopusu"] == {"ardisik": 1, "ilk_bolum": 4}
    assert not any(o.get("tip") == "format_kopusu" for o in o1)
    d5 = diffle(m1, _okuma(5, cast=["TANIMSIZ KISI"], crew={}))
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
