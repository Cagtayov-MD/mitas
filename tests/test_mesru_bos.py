# -*- coding: utf-8 -*-
"""İP-9 MESRU_BOS 6-durum + mühür testleri (2026-07-11, plan rev.4).
Kritik sözleşmeler: OCR-boş TEK BAŞINA terminal-mühür VERMEZ (VL şart); C_OKUNAMAZ otomatik
TEKNIK_ARIZA DEĞİL; framede-net-ama-OCR-çöp → OCR_MISSED_VISIBLE_TEXT (retry, terminal değil);
mühür yeni-kanıtta (hash değişince) geçersiz (grandfather yok)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mesru_bos as mb  # noqa: E402


# ── sınıflandırıcı ───────────────────────────────────────────────────────────
def test_ocr_bos_vl_yok_terminal_degil_vl_bekler():
    r = mb.classify_field(ocr_empty=True, legibility="unknown", vl_verdict=None)
    assert r["needs_vl"] is True
    assert r["terminal"] is False, "VL'siz terminal-mühür YASAK (OCR tek başına yetkisiz)"


def test_framede_net_ama_ocr_cop_teknik_ariza():
    """En kritik ayrım: legibility high + VL metin-var → OCR kaçırdı = TEKNIK_ARIZA, meşru-boş DEĞİL."""
    r = mb.classify_field(ocr_empty=True, legibility="high", vl_verdict="has_text")
    assert r["durum"] == mb.OCR_MISSED_VISIBLE_TEXT
    assert r["terminal"] is False and r["durum"] in mb.RETRYABLE


def test_kredi_yok_okunabilir_source_absent_terminal():
    r = mb.classify_field(ocr_empty=True, legibility="high", vl_verdict="no_text")
    assert r["durum"] == mb.SOURCE_ABSENT and r["terminal"] is True


def test_rol_yok_ama_jenerik_var_role_absent_terminal():
    r = mb.classify_field(ocr_empty=True, legibility="high", vl_verdict="role_absent")
    assert r["durum"] == mb.ROLE_ABSENT and r["terminal"] is True


def test_c_okunamaz_otomatik_teknik_ariza_degil():
    """Şartname: metin-yok + düşük-okunabilirlik → kaynak-okunamaz (retry), TEKNIK_ARIZA DEĞİL."""
    r = mb.classify_field(ocr_empty=True, legibility="low", vl_verdict="no_text")
    assert r["durum"] == mb.SOURCE_UNREADABLE
    assert r["durum"] != mb.OCR_MISSED_VISIBLE_TEXT


def test_frame_coverage_gap_evidence_insufficient():
    r = mb.classify_field(ocr_empty=True, legibility="high", vl_verdict=None, coverage_ok=False)
    assert r["durum"] == mb.EVIDENCE_INSUFFICIENT and r["terminal"] is False


def test_policy_not_applicable_terminal():
    r = mb.classify_field(ocr_empty=True, legibility="unknown", vl_verdict=None, policy_na=True)
    assert r["durum"] == mb.NOT_APPLICABLE and r["terminal"] is True


def test_ocr_dolu_kapsam_disi():
    r = mb.classify_field(ocr_empty=False, legibility="high", vl_verdict=None)
    assert r["terminal"] is False and r["durum"] == "NOT_EMPTY"


# ── mühür ───────────────────────────────────────────────────────────────────
def test_muhur_yalniz_terminal_ve_insan_onayli():
    with pytest.raises(ValueError, match="terminal"):
        mb.make_seal(trt="t", field="YONETMEN", durum=mb.SOURCE_UNREADABLE,
                     source_hash="s", evidence_hash="e", approved_by="x")
    with pytest.raises(ValueError, match="approved_by"):
        mb.make_seal(trt="t", field="YONETMEN", durum=mb.SOURCE_ABSENT,
                     source_hash="s", evidence_hash="e", approved_by="")


def test_muhur_yeni_kanitta_gecersiz_grandfather_yok():
    seal = mb.make_seal(trt="1990-0001-1-0000-00-1", field="YONETMEN", durum=mb.SOURCE_ABSENT,
                        source_hash="src1", evidence_hash="ev1", approved_by="cagatay")
    assert mb.is_seal_valid(seal, current_source_hash="src1", current_evidence_hash="ev1")
    # yeni frame → source_hash değişti → mühür GEÇERSİZ (yeniden-kapıdan geçer)
    assert not mb.is_seal_valid(seal, current_source_hash="src2", current_evidence_hash="ev1")
    assert not mb.is_seal_valid(seal, current_source_hash="src1", current_evidence_hash="ev2")


def test_muhur_bos_gecersiz():
    assert mb.is_seal_valid({}, current_source_hash="a", current_evidence_hash="b") is False


def test_muhur_kimlik_alanlari_ve_seal_id_tahrif_edilemez():
    seal = mb.make_seal(trt="1990-0001-1-0000-00-1", field="YONETMEN",
                        durum=mb.ROLE_ABSENT, source_hash="src", evidence_hash="ev",
                        approved_by="cagatay")
    assert mb.is_seal_valid(seal, current_source_hash="src", current_evidence_hash="ev",
                            expected_trt=seal["trt"], expected_field="YONETMEN")
    for key, bad in (("trt", "baska"), ("field", "CAST"),
                     ("durum", mb.SOURCE_UNREADABLE), ("approved_by", ""),
                     ("seal_id", "sahte")):
        changed = dict(seal)
        changed[key] = bad
        assert not mb.is_seal_valid(changed, current_source_hash="src",
                                    current_evidence_hash="ev")


# ── KOKNEDEN köprüsü ─────────────────────────────────────────────────────────
def test_d_jenerikte_yok_hepsi_vl_gerektirir():
    m = mb.from_kokneden_verdict("D_JENERIKTE_YOK", "jenerikte hiç mevcut değil", "")
    assert m["on_durum"] == mb.ROLE_ABSENT and m["needs_vl"] is True


def test_c_okunamaz_source_unreadable_vl_gerek():
    m = mb.from_kokneden_verdict("C_OKUNAMAZ", "bulanık kare", "")
    assert m["on_durum"] == mb.SOURCE_UNREADABLE and m["needs_vl"] is True
