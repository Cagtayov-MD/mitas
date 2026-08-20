"""Kırpım-keskinleştirme (crop-sharpen) kapısı — 2026-08-19 Çiçek Taksi.

Ölçüm: kutu kırpımı 2× lanczos + unsharp(5x5,1.0) ile tanımaya girmesi
ham havuzda 25→26/29 kişi (ÜMİT YESİN düzeldi), zarar sıfır. Kare-seviyesi
ölçekleme iki kulüde de zarar veriyor — yalnız kırpım seviyesi geçerli.
"""
import numpy as np

import metin_worker
from metin_secici import worker_komutu


def test_kirpim_keskinlestir_boyutu_ikiye_katlar_ve_uint8_kalir():
    im = np.random.default_rng(7).integers(0, 255, (28, 96, 3)).astype("uint8")
    out = metin_worker.kirpim_keskinlestir(im)
    assert out.shape == (56, 192, 3)
    assert out.dtype == np.uint8


def test_kirpim_keskinlestir_saf_lanczosdan_farkli_piksel_uretir():
    import cv2
    im = np.random.default_rng(3).integers(0, 255, (28, 96, 3)).astype("uint8")
    saf = cv2.resize(im, (192, 56), interpolation=cv2.INTER_LANCZOS4)
    out = metin_worker.kirpim_keskinlestir(im)
    assert not np.array_equal(out, saf)


def test_worker_komutu_bayrak_acikken_eklenir_kapaliyken_eklenmez():
    taban = dict(model="PP-OCRv6_medium_det", rec_model="latin_PP-OCRv5_mobile_rec")
    acik = worker_komutu("/p", "/w", "/in.json", "/out.json",
                         {**taban, "kirpim_keskinlestir": True})
    kapali = worker_komutu("/p", "/w", "/in.json", "/out.json", taban)
    assert "--kirpim-keskinlestir" in acik
    assert "--kirpim-keskinlestir" not in kapali
