# -*- coding: utf-8 -*-
"""KONTROL kuyruğundaki beş raporlanmış film için kök-neden regresyonları."""
import importlib.util
import os
import sys
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import credit_crosscheck as cc  # noqa: E402
import credit_severity_router as router  # noqa: E402
import credit_text_read as ctr  # noqa: E402
import credit_video_read as cvr  # noqa: E402


def _load_tek_film_kunye():
    path = SCRIPTS / "tek_film_kunye.py"
    spec = importlib.util.spec_from_file_location(f"tek_film_kunye_five_{uuid.uuid4().hex}", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("film", ["BÜYÜK MÜCADELE", "BİR ZAMANLAR"])
def test_afis_only_filmler_onayli_uyariyla_gecer(film):
    route = router.classify({"cast_count": 10, "afis_missing": True})
    assert route["tier"] == "TEMIZ", film
    assert route["folder"] == "ONAYLI", film
    assert route["hafif"] == ["AFIS"], film


def test_deniz_ejderi_nordik_isim_iki_okuyucuda_ayni_katlanir():
    kb = "Ágúst Guðmundsson"
    assert cvr.fold(kb) == "agust gudmundsson"
    assert cc.fold(kb) == "agust gudmundsson"
    assert cc.name_close("AUGUST GUDMUNDSSON", kb)
    # NFKD'nin tek başına düşürdüğü diğer Latin harfler de ortak sözleşmede sabit.
    assert cc.fold("Þór Østergård, L'œuvre, Weiß") == "thor ostergard  l oeuvre  weiss"


def test_bana_trinity_derler_exact_ekran_mahlasi_guclu_kanittir():
    mod = _load_tek_film_kunye()
    vc = {
        "yonetmen": ["E. B. CLUCHER"],
        "vl_yon_eslesme": {"E. B. CLUCHER": {"method": "exact", "kanit": "e. b. clucher"}},
    }
    evidence = mod._strong_director_screen_evidence("E.B. Clucher", vc)
    assert evidence and evidence["method"] == "exact"
    # Fuzzy ve salt KB-anchor mahlas koruma kapısını açamaz.
    vc["vl_yon_eslesme"]["E. B. CLUCHER"]["method"] = "fuzzy"
    assert mod._strong_director_screen_evidence("E.B. Clucher", vc) is None


def test_apollo_11_unit_copu_reddedilir_gercek_yonetmen_raw_ocrdan_restore_edilir(tmp_path):
    mod = _load_tek_film_kunye()
    for junk in ("ND UNIT", "2ND UNIT", "SECOND UNIT", "UNIT DIRECTOR", "ASSISTANT DIRECTOR"):
        assert ctr._rsc_name_ok(junk) is False

    ocr = tmp_path / "ocr" / "ocr-apollo"
    ocr.mkdir(parents=True)
    (ocr / "kunye.txt").write_text(
        "NORBERTO BARBA\n2ND UNIT DIRECTOR\nND UNIT\n", encoding="utf-8")
    assert mod._ocr_corroborated_directors(["Norberto Barba"], str(tmp_path)) == ["Norberto Barba"]
    assert mod._ocr_corroborated_directors(["Unseen Director"], str(tmp_path)) == []


def test_candidate_afis_cache_env_ile_productiondan_ayrilir(monkeypatch, tmp_path):
    candidate_cache = tmp_path / "candidate" / "_102_afis_cache"
    monkeypatch.setenv("MITAS_AFIS_CACHE_DIR", str(candidate_cache))
    mod = _load_tek_film_kunye()
    assert Path(mod.AFIS_CACHE) == candidate_cache
    assert Path(mod.AFIS_CACHE) != Path(r"E:\MITAS\_102_afis_cache")


def test_deniz_ejderi_kimlik_dogru_ocr_yazim_varyanti_celiski_saymaz():
    """DENİZ EJDERİ C-fix (2026-07-12): kimlik cast-çapasıyla (cast_ov>=2) yön'den BAĞIMSIZ
    kurulabilir → kimlik_dogru=True TEK BAŞINA verdict=ÇELİŞKİ'yi aklamaz. OCR-yönetmeni KB'ye
    name_close (yazım varyantı) ise yanlış-film DEĞİL; name_close patlarsa (gerçek farklı yönetmen /
    remake tuzağı) contradiction KORUNUR. Konsey: A çok açar, C güvenli koridor."""
    import mitas_pipeline as mp  # noqa: E402

    # DENİZ: OCR 'AUGUST GUDMUNDSSON' ~ KB 'Ágúst Guðmundsson' → name_close TRUE → yanlış-film DEĞİL
    deniz = {"kimlik_dogru": True, "verdict": "ÇELİŞKİ", "yon_name_close": True}
    assert mp._has_identity_contradiction(deniz) is False

    # REMAKE tuzağı: cast örtüştü (kimlik_dogru=True) ama yönetmen GERÇEKTEN farklı (name_close=False)
    # → kimlik_dogru=True OLMASINA RAĞMEN contradiction KORUNUR (A seçeneğinin maskeleme riski kapalı).
    remake = {"kimlik_dogru": True, "verdict": "ÇELİŞKİ", "yon_name_close": False}
    assert mp._has_identity_contradiction(remake) is True

    # kimlik_dogru=False → her hâlükârda contradiction (fuzzy katman bile farklı-kişi dedi).
    assert mp._has_identity_contradiction({"kimlik_dogru": False, "verdict": "ÇELİŞKİ"}) is True

    # verdict=TEYİT → hiçbir zaman contradiction (yön exact-eşleşti).
    assert mp._has_identity_contradiction({"kimlik_dogru": True, "verdict": "TEYİT"}) is False

    # Güçlü ekran-mahlas/AKA istisnası korunur: kimlik_dogru=True + ÇELİŞKİ + name_close=False AMA
    # güçlü ekran-rol kanıtlı ad-farkı → blocker değil (mevcut _is_strong_screen_alias_conflict precedent).
    alias = {"kimlik_dogru": True, "verdict": "ÇELİŞKİ", "yon_name_close": False,
             "yon_screen_conflict": [{"okunan": "X", "ekran_kaniti": "directed by X"}]}
    assert mp._has_identity_contradiction(alias) is False
