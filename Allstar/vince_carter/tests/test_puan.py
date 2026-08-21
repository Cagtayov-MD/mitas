"""olcum/puan.py testleri — Türkçe casefold, diakritik katlama, boşluk
varyantı, KAYIP/FAZLA sayımı, sınıf bazlı rapor, fark dökümü sebep sayaçları.

Puanlayıcı ölçüm aletidir: yanlış ölçen alet, yanlış motoru "iyileşme" diye
onaylar. Bu yüzden aletin kendisi teste tabidir.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "olcum"))

import puan  # noqa: E402
from puan import (  # noqa: E402
    Satir,
    bosluksuz,
    diakritik_katla,
    fark_dokumu,
    hizala,
    metrikler,
    normalize,
    puanla,
    satirlari_oku,
    sinif_raporu,
    turkce_casefold,
)


def _s(metin: str, sira: int = 0, sinif: str | None = None) -> Satir:
    return Satir(ham=metin, sira=sira, sinif=sinif)


def _liste(metinler, siniflar=None) -> list[Satir]:
    siniflar = siniflar or [None] * len(metinler)
    return [Satir(ham=m, sira=i, sinif=c)
            for i, (m, c) in enumerate(zip(metinler, siniflar))]


# --------------------------------------------------------------------------- Türkçe casefold
def test_turkce_casefold_buyuk_noktali_i():
    """'İ'.lower() Python'da 'i'+U+0307 verir — sahte karakter. Bizim tablo
    temiz 'i' vermeli."""
    assert turkce_casefold("İ") == "i"
    assert "̇" not in turkce_casefold("İSTANBUL")
    assert turkce_casefold("İSTANBUL") == "istanbul"


def test_turkce_casefold_buyuk_noktasiz_i():
    """'I'.lower() 'i' verir ama Türkçe'de 'ı' olmalı."""
    assert turkce_casefold("I") == "ı"
    assert turkce_casefold("ISPARTA") == "ısparta"


def test_turkce_casefold_str_lower_ile_ayrisir():
    """Testin varlık sebebi: str.lower() bu iki harfte YANLIŞ sonuç verir."""
    assert turkce_casefold("İI") != "İI".lower()


def test_turkce_casefold_diger_harfler_normal():
    assert turkce_casefold("ŞÜKRÜ ÖZÇĞ") == "şükrü özçğ"


def test_normalize_bosluk_kirpar_ve_teke_indirir():
    assert normalize("  YÖNETMEN   ALİ   VELİ  ") == "yönetmen ali veli"


def test_normalize_sekme_ve_karisik_bosluk():
    assert normalize("A\t\tB\n") == "a b"


# --------------------------------------------------------------------------- diakritik katlama
@pytest.mark.parametrize("a,b", [
    ("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"),
    ("ö", "o"), ("ç", "c"), ("â", "a"), ("î", "i"), ("û", "u"),
])
def test_diakritik_katlama_ciftleri(a, b):
    assert diakritik_katla(a) == diakritik_katla(b)


def test_diakritik_katlama_gercek_ornek():
    """③ İ→I çöküşü: 'ATTiLA' ile 'ATTILA' katlandığında aynı olmalı."""
    assert (diakritik_katla(normalize("ATTiLA ERGUN"))
            == diakritik_katla(normalize("ATTILA ERGUN")))


def test_diakritik_katlama_celal_kose():
    assert (diakritik_katla(normalize("celaL köse"))
            == diakritik_katla(normalize("ÇELAL KÖSE")))


# --------------------------------------------------------------------------- boşluksuz varyant (hata sınıfı ④)
def test_bosluksuz_varyant():
    assert bosluksuz("seda canpol a t") == "sedacanpolat"


def test_bosluksuz_eslesme_is_tanimindaki_ornek():
    """④ 'SEDA CANPOL A T' ↔ 'SEDA CANPOLAT' YAKIN olarak yakalanmalı."""
    gt = _liste(["SEDA CANPOLAT"])
    ck = _liste(["SEDA CANPOL A T"])
    h = hizala(gt, ck)
    assert len(h.yakin) == 1
    assert h.yakin[0][3] in ("BOSLUK", "DIAKRITIK_BOSLUK")
    assert not h.kayip and not h.fazla


# --------------------------------------------------------------------------- hizalama temelleri
def test_birebir_tam_eslesme():
    gt = _liste(["YÖNETMEN", "ALİ VELİ", "YAPIMCI"])
    ck = _liste(["YÖNETMEN", "ALİ VELİ", "YAPIMCI"])
    h = hizala(gt, ck)
    assert len(h.birebir) == 3
    assert not h.yakin and not h.kayip and not h.fazla


def test_birebir_bosluk_ve_buyuk_kucuk_harf_farkini_yutar():
    """Normalizasyon karşılaştırma içindir: bunlar BİREBİR sayılır."""
    gt = _liste(["YÖNETMEN"])
    ck = _liste(["  yönetmen  "])
    h = hizala(gt, ck)
    assert len(h.birebir) == 1


def test_kayip_sayimi():
    gt = _liste(["A", "B", "C"])
    ck = _liste(["A", "C"])
    h = hizala(gt, ck)
    assert len(h.kayip) == 1
    assert gt[h.kayip[0]].ham == "B"


def test_fazla_sayimi():
    gt = _liste(["A", "C"])
    ck = _liste(["A", "UYDURMA", "C"])
    h = hizala(gt, ck)
    assert len(h.fazla) == 1
    assert ck[h.fazla[0]].ham == "UYDURMA"


def test_bir_gt_satiri_yalniz_bir_kez_eslesir():
    """GT'de bir kez geçen satır, çıktıda iki kez geçse bile bir kez sayılır;
    ikincisi FAZLA olur (⑤ kekeleme bu şekilde görünür)."""
    gt = _liste(["ALİ VELİ"])
    ck = _liste(["ALİ VELİ", "ALİ VELİ"])
    h = hizala(gt, ck)
    assert len(h.birebir) + len(h.yakin) == 1
    assert len(h.fazla) == 1


def test_gt_tekrarli_satir_iki_kez_eslesebilir():
    """GT'de GERÇEKTEN iki kez geçen satır (ör. 'film kopya') iki kez eşleşir."""
    gt = _liste(["film kopya", "X", "film kopya"])
    ck = _liste(["film kopya", "X", "film kopya"])
    h = hizala(gt, ck)
    assert len(h.birebir) == 3
    assert not h.kayip


def test_yakin_esigin_altinda_eslesmez():
    gt = _liste(["MEHMET CANPOLAT"])
    ck = _liste(["TAMAMEN BASKA BIR SEY"])
    h = hizala(gt, ck)
    assert not h.yakin
    assert len(h.kayip) == 1 and len(h.fazla) == 1


def test_yakin_esik_parametresi_calisir():
    gt = _liste(["MEHMET CANPOLAT"])
    ck = _liste(["MEHMET CANPOLAY"])
    assert hizala(gt, ck, esik=0.90).yakin, "0.90'da yakin bekleniyordu"
    assert not hizala(gt, ck, esik=0.999).yakin, "0.999'da yakin OLMAMALI"


def test_sira_korunur_karisik_eslesme_yapmaz():
    """Hizalama sıra-korumalı: uzaktaki aynı metin serbestçe eşleşmemeli."""
    gt = _liste(["A", "B", "C", "D"])
    ck = _liste(["D", "C", "B", "A"])
    h = hizala(gt, ck)
    assert len(h.birebir) + len(h.yakin) < 4


# --------------------------------------------------------------------------- metrikler
def test_metrikler_hesabi():
    gt = _liste(["A", "B", "C", "D"])
    ck = _liste(["A", "B", "FAZLADAN"])
    h = hizala(gt, ck)
    m = metrikler(h, gt, ck)
    assert m["birebir"] == 2
    assert m["kayip"] == 2
    assert m["fazla"] == 1
    assert m["gt_toplam"] == 4
    assert m["cikti_toplam"] == 3
    assert m["kesinlik"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["duyarlilik"] == pytest.approx(2 / 4, abs=1e-4)
    assert m["f1"] == pytest.approx(2 * (2/3) * 0.5 / ((2/3) + 0.5), abs=1e-4)


def test_metrikler_tam_isabet():
    gt = _liste(["A", "B"])
    ck = _liste(["A", "B"])
    m = metrikler(hizala(gt, ck), gt, ck)
    assert m["kesinlik"] == 1.0 and m["duyarlilik"] == 1.0 and m["f1"] == 1.0


def test_metrikler_bos_cikti_tanimsiz_kesinlik():
    """Boş çıktıda kesinlik TANIMSIZ'dır — 0.0 demek yalan olur, None döner."""
    gt = _liste(["A", "B"])
    ck: list[Satir] = []
    m = metrikler(hizala(gt, ck), gt, ck)
    assert m["kesinlik"] is None
    assert m["duyarlilik"] == 0.0
    assert m["f1"] is None
    assert m["kayip"] == 2


def test_metrikler_bos_gt_tanimsiz_duyarlilik():
    gt: list[Satir] = []
    ck = _liste(["A"])
    m = metrikler(hizala(gt, ck), gt, ck)
    assert m["duyarlilik"] is None
    assert m["kesinlik"] == 0.0


# --------------------------------------------------------------------------- okuma / süzme
def test_yorum_ve_bos_satirlar_atlanir(tmp_path):
    p = tmp_path / "gt.txt"
    p.write_text("# yorum\n\nA\n\n# baska yorum\nB\n", encoding="utf-8")
    satirlar = satirlari_oku(p)
    assert [s.ham for s in satirlar] == ["A", "B"]


def test_sira_suzme_sonrasi_indeksle_ortusur(tmp_path):
    """`sira` hizalama indeksleriyle birebir örtüşmeli — atılan yorum satırı
    kadar kaymamalı (sınıf raporu bu eşitliğe dayanıyor)."""
    p = tmp_path / "gt.txt"
    p.write_text("# yorum\n# yorum2\n\nA\nB\n", encoding="utf-8")
    satirlar = satirlari_oku(p)
    assert [s.sira for s in satirlar] == [0, 1]
    assert [s.kaynak_satir for s in satirlar] == [4, 5]


def test_json_ciktisi_okunur_sinif_korunur(tmp_path):
    p = tmp_path / "vince.json"
    p.write_text(json.dumps({
        "durum": "OKUNDU",
        "satirlar": [{"metin": "A", "sinif": "KESIN"},
                     {"metin": "B", "sinif": "SUPHELI"}],
    }, ensure_ascii=False), encoding="utf-8")
    satirlar = satirlari_oku(p)
    assert [s.ham for s in satirlar] == ["A", "B"]
    assert [s.sinif for s in satirlar] == ["KESIN", "SUPHELI"]


def test_ariza_jsonu_bos_liste_verir(tmp_path):
    """ARIZA vince.json'unda satır yoktur — bu bir hata değil, ölçülebilir
    gerçektir (o koşu hiçbir satır üretmemiştir)."""
    p = tmp_path / "vince.json"
    p.write_text(json.dumps({"durum": "ARIZA", "sinif": "MODEL_HATASI",
                             "mesaj": "x"}), encoding="utf-8")
    assert satirlari_oku(p) == []


# --------------------------------------------------------------------------- sınıf bazlı rapor (konsey kararı 7)
def test_sinif_raporu_temel():
    gt = _liste(["A", "B", "C"])
    ck = _liste(["A", "B", "UYDURMA"], ["KESIN", "SUPHELI", "SUPHELI"])
    h = hizala(gt, ck)
    r = sinif_raporu(h, ck)
    assert r["KESIN"]["toplam"] == 1
    assert r["KESIN"]["gt_karsiligi_var"] == 1
    assert r["KESIN"]["dogruluk"] == 1.0
    assert r["SUPHELI"]["toplam"] == 2
    assert r["SUPHELI"]["gt_karsiligi_var"] == 1
    assert r["SUPHELI"]["dogruluk"] == 0.5


def test_sinif_raporu_supheli_gercekte_dogruydu_sorusu():
    """Konsey kararı 7'nin tam sorusu: SÜPHELİ'ye attıklarımın kaçı GERÇEKTE
    doğruydu? Hepsi doğruysa karantina recall'ı kırıyor demektir."""
    gt = _liste(["ALİ VELİ", "AYŞE FATMA"])
    ck = _liste(["ALİ VELİ", "AYŞE FATMA"], ["SUPHELI", "SUPHELI"])
    r = sinif_raporu(hizala(gt, ck), ck)
    assert r["SUPHELI"]["dogruluk"] == 1.0, "karantina 2 dogru satiri yemis"


def test_sinif_raporu_yoksa_none():
    gt = _liste(["A"])
    ck = _liste(["A"])
    assert sinif_raporu(hizala(gt, ck), ck) is None


def test_sinif_raporu_yakin_eslesmeyi_sayar():
    gt = _liste(["ATTILA ERGUN"])
    ck = _liste(["ATTiLA ERGUN"], ["ZAYIF"])
    r = sinif_raporu(hizala(gt, ck), ck)
    assert r["ZAYIF"]["yakin"] == 1
    assert r["ZAYIF"]["gt_karsiligi_var"] == 1


# --------------------------------------------------------------------------- fark dökümü
def test_fark_dokumu_kayip_hic_yok():
    gt = _liste(["TAMAMEN OKUNMAMIS SATIR"])
    ck = _liste(["ALAKASIZ"])
    d = fark_dokumu(hizala(gt, ck), gt, ck)
    assert d["sebep_sayaclari"].get("KAYIP_HIC_YOK") == 1


def test_fark_dokumu_kayip_esik_alti():
    """Çıktıda benzeri var ama eşiğin altında → 'bozuk okundu', 'hiç yok' değil."""
    gt = _liste(["MEHMET CANPOLAT"])
    ck = _liste(["MEHMET CANPOLTA X"])
    d = fark_dokumu(hizala(gt, ck), gt, ck)
    assert d["sebep_sayaclari"].get("KAYIP_ESIK_ALTI") == 1
    assert d["detay"]["kayip"][0]["en_yakin_cikti"] == "MEHMET CANPOLTA X"


def test_fark_dokumu_fazla_tekrar():
    gt = _liste(["ALİ VELİ"])
    ck = _liste(["ALİ VELİ", "ALİ VELİ"])
    d = fark_dokumu(hizala(gt, ck), gt, ck)
    assert d["sebep_sayaclari"].get("FAZLA_TEKRAR") == 1


def test_fark_dokumu_fazla_motor_notu():
    gt = _liste(["ALİ VELİ"])
    ck = _liste(["ALİ VELİ",
                 "There is no visible credit text in the provided images."])
    d = fark_dokumu(hizala(gt, ck), gt, ck)
    assert d["sebep_sayaclari"].get("FAZLA_MOTOR_NOTU") == 1


def test_fark_dokumu_fazla_uydurma_adayi():
    gt = _liste(["ALİ VELİ"])
    ck = _liste(["ALİ VELİ", "EDITH HEAD"])
    d = fark_dokumu(hizala(gt, ck), gt, ck)
    assert d["sebep_sayaclari"].get("FAZLA_UYDURMA_ADAYI") == 1


def test_fark_dokumu_fazla_gt_disi_eslesme():
    """② rol kayması adayı: metin GT'de VAR ama başka yerde — saf uydurma
    değil, hizalama/rol kayması."""
    gt = _liste(["A", "ALİ VELİ", "B", "C", "D"])
    ck = _liste(["A", "ALİ VELİ", "B", "C", "D", "ALİ VELİ"])
    d = fark_dokumu(hizala(gt, ck), gt, ck)
    sayac = d["sebep_sayaclari"]
    assert sayac.get("FAZLA_GT_DISI_ESLESME", 0) + sayac.get("FAZLA_TEKRAR", 0) == 1
    assert "FAZLA_UYDURMA_ADAYI" not in sayac


def test_fark_dokumu_yakin_sebebi_diakritik():
    gt = _liste(["ATTILA ERGUN"])
    ck = _liste(["ATTiLA ERGUN"])
    d = fark_dokumu(hizala(gt, ck), gt, ck)
    assert d["sebep_sayaclari"].get("YAKIN_DIAKRITIK") == 1


def test_fark_dokumu_yakin_sebebi_bosluk():
    gt = _liste(["SEDA CANPOLAT"])
    ck = _liste(["SEDA CANPOL A T"])
    d = fark_dokumu(hizala(gt, ck), gt, ck)
    sayac = d["sebep_sayaclari"]
    assert (sayac.get("YAKIN_BOSLUK", 0)
            + sayac.get("YAKIN_DIAKRITIK_BOSLUK", 0)) == 1


def test_fark_dokumu_ham_metni_degistirmez():
    """Normalizasyon YALNIZ karşılaştırma için — rapor HAM satırı göstermeli."""
    gt = _liste(["  YÖNETMEN   ALİ  "])
    ck = _liste(["ALAKASIZ"])
    d = fark_dokumu(hizala(gt, ck), gt, ck)
    assert d["detay"]["kayip"][0]["gt"] == "  YÖNETMEN   ALİ  "


# --------------------------------------------------------------------------- uçtan uca puanla()
def test_puanla_uctan_uca(tmp_path):
    gt = tmp_path / "gt.txt"
    gt.write_text("# yorum\nYÖNETMEN\nALİ VELİ\nAYŞE FATMA\n", encoding="utf-8")
    ck = tmp_path / "cikti.txt"
    ck.write_text("YÖNETMEN\nALI VELI\nUYDURMA\n", encoding="utf-8")
    s = puanla(gt, ck)
    m = s["metrikler"]
    assert m["gt_toplam"] == 3
    assert m["cikti_toplam"] == 3
    assert m["birebir"] == 1          # YÖNETMEN
    assert m["yakin"] == 1            # ALİ VELİ ←→ ALI VELI (diakritik)
    assert m["kayip"] == 1            # AYŞE FATMA
    assert m["fazla"] == 1            # UYDURMA
    assert "fark_dokumu" in s
    assert "sinif_raporu" not in s    # düz .txt — sınıf yok


def test_puanla_json_ciktisi_sinif_raporu_uretir(tmp_path):
    gt = tmp_path / "gt.txt"
    gt.write_text("A\nB\nC\n", encoding="utf-8")
    ck = tmp_path / "vince.json"
    ck.write_text(json.dumps({
        "durum": "OKUNDU",
        "satirlar": [{"metin": "A", "sinif": "KESIN"},
                     {"metin": "B", "sinif": "SUPHELI"},
                     {"metin": "UYDURMA", "sinif": "SUPHELI"}],
    }, ensure_ascii=False), encoding="utf-8")
    s = puanla(gt, ck)
    assert s["sinif_raporu"]["KESIN"]["dogruluk"] == 1.0
    assert s["sinif_raporu"]["SUPHELI"]["dogruluk"] == 0.5
    assert "metrikler_gorunur" in s
    # SÜPHELİ hariç: yalnız "A" kalır → 1 birebir, 0 fazla, 2 kayıp
    g = s["metrikler_gorunur"]
    assert g["cikti_toplam"] == 1
    assert g["birebir"] == 1
    assert g["fazla"] == 0
    assert g["kayip"] == 2


def test_gorunur_metrik_hesabi_asil_dokumu_bozmaz(tmp_path):
    """metrikler_gorunur hesabı `ck` nesnelerini EZMEMELİ — ezerse ardından
    gelen fark dökümü yanlış satırı raporlar."""
    gt = tmp_path / "gt.txt"
    gt.write_text("A\nB\n", encoding="utf-8")
    ck = tmp_path / "vince.json"
    ck.write_text(json.dumps({
        "durum": "OKUNDU",
        "satirlar": [{"metin": "A", "sinif": "SUPHELI"},
                     {"metin": "B", "sinif": "KESIN"},
                     {"metin": "UYDURMA", "sinif": "KESIN"}],
    }, ensure_ascii=False), encoding="utf-8")
    s = puanla(gt, ck)
    fazlalar = [o["cikti"] for o in s["fark_dokumu"]["detay"]["fazla"]]
    assert fazlalar == ["UYDURMA"]
    assert s["sinif_raporu"]["KESIN"]["toplam"] == 2
    assert s["sinif_raporu"]["SUPHELI"]["toplam"] == 1


def test_puanla_gercek_gt_yatagi_marnali():
    """Kule içindeki GERÇEK GT ile gerçek motor çıktısı — alet canlı veride
    çalışıyor mu (uydurma fikstür değil)."""
    gt = KOK / "olcum/gt/marnali/cikis.txt"
    ck = Path("/opt/mitas/Allstar/gt_dizi/marnali/cikis_referans_8b.txt")
    if not (gt.exists() and ck.exists()):
        pytest.skip("gercek GT/referans dosyasi yok")
    s = puanla(gt, ck)
    m = s["metrikler"]
    assert m["gt_toplam"] == 128
    assert m["birebir"] > 100
    assert 0.0 <= m["f1"] <= 1.0
    assert m["birebir"] + m["yakin"] + m["kayip"] == m["gt_toplam"]


def test_hizalama_toplamlari_tutarli():
    """Değişmez: birebir+yakin+kayip = gt_toplam ve birebir+yakin+fazla =
    cikti_toplam. Bu eşitlik bozulursa alet satır KAYBEDİYOR demektir."""
    gt = _liste(["A", "B", "C", "D", "E"])
    ck = _liste(["A", "X", "C", "Y", "Z"])
    h = hizala(gt, ck)
    m = metrikler(h, gt, ck)
    assert m["birebir"] + m["yakin"] + m["kayip"] == m["gt_toplam"]
    assert m["birebir"] + m["yakin"] + m["fazla"] == m["cikti_toplam"]


@pytest.mark.parametrize("gt_metinler,ck_metinler", [
    (["A"], []),
    ([], ["A"]),
    ([], []),
    (["A", "A", "A"], ["A"]),
    (["A"], ["A", "A", "A"]),
])
def test_hizalama_toplamlari_kenar_durumlarda_da_tutarli(gt_metinler, ck_metinler):
    gt, ck = _liste(gt_metinler), _liste(ck_metinler)
    m = metrikler(hizala(gt, ck), gt, ck)
    assert m["birebir"] + m["yakin"] + m["kayip"] == m["gt_toplam"]
    assert m["birebir"] + m["yakin"] + m["fazla"] == m["cikti_toplam"]


# --------------------------------------------------------------------------- yatak
def test_yatak_json_gecerli_ve_gt_dosyalari_mevcut():
    yatak = json.loads((KOK / "olcum/yatak.json").read_text(encoding="utf-8"))
    assert yatak["yuzeyler"], "yatak bos"
    for y in yatak["yuzeyler"]:
        assert {"film", "bolum", "gt", "klip"} <= y.keys()
        assert (KOK / y["gt"]).exists(), f"GT yok: {y['gt']}"
        if y["klip"] is None:
            assert y.get("not"), f"{y['film']}: klip yok ama sebep yazilmamis"


def test_yatak_dogrulanmamis_yuzey_isaretli():
    """iz_pesinde GT'si doğrulanmamış — yatakta AÇIKÇA işaretli olmalı ki
    birincil ortalamaya sessizce karışmasın."""
    yatak = json.loads((KOK / "olcum/yatak.json").read_text(encoding="utf-8"))
    belirsiz = [y for y in yatak["yuzeyler"] if not y.get("dogrulanmis", True)]
    assert belirsiz, "dogrulanmamis yuzey isaretlenmemis"
    for y in belirsiz:
        assert y.get("not"), "dogrulanmamis yuzeyin sebebi yazilmamis"
