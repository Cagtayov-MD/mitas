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


def _hub_yap(kok: Path, ad: str, *, yonetmen=None, cast=None, karar="Kontrol",
             trt=TRT, run_id="parent-run") -> Path:
    h = kok / ad
    h.mkdir(parents=True)
    pdf = h / "pdf" / "kunye.pdf"
    pdf.parent.mkdir(exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4\nTEST\n%%EOF")
    (h / "_DURUM.json").write_text(json.dumps(
        {"trt_id": trt, "karar": karar, "yonetmen": yonetmen or [],
          "cast": cast or [], "title": "TEST FILM", "tur": "DRAM",
         "hub": str(h), "pdf": str(pdf), "extraction_status": "OK"}), encoding="utf-8")
    (h / "clip.json").write_text(json.dumps(
        {"source_path": str(h / "source" / "x.mp4"), "trt_id": trt}),
                                  encoding="utf-8")
    (h / "run_manifest.json").write_text(json.dumps(
        {"run_id": run_id, "status": karar, "finished_at": "2026-07-12T00:00:00",
         "git_dirty": False, "source_drift": False,
         "input": {"kind": "video", "sig_sha256": "a" * 64},
         "config_snapshot": {}}), encoding="utf-8")
    return h


def _candidate_yap(tmp_path: Path, ad: str, *, yonetmen=None, cast=None,
                   karar="Kontrol", run="run-1", trt=TRT) -> Path:
    run_root = tmp_path / "candidate_runs" / run
    h = _hub_yap(run_root / "Database", ad, yonetmen=yonetmen, cast=cast,
                 karar=karar, trt=trt, run_id="candidate-run")
    bucket = "ONAYLI" if karar == "Hazır" else "KONTROL"
    teslim = run_root / "export" / bucket / f"{trt} TEST.pdf"
    teslim.parent.mkdir(parents=True, exist_ok=True)
    teslim.write_bytes((h / "pdf" / "kunye.pdf").read_bytes())
    d = json.loads((h / "_DURUM.json").read_text(encoding="utf-8"))
    d["teslim"] = str(teslim)
    (h / "_DURUM.json").write_text(json.dumps(d), encoding="utf-8")
    m = json.loads((h / "run_manifest.json").read_text(encoding="utf-8"))
    m["config_snapshot"] = {"MITAS_RUN_ROOT": str(run_root)}
    (h / "run_manifest.json").write_text(json.dumps(m), encoding="utf-8")
    return h


@pytest.fixture()
def sahte_db(tmp_path, monkeypatch):
    db = tmp_path / "Database"
    db.mkdir()
    export = tmp_path / "production_export"
    roots = {"DB_ROOT": db, "EXPORT_ROOT": export,
             "HAZIR": export / "ONAYLI", "KONTROL": export / "KONTROL",
             "SPECIAL_GENRE_DIR": tmp_path / "special", "OUTPUTS_DIR": tmp_path / "outputs"}
    monkeypatch.setattr(ph.mitas_roots, "resolve_production", lambda: roots)
    monkeypatch.setattr(ph.mitas_roots, "CANDIDATE_ROOT", tmp_path / "candidate_runs")
    monkeypatch.setattr(ph, "quiesce_check", lambda hub: [])   # test-ortamı: handle taraması kapalı
    return db


def test_dry_run_dokunmaz(sahte_db, tmp_path):
    canon = _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=["Eski Yon"])
    cand = _candidate_yap(tmp_path, f"TEST FILM {TRT}", yonetmen=["Yeni Yon"])
    plan = ph.promote(cand, apply=False)
    assert plan["apply"] is False and canon.exists() and cand.exists()
    assert any(f["alan"] == "yonetmen" for f in plan["diff"]["fark"])


def test_hard_gate_dolu_bos_red(sahte_db, tmp_path):
    _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=["Gercek Yon"])
    cand = _candidate_yap(tmp_path, f"TEST FILM {TRT}", yonetmen=[])
    with pytest.raises(ph.PromoteError, match="HARD-GATE"):
        ph.promote(cand, apply=True, approved_by="test")


def test_hard_gate_allow_remove_insan_onayli(sahte_db, tmp_path):
    _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=["Gercek Yon"])
    cand = _candidate_yap(tmp_path, f"TEST FILM {TRT}", yonetmen=[])
    j = ph.promote(cand, apply=True, approved_by="cagatay", allow_remove=["yonetmen"])
    assert j["state"] == "DONE"


def test_apply_uctan_uca_archive_promote_journal(sahte_db, tmp_path):
    canon = _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=["Eski Yon"])
    cand = _candidate_yap(tmp_path, f"TEST FILM {TRT}", yonetmen=["Yeni Yon"])
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
    cand = _candidate_yap(tmp_path, f"TEST FILM {TRT}", yonetmen=["C"])
    with pytest.raises(ph.PromoteError, match="AMBIGUOUS_HUB"):
        ph.promote(cand, apply=True, approved_by="x")


def test_manuel_onay_zorunlu(sahte_db, tmp_path):
    _hub_yap(sahte_db, f"TEST FILM {TRT}")
    cand = _candidate_yap(tmp_path, f"TEST FILM {TRT}")
    with pytest.raises(ph.PromoteError, match="MANUEL"):
        ph.promote(cand, apply=True, approved_by="")


def test_crash_promoting_yarim_recovery_tamamlar(sahte_db, tmp_path):
    """Crash-injection: arşivleme bitti, PROMOTING yarım (candidate yerinde, canonical yok)."""
    cand = _candidate_yap(tmp_path, f"TEST FILM {TRT}", yonetmen=["Yeni"])
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
    cand = _candidate_yap(tmp_path, f"TEST FILM {TRT}", yonetmen=["Yeni Yon"])
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
        cand = _candidate_yap(tmp_path, f"TEST FILM {TRT}", yonetmen=[f"Y{i+1}"], run=f"run-{i}")
        ph.promote(cand, apply=True, approved_by="cagatay")
    arch = sahte_db / "_archive" / TRT
    assert len([p for p in arch.iterdir() if p.is_dir() and not p.name.startswith("_")]) == 4, \
        "hiçbir hub arşiv-sürümü silinmedi"
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


def test_candidate_parent_disinda_promote_red(sahte_db, tmp_path):
    cand = _hub_yap(tmp_path / "rastgele", f"TEST FILM {TRT}")
    with pytest.raises(ph.PromoteError, match="CANDIDATE-PARENT"):
        ph.promote(cand, apply=False)


@pytest.mark.parametrize("alan,deger,mesaj", [
    ("git_dirty", True, "DIRTY-CANDIDATE"),
    ("source_drift", True, "SOURCE-DRIFT"),
])
def test_manifest_guvenlik_kapilari(sahte_db, tmp_path, alan, deger, mesaj):
    _hub_yap(sahte_db, f"TEST FILM {TRT}")
    cand = _candidate_yap(tmp_path, f"TEST FILM {TRT}")
    p = cand / "run_manifest.json"
    m = json.loads(p.read_text(encoding="utf-8")); m[alan] = deger
    p.write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ph.PromoteError, match=mesaj):
        ph.promote(cand, apply=False)


def test_export_ve_durum_tek_transactionda_uzlasir(sahte_db, tmp_path):
    canon = _hub_yap(sahte_db, f"TEST FILM {TRT}", karar="Kontrol")
    roots = ph.mitas_roots.resolve_production()
    for root_key, suffix in (("KONTROL", "eski-kontrol"), ("HAZIR", "eski-onayli")):
        p = roots[root_key] / f"{TRT} {suffix}.pdf"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"%PDF-1.4\nOLD\n%%EOF")
    cand = _candidate_yap(tmp_path, f"TEST FILM {TRT}", karar="Hazır")
    expected = (cand / "pdf" / "kunye.pdf").read_bytes()
    j = ph.promote(cand, apply=True, approved_by="test")
    new_delivery = Path(j["production_delivery"])
    assert new_delivery.parent == roots["HAZIR"] and new_delivery.read_bytes() == expected
    assert not list(roots["KONTROL"].glob(f"*{TRT}*"))
    assert len(j["export_moves"]) == 2
    assert all(Path(x["archive"]).exists() for x in j["export_moves"])
    durum = json.loads((canon / "_DURUM.json").read_text(encoding="utf-8"))
    assert Path(durum["teslim"]) == new_delivery
    assert Path(durum["hub"]) == canon


def test_from_hub_parent_run_ve_input_drift_red(sahte_db, tmp_path):
    import run_manifest
    canon = _hub_yap(sahte_db, f"TEST FILM {TRT}", run_id="parent-123")
    cand = _candidate_yap(tmp_path, f"TEST FILM {TRT}")
    p = cand / "run_manifest.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    m["input"] = run_manifest.hub_input_signature(canon)
    m["parent_run_id"] = "yanlis-parent"
    m["config_snapshot"]["MITAS_FROM_HUB"] = "1"
    p.write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ph.PromoteError, match="PARENT-RUN-DRIFT"):
        ph.promote(cand, apply=False)

    m["parent_run_id"] = "parent-123"
    p.write_text(json.dumps(m), encoding="utf-8")
    d = json.loads((canon / "_DURUM.json").read_text(encoding="utf-8"))
    d["title"] = "SONRADAN DEGISTI"
    (canon / "_DURUM.json").write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ph.PromoteError, match="INPUT-DRIFT"):
        ph.promote(cand, apply=False)


def test_atomic_lock_ikinci_sahibi_reddeder(tmp_path):
    p = tmp_path / "x.lock"
    ph.acquire_lock(p, "test")
    try:
        with pytest.raises(ph.PromoteError, match="kilidi dolu"):
            ph.acquire_lock(p, "test")
    finally:
        ph.release_lock(p)
    assert not p.exists()


def test_export_promoting_crash_recovery_tamamlar(sahte_db, tmp_path, monkeypatch):
    canon = _hub_yap(sahte_db, f"TEST FILM {TRT}", yonetmen=["Eski"])
    cand = _candidate_yap(tmp_path, f"TEST FILM {TRT}", yonetmen=["Yeni"])
    real_replace = ph._replace_backoff

    def _crash_export(src, dst, tries=5):
        if ".promotion." in Path(src).name:
            raise ph.PromoteError("crash-injection export swap")
        return real_replace(src, dst, tries)

    monkeypatch.setattr(ph, "_replace_backoff", _crash_export)
    with pytest.raises(ph.PromoteError, match="crash-injection"):
        ph.promote(cand, apply=True, approved_by="test")
    jp = sahte_db / "_promotion_journal" / f"{TRT}.journal.json"
    assert json.loads(jp.read_text(encoding="utf-8"))["state"] == "EXPORT_PROMOTING"
    assert json.loads((canon / "_DURUM.json").read_text(encoding="utf-8"))["yonetmen"] == ["Yeni"]

    monkeypatch.setattr(ph, "_replace_backoff", real_replace)
    rapor = ph.startup_recovery(sahte_db)
    j = json.loads(jp.read_text(encoding="utf-8"))
    assert j["state"] == "DONE" and any("TAMAMLANDI" in x for x in rapor)
    assert Path(j["production_delivery"]).is_file()
