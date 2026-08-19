"""Paddle-exact proof — satır kanıtı yalnız TEK ve AÇIK eşleşmeden doğar.

Private Ollama satır-grounding desteklemediği için kanıt zinciri Free OCR
metni ↔ Paddle satır bbox'ı üzerinden kurulur. Fuzzy ve çoklu aday BURADA
ÖLÜR: belirsiz eşleşme bbox üretmez, COMPLETE yazılmaz. Bant-içi bbox,
`bant_y0` ofsetiyle master koordinatına; master bbox, layout haritasıyla
gerçek kaynak kareye çevrilir.
"""
import json

import cv2
import numpy as np

import proof

KAYNAK_H, W = 100, 200
MASTER_Y0 = 1000
SATIR = "YONETIM AHMET"


def _paket(tmp_path, monkeypatch, items, satir=SATIR):
    kaynak = tmp_path / "kaynak.png"
    master = tmp_path / "master.png"
    cv2.imwrite(str(kaynak), np.zeros((KAYNAK_H, W, 3), dtype=np.uint8))
    cv2.imwrite(str(master), np.zeros((MASTER_Y0 + KAYNAK_H, W, 3), dtype=np.uint8))
    frame_manifest = tmp_path / "frames.jsonl"
    frame_manifest.write_text(
        json.dumps({"filename": kaynak.name, "sequence": 42,
                    "source_time_s": 1.75}) + "\n", encoding="utf-8")
    monkeypatch.setenv("MITAS_SHERIFF_FRAME_MANIFEST", str(frame_manifest))
    reading = {
        "satir_kaynaklari": [{"text": satir, "bant": "bant_001.png",
                              "bant_index": 1}],
        "bant_y0": [0, MASTER_Y0],
        "paddle_satir_haritasi": {"bant_001.png": {"width": W, "height": 1100,
                                                   "items": items}},
    }
    manifest = {"size": [W, MASTER_Y0 + KAYNAK_H],
                "layout_map_version": "mitas.master-layout/v1",
                "layout_map": [{"master_y0": MASTER_Y0,
                                "master_y1": MASTER_Y0 + KAYNAK_H,
                                "source_path": str(kaynak),
                                "source_y0": 0, "source_y1": KAYNAK_H,
                                "width": W, "height": KAYNAK_H}]}
    return proof.build_packet(
        film_id="film", section="cikis",
        legacy={"durum": "OKUNDU", "satirlar": [satir]},
        master_path=master, manifest=manifest, reading=reading,
        input_dir=tmp_path, output_dir=tmp_path / "out")


def _tur(packet, kind):
    return next(e for e in packet["lines"][0]["evidence"] if e["kind"] == kind)


def test_tek_acik_eslesme_bant_ofsetiyle_master_ve_kaynak_kaniti_verir(
        tmp_path, monkeypatch):
    packet = _paket(tmp_path, monkeypatch, [
        {"text": "BASKA SATIR", "confidence": 0.5, "bbox": [5, 60, 90, 80]},
        {"text": SATIR, "confidence": 0.97, "bbox": [10, 20, 150, 50]}])

    master = _tur(packet, "master")
    assert master["bbox"] == [10, 1020, 150, 1050]      # yerel y + bant_y0
    assert master["match"] == "paddle_exact"
    assert master["paddle_confidence"] == 0.97
    assert master["coordinate_space"] == "pixel_xyxy"
    kaynak = _tur(packet, "source_frame")
    assert kaynak["bbox"] == [10, 20, 150, 50]          # layout üzerinden kaynak kare
    assert kaynak["frame_sequence"] == 42
    assert kaynak["source_time_s"] == 1.75
    assert packet["status"]["proof"] == "COMPLETE"
    assert packet["unread_regions"] == []
    assert packet["diagnostics"]["proof_strategy"] == "paddle_exact"


def test_fold_eslesme_buyukluk_ve_bosluk_tolere_edilir(tmp_path, monkeypatch):
    packet = _paket(tmp_path, monkeypatch, [
        {"text": " yonetim ahmet ", "confidence": 0.9, "bbox": [10, 20, 150, 50]}])

    assert _tur(packet, "master")["match"] == "paddle_fold_exact"
    assert packet["status"]["proof"] == "COMPLETE"


def test_iki_ayni_metinli_aday_belirsizdir_kanit_uretmez(tmp_path, monkeypatch):
    packet = _paket(tmp_path, monkeypatch, [
        {"text": SATIR, "confidence": 0.9, "bbox": [10, 20, 150, 50]},
        {"text": SATIR, "confidence": 0.8, "bbox": [12, 22, 152, 52]}])

    assert packet["lines"][0]["evidence"] == []
    assert packet["unread_regions"][0]["reason"] == "PADDLE_ESLESME_BELIRSIZ"
    assert packet["status"]["proof"] == "NONE"


def test_yakin_metin_fuzzy_olarak_kabul_edilmez(tmp_path, monkeypatch):
    packet = _paket(tmp_path, monkeypatch, [
        {"text": "YONETIM AHME", "confidence": 0.99, "bbox": [10, 20, 150, 50]}])

    assert packet["lines"][0]["evidence"] == []
    assert packet["unread_regions"][0]["reason"] == "PADDLE_ESLESME_YOK"
    assert packet["status"]["proof"] == "NONE"


def test_bozuk_bbox_kanit_uretmez(tmp_path, monkeypatch):
    packet = _paket(tmp_path, monkeypatch, [
        {"text": SATIR, "confidence": 0.9, "bbox": [None, 20, 150, 50]}])

    assert packet["lines"][0]["evidence"] == []
    assert packet["unread_regions"][0]["reason"] == "PADDLE_BBOX_GECERSIZ"
    assert packet["status"]["proof"] == "NONE"


def test_image_geneli_kutu_satir_kaniti_olamaz():
    """DeepSeek-OCR'un görüntü-geneli ``image[[...]]`` yanıtı ref/det
    biçiminde değildir; parserdan geçemez, dolayısıyla satır kanıtı olarak
    asla yayınlanamaz."""
    assert proof.parse_grounding("image[[0, 0, 999, 999]]") == []
    assert proof.parse_grounding("YONETIM AHMET\nimage[[10, 20, 500, 100]]") == []
    karisik = ("<|ref|>AHMET<|/ref|><|det|>[[10,20,500,100]]<|/det|>"
               "image[[0,0,999,999]]")
    assert [item["label"] for item in proof.parse_grounding(karisik)] == ["AHMET"]
