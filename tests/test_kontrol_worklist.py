# -*- coding: utf-8 -*-
"""İP-8 kontrol_worklist testleri (2026-07-11, plan rev.4).
Sahte KONTROL export + Database ile kova-sınıflandırmasını doğrular (canlı-veri değil, izole).
Kritik: TRIAJ_HAZIR koşulu (karar=Kontrol & yönetmen+≥2oyuncu+özet dolu) + çift-PDF + hub-yok."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kontrol_worklist as kw  # noqa: E402


@pytest.fixture()
def sahte(tmp_path, monkeypatch):
    db = tmp_path / "Database"
    kontrol = tmp_path / "export" / "KONTROL"
    db.mkdir(parents=True)
    kontrol.mkdir(parents=True)
    monkeypatch.setattr(kw.mitas_roots, "resolve",
                        lambda rr=None: {"DB_ROOT": db, "KONTROL": kontrol})
    return db, kontrol


def _film(db, kontrol, trt, ad, *, durum, pdf_sayi=1, ocr_status="done", asr_status="done",
          frames=True, kunye=True):
    for i in range(pdf_sayi):
        (kontrol / f"{trt} {ad}{'' if i == 0 else f' v{i}'}.pdf").write_text("x", encoding="utf-8")
    hub = db / f"{ad} {trt}"
    hub.mkdir()
    (hub / "_DURUM.json").write_text(json.dumps({**durum, "trt_id": trt}), encoding="utf-8")
    (hub / "clip.json").write_text(json.dumps(
        {"modules": {"ocr": {"status": ocr_status}, "asr": {"status": asr_status}}}), encoding="utf-8")
    if frames:
        (hub / "frames").mkdir()
    if kunye:
        oj = hub / "ocr" / "ocr-abc"
        oj.mkdir(parents=True)
        (oj / "kunye.txt").write_text("...", encoding="utf-8")
    return hub


def test_triaj_hazir_36_sinifi(sahte):
    db, kontrol = sahte
    _film(db, kontrol, "1990-0001-1-0000-00-1", "DOLU FILM",
          durum={"karar": "Kontrol", "neden": ["kimlik çelişkisi"],
                 "qwen_qc": {"yonetmen_var": True, "oyuncu_sayisi": 5, "ozet_var": True}})
    wl = kw.build_worklist()
    assert wl["ozet"].get("TRIAJ_HAZIR") == 1
    assert wl["kovalar"]["TRIAJ_HAZIR"][0]["trt"] == "1990-0001-1-0000-00-1"


def test_eksik_alan_triaj_disi(sahte):
    db, kontrol = sahte
    # özet yok → TRIAJ_HAZIR değil
    _film(db, kontrol, "1990-0002-1-0000-00-1", "EKSIK FILM",
          durum={"karar": "Kontrol", "qwen_qc": {"yonetmen_var": True, "oyuncu_sayisi": 5, "ozet_var": False}})
    wl = kw.build_worklist()
    assert wl["ozet"].get("TRIAJ_HAZIR", 0) == 0


def test_asr_failed_kovasi(sahte):
    db, kontrol = sahte
    _film(db, kontrol, "1990-0003-1-0000-00-1", "ASR FAIL", asr_status="failed",
          durum={"karar": "Kontrol", "qwen_qc": {}})
    wl = kw.build_worklist()
    assert wl["ozet"].get("TEKNIK_ARIZA_ASR") == 1


def test_ocr_kunye_yok_teknik_ariza(sahte):
    db, kontrol = sahte
    _film(db, kontrol, "1990-0004-1-0000-00-1", "OCR YOK", ocr_status="partial", kunye=False,
          durum={"karar": "Kontrol", "qwen_qc": {}})
    wl = kw.build_worklist()
    assert wl["ozet"].get("TEKNIK_ARIZA_OCR") == 1


def test_hub_yok(sahte):
    db, kontrol = sahte
    (kontrol / "1990-0005-1-0000-00-1 HUBSUZ.pdf").write_text("x", encoding="utf-8")
    wl = kw.build_worklist()
    assert wl["ozet"].get("HUB_YOK") == 1


def test_cift_pdf(sahte):
    db, kontrol = sahte
    _film(db, kontrol, "1990-0006-1-0000-00-1", "CIFT", pdf_sayi=2,
          durum={"karar": "Kontrol", "qwen_qc": {}})
    wl = kw.build_worklist()
    assert wl["ozet"].get("CIFT_PDF") == 1


def test_ambiguous_hub(sahte):
    db, kontrol = sahte
    _film(db, kontrol, "1990-0007-1-0000-00-1", "AMB", durum={"karar": "Kontrol", "qwen_qc": {}})
    # ikinci hub aynı TRT
    h2 = db / "AMB 1990-0007-1-0000-00-1 2"
    h2.mkdir()
    (h2 / "_DURUM.json").write_text("{}", encoding="utf-8")
    wl = kw.build_worklist()
    assert wl["ozet"].get("AMBIGUOUS_HUB") == 1
