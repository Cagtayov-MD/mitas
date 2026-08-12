"""Paylaşımlı fixture'lar — sahte Database, sahte events."""
import json
import pytest
from pathlib import Path


@pytest.fixture
def sahte_proje(tmp_path):
    """Geçici proje dizini: Database/, outputs/, docs/raporlar/, data/hafiza/"""
    proje = tmp_path / "mitas_test"
    proje.mkdir()
    (proje / "Database").mkdir()
    (proje / "outputs").mkdir()
    (proje / "docs" / "raporlar" / "gunluk").mkdir(parents=True)
    (proje / "docs" / "raporlar" / "kontrol").mkdir(parents=True)
    (proje / "data" / "hafiza").mkdir(parents=True)
    (proje / "Mitas Output" / "export" / "ONAYLI").mkdir(parents=True)
    (proje / "Mitas Output" / "export" / "KONTROL").mkdir(parents=True)
    (proje / "config").mkdir()

    # sahte system_events.jsonl
    events = [
        {
            "event_id": "evt-test01",
            "ts": "2026-08-01T10:00:00+00:00",
            "kind": "routed_kontrol",
            "level": "warn",
            "module": "pipeline",
            "media_id": "test_film_1",
            "summary": "test routed kontrol",
        },
        {
            "event_id": "evt-test02",
            "ts": "2026-08-01T10:05:00+00:00",
            "kind": "routed_onayli",
            "level": "info",
            "module": "pipeline",
            "media_id": "test_film_2",
            "summary": "test routed onayli",
        },
    ]
    ev_path = proje / "outputs" / "system_events.jsonl"
    ev_path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n",
        encoding="utf-8",
    )
    return proje


@pytest.fixture
def sahte_film_kontrol(sahte_proje):
    """KONTROL filmi: yönetmen hatası."""
    film_dir = sahte_proje / "Database" / "TEST FILM 2026-0001-1-0000-00-1"
    film_dir.mkdir()
    durum = {
        "karar": "Kontrol",
        "route": {
            "tier": "KONTROL",
            "kontrol_tip": "YONETMEN_KIMLIK",
            "folder": "KONTROL",
            "agir": [["YONETMEN", "yönetmen garble"]],
            "hafif": [],
        },
        "neden": [
            "yönetmen okunamadı (KB-fill yok — kırmızı çizgi)",
            "kimlik çelişkisi (KB cross-check)",
        ],
        "qwen_qc": {
            "ozet_var": True,
            "oyuncu_sayisi": 5,
            "yapimci_var": True,
            "yonetmen_var": False,
            "ses_dil_var": True,
            "afis_var": True,
            "hepsi_buyuk_harf": True,
            "turkce_karakter_bozuk_var": False,
            "latin_disi_alfabe_var": False,
            "yabanci_ad_ascii_degil": False,
        },
        "ocr_bucket": "GUVENILIR",
        "ocr_lines": 450,
        "asr_status": "done",
        "timings_sec": {
            "coz": 60.0,
            "ocr": 120.0,
            "asr": 100.0,
            "video_kunye": 45.0,
            "pdf": 30.0,
            "v4_final": 50.0,
            "qwen_qc": 5.0,
            "toplam": 410.0,
        },
        "title": "TEST FILM",
        "trt_id": "2026-0001-1-0000-00-1",
        "tur": "DRAMA",
        "duration": "01:30:00",
    }
    (film_dir / "_DURUM.json").write_text(
        json.dumps(durum, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return film_dir


@pytest.fixture
def sahte_film_onayli(sahte_proje):
    """ONAYLI filmi: temiz."""
    film_dir = sahte_proje / "Database" / "TEMIZ FILM 2026-0002-1-0000-00-1"
    film_dir.mkdir()
    durum = {
        "karar": "Onaylı",
        "route": {"tier": "ONAYLI", "folder": "ONAYLI"},
        "neden": [],
        "qwen_qc": {
            "ozet_var": True,
            "oyuncu_sayisi": 6,
            "yapimci_var": True,
            "yonetmen_var": True,
            "ses_dil_var": True,
            "afis_var": True,
            "hepsi_buyuk_harf": True,
            "turkce_karakter_bozuk_var": False,
            "latin_disi_alfabe_var": False,
            "yabanci_ad_ascii_degil": False,
        },
        "ocr_bucket": "GUVENILIR",
        "timings_sec": {"toplam": 300.0, "coz": 50, "ocr": 90, "asr": 80},
        "title": "TEMIZ FILM",
        "trt_id": "2026-0002-1-0000-00-1",
        "tur": "KOMEDI",
    }
    (film_dir / "_DURUM.json").write_text(
        json.dumps(durum, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return film_dir
