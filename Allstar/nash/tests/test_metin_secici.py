from pathlib import Path

import numpy as np

import metin_secici


def _yollar(n):
    return [Path(f"frame_{i:06d}.png") for i in range(n)]


def _calistir(analizler, *, tavan=100, griler=None, **ayar):
    yollar = _yollar(len(analizler))
    belge = {p.name: a for p, a in zip(yollar, analizler)}
    gri = griler or [np.full((8, 8), i, np.uint8) for i in range(len(yollar))]
    return metin_secici.sec(yollar=yollar, griler=gri, analizler=belge,
                            ayar={"tavan": tavan, **ayar})


def test_bos_kareler_aday_uretmez():
    secilen, kanit = _calistir([{"boxes": []} for _ in range(8)])
    assert secilen == []
    assert kanit["metinli_kare"] == 0


def test_yalniz_alt_yuzde_yirmideki_altyazi_elenir():
    altyazi = {"boxes": [[0.2, 0.84, 0.8, 0.96]]}
    secilen, kanit = _calistir([altyazi for _ in range(6)])
    assert secilen == []
    assert kanit["altyazi_elendi"] == 6


def test_kalici_kose_logosu_elenir_ama_tek_kart_kalir():
    logo = [0.01, 0.01, 0.12, 0.08]
    analiz = [{"boxes": [logo]} for _ in range(10)]
    analiz[5] = {"boxes": [logo, [0.25, 0.25, 0.75, 0.55]]}
    secilen, kanit = _calistir(analiz)
    assert [p.name for p in secilen] == ["frame_000005.png"]
    assert kanit["logo_kutusu_elendi"] == 10
    assert kanit["kalici_logo_imza_n"] == 1


def test_iki_bos_karelik_aralik_ayni_metin_blogudur():
    analiz = [{"boxes": []} for _ in range(8)]
    for i in (1, 2, 5, 6):
        analiz[i] = {"boxes": [[0.2, 0.2, 0.8, 0.5]]}
    _, kanit = _calistir(analiz, blok_bosluk=2)
    assert kanit["metin_blok_n"] == 1
    assert kanit["metin_bloklari"][0] == {
        "bas": "frame_000001.png", "son": "frame_000006.png", "kare": 4}


def test_blok_ilk_son_dort_kare_adimi_ve_dhash_degisimini_secer():
    analiz = [{"boxes": [[0.2, 0.2, 0.8, 0.5]]} for _ in range(12)]
    imzalar = [0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 255, 255]
    griler = [np.full((2, 2), deger, np.uint8) for deger in imzalar]
    # `sec` imza_fn'i ayardan degil acik argumandan alir.
    yollar = _yollar(12)
    belge = {p.name: a for p, a in zip(yollar, analiz)}
    secilen, kanit = metin_secici.sec(
        yollar=yollar, griler=griler, analizler=belge,
        ayar={"tavan": 100, "ornek_adim": 4, "dhash_degisim": 4},
        imza_fn=lambda g: int(g[0, 0]))
    adlar = {p.name for p in secilen}
    assert {"frame_000000.png", "frame_000004.png", "frame_000005.png",
            "frame_000008.png", "frame_000011.png"} <= adlar
    assert "dhash_degisim" in kanit["secim_nedenleri"]["frame_000005.png"]


def test_tavan_kronolojik_dagilimi_korur():
    analiz = [{"boxes": [[0.2, 0.2, 0.8, 0.5]]} for _ in range(40)]
    secilen, kanit = _calistir(analiz, tavan=6, ornek_adim=1)
    assert len(secilen) == 6
    assert secilen == sorted(secilen)
    assert secilen[0].name == "frame_000000.png"
    assert secilen[-1].name == "frame_000039.png"
    assert kanit["dusurulen_n"] > 0


def test_worker_dhash_varsa_gri_kare_gerekmez():
    analiz = [
        {"boxes": [[0.2, 0.2, 0.8, 0.5]], "dhash": imza}
        for imza in (0, 0, 255, 255, 255)
    ]
    yollar = _yollar(len(analiz))
    belge = {p.name: a for p, a in zip(yollar, analiz)}
    secilen, kanit = metin_secici.sec(
        yollar=yollar, griler=None, analizler=belge,
        ayar={"tavan": 100, "ornek_adim": 4, "dhash_degisim": 4})
    assert secilen
    assert "dhash_degisim" in kanit["secim_nedenleri"]["frame_000002.png"]
