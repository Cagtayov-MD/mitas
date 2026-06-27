# -*- coding: utf-8 -*-
"""OneOCR-tabanlı çıkış-jeneriği başlangıç (onset) detektörü — Plan B (2026-06-27).

DÜŞÜK-RİSK MİMARİ: paddle detektörünün (jenerik_frame_pool_detector.py) v31-valide
find_onset/postprocess MANTIĞINI ve tüm semantic yardımcılarını OLDUĞU GİBİ yeniden kullanır;
SADECE per-kare skoru paddle yerine OneOCR kutularından üretir. Skor-formülü paddle_frame_score
ile BİREBİR aynı tutulur (eşikler transfer olsun). Paddle dosyasına DOKUNULMAZ.

AVANTAJ: OneOCR tüm script'leri (Latin/Fransızca-küçük-harf/Arapça/Kiril) native okur →
paddle'ın dil-körlüğü + Fix B/E/zinciri GEREKSİZ. Maliyet ~2.5x yavaş (kabul edildi).

Koşum (venvs/ocr):
  python -m core.pipelines.ocr.jenerik_oneocr_detector <frames_dir> [--out DIR] [--stride 8]
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from core.pipelines.ocr.jenerik_frame_pool_detector import (
    DetectorConfig,
    DetectionResult,
    FrameScore,
    filter_ocr_boxes,
    find_onset,
    imread_unicode,
    is_prose_scene_text,
    is_scene_sign_text,
    is_subtitle_scene_text,
    is_ui_scene_text,
    line_stats,
    list_images,
    natural_frame_no,
    normalized_frame_change,
    phase_text_motion,
    postprocess_detection_result,
    resize_for_scan,
    semantic_text_features,
    write_scores_csv,
)


def make_oneocr_engine():
    import oneocr
    return oneocr.OcrEngine()


def oneocr_line_boxes(eng, image_bgr: np.ndarray) -> list[tuple[tuple[int, int, int, int], str]]:
    """Bir BGR kareden OneOCR satırlarını (box, text) olarak çıkar."""
    from PIL import Image
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    try:
        res = eng.recognize_pil(Image.fromarray(rgb))
    except Exception:
        return []
    out: list[tuple[tuple[int, int, int, int], str]] = []
    for ln in (res.get("lines") or []):
        t = (ln.get("text") or "").strip()
        if not t:
            continue
        br = ln.get("bounding_rect") or {}
        xs = [br[k] for k in ("x1", "x2", "x3", "x4") if br.get(k) is not None]
        ys = [br[k] for k in ("y1", "y2", "y3", "y4") if br.get(k) is not None]
        if not xs or not ys:
            continue
        box = (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))
        out.append((box, t))
    return out


def oneocr_frame_score(eng, image: np.ndarray, cfg: DetectorConfig) -> tuple[float, dict, np.ndarray]:
    """paddle_frame_score'un BİREBİR aynası; kutu/metin kaynağı OneOCR. (score, info, box_mask) döndürür."""
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    dark_ratio = float(np.count_nonzero(gray < 42) / max(1, gray.size))
    luma_mean = float(gray.mean())

    items = oneocr_line_boxes(eng, image)
    boxes: list[tuple[int, int, int, int]] = []
    texts: list[str] = []
    for box, t in items:
        if filter_ocr_boxes([box], w, h):
            boxes.append(box)
            texts.append(t)

    mask = np.zeros((h, w), np.uint8)
    for x1, y1, x2, y2 in boxes:
        cv2.rectangle(mask, (max(0, x1), max(0, y1)), (min(w - 1, x2), min(h - 1, y2)), 255, -1)

    if not boxes:
        info = {"mask_density": 0.0, "component_count": 0, "line_count": 0, "vertical_coverage": 0.0,
                "y_min": None, "y_max": None, "bottom_only": False, "dark_ratio": dark_ratio,
                "luma_mean": luma_mean, "ocr_text": "", "semantic_score": 0.0, "credit_keyword_count": 0,
                "name_like_count": 0, "two_column_layout": False, "end_card_like": False,
                "prose_like": False, "scene_sign_like": False, "subtitle_like": False, "ui_like": False}
        return 0.0, info, mask

    lines, coverage, y_min, y_max = line_stats(mask)
    active_cols = np.where((mask > 0).any(axis=0))[0]
    if active_cols.size:
        x_min = float(active_cols.min() / max(1, w - 1))
        x_max = float(active_cols.max() / max(1, w - 1))
        x_center = (x_min + x_max) / 2.0
        x_coverage = max(0.0, x_max - x_min)
    else:
        x_center, x_coverage = 0.5, 0.0
    density = float(np.count_nonzero(mask) / max(1, mask.size))
    bottom_only = bool(y_min is not None and y_min >= cfg.bottom_only_y and coverage < 0.12 and lines <= 2)

    density_score = min(1.0, density / 0.035)
    box_score = min(1.0, len(boxes) / 8.0)
    line_score = min(1.0, max(lines, len(boxes) // 2) / 4.0)
    coverage_score = min(1.0, coverage / 0.24)
    score = 0.36 * density_score + 0.26 * box_score + 0.24 * line_score + 0.14 * coverage_score
    if len(boxes) >= 1 and lines >= 1:
        score += 0.10
    if len(boxes) >= 4:
        score += 0.10
    dark_credit_field = dark_ratio >= 0.48 or luma_mean <= 58.0

    features = semantic_text_features(texts, boxes, w, h)
    prose_like = is_prose_scene_text(texts) or bool(features["epilogue_like"])
    scene_sign_like = is_scene_sign_text(texts, box_count=len(boxes), dark_ratio=dark_ratio, luma_mean=luma_mean) or bool(features["plaque_like"])
    subtitle_like = is_subtitle_scene_text(texts, y_min=y_min, y_max=y_max, box_count=len(boxes),
                                           line_count=max(lines, 1 if boxes else 0), dark_ratio=dark_ratio, luma_mean=luma_mean)
    ui_like = is_ui_scene_text(texts)
    end_card_like = bool(features["end_card_like"])

    if len(boxes) <= 1 and density < 0.10:
        score *= 0.06
    elif len(boxes) <= 1 and not dark_credit_field:
        score *= 0.18
    elif len(boxes) <= 1:
        score *= 0.50
    elif len(boxes) <= 2 and lines <= 2 and not dark_credit_field:
        score *= 0.42
    elif len(boxes) <= 3 and lines <= 1 and not dark_credit_field:
        score *= 0.68
    small_offcenter_text = (len(boxes) <= 2 and lines <= 2 and x_coverage < 0.30 and not (0.39 <= x_center <= 0.61))
    tiny_text_island = len(boxes) <= 2 and lines <= 1 and x_coverage < 0.20 and coverage < 0.14
    if small_offcenter_text:
        score *= 0.24
    elif tiny_text_island:
        score *= 0.50
    if ui_like:
        score *= 0.08
    if scene_sign_like:
        score *= 0.05
    if subtitle_like:
        score *= 0.04
    # Fix E gömülü (koşulsuz): iki-sütun + yüksek-semantic NET kredi karelerini düzyazı-cezasından muaf
    # tut. OneOCR'ın temiz çoklu-script okuması bu muafiyeti güvenli kılar (FR/IT küçük-harf kredi kurtulur).
    if prose_like and not (features["two_column_layout"] and features["semantic_score"] >= 0.45):
        score *= 0.08
    if end_card_like:
        score *= 0.10
    if bottom_only:
        score *= 0.45

    info = {"mask_density": density, "component_count": len(boxes), "line_count": max(lines, 1 if boxes else 0),
            "vertical_coverage": coverage, "y_min": y_min, "y_max": y_max, "bottom_only": bottom_only,
            "dark_ratio": dark_ratio, "luma_mean": luma_mean, "ocr_text": " | ".join(texts)[:500],
            "semantic_score": features["semantic_score"], "credit_keyword_count": features["credit_keyword_count"],
            "name_like_count": features["name_like_count"], "two_column_layout": features["two_column_layout"],
            "end_card_like": end_card_like, "prose_like": prose_like, "scene_sign_like": scene_sign_like,
            "subtitle_like": subtitle_like, "ui_like": ui_like}
    return max(0.0, min(1.0, score)), info, mask


def score_frames_oneocr(frame_dir: Path, cfg: DetectorConfig, eng, stride: int = 1) -> tuple[list[Path], list[FrameScore], list[np.ndarray]]:
    # HIZ: her kareyi değil her stride'ıncı kareyi OCR'la (paddle gibi). FrameScore.pos = alt-örneklem
    # indeksi; gerçek kare frame_no/file'da korunur. start_pos detect'te ×stride ile tam-kareye çevrilir.
    full_paths = list_images(frame_dir)
    paths = full_paths[::stride] if stride > 1 else full_paths
    scores: list[FrameScore] = []
    masks: list[np.ndarray] = []
    prev_gray = prev_mask = None
    for pos, path in enumerate(paths):
        image = imread_unicode(path)
        if image is None:
            scores.append(FrameScore(pos=pos, frame_no=natural_frame_no(path), file=path.name,
                                     text_score=0.0, mask_density=0.0, component_count=0, line_count=0,
                                     vertical_coverage=0.0, y_min=None, y_max=None, bottom_only=False,
                                     dark_ratio=0.0, luma_mean=0.0, frame_change=0.0, text_dy=0.0,
                                     text_dx=0.0, phase_response=0.0, credit_like=False))
            masks.append(np.zeros((1, 1), np.uint8))
            prev_gray = prev_mask = None
            continue
        image = resize_for_scan(image, cfg.max_width)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        text_score, info, mask = oneocr_frame_score(eng, image, cfg)
        dx, dy, response = phase_text_motion(prev_gray, prev_mask, gray.copy(), mask)
        change = normalized_frame_change(prev_gray, gray)
        scores.append(FrameScore(
            pos=pos, frame_no=natural_frame_no(path), file=path.name,
            text_score=round(float(text_score), 5), mask_density=round(float(info["mask_density"]), 6),
            component_count=int(info["component_count"]), line_count=int(info["line_count"]),
            vertical_coverage=round(float(info["vertical_coverage"]), 5),
            y_min=None if info["y_min"] is None else round(float(info["y_min"]), 5),
            y_max=None if info["y_max"] is None else round(float(info["y_max"]), 5),
            bottom_only=bool(info["bottom_only"]), dark_ratio=round(float(info["dark_ratio"]), 5),
            luma_mean=round(float(info["luma_mean"]), 3), frame_change=round(float(change), 5),
            text_dy=round(float(dy), 4), text_dx=round(float(dx), 4), phase_response=round(float(response), 4),
            credit_like=bool(text_score >= cfg.text_threshold), ocr_text=str(info.get("ocr_text") or ""),
            semantic_score=round(float(info.get("semantic_score", 0.0) or 0.0), 4),
            credit_keyword_count=int(info.get("credit_keyword_count", 0) or 0),
            name_like_count=int(info.get("name_like_count", 0) or 0),
            two_column_layout=bool(info.get("two_column_layout", False)),
            end_card_like=bool(info.get("end_card_like", False)), prose_like=bool(info.get("prose_like", False)),
            scene_sign_like=bool(info.get("scene_sign_like", False)), subtitle_like=bool(info.get("subtitle_like", False)),
            ui_like=bool(info.get("ui_like", False))))
        masks.append(mask)
        prev_gray, prev_mask = gray, mask
    return paths, scores, masks


def detect_frame_dir_oneocr(frame_dir: Path, out_dir: Path | None, cfg: DetectorConfig, eng=None, stride: int = 1) -> DetectionResult:
    if eng is None:
        eng = make_oneocr_engine()
    paths, scores, _ = score_frames_oneocr(frame_dir, cfg, eng, stride=stride)
    result = find_onset(paths, scores, cfg, frame_dir)
    result = postprocess_detection_result(paths, scores, result, cfg)
    # stride alt-örneklem indekslerini TAM-kare indeksine çevir (havuz list_images TAM listeyi kullanır).
    if stride > 1:
        if result.start_pos is not None:
            result.start_pos = int(result.start_pos) * stride
        if result.first_text_pos is not None:
            result.first_text_pos = int(result.first_text_pos) * stride
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "result.json").write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
        write_scores_csv(out_dir / "scores.csv", scores)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OneOCR-tabanlı jenerik onset detektörü")
    ap.add_argument("frames")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-width", type=int, default=DetectorConfig.max_width)
    ap.add_argument("--text-threshold", type=float, default=DetectorConfig.text_threshold)
    ap.add_argument("--soft-threshold", type=float, default=DetectorConfig.soft_threshold)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    cfg = DetectorConfig(max_width=args.max_width, text_threshold=args.text_threshold,
                         soft_threshold=args.soft_threshold, ocr_mode="oneocr")
    res = detect_frame_dir_oneocr(Path(args.frames), Path(args.out) if args.out else None, cfg)
    print(json.dumps(asdict(res), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
