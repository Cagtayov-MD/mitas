import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import mitas_pipeline as mp  # noqa: E402


def _clean_v4():
    return {
        "v4": {
            "yonetmen": ["JEAN-LUC GODARD"],
            "cast": 10,
            "cast_list": [
                "MARUSCHKA DETMERS", "JACQUES BONNAFFE", "MYRIEM ROUSSEL",
                "CHRISTOPHE ODENT", "PIERRE-ALAIN CHAPUIS",
            ],
            "cast_garble_lex_count": 0,
            "yon_garble_lex": False,
            "qc_block_gerekceler": ["özet yok/kısa (5 kelime / placeholder)"],
            "qc_block_floor": {"hedef": 6, "ulasilan": 10, "kabul": True},
            "qc_block_otorite_audit": {"ocr_authority_violation": False},
        },
        "adimlar": {
            "cross_check": {
                "verdict": "TEYİT",
                "kimlik_dogru": True,
                "cast_ortusme": 9,
                "cast_garble": False,
            },
            "qc_block": {
                "gerekceler": ["özet yok/kısa (5 kelime / placeholder)"],
                "floor": {"hedef": 6, "ulasilan": 10, "kabul": True},
            },
        },
    }


def test_gozden_gecir_relaxes_when_final_v4_is_clean_and_locked():
    assert mp._ocr_bucket_can_be_warning("GOZDEN_GECIR", _clean_v4()) is True


def test_gozden_gecir_stays_hard_when_final_v4_has_identity_reason():
    report = _clean_v4()
    report["v4"]["qc_block_gerekceler"] = ["kimlik kurulamadı (cast-örtüşmesi 0) / yanlış-film şüphesi"]
    assert mp._ocr_bucket_can_be_warning("GOZDEN_GECIR", report) is False


def test_only_gozden_gecir_bucket_is_relaxed():
    assert mp._ocr_bucket_can_be_warning("DUSUK", _clean_v4()) is False
