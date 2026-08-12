"""Config modülü testleri — yol çözümü ve YAML yükleme."""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))


def test_proje_koku_env_var(monkeypatch, tmp_path):
    """MITAS_PROJECT_ROOT env'dan okunur."""
    monkeypatch.setenv("MITAS_PROJECT_ROOT", str(tmp_path))
    import importlib
    from genel_sekreter import config

    importlib.reload(config)
    assert config.PROJE_KOKU == tmp_path


def test_proje_koku_fallback():
    """Env yoksa /opt/mitas'a düşer."""
    from genel_sekreter import config

    assert config.PROJE_KOKU.is_dir() or str(config.PROJE_KOKU) == "/opt/mitas"


def test_load_gs_config_varsayilan(sahte_proje, monkeypatch):
    """gs_config.yaml yoksa varsayılan değerler döner."""
    monkeypatch.setenv("MITAS_PROJECT_ROOT", str(sahte_proje))
    import importlib
    from genel_sekreter import config

    importlib.reload(config)
    c = config.load_gs_config()
    assert isinstance(c, dict)
    assert "schedule" in c
    assert "thresholds" in c
    assert c["thresholds"]["onayli_sample_pct"] == 10


def test_load_gs_config_yaml(sahte_proje, monkeypatch):
    """gs_config.yaml varsa yüklenir."""
    monkeypatch.setenv("MITAS_PROJECT_ROOT", str(sahte_proje))
    cfg_file = sahte_proje / "config" / "gs_config.yaml"
    cfg_file.write_text(
        "schedule:\n  kontrol_analiz: '09:00'\n"
        "thresholds:\n  onayli_sample_pct: 25\n",
        encoding="utf-8",
    )
    import importlib
    from genel_sekreter import config

    importlib.reload(config)
    c = config.load_gs_config()
    assert c["schedule"]["kontrol_analiz"] == "09:00"
    assert c["thresholds"]["onayli_sample_pct"] == 25


def test_reload_config(sahte_proje, monkeypatch):
    """reload_config cache'i temizler."""
    monkeypatch.setenv("MITAS_PROJECT_ROOT", str(sahte_proje))
    import importlib
    from genel_sekreter import config

    importlib.reload(config)
    c1 = config.load_gs_config()
    c2 = config.reload_config()
    assert c1 == c2


def test_hafiza_path(sahte_proje, monkeypatch):
    """Hafıza yolu doğru çözülür."""
    monkeypatch.setenv("MITAS_PROJECT_ROOT", str(sahte_proje))
    import importlib
    from genel_sekreter import config

    importlib.reload(config)
    assert "hafiza" in str(config.HAFIZA_DIR)
    assert str(config.HAFIZA_COZUMLER).endswith("cozumler.jsonl")
