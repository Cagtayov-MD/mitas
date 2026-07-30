"""Havuz v2 birim testleri — konsey senaryoları sentetik dizilerle.
Koşum: /opt/mitas/venvs/ocr/bin/python -m pytest harness/track_kunye/test_havuz.py -v
"""
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
