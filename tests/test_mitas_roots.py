# -*- coding: utf-8 -*-
"""İP-5 RUN_ROOT kök-çözücü testleri (2026-07-11, plan rev.4).
Kritik sözleşme: (1) env boşken üretim yolları BYTE-AYNI (sıfır davranış değişikliği);
(2) candidate modunda TÜM yazma-kökleri run-root altında — üretime işaret eden tek yol kalmaz;
(3) alt-süreç env-köprüsü kurulur. (Tam hash/mtime side-effect kanıtı = 1-film pilot.)"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mitas_roots  # noqa: E402

YAZMA_KOKLERI = ("DB_ROOT", "OUT_ROOT", "EXPORT_ROOT", "HAZIR", "KONTROL", "SPECIAL_GENRE_DIR",
                 "EVENTS_PATH", "MASTER_MD", "MASTER_JSONL", "MANIFEST_DIR", "OUTPUTS_DIR",
                 "WEB_CACHE_DIR", "AFIS_CACHE_DIR")

URETIM_BEKLENEN = {
    "DB_ROOT": r"E:\MITAS\Database",
    "OUT_ROOT": r"E:\MITAS\Mitas Output",
    "EXPORT_ROOT": r"E:\MITAS\Mitas Output\export",
    "HAZIR": r"E:\MITAS\Mitas Output\export\ONAYLI",
    "KONTROL": r"E:\MITAS\Mitas Output\export\KONTROL",
    "SPECIAL_GENRE_DIR": r"E:\MITAS\Mitas Output\muzikal_animasyon_belgesel",
    "EVENTS_PATH": r"E:\MITAS\outputs\system_events.jsonl",
    "MASTER_MD": r"E:\MITAS\Mitas Output\export\_ISLEM_LOG.md",
    "MASTER_JSONL": r"E:\MITAS\Mitas Output\export\_ISLEM_LOG.jsonl",
    "MANIFEST_DIR": r"E:\MITAS\outputs\manifests",
    "OUTPUTS_DIR": r"E:\MITAS\outputs",
    "WEB_CACHE_DIR": r"E:\MITAS\cache\web",
    "AFIS_CACHE_DIR": r"E:\MITAS\_102_afis_cache",
}


def test_uretim_yollari_byte_ayni(monkeypatch):
    """MITAS_RUN_ROOT boş → eski hardcode yollarla BİREBİR aynı (regresyon-sıfır sözleşmesi)."""
    monkeypatch.delenv("MITAS_RUN_ROOT", raising=False)
    r = mitas_roots.resolve()
    assert r["RUN_ROOT"] is None
    for k, beklenen in URETIM_BEKLENEN.items():
        assert str(r[k]) == beklenen, f"{k}: {r[k]} != {beklenen}"


def test_candidate_tum_yazma_kokleri_runroot_altinda(tmp_path, monkeypatch):
    monkeypatch.delenv("MITAS_RUN_ROOT", raising=False)
    candidate_base = tmp_path / "candidate_runs"
    run_root = candidate_base / "run-1"
    monkeypatch.setattr(mitas_roots, "CANDIDATE_ROOT", candidate_base)
    r = mitas_roots.resolve(str(run_root))
    for k in YAZMA_KOKLERI:
        assert str(r[k]).startswith(str(run_root)), \
            f"{k} üretime işaret ediyor: {r[k]} (İZOLASYON İHLALİ)"
    # plan rev.4 yapısı: Database/export/manifests run-root altında
    assert str(r["DB_ROOT"]) == str(run_root / "Database")
    assert str(r["EXPORT_ROOT"]) == str(run_root / "export")
    assert str(r["MANIFEST_DIR"]) == str(run_root / "manifests")


def test_env_uzerinden_de_calisir(tmp_path, monkeypatch):
    candidate_base = tmp_path / "candidate_runs"
    run_root = candidate_base / "run-1"
    monkeypatch.setattr(mitas_roots, "CANDIDATE_ROOT", candidate_base)
    monkeypatch.setenv("MITAS_RUN_ROOT", str(run_root))
    r = mitas_roots.resolve()
    assert str(r["DB_ROOT"]).startswith(str(run_root))
    assert mitas_roots.is_candidate()


def test_child_env_koprusu(tmp_path, monkeypatch):
    for k in ("MITAS_WEB_CACHE_DIR", "MITAS_OUTPUTS_DIR", "MITAS_MANIFEST_DIR",
              "MITAS_AFIS_CACHE_DIR", "MITAS_RUN_ROOT"):
        monkeypatch.delenv(k, raising=False)
    candidate_base = tmp_path / "candidate_runs"
    run_root = candidate_base / "run-1"
    monkeypatch.setattr(mitas_roots, "CANDIDATE_ROOT", candidate_base)
    r = mitas_roots.resolve(str(run_root))
    mitas_roots.export_child_env(r)
    import os
    assert os.environ["MITAS_WEB_CACHE_DIR"].startswith(str(tmp_path))
    assert os.environ["MITAS_OUTPUTS_DIR"].startswith(str(tmp_path))
    assert os.environ["MITAS_AFIS_CACHE_DIR"] == str(run_root / "cache" / "afis")
    assert os.environ["MITAS_RUN_ROOT"] == str(run_root)


def test_candidate_production_ve_base_koklerini_reddeder(monkeypatch):
    monkeypatch.setattr(mitas_roots, "CANDIDATE_ROOT", mitas_roots.PROJECT_ROOT / "candidate_runs")
    with pytest.raises(mitas_roots.RootSafetyError):
        mitas_roots.resolve(str(mitas_roots.PROJECT_ROOT))
    with pytest.raises(mitas_roots.RootSafetyError):
        mitas_roots.resolve(str(mitas_roots.CANDIDATE_ROOT))


def test_candidate_env_override_lari_ezer(tmp_path, monkeypatch):
    candidate_base = tmp_path / "candidate_runs"
    run_root = candidate_base / "run-1"
    monkeypatch.setattr(mitas_roots, "CANDIDATE_ROOT", candidate_base)
    monkeypatch.setenv("MITAS_OUTPUTS_DIR", r"E:\MITAS\outputs")
    monkeypatch.setenv("MITAS_MANIFEST_DIR", r"E:\MITAS\outputs\manifests")
    monkeypatch.setenv("MITAS_WEB_CACHE_DIR", r"E:\MITAS\cache\web")
    monkeypatch.setenv("MITAS_AFIS_CACHE_DIR", r"E:\MITAS\_102_afis_cache")
    r = mitas_roots.resolve(str(run_root))
    mitas_roots.export_child_env(r)
    assert os.environ["MITAS_OUTPUTS_DIR"] == str(run_root / "outputs")
    assert os.environ["MITAS_MANIFEST_DIR"] == str(run_root / "manifests")
    assert os.environ["MITAS_WEB_CACHE_DIR"] == str(run_root / "cache" / "web")
    assert os.environ["MITAS_AFIS_CACHE_DIR"] == str(run_root / "cache" / "afis")


def test_resolve_production_envden_etkilenmez(monkeypatch):
    monkeypatch.setenv("MITAS_RUN_ROOT", r"E:\MITAS\candidate_runs\x")
    assert mitas_roots.resolve_production()["RUN_ROOT"] is None


def test_uretim_modunda_kopru_dokunmaz(monkeypatch):
    for k in ("MITAS_WEB_CACHE_DIR", "MITAS_OUTPUTS_DIR", "MITAS_RUN_ROOT"):
        monkeypatch.delenv(k, raising=False)
    r = mitas_roots.resolve(None)
    mitas_roots.export_child_env(r)
    import os
    assert "MITAS_RUN_ROOT" not in os.environ, "üretim modunda env-köprüsü KURULMAZ"
