# -*- coding: utf-8 -*-
"""_channel_lang.extract() filmler-arası LID kontaminasyon regresyon testi (mock, ffmpeg'siz).

Bug (2026-06-06): extract() temp adını yalnız stream/kanal/zaman ile veriyordu (videodan
BAĞIMSIZ) ve ffmpeg dönüş kodunu kontrol ETMİYORDU → bir filmin ses extraction'ı başarısızsa
(ses yok / kodek) önceki filmden kalan aynı-adlı bayat wav 'başarılı' sanılıp sınıflanıyordu
(filmler-arası dil kontaminasyonu, conf 1.00, müzik-gate bypass). Fix: dst.unlink() + returncode.
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import _channel_lang as cl


def test_extract_basarisiz_ffmpeg_bayat_wavi_kullanmaz(tmp_path, monkeypatch):
    """ffmpeg başarısız (returncode!=0) + önceki filmden kalan bayat dst → False ve dst silinmiş."""
    dst = tmp_path / "s0_c0_20.wav"
    dst.write_bytes(b"\x00" * 5000)          # önceki filmin >1000 byte bayat wav'ı

    def fake_run(*args, **kwargs):           # ffmpeg çağrısı → hata, dosya YAZMAZ
        return types.SimpleNamespace(returncode=1, stdout=b"", stderr=b"no audio")

    monkeypatch.setattr(cl.subprocess, "run", fake_run)
    ok = cl.extract("yeni_film.mp4", 0, 0, 20, 20, dst)
    assert ok is False                        # bayat wav SINIFLANMAMALI
    assert not dst.exists()                   # ve bayat dosya silinmiş olmalı (unlink)


def test_extract_basarili_ffmpeg_true_doner(tmp_path, monkeypatch):
    """ffmpeg başarılı (returncode 0, geçerli boyut) → True."""
    dst = tmp_path / "s0_c0_20.wav"

    def fake_run(*args, **kwargs):
        dst.write_bytes(b"\x00" * 5000)       # ffmpeg gerçek wav yazdı
        return types.SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(cl.subprocess, "run", fake_run)
    ok = cl.extract("film.mp4", 0, 0, 20, 20, dst)
    assert ok is True
