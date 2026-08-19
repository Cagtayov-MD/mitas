"""Okuyucu — bantlama, süzgeçler, piksel kalkanı. Hepsi GPU'suz.

Buradaki her süzgeç gerçek bir üretim kazasından geldi; testler o kazaları
kilitler. `sor` bir geri-çağrı olduğu için model olmadan koşulur.
"""
from pathlib import Path

import pytest

from okuyucu import (BANT_H, BINDIRME, MIN_BANT_H, Bellek, ModelYok, OkumaCoktu,
                     bant_sinirlari, fold_tr, garble_mi, gevezelik_mi, oku,
                     satirlari_ayikla, yapisal_veto)


# --- bantlama ---------------------------------------------------------------
def test_bant_geometrisi_uretimden():
    """1100/120 uydurma DEĞİL — _pipe_hibrit_okuma.py:59'dan."""
    assert (BANT_H, BINDIRME, MIN_BANT_H) == (1100, 120, 40)


def test_tek_bant():
    assert bant_sinirlari(800) == [0]


def test_bindirmeli_ilerleme():
    """Adım = 1100 - 120 = 980."""
    assert bant_sinirlari(3000) == [0, 980, 1960]


def test_kisa_son_bant_atilir():
    """<40 px kalan artık okunmaz — kol_master:305'teki kural."""
    o = bant_sinirlari(1100 + 980 - 120 + 10)   # son parça çok kısa
    assert all(o[i + 1] - o[i] == 980 for i in range(len(o) - 1))
    assert o[-1] + MIN_BANT_H <= 1100 + 980 - 120 + 10


def test_sifir_yukseklik():
    assert bant_sinirlari(0) == []


def test_bantlar_master_i_kapsar():
    """Hiçbir piksel iki bandın arasında kaybolmamalı."""
    H = 7508
    o = bant_sinirlari(H)
    assert o[0] == 0
    for i in range(len(o) - 1):
        assert o[i] + BANT_H > o[i + 1], "bantlar arasinda bosluk var"
    assert o[-1] + BANT_H >= H, "master'in sonu okunmuyor"


# --- satır ayıklama ---------------------------------------------------------
def test_markdown_isaretleri_soyulur():
    assert satirlari_ayikla("**YÖNETMEN**\n`ali veli`\n# BAŞLIK") == [
        "YÖNETMEN", "ali veli", "BAŞLIK"]


def test_tek_karakter_atilir():
    assert satirlari_ayikla("a\nAB") == ["AB"]


# --- gevezelik --------------------------------------------------------------
@pytest.mark.parametrize("s", [
    "[图片中没有可识别的文字内容]",
    "No recognizable text found",
    "Caption: the credits roll",
    "Here is the extracted text",
    "福",
])
def test_gevezelik_yakalanir(s):
    assert gevezelik_mi(s) is True


@pytest.mark.parametrize("s", ["客串演出", "导演", "YÖNETMEN: ALİ", "LEE MARVIN"])
def test_gercek_jenerik_korunur(s):
    """MUHAFAZAKÂR olmak zorunda: gerçek künyeyi atmak en pahalı hata."""
    assert gevezelik_mi(s) is False


# --- yapısal veto -----------------------------------------------------------
@pytest.mark.parametrize("s,sebep", [
    ("(kamera yavaşça kayıyor)", "anlatim_parantez"),
    ("**kalın**", "markdown"),
    ("<td>Category</td>", "html_artefakt"),
    ("- 1", "harfsiz"),
    ("There is a man walking", "duzyazi_fiil"),
])
def test_veto_sebepleri(s, sebep):
    assert yapisal_veto(s) == sebep


def test_temiz_satir_gecer():
    assert yapisal_veto("MÜZİK: NEDİM OTYAM") is None


def test_garble_cift_basim():
    """Slit çift-basımı: master yanlış hizalanınca aynı dizi iki kez basılır."""
    assert garble_mi("LEE MARVIN LEE MARVIN") is True
    assert garble_mi("LEE MARVIN") is False


def test_fold_tr_turkce():
    assert fold_tr("İSTANBUL Ağrı") == "istanbul agri"


# --- oku() ------------------------------------------------------------------
def _yollar(tmp_path, n):
    out = []
    for i in range(n):
        p = tmp_path / f"bant_{i:03d}.png"
        p.write_bytes(b"x")
        out.append(p)
    return out


def test_okuma_ve_dedup(tmp_path):
    """Bantlar 120 px örtüşür → sınırdaki satır iki bantta da okunur, bir kez girer."""
    y = _yollar(tmp_path, 2)
    cevaplar = {y[0].name: "LEE MARVIN\nGARY GRIMES",
                y[1].name: "GARY GRIMES\nRON HOWARD"}
    r = oku(y, lambda p: cevaplar[p.name], lambda p: 5)
    assert r["satirlar"] == ["LEE MARVIN", "GARY GRIMES", "RON HOWARD"]


def test_piksel_kalkani_sifir_kutu(tmp_path):
    """Kutu 0 iken satır ŞÜPHELİDİR — damgalanır, ama SİLİNMEZ.

    2026-07-31'de bu satırlar atılıyordu (deepseek boş bantta '- 1' listesi
    uyduruyor — gerçek ve ölçülmüş bulgu). 2026-08-20'de kalkanın GERÇEK
    içeriği de yediği ölçüldü: İZ PEŞİNDE girişinde derleyici 88 kareyi
    595 px'e çökertti, model o masterdan GÜLER KARAMAN'ı okudu, kalkan onu
    uydurma sayıp sildi ve kule METIN_YOK yazdı — bir DERLEME ARIZASI
    "bu jenerikte yazı yoktu" cevabına dönüştü.

    Yeni sözleşme (Çağatay 2026-08-20): kaybetmek uydurmaktan kötüdür.
    Satır çıktıda kalır, `piksel_kanitsiz` damgası taşır, aşağı akıştaki
    güven katmanı düşük tartar. Kalkanın ASIL işi — şüpheyi görünür kılmak —
    korunuyor; değişen tek şey şüphelinin idam yerine işaretlenmesi.

    Not: 31 Temmuz'un asıl şikâyeti olan '- 1' / '- 2' listesi zaten
    `yapisal_veto` tarafından eleniyor — piksel kalkanı o desen için
    GEREKSİZDİ. Geriye yalnız isim-benzeri satır kalıyor ve o damgalanıyor.
    """
    y = _yollar(tmp_path, 1)
    r = oku(y, lambda p: "- 1\n- 2\nHAYALET İSİM", lambda p: 0)
    assert r["satirlar"] == ["HAYALET İSİM"]          # '- 1'/'- 2' yapisal veto
    assert r["piksel_kanitsiz_n"] == 1
    assert all(k["piksel_kanitsiz"] for k in r["satir_kaynaklari"])


def test_kutu_none_ise_hukum_verilmez(tmp_path):
    """None = 'ölçemedik'. 0 ile karışırsa sağlam satırlar atılır."""
    y = _yollar(tmp_path, 1)
    r = oku(y, lambda p: "LEE MARVIN", lambda p: None)
    assert r["satirlar"] == ["LEE MARVIN"]
    assert r["kutu_durum"] == "kismi"


def test_kalkan_yoksa_raporlanir(tmp_path):
    """Motor yoksa kalkan SESSİZCE düşmez — künyede görünür."""
    y = _yollar(tmp_path, 1)
    r = oku(y, lambda p: "LEE MARVIN", None)
    assert r["kutu_durum"] == "yok"


def test_tek_bant_hatasi_okumayi_durdurmaz(tmp_path):
    y = _yollar(tmp_path, 3)

    def sor(p):
        if p.name == "bant_001.png":
            raise RuntimeError("bant patladi")
        return f"SATIR {p.name}"
    r = oku(y, sor, lambda p: 5)
    assert len(r["satirlar"]) == 2
    assert r["hata_n"] == 1


def test_HEPSI_patlarsa_metin_yok_DEGIL(tmp_path):
    """GERÇEK KAZA (2026-08-15, ilk uçtan uca koşu).

    CUDA kütüphane çarpışması yüzünden 3 bandın 3'ü de patladı. Hatalar tek tek
    sayılıp yutuldu, satır listesi boş kaldı ve kule `METIN_YOK` dedi — yani
    "bu jenerikte yazı yok". YALAN: yazı vardı, biz okuyamadık.

    Sözleşmenin yasakladığı tam şey buydu: ARIZA sessizce içerik gerçeğine
    dönüştü. Bu test o kapıyı kilitler.
    """
    y = _yollar(tmp_path, 3)

    def sor(p):
        raise RuntimeError("nvrtc: failed to open libnvrtc-builtins.so.13.0")
    with pytest.raises(OkumaCoktu) as e:
        oku(y, sor, lambda p: 5)
    assert "3/3" in str(e.value)
    assert "nvrtc" in str(e.value), "ilk hatanin sebebi kunyeye tasinmali"


def test_bant_yoksa_cokme_sayilmaz(tmp_path):
    """Boş bant listesi hata değildir — bölünecek master yoktu."""
    r = oku([], lambda p: "X", lambda p: 5)
    assert r["satirlar"] == [] and r["hata_n"] == 0


def test_model_hatasi_YUKARI_ATILIR(tmp_path):
    """ModelYok/Bellek yutulmaz: 'metin yok' sanılmamalı, ARIZA olmalı."""
    y = _yollar(tmp_path, 2)

    def sor(p):
        raise Bellek("CUDA OOM")
    with pytest.raises(Bellek):
        oku(y, sor, lambda p: 5)

    def sor2(p):
        raise ModelYok("model yok")
    with pytest.raises(ModelYok):
        oku(y, sor2, lambda p: 5)


def test_elenen_yok_edilmez(tmp_path):
    """Yanlış eleme yapıyorsak GÖRÜNÜR olsun."""
    y = _yollar(tmp_path, 1)
    r = oku(y, lambda p: "LEE MARVIN\nCaption: credits\nThere is a man", lambda p: 5)
    assert r["satirlar"] == ["LEE MARVIN"]
    sebepler = {e["sebep"] for e in r["elenen"]}
    assert sebepler == {"gevezelik", "duzyazi_fiil"}
