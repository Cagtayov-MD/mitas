from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.pipelines.ocr.text_layer_row_reconstruct import (
    _trim_composite_by_row_gap,
    detect_auto_split,
    detect_rows,
    quality_score,
    run_text_layer_row_reconstruct,
)


def test_row_reconstruct_exports_composite_rows_and_auto_split(tmp_path: Path) -> None:
    frames = _make_scrolling_role_name_frames(tmp_path / "frames")
    output_dir = tmp_path / "row_reconstruct"

    result = run_text_layer_row_reconstruct(frame_paths=frames, output_dir=output_dir, max_frames=60, scale_for_rows=1)
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

    assert result.composite_path.exists()
    assert summary["composite_size"][1] > 360
    assert summary["motion"]["status"] == "ok"
    assert summary["row_count"] >= 8
    assert summary["auto_split"]["status"] == "detected"
    assert 230 <= summary["auto_split"]["split_x"] <= 380
    assert any("role_crop_path" in row for row in summary["rows"])
    assert any("name_crop_path" in row for row in summary["rows"])
    assert "quality" in summary
    assert summary["quality"]["score"] >= 0.0
    assert "frame_filter" in summary
    assert summary["candidate_selector"]["selected"] in {"current_displacement", "static_best_frame"}
    assert len(summary["candidate_selector"]["candidates"]) >= 2
    # §27 — Hakim 2026-05-29 itibariyle tamamen pasif: shadow logu DEFAULT KAPALI
    assert summary["candidate_selector"]["selection_policy"] == "current_first_with_emergency_static_fallback"
    shadow = summary["candidate_selector"]["hakim_shadow_decision"]
    assert isinstance(shadow, dict)
    assert shadow["status"] == "disabled"
    # Sağlıklı scroll'da panorama seçilmeli
    assert summary["candidate_selector"]["selected"] == "current_displacement"


def test_quality_score_flags_blank_lower_than_text_image() -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    blank = np.zeros((240, 360, 3), dtype=np.uint8)
    text = blank.copy()
    for index in range(5):
        cv2.putText(text, f"NAME {index}", (80, 55 + index * 34), cv2.FONT_HERSHEY_SIMPLEX, 0.74, (255, 255, 255), 2, cv2.LINE_AA)

    q_blank = quality_score(blank, cv2)
    q_text = quality_score(text, cv2)

    assert q_blank["score"] < 0.2
    assert q_text["score"] > q_blank["score"]


def test_auto_split_declines_single_center_column(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    image = np.zeros((360, 640, 3), dtype=np.uint8)
    for index, text in enumerate(["DIRECTED BY", "MICHAEL BIEHN", "PRODUCED BY", "ANNE DENMAN"]):
        cv2.putText(image, text, (210, 120 + index * 42), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)

    split = detect_auto_split(image)

    assert split["split_x"] is None
    assert split["status"] in {"no_clear_column_gap", "no_balanced_gap", "low_confidence_gap"}


def test_detect_rows_finds_physical_rows(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    image = np.zeros((480, 640, 3), dtype=np.uint8)
    for index in range(7):
        cv2.putText(image, f"ROLE {index}", (80, 70 + index * 55), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(image, f"NAME {index}", (360, 70 + index * 55), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)

    rows = detect_rows(image)

    assert len(rows) == 7
    assert rows[0]["y0"] < rows[0]["peak_y"] < rows[0]["y1"]


def test_trim_composite_by_row_gap_drops_tail_after_oversized_gap() -> None:
    np = pytest.importorskip("numpy")
    composite = np.zeros((1000, 200, 3), dtype=np.uint8)
    rows = [
        {"index": 1, "y0": 0, "y1": 30, "peak_y": 15},
        {"index": 2, "y0": 40, "y1": 70, "peak_y": 55},
        {"index": 3, "y0": 80, "y1": 110, "peak_y": 95},
        {"index": 4, "y0": 120, "y1": 150, "peak_y": 135},
        {"index": 5, "y0": 160, "y1": 190, "peak_y": 175},
        {"index": 6, "y0": 600, "y1": 630, "peak_y": 615},
        {"index": 7, "y0": 750, "y1": 780, "peak_y": 765},
    ]

    info, trimmed, kept = _trim_composite_by_row_gap(composite, rows)

    assert info["applied"] is True
    assert info["kept_rows"] == 5
    assert info["dropped_rows"] == 2
    assert info["cut_gap_px"] == 410
    assert trimmed.shape[0] == info["cut_y"]
    assert trimmed.shape[0] < composite.shape[0]
    assert [row["index"] for row in kept] == [1, 2, 3, 4, 5]


def test_trim_composite_by_row_gap_no_op_when_gaps_are_uniform() -> None:
    np = pytest.importorskip("numpy")
    composite = np.zeros((400, 200, 3), dtype=np.uint8)
    rows = [
        {"index": idx + 1, "y0": idx * 40, "y1": idx * 40 + 30, "peak_y": idx * 40 + 15}
        for idx in range(8)
    ]

    info, trimmed, kept = _trim_composite_by_row_gap(composite, rows)

    assert info["applied"] is False
    assert info["reason"] == "no_oversized_gap"
    assert trimmed is composite
    assert kept is rows


def test_trim_composite_by_row_gap_no_op_when_too_few_rows() -> None:
    np = pytest.importorskip("numpy")
    composite = np.zeros((400, 200, 3), dtype=np.uint8)
    rows = [
        {"index": 1, "y0": 0, "y1": 30, "peak_y": 15},
        {"index": 2, "y0": 200, "y1": 230, "peak_y": 215},
    ]

    info, trimmed, kept = _trim_composite_by_row_gap(composite, rows)

    assert info["applied"] is False
    assert info["reason"] == "too_few_rows"


def test_trim_composite_self_corrects_when_dropping_almost_everything():
    """ANJELIK-style: 14 row, ilk büyük gap'te 13 row atıldı → self-correction reverse."""
    import numpy as np
    from core.pipelines.ocr.text_layer_row_reconstruct import _trim_composite_by_row_gap

    # 14 row: ilk 1 row üstte (y=0..15), sonra 462px gap, sonra 13 row (y=480..960)
    rows = [{"index": 1, "y0": 0, "y1": 15}]
    # büyük gap sonrası 13 row, her biri ~15px yüksek, 7px aralık (median≈7)
    y = 480
    for i in range(2, 15):
        rows.append({"index": i, "y0": y, "y1": y + 15})
        y += 15 + 7  # 7px gap (median_gap=7)
    composite = np.zeros((1000, 600, 3), dtype=np.uint8)

    info, returned_composite, returned_rows = _trim_composite_by_row_gap(composite, rows)

    # Self-correction tetiklenmeli
    assert info["applied"] is False, f"Self-correction beklendi, ama applied=True: {info}"
    assert info["reason"] == "self_corrected_kept_too_few"
    assert info["would_keep_rows"] == 1
    assert info["would_drop_rows"] == 13
    # Composite ve rows orjinal halinde dönmeli (modify edilmemiş)
    assert returned_composite.shape == composite.shape
    assert len(returned_rows) == len(rows)


def test_trim_composite_normal_tail_still_trimmed():
    """Normal kuyruk: 12 row başta, 2 row sonda (post-credit shot) → trim çalışmalı."""
    import numpy as np
    from core.pipelines.ocr.text_layer_row_reconstruct import _trim_composite_by_row_gap

    rows = []
    y = 0
    for i in range(1, 13):  # 12 sağlam row
        rows.append({"index": i, "y0": y, "y1": y + 15})
        y += 15 + 7
    # Büyük gap → 2 kuyruk row
    y += 300
    rows.append({"index": 13, "y0": y, "y1": y + 15})
    y += 22
    rows.append({"index": 14, "y0": y, "y1": y + 15})
    composite = np.zeros((y + 50, 600, 3), dtype=np.uint8)

    info, returned_composite, returned_rows = _trim_composite_by_row_gap(composite, rows)

    # Trim uygulanmalı, 12 row kalmalı (self-correction tetiklenmez: 12 > max(2, 4.2)=4)
    assert info["applied"] is True, f"Normal trim beklendi, görülen: {info}"
    assert info["reason"] == "oversized_inter_row_gap"
    assert info["kept_rows"] == 12
    assert info["dropped_rows"] == 2
    assert len(returned_rows) == 12


def test_trim_composite_jurassic_style_long_tail_still_trimmed():
    """JURASSIC: 82 kept + 211 dropped — makul trim, self-correction tetiklenmemeli.

    Eski gevşek heuristik (kept ≤ 30%*total) bunu yanlışlıkla reverse ediyordu;
    yeni sıkı heuristik (kept ≤ 2) sadece ekstrem 1-2 row yakalar."""
    import numpy as np
    from core.pipelines.ocr.text_layer_row_reconstruct import _trim_composite_by_row_gap

    rows = []
    y = 0
    # 82 sağlam row (median gap ~7)
    for i in range(1, 83):
        rows.append({"index": i, "y0": y, "y1": y + 15})
        y += 15 + 7
    # Büyük gap (kuyruk başlangıcı, gerçek post-credit shot)
    y += 600
    # 211 kuyruk row (ghost, aligned non-text frame'ler)
    for i in range(83, 294):
        rows.append({"index": i, "y0": y, "y1": y + 15})
        y += 15 + 7
    composite = np.zeros((y + 50, 600, 3), dtype=np.uint8)

    info, returned_composite, returned_rows = _trim_composite_by_row_gap(composite, rows)

    # Trim uygulanmalı; self-correction tetiklenmemeli (82 > 2)
    assert info["applied"] is True, f"JURASSIC trim'i normal çalışmalı, görülen: {info}"
    assert info["reason"] == "oversized_inter_row_gap"
    assert info["kept_rows"] == 82
    assert info["dropped_rows"] == 211
    assert len(returned_rows) == 82


def _make_scrolling_role_name_frames(directory: Path) -> list[Path]:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    directory.mkdir(parents=True, exist_ok=True)
    frame_count = 60
    rows = [
        ("Director", "MICHAEL BIEHN"),
        ("Producer", "ANNE DENMAN"),
        ("Editor", "BETTINA McCALL"),
        ("Sound", "MARTIN EVANS"),
        ("Camera", "JAMES ASPINALL"),
        ("Location", "EJAZ AHMED"),
        ("Carpenter", "NICK CUMMINS"),
        ("Costumer", "LYNN TALBOT"),
        ("Makeup", "SAUL SULTAN"),
        ("Paint", "MARKO LYTVIAK"),
        ("Chef", "SOREN TAMBOUR"),
        ("Assistant", "PENNY WOOLLEY"),
    ]
    paths: list[Path] = []
    for frame_index in range(frame_count):
        image = np.zeros((360, 640, 3), dtype=np.uint8)
        y_base = 390 - frame_index * 9
        for row_index, (role, name) in enumerate(rows):
            y = y_base + row_index * 42
            if -40 <= y <= 400:
                cv2.putText(image, role, (72, y), cv2.FONT_HERSHEY_SIMPLEX, 0.64, (230, 230, 230), 2, cv2.LINE_AA)
                cv2.putText(image, name, (370, y), cv2.FONT_HERSHEY_SIMPLEX, 0.64, (255, 255, 255), 2, cv2.LINE_AA)
        path = directory / f"frame_{frame_index:04d}.png"
        cv2.imwrite(str(path), image)
        paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# _frame_text_mask mode testleri
# ---------------------------------------------------------------------------


def test_frame_text_mask_strict_global_only_passes_bright_text():
    """Global sıkı eşik karanlık BG noise'ı eler, sadece parlak text geçer."""
    import numpy as np
    cv2 = pytest.importorskip("cv2")
    from core.pipelines.ocr.text_layer_row_reconstruct import _frame_text_mask

    # 100×200 sentetik: BG noise 40-90, üst kısımda 20×100 text patch 220-255
    rng = np.random.default_rng(42)
    gray = rng.integers(40, 90, size=(100, 200), dtype=np.uint8)
    gray[10:30, 50:150] = rng.integers(220, 255, size=(20, 100), dtype=np.uint8)

    mask = _frame_text_mask(gray, cv2, np, mode="strict_global")
    # Text bölgesi maskelenmeli (dilate sonrası geniş)
    assert (mask[10:30, 50:150] > 0).sum() >= 1500
    # BG bölgesi büyük ölçüde temiz (dilate sızıntısı hariç)
    bg_region = mask[50:90, 10:40]
    assert (bg_region > 0).sum() < 100, f"BG temiz olmalı, görülen: {(bg_region > 0).sum()}"


def test_frame_text_mask_current_default_when_env_unset(monkeypatch):
    """Env var set edilmemişse default current mode kullanılır."""
    import numpy as np
    cv2 = pytest.importorskip("cv2")
    from core.pipelines.ocr.text_layer_row_reconstruct import _frame_text_mask, _text_mask_mode

    monkeypatch.delenv("OCR_TEXT_MASK_MODE", raising=False)
    assert _text_mask_mode() == "current"

    gray = np.full((50, 50), 100, dtype=np.uint8)
    gray[20:30, 20:30] = 230
    # Default (None) ile çağırıldığında hata vermemeli
    mask = _frame_text_mask(gray, cv2, np)
    assert mask.shape == gray.shape


def test_frame_text_mask_hybrid_is_intersection():
    """Hybrid mask = current AND strict_global."""
    import numpy as np
    cv2 = pytest.importorskip("cv2")
    from core.pipelines.ocr.text_layer_row_reconstruct import _frame_text_mask

    rng = np.random.default_rng(7)
    gray = rng.integers(30, 100, size=(80, 120), dtype=np.uint8)
    gray[20:40, 30:90] = 220  # parlak text patch

    current = _frame_text_mask(gray, cv2, np, mode="current")
    strict = _frame_text_mask(gray, cv2, np, mode="strict_global")
    hybrid = _frame_text_mask(gray, cv2, np, mode="hybrid")

    # Hybrid piksel sayısı ikisinin de altında veya eşit olmalı
    assert (hybrid > 0).sum() <= (current > 0).sum()
    assert (hybrid > 0).sum() <= (strict > 0).sum()


# ---------------------------------------------------------------------------
# _compute_boot_min adaptive bootstrap testleri
# ---------------------------------------------------------------------------


def test_compute_boot_min_short_scroll_drops_below_default():
    """SON METRO benzeri 45 frame'de boot_min adaptive değer (22) almalı.

    Sabit 50 eşiği 45 frame'de cruise_speed öğrenmeyi engelliyordu; smoothing
    ve band-clamp tetiklenmiyor, measured noise cumulative displacement'a
    sızıyordu. Yeni hesap: max(10, min(50, frame_count // 2)).
    """
    from core.pipelines.ocr.text_layer_row_reconstruct import _compute_boot_min

    assert _compute_boot_min(45) == 22
    assert _compute_boot_min(20) == 10  # floor guard
    assert _compute_boot_min(2) == 10  # extreme short
    assert _compute_boot_min(0) == 10  # defensive


def test_compute_boot_min_long_scroll_keeps_default_cap():
    """≥100 frame'de boot_min eski 50 sabitiyle aynı kalmalı (regression yok).

    ANJELIK (105 frame) ve daha uzun scroll'lar cap'i koruyor — uzun bootstrap
    cruise-speed median'ını stabilize ediyor.
    """
    from core.pipelines.ocr.text_layer_row_reconstruct import _compute_boot_min

    assert _compute_boot_min(100) == 50
    assert _compute_boot_min(105) == 50  # ANJELIK
    assert _compute_boot_min(200) == 50
    assert _compute_boot_min(500) == 50


# ---------------------------------------------------------------------------
# §25 — Hakim gözlemci modu (yeni seçim politikası + shadow log)
# ---------------------------------------------------------------------------


def _make_candidate(
    name: str,
    *,
    composite,
    row_count: int,
    score: float,
    quality_score_value: float = 0.5,
    motion_status: str = "ok",
) -> dict:
    """Yardımcı: _candidate_summary / shadow helper'lar için aday sözlüğü inşa et."""
    return {
        "name": name,
        "status": "ok" if composite is not None else "no_composite",
        "score": score,
        "score_parts": {"quality": quality_score_value, "rows": 0.0, "split": 0.0, "motion": 0.0, "penalty": 0.0, "bias": 0.0},
        "selected": False,
        "composite": composite,
        "motion": {"status": motion_status, "estimator": name},
        "quality": {"score": quality_score_value, "sharpness": 0.0, "contrast": 0.0, "text_density": 0.0},
        "auto_split": {"split_x": None, "confidence": 0.0, "status": "no_text_pixels"},
        "row_count": row_count,
        "rows": [{"index": i + 1, "y0": i * 20, "y1": i * 20 + 15} for i in range(row_count)],
    }


def test_hakim_shadow_decision_logs_when_opted_in(monkeypatch):
    """OCR_HAKIM_SHADOW=1 ile gözlemci-logu açılır; panorama seçilse de Hakim 'static' derdi."""
    import numpy as np
    from core.pipelines.ocr.text_layer_row_reconstruct import _candidate_summary, _compute_hakim_shadow_decision

    monkeypatch.setenv("OCR_HAKIM_SHADOW", "1")
    composite = np.zeros((400, 300, 3), dtype=np.uint8)
    current = _make_candidate("current_displacement", composite=composite, row_count=24, score=0.55, quality_score_value=0.46)
    static = _make_candidate("static_best_frame", composite=composite.copy(), row_count=6, score=0.62, quality_score_value=0.62)
    current["selected"] = True  # Yeni politika panorama seçti

    summary = _candidate_summary(current, [current, static])
    shadow = summary["hakim_shadow_decision"]

    # Yeni politika string'i
    assert summary["selection_policy"] == "current_first_with_emergency_static_fallback"
    assert summary["selected"] == "current_displacement"
    # Hakim eski formülle static seçecekti (0.62 > 0.55 + 0.06)
    direct = _compute_hakim_shadow_decision([current, static])
    assert direct["would_select"] == "static_best_frame"
    assert shadow["would_select"] == "static_best_frame"
    assert shadow["scores"]["current_displacement"] == 0.55
    assert shadow["scores"]["static_best_frame"] == 0.62


def test_select_panorama_when_row_count_positive(tmp_path):
    """current_displacement.composite var + row_count>0 → panorama seçilir, fallback yok."""
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    frames = _make_scrolling_role_name_frames(tmp_path / "frames_panorama")
    output_dir = tmp_path / "row_reconstruct_panorama"
    result = run_text_layer_row_reconstruct(frame_paths=frames, output_dir=output_dir, max_frames=60, scale_for_rows=1)
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))

    assert summary["candidate_selector"]["selected"] == "current_displacement"
    assert summary["candidate_selector"]["selection_policy"] == "current_first_with_emergency_static_fallback"
    # row_count pozitif olduğu için fallback_reason kayıtlı olmamalı
    assert "fallback_reason" not in summary["candidate_selector"]


def test_select_static_fallback_when_panorama_row_count_zero():
    """Panorama composite var ama row_count=0 → static_best_frame'e düş."""
    import numpy as np
    from core.pipelines.ocr.text_layer_row_reconstruct import _candidate_summary, _select_best_row_candidate

    # _select_best_row_candidate çağırmak yerine direkt fallback davranışını
    # doğruluyoruz: _candidate_summary sonucu + selected.fallback_reason zinciri.
    composite = np.zeros((300, 200, 3), dtype=np.uint8)
    current = _make_candidate("current_displacement", composite=composite, row_count=0, score=0.20)
    static = _make_candidate("static_best_frame", composite=composite.copy(), row_count=8, score=0.55)
    static["selected"] = True
    current["fallback_reason"] = None  # placeholder
    static["fallback_reason"] = "current_row_count_zero"

    summary = _candidate_summary(static, [current, static])
    assert summary["selected"] == "static_best_frame"
    assert summary.get("fallback_reason") == "current_row_count_zero"
    # Hakim default kapalı → shadow disabled marker (seçim Hakim'den bağımsız)
    assert summary["hakim_shadow_decision"]["status"] == "disabled"


def test_select_static_fallback_when_panorama_composite_none():
    """Panorama composite None → static_best_frame'e düş, fallback_reason='current_composite_none'."""
    import numpy as np
    from core.pipelines.ocr.text_layer_row_reconstruct import _candidate_summary

    static_composite = np.zeros((300, 200, 3), dtype=np.uint8)
    current = _make_candidate("current_displacement", composite=None, row_count=0, score=0.0)
    current["status"] = "no_composite"
    static = _make_candidate("static_best_frame", composite=static_composite, row_count=8, score=0.55)
    static["selected"] = True
    static["fallback_reason"] = "current_composite_none"

    summary = _candidate_summary(static, [current, static])
    assert summary["selected"] == "static_best_frame"
    assert summary.get("fallback_reason") == "current_composite_none"


def test_hakim_shadow_disabled_by_default_enabled_when_opted_in(tmp_path, monkeypatch):
    """Hakim default KAPALI (status=disabled); OCR_HAKIM_SHADOW=1 ile gözlemci-logu dolar."""
    # Default koşum: shadow kapalı
    frames = _make_scrolling_role_name_frames(tmp_path / "frames_shadow_off")
    result_off = run_text_layer_row_reconstruct(
        frame_paths=frames, output_dir=tmp_path / "ror_off", max_frames=60, scale_for_rows=1
    )
    summary_off = json.loads(result_off.summary_path.read_text(encoding="utf-8"))
    assert summary_off["candidate_selector"]["hakim_shadow_decision"]["status"] == "disabled"

    # Opt-in koşum: shadow açık, would_select + scores dolu
    monkeypatch.setenv("OCR_HAKIM_SHADOW", "1")
    frames2 = _make_scrolling_role_name_frames(tmp_path / "frames_shadow_on")
    result_on = run_text_layer_row_reconstruct(
        frame_paths=frames2, output_dir=tmp_path / "ror_on", max_frames=60, scale_for_rows=1
    )
    summary_on = json.loads(result_on.summary_path.read_text(encoding="utf-8"))
    shadow = summary_on["candidate_selector"]["hakim_shadow_decision"]
    assert shadow["would_select"] in {"current_displacement", "static_best_frame", None}
    assert "scores" in shadow
    assert any(value is not None for value in shadow["scores"].values())


def test_hakim_shadow_decision_anjelik_scenario_reproduction(monkeypatch):
    """ANJELIK örneği: Hakim panorama'ya 0.456, static'e 0.623 verir → 'static' derdi.

    Yeni politika row_count>0 olan panorama'yı seçer; OCR_HAKIM_SHADOW=1 ile açılan
    gözlemci-logu Hakim'in 'static' diyeceğini kaydetmeli (eski sabote eden davranış)."""
    import numpy as np
    from core.pipelines.ocr.text_layer_row_reconstruct import _candidate_summary, _compute_hakim_shadow_decision

    monkeypatch.setenv("OCR_HAKIM_SHADOW", "1")
    composite_panorama = np.zeros((3200, 600, 3), dtype=np.uint8)
    composite_static = np.zeros((720, 600, 3), dtype=np.uint8)
    # Hakim formülünden bağımsız, ham skorları doğrudan veriyoruz (telemetri)
    current = _make_candidate("current_displacement", composite=composite_panorama, row_count=66, score=0.456)
    static = _make_candidate("static_best_frame", composite=composite_static, row_count=14, score=0.623)
    current["selected"] = True  # Yeni politika panorama dedi

    summary = _candidate_summary(current, [current, static])
    shadow = summary["hakim_shadow_decision"]

    # Gerçek seçim panorama, ama Hakim eski formülle static seçerdi
    assert summary["selected"] == "current_displacement"
    assert shadow["would_select"] == "static_best_frame"
    # Skor farkı 0.06 marjını geçtiği için Hakim "static" derdi
    direct = _compute_hakim_shadow_decision([current, static])
    assert direct["would_select"] == "static_best_frame"
