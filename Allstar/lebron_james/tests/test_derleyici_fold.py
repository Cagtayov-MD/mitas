"""LEBRON Sınıf-A fold-dedup + Sınıf-B substrat yarışması — GPU'suz testler.

SINIF-A (2026-08-18, Çağatay onayı "tekrar da istenmez"): segment kapanırken
içerik-kapsamasına bakılır — token'ları önceki segmentlerde zaten varsa
segment saygı duyulan tekrar DEĞİL okuma gürültüsüdür, düşürülür; kanıtı
manifest'e yazılır.

SINIF-B: "çok scroll bulan kazanır" dy-tutarlılığıyla kırılır — sobel
bazen DAHA FAZLA ama dağınık scroll bulur (altin-adam: 0.30→0.01).
"""
import sys
from pathlib import Path

import numpy as np

KULE = Path(__file__).resolve().parents[1]
for p in (KULE / "aday", KULE / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from derleyici import (scroll_duzlugu, substrat_karari, segment_dusur,
                   SEG_KAPSAMA_DUSUR, SEG_ORNEKLEM)


def _im(isaret: int) -> np.ndarray:
    """İşaret pikseli gömülü sahte kare — token_fonk bunu okur."""
    im = np.zeros((40, 60, 3), dtype=np.uint8)
    im[0, 0] = isaret
    return im


# --------------------------------------------------------------------------- #
# SINIF-B: scroll_duzlugu + substrat_karari
# --------------------------------------------------------------------------- #
def _cift(sinif, dy):
    return {"sinif": sinif, "dy": dy, "resp": 0.9}


def test_scroll_duzlugu_tutarli_akis_sifira_yakin():
    c = [_cift("scroll", d) for d in (20.0, 20.0, 21.0, 20.0, 19.5, 20.5)]
    assert scroll_duzlugu(c) <= 0.05


def test_scroll_duzlugu_daginik_olcum_yuksek():
    c = [_cift("scroll", d) for d in (4.0, 60.0, 2.5, 90.0, 7.0, 33.0)]
    assert scroll_duzlugu(c) >= 0.5


def test_scroll_duzlugu_az_kanit_none():
    assert scroll_duzlugu([_cift("scroll", 20.0), _cift("scroll", 21.0)]) is None


def test_substrat_daginik_sobel_cok_scroll_bulsa_bile_kaybeder():
    """ALTIN-ADAM dersi: sobel daha ÇOK scroll buldu ama dy'ler dağınık —
    kesmeleri scroll sanıyordu. Fenerin az ama tutarlı ölçümü kazanır."""
    fener = [_cift("scroll", 18.0), _cift("scroll", 19.0), _cift("scroll", 18.5),
             _cift("duraksama", 0.0)] * 3
    sobel = [_cift("scroll", d) for d in (3.0, 55.0, 4.0, 80.0, 2.0, 40.0, 6.0)]
    assert substrat_karari(fener, sobel) == "fener"


def test_substrat_tutarli_sobel_kazanir():
    """JETGİLLER dersi: sobel çok VE tutarlı scroll buluyorsa devralır."""
    fener = [_cift("scroll", 20.0), _cift("duraksama", 0.0)] * 4
    sobel = [_cift("scroll", 18.0 + 0.5 * i) for i in range(12)]
    assert substrat_karari(fener, sobel) == "sob"


def test_substrat_fener_hic_scroll_bulamadiysa_sobel():
    """PARTİ sınıfı: fener 0 scroll (kilitli) → sobel kurtarma."""
    fener = [_cift("duraksama", 0.0)] * 10
    sobel = [_cift("scroll", d) for d in (30.0, 32.0, 31.0, 29.0)]
    assert substrat_karari(fener, sobel) == "sob"


def test_substrat_sobel_fazla_scroll_bulmadiysa_dokunma():
    fener = [_cift("scroll", 20.0)] * 6
    sobel = [_cift("scroll", 20.0)] * 3 + [_cift("duraksama", 0.0)] * 3
    assert substrat_karari(fener, sobel) == "fener"


# --------------------------------------------------------------------------- #
# SINIF-A: segment_dusur
# --------------------------------------------------------------------------- #
def _tok_fonk(im):
    isaret = int(im[0, 0, 0])
    sozluk = {
        1: {"ALI", "AYSE", "MEHMET", "FATMA", "HASAN", "ZEYNEP"},   # kadro A
        2: {"ALI", "AYSE", "MEHMET", "FATMA", "HASAN", "ZEYNEP"},   # kadro A tekrar
        3: {"ALI", "AYSE", "MEHMET", "FATMA", "HASAN", "ZEYNEP",    # devam listesi
            "OSMAN", "ELIF"},                                        # (2 yeni isim)
        4: {"LOGO"},                                                  # az token
    }
    return set(sozluk.get(isaret, set()))


def _seg(isaret, kare=1):
    return ([_im(isaret) for _ in range(kare)], [0.0] * kare)


def test_tam_kapsamli_tekrar_segment_dusulur():
    segler = [_seg(1, 4), _seg(2, 4)]  # aynı kadro, iki segment
    kalan, dus = segment_dusur(segler, _tok_fonk)
    assert len(kalan) == 1
    assert len(dus) == 1 and dus[0]["kapsama"] == 1.0 and dus[0]["kare"] == 4


def test_devam_listesi_yeni_isinle_dusulmez():
    """Kapsama 6/8 = 0.75 < 0.80 → 'CONTINUED' listesi yeni isim taşıyor,
    düşürülemez (gerçek içerik)."""
    segler = [_seg(1, 4), _seg(3, 4)]
    kalan, dus = segment_dusur(segler, _tok_fonk)
    assert len(kalan) == 2 and not dus


def test_az_tokenlu_segment_asla_dusulmez():
    segler = [_seg(1, 4), _seg(4, 2)]  # logo: 1 token → kanıt yetersiz
    kalan, dus = segment_dusur(segler, _tok_fonk)
    assert len(kalan) == 2 and not dus


def test_hepsi_duserse_ilk_korunur():
    segler = [_seg(2, 2), _seg(2, 2), _seg(2, 2)]
    kalan, dus = segment_dusur(segler, _tok_fonk)
    assert len(kalan) == 1 and len(dus) == 2


def test_ornekleme_uzun_segmenti_sinirlar():
    """Çok kareli segmentte token çağrısı ≤ SEG_ORNEKLEM — scroll panoraması
    için maliyet sınırlı kalır."""
    cagrilar = []

    def tok(im):
        cagrilar.append(1)
        return {"A", "B", "C", "D"}

    segler = [([_im(1)] * 40, [0.0] * 40), _seg(2, 1)]
    segment_dusur(segler, tok)
    assert len(cagrilar) <= SEG_ORNEKLEM + 1


def test_esik_siniri_kapsamasi():
    """Kapsama 6/7 ≈ 0.857: varsayılan eşikte (0.80) düşer, 0.90 eşikte kalır."""
    sozluk = dict(_sozluk_6_7())

    def tok(im):
        return set(sozluk[int(im[0, 0, 0])])

    kalan, dus = segment_dusur([_seg(1, 2), _seg(5, 2)], tok)
    assert len(kalan) == 1 and dus and abs(dus[0]["kapsama"] - 0.857) < 0.01
    kalan2, dus2 = segment_dusur([_seg(1, 2), _seg(5, 2)], tok, esik=0.90)
    assert len(kalan2) == 2 and not dus2


def _sozluk_6_7():
    taban = {"ALI", "AYSE", "MEHMET", "FATMA", "HASAN", "ZEYNEP"}
    return {1: set(taban), 5: set(taban) | {"YENI"}}
