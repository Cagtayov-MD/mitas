import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest


MODULE_PATH = Path(r"E:\MITAS\OCR-worktree\master_png_monitor.py")
SPEC = importlib.util.spec_from_file_location("test_master_png_monitor", MODULE_PATH)
monitor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = monitor
SPEC.loader.exec_module(monitor)


def test_giris_reading_master_uses_distinct_name_and_full_timeline_split(
    monkeypatch, tmp_path
):
    frames = ["g_0001.png", "g_0002.png", "g_0003.png"]
    captured = {}

    monkeypatch.setattr(
        monitor, "_seg_source", lambda _film, seg: (frames, f"{seg}_textset")
    )

    def fake_compose(_frames, args):
        captured["early_split_frames"] = args.reading_early_split_frames
        return np.zeros((10, 20, 3), np.uint8), {
            "status": "OK",
            "size": [20, 10],
            "manifest": {"status": "OK"},
        }

    monkeypatch.setattr(monitor, "_compose_reading_seg", fake_compose)
    monkeypatch.setattr(
        monitor.dc, "wr", lambda path, _image: captured.setdefault("path", Path(path))
    )

    result = monitor.gen_reading_master(tmp_path, seg="giris")
    info = result["giris_reading_master_runaware"]

    assert captured["early_split_frames"] == len(frames)
    assert captured["path"].name == "giris_reading_master_runaware.png"
    assert info["source"] == "giris_textset"
    assert info["segment"] == "giris"
    assert (tmp_path / "giris_reading_master_runaware_manifest.json").exists()


def test_reading_master_rejects_unknown_segment(tmp_path):
    with pytest.raises(ValueError, match="unsupported reading-master segment"):
        monitor.gen_reading_master(tmp_path, seg="orta")


def test_semantic_groups_split_same_layout_cards_by_ocr_signature(tmp_path):
    manifest = {
        "frames": [
            {"file": "g_0001.png", "decision": "kept", "sig": "first credit"},
            {"file": "g_0002.png", "decision": "kept", "sig": "first credits"},
            {"file": "g_0003.png", "decision": "kept", "sig": "second name"},
            {"file": "g_0004.png", "decision": "kept", "sig": "second names"},
            {"file": "g_0005.png", "decision": "kept", "sig": "final title"},
            {"file": "g_0006.png", "decision": "kept", "sig": "final title"},
        ]
    }
    manifest_path = tmp_path / "frames" / "giris_jenerik_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    frames = [str(tmp_path / "frames" / "giris" / row["file"]) for row in manifest["frames"]]

    groups = monitor._semantic_giris_groups(tmp_path, frames)

    assert [[Path(frame).name for frame in group] for group in groups] == [
        ["g_0001.png", "g_0002.png"],
        ["g_0003.png", "g_0004.png"],
        ["g_0005.png", "g_0006.png"],
    ]


def test_semantic_rescue_replaces_single_card_baseline(monkeypatch, tmp_path):
    groups = [["a1", "a2"], ["b1", "b2"], ["c1", "c2"]]
    calls = {"count": 0}

    def fake_compose(frames, _args):
        calls["count"] += 1
        if calls["count"] == 1:
            return np.zeros((20, 100, 3), np.uint8), {
                "mode": "reading_runaware",
                "status": "OK",
                "size": [100, 20],
                "kept_blocks": 1,
                "strict_scroll_frac": 0.0,
                "runs": [[0, len(frames) - 1, "S"]],
                "manifest": {
                    "mode": "reading_runaware",
                    "size": [100, 20],
                    "runs": [[0, len(frames) - 1, "S"]],
                },
            }
        return np.zeros((10, 100, 3), np.uint8), {
            "status": "OK",
            "size": [100, 10],
            "kept_blocks": 1,
            "strict_scroll_frac": 0.0,
            "manifest": {"mode": "reading_runaware"},
        }

    monkeypatch.setattr(monitor, "_compose_reading_seg", fake_compose)
    monkeypatch.setattr(monitor, "_semantic_giris_groups", lambda *_args: groups)

    master, info = monitor._compose_giris_reading_seg(
        tmp_path, [frame for group in groups for frame in group], monitor.make_args()
    )

    assert master.shape == (34, 100, 3)
    assert info["mode"] == "reading_runaware_semantic_rescue"
    assert info["kept_blocks"] == 3
