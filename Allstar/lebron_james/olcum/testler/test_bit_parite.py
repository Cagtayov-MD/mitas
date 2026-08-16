#!/usr/bin/env python3
"""Bit-parite regresyon testi (Görev M4, MITAS_Master_Dup_Kok_Sebep_Plani_v1.md).

MITAS_MASTER_V2 bayrağı KAPALIYKEN db_compose_master.py'nin (F1/F2/F3 fix'leri
eklendikten SONRA) ürettiği master PNG'nin, gerçek üretim çıktısıyla (SON_METRO
cikis_jenerik havuzu, candidate_runs/kunye51_20260714) piksel-piksel ÖZDEŞ
kaldığını kanıtlar. AYRICA aynı süreç içinde bayrak AÇIK bir çağrı yapılıp
hemen ardından KAPALI bir çağrı tekrarlanarak, bayrağın modül-yükleme değil
ÇAĞRI ZAMANINDA okunduğu (aynı süreçte A/B mümkün) doğrulanır.

Çalıştır:
  /opt/mitas/venvs/ocr/bin/python -m pytest harness/master_dup/test_bit_parite.py -q -s

SALT-OKUNUR kaynaklar: OCR-worktree/master_png_monitor.py + db_compose_master.py
(yalnız import edilir), candidate_runs/kunye51_20260714/... (yalnız okunur).
"""
from __future__ import annotations

import glob
import importlib.util
import os
import sys
import types
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MONITOR_PY = PROJECT_ROOT / "OCR-worktree" / "master_png_monitor.py"

SON_METRO_FILM = (
    PROJECT_ROOT / "candidate_runs" / "kunye51_20260714" / "Database"
    / "evoArcadmin_COZUMLEMEV2S27_1980-0186-1-0000-00-1-SON_METRO"
)
SON_METRO_FRAMES = SON_METRO_FILM / "frames" / "cikis_jenerik"
SON_METRO_REFERANS_PNG = SON_METRO_FILM / "reading_master_runaware.png"


def _import_monitor():
    os.environ.setdefault("MITAS_PROJECT_ROOT", str(PROJECT_ROOT))
    spec = importlib.util.spec_from_file_location("master_png_monitor_bitparite", str(MONITOR_PY))
    mon = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mon
    spec.loader.exec_module(mon)
    return mon


def _read_bgr(path: Path) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    assert img is not None, f"okunamadı: {path}"
    return img


@pytest.mark.skipif(not SON_METRO_FRAMES.is_dir(), reason="SON_METRO kare havuzu bu ortamda yok")
@pytest.mark.skipif(not SON_METRO_REFERANS_PNG.exists(), reason="referans üretim PNG'si yok")
def test_v2_flag_off_is_bit_identical_to_production():
    mon = _import_monitor()
    dc = mon.dc
    frames = sorted(glob.glob(str(SON_METRO_FRAMES / "*.png")), key=dc.nat_sort_key)
    assert len(frames) > 100, "beklenenden az kare -- havuz eksik olabilir"

    referans = _read_bgr(SON_METRO_REFERANS_PNG)

    # 1) Bayrak hiç set edilmemiş / "0" -- eski davranış.
    os.environ.pop("MITAS_MASTER_V2", None)
    mon._profil_dy_kilidi(SON_METRO_FILM)
    dc.clear_cache()
    args = mon.make_args()
    master_off_1, info_off_1 = mon._compose_reading_seg(frames, args)
    assert master_off_1 is not None
    assert info_off_1["manifest"]["mode"] == "reading_runaware"
    assert np.array_equal(master_off_1, referans), (
        f"BİT-PARİTE BOZULDU (bayrak kapalı, ilk çağrı): shape "
        f"{master_off_1.shape} vs referans {referans.shape}"
    )

    # 2) AYNI SÜREÇTE bayrağı aç, farklı bir çağrı yap (F1/F2/F3 çalışabilir --
    #    burada yalnız "çökmeden çalışıyor" doğrulanır, içerik M4 adım 5c/5d'de
    #    ayrı ölçülür).
    os.environ["MITAS_MASTER_V2"] = "1"
    dc.clear_cache()
    master_on, info_on = mon._compose_reading_seg(frames, args)
    assert master_on is not None

    # 3) AYNI SÜREÇTE bayrağı tekrar kapat -- çağrı zamanlı okuma kanıtı: sonuç
    #    yine referansla bit-birebir olmalı (modül YENİDEN YÜKLENMEDEN).
    os.environ["MITAS_MASTER_V2"] = "0"
    dc.clear_cache()
    master_off_2, info_off_2 = mon._compose_reading_seg(frames, args)
    assert master_off_2 is not None
    assert np.array_equal(master_off_2, referans), (
        "BİT-PARİTE BOZULDU (bayrak yeniden kapatıldıktan sonra, AYNI süreç/modül) "
        "-- flag çağrı-zamanlı okunmuyor olabilir"
    )
    os.environ.pop("MITAS_MASTER_V2", None)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
