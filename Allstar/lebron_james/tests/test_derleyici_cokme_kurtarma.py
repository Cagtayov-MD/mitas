"""Çöküş kurtarma (temporal_chunk_stack) — 2026-08-19 davranış kapıları.

Sentetik 100+ karelik filmler `cift_olc` dikişiyle tamamen scroll'a çevrilir;
karar zinciri (çöküş kuralı → 12'lik zaman parçaları → H_MAKS) GPU'suz,
kapalı biçimde sınanır. Kare i tamamen (i, 0, 0) rengiyle doludur — masterın
her satırının hangi kaynak kareden geldiği layout haritasından yeniden
kurulabilmelidir. Kurtarma yalnız çöküş kuralı tetiklendiğinde devreye
girer; sağlıklı filmin masterı piksel piksel normal yolun sonucudur.
"""
import numpy as np

import derleyici

H, W = 200, 64


def _kareler(n, h=H, w=W):
    return [np.full((h, w, 3), (i % 256, 0, 0), dtype=np.uint8) for i in range(n)]


def _derle(ims):
    return derleyici.derle(
        "film", ims=ims,
        flashlight=lambda im, _idx: im,
        token_saglayici=lambda im, _idx: set())


# AKILLI BIÇAK kuyruk kuralı duraksama bulamayınca SON kareyi atar
# (bitis = len(ciftler)-1); 121 karelik girdi trim sonrası tam 120 kalır.
N = 121


def _hepsi_scroll(monkeypatch, adet, dy=-1.0):
    """Ölçümü sahtele: bütün çiftler 'scroll' — karar mantığı sınanır."""
    ciftler = [{"dy": dy, "resp": 0.9, "sinif": "scroll"} for _ in range(adet)]
    monkeypatch.setattr(derleyici, "cift_olc", lambda *a, **k: list(ciftler))


def test_yuz_yirmi_kare_cokusu_12lik_zaman_parcalariyla_kurtarilir(monkeypatch):
    ims = _kareler(N)
    _hepsi_scroll(monkeypatch, N - 1, dy=-1.0)
    kanvas, m = _derle(ims)

    assert m["durum"] == "OK"
    cr = m["collapse_recovery"]
    assert cr["triggered"] is True
    assert cr["strategy"] == "temporal_chunk_stack"
    assert cr["chunk_size"] == 12
    assert cr["chunk_count"] == 10
    assert cr["original_frames"] == 120
    assert cr["original_height"] == 319          # 119 px toplam kayma + H
    assert cr["recovered_height"] == 2110        # 10 parça × (11 + 200)
    assert kanvas.shape == (2110, W, 3)
    assert m["segment"] == 10
    assert m["size"] == [W, 2110]


def test_kurtarma_layoutu_sati_sati_kaynaga_baglanir(monkeypatch):
    ims = _kareler(N)
    _hepsi_scroll(monkeypatch, N - 1, dy=-1.0)
    kanvas, m = _derle(ims)
    rows = m["layout_map"]

    assert rows[0]["master_y0"] == 0
    assert rows[-1]["master_y1"] == 2110
    for onceki, sonraki in zip(rows, rows[1:]):
        assert onceki["master_y1"] == sonraki["master_y0"], "layout delikli"

    # parça sınırları: her 211. satırda kaynak, 12'lik zaman adımıyla başa döner
    for parca in range(10):
        satir = next(r for r in rows if r["master_y0"] == parca * 211)
        assert satir["source_path"].endswith(f"frame-{parca * 12:06d}")
        assert satir["source_y0"] == 0

    kaynaklar = {f"synthetic://frame-{i:06d}": im for i, im in enumerate(ims)}
    for r in rows:
        assert np.array_equal(
            kanvas[r["master_y0"]:r["master_y1"]],
            kaynaklar[r["source_path"]][r["source_y0"]:r["source_y1"]])


def test_h_maks_asimi_kurtarma_kunyesiyle_gorunur_kalir(monkeypatch):
    ims = _kareler(201)                       # trim sonrası 200 kare
    _hepsi_scroll(monkeypatch, 200, dy=-1.0)
    monkeypatch.setattr(derleyici, "H_MAKS", 3000)
    kanvas, m = _derle(ims)

    assert kanvas is None
    assert m["durum"] == "boy_asimi"
    assert m["boy"] == 3583                     # 16 dolu parça × 211 + 207
    assert m["collapse_recovery"]["triggered"] is True
    assert m["collapse_recovery"]["recovered_height"] == 3583
    assert m["collapse_recovery"]["chunk_count"] == 17


def test_cokus_yoksa_normal_master_piksel_paritesi_korunur(monkeypatch):
    """Çöküş kuralı girmeyen film kurtarma yoluna DEĞMEZ: master, saf
    `_segment_kanvas` kompozisyonuyla piksel piksel aynı olmalıdır."""
    ims = _kareler(N)
    _hepsi_scroll(monkeypatch, N - 1, dy=-8.0)     # 1152 px > 2×H → çöküş değil
    kanvas, m = _derle(ims)

    assert m["collapse_recovery"] == {
        "triggered": False, "original_frames": 120,
        "original_segments": 1, "original_height": 1152}
    assert m["segment"] == 1
    beklenen = derleyici._segment_kanvas(
        ims[:120], [8.0 * i for i in range(120)])
    assert np.array_equal(kanvas, beklenen)


def test_parcalama_segment_bazli_yapilir_ve_master_y_birikir():
    ims1 = _kareler(15, h=100, w=32)
    ims2 = _kareler(5, h=100, w=32)
    kaynak = {id(im): f"synthetic://a-{i}" for i, im in enumerate(ims1)}
    kaynak.update({id(im): f"synthetic://b-{i}" for i, im in enumerate(ims2)})

    parcalar, layout = derleyici._cokme_kurtarma_parcalari(
        [(ims1, [float(i) for i in range(15)]),
         (ims2, [float(i) for i in range(5)])], kaynak)

    # 15 kare → 12+3; 5 kare → tek parça
    assert [p.shape[0] for p in parcalar] == [111, 102, 104]
    assert layout[0]["master_y0"] == 0
    assert layout[-1]["master_y1"] == 317
    for onceki, sonraki in zip(layout, layout[1:]):
        assert onceki["master_y1"] == sonraki["master_y0"]
    ikinci_kosu = next(r for r in layout if r["source_path"] == "synthetic://b-0")
    assert ikinci_kosu["master_y0"] == 111 + 102
