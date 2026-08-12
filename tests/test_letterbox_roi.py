# -*- coding: utf-8 -*-
"""Letterbox ROI tespiti — film-geneli örnekleme.

KÖK VAKA (2026-08-11, YANLIŞ SUÇLU 1999-0406-1-0000-00-1): ROI TEK kareden
(ilk okunabilir kare) hesaplanıyordu. Giriş jeneriği neredeyse her filmde
siyahtan açıldığı için ilk kare kapkara → "aktif alan 8 piksel" sanıldı →
8 piksellik cetvelle ölçülen her yazı SUB_FRAC=0.82 eşiğinin altında kaldı →
360 karenin 360'ı "altyazı" sayılıp elendi → havuz boş → master üretilmedi.
623 filmin 102'si etkilenmişti (16'sı komple sıfır, 86'sı sessizce eksik).

DERS: letterbox filmin GEOMETRİK sabitidir; tek karenin karanlığı ise İÇERİKTİR.
Bir satır ancak film genelinden örneklenen KARELERİN HEPSİNDE siyahsa banttır.
"""
import os
import sys

import numpy as np
import pytest

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_KOK, "scripts"))

from _letterbox_roi import letterbox_roi_from_frames, ornek_kare_indisleri


def _kare(H=480, W=600, bant_ust=0, bant_alt=0, parlaklik=200):
    """Sentetik kare: üst/alt siyah bant + ortada parlak içerik."""
    img = np.zeros((H, W, 3), dtype=np.uint8)
    img[bant_ust:H - bant_alt, :, :] = parlaklik
    return img


def test_ilk_kare_siyah_olsa_bile_tam_kare_doner():
    """KÖK VAKA: fade-in ilk karesi ROI'yi çökertmemeli."""
    kareler = [_kare(parlaklik=3)] + [_kare() for _ in range(9)]
    y0, y1, kaynak = letterbox_roi_from_frames(kareler)
    assert (y0, y1) == (0, 480), f"tam kare beklenirdi, {kaynak} verdi ({y0},{y1})"


def test_gercek_letterbox_bulunur():
    """Bant TÜM karelerde varsa tespit edilmeli (RAGNAROK deseni: 60/60)."""
    kareler = [_kare(bant_ust=60, bant_alt=60) for _ in range(10)]
    y0, y1, _ = letterbox_roi_from_frames(kareler)
    assert (y0, y1) == (60, 420)


def test_bant_sadece_bazi_karelerde_ise_bant_degildir():
    """Karanlık SAHNE bant değildir — tek karede siyah olan satır elenmez."""
    kareler = [_kare(bant_ust=60, bant_alt=60) for _ in range(9)] + [_kare()]
    y0, y1, _ = letterbox_roi_from_frames(kareler)
    assert (y0, y1) == (0, 480)


def test_sacma_roi_reddedilir_tam_kareye_dusulur():
    """Aktif alan resmin yarısından küçükse ROI güvenilmezdir → tam kare."""
    kareler = [_kare(bant_ust=0, bant_alt=472) for _ in range(10)]   # aktif 8px
    y0, y1, kaynak = letterbox_roi_from_frames(kareler)
    assert (y0, y1) == (0, 480)
    assert "sacma" in kaynak


def test_hepsi_siyah_tam_kare_doner():
    kareler = [_kare(parlaklik=2) for _ in range(10)]
    y0, y1, _ = letterbox_roi_from_frames(kareler)
    assert (y0, y1) == (0, 480)


def test_yetersiz_ornek_tam_kare_doner():
    """3'ten az okunabilir kare → tahmin etme, tam kareye düş."""
    y0, y1, kaynak = letterbox_roi_from_frames([_kare(bant_ust=60, bant_alt=60)])
    assert (y0, y1) == (0, 480)
    assert "yetersiz" in kaynak


def test_okunamayan_kareler_atlanir():
    kareler = [None, _kare(bant_ust=60, bant_alt=60), None] + \
              [_kare(bant_ust=60, bant_alt=60) for _ in range(3)]
    y0, y1, _ = letterbox_roi_from_frames(kareler)
    assert (y0, y1) == (60, 420)


def test_ihmal_edilebilir_bant_yok_sayilir():
    """1-2 piksellik kenar gürültüsü ölçüyü kaydırmamalı."""
    kareler = [_kare(bant_ust=2, bant_alt=1) for _ in range(10)]
    y0, y1, _ = letterbox_roi_from_frames(kareler)
    assert (y0, y1) == (0, 480)


def test_farkli_boyutlu_kareler_karisirsa_tam_kareye_dusulur():
    kareler = [_kare(H=480) for _ in range(5)] + [_kare(H=288) for _ in range(5)]
    y0, y1, kaynak = letterbox_roi_from_frames(kareler)
    assert "karisik" in kaynak


@pytest.mark.parametrize("n,sample,beklenen", [
    (360, 10, 10),
    (7, 10, 7),
    (1, 10, 1),
    (0, 10, 0),
])
def test_ornekleme_film_geneline_yayilir(n, sample, beklenen):
    idx = ornek_kare_indisleri(n, sample)
    assert len(idx) == beklenen
    assert len(set(idx)) == beklenen, "aynı kare iki kez örneklenmemeli"
    if n:
        assert idx[0] == 0 and idx[-1] == n - 1, "ilk ve son kare kapsanmalı"
        assert all(0 <= i < n for i in idx)
