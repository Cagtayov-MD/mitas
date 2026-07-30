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
