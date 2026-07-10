# -*- coding: utf-8 -*-
"""İP-5 RUN_ROOT kök-çözücü testleri (2026-07-11, plan rev.4).
Kritik sözleşme: (1) env boşken üretim yolları BYTE-AYNI (sıfır davranış değişikliği);
(2) candidate modunda TÜM yazma-kökleri run-root altında — üretime işaret eden tek yol kalmaz;
(3) alt-süreç env-köprüsü kurulur. (Tam hash/mtime side-effect kanıtı = 1-film pilot.)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mitas_roots  # noqa: E402

YAZMA_KOKLERI = ("DB_ROOT", "OUT_ROOT", "EXPORT_ROOT", "HAZIR", "KONTROL", "SPECIAL_GENRE_DIR",
                 "EVENTS_PATH", "MASTER_MD", "MASTER_JSONL", "MANIFEST_DIR", "OUTPUTS_DIR",
                 "WEB_CACHE_DIR")

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
    r = mitas_roots.resolve(str(tmp_path))
    for k in YAZMA_KOKLERI:
        assert str(r[k]).startswith(str(tmp_path)), \
            f"{k} üretime işaret ediyor: {r[k]} (İZOLASYON İHLALİ)"
    # plan rev.4 yapısı: Database/export/manifests run-root altında
    assert str(r["DB_ROOT"]) == str(tmp_path / "Database")
    assert str(r["EXPORT_ROOT"]) == str(tmp_path / "export")
    assert str(r["MANIFEST_DIR"]) == str(tmp_path / "manifests")


def test_env_uzerinden_de_calisir(tmp_path, monkeypatch):
    monkeypatch.setenv("MITAS_RUN_ROOT", str(tmp_path))
    r = mitas_roots.resolve()
    assert str(r["DB_ROOT"]).startswith(str(tmp_path))
    assert mitas_roots.is_candidate()


def test_child_env_koprusu(tmp_path, monkeypatch):
    for k in ("MITAS_WEB_CACHE_DIR", "MITAS_OUTPUTS_DIR", "MITAS_MANIFEST_DIR", "MITAS_RUN_ROOT"):
        monkeypatch.delenv(k, raising=False)
    r = mitas_roots.resolve(str(tmp_path))
    mitas_roots.export_child_env(r)
    import os
    assert os.environ["MITAS_WEB_CACHE_DIR"].startswith(str(tmp_path))
    assert os.environ["MITAS_OUTPUTS_DIR"].startswith(str(tmp_path))
    assert os.environ["MITAS_RUN_ROOT"] == str(tmp_path)


def test_uretim_modunda_kopru_dokunmaz(monkeypatch):
    for k in ("MITAS_WEB_CACHE_DIR", "MITAS_OUTPUTS_DIR", "MITAS_RUN_ROOT"):
        monkeypatch.delenv(k, raising=False)
    r = mitas_roots.resolve(None)
    mitas_roots.export_child_env(r)
    import os
    assert "MITAS_RUN_ROOT" not in os.environ, "üretim modunda env-köprüsü KURULMAZ"
