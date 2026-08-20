"""Okuyucu testleri — modelsiz. Süzgeçler ve sayaçlar kodda mı?"""
from pathlib import Path

import pytest

import okuyucu


def _s(*adlar):
    return [Path(a) for a in adlar]


# ── gevezelik süzgeci (YAZ TATİLİ 1963-0035 vakası) ──────────────────────────

@pytest.mark.parametrize("satir", [
    "Caption: a film still",
    "Markdown-style Summary:",
    "Here is the extracted text",
    "OCR Result:",
    "No recognizable text in this image",
    "The image shows a dark screen",
    "[图片中没有可识别的文字内容]",
    "福",                                  # tek karakter CJK gurultusu
])
def test_gevezelik_elenir(satir):
    assert okuyucu.gevezelik_mi(satir)


@pytest.mark.parametrize("satir", [
    "YONETMEN AHMET",
    "客串演出",                             # gercek CJK jenerik — KORUNUR
    "导演",
    "MUSIC BY JOHN WILLIAMS",
    "GORUNTU YONETMENI: MEHMET",
    "(c) 1985 TRT",
])
def test_gercek_jenerik_korunur(satir):
    assert not okuyucu.gevezelik_mi(satir)


def test_gevezelik_bos_satirda_false():
    assert not okuyucu.gevezelik_mi("") and not okuyucu.gevezelik_mi("   ")


# ── okuma akışı ──────────────────────────────────────────────────────────────

def test_dedup_ardisik_sayfada_tekrari_atar():
    cevaplar = {"a.png": "YONETMEN AHMET\nKURGU AYSE",
                "b.png": "YONETMEN AHMET\nMUZIK VELI"}
    k, _ = okuyucu.oku(_s("a.png", "b.png"), lambda p: cevaplar[p.name])
    assert [x["text"] for x in k] == ["YONETMEN AHMET", "KURGU AYSE", "MUZIK VELI"]


def test_dedup_yalniz_onceki_sayfaya_bakar():
    """Uzak tekrar KORUNUR — jenerikte aynı isim gerçekten iki kez geçebilir."""
    cevaplar = {"a.png": "AHMET", "b.png": "BASKA SATIR", "c.png": "AHMET"}
    k, _ = okuyucu.oku(_s("a.png", "b.png", "c.png"), lambda p: cevaplar[p.name])
    assert [x["text"] for x in k] == ["AHMET", "BASKA SATIR", "AHMET"]


def test_markdown_susleri_soyulur():
    k, _ = okuyucu.oku(_s("a.png"), lambda p: "## **YONETMEN AHMET** \n`KURGU`")
    assert [x["text"] for x in k] == ["YONETMEN AHMET", "KURGU"]


def test_gevezelik_sayilir_ve_atilir():
    k, kanit = okuyucu.oku(_s("a.png"),
                           lambda p: "Caption: x\nYONETMEN AHMET\nsummary: y")
    assert [x["text"] for x in k] == ["YONETMEN AHMET"]
    assert kanit["elenen_n"] == 2


def test_duzyazi_betimleme_elenir_ama_kanitta_kalir():
    """Gercek kosuda cikti (CIGERPAREM, 2026-08-14): model Ozbekce jenerigin
    ortasina 500 karakterlik Ingilizce sahne betimlemesi yazdi ve ilk surum
    sizdirdi. Duzyazi fiil imzasi yakalar; satir YOK EDILMEZ, kanita duser."""
    betim = ("A man and a woman are standing close to each other, with the "
             "woman's hand around the man's arm. The image is a photograph.")
    k, kanit = okuyucu.oku(_s("a.png"), lambda p: betim + "\nYODGOR SA DIYEV")
    assert [x["text"] for x in k] == ["YODGOR SA DIYEV"]
    assert kanit["elenme_sebepleri"] == {"duzyazi_fiil": 1}
    assert kanit["elenen"][0]["text"].startswith("A man and a woman")


def test_madde_imli_gercek_isimler_KORUNUR():
    """KERMİT BATAKLIKTA / cikis_0384 (sadakat sondaji, 2026-08-14): Muppet
    Workshop kunyesi ekranda GERCEKTEN madde imli. Uretimden alinan
    'jenerikte madde imi olmaz' kurali o karede 14 GERCEK ismi eliyordu."""
    ham = "- **Heather Asch\n- ROLLIE KREWSON\n• Polly Smith"
    k, kanit = okuyucu.oku(_s("a.png"), lambda p: ham)
    assert [x["text"] for x in k] == ["Heather Asch", "ROLLIE KREWSON", "Polly Smith"]
    assert kanit["elenen_n"] == 0


def test_madde_imi_soyulur_kalan_icerik_kurallardan_gecer():
    """Im soyulur ama satir muaf DEGIL: kalan icerik duzyazi ise yine elenir."""
    k, kanit = okuyucu.oku(
        _s("a.png"), lambda p: "- The image shows a river\n- AHMET VELI")
    assert [x["text"] for x in k] == ["AHMET VELI"]
    assert kanit["elenen_n"] == 1


def test_harfsiz_liste_numarasi_elenir():
    k, kanit = okuyucu.oku(_s("a.png"), lambda p: "- 12\n- 34\nMUZIK VELI")
    assert [x["text"] for x in k] == ["MUZIK VELI"]


def test_garble_deseni_elenir():
    k, kanit = okuyucu.oku(_s("a.png"), lambda p: "AHMET VELI AHMET VELI\nKURGU")
    assert kanit["elenme_sebepleri"].get("garble_desen") == 1


def test_sayfa_hatasi_sayilir_sessiz_degil():
    """Bugün üretimde patlayan sayfa `continue` ile SESSİZCE atlanıyor."""
    def sor(p):
        if p.name == "b.png":
            raise TimeoutError("model cevap vermedi")
        return "SATIR " + p.stem
    k, kanit = okuyucu.oku(_s("a.png", "b.png", "c.png"), sor)
    assert kanit["sayfa_hata_n"] == 1
    assert kanit["sayfa_basarili_n"] == 2
    assert kanit["sayfa_hatalari"][0]["kaynak"] == "b.png"
    assert len(k) == 2


def test_model_yok_istisnasi_yutulmaz():
    with pytest.raises(okuyucu.ModelYok):
        okuyucu.oku(_s("a.png"), lambda _p: (_ for _ in ()).throw(
            okuyucu.ModelYok("model yok")))


def test_bellek_istisnasi_yutulmaz():
    """OOM sayfa hatası değildir — yukarı sızmalı, ARIZA(BELLEK) olmalı."""
    def sor(p):
        raise okuyucu.Bellek("CUDA out of memory")
    with pytest.raises(okuyucu.Bellek):
        okuyucu.oku(_s("a.png"), sor)


def test_kaynak_ve_sira_kaydedilir():
    k, _ = okuyucu.oku(_s("kare_007.png"), lambda p: "BIR\nIKI")
    assert k[0] == {"kaynak": "kare_007.png", "sayfa_sira": 1,
                    "satir_sira": 0, "text": "BIR"}
    assert k[1]["satir_sira"] == 1


def test_cok_kisa_satir_atilir():
    k, _ = okuyucu.oku(_s("a.png"), lambda p: "A\n-\nGERCEK SATIR")
    assert [x["text"] for x in k] == ["GERCEK SATIR"]


# ── sağlık (garble dedektörü) ────────────────────────────────────────────────

def test_saglik_bos():
    assert okuyucu.saglik([]) == (False, "bos_cikti")


def test_saglik_cok_kisa():
    assert okuyucu.saglik(["kisa"])[1] == "cok_kisa"


def test_saglik_garble():
    ok, sebep = okuyucu.saglik(["!@#$%^&*()" * 40])
    assert not ok and sebep == "garble_yuksek"


def test_saglik_iyi_cikti():
    assert okuyucu.saglik(["YONETMEN AHMET MEHMET " * 20]) == (True, "ok")


def test_saglik_esikleri_ayardan_okur():
    assert okuyucu.saglik(["kisa ama yeter"], {"min_uzunluk": 5})[0] is True
