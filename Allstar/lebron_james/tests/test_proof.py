import json
import numpy as np

import derleyici
import proof
import cv2


def test_grounding_parser_eval_kullanmaz_ve_tasan_bbox_reddeder():
    text = ("<|ref|>AHMET<|/ref|><|det|>[[10,20,500,100]]<|/det|>"
            "<|ref|>KOTU<|/ref|><|det|>[[0,0,1001,50]]<|/det|>"
            "<|ref|>KOD<|/ref|><|det|>__import__('os').system('false')<|/det|>")
    assert proof.parse_grounding(text) == [
        {"label": "AHMET", "boxes_999": [[10.0, 20.0, 500.0, 100.0]]}]


def test_layout_haritasi_master_piksellerini_degistirmez():
    a = np.zeros((8, 6, 3), dtype=np.uint8)
    b = np.full((8, 6, 3), 200, dtype=np.uint8)
    old = derleyici._segment_kanvas([a, b], [0.0, 3.0])
    new, layout = derleyici._segment_kanvas_haritali(
        [a, b], [0.0, 3.0], {id(a): "/a.png", id(b): "/b.png"})
    assert np.array_equal(old, new)
    assert layout
    assert layout[0]["master_y0"] == 0
    assert layout[-1]["master_y1"] == new.shape[0]
    rebuilt = np.zeros_like(new)
    sources = {"/a.png": a, "/b.png": b}
    for run in layout:
        rebuilt[run["master_y0"]:run["master_y1"]] = sources[run["source_path"]][
            run["source_y0"]:run["source_y1"]]
    assert np.array_equal(new, rebuilt)

    import cv2
    old_bytes = cv2.imencode(".png", old)[1].tobytes()
    new_bytes = cv2.imencode(".png", new)[1].tobytes()
    assert old_bytes == new_bytes


def test_master_bbox_layout_ile_gercek_kaynak_framee_doner(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    master = tmp_path / "master.png"
    cv2.imwrite(str(source), np.zeros((100, 200, 3), dtype=np.uint8))
    cv2.imwrite(str(master), np.zeros((100, 200, 3), dtype=np.uint8))
    frame_manifest = tmp_path / "frames.jsonl"
    frame_manifest.write_text(json.dumps({"filename": source.name, "sequence": 7,
                                          "source_time_s": 3.5}) + "\n",
                              encoding="utf-8")
    for key, value in (("MITAS_SHERIFF_RUN_ID", "run"),
                       ("MITAS_SHERIFF_TASK_ID", "task"),
                       ("MITAS_SHERIFF_ATTEMPT_ID", "attempt")):
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("MITAS_SHERIFF_FRAME_MANIFEST", str(frame_manifest))
    reading = {
        "satir_kaynaklari": [{"text": "AHMET", "bant": "bant_000.png",
                              "bant_index": 0}],
        "bant_y0": [0],
        "grounding": {"bant_000.png": {"width": 200, "height": 100,
                                        "items": [{"label": "AHMET",
                                                   "boxes_999": [[0, 100, 500, 300]]}]}},
    }
    manifest = {"size": [200, 100], "layout_map_version": "mitas.master-layout/v1",
                "layout_map": [{"master_y0": 0, "master_y1": 100,
                                "source_path": str(source), "source_y0": 0,
                                "source_y1": 100, "width": 200, "height": 100}]}
    packet = proof.build_packet(
        film_id="film", section="giris",
        legacy={"durum": "OKUNDU", "satirlar": ["AHMET"]},
        master_path=master, manifest=manifest, reading=reading,
        input_dir=tmp_path, output_dir=tmp_path / "out")
    source_evidence = [item for item in packet["lines"][0]["evidence"]
                       if item.get("kind") == "source_frame"]
    assert source_evidence
    assert source_evidence[0]["bbox"] == [0, 10, 100, 30]
    assert packet["status"]["proof"] == "COMPLETE"
    layout = json.loads((tmp_path / "out/layout_map.json").read_text(encoding="utf-8"))
    assert layout["rows"][0]["source_asset_id"] == source_evidence[0]["asset_id"]
    assert any(asset["asset_id"] == layout["rows"][0]["source_asset_id"]
               for asset in packet["assets"])
