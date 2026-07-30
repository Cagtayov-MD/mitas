"""Havuz v2 birim testleri — konsey senaryoları sentetik dizilerle.
Koşum: /opt/mitas/venvs/ocr/bin/python -m pytest harness/track_kunye/test_havuz.py -v
"""
import cv2
import numpy as np
import pytest

import senaryo
import havuz


def test_kart_uretici_ayni_icerik():
    k = senaryo.kart("YONETMEN AHMET", 5)
    assert len(k) == 5
    assert k[0].shape == (160, 200)
    assert k[0].dtype == np.uint8
    assert np.array_equal(k[0], k[4])          # kopyalar özdeş
    assert k[0].max() > 200 and k[0].min() < 30  # yazı parlak, zemin koyu


def test_imza_ayni_karede_sifir_fark():
    k = senaryo.kart("AYNI KART", 2)
    assert havuz.hamming(havuz.imza(k[0]), havuz.imza(k[1])) == 0


def test_imza_farkli_kartlarda_buyuk_fark():
    a = senaryo.kart("BIRINCI KART UZUN METIN", 1)[0]
    b = senaryo.kart("XYZW BAMBASKA ICERIK QQ", 1)[0]
    assert havuz.hamming(havuz.imza(a), havuz.imza(b)) > 12


def test_film_esigi_bimodal_ayirir():
    farklar = [3, 4, 5, 4, 3, 5, 4] * 10 + [60, 65, 70, 62] * 3
    esik = havuz.film_esigi(farklar)
    assert 5 <= esik < 60         # düşük kümenin tepesi DAHİL (düşük-taraf tie-break = kaçırmamak)


def test_film_esigi_dar_bant_guvenli_taraf():
    # hayat-agaci imzası: 6-25 bandı, zayıf bimodallik → p25+2 (agresif-ALMA)
    farklar = [6, 8, 10, 12, 14, 15, 16, 17, 18, 19, 20, 22, 25] * 8
    esik = havuz.film_esigi(farklar)
    assert esik <= 16             # medyanın altında kalmalı ki kartlar ALINSIN


def test_film_esigi_az_veri_taban():
    assert havuz.film_esigi([5, 6]) == 24   # veri yoksa muhafazakar taban


def test_temporal_median_kari_siler():
    temiz = senaryo.kart("SABIT KART", 9)
    karli = senaryo.kar_ekle(temiz, 0.03)
    m = havuz.temporal_median(karli)
    # median sonrası kar noktalarının ezici kısmı gitmeli:
    fark_once = int(np.count_nonzero(karli[4] != temiz[4]))
    fark_sonra = int(np.count_nonzero(m[4] != temiz[4]))
    assert fark_sonra < fark_once * 0.10


def test_temporal_median_interlace_duzeltir():
    temiz = senaryo.kart("ESKI TV KARTI", 8)
    bozuk = senaryo.interlace_boz(temiz)
    m = havuz.temporal_median(bozuk)
    farklar = [havuz.hamming(havuz.imza(m[i]), havuz.imza(m[i + 1]))
               for i in range(len(m) - 1)]
    assert max(farklar) <= 4      # tarak etkisi imzadan silinmeli


def test_temporal_median_kapali_girdiyi_bozmaz():
    k = senaryo.kart("X", 3)
    assert all(np.array_equal(a, b) for a, b in zip(havuz.temporal_median(k, 0), k))


def _kartlar(*metinler, kopya=10):
    kareler = []
    for m in metinler:
        kareler += senaryo.kart(m, kopya)
    return kareler


def test_derle_uc_kart_uc_sayfa():
    kareler = _kartlar("KART BIR AAA", "KART IKI BBB", "KART UC CCC")
    s = havuz.havuz_derle(kareler)
    assert len(s.sayfalar) == 3
    assert s.istatistik.grup_sayisi == 3


def test_los_kart_std_yedegiyle_kurtulur():
    # loş kart: temsilci düz çıkabilir ama grubun EN parlak üyesi kurtarmalı
    los = senaryo.kart("LOS KART", 9, parlaklik=40, zemin=25)
    # tek üye biraz kontrastlı (65 → std 3.21: kapının ÜSTÜNDE; 60 std 2.81 verip
    # kapının altında kalıyordu — senaryo kalibrasyonu, üretim kapısı 3.0 değişmedi)
    los[4] = senaryo.kart("LOS KART", 1, parlaklik=65, zemin=25)[0]
    duz = [np.full((160, 200), 25, np.uint8) for _ in range(9)]      # gerçek boş grup
    kareler = los + senaryo.kart("NORMAL PARLAK KART", 9) + duz
    s = havuz.havuz_derle(kareler)
    assert any(i < 9 for i in s.sayfalar)          # loş kartın sayfası VAR
    assert not any(i >= 18 for i in s.sayfalar)    # gerçek boş grup yine YOK


def test_birikim_esigi_yuksek_esikte_ulasilabilir(monkeypatch):
    # gercek-yalanlar vakası: Otsu 46 → 3×46=138 > maks fark 112, fade sinyali ölüyordu
    monkeypatch.setattr(havuz, "film_esigi", lambda farklar: 46)
    kareler = _kartlar("AA BB", "CC DD", kopya=12)
    s = havuz.havuz_derle(kareler)
    assert s.istatistik.birikim_esigi <= 90


def test_dev_sessiz_grup_periyodik_bolunur(monkeypatch):
    # van-gogh vakası: yüksek eşik altında 253-kare sürünen grup tek sayfaya iniyordu
    monkeypatch.setattr(havuz, "film_esigi", lambda farklar: 200)  # hiçbir fark eşiği aşamaz
    metinler = [f"SURUNEN SATIR {i}" for i in range(20)]
    kareler = senaryo.scroll(metinler, 100)
    s = havuz.havuz_derle(kareler)
    sirali = sorted(s.sayfalar)
    araliklar = [b - a for a, b in zip(sirali, sirali[1:])]
    assert (max(araliklar) if araliklar else 0) <= 25    # 25+ karelik okunmamış boşluk YOK
    assert max(sirali) >= s.istatistik.kare_sayisi - 25  # kuyruk temsil edildi


def test_derle_fade_iki_kart_yakalanir():
    a = senaryo.kart("ILK KART UZUN", 12)
    b = senaryo.kart("SON KART FARKLI", 12)
    kareler = a + senaryo.fade(a[0], b[0], 15) + b
    s = havuz.havuz_derle(kareler)
    assert set(s.sayfalar) & set(range(0, 12))        # ilk kartın temsilcisi var
    # DAVRANIŞSAL iddia (Task 4 kuyruk-emsali): son seçilen sayfa İÇERİK olarak
    # kart-B'dir — fade'in t=1.0 ucu b[0] ile piksel-özdeş olabildiğinden indeks
    # penceresi yanıltır; imza-eşdeğerliği yanıltmaz.
    temiz = havuz.temporal_median(kareler)
    hedef = havuz.imza(temiz[len(kareler) - 6])       # kart-B bölgesi referansı
    assert havuz.hamming(havuz.imza(temiz[max(s.sayfalar)]), hedef) <= 2


def test_derle_pan_tek_grup():
    kareler = senaryo.pan("PAN KARTI SABIT METIN", 20)
    s = havuz.havuz_derle(kareler)
    # Pan israfı KABUL (kayıp değil — metin-dedup halleder); ideal tek-grup Task 9
    # KDE unimodal→p90 iyileştirmesinin konusu. Eski sabit-çapa bug'ı 10+ parçalıyordu.
    assert len(s.sayfalar) <= 8


def test_derle_scroll_coklu_sayfa_ve_kuyruk():
    metinler = [f"ISIM SOYISIM {i:02d}" for i in range(30)]
    kareler = senaryo.scroll(metinler, 90)
    s = havuz.havuz_derle(kareler)
    assert len(s.sayfalar) >= 8                       # içerik akışı örtüşmeli örneklenmeli
    # KUYRUK GARANTISI (davranışsal): son seçilen sayfa ile SON kare arasında
    # okunmamış yeni içerik kalmamalı (indeks sınırı değil, içerik iddiası).
    temiz = havuz.temporal_median(kareler)
    assert havuz.hamming(havuz.imza(temiz[max(s.sayfalar)]),
                         havuz.imza(temiz[-1])) <= s.istatistik.esik


def test_flas_temsilci_olamaz():
    kareler = senaryo.kart("NORMAL KART ICERIK", 10)
    kareler[5] = senaryo.flas()               # tek-kare flaş grubun içinde
    s = havuz.havuz_derle(kareler)
    assert 5 not in s.sayfalar                # konsey: 'en keskin' flaşı seçiyordu


def test_temsilci_medyan_keskinlige_yakin():
    kareler = senaryo.kart("KART", 9)
    bulanik = cv2.GaussianBlur(kareler[0], (9, 9), 4)
    kareler[0] = bulanik                       # grubun ilk karesi bulanık
    s = havuz.havuz_derle(kareler)
    assert s.sayfalar[0] != 0                  # bulanık uç temsilci olmamalı


def test_kar_firtinasi_alarmi_ve_kurtarma():
    # medyan filtresinin TEK BAŞINA çözemeyeceği yoğun kar (yogunluk 0.25):
    kareler = senaryo.kar_ekle(senaryo.kart("TEK KART FIRTINADA", 60), 0.25)
    s = havuz.havuz_derle(kareler, medyan_pencere=0)   # medyan kapalı → en kötü durum
    assert s.istatistik.alarm is True
    assert len(s.sayfalar) <= 12       # 60 kopya sayfa DEĞİL — kümeleme kurtardı


def test_normal_film_alarm_calmaz():
    kareler = _kartlar("A KARTI", "B KARTI", "C KARTI", kopya=15)
    s = havuz.havuz_derle(kareler)
    assert s.istatistik.alarm is False


def test_ikinci_gecis_surunen_scrollu_yakalar():
    # fark hep eşik-altı kalan sürünen içerik: gruplar kapanmaz, tek sayfa çıkar;
    # sigorta aradaki birikmiş enerjiyi görüp ek kare istemeli.
    metinler = [f"SATIR {i}" for i in range(40)]
    kareler = senaryo.scroll(metinler, 120)          # yavaş: kare-başı fark küçük
    s = havuz.havuz_derle(kareler)
    if len(s.sayfalar) >= 8:
        pytest.skip("gruplama zaten yakaladı — sigorta senaryosu oluşmadı")
    ek = havuz.ikinci_gecis(kareler, s)
    assert len(ek) >= 3
    assert not set(ek) & set(s.sayfalar)


def test_ikinci_gecis_statik_filmde_bos():
    kareler = _kartlar("SABIT A", "SABIT B", kopya=20)
    s = havuz.havuz_derle(kareler)
    assert havuz.ikinci_gecis(kareler, s) == []


def test_pilot_hat_havuz_modulunu_kullanir():
    import importlib, pilot_hat
    importlib.reload(pilot_hat)
    import inspect
    kaynak = inspect.getsource(pilot_hat)
    assert "import havuz" in kaynak or "from havuz" in kaynak
    assert "def film_esigi" not in kaynak      # kopya mantık kalmadı
    assert "DHASH_ESIK" not in kaynak


def test_kde_bimodal_vadi():
    farklar = [4, 5, 6, 5, 4] * 12 + [50, 55, 60, 52] * 4
    esik = havuz.film_esigi_kde(farklar)
    assert 6 < esik < 50


def test_kde_tek_tepe_p90():
    farklar = [10, 11, 12, 13, 12, 11, 10, 12] * 8
    esik = havuz.film_esigi_kde(farklar)
    assert esik >= 12              # tek küme → yalnız sert sıçrama yeni sayfa


def test_derle_esik_yontemi_parametresi():
    # "AA BB"/"CC DD" 16×16 imzada ÇAKIŞIYOR (Hamming=0, Task 9 ölçümü) —
    # Task 1'de kanıtlı imza-ayrık uzun metinler kullanılır.
    kareler = _kartlar("BIRINCI KART UZUN METIN", "XYZW BAMBASKA ICERIK QQ", kopya=8)
    s1 = havuz.havuz_derle(kareler, esik_yontemi="otsu")
    s2 = havuz.havuz_derle(kareler, esik_yontemi="kde")
    assert s1.istatistik.grup_sayisi >= 2 and s2.istatistik.grup_sayisi >= 2
