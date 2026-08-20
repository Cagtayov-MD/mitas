from __future__ import annotations

import pytest

from src.contracts import ContractError, line_record, packet, validate_packet


def base_packet(**overrides):
    values = dict(
        film_id="film", section="giris", run_id="run", task_id="task",
        attempt_id="attempt", producer={"id": "reader"}, inputs=[],
        execution_status="SUCCEEDED", content_status="READ", proof_status="PARTIAL",
        lines=[line_record("Ahmet", 0)],
    )
    values.update(overrides)
    return packet(**values)


def test_bbox_uydurulamaz_ve_xyxy_tam_sayi_olmalidir():
    value = base_packet()
    value["assets"] = [{"asset_id": "a", "path": "/tmp/a.png", "origin_path": None,
                        "sha256": "0" * 64, "mime_type": "image/png"}]
    value["lines"][0]["evidence"] = [{"asset_id": "a", "bbox": [1.1, 2, 3, 4],
                                        "coordinate_space": "pixel_xyxy"}]
    with pytest.raises(ContractError):
        validate_packet(value)


def test_complete_proof_kanitsiz_satir_kabul_etmez():
    with pytest.raises(ContractError):
        base_packet(proof_status="COMPLETE")


def test_complete_proof_bboxsiz_evidence_kabul_etmez():
    value = base_packet(proof_status="PARTIAL")
    value["assets"] = [{"asset_id": "a", "path": "/tmp/a.png", "origin_path": None,
                        "sha256": "0" * 64, "mime_type": "image/png",
                        "width": 10, "height": 10, "frame_sequence": 1,
                        "source_time_s": 0.0}]
    value["lines"][0]["evidence"] = [{"asset_id": "a", "coordinate_space": "pixel_xyxy"}]
    value["status"]["proof"] = "COMPLETE"
    with pytest.raises(ContractError, match="bbox"):
        validate_packet(value)


def test_complete_proof_bbox_frame_ve_timecode_ile_gecerlidir():
    value = base_packet(proof_status="PARTIAL")
    value["assets"] = [{"asset_id": "a", "path": "/tmp/a.png", "origin_path": None,
                        "sha256": "0" * 64, "mime_type": "image/png",
                        "width": 10, "height": 10, "frame_sequence": 1,
                        "source_time_s": 0.0}]
    value["lines"][0]["evidence"] = [{"asset_id": "a", "bbox": [1, 2, 9, 8],
                                         "coordinate_space": "pixel_xyxy"}]
    value["status"]["proof"] = "COMPLETE"
    validate_packet(value)


def test_no_content_celiskili_status_tasiyamaz():
    value = base_packet()
    value["status"] = {"execution": "NO_CONTENT", "content": "READ", "proof": "PARTIAL"}
    with pytest.raises(ContractError, match="NO_CONTENT"):
        validate_packet(value)


def test_partial_proof_satiri_kaybetmeden_kabul_eder():
    value = base_packet()
    assert value["lines"][0]["raw_text"] == "Ahmet"
    assert value["status"]["proof"] == "PARTIAL"


def test_bbox_asset_pixel_sinirini_asamaz():
    value = base_packet()
    value["assets"] = [{"asset_id": "a", "path": "/tmp/a.png", "origin_path": None,
                        "sha256": "0" * 64, "mime_type": "image/png",
                        "width": 10, "height": 10}]
    value["lines"][0]["evidence"] = [{"asset_id": "a", "bbox": [1, 2, 20, 9],
                                        "coordinate_space": "pixel_xyxy"}]
    with pytest.raises(ContractError, match="sinirini asiyor"):
        validate_packet(value)


def test_complete_proof_sahte_frame_time_tipiyle_gecemez():
    value = base_packet()
    value["assets"] = [{"asset_id": "a", "path": "/tmp/a.png", "origin_path": None,
                        "sha256": "0" * 64, "mime_type": "image/png",
                        "width": 10, "height": 10, "frame_sequence": "bir",
                        "source_time_s": "simdi"}]
    value["lines"][0]["evidence"] = [{"asset_id": "a", "bbox": [1, 2, 9, 8],
                                         "coordinate_space": "pixel_xyxy"}]
    with pytest.raises(ContractError, match="frame_sequence"):
        validate_packet(value)


def test_bozuk_container_tipi_validatoru_cokertmek_yerine_contract_hatasi_verir():
    value = base_packet()
    value["lines"] = {"line": "yanlis-tip"}
    with pytest.raises(ContractError, match="lines liste"):
        validate_packet(value)
