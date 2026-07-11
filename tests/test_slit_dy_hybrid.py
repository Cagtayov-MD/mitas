# -*- coding: utf-8 -*-
"""test_slit_dy_hybrid.py — HİBRİT-DY kanal seçimi (şartname 2026-07-09) testleri.

Kapsam: _slit_channel_decision (SAF — ölçülmüş imza fixture'ları), _slit_channel_stats
(sentetik kayan-bar), slitscan bayrak davranışı (0=bit-identik/None-info, golge=piksel
aynı+sidecar kaydı, 1+DEMOTE+allow_demote=None dönüşü), _hybrid_flush sidecar'ı.

Çalıştır (cv2 gerekir — OCR venv):
  E:\\MITAS\\venvs\\ocr\\Scripts\\python.exe -m pytest tests/test_slit_dy_hybrid.py -x -q
Sistem python'unda cv2 yoksa modül SKIP olur (mevcut paket yeşilliği bozulmaz).
"""
import argparse
import importlib.util
import os
import sys

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

_DC_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "OCR-worktree", "db_compose_master.py")
_spec = importlib.util.spec_from_file_location("dc_hybrid_under_test", _DC_PATH)
dc = importlib.util.module_from_spec(_spec)
sys.modules["dc_hybrid_under_test"] = dc
_spec.loader.exec_module(dc)


def _args():
    return argparse.Namespace(polarity="auto", deinterlace=False, luma_key=False,
                              tht=22, min_hold=5, no_dedup=False)


def _params(h=64, w=64):
    return dc.derive_params(h, w, _args())


# ─────────────────────── _slit_channel_decision (SAF) ───────────────────────

def _stats(n=120, skip=0.05, cov=0.20, n_coin=60, med_f=31.6):
    return {"n_meas": n, "skip_frac_m": skip, "cov_med": cov, "n_coin": n_coin,
            "med_f": med_f, "med_f_signed": -med_f, "iqr_f": 0.09,
            "valid_rate_f": 0.95, "tol_coin": max(2.0, 0.1 * med_f),
            "resp_m_med": 0.4, "resp_f_med": 0.5, "dy_m": [], "dy_f": [], "cov_seri": []}


def test_karar_yedi_numara_imzasi_full():
    # Ölçülmüş vaka: cov 0.576, skip 0.875, n_coin ~18/120 → FIRE (FULL)
    s = _stats(n=120, skip=0.875, cov=0.576, n_coin=18, med_f=31.63)
    assert dc._slit_channel_decision(s, _params()) == "FULL"


def test_karar_duran_yazi_imzasi_demote():
    # İLK YARIŞ sınıfı: maske dürüst (cov normal), hareket yok, kesişme yok
    s = _stats(n=100, skip=0.99, cov=0.18, n_coin=0, med_f=15.8)
    assert dc._slit_channel_decision(s, _params()) == "DEMOTE"


def test_karar_saglikli_masked():
    s = _stats(n=120, skip=0.05, cov=0.22, n_coin=90, med_f=12.0)
    assert dc._slit_channel_decision(s, _params()) == "MASKED"


def test_karar_ucuncu_mod_statuko():
    # Şişik maske + duran yazı (dy_M≈dy_F≈0): skip yüksek + cov yüksek + kesişme
    # bol ama med_f<vmin → FULL koşulu (med_f>=vmin) sağlanmaz → MASKED (statüko).
    p = _params()
    s = _stats(n=100, skip=0.95, cov=0.60, n_coin=80, med_f=p.vmin * 0.5)
    assert dc._slit_channel_decision(s, p) == "MASKED"


def test_karar_none_ve_kisa_run_masked():
    assert dc._slit_channel_decision(None, _params()) == "MASKED"


def test_karar_ambiguous_ara_bolge_masked():
    # skip yüksek ama n_coin ne FIRE tabanında ne NULL'da → belirsiz → MASKED
    s = _stats(n=120, skip=0.7, cov=0.45, n_coin=2, med_f=20.0)
    assert dc._slit_channel_decision(s, _params()) == "MASKED"


# ─────────────────────── _slit_channel_stats (sentetik) ───────────────────────

def _kayan_bar_kareleri(tmp_path, n=24, hiz=4, h=240, w=320):
    """Sentetik kayan-jenerik: siyah zemin, yukarı akan beyaz metin satırları
    (putText — text_mask'in bileşen sınırlarından gerçek glif olarak geçer)."""
    yollar = []
    for i in range(n):
        img = np.zeros((h, w, 3), dtype=np.uint8)
        for k in range(6):
            y = (40 + k * 36 - i * hiz) % (h + 36)
            if 12 <= y <= h - 4:
                cv2.putText(img, f"ISIM SOYAD {k}", (24, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        yol = str(tmp_path / f"f_{i:05d}.png")
        cv2.imwrite(yol, img)
        yollar.append(yol)
    return yollar


def test_stats_sentetik_kayan_bar(tmp_path):
    frames = _kayan_bar_kareleri(tmp_path, n=24, hiz=4)
    st = dc._slit_channel_stats(frames, dc.derive_params(240, 320, _args()), _args())
    assert st is not None
    assert st["n_meas"] >= dc.SLIT_HY_MIN_MEAS
    # siyah zemin + parlak bar: maske dürüst → iki kanal da ~hiz ölçer, kesişme yüksek
    assert st["n_coin"] >= st["n_meas"] // 2
    assert st["skip_frac_m"] < 0.5


def test_stats_kisa_run_none(tmp_path):
    frames = _kayan_bar_kareleri(tmp_path, n=4, hiz=4)
    assert dc._slit_channel_stats(frames, dc.derive_params(240, 320, _args()), _args()) is None


# ─────────────────────── slitscan bayrak davranışı ───────────────────────

def test_slitscan_bayrak_0_info_yok_log_bos(tmp_path, monkeypatch):
    monkeypatch.setattr(dc, "SLIT_DY_HYBRID", "0")
    del dc.HYBRID_LOG[:]
    frames = _kayan_bar_kareleri(tmp_path, n=20, hiz=4)
    block, info = dc.slitscan(frames, dc.derive_params(240, 320, _args()), _args())
    assert info is None
    assert dc.HYBRID_LOG == []
    assert block is not None and block.size


def test_slitscan_golge_piksel_ayni_log_dolu(tmp_path, monkeypatch):
    frames = _kayan_bar_kareleri(tmp_path, n=20, hiz=4)
    monkeypatch.setattr(dc, "SLIT_DY_HYBRID", "0")
    del dc.HYBRID_LOG[:]
    b0, _ = dc.slitscan(frames, dc.derive_params(240, 320, _args()), _args())
    monkeypatch.setattr(dc, "SLIT_DY_HYBRID", "golge")
    del dc.HYBRID_LOG[:]
    b1, info = dc.slitscan(frames, dc.derive_params(240, 320, _args()), _args())
    assert info is not None and info["decision"] in ("MASKED", "FULL", "DEMOTE")
    assert len(dc.HYBRID_LOG) == 1
    assert (b0 is None) == (b1 is None)
    if b0 is not None:
        assert np.array_equal(b0, b1)          # gölge PİKSEL DEĞİŞTİRMEZ
    del dc.HYBRID_LOG[:]


def test_slitscan_bayrak1_demote_none_doner(tmp_path, monkeypatch):
    frames = _kayan_bar_kareleri(tmp_path, n=20, hiz=4)
    monkeypatch.setattr(dc, "SLIT_DY_HYBRID", "1")
    monkeypatch.setattr(dc, "_slit_channel_decision", lambda st, p: "DEMOTE")
    del dc.HYBRID_LOG[:]
    block, info = dc.slitscan(frames, dc.derive_params(240, 320, _args()), _args(), allow_demote=True)
    assert block is None and info["applied"] is True and info["decision"] == "DEMOTE"
    # allow_demote=False (film-ortak hat): DEMOTE uygulanmaz, statüko üretir
    del dc.HYBRID_LOG[:]
    block2, info2 = dc.slitscan(frames, dc.derive_params(240, 320, _args()), _args(), allow_demote=False)
    assert block2 is not None and info2["applied"] is False
    del dc.HYBRID_LOG[:]


def test_hybrid_flush_sidecar(tmp_path, monkeypatch):
    del dc.HYBRID_LOG[:]
    dc.HYBRID_LOG.append({"decision": "FULL", "stats": {"n_meas": 10}, "applied": True,
                          "src_first": "a.png", "src_last": "b.png", "n_frames": 10})
    dc._hybrid_flush(tmp_path)
    yol = tmp_path / "hybrid_shadow.jsonl"
    assert yol.exists()
    import json
    kayit = json.loads(yol.read_text(encoding="utf-8").splitlines()[0])
    assert kayit["decision"] == "FULL"
    assert dc.HYBRID_LOG == []          # flush temizler


def test_hy_manifest_ozet_travel():
    hy = {"decision": "FULL", "applied": True,
          "stats": {"cov_med": 0.576, "skip_frac_m": 0.875, "n_coin": 18,
                    "med_f": 31.63, "n_meas": 120}}
    oz = dc._hy_manifest_ozet(hy, 928)
    assert oz["dy_source"] == "full"
    assert abs(oz["travel_expected"] - 31.63 * 120) < 1
    assert 0.2 < oz["travel_ratio"] < 0.3      # Yedi Numara çöküklüğü ~0.24