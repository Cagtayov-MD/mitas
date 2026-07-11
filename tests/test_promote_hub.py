# -*- coding: utf-8 -*-
"""İP-6 promotion/demote transaction testleri (2026-07-11, plan rev.4 + qwen/GLM İP-6-turu).
Kapsam: HARD-GATE (dolu→boş RED + allow-remove insan-onaylı) · AMBIGUOUS_HUB · dry-run dokunmaz ·
apply uçtan-uca (archive+promote+rebase+journal DONE) · crash-injection (PROMOTING-yarım →
startup_recovery güvenli-tamamlar; belirsiz → HUMAN_LOCK, silme YOK) · demote (rebase dahil) ·
promotion manuel (approved_by zorunlu). Tümü tmp sahte-DB'de — üretime dokunmaz."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import promote_hub as ph  # noqa: E402

TRT = "1990-0001-1-0000-00-1"


def _hub_yap(kok: Path, ad: str, *, yonetmen=None, cast=None, karar="Kontrol") -> Path:
    h = kok / ad
    h.mkdir(parents=True)
    (h / "_DURUM.json").write_text(json.dumps(
        {"trt_id": TRT, "karar": karar, "yonetmen": yonetmen or [],
         "cast": cast or [], "title": "TEST FILM", "tur": "DRAM",
         "hub": str(h)}), encoding="utf-8")
    (h / "clip.json").write_text(json.dumps({"source_path": str(h / "source" / "x.mp4")}),
                                 encoding="utf-8")
    (h / "pdf").mkdir(exist_ok=True)
    (h / "pdf" / "kunye.pdf").write_bytes(b"%PDF-sahte")   # teslim-tamlik kapisi icin
    return h


@pytest.fixture()
def sahte_db(tmp_path, monkeypatch):
    db = tmp_path / "Database"
    db.mkdir()
    monkeypatch.setattr(ph.mitas_roots, "resolve", lambda rr=None: {"DB_ROOT": db})
    monkeypatch.setattr(ph, "quiesce_check", lambda hub: [])   # test-ortamı: handle taraması kapalı
    return db


def test_dry_run_dokunmaz(sahte_db, tmp_path):
    canon = _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=["Eski Yon"])
    cand = _hub_yap(tmp_path / "cand", f"TEST FILM {TRT}", yonetmen=["Yeni Yon"])
    plan = ph.promote(cand, apply=False)
    assert plan["apply"] is False and canon.exists() and cand.exists()
    assert any(f["alan"] == "yonetmen" for f in plan["diff"]["fark"])


def test_hard_gate_dolu_bos_red(sahte_db, tmp_path):
    _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=["Gercek Yon"])
    cand = _hub_yap(tmp_path / "cand", f"TEST FILM {TRT}", yonetmen=[])
    with pytest.raises(ph.PromoteError, match="HARD-GATE"):
        ph.promote(cand, apply=True, approved_by="test")


def test_hard_gate_allow_remove_insan_onayli(sahte_db, tmp_path):
    _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=["Gercek Yon"])
    cand = _hub_yap(tmp_path / "cand", f"TEST FILM {TRT}", yonetmen=[])
    j = ph.promote(cand, apply=True, approved_by="cagatay", allow_remove=["yonetmen"])
    assert j["state"] == "DONE"


def test_apply_uctan_uca_archive_promote_journal(sahte_db, tmp_path):
    canon = _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=["Eski Yon"])
    cand = _hub_yap(tmp_path / "cand", f"TEST FILM {TRT}", yonetmen=["Yeni Yon"])
    j = ph.promote(cand, apply=True, approved_by="cagatay")
    assert j["state"] == "DONE"
    yeni = json.loads((canon / "_DURUM.json").read_text(encoding="utf-8"))
    assert yeni["yonetmen"] == ["Yeni Yon"], "canonical artık candidate içeriği"
    arch = sahte_db / "_archive" / TRT
    assert any(arch.iterdir()), "eski canonical arşivde (SİLİNMEDİ)"
    assert not cand.exists(), "candidate taşındı (kopya değil)"
    assert '" (n)"' not in [d.name for d in sahte_db.iterdir()]  # ikinci aktif hub yok


def test_ambiguous_hub_hard_fail(sahte_db, tmp_path):
    _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=["A"])
    _hub_yap(sahte_db, f"TEST FILM {TRT} 2", yonetmen=["B"])
    cand = _hub_yap(tmp_path / "cand", f"TEST FILM {TRT}", yonetmen=["C"])
    with pytest.raises(ph.PromoteError, match="AMBIGUOUS_HUB"):
        ph.promote(cand, apply=True, approved_by="x")


def test_manuel_onay_zorunlu(sahte_db, tmp_path):
    _hub_yap(sahte_db, f"TEST FILM {TRT}")
    cand = _hub_yap(tmp_path / "cand", f"TEST FILM {TRT}")
    with pytest.raises(ph.PromoteError, match="MANUEL"):
        ph.promote(cand, apply=True, approved_by="")


def test_crash_promoting_yarim_recovery_tamamlar(sahte_db, tmp_path):
    """Crash-injection: arşivleme bitti, PROMOTING yarım (candidate yerinde, canonical yok)."""
    cand = _hub_yap(tmp_path / "cand", f"TEST FILM {TRT}", yonetmen=["Yeni"])
    jdir = sahte_db / "_promotion_journal"
    jdir.mkdir()
    (jdir / f"{TRT}.journal.json").write_text(json.dumps({
        "trt": TRT, "state": "PROMOTING", "candidate": str(cand),
        "canonical": str(sahte_db / f"TEST FILM {TRT}"),
        "archive": str(sahte_db / "_archive" / TRT / "eski")}), encoding="utf-8")
    rapor = ph.startup_recovery(sahte_db)
    assert any("TAMAMLANDI" in r for r in rapor)
    assert (sahte_db / f"TEST FILM {TRT}" / "_DURUM.json").exists()
    j = json.loads((jdir / f"{TRT}.journal.json").read_text(encoding="utf-8"))
    assert j["state"] == "DONE"


def test_crash_belirsiz_human_lock_silme_yok(sahte_db, tmp_path):
    """Belirsiz yarım-durum → HUMAN_LOCK; script HİÇBİR dosyaya dokunmaz (qwen kuralı)."""
    canon = _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=["Eski"])
    jdir = sahte_db / "_promotion_journal"
    jdir.mkdir()
    (jdir / f"{TRT}.journal.json").write_text(json.dumps({
        "trt": TRT, "state": "ARCHIVING", "candidate": str(tmp_path / "yok"),
        "canonical": str(canon), "archive": str(sahte_db / "_archive" / TRT / "x")}),
        encoding="utf-8")
    once = sorted(p.name for p in sahte_db.rglob("*"))
    rapor = ph.startup_recovery(sahte_db)
    assert any("İNSAN-KİLİDİ" in r for r in rapor)
    j = json.loads((jdir / f"{TRT}.journal.json").read_text(encoding="utf-8"))
    assert j["state"] == "HUMAN_LOCK"
    sonra = sorted(p.name for p in sahte_db.rglob("*"))
    assert once == sonra, "belirsiz durumda dosya sistemi DEĞİŞMEZ"


def test_demote_geri_alir_rebase_dahil(sahte_db, tmp_path):
    canon = _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=["Eski Yon"])
    cand = _hub_yap(tmp_path / "cand", f"TEST FILM {TRT}", yonetmen=["Yeni Yon"])
    ph.promote(cand, apply=True, approved_by="cagatay")
    j = ph.demote(TRT, approved_by="cagatay")
    assert j["state"] == "DONE"
    geri = json.loads((canon / "_DURUM.json").read_text(encoding="utf-8"))
    assert geri["yonetmen"] == ["Eski Yon"], "demote eski sürümü geri getirdi"
    assert "demoted_canonical_to" in j, "yeni sürüm de arşivde (SİLİNMEDİ)"


def test_arsiv_gc_silmez_aday_raporlar(sahte_db, tmp_path):
    """ARCHIVE_MAX_SURUM aşımı: silme YOK, gc-adayı journal'a yazılır (silme-yasak kanunu)."""
    for i in range(4):
        _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=[f"Y{i}"]) if i == 0 else None
        cand = _hub_yap(tmp_path / f"cand{i}", f"TEST FILM {TRT}", yonetmen=[f"Y{i+1}"])
        ph.promote(cand, apply=True, approved_by="cagatay")
    arch = sahte_db / "_archive" / TRT
    assert len(list(arch.iterdir())) == 4, "hiçbir arşiv-sürümü silinmedi"
    j = json.loads((sahte_db / "_promotion_journal" / f"{TRT}.journal.json").read_text(encoding="utf-8"))
    assert j.get("gc_adayi"), "aşım gc-adayı olarak raporlandı"


def test_teslim_tamlik_iskelet_aday_red(sahte_db, tmp_path):
    """Opus akış-incelemesi: yalnız ocr/ içeren LEAN-iskelet aday, TAM kanoniği değiştiremez."""
    _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=["Eski"])
    iskelet = tmp_path / "cand" / f"TEST FILM {TRT}"
    (iskelet / "ocr" / "ocr-x").mkdir(parents=True)
    (iskelet / "ocr" / "ocr-x" / "kunye.txt").write_text("x", encoding="utf-8")
    (iskelet / "_DURUM.json").write_text(json.dumps({"karar": "Hazır"}), encoding="utf-8")
    with pytest.raises(ph.PromoteError, match="TESLİM-TAMLIK"):
        ph.promote(iskelet, apply=False)   # dry-run bile RED — yanlış-güven verilmesin
