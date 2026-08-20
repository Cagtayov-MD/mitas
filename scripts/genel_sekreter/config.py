"""Merkezi yapılandırma — yol çözümlemesi, sabitler, YAML yükleme."""
from __future__ import annotations

import os
import yaml
from pathlib import Path

# ── Kök dizinler ──────────────────────────────────────────────────────────
PROJE_KOKU = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
DB = PROJE_KOKU / "Database"
EVENTS_PATH = PROJE_KOKU / "outputs" / "system_events.jsonl"
CIKTI = PROJE_KOKU / "Mitas Output" / "export"
ONAYLI_DIR = CIKTI / "ONAYLI"
KONTROL_DIR = CIKTI / "KONTROL"
RAPORLAR_DIR = PROJE_KOKU / "docs" / "raporlar" / "gunluk"
KONTROL_RAPORLAR_DIR = PROJE_KOKU / "docs" / "raporlar" / "kontrol"
GUNLUK_PATH = PROJE_KOKU / "docs" / "GUNLUK.md"
QUEUE_PATH = PROJE_KOKU / "outputs" / "flow_queue" / "queue.json"
KOSUCU_LOG = PROJE_KOKU / "outputs" / "toplu_kosu" / "kosucu.log"
GECE_MONITOR_LOG = PROJE_KOKU / "outputs" / "gece_monitor.log"
HAFIZA_DIR = PROJE_KOKU / "data" / "hafiza"
HAFIZA_COZUMLER = HAFIZA_DIR / "cozumler.jsonl"

# ── Referans veritabanları (Araştırma ajanı için) ─────────────────────────
MITAS_FILES = PROJE_KOKU / "Mitas_Files"
IMDB_DIR = MITAS_FILES / "IMDB"
WIKIDATA_DIR = MITAS_FILES / "WIKIDATA"
TURKISH_NAME_DB = MITAS_FILES / "TURKISHNAMEDATABASE"

# ── YAML konfigürasyon ───────────────────────────────────────────────────
_GS_CONFIG_PATH = PROJE_KOKU / "config" / "gs_config.yaml"
_cached_config: dict | None = None


def load_gs_config() -> dict:
    """gs_config.yaml'ı yükle ve cache'le. Yoksa varsayılan değerler döndür."""
    global _cached_config
    if _cached_config is not None:
        return _cached_config
    if _GS_CONFIG_PATH.is_file():
        with open(_GS_CONFIG_PATH, encoding="utf-8") as f:
            _cached_config = yaml.safe_load(f) or {}
    else:
        _cached_config = _varsayilan_config()
    return _cached_config


def reload_config() -> dict:
    """Cache'i temizle ve yeniden yükle."""
    global _cached_config
    _cached_config = None
    return load_gs_config()


def _varsayilan_config() -> dict:
    return {
        "schedule": {
            "performans": "06:00",
            "kontrol_analiz": "08:00",
            "onayli_qc": "12:00",
            "hafiza_guncelle": "14:00",
            "arastirma": "16:00",
            "gunluk_rapor": "23:00",
        },
        "thresholds": {
            "onayli_sample_pct": 10,
            "performans_slow_min": 15,
            "event_stale_hours": 2,
            "disk_warn_gb": 100,
            "gpu_vram_warn_pct": 85,
        },
        "rapor": {
            "dil": "tr",
            "gunluk_append": True,
        },
    }


# ── Ollama bağlantısı ────────────────────────────────────────────────────
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# ── Council MCP ──────────────────────────────────────────────────────────
COUNCIL_DIR = PROJE_KOKU / "council_mcp"
