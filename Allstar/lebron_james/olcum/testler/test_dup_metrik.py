"""M1 — dup_metrik.olc() için sentetik birim testleri.

Plandaki 5 vaka (docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md, Görev M1 madde 5):
  a) temiz sahte-künye -> dup_oran ~ 0
  b) aynı görüntünün alt alta 2 kopyası -> ~0.5
  c) %30'u tekrarlanmış -> ~0.3
  d) boş-siyah geniş bantlı temiz -> ~0 (doku kapısı kanıtı)
  e) tek satır/blok tekrarı (rol başlığı simülasyonu) -> 0 (blok şartı kanıtı)

Görüntüler kod içinde PIL/numpy ile üretilir (rastgele konumlu beyaz
metin-benzeri satır blokları siyah zeminde), sabit seed ile determinist.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dup_metrik import olc  # noqa: E402

GENISLIK = 460
SATIR_H = 20
SATIR_ARA = 55


def _satir_deseni(rng: np.random.Generator, h: int, w: int, hucre_w: int = 6) -> np.ndarray:
    """Siyah zemin üzerinde beyaz 'harf-benzeri' bloklu, rng'ye özgü bir satır deseni."""
    n_hucre = max(4, w // hucre_w)
    desen = (rng.random(n_hucre) > 0.45).astype(np.uint8) * 255
    satir = np.repeat(desen, hucre_w)
    if satir.shape[0] < w:
        satir = np.pad(satir, (0, w - satir.shape[0]))
    else:
        satir = satir[:w]
    blok = np.tile(satir, (h, 1)).astype(np.uint8)
    return blok


def _kunye_tuval(
    genislik: int,
    yukseklik: int,
    rng: np.random.Generator,
    satir_h: int = SATIR_H,
    satir_ara: int = SATIR_ARA,
    doluluk: float = 0.85,
) -> np.ndarray:
    """Rastgele konumlu/genişlikte metin-benzeri satır bloklarından oluşan
    sahte-künye tuvali (siyah zemin, beyaz 'satırlar')."""
    tuval = np.zeros((yukseklik, genislik), dtype=np.uint8)
    y = 10
    while y + satir_h <= yukseklik:
        if rng.random() < doluluk:
            satir_genislik = int(rng.integers(genislik // 3, genislik - 20))
            x0 = int(rng.integers(5, max(6, genislik - satir_genislik - 5)))
            tuval[y : y + satir_h, x0 : x0 + satir_genislik] = _satir_deseni(rng, satir_h, satir_genislik)
        y += satir_ara
    return tuval


def _png_yaz(tmp_path: Path, arr: np.ndarray, ad: str) -> Path:
    p = tmp_path / ad
    Image.fromarray(arr, mode="L").save(p)
    return p


# --------------------------------------------------------------------------- #
# (a) temiz sahte-künye -> dup_oran ~ 0
# --------------------------------------------------------------------------- #


def test_a_temiz_dup_oran_sifira_yakin(tmp_path):
    rng = np.random.default_rng(1)
    tuval = _kunye_tuval(GENISLIK, 1400, rng)
    p = _png_yaz(tmp_path, tuval, "a_temiz.png")

    sonuc = olc(str(p), satir_yuksekligi=SATIR_H)

    assert sonuc["dup_oran"] < 0.05, sonuc
    assert sonuc["boy"] == [GENISLIK, 1400]


# --------------------------------------------------------------------------- #
# (b) aynı görüntünün alt alta 2 kopyası -> ~0.5
# --------------------------------------------------------------------------- #


def test_b_iki_kopya_dup_oran_yarim(tmp_path):
    rng = np.random.default_rng(2)
    taban = _kunye_tuval(GENISLIK, 900, rng)
    tuval = np.vstack([taban, taban])
    p = _png_yaz(tmp_path, tuval, "b_iki_kopya.png")

    sonuc = olc(str(p), satir_yuksekligi=SATIR_H)

    assert 0.4 <= sonuc["dup_oran"] <= 0.6, sonuc
    assert sonuc["blok_sayisi"] >= 1, sonuc


# --------------------------------------------------------------------------- #
# (c) %30'u tekrarlanmış -> ~0.3
# --------------------------------------------------------------------------- #


def test_c_otuz_yuzde_tekrar(tmp_path):
    rng = np.random.default_rng(3)
    h = 1000
    tuval = _kunye_tuval(GENISLIK, h, rng, doluluk=0.95)
    # [100:400) bloğunu [650:950) üzerine kopyala (kaynak != hedef, uzak, %30 boy)
    kaynak = tuval[100:400].copy()
    tuval[650:950] = kaynak
    p = _png_yaz(tmp_path, tuval, "c_otuzyuzde.png")

    sonuc = olc(str(p), satir_yuksekligi=SATIR_H)

    assert 0.15 <= sonuc["dup_oran"] <= 0.45, sonuc


# --------------------------------------------------------------------------- #
# (d) boş-siyah geniş bantlı temiz -> ~0 (doku kapısı kanıtı)
# --------------------------------------------------------------------------- #


def test_d_bos_bantli_doku_kapisi(tmp_path):
    rng = np.random.default_rng(4)
    h = 2000
    tuval = np.zeros((h, GENISLIK), dtype=np.uint8)
    # birbirinden bağımsız, TEKRARSIZ, birkaç adet benzersiz satır bloğu;
    # aralarında geniş siyah (dokusuz) bantlar var.
    for y0 in (50, 500, 1000, 1500):
        satir_genislik = int(rng.integers(GENISLIK // 3, GENISLIK - 20))
        x0 = int(rng.integers(5, max(6, GENISLIK - satir_genislik - 5)))
        tuval[y0 : y0 + SATIR_H, x0 : x0 + satir_genislik] = _satir_deseni(rng, SATIR_H, satir_genislik)
    p = _png_yaz(tmp_path, tuval, "d_bosbant.png")

    sonuc = olc(str(p), satir_yuksekligi=SATIR_H)

    assert sonuc["dup_oran"] < 0.05, sonuc
    assert sonuc["doku_kapsami"] < 0.25, sonuc


# --------------------------------------------------------------------------- #
# (e) tek satır/blok tekrarı (rol başlığı simülasyonu) -> 0 (blok şartı kanıtı)
# --------------------------------------------------------------------------- #


def test_e_tek_serit_tekrari_blok_sayilmaz(tmp_path):
    rng = np.random.default_rng(5)
    h = 1200
    tuval = _kunye_tuval(GENISLIK, h, rng, doluluk=0.9)

    # "rol başlığı" simülasyonu: TEK bir şerit (serit_h = 2*SATIR_H) yüksekliğinde
    # aynı içerik, adım (adim=SATIR_H) ızgarasına hizalı iki UZAK konuma yerleştirilir.
    # Aradaki/çevredeki içerik (tuval'in geri kalanı) birbirinden bağımsız rastgele
    # olduğundan, komşu (örtüşen) şeritler eşleşmez -> yalnız TEK şerit eşleşir ->
    # blok şartı (>=2 ardışık) bunu reddetmeli.
    baslik_rng = np.random.default_rng(99)
    baslik = _satir_deseni(baslik_rng, SATIR_H * 2, GENISLIK - 40)
    y1, y2 = 200, 800  # SATIR_H (adim) ızgarasına hizalı, birbirinden uzak
    tuval[y1 : y1 + SATIR_H * 2, 20 : GENISLIK - 20] = baslik
    tuval[y2 : y2 + SATIR_H * 2, 20 : GENISLIK - 20] = baslik
    p = _png_yaz(tmp_path, tuval, "e_teksatir.png")

    sonuc = olc(str(p), satir_yuksekligi=SATIR_H)

    assert sonuc["dup_oran"] == 0.0, sonuc
    assert sonuc["blok_sayisi"] == 0, sonuc


# --------------------------------------------------------------------------- #
# (f) M10: periyodik noktalı-lider listesi (her satır AYNI nokta deseni, isim
#     alanı farklı) -> periyodik-doku muafiyeti devreye girer, dup ~ 0.
#     Karşıt-kanıt: gerçek iki-kopya (test b) hala ~0.5 ölçülüyor -- muafiyet
#     yalnız YOĞUN delta-kümesi imzasında çalışır, ayrık tekrara dokunmaz.
# --------------------------------------------------------------------------- #


def test_f_periyodik_noktali_liste_muafiyeti(tmp_path):
    rng = np.random.default_rng(7)
    h = 1400
    tuval = np.zeros((h, GENISLIK), dtype=np.uint8)
    # her SATIR_ARA'da: solda kısa benzersiz 'isim' bloğu + genis SABİT
    # noktalı-lider deseni (satırdan satıra AYNI -- periyodik doku kaynağı)
    nokta = np.zeros((SATIR_H, GENISLIK - 160), dtype=np.uint8)
    nokta[SATIR_H // 2 - 1 : SATIR_H // 2 + 1, ::12] = 255  # nokta dizisi
    y = 10
    while y + SATIR_H <= h:
        isim_w = int(rng.integers(40, 120))
        tuval[y : y + SATIR_H, 10 : 10 + isim_w] = _satir_deseni(rng, SATIR_H, isim_w)
        tuval[y : y + SATIR_H, 140 : 140 + nokta.shape[1]] = nokta
        y += SATIR_ARA
    p = _png_yaz(tmp_path, tuval, "f_noktali.png")

    sonuc = olc(str(p), satir_yuksekligi=SATIR_H)

    assert sonuc["dup_oran"] < 0.10, sonuc
    assert sonuc["periyodik_dusulen_eslesme"] >= 0  # alan raporlanıyor
