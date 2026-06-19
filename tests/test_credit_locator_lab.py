from __future__ import annotations

import csv
from pathlib import Path

from scripts import credit_locator_lab as lab


def _record(
    text: str,
    y: float,
    *,
    x: float = 200.0,
    w: float = 500.0,
    h: float = 24.0,
    confidence: float = 0.9,
) -> dict:
    return {
        "text": text,
        "bbox": [x, y, w, h],
        "confidence": confidence,
    }


def test_subtitle_baseline_does_not_trigger_credit_for_bottom_dialogue() -> None:
    metrics = [
        lab.metric_from_records(10.0, "a.jpg", 960, 540, [_record("hello there", 450.0)]),
        lab.metric_from_records(12.0, "b.jpg", 960, 540, [_record("another subtitle", 452.0)]),
        lab.metric_from_records(14.0, "c.jpg", 960, 540, [_record("bottom only", 448.0)]),
    ]

    baseline = lab.learn_subtitle_baseline(metrics)
    rescored = lab.rescore_metrics(metrics, baseline_y=baseline, score_threshold=0.55)

    assert baseline is not None
    assert all(not metric.is_credit for metric in rescored)
    assert max(metric.credit_score for metric in rescored) < 0.55


def test_persistent_credit_layout_selects_run_and_preroll_start() -> None:
    metrics = []
    for idx, timestamp in enumerate([100.0, 102.0, 104.0, 106.0]):
        records = [
            _record("DIRECTED BY", 90.0),
            _record("JANE DOE", 150.0),
            _record("PRODUCED BY", 230.0),
            _record("JOHN SMITH", 290.0),
            _record("CAST", 360.0),
        ]
        metrics.append(lab.metric_from_records(timestamp, f"f{idx}.jpg", 960, 540, records))

    rescored = lab.rescore_metrics(metrics, baseline_y=455.0, score_threshold=0.55)
    run = lab.choose_credit_run(rescored, side="closing", score_threshold=0.55, min_sustain_sec=3.0)
    start = lab.refine_start_time(
        rescored,
        trigger_sec=float(run["trigger_sec"]),
        search_start_sec=0.0,
        pre_roll_sec=15.0,
        lookback_sec=45.0,
    )

    assert run is not None
    assert run["start_sec"] == 100.0
    assert run["confidence"] >= 0.55
    assert start == 85.0


def test_4k_subtitle_baseline_scales_with_frame_height() -> None:
    metrics = [
        lab.metric_from_records(10.0, "a.jpg", 3840, 2160, [_record("hello there", 1900.0, h=54.0)]),
        lab.metric_from_records(12.0, "b.jpg", 3840, 2160, [_record("another subtitle", 1910.0, h=54.0)]),
        lab.metric_from_records(14.0, "c.jpg", 3840, 2160, [_record("bottom only", 1895.0, h=54.0)]),
    ]

    baseline = lab.learn_subtitle_baseline(metrics)

    assert baseline is not None
    assert 0.85 < baseline / 2160.0 < 0.92


def test_overlay_role_card_with_low_ocr_confidence_still_scores() -> None:
    metrics = [
        lab.metric_from_records(
            0.0,
            "a.jpg",
            960,
            540,
            [
                _record("DIRECTED BY", 120.0, confidence=0.38),
                _record("JANE DOE", 176.0, confidence=0.41),
            ],
        ),
        lab.metric_from_records(
            2.0,
            "b.jpg",
            960,
            540,
            [
                _record("DIRECTED BY", 120.0, confidence=0.36),
                _record("JANE DOE", 176.0, confidence=0.39),
            ],
        ),
        lab.metric_from_records(
            4.0,
            "c.jpg",
            960,
            540,
            [
                _record("DIRECTED BY", 120.0, confidence=0.35),
                _record("JANE DOE", 176.0, confidence=0.37),
            ],
        ),
    ]

    rescored = lab.rescore_metrics(metrics, baseline_y=455.0, score_threshold=0.55)
    run = lab.choose_credit_run(rescored, side="opening", score_threshold=0.55, min_sustain_sec=3.0)

    assert all(metric.role_card_flag for metric in rescored)
    assert min(metric.credit_score for metric in rescored) >= 0.55
    assert run is not None
    assert run["type"] == "static_sequence"


def test_two_line_role_cards_sequence_is_static_sequence() -> None:
    metrics = [
        lab.metric_from_records(0.0, "a.jpg", 960, 540, [_record("DIRECTED BY", 120.0), _record("JANE DOE", 176.0)]),
        lab.metric_from_records(5.0, "b.jpg", 960, 540, [_record("PRODUCED BY", 120.0), _record("JOHN SMITH", 176.0)]),
        lab.metric_from_records(10.0, "c.jpg", 960, 540, [_record("CAST", 120.0), _record("ALICE A.", 176.0)]),
    ]

    rescored = lab.rescore_metrics(metrics, baseline_y=455.0, score_threshold=0.55)
    run = lab.choose_credit_run(rescored, side="opening", score_threshold=0.55, min_sustain_sec=3.0)

    assert run is not None
    assert run["start_sec"] == 0.0
    assert run["type"] == "static_sequence"
    assert run["role_card_frames"] == 3


def test_box_drop_marks_ocr_difficult_without_killing_role_card() -> None:
    metrics = [
        lab.metric_from_records(
            0.0,
            "a.jpg",
            960,
            540,
            [
                _record("DIRECTED BY", 80.0),
                _record("JANE DOE", 130.0),
                _record("PRODUCED BY", 200.0),
                _record("JOHN SMITH", 250.0),
                _record("CAST", 320.0),
            ],
        ),
        lab.metric_from_records(2.0, "b.jpg", 960, 540, [_record("DIRECTED BY", 120.0), _record("JANE DOE", 176.0)]),
    ]

    rescored = lab.rescore_metrics(metrics, baseline_y=455.0, score_threshold=0.55)

    assert rescored[1].box_drop == 3
    assert rescored[1].ocr_difficult is True
    assert rescored[1].role_card_flag is True
    assert rescored[1].is_credit is True


def test_scene_prop_text_does_not_pull_start_before_safe_preroll() -> None:
    phone = lab.metric_from_records(
        100.0,
        "phone.jpg",
        960,
        540,
        [
            _record("ETHAN", 300.0, x=410.0, w=90.0),
            _record("HUNT", 330.0, x=410.0, w=90.0),
            _record("CALLING", 360.0, x=405.0, w=100.0),
        ],
    )
    credit = lab.metric_from_records(
        126.0,
        "credit.jpg",
        960,
        540,
        [
            _record("DIRECTED BY", 120.0),
            _record("JANE DOE", 176.0),
        ],
    )
    rescored = lab.rescore_metrics([phone, credit], baseline_y=455.0, score_threshold=0.55)

    start = lab.refine_start_time(
        rescored,
        trigger_sec=126.0,
        search_start_sec=0.0,
        pre_roll_sec=15.0,
        lookback_sec=45.0,
    )

    assert rescored[0].significant_line_count == 3
    assert lab.is_credit_start_evidence(rescored[0]) is False
    assert start == 111.0


def test_review_summary_marks_gains_and_regressions(tmp_path: Path) -> None:
    review = tmp_path / "review_template.csv"
    rows = [
        {
            "film_id": "a",
            "side": "closing",
            "verdict_new": "hit",
            "verdict_old": "miss",
        },
        {
            "film_id": "b",
            "side": "opening",
            "verdict_new": "late",
            "verdict_old": "hit",
        },
    ]
    with review.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["film_id", "side", "verdict_new", "verdict_old"])
        writer.writeheader()
        writer.writerows(rows)

    summary = lab.build_review_summary(lab.read_csv(review))

    assert summary["rows_filled"] == 2
    assert len(summary["new_gains_over_old"]) == 1
    assert len(summary["new_regressions_vs_old"]) == 1
    assert summary["new"]["counts"]["hit"] == 1
    assert summary["old"]["counts"]["miss"] == 1
