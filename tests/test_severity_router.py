# -*- coding: utf-8 -*-
"""İP-4 router + karar-sözleşmesi testleri (2026-07-11, plan rev.4) — GERÇEK production import.
Kapsam: (1) AFIS warning-nonblocking; diğer 6 hafif kod KONTROL davranışını korur;
(2) write_pipeline_karar şema+dosya sözleşmesi (human'a dokunmaz, view regenerate);
(3) TECHNICAL_FAILURE → RETRYABLE_FAILURE + first_blocker; (4) drift tespiti."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import credit_severity_router as router  # noqa: E402


# ── classify: üç tier ────────────────────────────────────────────────────────
def test_temiz_onayli():
    r = router.classify({"cast_count": 8})
    assert r["tier"] == "TEMIZ" and r["folder"] == "ONAYLI"


def test_agir_kontrol_oncelik_yonetmen():
    r = router.classify({"cast_count": 8, "yon_garble": True, "ozet_missing": True})
    assert r["tier"] == "KONTROL" and r["folder"] == "KONTROL"
    assert r["kontrol_tip"].startswith("YONETMEN"), "öncelik: YONETMEN en temel"


HAFIF_SENARYOLAR = {
    "AFIS": {"afis_missing": True},
    "CASING": {"casing_bad": True},
    "GENRE": {"genre_format": True},
    "KEYWORD": {"keyword_desync": True},
    "OZET_STIL": {"ozet_dateintro": True},
    "YAP_FILL": {"yap_missing": True, "yap_fillable": True},
    "CAST_CAP_DUSEN": {"cast_cap_dusen": True},
}


def test_insan_kontrollu_6_hafif_kod_asla_temiz_dusmez():
    """AFIS dışındaki hafif kodlar mevcut insan-kontrolü davranışını korur."""
    for kod, sig in HAFIF_SENARYOLAR.items():
        if kod == "AFIS":
            continue
        r = router.classify({"cast_count": 8, **sig})
        assert r["tier"] == "NEEDS_REVIEW_HAFIF", f"{kod}: tier={r['tier']}"
        assert r["folder"] == "KONTROL", f"{kod}: sessiz-TEMIZ YASAK"
        assert kod in r["hafif"], f"{kod} hafif listesinde değil: {r['hafif']}"
        assert kod in router.HAFIF_GECIS, f"{kod} geçiş-tablosunda tanımsız"


def test_afis_only_warning_nonblocking_onayli():
    r = router.classify({"cast_count": 8, "afis_missing": True})
    assert r["tier"] == "TEMIZ"
    assert r["folder"] == "ONAYLI"
    assert r["kontrol_tip"] is None
    assert r["hafif"] == ["AFIS"], "warning görünürlüğü kaybolmamalı"


def test_afis_baska_hafif_veya_agir_sorunu_maskelemez():
    r = router.classify({"cast_count": 8, "afis_missing": True, "genre_format": True})
    assert r["tier"] == "NEEDS_REVIEW_HAFIF" and r["kontrol_tip"] == "HAFIF_GENRE"
    assert set(r["hafif"]) == {"AFIS", "GENRE"}
    r2 = router.classify({"cast_count": 8, "afis_missing": True, "yon_garble": True})
    assert r2["tier"] == "KONTROL" and "AFIS" in r2["hafif"]


# ── karar.pipeline.json gölge-yazımı ─────────────────────────────────────────
def _route_ornek():
    return router.classify({"cast_count": 8, "yon_garble": True, "afis_missing": True})


def test_shadow_yazim_sema_ve_dosyalar(tmp_path):
    obj = router.write_pipeline_karar(
        tmp_path, _route_ornek(), karar="Kontrol",
        reasons=["yönetmen okunamadı"], qwen_uyari=["afiş yok"],
        extraction_status="OK", run_id="r123")
    for alan in ("schema_version", "gate_version", "processing_status", "proposed_review_status",
                 "tier", "first_blocker", "blocking_reason_codes", "warning_codes",
                 "evidence_refs", "extraction_status", "karar_durum_esleme"):
        assert alan in obj, alan
    assert obj["processing_status"] == "SUCCEEDED"
    assert obj["proposed_review_status"] == "NEEDS_REVIEW"
    assert obj["first_blocker"] == "YONETMEN"
    assert "AFIS" in obj["warning_codes"]
    assert (tmp_path / "karar.pipeline.json").exists()
    assert (tmp_path / "karar.view.json").exists()
    assert not (tmp_path / "karar.human.json").exists(), "pipeline HUMAN dosyası OLUŞTURAMAZ"


def test_shadow_tf_retryable_ve_first_blocker(tmp_path):
    obj = router.write_pipeline_karar(
        tmp_path, _route_ornek(), karar="Kontrol",
        extraction_status="TECHNICAL_FAILURE", run_id="r1")
    assert obj["processing_status"] == "RETRYABLE_FAILURE"
    assert obj["first_blocker"] == "TEKNIK_ARIZA_EXTRACTION"


def test_shadow_temiz_auto_approved(tmp_path):
    r = router.classify({"cast_count": 8})
    obj = router.write_pipeline_karar(tmp_path, r, karar="Hazır", extraction_status="OK")
    assert obj["proposed_review_status"] == "AUTO_APPROVED"
    assert obj["blocking_reason_codes"] == []


def test_view_human_yanyana_ve_regenerate(tmp_path):
    (tmp_path / "karar.human.json").write_text(
        json.dumps({"disposition": "ONAYLADIM", "lock": {"owner": "human"}}), encoding="utf-8")
    router.write_pipeline_karar(tmp_path, _route_ornek(), karar="Kontrol")
    view = json.loads((tmp_path / "karar.view.json").read_text(encoding="utf-8"))
    assert view["pipeline"]["tier"] == "KONTROL"
    assert view["human"]["disposition"] == "ONAYLADIM", "human alanı view'de yan-yana korunur"
    # human dosyası pipeline yazımından ETKİLENMEDİ
    h = json.loads((tmp_path / "karar.human.json").read_text(encoding="utf-8"))
    assert h["lock"]["owner"] == "human"


# ── drift ────────────────────────────────────────────────────────────────────
def test_drift_yokken_none(tmp_path):
    (tmp_path / "_DURUM.json").write_text(json.dumps({"karar": "Kontrol"}), encoding="utf-8")
    router.write_pipeline_karar(tmp_path, _route_ornek(), karar="Kontrol")
    assert router.check_drift(tmp_path) is None


def test_drift_baska_yazar_degistirince_yakalanir(tmp_path):
    (tmp_path / "_DURUM.json").write_text(json.dumps({"karar": "Kontrol"}), encoding="utf-8")
    router.write_pipeline_karar(tmp_path, _route_ornek(), karar="Kontrol")
    (tmp_path / "_DURUM.json").write_text(json.dumps({"karar": "Hazır"}), encoding="utf-8")
    d = router.check_drift(tmp_path)
    assert d and "DRIFT" in d
