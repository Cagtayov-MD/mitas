"""MAGIC plato mimarisi — istikrar eğrisi temsilci seçimi (GPU'suz).

ibrahimovic'in plato v4'ünün magic'e taşımasının kapısı: dissolve zincirlerinde
sayfa TEMSİLCİSİ geçiş karesi olmamalı; temsilci istikrar eğrisinin yerel
tepesindeki platonun İÇİNDEN seçilir (magic'de: plato içinde en keskin kare).

Senaryolar sentetik satır-maskeleriyle kurulur — IoU dizisi elle hesaplanabilir
olduğu için davranış kapalı biçimde doğrulanır.
"""
import sys
from pathlib import Path

import numpy as np

KULE = Path(__file__).resolve().parents[1]
for p in (KULE / "aday", KULE / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from magic import kosu_platolari, adaylar_hesapla, IZGARA_MIN_KOSU

H, W = 50, 80


def _maske(satirlar: set[int]) -> np.ndarray:
    """Verilen satır kümesi 'dolu' bir varlık maskesi (10 satır = 800 px ≥ 400)."""
    m = np.zeros((H, W), dtype=np.float32)
    for r in satirlar:
        m[r, :] = 1.0
    return m


def _aralik(bas, son):  # [bas, son] kapalı
    return set(range(bas, son + 1))


A = _aralik(0, 9)      # kart A platosu
B = _aralik(30, 39)    # derin vadi (dissolve anı)
C = _aralik(40, 49)    # kart C platosu
C1 = _aralik(5, 14)    # zayıf-tepe bölgesi: IoU(C1,C2)=6/14≈0.43
C2 = _aralik(1, 10)
D = _aralik(35, 44)
D2 = _aralik(40, 49)   # IoU(D,D2)=5/15≈0.33


def test_iki_plato_dissolve_vadisi_iki_temsilci_verir():
    """[A,A,A,B,C,C,C]: plato → vadi → plato. Temsilciler vadiden DEĞİL
    plato içinden seçilir (kucuk-dev-adam dissolve-zinciri sınıfı)."""
    varliklar = [_maske(A), _maske(A), _maske(A), _maske(B),
                 _maske(C), _maske(C), _maske(C)]
    kosu = list(range(7))
    tems = kosu_platolari(kosu, varliklar)
    assert len(tems) == 2, tems
    assert tems[0] in (0, 1, 2)      # A platosundan
    assert tems[1] in (4, 5, 6)      # C platosundan — 3 (vadi) ASLA


def test_plato_icinde_en_keskin_kare_secilir():
    """Magic farkı: ibrahimovic plato-ORTASINI alır; magic plato içinde en
    keskin kareyi — lebron'un kalite ölçütü plato sınırları içinde kalır."""
    varliklar = [_maske(A), _maske(A), _maske(A), _maske(B),
                 _maske(C), _maske(C), _maske(C)]
    keskinlik = [1.0, 5.0, 2.0, 0.0, 2.0, 9.0, 3.0]
    tems = kosu_platolari(list(range(7)), varliklar, keskinlik)
    assert tems == [1, 5], tems


def test_keskinlik_yoksa_plato_ortasi_ibrahimovic_davranisi():
    varliklar = [_maske(A), _maske(A), _maske(A), _maske(B),
                 _maske(C), _maske(C), _maske(C)]
    tems = kosu_platolari(list(range(7)), varliklar, None)
    assert tems == [1, 5], tems  # (0..2) ortası=1, (4..6) ortası=5


def test_kisa_kosu_son_kareyi_verir():
    """<3 karede tepe tanımsız → son kare (oturmuş içerik)."""
    varliklar = [_maske(A), _maske(A)]
    assert kosu_platolari([0, 1], varliklar) == [1]


def test_bos_kare_kosuyu_boler():
    """Siyah-aralıklı kartlar doğal ayrılır: maske < MIN_MASKE_PX olan kare
    koşuyu böler, iki plato iki temsilci verir."""
    varliklar = [_maske(A), _maske(A), np.zeros((H, W), np.float32),
                 _maske(C), _maske(C)]
    tems = kosu_platolari(list(range(5)), varliklar)
    assert len(tems) == 2
    assert tems[0] in (0, 1) and tems[1] in (3, 4)


def test_gecis_filtresi_zayif_tepiyi_atar():
    """[A,A,B,C1,C2,D,D2]: ortada 0.43'lük bir 'tepe' var ama PLATO_IOU
    (0.75) altı → güçlü plato VARken geçiş-karışımı temsilci OLAMAZ.
    (kucuk-dev-adam kare-20 vakası.)"""
    varliklar = [_maske(A), _maske(A), _maske(B), _maske(C1),
                 _maske(C2), _maske(D), _maske(D2)]
    tems = kosu_platolari(list(range(7)), varliklar)
    assert tems == [0], tems  # yalnız güçlü plato bölgesinin temsilcisi


def test_gecis_filtresi_guclu_tepe_yoksa_zayif_yasar():
    """Aynı zayıf tepe, güçlü plato YOKken: filtre temsilci seçimini
    inceltir, İÇERİK ATLAZMAZ — grenli soluk kartlar (karadeniz sınıfı)
    filtresiz tepelere geri düşer."""
    varliklar = [_maske(A), _maske(B), _maske(C1),
                 _maske(C2), _maske(D), _maske(D2)]
    tems = kosu_platolari(list(range(6)), varliklar)
    assert tems and all(t in (2, 3) for t in tems), tems


def test_izgara_uzun_kosuda_her_ucuncu_kareyi_ekler():
    """Token ızgara sondajı: koşu ≥ IZGARA_MIN_KOSU olunca her 3. kare de
    aday olur — düz istikrar eğrisi koca koşudan 1-2 tepe çıkarıp kart
    yutuyordu (427-koşu vakası). Adaylar token-kimliğe sorulur; karışım
    kareleri kapsama sayesinde kendiliğinden elenir."""
    varliklar = [_maske(A)] * 12  # dümdüz istikrar → tek plato
    kosu = list(range(12))
    hepsi = adaylar_hesapla(kosu, varliklar, [1.0] * 12, plato=True, izgara=True)
    yalniz_plato = adaylar_hesapla(kosu, varliklar, [1.0] * 12, plato=True, izgara=False)
    assert len(hepsi) > len(yalniz_plato)
    assert set(range(0, 12, 3)) <= set(hepsi)


def test_plato_kapaliyken_lebron_tek_keskin_kare():
    """Ablasyon: plato=False → lebron davranışı, koşunun en keskin TEK karesi."""
    varliklar = [_maske(A)] * 8
    keskinlik = [1.0, 2.0, 9.0, 3.0, 1.0, 2.0, 4.0, 1.0]
    assert adaylar_hesapla(list(range(8)), varliklar, keskinlik,
                            plato=False, izgara=True) == [2]


def test_kisa_kosuda_izgara_devreye_girmez():
    varliklar = [_maske(A)] * (IZGARA_MIN_KOSU - 1)
    kosu = list(range(IZGARA_MIN_KOSU - 1))
    hepsi = adaylar_hesapla(kosu, varliklar, [1.0] * len(kosu), plato=True, izgara=True)
    yalniz = adaylar_hesapla(kosu, varliklar, [1.0] * len(kosu), plato=True, izgara=False)
    assert hepsi == yalniz
