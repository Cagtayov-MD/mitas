"""KARDEŞ GENİŞLETME — Kobe'nin dedup'ladığı kareler kaynaktan geri gelir.

TARİHÇE (üç adım, üçü de ölçülmüş):

1. 2026-08-20 sabah — Kobe alt bantta yazan kareleri "altyazı" sanıp
   eliyordu, oyuncu isimleri kayboluyordu. İçeriğe bakacak şekilde
   düzeltildi; kareler `recall_altbant` sınıfıyla havuza girmeye başladı.

2. Aynı gün — o kareler LeBron'a girince master çöktü (6087→449 px), bu
   yüzden LeBron tarafına bir SÜZGEÇ konuldu: alt-bant kareleri
   birleştirmeden çıkarılıyordu. Bedeli ölçüldü: Çiçek Taksi b2 girişinde
   17 ismin 8'i (kadronun yarısı) master'a hiç girmiyordu.

3. Aynı gün akşam — asıl sebep bulundu ve süzgeç KALDIRILDI. Çöküş
   alt-bant karelerinden değil, AKILLI BIÇAK'tan geliyordu: bıçak
   "jenerik kaymanın başladığı yerde başlar" varsayıp duran oyuncu
   kartlarını çöp footage sayıp kesiyordu.

BUGÜNKÜ SÖZLEŞME: kare atılmaz, dedup'ın yok ettiği kardeşler kaynaktan
GERİ GETİRİLİR; genişletme yapıldıysa bıçak susar.
    bıçak açık   → 119 kare / 13 segment /  3.921 px /  0 isim
    bıçak kapalı → 250 kare / 53 segment / 15.596 px / 16 isim
"""
import json
import sys
from pathlib import Path

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE / "src"))

from yukleyici import (ardisik_aralik_mi, genisletildi_mi, kareler,
                       temsil_sayilari)  # noqa: E402


def _kur(tmp_path, havuz_adlari, kaynak_adlari, kayitlar):
    kaynak = tmp_path / "kaynak"
    havuz = tmp_path / "havuz"
    kaynak.mkdir()
    havuz.mkdir()
    for a in kaynak_adlari:
        (kaynak / a).write_bytes(b"x")
    for a in havuz_adlari:
        (havuz / a).write_bytes(b"x")
    (havuz / "_sinif.json").write_text(
        json.dumps({"kaynak": str(kaynak), "kareler": kayitlar},
                   ensure_ascii=False), encoding="utf-8")
    return havuz


def test_kardesler_kaynaktan_yuklenir(tmp_path):
    """Havuzda 1 kare var; manifesto 3 kardeş diyor → 3 kare yüklenir."""
    d = _kur(tmp_path, ["g_0030.png"],
             ["g_0030.png", "g_0031.png", "g_0032.png"],
             {"g_0030.png": {"sinif": "recall_altbant", "temsil_kare": 3,
                             "temsil": ["g_0030.png", "g_0031.png",
                                        "g_0032.png"]}})
    assert [p.name for p in kareler(d)] == ["g_0030.png", "g_0031.png",
                                            "g_0032.png"]


def test_alt_bant_ARTIK_ELENMEZ(tmp_path):
    """Süzgeç kalktı: alt-bant karesi de havuzda kalır."""
    d = _kur(tmp_path, ["g_0030.png"], ["g_0030.png"],
             {"g_0030.png": {"sinif": "recall_altbant", "temsil_kare": 1,
                             "temsil": ["g_0030.png"]}})
    assert [p.name for p in kareler(d)] == ["g_0030.png"]


def test_kardes_tavani_asilmaz(tmp_path):
    """8 kardeş varsa hepsi degil, KARDES_TAVANI kadari yuklenir."""
    kaynak = [f"g_{n:04d}.png" for n in range(30, 38)]
    d = _kur(tmp_path, ["g_0030.png"], kaynak,
             {"g_0030.png": {"sinif": "icerik", "temsil_kare": 8,
                             "temsil": kaynak}})
    from yukleyici import KARDES_TAVANI
    assert len(kareler(d)) == KARDES_TAVANI


def test_genisletme_bayragi(tmp_path):
    """Bicak bu bayraga bakip susar."""
    d = _kur(tmp_path, ["g_0030.png"], ["g_0030.png", "g_0031.png"],
             {"g_0030.png": {"sinif": "icerik", "temsil_kare": 2,
                             "temsil": ["g_0030.png", "g_0031.png"]}})
    assert genisletildi_mi(d) is True


def test_tek_kardeste_genisletme_YOK(tmp_path):
    """Her kart tek kareyse genisletme olmamistir; bicak calismaya devam."""
    d = _kur(tmp_path, ["g_0030.png"], ["g_0030.png"],
             {"g_0030.png": {"sinif": "icerik", "temsil_kare": 1,
                             "temsil": ["g_0030.png"]}})
    assert genisletildi_mi(d) is False


def test_manifesto_yoksa_ESKI_davranis(tmp_path):
    """Geriye uyum: manifestosuz havuzda hicbir sey degismez."""
    d = tmp_path / "havuz"
    d.mkdir()
    for a in ("g_0027.png", "g_0030.png"):
        (d / a).write_bytes(b"x")
    assert [p.name for p in kareler(d)] == ["g_0027.png", "g_0030.png"]
    assert genisletildi_mi(d) is False


def test_kaynak_erisilemezse_havuzla_yetinir(tmp_path):
    """Kaynak silinmisse kule DURMAZ — elindeki havuzla calisir."""
    d = _kur(tmp_path, ["g_0030.png"], [],
             {"g_0030.png": {"sinif": "icerik", "temsil_kare": 3,
                             "temsil": ["g_0030.png", "g_0031.png",
                                        "g_0032.png"]}})
    import shutil
    shutil.rmtree(tmp_path / "kaynak")
    assert [p.name for p in kareler(d)] == ["g_0030.png"]


def test_temsil_sayilari_okunur(tmp_path):
    d = _kur(tmp_path, ["g_0030.png"], ["g_0030.png"],
             {"g_0030.png": {"sinif": "icerik", "temsil_kare": 5,
                             "temsil": ["g_0030.png"]}})
    assert temsil_sayilari(d)["g_0030.png"] == 5


def test_ardisik_aralik_bayragi_ve_sirasi(tmp_path):
    """Yeni Kobe sözleşmesi: aradaki kare silinmez, doğal sıra korunur."""
    d = tmp_path / "ardisik"
    d.mkdir()
    for a in ("g_0003.png", "g_0001.png", "g_0002.png"):
        (d / a).write_bytes(b"x")
    (d / "_sinif.json").write_text(
        json.dumps({"surum": 1, "mod": "ardisik_aralik",
                    "kaynak": "/ham/giris", "ilk_kare": 1,
                    "son_kare": 3, "kareler": {}}),
        encoding="utf-8")

    assert ardisik_aralik_mi(d) is True
    assert genisletildi_mi(d) is False
    assert [p.name for p in kareler(d)] == ["g_0001.png", "g_0002.png",
                                            "g_0003.png"]


def test_eski_manifesto_ardisik_sayilmaz(tmp_path):
    d = _kur(tmp_path, ["g_0030.png"], ["g_0030.png"],
             {"g_0030.png": {"sinif": "icerik", "temsil_kare": 1,
                             "temsil": ["g_0030.png"]}})
    assert ardisik_aralik_mi(d) is False
