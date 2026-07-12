# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mitas_pipeline as mp  # noqa: E402
import retry_planner as rp  # noqa: E402


def test_technical_failure_teslim_kapisinin_tek_sinyali():
    assert mp._is_technical_failure({"extraction_status": "technical_failure"}) is True
    assert mp._is_technical_failure({"extraction_status": "DEGRADED"}) is False
    assert mp._is_technical_failure({"extraction_status": "OK"}) is False
    assert mp._is_technical_failure(None) is False


def test_guclu_ekran_alias_farki_kimlik_blockeri_degildir():
    cc = {
        "verdict": "ÇELİŞKİ",
        "kimlik_dogru": True,
        "yon_screen_conflict": [{
            "okunan": "E.B. Clucher",
            "otoriter_yonetmen": ["Enzo Barboni"],
            "ekran_kaniti": {"kind": "exact_role_line"},
        }],
    }
    assert mp._is_strong_screen_alias_conflict(cc) is True
    assert mp._has_identity_contradiction(cc) is False


def test_kanitsiz_veya_kimligi_acik_celiski_blocker_kalir():
    assert mp._has_identity_contradiction(
        {"verdict": "ÇELİŞKİ", "kimlik_dogru": True}) is True
    assert mp._has_identity_contradiction({
        "verdict": "ÇELİŞKİ", "kimlik_dogru": False,
        "yon_screen_conflict": [{"okunan": "X Y", "ekran_kaniti": {"kind": "role"}}],
    }) is True


def test_tf_candidate_retry_work_item_kalici_ve_silmesiz(monkeypatch, tmp_path):
    project = tmp_path / "MITAS"
    db = project / "Database"
    db.mkdir(parents=True)
    monkeypatch.setattr(mp, "PROJECT_ROOT", project)
    monkeypatch.setattr(rp, "CANDIDATE_ROOT", project / "candidate_runs")
    clip = tmp_path / "run" / "Database" / "FILM 1990-0001-1-0000-00-1"
    clip.mkdir(parents=True)
    video = tmp_path / "1990-0001-1-0000-00-1 FILM.mp4"

    item = mp._write_extraction_retry_work_item(
        clip, video=video, profile="film", source_run_id="run-1")

    saved = json.loads((clip / "retry_work_item.json").read_text(encoding="utf-8"))
    assert item == saved
    assert saved["status"] == "PENDING"
    assert saved["reason_code"] == "TEKNIK_ARIZA_EXTRACTION"
    assert saved["plan"]["candidate_run"] is True
    assert saved["plan"]["delete_existing"] is False
    assert "--run-root" in saved["plan"]["cmd"]


def test_mesru_bos_ocr_only_yalniz_pending_yazar_muhur_yazmaz(tmp_path):
    clip = tmp_path / "hub"
    for side in ("giris", "cikis"):
        d = clip / "frames" / side
        d.mkdir(parents=True)
        (d / "001.png").write_bytes(b"frame")

    obj = mp._write_mesru_bos_pending(
        clip, v4_credits={"yonetmen_list": [], "yapimci_list": [], "cast_list": []},
        video_credits={"yonetmen": [], "yapimci": [], "cast": []})

    assert obj and obj["status"] == "PENDING_SECOND_WITNESS"
    assert {x["field"] for x in obj["items"]} == {"YONETMEN", "YAPIMCI", "CAST"}
    assert all(x["terminal"] is False for x in obj["items"])
    assert (clip / "mesru_bos.pending.json").exists()
    assert not list(clip.glob("*seal*")) and not list(clip.glob("*muhur*"))


def test_mesru_bos_dolu_alanlarda_pending_yok(tmp_path):
    obj = mp._write_mesru_bos_pending(
        tmp_path, v4_credits={
            "yonetmen_list": ["Director Name"],
            "yapimci_list": ["Producer Name"],
            "cast_list": ["Actor Name"],
        }, video_credits={})
    assert obj is None
    assert not (tmp_path / "mesru_bos.pending.json").exists()
