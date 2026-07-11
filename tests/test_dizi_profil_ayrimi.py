# -*- coding: utf-8 -*-
"""test_dizi_profil_ayrimi.py — FİLM/DİZİ profil ayrımı %100 kilidi (Çağatay 2026-07-11).

İki prensip:
1) master_png_monitor: hub adındaki TRT tipi bayrağı ZORLAR — film(tip=1) → hibrit-dy '0'
   (ortam değişkeni ne derse desin), dizi(tip=0) → '1'. TRT'siz hub → env'e dokunulmaz.
2) dizi_isle: pipeline subprocess env'inde MITAS_SLIT_DY_HYBRID=1 + MITAS_SHADOW_VL=1.

Çalıştır (cv2 gerekir): E:\\MITAS\\venvs\\ocr\\Scripts\\python.exe -m pytest tests/test_dizi_profil_ayrimi.py -q
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MON = os.path.join(_ROOT, "OCR-worktree", "master_png_monitor.py")
_spec = importlib.util.spec_from_file_location("monitor_profil_under_test", _MON)
mon = importlib.util.module_from_spec(_spec)
sys.modules["monitor_profil_under_test"] = mon
_spec.loader.exec_module(mon)


def test_film_tipi_hibriti_zorla_kapatir(monkeypatch):
    # env '1' bile olsa FİLM hub'ında (tip parseli =1) bayrak ZORLA '0'
    monkeypatch.setattr(mon.dc, "SLIT_DY_HYBRID", "1")
    sonuc = mon._profil_dy_kilidi(Path(r"E:\X\HAYALET BABAM 1990-0488-1-0000-00-1"))
    assert sonuc == "0"
    assert mon.dc.SLIT_DY_HYBRID == "0"


def test_dizi_tipi_hibriti_zorla_acar(monkeypatch):
    # env '0' bile olsa DİZİ hub'ında (tip parseli =0) bayrak ZORLA '1'
    monkeypatch.setattr(mon.dc, "SLIT_DY_HYBRID", "0")
    sonuc = mon._profil_dy_kilidi(Path(r"E:\X\YARGIÇ VE POLİS 1992-0324-0-0001-00-1"))
    assert sonuc == "1"
    assert mon.dc.SLIT_DY_HYBRID == "1"


def test_trt_siz_hub_env_korunur(monkeypatch):
    # TRT kimliği olmayan hub (lab/test): karar verilemez → mevcut değer DEĞİŞMEZ
    for once in ("0", "golge", "1"):
        monkeypatch.setattr(mon.dc, "SLIT_DY_HYBRID", once)
        sonuc = mon._profil_dy_kilidi(Path(r"D:\lab\yedi_numara"))
        assert sonuc == once
        assert mon.dc.SLIT_DY_HYBRID == once


def test_gen_reading_master_kilidi_cagirir(tmp_path, monkeypatch):
    # gen_reading_master, kilidi film-tipinde '0'a çekmeli (boş hub: erken no_frames dönüşü yeter)
    monkeypatch.setattr(mon.dc, "SLIT_DY_HYBRID", "1")
    hub = tmp_path / "TEST FILM 1999-0001-1-0000-00-1"
    (hub / "frames").mkdir(parents=True)
    mon.gen_reading_master(hub, "TEST", seg="cikis", write_manifest=False)
    assert mon.dc.SLIT_DY_HYBRID == "0"


def test_dizi_isle_pipeline_env_bayraklari(monkeypatch):
    sys.path.insert(0, os.path.join(_ROOT, "scripts"))
    import dizi_isle

    yakalanan = {}

    def sahte_run(cmd, env=None, **kw):
        yakalanan["env"] = env
        class R:  # noqa: N801
            returncode = 0
        return R()

    monkeypatch.setattr(dizi_isle.subprocess, "run", sahte_run)
    dizi_isle._pipeline_kos(r"D:\x\video 1900-0138-0-0001-00-1.mp4")
    assert yakalanan["env"]["MITAS_SHADOW_VL"] == "1"
    assert yakalanan["env"]["MITAS_SLIT_DY_HYBRID"] == "1"   # DİZİ hattı = hibrit AÇIK
