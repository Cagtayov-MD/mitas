import json
import proof
import cv2
import numpy as np


def test_grounding_parser_guvenli_ve_yalniz_gecerli_bbox_alir():
    text = ("<|ref|>Ahmet<|/ref|><|det|>[[1,2,300,50]]<|/det|>"
            "<|ref|>Tasan<|/ref|><|det|>[[-1,2,30,40]]<|/det|>"
            "<|ref|>Kod<|/ref|><|det|>open('/tmp/x','w')<|/det|>")
    assert proof.parse_grounding(text) == [
        {"label": "Ahmet", "boxes_999": [[1.0, 2.0, 300.0, 50.0]]}]


def test_grounding_gercek_deepseek_biciminde_ref_text_degil_metni_alir():
    ham = ("<|ref|>text<|/ref|><|det|>[[48,592,240,640]]<|/det|>\n"
           "UMIT KANTAR\n\n"
           "<|ref|>text<|/ref|><|det|>[[750,592,953,640]]<|/det|>\n"
           "SEVCAN YASAR")
    assert proof.parse_grounding(ham) == [
        {"label": "UMIT KANTAR", "boxes_999": [[48.0, 592.0, 240.0, 640.0]]},
        {"label": "SEVCAN YASAR", "boxes_999": [[750.0, 592.0, 953.0, 640.0]]},
    ]


def test_image_bolgesi_ocr_satiri_degildir_ama_grounding_bicimidir():
    ham = "<|ref|>image<|/ref|><|det|>[[1,2,30,40]]<|/det|>"
    assert proof.parse_grounding(ham) == []
    assert proof.grounding_bicimi_var(ham)


def test_fold_exact_fuzzy_degildir():
    assert proof.fold_exact("  AHMET  ") == proof.fold_exact("ahmet")
    assert proof.fold_exact("ahmat") != proof.fold_exact("ahmet")


def test_grounding_cok_satirli_ref_okuma_satirlarina_acilir():
    assert proof.grounding_lines([
        {"label": "YONETMEN\nAHMET", "boxes_999": [[1, 2, 30, 40]]}
    ]) == [
        {"label": "YONETMEN", "boxes_999": [[1, 2, 30, 40]]},
        {"label": "AHMET", "boxes_999": [[1, 2, 30, 40]]},
    ]


def test_fuzzy_yakin_satira_bbox_atanmaz_ama_satir_korunur(tmp_path, monkeypatch):
    image = tmp_path / "frame_000001.png"
    cv2.imwrite(str(image), np.zeros((100, 200, 3), dtype=np.uint8))
    monkeypatch.setenv("MITAS_SHERIFF_RUN_ID", "run")
    monkeypatch.setenv("MITAS_SHERIFF_TASK_ID", "task")
    monkeypatch.setenv("MITAS_SHERIFF_ATTEMPT_ID", "attempt")
    legacy = {"durum": "OKUNDU", "motor_surumu": "nash@test", "sure_sn": 1,
              "satirlar": [{"kaynak": image.name, "text": "AHMET"}]}
    packet = proof.build_packet(
        film_id="film", section="giris", legacy=legacy, selected_paths=[image],
        accepted=legacy["satirlar"], rejected=[],
        grounding={image.name: [{"label": "AHMAT", "boxes_999": [[1, 2, 300, 50]]}]},
        grounding_failures=[])
    assert packet["lines"][0]["raw_text"] == "AHMET"
    assert packet["lines"][0]["evidence"] == []
    assert packet["status"]["proof"] == "NONE"


def test_exact_grounding_pixel_bbox_uretir(tmp_path, monkeypatch):
    image = tmp_path / "frame.png"
    cv2.imwrite(str(image), np.zeros((100, 200, 3), dtype=np.uint8))
    frame_manifest = tmp_path / "frames.jsonl"
    frame_manifest.write_text(json.dumps({"filename": image.name, "sequence": 4,
                                          "source_time_s": 1.5}) + "\n",
                              encoding="utf-8")
    for key, value in (("MITAS_SHERIFF_RUN_ID", "run"),
                       ("MITAS_SHERIFF_TASK_ID", "task"),
                       ("MITAS_SHERIFF_ATTEMPT_ID", "attempt")):
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("MITAS_SHERIFF_FRAME_MANIFEST", str(frame_manifest))
    accepted = [{"kaynak": image.name, "text": "AHMET"}]
    packet = proof.build_packet(
        film_id="film", section="giris", legacy={"durum": "OKUNDU",
        "satirlar": accepted}, selected_paths=[image], accepted=accepted, rejected=[],
        grounding={image.name: [{"label": "ahmet", "boxes_999": [[0, 0, 500, 500]]}]},
        grounding_failures=[])
    assert packet["status"]["proof"] == "COMPLETE"
    assert packet["lines"][0]["evidence"][0]["bbox"] == [0, 0, 100, 50]


def test_hybrid_packet_paddle_motorunu_ve_peak_vrami_yazar(tmp_path):
    image = tmp_path / "frame.png"
    cv2.imwrite(str(image), np.zeros((100, 200, 3), dtype=np.uint8))
    accepted = [{"kaynak": image.name, "text": "AHMET", "motor": "paddle"}]
    legacy = {"durum": "OKUNDU", "satirlar": accepted,
              "kanit": {"okuma_modu": "hybrid", "paddle_peak_vram_mb": 345.0}}
    packet = proof.build_packet(
        film_id="film", section="cikis", legacy=legacy, selected_paths=[image],
        accepted=accepted, rejected=[], grounding={image.name: [
            {"label": "AHMET", "boxes_999": [[0, 0, 500, 500]],
             "engine": "paddle", "score": 0.98}]}, grounding_failures=[])
    assert packet["producer"]["strategy"] == "text-run-paddle-first+deepseek-fallback"
    assert packet["lines"][0]["evidence"][0]["engine"] == "paddle"
    assert packet["resource_usage"]["vram_peak_mb"] == 345.0


def test_deepseek_kapaliyken_packet_paddle_stratejisini_dogru_yazar(tmp_path):
    image = tmp_path / "frame.png"
    cv2.imwrite(str(image), np.zeros((100, 200, 3), dtype=np.uint8))
    accepted = [{"kaynak": image.name, "text": "محسن عبد الوهاب",
                 "motor": "paddle_arabic"}]
    legacy = {"durum": "OKUNDU", "satirlar": accepted, "kanit": {
        "okuma_modu": "hybrid", "deepseek_fallback_enabled": False,
        "paddle_script_fallback": {"kabul_satir_n": 1}}}
    packet = proof.build_packet(
        film_id="film", section="cikis", legacy=legacy, selected_paths=[image],
        accepted=accepted, rejected=[], grounding={image.name: [
            {"label": "محسن عبد الوهاب", "boxes_999": [[0, 0, 500, 500]],
             "engine": "paddle_arabic", "score": 0.98}]},
        grounding_failures=[])
    assert packet["producer"]["strategy"] == "text-run-paddle-multiscript"
    assert packet["producer"]["strategy_version"] == "nash-paddle/v5"
    assert "deepseek" not in packet["producer"]["model"]
