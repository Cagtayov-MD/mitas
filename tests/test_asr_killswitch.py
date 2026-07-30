# -*- coding: utf-8 -*-
"""ASR kalıcı kill-switch (Çağatay 2026-07-11) API yolunda da geçerli olmalı.

2026-07-29 kanıtı: outputs/system_events.jsonl 11:24:36'da asr_queued+asr_started
üretti; ASR_KAPALI.flag diskte duruyordu. Kill-switch'i yalnız
scripts/mitas_pipeline.py:2394 kontrol ediyordu, core/api/asr_server.py hiç bakmıyordu."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.api import asr_server  # noqa: E402


def test_flag_dosyasi_varsa_kapali(tmp_path, monkeypatch):
    monkeypatch.delenv("MITAS_DISABLE_ASR", raising=False)
    monkeypatch.setattr(asr_server, "PROJECT_ROOT", tmp_path)
    (tmp_path / "ASR_KAPALI.flag").write_text("test")
    kapali, sebep = asr_server.asr_kapali_mi()
    assert kapali is True
    assert "ASR_KAPALI.flag" in sebep


def test_flag_yoksa_ve_env_yoksa_acik(tmp_path, monkeypatch):
    monkeypatch.delenv("MITAS_DISABLE_ASR", raising=False)
    monkeypatch.setattr(asr_server, "PROJECT_ROOT", tmp_path)
    kapali, sebep = asr_server.asr_kapali_mi()
    assert kapali is False
    assert sebep == ""


@pytest.mark.parametrize("deger", ["1", "true", "TRUE", "on", "yes", " 1 "])
def test_env_degiskeni_kapatir(tmp_path, monkeypatch, deger):
    """mitas_pipeline.py:2395-2396 ile BİREBİR aynı kabul listesi."""
    monkeypatch.setattr(asr_server, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("MITAS_DISABLE_ASR", deger)
    kapali, sebep = asr_server.asr_kapali_mi()
    assert kapali is True
    assert "MITAS_DISABLE_ASR" in sebep


@pytest.mark.parametrize("deger", ["0", "false", "off", "no", ""])
def test_env_degiskeni_yanlis_degerde_kapatmaz(tmp_path, monkeypatch, deger):
    monkeypatch.setattr(asr_server, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("MITAS_DISABLE_ASR", deger)
    kapali, _ = asr_server.asr_kapali_mi()
    assert kapali is False


def test_pipeline_ile_ayni_mantik(tmp_path, monkeypatch):
    """Regresyon kilidi: iki kill-switch uygulaması ayrışmamalı.

    mitas_pipeline.py:2394-2396 mantığı burada birebir tekrarlanıyor; ikisi
    ayrışırsa bu test patlar."""
    monkeypatch.setattr(asr_server, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("MITAS_DISABLE_ASR", raising=False)
    for flag_var, env_deger, beklenen in [
        (False, None, False),
        (True, None, True),
        (False, "1", True),
        (True, "0", True),
    ]:
        bayrak = tmp_path / "ASR_KAPALI.flag"
        if flag_var:
            bayrak.write_text("x")
        elif bayrak.exists():
            bayrak.unlink()
        if env_deger is None:
            monkeypatch.delenv("MITAS_DISABLE_ASR", raising=False)
        else:
            monkeypatch.setenv("MITAS_DISABLE_ASR", env_deger)
        assert asr_server.asr_kapali_mi()[0] is beklenen, (flag_var, env_deger)


def test_gercek_repo_kokunde_flag_YOK():
    """Rejim değişikliği (Çağatay 2026-07-30): ASR'nin normal kontrolü artık webui
    anahtarı (queue.json asrEnabled). ASR_KAPALI.flag yalnız ACİL global kill —
    varsayılan durumda diskte DURMAMALI (dursa her film-koşusunu sessizce ezer).
    Bilinçli bir kampanya kill'i sırasında bu test kırmızı olur — o dönem için
    xfail'leyin, kampanya bitince dosyayı silin."""
    kok = Path(__file__).resolve().parents[1]
    assert not (kok / "ASR_KAPALI.flag").exists(), (
        "ASR_KAPALI.flag diskte duruyor — webui ASR anahtarını geçersiz kılar. "
        "Acil kill bilinçli değilse dosyayı silin (2026-07-11 talimatı 2026-07-30'da "
        "anahtar rejimiyle değiştirildi).")
