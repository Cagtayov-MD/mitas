"""LEBRON Sobel yedek yolu — iki tetik (GPU'suz).

1. FILM düzeyi: el-feneri maskesi kareyi dolduruyorsa (kapsama > 0.25 —
   parlak zemin sınıfı, parti) ölçüm Sobel kenar-maskeli griye geçer;
   korelasyon statik parlak zemine kilitlenmekten kurtulur.
2. KARE düzeyi: OCR istisnası anında lebron kaba threshold(180)'e düşüyordu;
   LeBron Sobel'e düşer. (Kapalıysa taban davranış aynen korunur.)
"""
import sys
from pathlib import Path

import numpy as np

KULE = Path(__file__).resolve().parents[1]
for p in (KULE / "aday", KULE / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from derleyici import (derle, el_feneri_govde, sobel_metin_maskesi,
                   MASKE_KAPSAMA_ESIK)


# --------------------------------------------------------------------------- #
# sobel_metin_maskesi — saf
# --------------------------------------------------------------------------- #
def test_duz_parlak_alanin_gradyani_yok():
    """Düz parlak zemin (gökyüzü/duvar) kenar üretmez → maske boş.
    Parlaklık eşiği burada YOZLAŞIYORDU; gradyan yozlaşmaz."""
    gri = np.full((120, 160), 220, dtype=np.uint8)
    m = sobel_metin_maskesi(gri)
    assert int(m.sum()) == 0


def test_yazi_kenarlari_maskede_kalir():
    gri = np.zeros((120, 160), dtype=np.uint8)
    gri[40:46, 20:140] = 255  # parlak 'satır'
    m = sobel_metin_maskesi(gri)
    assert int(m.sum()) > 0
    # maske satır banda yakın: bandın üstü/altı kenarında yoğunlaşır
    prof = m.sum(axis=1)
    assert prof[36:50].sum() >= 0.9 * prof.sum()


# --------------------------------------------------------------------------- #
# kare düzeyi — OCR patlaması
# --------------------------------------------------------------------------- #
def _patlayan_predict(img):
    raise RuntimeError("sahte OCR patlamasi")


def _gradyan_gri(h=100, w=140):
    """100..200 arası düz rampa: threshold(180) ile Sobel maskeleri FARKLI
    çıktılar verir — hangi yola düştüğü ölçülebilir olsun."""
    return np.tile(np.linspace(100, 200, w, dtype=np.uint8), (h, 1))


def _bgr(gri):
    import cv2
    return cv2.cvtColor(gri, cv2.COLOR_GRAY2BGR)


def test_ocr_patlayinca_sobel_threshold_degil():
    img = _bgr(_gradyan_gri())
    gri = img[:, :, 0]  # gri kopya (BGR'den gri == rampa)
    sonuc = el_feneri_govde(img, _patlayan_predict, sobel_acik=True)
    beklenen = np.where(sobel_metin_maskesi(gri) > 0, gri, 0)
    assert np.array_equal(sonuc, beklenen)
    # lebron'un kaba fallback'ine DÜŞMEMİŞ olmalı:
    _, thr = None, None
    import cv2
    _, thr_mask = cv2.threshold(gri, 180, 255, cv2.THRESH_BINARY)
    thr = cv2.bitwise_and(gri, gri, mask=thr_mask)
    assert not np.array_equal(sonuc, thr)


def test_sobel_kapaliyken_lebron_threshold_davranisi_korunur():
    img = _bgr(_gradyan_gri())
    gri = img[:, :, 0]
    sonuc = el_feneri_govde(img, _patlayan_predict, sobel_acik=False)
    import cv2
    _, thr_mask = cv2.threshold(gri, 180, 255, cv2.THRESH_BINARY)
    beklenen = cv2.bitwise_and(gri, gri, mask=cv2.dilate(thr_mask, np.ones((5, 5), np.uint8), iterations=2))
    assert np.array_equal(sonuc, beklenen)


# --------------------------------------------------------------------------- #
# film düzeyi — kapsama anahtarı (KARAR PARLAKLIKTAN, acemiler dersi)
# --------------------------------------------------------------------------- #
def _yoz_el_fenerisi(img, _idx):
    """Maske kareyi dolduruyor gibi görünen el-feneri (kapsama=1.0)."""
    import cv2
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _dar_el_fenerisi(img, _idx):
    import cv2
    gri = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return np.where(gri > 110, gri, 0).astype(np.uint8)


def _bos_tokenler(img, _idx):
    return set()


def _scroll_film(n=10, arka=30, bant=235):
    """Kenarlı bant kaydırma filmi. arka=30 → karanlık zemin (parlaklık
    kapsaması düşük); arka=210 + koyu bant → parlak zemin sınıfı (parti)."""
    rng = np.random.default_rng(7)
    ims = []
    for i in range(n):
        gri = arka + rng.integers(-3, 4, (240, 320)).astype(np.uint8)
        y0 = 180 - 15 * i
        gri[y0:y0 + 8, 40:280] = bant
        ims.append(_bgr(gri))
    return ims


def test_kilitli_fener_sobel_kurtarmasi_parlak_zeminde_calisir():
    """HAREKET-ÖNCELİKLİ anahtar (totoro dersi): sobel yalnız KURTARMA'dır.
    Fener HİÇ hareket bulamıyorsa (kilitli — statik zemin döndürüyor) VE
    parlaklık kapsaması yozsa sobel denenir; sobel hareketi bulursa devralır."""
    ims = _scroll_film(arka=210, bant=20)

    def _kilitli_fener(img, _idx):
        # OCR'ın statik parlak zemine kilitlenmesi: her karede AYNI (hareketsiz)
        # görüntü döndürsün — korelasyon dy=0 der, scroll bulunamaz
        return np.full(img.shape[:2], 210, dtype=np.uint8)

    master, man = derle("sobel-kurtarma", ims=ims, flashlight=_kilitli_fener,
                        token_saglayici=_bos_tokenler)
    assert man["olcum_yolu"] == "sobel", man["olcum_yolu"]
    assert man["sobel_kurtarma"] is True
    assert master is not None


def test_kurtarma_da_hareket_bulamazsa_fener_korunur():
    """Sobel de hiçbir şey bulamıyorsa substrat değişmenin anlamı yok —
    fener yolu korunur, yanlış güven ile sobel'e geçilmez."""
    ims = _scroll_film(arka=210, bant=20)
    ims = [np.full_like(im, 205) for im in ims]  # HİÇ hareket yok (statik film)

    def _kilitli_fener(img, _idx):
        return np.full(img.shape[:2], 205, dtype=np.uint8)

    _, man = derle("kurtarma-red", ims=ims, flashlight=_kilitli_fener,
                   token_saglayici=_bos_tokenler)
    assert man["olcum_yolu"] == "ai_flashlight"
    assert man["sobel_kurtarma"] is False


def test_acemiler_dersi_dolmus_fener_saglam_filmin_yolunu_degistirmez():
    """REGRESYON (2026-08-17, acemiler-cetesi): el-feneri maskesi sağlıklı
    filmde bile 0.2-0.5 dolabilir (dilate kutuları). Karar PARLAKLIKTAN
    verilir — karanlık zeminli sağlıklı film, dolu görünen fenerle bile
    el-feneri yolunda KALMALI. (Yanlış ölçülünce MGM kartı yutuldu,
    recall 0.857→0.753.)"""
    ims = _scroll_film(arka=30, bant=235)
    _, man = derle("acemiler-dersi", ims=ims, flashlight=_yoz_el_fenerisi,
                   token_saglayici=_bos_tokenler)
    assert man["olcum_yolu"] == "ai_flashlight", man["olcum_yolu"]
    assert man["maske_kapsama"] <= MASKE_KAPSAMA_ESIK


def test_totoro_dersi_fener_hareket_buluyorsa_parak_zeminde_de_sobel_atlanir():
    """REGRESYON (2026-08-17, komşum-totoro): parlaklık kapsaması 0.699'du,
    sobel'e geçildi, 2D korelasyon statik zemin kenarına kilitlendi —
    115 kare 'duraksama' sanıldı, master 7624→1920, recall 0.24→0.006.
    Fener hareket buluyorsa (bu testte dolu ama HAREKETLİ görüntü) sobel
    ASLA denenmez."""
    ims = _scroll_film(arka=210, bant=20)
    _, man = derle("totoro-dersi", ims=ims, flashlight=_yoz_el_fenerisi,
                   token_saglayici=_bos_tokenler)
    assert man["olcum_yolu"] == "ai_flashlight", man["olcum_yolu"]
    assert man["sobel_kurtarma"] is False


def test_karanlik_zemin_flashlight_yolunda_kalir():
    ims = _scroll_film(arka=30, bant=235)
    _, man = derle("flashlight-deneme", ims=ims, flashlight=_dar_el_fenerisi,
                   token_saglayici=_bos_tokenler)
    assert man["olcum_yolu"] == "ai_flashlight"


def test_sobel_kapaliyken_parlak_zeminde_de_israr_eder():
    """Ablasyon: sobel=False → kapsama yoz olsa bile lebron yolu (geri
    uyumluluk; kıyas koşusu farkı ölçer)."""
    ims = _scroll_film(arka=210, bant=20)
    _, man = derle("sobel-kapali", ims=ims, flashlight=_dar_el_fenerisi,
                   token_saglayici=_bos_tokenler,
                   ozellikler={"sobel": False})
    assert man["olcum_yolu"] == "ai_flashlight"
