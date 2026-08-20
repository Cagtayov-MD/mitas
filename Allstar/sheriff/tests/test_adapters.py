from __future__ import annotations

import json

import pytest

from src.adapters import TowerAdapter, TowerContractError
from src.contracts import ContractError
from src.runner import ProcessResult


def _boundary_fixture(tmp_path, *, start_frame=1, end_frame=None, end_s=None):
    inputs = tmp_path / "input"
    selected = tmp_path / "tower/kareler"
    inputs.mkdir()
    selected.mkdir(parents=True)
    frame = inputs / "frame_000001.png"
    frame.write_bytes(b"frame")
    (selected / frame.name).write_bytes(frame.read_bytes())
    (inputs / "frames.jsonl").write_text(json.dumps({
        "filename": frame.name, "sequence": 1, "section_time_s": 0.0,
        "source_time_s": 20.0, "sha256": "ignored-here"}) + "\n", encoding="utf-8")
    document = {"schema_version": "mitas.boundary/v1", "durum": "BULUNDU",
                "baslangic_kare": start_frame, "baslangic_sn": 0.0,
                "bitis_kare": end_frame, "bitis_sn": end_s,
                "uretilen": [{"tip": "kare", "yol": "kareler", "adet": 1}]}
    return document, tmp_path / "tower/kobe.json", inputs


def test_boundary_baslangic_kare_kaynak_manifestte_olmalidir(tmp_path):
    document, result, inputs = _boundary_fixture(tmp_path, start_frame=99)
    with pytest.raises(TowerContractError, match="kaynak manifestte yok"):
        TowerAdapter._validate_boundary(document, result, inputs)


def test_boundary_bitis_kare_ve_zaman_birlikte_verilir(tmp_path):
    document, result, inputs = _boundary_fixture(tmp_path, end_frame=1, end_s=None)
    with pytest.raises(TowerContractError, match="birlikte"):
        TowerAdapter._validate_boundary(document, result, inputs)


def test_jordan_metin_yok_ile_blok_tasiyamaz():
    value = {"durum": "METIN_YOK", "bloklar": [{"satirlar": ["AHMET"]}],
             "ciftler": [], "kanit": {}}
    with pytest.raises(ContractError, match="METIN_YOK"):
        TowerAdapter._validate_jordan(value)


def test_jordan_ariza_metinsiz_hata_zarfi_olarak_kabul_edilir():
    TowerAdapter._validate_jordan({
        "durum": "ARIZA", "sinif": "BELLEK", "mesaj": "cudaMalloc failed",
        "kanit": {"grup_sayisi": 2},
    })


def test_jordan_ariza_varsa_sinif_ve_mesaj_ister():
    with pytest.raises(ContractError, match="sinif/mesaj"):
        TowerAdapter._validate_jordan({"durum": "ARIZA", "kanit": {}})


def test_jordan_frame_okuyucu_producer_ve_prompt_kimligi_registryden_gelir(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    (frames / "frames.jsonl").write_text("{}\n", encoding="utf-8")
    task = {"film_id": "film", "section": "giris", "run_id": "run",
            "task_id": "task"}
    legacy = {"durum": "METIN_YOK", "bloklar": [], "ciftler": [],
              "kanit": {"istem_sha256": "a" * 64}, "motor_surumu": "bird/v1"}
    process = ProcessResult(0, False, False, 0.1, 1.0, 1.0, None,
                            "/tmp/stdout", "/tmp/stderr", ["bird"], 1, 1, None)
    path, document = TowerAdapter._wrap_jordan(
        task, "attempt", frames, legacy, tmp_path / "run", process, [],
        producer_id="bird", independence_group="video_reader_role")
    assert path.name == "bird.okuma.json"
    assert document["producer"]["id"] == "bird"
    assert document["producer"]["prompt_digest"] == "a" * 64
    assert document["lineage"]["inputs"][0]["kind"] == "verified_frame_pool"


def test_kule_owned_cikti_yerinde_kalir_ve_attempt_snapshotina_alinir(tmp_path):
    tower_root = tmp_path / "kobe/out/film/cikis"
    tower_root.mkdir(parents=True)
    result = tower_root / "kobe.json"
    marker = tower_root / "_TAMAM"
    frame = tower_root / "kareler/frame_000001.png"
    frame.parent.mkdir()
    result.write_text('{"durum":"BULUNDU"}', encoding="utf-8")
    marker.write_text("", encoding="utf-8")
    frame.write_bytes(b"frame")

    archived_result, archived_marker, _ = TowerAdapter._snapshot_tower_output(
        result, marker, None, tmp_path / "run/tower_outputs/boundary/attempt-1",
        {"film_id": "film", "section": "cikis"})

    assert result.is_file() and marker.is_file() and frame.is_file()
    assert archived_result.read_bytes() == result.read_bytes()
    assert archived_marker.is_file()
    assert (archived_result.parent / "kareler/frame_000001.png").read_bytes() == b"frame"


def test_snapshot_packet_asset_yolu_kule_outundan_archive_cevrilir(tmp_path):
    source_root = tmp_path / "lebron/out/film/giris"
    archive_root = tmp_path / "run/tower_outputs/reader_master/attempt/film/giris"
    source_asset = source_root / "master.png"
    archived_asset = archive_root / "master.png"
    source_asset.parent.mkdir(parents=True)
    archived_asset.parent.mkdir(parents=True)
    source_asset.write_bytes(b"png")
    archived_asset.write_bytes(source_asset.read_bytes())
    document = {"assets": [{"path": str(source_asset), "origin_path": str(source_asset)}]}

    TowerAdapter._rebase_packet_assets(document, source_root, archive_root)

    assert document["assets"][0]["path"] == str(archived_asset.resolve())
    assert document["assets"][0]["origin_path"] == str(source_asset)
