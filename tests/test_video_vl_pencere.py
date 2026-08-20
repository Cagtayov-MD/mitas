# -*- coding: utf-8 -*-
"""test_video_vl_pencere.py — video-VL kesim noktası havuz penceresiyle aynı olmalı.

Kök sorun (2026-07-30): `_pipe_video_vl.py` pencere başlangıcını `dur - CIKIS_TAIL_S`
ile KENDİ tahmin ediyordu (sabit 600 sn). Üretim penceresi ise `--ocr-tail` (default
480 sn) — pipeline bu değeri iletmiyordu. Sonuç: start_pos aynı olsa bile kesim
noktası 120 sn erken hesaplanıyordu.

Doğru desen `_jenerik_dense.py`'de zaten var: pipeline gerçek pencere başlangıcını
`--win-start` ile mutlak saniye olarak iletir. Bu test o sözleşmeyi kilitler.

Çalıştır: /opt/mitas/venvs/ocr/bin/python -m pytest tests/test_video_vl_pencere.py -q
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_MOD = _ROOT / "scripts" / "_pipe_video_vl.py"
_spec = importlib.util.spec_from_file_location("video_vl_under_test", _MOD)
vv = importlib.util.module_from_spec(_spec)
sys.modules["video_vl_under_test"] = vv
_spec.loader.exec_module(vv)

SURE = 3689.0      # ÇİÇEK TAKSİ b001 — 61:29
START_POS = 716    # _jenerik_pool v5 kararı (kare indeksi, havuz içinde)
FPS = 1.5


def _hub(tmp_path: Path, start_pos: int = START_POS) -> Path:
    clip = tmp_path / "HUB"
    (clip / "frames").mkdir(parents=True)
    (clip / "frames" / "jenerik_detection.json").write_text(
        json.dumps({"status": "found", "start_pos": start_pos}), encoding="utf-8")
    return clip


def test_kesim_noktasi_pipeline_penceresini_kullanir(tmp_path, monkeypatch):
    """Üretim penceresi (tail=480) verildiğinde kesim o pencereden hesaplanır."""
    monkeypatch.setattr(vv, "_sure", lambda _v: SURE)
    clip = _hub(tmp_path)
    win_start = SURE - 480.0                      # pipeline'ın _cik_start'ı

    sonuc = vv._baslangic_saniyesi(clip, Path("sahte.mp4"), win_start=win_start)

    assert sonuc == win_start + START_POS / FPS   # 3209.0 + 477.333 = 3686.333


def test_pencere_verilmezse_eski_600_davranisi_korunur(tmp_path, monkeypatch):
    """CLI'dan elle çağrı (win_start yok) mevcut davranışı bozmaz — geriye uyum."""
    monkeypatch.setattr(vv, "_sure", lambda _v: SURE)
    clip = _hub(tmp_path)

    sonuc = vv._baslangic_saniyesi(clip, Path("sahte.mp4"))

    assert sonuc == max(0.0, SURE - vv.CIKIS_TAIL_S) + START_POS / FPS


def test_iki_pencere_arasindaki_fark_tail_farkina_esittir(tmp_path, monkeypatch):
    """Bug'ın büyüklüğü: 600-480 = 120 sn. Regresyon olursa bu sayı değişir."""
    monkeypatch.setattr(vv, "_sure", lambda _v: SURE)
    clip = _hub(tmp_path)

    dogru = vv._baslangic_saniyesi(clip, Path("s.mp4"), win_start=SURE - 480.0)
    eski = vv._baslangic_saniyesi(clip, Path("s.mp4"))

    assert round(dogru - eski, 3) == 120.0


def test_pipeline_win_start_ve_src_fps_iletir():
    """mitas_pipeline._pipe_video_vl çağrısı dense deseniyle aynı argümanları geçmeli."""
    kaynak = (_ROOT / "scripts" / "mitas_pipeline.py").read_text(encoding="utf-8", errors="replace")
    i = kaynak.find("_pipe_video_vl.py")
    assert i > 0, "_pipe_video_vl çağrısı bulunamadı"
    blok = kaynak[i:i + 400]
    assert "--win-start" in blok, "pipeline pencere başlangıcını iletmiyor"
    assert "--src-fps" in blok, "pipeline kare fps'ini iletmiyor"
