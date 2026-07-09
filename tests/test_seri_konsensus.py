# -*- coding: utf-8 -*-
"""seri_konsensus testleri — dizi_SISTEM.md "Konsensüs kuralları" sözleşmesi (TDD).

KISIT: seri_konsensus SAF'tır (IO yok, ağ yok); KB duck-typed SAHTE nesneyle verilir —
X:/Y: sürücülerine ve Ollama'ya ASLA dokunulmaz.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import credit_crosscheck as cc  # fold — sahte KB'nin eşleşme anahtarı için
import seri_konsensus as sk


class SahteKB:
    """dizi_SISTEM KB arayüzü (duck-typing): kanonik_yazim(adaylar) -> tanınan yazım | None.

    KISIT: gerçek CreditKB duckdb açar (X:/Y:) — testte YASAK; bu sahte, fold-eşitliğiyle
    "tanıdığı" adayı geri verir, tanımadığında None döner (arayüz sözleşmesinin aynısı).
    """

    def __init__(self, bilinenler):
        self._fold_kume = {cc.fold(b) for b in bilinenler}

    def kanonik_yazim(self, adaylar):
        for a in adaylar:
            if cc.fold(a) in self._fold_kume:
                return a
        return None


def okuma(bolum_no, cast=(), crew=None, konuk=(), trt_id=None):
    """Asgari BolumOkuma (dizi_SISTEM şeması) — konsensüsün okuduğu alanlarla."""
    return {
        "bolum_no": bolum_no,
        "trt_id": trt_id or "1900-0138-0-%04d-00-1" % bolum_no,
        "cast": list(cast),
        "crew": dict(crew or {}),
        "konuk_acik": list(konuk),
        "kb_hatti": {"yonetmen": [], "yapimci": [], "cast": []},
        "vl": {"yonetmen": [], "oyuncular": [], "diger_roller": []},
        "stop_kart_bolum_no": None,
        "kaynak": "master_dilim",
        "uyarilar": [],
    }


def kur(okumalar, kb=None):
    return sk.kur_master(
        okumalar,
        seri_adi="BİZİM DİZİ",
        seri_anahtar="BIZIM_DIZI_deadbeef",
        kaynak_klasor="D:\\GELEN\\BİZİM DİZİ",
        kb=kb,
        simdi="2026-07-09T12:00:00",
    )


# ---------------------------------------------------------------- isim_kumele

def test_isim_kumele_ocr_varyanti_tek_kume():
    # "SAMET POLAT"x2 + "SAMET P0LAT"x1 → name_close kenarıyla TEK küme
    kumeler = sk.isim_kumele([(1, "SAMET POLAT"), (2, "SAMET POLAT"), (3, "SAMET P0LAT")])
    assert len(kumeler) == 1
    assert kumeler[0]["yazimlar"] == {"SAMET POLAT": 2, "SAMET P0LAT": 1}
    assert kumeler[0]["bolumler"] == [1, 2, 3]


def test_isim_kumele_ayni_bolum_benzemeyenler_ayri_kume_kalir():
    # Regresyon: aynı bölümde birlikte görülen, name_match/name_close FALSE olan
    # iki isim AYRI küme kalır (fonksiyonun doğal davranışı — özel mantık YOK).
    assert not cc.name_match("SCOTT PAULIN", "PAULINE CHAN")
    assert not cc.name_close("SCOTT PAULIN", "PAULINE CHAN")
    kumeler = sk.isim_kumele([(1, "SCOTT PAULIN"), (1, "PAULINE CHAN")])
    assert len(kumeler) == 2
    # deterministik sıra: ilk görülme
    assert list(kumeler[0]["yazimlar"]) == ["SCOTT PAULIN"]
    assert list(kumeler[1]["yazimlar"]) == ["PAULINE CHAN"]


def test_isim_kumele_ayni_bolum_ayni_yazim_tek_tanik():
    # bir bölüm aynı yazıma en çok 1 tanık verir (çift satır OCR tekrarı şişirmesin)
    kumeler = sk.isim_kumele([(1, "SAMET POLAT"), (1, "SAMET POLAT")])
    assert kumeler[0]["yazimlar"] == {"SAMET POLAT": 1}
    assert kumeler[0]["bolumler"] == [1]


# ---------------------------------------------------------------- kanonik_sec

def _tek_kume(tanikliklar):
    kumeler = sk.isim_kumele(tanikliklar)
    assert len(kumeler) == 1
    return kumeler[0]


def test_kanonik_sec_rakam_cezasi():
    kume = _tek_kume([(1, "SAMET POLAT"), (2, "SAMET POLAT"), (3, "SAMET P0LAT")])
    kanonik, kb_teyit = sk.kanonik_sec(kume)
    assert kanonik == "SAMET POLAT"
    assert kb_teyit is False


def test_kanonik_sec_rakamli_cogunlukta_bile_kaybeder():
    # rakamlı yazım rakamsıza HER ZAMAN kaybeder — çoğunluk olsa bile
    kume = _tek_kume([(1, "SAMET P0LAT"), (2, "SAMET P0LAT"), (3, "SAMET POLAT")])
    kanonik, _ = sk.kanonik_sec(kume)
    assert kanonik == "SAMET POLAT"


def test_kanonik_sec_beraberlikte_kb_kazanir():
    kume = _tek_kume([(1, "MURAT CIMCIR"), (2, "MURAT CEMCIR")])
    kanonik, kb_teyit = sk.kanonik_sec(kume, kb=SahteKB(["MURAT CEMCIR"]))
    assert kanonik == "MURAT CEMCIR"
    assert kb_teyit is True


def test_kanonik_sec_kbsiz_beraberlikte_garblesiz_kazanir():
    # "MAKSUP" _looks_garble rol/kurum blocklist'inde; "MAKSUT" temiz.
    # Garble ÖNCE görülüyor ki (5) ilk-görülme fallback'i yanlış cevabı verirdi —
    # (4) garble-siz adımının kazandığı böyle kanıtlanır.
    kume = _tek_kume([(1, "MAKSUP DEMIR"), (2, "MAKSUT DEMIR")])
    kanonik, kb_teyit = sk.kanonik_sec(kume)
    assert kanonik == "MAKSUT DEMIR"
    assert kb_teyit is False


def test_kanonik_sec_kbsiz_garble_esitse_ilk_bolumdeki():
    # ikisi de temiz + beraberlik + KB yok → (5) ilk görülen kazanır
    kume = _tek_kume([(1, "MURAT CIMCIR"), (2, "MURAT CEMCIR")])
    kanonik, _ = sk.kanonik_sec(kume)
    assert kanonik == "MURAT CIMCIR"


def test_kanonik_sec_tek_kazanani_kb_teyit_eder():
    # beraberlik olmasa da KB verildiyse kazanan teyit edilir (kur_master ZAYIF kuralı buna dayanır)
    kume = _tek_kume([(1, "NURI BILGE CEYLAN")])
    kanonik, kb_teyit = sk.kanonik_sec(kume, kb=SahteKB(["NURI BILGE CEYLAN"]))
    assert kanonik == "NURI BILGE CEYLAN"
    assert kb_teyit is True


# ------------------------------------------------------ kur_master: TEKİL alanlar

def test_tekil_alan_2of3_kesin():
    m = kur([
        okuma(1, crew={"Yönetmen": ["SAMET POLAT"]}),
        okuma(2, crew={"Yönetmen": ["SAMET POLAT"]}),
        okuma(3),  # yönetmen okunamadı — "bölümde yok" alarm değildir
    ])
    a = m["alanlar"]["Yönetmen"]
    assert a["kanonik"] == ["SAMET POLAT"]
    assert a["guven"] == "KESIN"
    assert a["kb_teyit"] is False
    assert a["tanik"]["SAMET POLAT"]["bolumler"] == [1, 2]
    assert a["tanik"]["SAMET POLAT"]["yazimlar"] == {"SAMET POLAT": 2}


def test_tekil_alan_hic_iki_tanik_yok_kbsiz_alan_yazilmaz():
    # "okunamadı > yanlış oku": 3 bölüm 3 farklı tek-tanık isim + KB yok → alan HİÇ yazılmaz
    m = kur([
        okuma(1, crew={"Yönetmen": ["ALI VELI"]}),
        okuma(2, crew={"Yönetmen": ["HASAN BASRI"]}),
        okuma(3, crew={"Yönetmen": ["KEMAL SUNAL"]}),
    ])
    assert "Yönetmen" not in m["alanlar"]
    # kayıp verilmez: tek-tanıklar alan bilgisiyle aday havuzuna düşer
    assert m["aday_havuzu"]["ALI VELI"]["alan"] == "Yönetmen"
    assert m["aday_havuzu"]["HASAN BASRI"]["bolumler"] == [2]


def test_tekil_alan_tek_tanik_kb_teyitli_zayif():
    m = kur(
        [
            okuma(1, crew={"Yönetmen": ["NURI BILGE CEYLAN"]}),
            okuma(2),
            okuma(3),
        ],
        kb=SahteKB(["NURI BILGE CEYLAN"]),
    )
    a = m["alanlar"]["Yönetmen"]
    assert a["kanonik"] == ["NURI BILGE CEYLAN"]
    assert a["guven"] == "ZAYIF"
    assert a["kb_teyit"] is True


def test_tekil_alan_celisen_iki_kb_teyitli_tek_tanik_alan_yazilmaz():
    # muhafazakâr yorum: birden çok KB-teyitli tek-tanık küme = çelişki → alan yazılmaz
    m = kur(
        [
            okuma(1, crew={"Yönetmen": ["ALI VELI"]}),
            okuma(2, crew={"Yönetmen": ["HASAN BASRI"]}),
            okuma(3),
        ],
        kb=SahteKB(["ALI VELI", "HASAN BASRI"]),
    )
    assert "Yönetmen" not in m["alanlar"]
    assert m["aday_havuzu"]["ALI VELI"]["alan"] == "Yönetmen"
    assert m["aday_havuzu"]["HASAN BASRI"]["alan"] == "Yönetmen"


def test_es_yonetmen_iki_kume_coklu():
    m = kur([
        okuma(1, crew={"Yönetmen": ["EZEL AKAY", "GANI MUJDE"]}),
        okuma(2, crew={"Yönetmen": ["EZEL AKAY", "GANI MUJDE"]}),
        okuma(3, crew={"Yönetmen": ["EZEL AKAY"]}),
    ])
    a = m["alanlar"]["Yönetmen"]
    assert a["guven"] == "COKLU"
    assert set(a["kanonik"]) == {"EZEL AKAY", "GANI MUJDE"}
    assert a["tanik"]["EZEL AKAY"]["bolumler"] == [1, 2, 3]
    assert a["tanik"]["GANI MUJDE"]["bolumler"] == [1, 2]


def test_tekil_alan_yazim_varyantli_konsensus():
    # 2 bölüm temiz + 1 bölüm OCR-varyantı → tek küme, 3 bölüm-tanık, kanonik temiz yazım
    m = kur([
        okuma(1, crew={"Yönetmen": ["SAMET POLAT"]}),
        okuma(2, crew={"Yönetmen": ["SAMET P0LAT"]}),
        okuma(3, crew={"Yönetmen": ["SAMET POLAT"]}),
    ])
    a = m["alanlar"]["Yönetmen"]
    assert a["kanonik"] == ["SAMET POLAT"]
    assert a["guven"] == "KESIN"
    assert a["tanik"]["SAMET POLAT"]["yazimlar"] == {"SAMET POLAT": 2, "SAMET P0LAT": 1}
    assert a["tanik"]["SAMET POLAT"]["bolumler"] == [1, 2, 3]


# ------------------------------------------------------------- kur_master: CAST

def test_cast_esikleri_3of3_aktif_2of3_zayif_1of3_aday():
    m = kur([
        okuma(1, cast=["POLAT ALEMDAR"]),
        okuma(2, cast=["POLAT ALEMDAR", "MEMATI BAS", "ALTAN ALKAN"]),
        okuma(3, cast=["P0LAT ALEMDAR", "MEMATI BAS"]),
    ])
    o = m["oyuncular"]["POLAT ALEMDAR"]  # anahtar = kanonik yazım (rakamlı varyant kaybetti)
    assert o["durum"] == "AKTIF"
    assert o["yazimlar"] == {"POLAT ALEMDAR": 2, "P0LAT ALEMDAR": 1}
    assert o["bolumler"] == [1, 2, 3]
    assert o["son_gorulme"] == 3
    assert o["ardisik_yok"] == 0
    assert o["ayrilma_bolumu"] is None
    assert m["oyuncular"]["MEMATI BAS"]["durum"] == "ZAYIF_UYE"
    assert "ALTAN ALKAN" not in m["oyuncular"]
    assert m["aday_havuzu"]["ALTAN ALKAN"] == {
        "alan": "oyuncular", "bolumler": [2], "yazimlar": {"ALTAN ALKAN": 1}}


def test_cast_sira_ilk_bolum_gorunme_sirasi():
    m = kur([
        okuma(1, cast=["AYSEL TERZI", "BULENT KAYA", "CEMIL IPEK"]),
        okuma(2, cast=["AYSEL TERZI", "CEMIL IPEK", "BULENT KAYA", "DENIZ ARGUN"]),
        okuma(3, cast=["BULENT KAYA", "AYSEL TERZI", "CEMIL IPEK", "DENIZ ARGUN"]),
    ])
    # sıra = İLK bölümdeki görünme sırası; ilk bölümde olmayan (DENIZ) sonraki bölümden sıralanır
    assert [ad for ad in m["oyuncular"]] == [
        "AYSEL TERZI", "BULENT KAYA", "CEMIL IPEK", "DENIZ ARGUN"]
    assert [m["oyuncular"][ad]["sira"] for ad in m["oyuncular"]] == [0, 1, 2, 3]
    assert m["oyuncular"]["DENIZ ARGUN"]["durum"] == "ZAYIF_UYE"


def test_konuk_acik_konsensus_disi_ve_gecmise_yazilir():
    # savunma: konuk ismi cast listesine sızmış olsa bile konsensüse GİRMEZ
    m = kur([
        okuma(1, cast=["POLAT ALEMDAR"]),
        okuma(2, cast=["POLAT ALEMDAR", "OKTAY DENER"], konuk=["OKTAY DENER"]),
        okuma(3, cast=["POLAT ALEMDAR"]),
    ])
    assert "OKTAY DENER" not in m["oyuncular"]
    assert "OKTAY DENER" not in m["aday_havuzu"]
    assert m["konuk_gecmisi"]["OKTAY DENER"] == {
        "bolumler": [2], "yazimlar": {"OKTAY DENER": 1}}
    assert m["oyuncular"]["POLAT ALEMDAR"]["durum"] == "AKTIF"


# ------------------------------------------------------ kur_master: teknik_ekip

def test_teknik_ekip_esik_iki_tanik_girer_tek_tanik_aday():
    m = kur([
        okuma(1, crew={"Müzik Yönetmeni": ["CAN ATİLLA"], "Işık": ["VEDAT KOC"]}),
        okuma(2, crew={"Müzik Yönetmeni": ["CAN ATİLLA"]}),
        okuma(3, crew={"Müzik Yönetmeni": ["CAN ATİLLA"]}),
    ])
    kayit = m["teknik_ekip"]["Müzik Yönetmeni"]["CAN ATİLLA"]
    assert kayit == {"yazimlar": {"CAN ATİLLA": 3}, "bolumler": [1, 2, 3]}
    assert "Işık" not in m["teknik_ekip"]
    assert m["aday_havuzu"]["VEDAT KOC"]["alan"] == "Işık"


# -------------------------------------------------------- N=2 / N=1 kenarları

def test_n2_esikler_2of2_aktif_zayif_uye_yok():
    m = kur([
        okuma(1, cast=["EMRE DAG", "FERIDE SEN"], crew={"Yönetmen": ["SAMET POLAT"]}),
        okuma(2, cast=["EMRE DAG"], crew={"Yönetmen": ["SAMET POLAT"]}),
    ])
    assert m["oyuncular"]["EMRE DAG"]["durum"] == "AKTIF"
    assert "FERIDE SEN" not in m["oyuncular"]  # N=2'de ZAYIF_UYE YOK → aday
    assert m["aday_havuzu"]["FERIDE SEN"]["alan"] == "oyuncular"
    assert all(o["durum"] != "ZAYIF_UYE" for o in m["oyuncular"].values())
    assert m["alanlar"]["Yönetmen"]["guven"] == "KESIN"


def test_n2_tek_tanik_tekil_alan_kbsiz_yazilmaz():
    m = kur([
        okuma(1, crew={"Kurgu": ["ISMAIL KARA"]}),
        okuma(2),
    ])
    assert "Kurgu" not in m["alanlar"]
    assert m["aday_havuzu"]["ISMAIL KARA"]["alan"] == "Kurgu"


def test_n1_hepsi_girer_tek_tanik_guveniyle():
    m = kur([
        okuma(5, cast=["EMRE DAG", "FERIDE SEN"],
              crew={"Yönetmen": ["SAMET POLAT"], "Işık": ["VEDAT KOC"]}),
    ])
    assert m["alanlar"]["Yönetmen"]["guven"] == "TEK_TANIK"
    assert m["alanlar"]["Yönetmen"]["kanonik"] == ["SAMET POLAT"]
    assert m["oyuncular"]["EMRE DAG"]["durum"] == "AKTIF"
    assert m["oyuncular"]["EMRE DAG"]["sira"] == 0
    assert m["oyuncular"]["FERIDE SEN"]["sira"] == 1
    assert m["teknik_ekip"]["Işık"]["VEDAT KOC"]["bolumler"] == [5]
    assert m["aday_havuzu"] == {}
    assert m["durum"] == "BUILDING"
    assert m["kilit_bolumler"] == [5]


# ----------------------------------------------------------- master gövdesi

def test_kur_master_govde_alanlari():
    m = kur([
        okuma(1, cast=["POLAT ALEMDAR"]),
        okuma(2, cast=["POLAT ALEMDAR"]),
        okuma(3, cast=["POLAT ALEMDAR"]),
    ])
    assert m["surum_sema"] == 1
    assert m["seri_anahtar"] == "BIZIM_DIZI_deadbeef"
    assert m["seri_adi"] == "BİZİM DİZİ"
    assert m["kaynak_klasor"] == "D:\\GELEN\\BİZİM DİZİ"
    assert m["trt_on_ekler"] == ["1900-0138-0"]
    assert m["durum"] == "BUILDING"           # kilidi ÇAĞIRAN basar
    assert m["master_surum"] == 1
    assert m["kilit_bolumler"] == [1, 2, 3]
    assert m["surum_gecmisi"] == []           # kilit olayını çağıran ekler
    assert m["bekleyen_degisimler"] == []
    assert m["format_kopusu"] == {"ardisik": 0, "ilk_bolum": None}
    assert m["tanik_kayitlari"] == {}         # content_hash IO'su çağıranın işi
    assert m["guncelleme"] == {
        "ts": "2026-07-09T12:00:00", "modul": "seri_konsensus", "bolum": 3}


def test_kur_master_bolum_sirasina_gore_calisir():
    # okumalar karışık gelse de bölüm-no sırasıyla işlenir (sira + ilk-görülme kararlı)
    m = kur([
        okuma(3, cast=["BULENT KAYA", "AYSEL TERZI"]),
        okuma(1, cast=["AYSEL TERZI", "BULENT KAYA"]),
        okuma(2, cast=["AYSEL TERZI", "BULENT KAYA"]),
    ])
    assert m["kilit_bolumler"] == [1, 2, 3]
    assert m["oyuncular"]["AYSEL TERZI"]["sira"] == 0
    assert m["oyuncular"]["BULENT KAYA"]["sira"] == 1
