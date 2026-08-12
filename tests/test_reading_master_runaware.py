import importlib.util
import sys
import types
from pathlib import Path

import numpy as np


import os

_KOK = Path(os.environ.get("MITAS_PROJECT_ROOT") or Path(__file__).resolve().parents[1])
MODULE_PATH = _KOK / "OCR-worktree" / "db_compose_master.py"
SPEC = importlib.util.spec_from_file_location("test_db_compose_master", MODULE_PATH)
dc = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dc
SPEC.loader.exec_module(dc)


def test_uncertain_motion_falls_back_to_static_without_erasing_boundary():
    cut_runs = [[0, 4, "S"], [5, 6, "C"], [7, 12, "S"]]
    short_scroll_runs = [[0, 4, "S"], [5, 6, "R"], [7, 12, "S"]]

    assert dc._resolve_reading_runs(cut_runs, min_scroll=5) == [
        [0, 4, "S"],
        [5, 12, "S"],
    ]
    assert dc._resolve_reading_runs(short_scroll_runs, min_scroll=5) == [[0, 12, "S"]]


def test_uncertain_motion_between_scroll_runs_becomes_static():
    raw_runs = [[0, 5, "R"], [6, 7, "C"], [8, 13, "R"]]

    assert dc._resolve_reading_runs(raw_runs, min_scroll=5) == [
        [0, 5, "R"],
        [6, 7, "S"],
        [8, 13, "R"],
    ]


def test_stable_medoid_beats_a_sharper_transition_frame():
    candidates = [
        (100.0, "stable-a", 0, None, 0),
        (90.0, "stable-b", 1, None, 0),
        (1000.0, "transition", 2, None, 255),
    ]

    best, distance = dc._best_stable_candidate(candidates)

    assert best[1] == "stable-b"
    assert distance == 8


def test_aligned_text_mask_similarity_recognizes_shifted_duplicate():
    first = np.zeros((64, 96), dtype=np.uint8)
    second = np.zeros_like(first)
    first[20:30, 25:55] = 255
    second[20:30, 31:61] = 255

    response, iou = dc._aligned_text_mask_similarity(first, second)

    assert response >= 0.5
    assert iou >= 0.9


def test_two_frame_card_is_allowed_only_inside_opening_window(monkeypatch):
    hashes = [0, 255, 255, 0, 0, 0, 0, 0]
    frames = [str(i) for i in range(len(hashes))]

    def fake_prep(frame, _p, _args):
        return np.full((2, 2, 3), int(frame), dtype=np.uint8)

    def fake_hash(image, _p, _args):
        return hashes[int(image[0, 0, 0])]

    monkeypatch.setattr(dc, "_prep", fake_prep)
    monkeypatch.setattr(dc, "_textmask_dhash", fake_hash)
    p = types.SimpleNamespace(min_hold=5)
    args = types.SimpleNamespace(card_same_thr=6, card_min_hold=5)

    opening_cards = dc.split_static_cards(
        frames,
        p,
        args,
        timeline_offset=0,
        opening_frame_limit=30,
        opening_min_hold=2,
    )
    later_cards = dc.split_static_cards(
        frames,
        p,
        args,
        timeline_offset=30,
        opening_frame_limit=30,
        opening_min_hold=2,
    )

    assert [len(card) for card in opening_cards] == [1, 2, 5]
    assert [len(card) for card in later_cards] == [3, 5]


def test_reading_min_hold_override_accepts_three_frame_card(monkeypatch):
    hashes = [0, 255, 255, 255, 0, 0, 0, 0, 0]
    frames = [str(i) for i in range(len(hashes))]

    monkeypatch.setattr(
        dc,
        "_prep",
        lambda frame, _p, _args: np.full((2, 2, 3), int(frame), dtype=np.uint8),
    )
    monkeypatch.setattr(
        dc,
        "_textmask_dhash",
        lambda image, _p, _args: hashes[int(image[0, 0, 0])],
    )
    p = types.SimpleNamespace(min_hold=5)
    args = types.SimpleNamespace(card_same_thr=6, card_min_hold=5)

    cards = dc.split_static_cards(
        frames,
        p,
        args,
        timeline_offset=30,
        opening_frame_limit=10,
        opening_min_hold=2,
        min_hold_override=3,
    )

    assert [len(card) for card in cards] == [1, 3, 5]


def test_short_transition_fragment_is_attached_to_next_stable_card():
    cards = [["transition"], ["a", "b", "c"], ["d", "e", "f"]]

    merged = dc._merge_short_reading_cards(
        cards,
        timeline_offset=30,
        opening_frame_limit=10,
        opening_min_hold=2,
        min_hold=3,
    )

    assert merged == [["transition", "a", "b", "c"], ["d", "e", "f"]]


def test_chain_stability_accepts_a_consistent_three_frame_drift(monkeypatch):
    hashes = [511, 0, 63, 255]
    frames = [str(i) for i in range(len(hashes))]
    monkeypatch.setattr(
        dc,
        "_prep",
        lambda frame, _p, _args: np.full((2, 2, 3), int(frame), dtype=np.uint8),
    )
    monkeypatch.setattr(
        dc,
        "_textmask_dhash",
        lambda image, _p, _args: hashes[int(image[0, 0, 0])],
    )
    p = types.SimpleNamespace(min_hold=3)
    args = types.SimpleNamespace(card_same_thr=7, card_min_hold=3)

    fixed = dc.split_static_cards(frames, p, args)
    chained = dc.split_static_cards(frames, p, args, chain_stability=True)

    assert [len(card) for card in fixed] == [4]
    assert [len(card) for card in chained] == [1, 3]


def test_long_mixed_card_is_split_at_strong_internal_jump(monkeypatch):
    hashes = [0, 0, 0, 0, 1023, 1023, 1023, 1023]
    frames = [str(i) for i in range(len(hashes))]
    monkeypatch.setattr(
        dc,
        "_prep",
        lambda frame, _p, _args: np.full((2, 2, 3), int(frame), dtype=np.uint8),
    )
    monkeypatch.setattr(
        dc,
        "_textmask_dhash",
        lambda image, _p, _args: hashes[int(image[0, 0, 0])],
    )

    cards = dc._split_long_reading_cards(
        [frames],
        types.SimpleNamespace(),
        types.SimpleNamespace(),
        min_hold=3,
        same_thr=7,
        timeline_offset=0,
        frame_limit=45,
    )

    assert [len(card) for card in cards] == [4, 4]
