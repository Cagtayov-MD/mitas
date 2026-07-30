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
