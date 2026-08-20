from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import re
from statistics import median
from typing import Iterable
import unicodedata

import cv2
import numpy as np


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
_PADDLE_CACHE: dict[str, object] = {}

# Çok-dilli kredi-rol anahtarları (Arapça/Farsça/Kiril/Yunanca) — credit_terms Latin-merkezli; bu liste
# OneOCR'ın okuduğu non-Latin kredi kelimelerini HAM metinde yakalar. Latin/Türkçe'de eşleşmez → additive,
# 0-regresyon. Recall için geniş (kök/stem ile çekim varyantları): atlama riskini düşürür.
_ML_CREDIT_RE = re.compile(
    # Arapça
    "إخراج|اخراج|مخرج|سيناريو|تأليف|قصة|تمثيل|بطولة|موسيق|مونتاج|تصوير|إنتاج|انتاج|الأدوار|الادوار|أدوار|"
    "مساعد|أداء|اداء|حوار|ديكور|ملابس|تصميم|"
    # Farsça (Arap-alfabe ek harfler: گ چ پ ژ)
    "کارگردان|فیلمنامه|بازیگر|تهیه|موسیقی|تدوین|فیلمبردار|طراح|"
    # Kiril (Rusça vb.) — kök/stem
    "режисс|постанов|сценар|оператор|монтаж|музык|композит|продюс|ролях|роли|актёр|актер|актрис|художн|"
    "звук|производ|съёмк|съемк|оформлен|"
    # Yunanca — kök/stem
    "σκηνοθεσ|σενάρ|μουσικ|παραγωγ|ηθοποι|φωτογραφ|μοντάζ"
)


@dataclass
class DetectorConfig:
    max_width: int = 640
    text_threshold: float = 0.34
    soft_threshold: float = 0.23
    lookahead: int = 8
    min_hits: int = 3
    preroll_frames: int = 2
    already_credit_frames: int = 5
    bottom_only_y: float = 0.69
    ocr_mode: str = "none"
    ocr_stride: int = 5
    ocr_lang: str = "en"
    sustain_window: int = 18
    sustain_hits: int = 6


@dataclass
class FrameScore:
    pos: int
    frame_no: int | None
    file: str
    text_score: float
    mask_density: float
    component_count: int
    line_count: int
    vertical_coverage: float
    y_min: float | None
    y_max: float | None
    bottom_only: bool
    dark_ratio: float
    luma_mean: float
    frame_change: float
    text_dy: float
    text_dx: float
    phase_response: float
    credit_like: bool
    ocr_text: str = ""
    semantic_score: float = 0.0
    credit_keyword_count: int = 0
    name_like_count: int = 0
    two_column_layout: bool = False
    end_card_like: bool = False
    prose_like: bool = False
    scene_sign_like: bool = False
    subtitle_like: bool = False
    ui_like: bool = False


@dataclass
class DetectionResult:
    frame_dir: str
    total_frames: int
    status: str
    start_pos: int | None
    start_frame_no: int | None
    start_file: str | None
    first_text_pos: int | None
    first_text_frame_no: int | None
    first_text_file: str | None
    confidence: float
    credit_type: str
    reason: str
    config: dict


def natural_frame_no(path: Path) -> int | None:
    numbers = re.findall(r"\d+", path.stem)
    if not numbers:
        return None
    return int(numbers[-1])


def list_images(frame_dir: Path) -> list[Path]:
    files = [p for p in frame_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    return sorted(files, key=lambda p: (natural_frame_no(p) is None, natural_frame_no(p) or 0, p.name.lower()))


def imread_unicode(path: Path) -> np.ndarray | None:
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def resize_for_scan(image: np.ndarray, max_width: int) -> np.ndarray:
    h, w = image.shape[:2]
    if w <= max_width:
        return image
    scale = max_width / float(w)
    new_size = (max_width, max(1, int(round(h * scale))))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def text_like_mask(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, w = gray.shape[:2]
    short = max(1, min(h, w))
    kx = max(9, int(short * 0.035) | 1)
    ky = max(3, int(short * 0.010) | 1)
    rect = cv2.getStructuringElement(cv2.MORPH_RECT, (kx, ky))

    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, rect)
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, rect)
    blur = cv2.GaussianBlur(gray, (0, 0), 2.2)
    local = cv2.absdiff(gray, blur)

    top_thr = max(10.0, float(tophat.mean()) + 1.25 * float(tophat.std()))
    black_thr = max(10.0, float(blackhat.mean()) + 1.25 * float(blackhat.std()))
    local_thr = max(8.0, float(local.mean()) + 1.15 * float(local.std()))
    bright_gate = gray > max(56.0, float(gray.mean()) + 0.10 * float(gray.std()))
    dark_gate = gray < min(205.0, float(gray.mean()) - 0.35 * float(gray.std()))

    bright_text = ((tophat > top_thr) | ((local > local_thr) & bright_gate)).astype(np.uint8) * 255
    dark_text = ((blackhat > black_thr) | ((local > local_thr * 1.1) & dark_gate)).astype(np.uint8) * 255
    saturated_text = (
        (hsv[:, :, 1] > 65)
        & (hsv[:, :, 2] > 75)
        & (local > max(6.0, local_thr * 0.55))
    ).astype(np.uint8) * 255

    mask = cv2.bitwise_or(cv2.bitwise_or(bright_text, dark_text), saturated_text)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 2), np.uint8), iterations=1)
    return filter_text_components(mask)


def filter_text_components(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
    h, w = mask.shape[:2]
    out = np.zeros_like(mask)
    max_area = max(40, int(h * w * 0.020))
    min_h = max(2, int(h * 0.006))
    max_h = max(12, int(h * 0.18))
    for label in range(1, count):
        x, y, cw, ch, area = stats[label]
        if area < 3 or area > max_area:
            continue
        if ch < min_h or ch > max_h:
            continue
        if cw < 2 or cw > w * 0.90:
            continue
        # Keep single letters, but reject tall thin scratches and large graphic blocks.
        aspect = cw / max(1.0, float(ch))
        fill = area / max(1.0, float(cw * ch))
        if aspect < 0.08 or fill > 0.86:
            continue
        if ch > h * 0.12 and aspect < 0.35:
            continue
        out[labels == label] = 255
    out = cv2.dilate(out, np.ones((2, 2), np.uint8), iterations=1)
    return out


def line_stats(mask: np.ndarray) -> tuple[int, float, float | None, float | None]:
    active = mask > 0
    if int(active.sum()) < 8:
        return 0, 0.0, None, None
    h, w = mask.shape[:2]
    row_profile = active.sum(axis=1).astype(np.float32)
    smooth_k = max(3, int(h * 0.012) | 1)
    smooth = np.convolve(row_profile, np.ones(smooth_k, dtype=np.float32) / smooth_k, mode="same")
    active_rows = smooth > max(2.0, w * 0.006)
    rows = np.where(active_rows)[0]
    if rows.size == 0:
        return 0, 0.0, None, None
    bands = 0
    prev = -10
    for row in rows:
        if row > prev + 2:
            bands += 1
        prev = int(row)
    y_min = float(rows.min() / max(1, h - 1))
    y_max = float(rows.max() / max(1, h - 1))
    return bands, float(rows.size / max(1, h)), y_min, y_max


def component_count(mask: np.ndarray) -> int:
    count, _labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
    h, w = mask.shape[:2]
    good = 0
    for label in range(1, count):
        _x, _y, cw, ch, area = stats[label]
        if area >= 5 and ch >= max(2, h * 0.006) and cw >= 2 and cw <= w * 0.85:
            good += 1
    return good


def frame_text_score(
    image: np.ndarray,
    mask: np.ndarray,
    *,
    cfg: DetectorConfig,
) -> tuple[float, dict]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    density = float(np.count_nonzero(mask) / max(1, mask.size))
    lines, coverage, y_min, y_max = line_stats(mask)
    comps = component_count(mask)
    bottom_only = bool(
        y_min is not None
        and y_max is not None
        and y_min >= cfg.bottom_only_y
        and coverage < 0.11
        and lines <= 2
    )

    density_score = min(1.0, density / 0.018)
    comp_score = min(1.0, comps / 22.0)
    line_score = min(1.0, lines / 4.0)
    coverage_score = min(1.0, coverage / 0.22)
    band_height = 0.0 if y_min is None or y_max is None else max(0.0, y_max - y_min)
    title_bonus = 0.12 if comps >= 3 and lines >= 1 and band_height >= 0.045 else 0.0
    multi_line_bonus = 0.10 if lines >= 3 else 0.0

    score = (
        0.38 * density_score
        + 0.23 * line_score
        + 0.18 * comp_score
        + 0.16 * coverage_score
        + title_bonus
        + multi_line_bonus
    )
    if comps < 2 or density < 0.00055:
        score *= 0.25
    elif comps < 4 and lines <= 1:
        score *= 0.72
    if bottom_only:
        score *= 0.42

    # Strong full-screen credits often sit over very dark or very flat fields.
    dark_ratio = float(np.count_nonzero(gray < 38) / max(1, gray.size))
    if dark_ratio > 0.45 and comps >= 3 and not bottom_only:
        score += 0.06
    return max(0.0, min(1.0, score)), {
        "mask_density": density,
        "component_count": comps,
        "line_count": lines,
        "vertical_coverage": coverage,
        "y_min": y_min,
        "y_max": y_max,
        "bottom_only": bottom_only,
        "dark_ratio": dark_ratio,
        "luma_mean": float(gray.mean()),
    }


def phase_text_motion(prev_gray: np.ndarray | None, prev_mask: np.ndarray | None, gray: np.ndarray, mask: np.ndarray) -> tuple[float, float, float]:
    if prev_gray is None or prev_mask is None:
        return 0.0, 0.0, 0.0
    h, w = gray.shape[:2]
    if prev_gray.shape != gray.shape:
        return 0.0, 0.0, 0.0
    union = cv2.dilate(cv2.bitwise_or(prev_mask, mask), np.ones((9, 9), np.uint8), iterations=1)
    if int(np.count_nonzero(union)) < max(40, int(h * w * 0.0008)):
        return 0.0, 0.0, 0.0
    a = prev_gray.astype(np.float32)
    b = gray.astype(np.float32)
    a[union == 0] = 0.0
    b[union == 0] = 0.0
    try:
        (dx, dy), response = cv2.phaseCorrelate(a, b)
    except cv2.error:
        return 0.0, 0.0, 0.0
    if abs(dx) > w * 0.25 or abs(dy) > h * 0.25:
        return 0.0, 0.0, 0.0
    return float(dx), float(dy), float(response)


def normalized_frame_change(prev_gray: np.ndarray | None, gray: np.ndarray) -> float:
    if prev_gray is None or prev_gray.shape != gray.shape:
        return 0.0
    diff = cv2.absdiff(prev_gray, gray)
    return float(np.mean(diff) / 255.0)


def score_frames(frame_dir: Path, cfg: DetectorConfig) -> tuple[list[Path], list[FrameScore], list[np.ndarray]]:
    paths = list_images(frame_dir)
    scores: list[FrameScore] = []
    masks: list[np.ndarray] = []
    prev_gray: np.ndarray | None = None
    prev_mask: np.ndarray | None = None
    for pos, path in enumerate(paths):
        image = imread_unicode(path)
        if image is None:
            # DET-1 fix (2026-06-27): okunamayan kareyi ATLAMA — BOŞ skor ekle ki scores listesi
            # paths ile 1:1 kalsın (score.pos == liste-index == list_images index == pool start_pos uzayı).
            # Eskiden `continue` indeksleri kaydırıyordu → paddle skorları %18'e çöküp not_found üretebiliyordu.
            # Temiz karelerde (hiç None yok) bu dal HİÇ çalışmaz → davranış birebir AYNI (sıfır regresyon).
            scores.append(FrameScore(
                pos=pos, frame_no=natural_frame_no(path), file=path.name,
                text_score=0.0, mask_density=0.0, component_count=0, line_count=0,
                vertical_coverage=0.0, y_min=None, y_max=None, bottom_only=False,
                dark_ratio=0.0, luma_mean=0.0, frame_change=0.0,
                text_dy=0.0, text_dx=0.0, phase_response=0.0, credit_like=False,
            ))
            masks.append(np.zeros((1, 1), np.uint8))
            prev_gray = None
            prev_mask = None
            continue
        image = resize_for_scan(image, cfg.max_width)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mask = text_like_mask(image)
        text_score, info = frame_text_score(image, mask, cfg=cfg)
        dx, dy, response = phase_text_motion(prev_gray, prev_mask, gray.copy(), mask)
        change = normalized_frame_change(prev_gray, gray)
        scores.append(
            FrameScore(
                pos=pos,
                frame_no=natural_frame_no(path),
                file=path.name,
                text_score=round(float(text_score), 5),
                mask_density=round(float(info["mask_density"]), 6),
                component_count=int(info["component_count"]),
                line_count=int(info["line_count"]),
                vertical_coverage=round(float(info["vertical_coverage"]), 5),
                y_min=None if info["y_min"] is None else round(float(info["y_min"]), 5),
                y_max=None if info["y_max"] is None else round(float(info["y_max"]), 5),
                bottom_only=bool(info["bottom_only"]),
                dark_ratio=round(float(info["dark_ratio"]), 5),
                luma_mean=round(float(info["luma_mean"]), 3),
                frame_change=round(float(change), 5),
                text_dy=round(float(dy), 4),
                text_dx=round(float(dx), 4),
                phase_response=round(float(response), 4),
                credit_like=bool(text_score >= cfg.text_threshold),
            )
        )
        masks.append(mask)
        prev_gray = gray
        prev_mask = mask
    if cfg.ocr_mode == "paddle" and scores:
        refine_scores_with_paddle(paths, scores, cfg)
    return paths, scores, masks


def refine_scores_with_paddle(paths: list[Path], scores: list[FrameScore], cfg: DetectorConfig) -> None:
    try:
        from paddleocr import PaddleOCR
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "PaddleOCR is not importable in this Python. Run with a Python that has paddleocr, "
            "for example E:\\MITAS\\venvs\\ocr\\Scripts\\python.exe on this machine."
        ) from exc

    if cfg.ocr_lang not in _PADDLE_CACHE:
        # Linux geçişi 2026-07-16: MITAS_ önekli env de kabul (mitas.env bu adı kullanıyor — önek uyuşmazlığı fix'i).
        model_root = Path(
            os.environ.get("JENERIK_PADDLE_MODEL_ROOT")
            or os.environ.get("MITAS_JENERIK_PADDLE_MODEL_ROOT")
            or (Path(os.environ.get("MITAS_PROJECT_ROOT") or "/opt/mitas")
                / "models" / "ocr" / "paddle" / "official_models"))
        rec_name = "latin_PP-OCRv5_mobile_rec" if cfg.ocr_lang.lower() == "latin" else "en_PP-OCRv5_mobile_rec"
        kwargs = {
            "lang": cfg.ocr_lang,
        }
        if os.environ.get("JENERIK_PADDLE_FAST_NO_DOC") == "1":
            kwargs["use_doc_orientation_classify"] = False
            kwargs["use_doc_unwarping"] = False
            kwargs["use_textline_orientation"] = False
        det_dir = model_root / "PP-OCRv5_server_det"
        rec_dir = model_root / rec_name
        if det_dir.exists():
            kwargs["text_detection_model_name"] = "PP-OCRv5_server_det"
            kwargs["text_detection_model_dir"] = str(det_dir)
        if rec_dir.exists():
            kwargs["text_recognition_model_name"] = rec_name
            kwargs["text_recognition_model_dir"] = str(rec_dir)
        _PADDLE_CACHE[cfg.ocr_lang] = PaddleOCR(**kwargs)
    ocr = _PADDLE_CACHE[cfg.ocr_lang]
    n = len(scores)
    stride = max(1, int(cfg.ocr_stride))
    coarse_positions = sorted(set(list(range(0, n, stride)) + [n - 1]))
    ocr_scores: dict[int, float] = {}
    ocr_info: dict[int, dict] = {}
    for pos in coarse_positions:
        value, info = paddle_frame_score(ocr, paths[pos], cfg)
        ocr_scores[pos] = value
        ocr_info[pos] = info

    coarse_hit = None
    for pos in coarse_positions:
        next_positions = [p for p in coarse_positions if pos <= p <= pos + stride * max(2, cfg.min_hits + 1)]
        hits = sum(1 for p in next_positions if ocr_scores.get(p, 0.0) >= cfg.text_threshold)
        if ocr_scores.get(pos, 0.0) >= cfg.text_threshold and hits >= 1:
            coarse_hit = pos
            break
        if hits >= 2:
            coarse_hit = pos
            break

    refine_positions: set[int] = set()
    if coarse_hit is not None:
        lo = max(0, coarse_hit - stride - cfg.preroll_frames - 2)
        hi = min(n - 1, coarse_hit + stride * 2 + cfg.lookahead)
        refine_positions.update(range(lo, hi + 1))
    # Always verify the very beginning so late/already-in-credit clips are not misread.
    refine_positions.update(range(0, min(n, max(cfg.already_credit_frames + 2, stride + 1))))

    for pos in sorted(refine_positions):
        if pos in ocr_scores:
            continue
        value, info = paddle_frame_score(ocr, paths[pos], cfg)
        ocr_scores[pos] = value
        ocr_info[pos] = info

    bridge_short_ocr_gaps(ocr_scores, ocr_info, cfg)

    # In OCR mode, OCR is authoritative for text presence on checked frames. Unchecked
    # frames keep only a weak heuristic trace so natural texture cannot trigger onset.
    for score in scores:
        if score.pos in ocr_scores:
            apply_ocr_score(score, ocr_scores[score.pos], ocr_info.get(score.pos, {}), cfg)
        else:
            score.text_score = round(float(min(score.text_score * 0.18, 0.20)), 5)
            score.credit_like = False


def paddle_frame_score(ocr: object, path: Path, cfg: DetectorConfig) -> tuple[float, dict]:
    image = imread_unicode(path)
    if image is None:
        return 0.0, {}
    image = resize_for_scan(image, cfg.max_width)
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    dark_ratio = float(np.count_nonzero(gray < 42) / max(1, gray.size))
    luma_mean = float(gray.mean())
    try:
        result = ocr.ocr(image)
    except Exception:
        return 0.0, {}
    text_items = extract_paddle_text_boxes(result)
    filtered_items: list[tuple[tuple[int, int, int, int], str, float]] = []
    for item in text_items:
        if filter_ocr_boxes([item[0]], w, h):
            filtered_items.append(item)
    boxes = [item[0] for item in filtered_items]
    if not boxes:
        return 0.0, {
            "mask_density": 0.0,
            "component_count": 0,
            "line_count": 0,
            "vertical_coverage": 0.0,
            "y_min": None,
            "y_max": None,
            "bottom_only": False,
            "dark_ratio": dark_ratio,
            "luma_mean": luma_mean,
            "ocr_text": "",
            "semantic_score": 0.0,
            "credit_keyword_count": 0,
            "name_like_count": 0,
            "two_column_layout": False,
            "end_card_like": False,
            "prose_like": False,
            "scene_sign_like": False,
            "subtitle_like": False,
            "ui_like": False,
        }
    mask = np.zeros((h, w), np.uint8)
    for x1, y1, x2, y2 in boxes:
        cv2.rectangle(mask, (max(0, x1), max(0, y1)), (min(w - 1, x2), min(h - 1, y2)), 255, -1)
    lines, coverage, y_min, y_max = line_stats(mask)
    active_cols = np.where((mask > 0).any(axis=0))[0]
    if active_cols.size:
        x_min = float(active_cols.min() / max(1, w - 1))
        x_max = float(active_cols.max() / max(1, w - 1))
        x_center = (x_min + x_max) / 2.0
        x_coverage = max(0.0, x_max - x_min)
    else:
        x_center = 0.5
        x_coverage = 0.0
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
    texts = [item[1] for item in filtered_items]
    features = semantic_text_features(texts, boxes, w, h)
    prose_like = is_prose_scene_text(texts) or bool(features["epilogue_like"])
    scene_sign_like = is_scene_sign_text(
        texts,
        box_count=len(boxes),
        dark_ratio=dark_ratio,
        luma_mean=luma_mean,
    ) or bool(features["plaque_like"])
    subtitle_like = is_subtitle_scene_text(
        texts,
        y_min=y_min,
        y_max=y_max,
        box_count=len(boxes),
        line_count=max(lines, 1 if boxes else 0),
        dark_ratio=dark_ratio,
        luma_mean=luma_mean,
    )
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
    small_offcenter_text = (
        len(boxes) <= 2
        and lines <= 2
        and x_coverage < 0.30
        and not (0.39 <= x_center <= 0.61)
    )
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
    if prose_like and not (
        _credit_prose_exempt_enabled()
        and features["two_column_layout"]
        and features["semantic_score"] >= 0.45
    ):
        score *= 0.08
    if end_card_like:
        score *= 0.10
    if bottom_only:
        score *= 0.45
    return max(0.0, min(1.0, score)), {
        "mask_density": density,
        "component_count": len(boxes),
        "line_count": max(lines, 1 if boxes else 0),
        "vertical_coverage": coverage,
        "y_min": y_min,
        "y_max": y_max,
        "bottom_only": bottom_only,
        "dark_ratio": dark_ratio,
        "luma_mean": luma_mean,
        "ocr_text": " | ".join(texts)[:500],
        "semantic_score": features["semantic_score"],
        "credit_keyword_count": features["credit_keyword_count"],
        "name_like_count": features["name_like_count"],
        "two_column_layout": features["two_column_layout"],
        "end_card_like": end_card_like,
        "prose_like": prose_like,
        "scene_sign_like": scene_sign_like,
        "subtitle_like": subtitle_like,
        "ui_like": ui_like,
    }


def bridge_short_ocr_gaps(ocr_scores: dict[int, float], ocr_info: dict[int, dict], cfg: DetectorConfig) -> None:
    positive = sorted(pos for pos, value in ocr_scores.items() if value >= cfg.text_threshold)
    if len(positive) < 2:
        return
    max_gap = max(2, int(cfg.ocr_stride) + 2)
    for left, right in zip(positive, positive[1:]):
        gap = right - left
        if gap <= 1 or gap > max_gap:
            continue
        bridge_score = max(cfg.text_threshold + 0.02, min(0.62, min(ocr_scores[left], ocr_scores[right]) * 0.70))
        bridge_info = ocr_info.get(left) or ocr_info.get(right) or {}
        for pos in range(left + 1, right):
            if ocr_scores.get(pos, 0.0) < cfg.soft_threshold:
                ocr_scores[pos] = bridge_score
                ocr_info[pos] = bridge_info


def valid_ocr_text(text: object, score: object, min_score: float = 0.42) -> bool:
    text_s = "" if text is None else str(text).strip()
    alnum = [ch for ch in text_s if ch.isalnum()]
    if len(alnum) < 2:
        return False
    try:
        score_f = float(score)
    except Exception:
        score_f = 1.0
    return score_f >= min_score


def normalize_ascii(text: str) -> str:
    text = text.replace("ı", "i").replace("İ", "I")
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def normalized_tokens(texts: list[str]) -> list[str]:
    joined = normalize_ascii(" ".join(texts))
    tokens = [re.sub(r"^\W+|\W+$", "", token) for token in re.split(r"\s+", joined)]
    return [token for token in tokens if token]


def is_end_card_text(texts: list[str]) -> bool:
    if not texts:
        return False
    cleaned = re.sub(r"[^a-z0-9]+", " ", normalize_ascii(" ".join(texts))).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned in {"the end", "end", "son", "fine", "fin", "finis"}


def _nonlatin_names_enabled() -> bool:
    """Latin-dışı (Arapça/Farsça/Sorani Kürtçe) isim satırlarını isim-benzeri say. DEFAULT OFF —
    MITAS_JENERIK_NONLATIN_NAMES=1 ile aç. FP riski: kısa non-cased sahne-yazısı/altyazı."""
    return os.environ.get("MITAS_JENERIK_NONLATIN_NAMES", "").strip().lower() in ("1", "true", "on", "yes")


def _latin_lowercase_names_enabled() -> bool:
    """Fix B (2026-06-27): küçük-harf CASED Latin kredi isimlerini (Fransızca/İtalyanca/İspanyolca —
    'pierre lary', 'michèle moretti') isim-benzeri say. DEFAULT OFF — MITAS_JENERIK_LATIN_LC_NAMES=1.
    Mevcut büyük-harf yolu (upper_ratio>=0.65) bu satırlara name_like=False veriyordu (Opus teyitli).
    FP koruması: fonksiyon-kelimesi (_LATIN_LC_STOPWORDS) içeren satır = altyazı/düzyazı → isim DEĞİL."""
    return os.environ.get("MITAS_JENERIK_LATIN_LC_NAMES", "").strip().lower() in ("1", "true", "on", "yes")


def _credit_prose_exempt_enabled() -> bool:
    """Fix E (2026-06-27): iki-sütunlu + yüksek-semantic kredi karelerini düzyazı-cezasından (score*=0.08)
    MUAF tut. DEFAULT OFF — MITAS_JENERIK_PROSE_CREDIT_EXEMPT=1. is_prose_scene_text küçük-harf Fransızca
    kredileri ('luis peralta | électriciens') düzyazı sanıp text_score'u katlediyor; two_column+semantic>=0.45
    NET kredidir → muaf. Koşul DAR: tek-sütun düzyazı/epilog (ANTON Çehov alıntısı, 2col=False) muaf DEĞİL."""
    return os.environ.get("MITAS_JENERIK_PROSE_CREDIT_EXEMPT", "").strip().lower() in ("1", "true", "on", "yes")


# Fix B FP-koruması: bu fonksiyon-kelimelerden biri satırda varsa = altyazı/düzyazı, isim DEĞİL.
# Hepsi normalize_ascii (aksansız küçük-harf) biçiminde. İsim-parçacıkları (de/von/van/di/la/le)
# KASITEN dışarıda — 'michel de broca' gibi parçacıklı isimler korunsun.
_LATIN_LC_STOPWORDS = {
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "est", "sont", "etre", "ne", "pas",
    "que", "qui", "pour", "avec", "dans", "mais", "comme", "tout", "tres", "bien", "plus", "ce",
    "cette", "ces", "mon", "ton", "son", "quoi", "quand",  # FR
    "i", "you", "he", "she", "we", "they", "is", "are", "was", "were", "have", "has", "this",
    "that", "with", "for", "not", "but", "what", "when", "your", "his", "her",  # EN
    "io", "lui", "lei", "noi", "voi", "sono", "che", "non", "per", "con", "ma", "questo",
    "quello", "molto",  # IT
    "yo", "ella", "nosotros", "ellos", "ellas", "para", "pero", "este", "esta", "muy",  # ES
    "ben", "sen", "biz", "siz", "icin", "ama", "gibi", "cok", "daha", "bu", "su", "var", "yok",
    "degil", "nasil",  # TR
}


def is_name_like_line(text: str) -> bool:
    raw = text.strip()
    if not raw or any(ch.isdigit() for ch in raw):
        return False
    if len(raw) > 32:
        return False
    if raw.count(".") >= 2 or any(ch in raw for ch in ":;!?"):
        return False
    tokens = [token for token in re.split(r"\s+", raw) if any(ch.isalpha() for ch in token)]
    if not 1 <= len(tokens) <= 4:
        return False
    normalized = [re.sub(r"^\W+|\W+$", "", normalize_ascii(token)) for token in tokens]
    normalized = [token for token in normalized if token]
    if not normalized:
        return False
    reject_words = {
        "a",
        "an",
        "and",
        "aviation",
        "broke",
        "cemetery",
        "field",
        "first",
        "flight",
        "from",
        "hours",
        "logged",
        "mail",
        "men",
        "nearest",
        "over",
        "park",
        "record",
        "solo",
        "speed",
        "successful",
        "the",
        "to",
        "virginia",
        "who",
    }
    if any(token in reject_words for token in normalized):
        return False
    alpha = [ch for ch in raw if ch.isalpha()]
    if not alpha:
        return False
    # #2a (2026-06-27): non-cased script (Arapça/Farsça/Sorani Kürtçe vb.) — büyük-harf/baş-harf testi
    # ANLAMSIZ (o alfabelerde büyük-küçük yok). Yapısal filtreleri (1-4 token, rakam yok, ≤32, cümle-
    # noktalama yok, reject_words değil) zaten geçen satırı isim-benzeri say. Flag-gated DEFAULT OFF.
    # Latin/Türkçe filmlerde non-cased satır olmadığından bu dal HİÇ çalışmaz → o korpusta SIFIR değişim.
    if not any(ch.lower() != ch.upper() for ch in alpha):
        return _nonlatin_names_enabled()
    upper_ratio = sum(1 for ch in alpha if ch.isupper()) / max(1, len(alpha))
    initial_caps = 0
    for token in tokens:
        first_alpha = next((ch for ch in token if ch.isalpha()), "")
        if first_alpha and first_alpha.isupper():
            initial_caps += 1
    initial_ratio = initial_caps / max(1, len(tokens))
    if upper_ratio >= 0.65 or initial_ratio >= 0.75:
        return True
    # Fix B (2026-06-27): küçük-harf Latin yabancı kredi ismi (pierre lary, michèle moretti). Flag-gated
    # DEFAULT OFF → bu iki satır False döner = mevcut davranışla BİREBİR (sıfır regresyon). Flag ON iken:
    # yapısal filtreler geçmiş + fonksiyon-kelimesi yok (altyazı/düzyazı değil) → isim say.
    if _latin_lowercase_names_enabled() and not any(tok in _LATIN_LC_STOPWORDS for tok in normalized):
        return True
    return False


def has_two_column_layout(boxes: list[tuple[int, int, int, int]], width: int, height: int) -> bool:
    if len(boxes) < 6:
        return False
    centers = [((x1 + x2) / 2.0) / max(1, width) for x1, _y1, x2, _y2 in boxes]
    left = sum(1 for value in centers if value <= 0.43)
    right = sum(1 for value in centers if value >= 0.57)
    x_min = min(x1 for x1, _y1, _x2, _y2 in boxes) / max(1, width)
    x_max = max(x2 for _x1, _y1, x2, _y2 in boxes) / max(1, width)
    y_min = min(y1 for _x1, y1, _x2, _y2 in boxes) / max(1, height)
    y_max = max(y2 for _x1, _y1, _x2, y2 in boxes) / max(1, height)
    return left >= 3 and right >= 3 and (x_max - x_min) >= 0.62 and (y_max - y_min) >= 0.22


def semantic_text_features(
    texts: list[str],
    boxes: list[tuple[int, int, int, int]],
    width: int,
    height: int,
) -> dict:
    tokens = normalized_tokens(texts)
    joined = " ".join(tokens)
    credit_terms = {
        "actor",
        "actors",
        "actress",
        "adaptation",
        "assistant",
        "associate",
        "avec",
        "basrolde",
        "camera",
        "cast",
        "casting",
        "cinematographer",
        "cinematography",
        "costarring",
        "costume",
        "costumes",
        "crew",
        "dialogue",
        "directed",
        "director",
        "editor",
        "editing",
        "executive",
        "gaffer",
        "goruntu",
        "grip",
        "kurgu",
        "makeup",
        "music",
        "muzik",
        "oyuncu",
        "oyuncular",
        "photography",
        "producer",
        "produced",
        "production",
        "producers",
        "reji",
        "screenplay",
        "senaryo",
        "ses",
        "sound",
        "starring",
        "story",
        "unit",
        "visual",
        "written",
        "yapim",
        "yapimci",
        "yonetmen",
    }
    name_like_count = sum(1 for text in texts if is_name_like_line(text))
    two_column = has_two_column_layout(boxes, width, height)
    credit_keyword_count = sum(1 for token in tokens if token in credit_terms or "starring" in token)
    phrase_credit_hits = 0
    if any(phrase in joined for phrase in ("a film by", "film by", "film von", "film vom", "un film de")) and name_like_count >= 1:
        phrase_credit_hits += 1
    if any(phrase in joined for phrase in ("english version by", "version by", "version de", "version francaise")):
        phrase_credit_hits += 1
    if "author" in tokens and name_like_count >= 1:
        phrase_credit_hits += 1
    if "as" in tokens and name_like_count >= 2:
        phrase_credit_hits += 1
    credit_keyword_count += phrase_credit_hits
    # Çok-dilli (Arapça/Kiril) kredi-rol anahtarları — normalize_ascii bunları Latin'e çevirmez; HAM metinde
    # ara. Latin/Türkçe korpusta EŞLEŞMEZ → 0-regresyon (additive). OneOCR non-Latin'i okur, bu onu "kredi" sayar.
    if _ML_CREDIT_RE.search(" ".join(texts)):
        credit_keyword_count += 1
    plaque_terms = {
        "advanced",
        "aviation",
        "buried",
        "cemetery",
        "field",
        "flight",
        "flying",
        "hours",
        "logged",
        "mail",
        "men",
        "park",
        "record",
        "roosevelt",
        "solo",
        "speed",
        "successful",
        "virginia",
    }
    plaque_hits = sum(1 for token in tokens if token in plaque_terms)
    story_terms = {
        "arrested",
        "buried",
        "cemetery",
        "died",
        "execution",
        "executed",
        "grave",
        "killed",
        "released",
        "sentenced",
    }
    story_hits = sum(1 for token in tokens if token in story_terms)
    end_card = is_end_card_text(texts)
    plaque_like = bool(plaque_hits >= 2 and credit_keyword_count == 0 and not two_column)
    epilogue_like = bool(story_hits >= 1 and credit_keyword_count == 0 and not two_column)

    score = 0.0
    if credit_keyword_count:
        score += min(0.60, 0.28 + 0.10 * credit_keyword_count)
    if two_column and name_like_count >= 4:
        score += 0.52
    elif two_column:
        score += 0.28
    if name_like_count >= 6 and not plaque_like:
        score += 0.24
    elif name_like_count >= 3 and two_column and not plaque_like:
        score += 0.16
    if end_card or plaque_like or epilogue_like:
        score *= 0.25

    return {
        "semantic_score": max(0.0, min(1.0, score)),
        "credit_keyword_count": credit_keyword_count,
        "name_like_count": name_like_count,
        "two_column_layout": two_column,
        "end_card_like": end_card,
        "plaque_like": plaque_like,
        "epilogue_like": epilogue_like,
        "joined_tokens": joined,
    }


def is_prose_scene_text(texts: list[str]) -> bool:
    if not texts:
        return False
    joined = " ".join(texts)
    alpha = [ch for ch in joined if ch.isalpha()]
    if not alpha:
        return False
    lower_ratio = sum(1 for ch in alpha if ch.islower()) / max(1, len(alpha))
    original_tokens = [re.sub(r"^\W+|\W+$", "", text) for text in re.split(r"\s+", joined)]
    original_tokens = [token for token in original_tokens if any(ch.isalpha() for ch in token)]
    title_initials = 0
    for token in original_tokens:
        first_alpha = next((ch for ch in token if ch.isalpha()), "")
        if first_alpha and first_alpha.isupper():
            title_initials += 1
    title_initial_ratio = title_initials / max(1, len(original_tokens))
    punct = sum(1 for ch in joined if ch in ".,;:!?")
    long_lines = sum(1 for text in texts if len(text.strip()) >= 15)
    avg_len = sum(len(text.strip()) for text in texts) / max(1, len(texts))
    stopwords = {
        "a",
        "an",
        "and",
        "au",
        "aux",
        "bir",
        "by",
        "da",
        "de",
        "del",
        "der",
        "di",
        "du",
        "en",
        "est",
        "et",
        "il",
        "in",
        "je",
        "la",
        "le",
        "les",
        "ne",
        "nous",
        "of",
        "pas",
        "quelle",
        "si",
        "the",
        "to",
        "ve",
        "ya",
    }
    tokens = [re.sub(r"^\W+|\W+$", "", text.lower()) for text in re.split(r"\s+", joined)]
    tokens = [token for token in tokens if token]
    stop_ratio = sum(1 for token in tokens if token in stopwords) / max(1, len(tokens))
    dialogue_words = {
        "aslinda",
        "ben",
        "beni",
        "buradan",
        "cok",
        "degil",
        "guzel",
        "mi",
        "ne",
        "sen",
        "sersem",
    }
    dialogue_ratio = sum(1 for token in tokens if token in dialogue_words) / max(1, len(tokens))
    bio_words = {"arrested", "born", "died", "killed", "lived", "married", "released"}
    has_year = re.search(r"\b(?:18|19|20)\d{2}\b", joined) is not None
    short_bio_card = len(tokens) <= 10 and has_year and any(token in bio_words for token in tokens)
    sentence_case = title_initial_ratio <= 0.55
    sentence_case_block = len(tokens) >= 8 and sentence_case and lower_ratio >= 0.35
    quote_or_epilogue_block = len(tokens) >= 14 and stop_ratio >= 0.22 and punct >= 2
    many_prose_words = (
        (len(tokens) >= 12 and stop_ratio >= 0.18 and sentence_case)
        or (len(tokens) >= 4 and dialogue_ratio >= 0.25)
        or short_bio_card
        or sentence_case_block
        or quote_or_epilogue_block
    ) and lower_ratio >= 0.35
    if quote_or_epilogue_block and long_lines >= 2:
        many_prose_words = True
    long_sentence_lines = (
        (long_lines >= 2 or avg_len >= 13.0)
        and punct >= 1
        and lower_ratio >= 0.22
        and sentence_case
    )
    return many_prose_words or long_sentence_lines


def is_subtitle_scene_text(
    texts: list[str],
    *,
    y_min: float | None,
    y_max: float | None,
    box_count: int,
    line_count: int,
    dark_ratio: float,
    luma_mean: float,
) -> bool:
    if not texts or y_min is None or y_max is None:
        return False
    if box_count > 5 or line_count > 4:
        return False
    if y_min < 0.68 or y_max < 0.82:
        return False
    cleaned = [text.strip() for text in texts if text and text.strip()]
    if not cleaned:
        return False

    joined = " ".join(cleaned)
    starts_dialogue = any(text.lstrip().startswith(("-", "–", "—")) for text in cleaned)
    if starts_dialogue:
        return True

    alpha = [ch for ch in joined if ch.isalpha()]
    if not alpha:
        return False
    lower_ratio = sum(1 for ch in alpha if ch.islower()) / max(1, len(alpha))
    original_tokens = [re.sub(r"^\W+|\W+$", "", text) for text in re.split(r"\s+", joined)]
    original_tokens = [token for token in original_tokens if any(ch.isalpha() for ch in token)]
    title_initials = 0
    for token in original_tokens:
        first_alpha = next((ch for ch in token if ch.isalpha()), "")
        if first_alpha and first_alpha.isupper():
            title_initials += 1
    title_initial_ratio = title_initials / max(1, len(original_tokens))
    sentence_punct = any(ch in joined for ch in "?!")
    tokens = [re.sub(r"^\W+|\W+$", "", text.lower()) for text in re.split(r"\s+", joined)]
    tokens = [token for token in tokens if token]
    stopwords = {
        "a",
        "an",
        "ama",
        "and",
        "aslinda",
        "are",
        "be",
        "beni",
        "bir",
        "buradan",
        "bu",
        "bunu",
        "by",
        "cok",
        "da",
        "de",
        "degil",
        "dolayi",
        "for",
        "guzel",
        "have",
        "he",
        "her",
        "i",
        "icin",
        "ilk",
        "in",
        "is",
        "it",
        "mi",
        "ne",
        "of",
        "oldu",
        "on",
        "sen",
        "sersem",
        "the",
        "to",
        "ve",
        "was",
        "we",
        "you",
    }
    stop_ratio = sum(1 for token in tokens if token in stopwords) / max(1, len(tokens))
    longish = len(tokens) >= 5 or len(joined) >= 28
    sentence_case = longish and lower_ratio >= 0.32 and title_initial_ratio <= 0.42
    prose_sentence = longish and lower_ratio >= 0.35 and (stop_ratio >= 0.16 or sentence_punct or sentence_case)

    return prose_sentence


def is_scene_sign_text(
    texts: list[str],
    *,
    box_count: int,
    dark_ratio: float,
    luma_mean: float,
) -> bool:
    if not texts or box_count > 4:
        return False
    tokens = [re.sub(r"^\W+|\W+$", "", text.lower()) for text in re.split(r"\s+", " ".join(texts))]
    tokens = [token for token in tokens if token]
    sign_words = {
        "admission",
        "ambulance",
        "clinic",
        "coeur",
        "emergency",
        "hospital",
        "oumons",
        "permanence",
        "poumons",
        "transplant",
        "umons",
        "urgence",
    }
    has_sign_word = any(token in sign_words for token in tokens)
    bright_sign = dark_ratio <= 0.35 and luma_mean >= 50.0
    medical_poster = any(token in {"coeur", "oumons", "poumons", "umons"} for token in tokens)
    return has_sign_word and (bright_sign or medical_poster)


def is_ui_scene_text(texts: list[str]) -> bool:
    if len(texts) < 4:
        return False
    joined = " ".join(texts)
    chars = [ch for ch in joined if not ch.isspace()]
    if not chars:
        return False
    digit_ratio = sum(1 for ch in chars if ch.isdigit()) / max(1, len(chars))
    has_time = re.search(r"\d{1,2}\s*[:.]\s*\d{2}", joined) is not None
    has_phone_like = re.search(r"(\+?\d[\d\s()/-]{5,})", joined) is not None
    short_fragment_ratio = sum(1 for text in texts if len(text.strip()) <= 4) / max(1, len(texts))
    return (digit_ratio >= 0.28 and short_fragment_ratio >= 0.35) or has_time or has_phone_like


def extract_paddle_text_boxes(result: object) -> list[tuple[tuple[int, int, int, int], str, float]]:
    items: list[tuple[tuple[int, int, int, int], str, float]] = []
    if not result:
        return items
    pages = result if isinstance(result, list) else [result]
    for page in pages:
        if isinstance(page, dict):
            texts = list(page.get("rec_texts") or [])
            rec_scores = list(page.get("rec_scores") or [])
            raw_rec_boxes = page.get("rec_boxes")
            rec_boxes = [] if raw_rec_boxes is None else np.asarray(raw_rec_boxes).tolist()
            raw_rec_polys = page.get("rec_polys")
            rec_polys = [] if raw_rec_polys is None else list(raw_rec_polys)
            if texts and rec_boxes:
                for idx, b in enumerate(rec_boxes):
                    text = texts[idx] if idx < len(texts) else ""
                    rec_score = rec_scores[idx] if idx < len(rec_scores) else 1.0
                    if len(b) >= 4 and valid_ocr_text(text, rec_score):
                        x1, y1, x2, y2 = [int(round(float(v))) for v in b[:4]]
                        box = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                        items.append((box, str(text), float(rec_score)))
            elif texts and rec_polys:
                for idx, poly in enumerate(rec_polys):
                    text = texts[idx] if idx < len(texts) else ""
                    rec_score = rec_scores[idx] if idx < len(rec_scores) else 1.0
                    if not valid_ocr_text(text, rec_score):
                        continue
                    arr = np.asarray(poly).reshape(-1, 2)
                    if arr.size:
                        x1, y1 = arr.min(axis=0)
                        x2, y2 = arr.max(axis=0)
                        box = (int(x1), int(y1), int(x2), int(y2))
                        items.append((box, str(text), float(rec_score)))
        elif isinstance(page, list):
            for item in page:
                if not item:
                    continue
                text, rec_score = "", 1.0
                if isinstance(item, (list, tuple)) and len(item) > 1:
                    rec = item[1]
                    if isinstance(rec, (list, tuple)):
                        text = rec[0] if len(rec) > 0 else ""
                        rec_score = rec[1] if len(rec) > 1 else 1.0
                    else:
                        text = rec
                if not valid_ocr_text(text, rec_score):
                    continue
                poly = item[0] if isinstance(item, (list, tuple)) else item
                arr = np.asarray(poly).reshape(-1, 2)
                if arr.size:
                    x1, y1 = arr.min(axis=0)
                    x2, y2 = arr.max(axis=0)
                    box = (int(x1), int(y1), int(x2), int(y2))
                    items.append((box, str(text), float(rec_score)))
    # Deduplicate near-identical boxes.
    deduped: list[tuple[tuple[int, int, int, int], str, float]] = []
    for box, text, rec_score in items:
        if not any(box_iou(box, prev_box) > 0.82 for prev_box, _prev_text, _prev_score in deduped):
            deduped.append((box, text, rec_score))
    return deduped


def extract_paddle_boxes(result: object) -> list[tuple[int, int, int, int]]:
    return [box for box, _text, _score in extract_paddle_text_boxes(result)]


def box_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1, (bx2 - bx1) * (by2 - by1))
    return inter / float(area_a + area_b - inter)


def filter_ocr_boxes(boxes: list[tuple[int, int, int, int]], width: int, height: int) -> list[tuple[int, int, int, int]]:
    out: list[tuple[int, int, int, int]] = []
    for x1, y1, x2, y2 in boxes:
        bw, bh = max(0, x2 - x1), max(0, y2 - y1)
        if bw < max(4, width * 0.006) or bh < max(4, height * 0.010):
            continue
        if bw > width * 0.92 or bh > height * 0.30:
            continue
        if bw * bh > width * height * 0.08:
            continue
        out.append((x1, y1, x2, y2))
    return out


def apply_ocr_score(score: FrameScore, value: float, info: dict, cfg: DetectorConfig) -> None:
    score.text_score = round(float(value), 5)
    score.mask_density = round(float(info.get("mask_density", 0.0)), 6)
    score.component_count = int(info.get("component_count", 0))
    score.line_count = int(info.get("line_count", 0))
    score.vertical_coverage = round(float(info.get("vertical_coverage", 0.0)), 5)
    score.y_min = None if info.get("y_min") is None else round(float(info.get("y_min")), 5)
    score.y_max = None if info.get("y_max") is None else round(float(info.get("y_max")), 5)
    score.bottom_only = bool(info.get("bottom_only", False))
    score.dark_ratio = round(float(info.get("dark_ratio", score.dark_ratio)), 5)
    score.luma_mean = round(float(info.get("luma_mean", score.luma_mean)), 3)
    score.credit_like = bool(value >= cfg.text_threshold)
    score.ocr_text = str(info.get("ocr_text") or "")
    score.semantic_score = round(float(info.get("semantic_score", 0.0) or 0.0), 4)
    score.credit_keyword_count = int(info.get("credit_keyword_count", 0) or 0)
    score.name_like_count = int(info.get("name_like_count", 0) or 0)
    score.two_column_layout = bool(info.get("two_column_layout", False))
    score.end_card_like = bool(info.get("end_card_like", False))
    score.prose_like = bool(info.get("prose_like", False))
    score.scene_sign_like = bool(info.get("scene_sign_like", False))
    score.subtitle_like = bool(info.get("subtitle_like", False))
    score.ui_like = bool(info.get("ui_like", False))


def rolling_hits(scores: list[FrameScore], start: int, cfg: DetectorConfig) -> tuple[int, float, float]:
    window = scores[start : min(len(scores), start + cfg.lookahead)]
    if not window:
        return 0, 0.0, 0.0
    hits = sum(1 for s in window if s.text_score >= cfg.text_threshold)
    soft = [s.text_score for s in window if s.text_score >= cfg.soft_threshold]
    mean_soft = float(sum(soft) / len(soft)) if soft else 0.0
    max_score = max(s.text_score for s in window)
    return hits, mean_soft, max_score


def sustained_cluster(scores: list[FrameScore], start: int, cfg: DetectorConfig) -> bool:
    window = scores[start : min(len(scores), start + max(cfg.lookahead, cfg.sustain_window))]
    if not window:
        return False
    hard_positions = [s.pos for s in window if s.text_score >= cfg.text_threshold]
    hard_hits = len(hard_positions)
    if len(hard_positions) >= 2:
        max_hard_gap = max(b - a for a, b in zip(hard_positions, hard_positions[1:]))
        if max_hard_gap > max(4, cfg.ocr_stride + 2):
            return False
    if hard_hits >= cfg.sustain_hits:
        return True
    rich_hits = sum(
        1
        for s in window
        if s.text_score >= cfg.text_threshold and (s.component_count >= 4 or s.line_count >= 3)
    )
    hard_span = 0 if len(hard_positions) < 2 else hard_positions[-1] - hard_positions[0]
    return (
        hard_hits >= cfg.min_hits + 1
        and rich_hits >= max(2, cfg.min_hits - 1)
        and hard_span >= max(5, cfg.lookahead - 1)
    )


def weak_visual_credit_trace(score: FrameScore, cfg: DetectorConfig) -> bool:
    if score.text_score < max(0.16, cfg.soft_threshold * 0.68):
        return False
    if score.mask_density < 0.012:
        return False
    if score.component_count < 6 or score.component_count > 110:
        return False
    if score.line_count < 2:
        return False
    if score.bottom_only:
        return False
    if score.vertical_coverage <= 0.0 or score.vertical_coverage > 0.62:
        return False
    if score.y_min is not None and score.y_min > 0.72:
        return False
    return True


def full_frame_scroll_credit_trace(score: FrameScore, cfg: DetectorConfig) -> bool:
    return (
        (score.text_score >= max(0.09, cfg.soft_threshold * 0.38) or score.mask_density >= 0.045)
        and 18 <= score.component_count <= 64
        and score.line_count >= 3
        and 0.018 <= score.mask_density <= 0.095
        and score.vertical_coverage >= 0.58
        and score.y_min is not None
        and score.y_max is not None
        and score.y_min <= 0.10
        and score.y_max >= 0.80
        and not score.bottom_only
    )


def moving_background_credit_trace(score: FrameScore, cfg: DetectorConfig) -> bool:
    return (
        score.text_score >= max(0.14, cfg.soft_threshold * 0.60)
        and 0.020 <= score.mask_density <= 0.075
        and 40 <= score.component_count <= 260
        and 1 <= score.line_count <= 5
        and 0.28 <= score.vertical_coverage <= 0.58
        and score.y_min is not None
        and score.y_max is not None
        and score.y_min >= 0.20
        and score.y_max <= 0.97
        and not score.bottom_only
    )


def compact_credit_trace(score: FrameScore, cfg: DetectorConfig) -> bool:
    if score.component_count < 2 or score.line_count < 1:
        return False
    if score.component_count > 32:
        return False
    if score.mask_density < 0.004:
        return False
    if score.vertical_coverage <= 0.0 or score.vertical_coverage > 0.46:
        return False
    if score.text_score >= max(0.19, cfg.soft_threshold * 0.82):
        return True
    return (
        score.mask_density >= 0.018
        and score.line_count >= 2
        and score.text_score >= max(0.07, cfg.soft_threshold * 0.30)
    )


def dense_scroll_credit_trace(score: FrameScore, cfg: DetectorConfig) -> bool:
    if score.text_score < max(0.095, cfg.soft_threshold * 0.40):
        return False
    if score.mask_density < 0.085:
        return False
    if score.component_count < 24 or score.component_count > 190:
        return False
    if score.line_count < 1:
        return False
    if score.vertical_coverage < 0.52 or score.vertical_coverage > 0.88:
        return False
    if score.y_min is None or score.y_max is None:
        return False
    # Scene texture often touches the very top or bottom. Full-frame scroll credits
    # usually leave a small black margin even when they span most of the frame.
    if score.y_min < 0.045 or score.y_max > 0.955:
        return False
    return True


def local_visible_credit_trace(score: FrameScore, cfg: DetectorConfig) -> bool:
    return (
        compact_credit_trace(score, cfg)
        or dense_scroll_credit_trace(score, cfg)
        or weak_visual_credit_trace(score, cfg)
    )


def dark_static_card_visible(path: Path, cfg: DetectorConfig) -> bool:
    image = imread_unicode(path)
    if image is None:
        return False
    image = resize_for_scan(image, cfg.max_width)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    dark_ratio = float(np.count_nonzero(gray < 42) / max(1, gray.size))
    if dark_ratio < 0.94 or float(gray.mean()) > 15.0:
        return False
    threshold = max(14.0, float(gray.mean()) + 3.5 * float(gray.std()))
    mask = ((gray > threshold) & (gray > 18)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 2), np.uint8), iterations=1)
    active_pixels = int(np.count_nonzero(mask))
    if active_pixels < 60:
        return False
    count, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), 8)
    h, w = gray.shape[:2]
    y_values: list[int] = []
    components = 0
    for label in range(1, count):
        _x, y, cw, ch, area = stats[label]
        if area < 4:
            continue
        if cw < 2 or cw > w * 0.82:
            continue
        if ch < 2 or ch > h * 0.22:
            continue
        components += 1
        y_values.extend([int(y), int(y + ch)])
    if components < 1 or components > 45 or not y_values:
        return False
    vertical_coverage = (max(y_values) - min(y_values)) / max(1, h)
    return 0.025 <= vertical_coverage <= 0.68


def start_frame_has_visible_credit(score: FrameScore, cfg: DetectorConfig) -> bool:
    if compact_credit_trace(score, cfg) or dense_scroll_credit_trace(score, cfg):
        return True
    if score.y_min is None or score.y_max is None:
        return False
    touches_full_frame = score.y_min < 0.015 and score.y_max > 0.965
    if (
        not touches_full_frame
        and 2 <= score.component_count <= 36
        and score.line_count >= 1
        and score.mask_density >= 0.018
        and 0.0 < score.vertical_coverage <= 0.58
    ):
        return True
    # OCR can miss tiny faint bottom cards; keep this as a start-frame guard only,
    # not as a global onset trigger.
    return (
        not touches_full_frame
        and score.component_count >= 1
        and score.line_count >= 1
        and score.mask_density >= 0.008
        and score.vertical_coverage <= 0.18
    )


def starts_inside_credit(scores: list[FrameScore], cfg: DetectorConfig) -> bool:
    early = scores[: min(max(cfg.already_credit_frames + 4, 9), len(scores))]
    if not early:
        return False
    compact_hits = sum(1 for s in early if compact_credit_trace(s, cfg))
    dense_hits = sum(1 for s in early if dense_scroll_credit_trace(s, cfg))
    full_hits = sum(1 for s in early if full_frame_scroll_credit_trace(s, cfg))
    strong_hits = sum(1 for s in early if s.text_score >= cfg.text_threshold)
    first = early[0]
    if compact_credit_trace(first, cfg) and compact_hits >= max(3, min(5, len(early) // 2)):
        return True
    if dense_scroll_credit_trace(first, cfg) and dense_hits >= max(5, min(7, len(early) - 1)):
        return True
    if full_frame_scroll_credit_trace(first, cfg) and full_hits >= max(5, min(7, len(early) - 1)):
        return True
    valid, _reason = semantic_credit_cluster_valid(early, 0, cfg, local_only=True)
    if not valid:
        return False
    return strong_hits >= max(2, min(3, len(early))) and sum(s.text_score for s in early) / max(1, len(early)) >= cfg.soft_threshold


def semantically_invalid_frame(score: FrameScore) -> bool:
    if not score.ocr_text:
        return False
    if score.semantic_score >= 0.40:
        return False
    prose_like = score.prose_like or is_prose_scene_text(score.ocr_text.split(" | "))
    return bool(
        score.end_card_like
        or prose_like
        or score.scene_sign_like
        or score.subtitle_like
        or score.ui_like
    )


def semantically_credit_frame(score: FrameScore) -> bool:
    if score.semantic_score >= 0.45:
        return True
    return bool(score.two_column_layout and score.name_like_count >= 4 and not semantically_invalid_frame(score))


def semantic_credit_cluster_valid(
    scores: list[FrameScore],
    start: int,
    cfg: DetectorConfig,
    *,
    local_only: bool = False,
) -> tuple[bool, str]:
    window_len = len(scores) if local_only else max(cfg.lookahead, 12)
    cluster = scores[start : min(len(scores), start + window_len)]
    semantic_frames = [
        s
        for s in cluster
        if s.ocr_text and s.text_score >= max(0.04, cfg.soft_threshold * 0.25)
    ]
    if not semantic_frames:
        return True, "no semantic OCR available"

    credit_frames = [s for s in semantic_frames if semantically_credit_frame(s)]
    invalid_frames = [s for s in semantic_frames if semantically_invalid_frame(s)]
    if credit_frames and (len(credit_frames) >= 2 or max(s.semantic_score for s in credit_frames) >= 0.55):
        return True, "semantic credit evidence"

    hard_or_soft = [s for s in semantic_frames if s.text_score >= cfg.soft_threshold]
    if invalid_frames and len(invalid_frames) >= max(1, math.ceil(len(semantic_frames) * 0.45)):
        labels = []
        if any(s.end_card_like for s in invalid_frames):
            labels.append("end_card")
        if any(s.prose_like for s in invalid_frames):
            labels.append("prose_or_epilogue")
        if any(s.scene_sign_like for s in invalid_frames):
            labels.append("scene_sign_or_plaque")
        if any(s.subtitle_like for s in invalid_frames):
            labels.append("subtitle")
        if any(s.ui_like for s in invalid_frames):
            labels.append("ui")
        return False, "semantic reject: " + ",".join(labels or ["non_credit_text"])

    if hard_or_soft and all(s.end_card_like for s in hard_or_soft) and not credit_frames:
        return False, "semantic reject: end_card_only"

    return True, "visual cluster accepted"


def guarded_start_pos(scores: list[FrameScore], first_text_pos: int, cfg: DetectorConfig, paths: list[Path] | None = None) -> int:
    pos = max(0, first_text_pos - cfg.preroll_frames)
    extra = 0
    max_extra = 4
    while pos > 0 and extra < max_extra and (
        start_frame_has_visible_credit(scores[pos], cfg)
        or (paths is not None and pos < len(paths) and dark_static_card_visible(paths[pos], cfg))
    ):
        pos -= 1
        extra += 1
    return pos


def advance_to_visible_text(scores: list[FrameScore], first_text_pos: int, cfg: DetectorConfig, paths: list[Path] | None = None) -> int:
    def visible(pos: int) -> bool:
        if pos < 0 or pos >= len(scores):
            return False
        if local_visible_credit_trace(scores[pos], cfg) or start_frame_has_visible_credit(scores[pos], cfg):
            return True
        return bool(paths is not None and pos < len(paths) and dark_static_card_visible(paths[pos], cfg))

    if visible(first_text_pos):
        return first_text_pos
    for pos in range(first_text_pos + 1, min(len(scores), first_text_pos + max(8, cfg.ocr_stride + 4))):
        if visible(pos):
            return pos
    return first_text_pos


def refine_local_visible_onset(scores: list[FrameScore], first_text_pos: int, cfg: DetectorConfig, paths: list[Path] | None = None) -> int:
    dark_card_cluster = False
    for pos in range(max(0, first_text_pos - 3), min(len(scores), first_text_pos + 2)):
        score = scores[pos]
        if (
            score.dark_ratio >= 0.94
            and score.luma_mean <= 15.0
            and (score.mask_density >= 0.020 or score.text_score >= 0.08 or score.line_count >= 1)
        ):
            dark_card_cluster = True
            break
    if paths is not None:
        for pos in range(max(0, first_text_pos - 3), min(len(scores), first_text_pos + 2)):
            if pos < len(paths) and dark_static_card_visible(paths[pos], cfg):
                dark_card_cluster = True
                break
    max_back = 32 if dark_card_cluster else max(6, cfg.preroll_frames + 6)
    limit = max(0, first_text_pos - max_back)
    best = first_text_pos
    gap_budget = 1
    gap_run = 0
    seen_trace = False
    pos = first_text_pos - 1
    while pos >= limit:
        trace = local_visible_credit_trace(scores[pos], cfg)
        if not trace and dark_card_cluster and paths is not None and pos < len(paths):
            trace = dark_static_card_visible(paths[pos], cfg)
        if trace:
            best = pos
            seen_trace = True
            gap_run = 0
            pos -= 1
            continue
        if seen_trace and gap_run < gap_budget:
            gap_run += 1
            pos -= 1
            continue
        break
    return best


def backtrack_visual_onset(scores: list[FrameScore], first_text_pos: int, cfg: DetectorConfig) -> int:
    min_back = 2
    max_back = max(6, cfg.ocr_stride + cfg.preroll_frames + 2)
    limit = max(0, first_text_pos - max_back)
    j = first_text_pos
    while j > limit and weak_visual_credit_trace(scores[j - 1], cfg):
        j -= 1
    if first_text_pos - j < min_back:
        return first_text_pos
    return j


def find_onset(paths: list[Path], scores: list[FrameScore], cfg: DetectorConfig, frame_dir: Path) -> DetectionResult:
    if not scores:
        return DetectionResult(str(frame_dir), 0, "no_frames", None, None, None, None, None, None, 0.0, "none", "No readable frames", asdict(cfg))

    early = scores[: min(cfg.already_credit_frames, len(scores))]
    first_text_pos: int | None = None
    reason = ""

    if starts_inside_credit(scores, cfg):
        first_text_pos = 0
        start_pos = 0
        status = "already_in_credit"
        reason = f"First {len(early)} frames already contain persistent credit-like text"
    else:
        onset = None
        rejected_clusters: list[str] = []
        for i, score in enumerate(scores):
            hits, mean_soft, max_score = rolling_hits(scores, i, cfg)
            if score.text_score >= cfg.soft_threshold and hits >= cfg.min_hits and max_score >= cfg.text_threshold:
                onset = i
                # Walk back into fade-in / first weak text trace, but not through a large gap.
                j = i
                while j > 0 and scores[j - 1].text_score >= cfg.soft_threshold * 0.70:
                    j -= 1
                if sustained_cluster(scores, j, cfg):
                    valid_cluster, reject_reason = semantic_credit_cluster_valid(scores, j, cfg)
                    if not valid_cluster:
                        if len(rejected_clusters) < 4:
                            rejected_clusters.append(f"pos={j} {reject_reason}")
                        onset = None
                        continue
                    first_text_pos = j
                    break
                onset = None
            if hits >= cfg.min_hits + 1 and mean_soft >= cfg.text_threshold:
                first_hit = next(
                    (j for j in range(i, min(len(scores), i + cfg.lookahead)) if scores[j].text_score >= cfg.soft_threshold),
                    None,
                )
                if first_hit is not None and sustained_cluster(scores, first_hit, cfg):
                    valid_cluster, reject_reason = semantic_credit_cluster_valid(scores, first_hit, cfg)
                    if not valid_cluster:
                        if len(rejected_clusters) < 4:
                            rejected_clusters.append(f"pos={first_hit} {reject_reason}")
                        onset = None
                        continue
                    onset = first_hit
                    first_text_pos = first_hit
                    break
        if onset is None or first_text_pos is None:
            return DetectionResult(
                str(frame_dir),
                len(scores),
                "not_found",
                None,
                None,
                None,
                None,
                None,
                None,
                0.0,
                "none",
                "No persistent credit text cluster found",
                asdict(cfg),
            )
        hard_first_text_pos = first_text_pos
        first_text_pos = backtrack_visual_onset(scores, first_text_pos, cfg)
        first_text_pos = refine_local_visible_onset(scores, first_text_pos, cfg, paths)
        start_pos = guarded_start_pos(scores, first_text_pos, cfg, paths)
        status = "found"
        if start_pos == 0 and first_text_pos <= cfg.preroll_frames:
            status = "found_clamped_to_first_frame"
        reason = f"Persistent text cluster begins at pos={hard_first_text_pos}; visual_onset={first_text_pos}; preroll={cfg.preroll_frames}"
        if rejected_clusters:
            reason += "; skipped " + "; ".join(rejected_clusters)

    cluster = scores[first_text_pos : min(len(scores), (first_text_pos or 0) + max(cfg.lookahead, 12))] if first_text_pos is not None else []
    confidence = confidence_from_cluster(cluster, cfg)
    credit_type = classify_credit_type(cluster)

    start_score = scores[start_pos]
    text_score = scores[first_text_pos] if first_text_pos is not None else None
    return DetectionResult(
        frame_dir=str(frame_dir),
        total_frames=len(scores),
        status=status,
        start_pos=start_pos,
        start_frame_no=start_score.frame_no,
        start_file=start_score.file,
        first_text_pos=first_text_pos,
        first_text_frame_no=None if text_score is None else text_score.frame_no,
        first_text_file=None if text_score is None else text_score.file,
        confidence=round(float(confidence), 4),
        credit_type=credit_type,
        reason=reason,
        config=asdict(cfg),
    )


def confidence_from_cluster(cluster: list[FrameScore], cfg: DetectorConfig) -> float:
    if not cluster:
        return 0.0
    hits = sum(1 for s in cluster if s.text_score >= cfg.text_threshold)
    hit_ratio = hits / max(1, len(cluster))
    mean_score = sum(s.text_score for s in cluster) / max(1, len(cluster))
    line_med = median([s.line_count for s in cluster]) if cluster else 0
    return min(1.0, 0.50 * hit_ratio + 0.35 * min(1.0, mean_score / 0.70) + 0.15 * min(1.0, line_med / 4.0))


def classify_credit_type(cluster: list[FrameScore]) -> str:
    if not cluster:
        return "none"
    dys = [s.text_dy for s in cluster if abs(s.text_dy) > 0.15 and s.phase_response > 0.03]
    if len(dys) >= 3:
        signs = [1 if d > 0 else -1 for d in dys]
        consistency = max(signs.count(1), signs.count(-1)) / len(signs)
        med_abs = median(abs(d) for d in dys)
        if consistency >= 0.70 and med_abs >= 0.65:
            return "scroll_credit"
    changes = [s.frame_change for s in cluster]
    if changes and median(changes) >= 0.045:
        return "mixed_or_moving_background_credit"
    return "static_credit"


def ocr_digit_ratio(text: str) -> float:
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return 0.0
    return sum(1 for ch in chars if ch.isdigit()) / max(1, len(chars))


def credit_anchor_frame(score: FrameScore, cfg: DetectorConfig) -> bool:
    if semantically_invalid_frame(score):
        return False
    if score.ocr_text and is_prose_scene_text(score.ocr_text.split(" | ")):
        return False
    if score.semantic_score >= 0.55:
        return True
    if score.two_column_layout and score.name_like_count >= 4:
        return True
    if score.credit_keyword_count >= 1 and score.text_score >= cfg.soft_threshold:
        return True
    if score.credit_keyword_count >= 1 and score.component_count >= 2 and score.line_count >= 1:
        return True
    return False


def confirmed_credit_anchor(scores: list[FrameScore], pos: int, cfg: DetectorConfig) -> bool:
    if pos < 0 or pos >= len(scores) or not credit_anchor_frame(scores[pos], cfg):
        return False
    window = scores[pos : min(len(scores), pos + max(cfg.lookahead, 12))]
    strong = sum(1 for s in window if credit_anchor_frame(s, cfg))
    hard = sum(1 for s in window if s.text_score >= cfg.text_threshold)
    return strong >= 2 or (strong >= 1 and hard >= 3)


def find_confirmed_credit_anchor(
    scores: list[FrameScore],
    start: int,
    cfg: DetectorConfig,
    *,
    stop: int | None = None,
) -> int | None:
    end = len(scores) if stop is None else min(len(scores), max(start, stop))
    for pos in range(max(0, start), end):
        if confirmed_credit_anchor(scores, pos, cfg):
            return pos
    return None


def cluster_has_credit_evidence(cluster: list[FrameScore], cfg: DetectorConfig) -> bool:
    return any(credit_anchor_frame(score, cfg) for score in cluster)


def scene_text_candidate_cluster(cluster: list[FrameScore], cfg: DetectorConfig) -> bool:
    visible = [s for s in cluster if s.text_score >= max(0.04, cfg.soft_threshold * 0.25) or s.ocr_text]
    if not visible:
        return True
    if cluster_has_credit_evidence(visible, cfg):
        return False
    if any(semantically_invalid_frame(s) for s in visible):
        return True
    max_components = max((s.component_count for s in visible), default=0)
    max_lines = max((s.line_count for s in visible), default=0)
    max_names = max((s.name_like_count for s in visible), default=0)
    max_density = max((s.mask_density for s in visible), default=0.0)
    max_semantic = max((s.semantic_score for s in visible), default=0.0)
    joined = " ".join(s.ocr_text for s in visible if s.ocr_text)
    numeric_or_garble = bool(ocr_digit_ratio(joined) >= 0.22 and max_names <= 2)
    small_scene_text = (
        max_semantic < 0.40
        and max_components <= 8
        and max_lines <= 2
        and max_names <= 7
        and max_density <= 0.14
    )
    return numeric_or_garble or small_scene_text


def blank_or_weak_boundary(score: FrameScore) -> bool:
    if score.line_count == 0 and score.component_count == 0:
        return True
    return bool(score.text_score < 0.06 and score.mask_density < 0.006 and score.component_count <= 4)


def dark_small_text_lead(score: FrameScore) -> bool:
    return (
        score.dark_ratio >= 0.96
        and score.luma_mean <= 10.0
        and score.mask_density >= 0.010
        and 2 <= score.component_count <= 24
        and score.line_count >= 1
        and 0.04 <= score.vertical_coverage <= 0.28
    )


def name_rich_visual_lead(score: FrameScore) -> bool:
    return (
        score.mask_density >= 0.040
        and score.component_count >= 18
        and score.line_count >= 3
        and score.vertical_coverage >= 0.38
        and not score.bottom_only
        and score.dark_ratio <= 0.92
    )


def performer_card_lead(score: FrameScore, cfg: DetectorConfig) -> bool:
    """Cast/guest performer cards can be the first end-credit card.

    These often read as "with NAME" or "starring NAME" before crew-role
    keywords appear.  Accept them only as a lead-in signal, not as a standalone
    found condition, so ordinary dialogue/subtitles do not become credits.
    """
    if not score.ocr_text:
        return False
    if semantically_invalid_frame(score) or score.prose_like or score.subtitle_like or score.scene_sign_like:
        return False
    tokens = normalized_tokens(score.ocr_text.split(" | "))
    if not ({"with", "starring", "featuring"} & set(tokens)):
        return False
    if score.name_like_count < 1:
        return False
    if score.bottom_only:
        return False
    if score.vertical_coverage <= 0.0 or score.vertical_coverage > 0.44:
        return False
    return (
        score.text_score >= max(cfg.soft_threshold, 0.18)
        or (score.mask_density >= 0.025 and score.line_count >= 1 and score.component_count <= 18)
    )


def find_performer_card_lead(scores: list[FrameScore], first: int, anchor: int, cfg: DetectorConfig) -> int | None:
    """Return earliest sustained performer card before a confirmed crew anchor."""
    start = max(0, first - 6)
    end = min(len(scores), anchor)
    candidates = [pos for pos in range(start, end) if performer_card_lead(scores[pos], cfg)]
    if not candidates:
        return None
    # Require either repetition of the performer card or a very close confirmed
    # credit anchor; this keeps single subtitle/dialogue "with ..." lines out.
    for pos in candidates:
        near = scores[pos : min(len(scores), pos + 12)]
        repeats = sum(1 for s in near if performer_card_lead(s, cfg))
        hard_visual = sum(1 for s in near if s.text_score >= cfg.text_threshold)
        if repeats >= 2 or hard_visual >= 2 or anchor - pos <= max(10, cfg.lookahead + 2):
            return pos
    return None


def short_visual_lead_onset(scores: list[FrameScore], anchor: int, cfg: DetectorConfig) -> int:
    limit = max(0, anchor - 8)
    best = anchor
    for pos in range(anchor - 1, limit - 1, -1):
        score = scores[pos]
        if dark_small_text_lead(score):
            best = pos
            continue
        if scores[anchor].name_like_count >= 8 and name_rich_visual_lead(score):
            best = pos
            continue
        if blank_or_weak_boundary(score):
            continue
        break
    return best


def dense_dark_scroll_trace(score: FrameScore) -> bool:
    if score.dark_ratio < 0.92 or score.luma_mean > 12.0:
        return False
    if not (0.035 <= score.mask_density <= 0.180):
        return False
    if not (5 <= score.component_count <= 150):
        return False
    if score.line_count < 2:
        return False
    if score.vertical_coverage < 0.45 or score.vertical_coverage > 0.92:
        return False
    if score.y_min is None or score.y_max is None:
        return False
    if score.y_min < 0.03 or score.y_max > 0.985:
        return False
    moving = abs(score.text_dy) >= 1.5 and score.phase_response >= 0.10
    dense = score.component_count >= 12 and score.vertical_coverage >= 0.58
    return moving or dense


def dense_dark_scroll_onset(scores: list[FrameScore], anchor: int, cfg: DetectorConfig) -> int | None:
    limit = max(0, anchor - 180)
    best_run: tuple[int, int, int] | None = None
    run_start: int | None = None
    run_last: int | None = None
    run_hits = 0
    gap = 0

    for pos in range(limit, anchor + 1):
        if dense_dark_scroll_trace(scores[pos]):
            if run_start is None:
                run_start = pos
                run_hits = 0
            run_last = pos
            run_hits += 1
            gap = 0
        elif run_start is not None and gap < 3:
            gap += 1
        else:
            if run_start is not None and run_last is not None and run_hits >= 5 and run_last - run_start >= 10:
                if best_run is None:
                    best_run = (run_start, run_last, run_hits)
            run_start = None
            run_last = None
            run_hits = 0
            gap = 0

    if run_start is not None and run_last is not None and run_hits >= 5 and run_last - run_start >= 10:
        if best_run is None:
            best_run = (run_start, run_last, run_hits)
    if best_run is None:
        return None
    return best_run[0]


def promote_result_to_anchor(
    result: DetectionResult,
    scores: list[FrameScore],
    anchor: int,
    cfg: DetectorConfig,
    *,
    reason_prefix: str,
    first_override: int | None = None,
    status: str = "found",
) -> DetectionResult:
    first = anchor if first_override is None else max(0, min(first_override, anchor))
    start = max(0, first - cfg.preroll_frames)
    cluster = scores[anchor : min(len(scores), anchor + max(cfg.lookahead, 12))]
    start_score = scores[start]
    first_score = scores[first]
    confidence = float(confidence_from_cluster(cluster, cfg))
    anchor_score = scores[anchor]
    if credit_anchor_frame(anchor_score, cfg):
        if anchor_score.semantic_score >= 0.55 or anchor_score.two_column_layout:
            confidence = max(confidence, 0.72)
        elif anchor_score.credit_keyword_count >= 1:
            confidence = max(confidence, 0.62)
    result.status = status
    result.start_pos = start
    result.start_frame_no = start_score.frame_no
    result.start_file = start_score.file
    result.first_text_pos = first
    result.first_text_frame_no = first_score.frame_no
    result.first_text_file = first_score.file
    result.confidence = round(float(confidence), 4)
    result.credit_type = classify_credit_type(cluster)
    result.reason = f"{reason_prefix}; anchor_pos={anchor}; first_visible={first}; preroll={cfg.preroll_frames}; previous=({result.reason})"
    return result


def mark_review(result: DetectionResult, status: str, reason_prefix: str) -> DetectionResult:
    result.status = status
    result.reason = f"{reason_prefix}; not promoted to found; previous=({result.reason})"
    return result


def postprocess_detection_result(paths: list[Path], scores: list[FrameScore], result: DetectionResult, cfg: DetectorConfig) -> DetectionResult:
    del paths
    if result.status in {"not_found", "no_frames"} or result.first_text_pos is None:
        return result

    first = int(result.first_text_pos)
    start = int(result.start_pos if result.start_pos is not None else first)
    cluster = scores[first : min(len(scores), first + max(cfg.lookahead, 12))]

    if scene_text_candidate_cluster(cluster, cfg):
        later_anchor = find_confirmed_credit_anchor(scores, first + max(cfg.lookahead, 12), cfg)
        if later_anchor is not None:
            performer_first = find_performer_card_lead(scores, first, later_anchor, cfg)
            if performer_first is not None:
                return promote_result_to_anchor(
                    result,
                    scores,
                    later_anchor,
                    cfg,
                    reason_prefix="accepted performer/with cast card before confirmed crew credit cluster",
                    first_override=performer_first,
                    status="found",
                )
            visual_first = short_visual_lead_onset(scores, later_anchor, cfg)
            dense_first = dense_dark_scroll_onset(scores, later_anchor, cfg)
            if dense_first is not None and later_anchor - dense_first >= 12:
                visual_first = dense_first
            status = "found"
            reason_prefix = "skipped early scene/table text and selected later confirmed credit cluster"
            if later_anchor - first > 8:
                status = "review_boundary_ambiguous"
                reason_prefix = "early scene/table text skipped but later credit cluster is too far for automatic found"
            return promote_result_to_anchor(
                result,
                scores,
                later_anchor,
                cfg,
                reason_prefix=reason_prefix,
                first_override=visual_first,
                status=status,
            )
        return mark_review(result, "review_scene_text", "scene/table/prose-like text without confirmed credit evidence")

    anchor = find_confirmed_credit_anchor(scores, max(0, min(start, first)), cfg, stop=min(len(scores), first + 32))
    if anchor is None:
        if float(result.confidence or 0.0) < 0.55 and not cluster_has_credit_evidence(cluster, cfg):
            return mark_review(result, "review_low_confidence", "low-confidence visual text without semantic credit evidence")
        return result

    performer_first = find_performer_card_lead(scores, first, anchor, cfg)
    if performer_first is not None:
        return promote_result_to_anchor(
            result,
            scores,
            anchor,
            cfg,
            reason_prefix="accepted performer/with cast card before confirmed crew credit cluster",
            first_override=performer_first,
            status="found",
        )

    dense_first = dense_dark_scroll_onset(scores, anchor, cfg)
    if dense_first is not None and anchor - dense_first >= 12:
        return promote_result_to_anchor(
            result,
            scores,
            anchor,
            cfg,
            reason_prefix="confirmed non-Latin/dense dark scroll before OCR-readable credit cluster",
            first_override=dense_first,
        )

    visual_first = short_visual_lead_onset(scores, anchor, cfg)
    if visual_first < first:
        return promote_result_to_anchor(
            result,
            scores,
            anchor,
            cfg,
            reason_prefix="tightened start to verified visual lead before confirmed credit cluster",
            first_override=visual_first,
        )

    if start < anchor and any(blank_or_weak_boundary(scores[pos]) for pos in range(start, min(anchor, start + 10))):
        status = "found"
        reason_prefix = "discarded blank/weak dark preroll before confirmed credit text"
        if anchor - start > 8:
            status = "review_boundary_ambiguous"
            reason_prefix = "blank/weak preroll was long; candidate credit boundary kept for review"
        return promote_result_to_anchor(
            result,
            scores,
            anchor,
            cfg,
            reason_prefix=reason_prefix,
            status=status,
        )

    if float(result.confidence or 0.0) < 0.55 and not cluster_has_credit_evidence(cluster, cfg):
        return mark_review(result, "review_low_confidence", "low-confidence visual text without semantic credit evidence")

    return result


def write_scores_csv(path: Path, scores: list[FrameScore]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not scores:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(scores[0]).keys()))
        writer.writeheader()
        for score in scores:
            writer.writerow(asdict(score))


def encode_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", image)
    if ok:
        buf.tofile(str(path))


def make_debug_sheet(frame_paths: list[Path], scores: list[FrameScore], result: DetectionResult, out_path: Path, cfg: DetectorConfig) -> None:
    if not scores:
        return
    positions: list[int] = []
    for p in [0, 1, 2, result.start_pos, result.first_text_pos]:
        if p is not None and 0 <= p < len(scores):
            positions.append(int(p))
    if result.first_text_pos is not None:
        for d in range(-4, 9):
            p = result.first_text_pos + d
            if 0 <= p < len(scores):
                positions.append(p)
    # Add strongest frames for sanity.
    for s in sorted(scores, key=lambda x: x.text_score, reverse=True)[:4]:
        positions.append(s.pos)
    positions = sorted(dict.fromkeys(positions))

    tiles = []
    for pos in positions:
        image = imread_unicode(frame_paths[pos])
        if image is None:
            continue
        image = resize_for_scan(image, cfg.max_width)
        h, w = image.shape[:2]
        scale = 260 / max(1, w)
        tile = cv2.resize(image, (260, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
        label = f"{pos} {scores[pos].file} score={scores[pos].text_score:.2f}"
        if result.start_pos == pos:
            label = "START " + label
        if result.first_text_pos == pos:
            label = "TEXT " + label
        cv2.rectangle(tile, (0, 0), (tile.shape[1], 24), (0, 0, 0), -1)
        cv2.putText(tile, label[:42], (5, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(tile)
    if not tiles:
        return
    cols = 4
    tw = 260
    th = max(t.shape[0] for t in tiles)
    rows = int(math.ceil(len(tiles) / cols))
    sheet = np.zeros((rows * th, cols * tw, 3), dtype=np.uint8)
    for idx, tile in enumerate(tiles):
        r, c = divmod(idx, cols)
        sheet[r * th : r * th + tile.shape[0], c * tw : c * tw + tile.shape[1]] = tile
    encode_png(out_path, sheet)


def detect_frame_dir(frame_dir: Path, out_dir: Path | None, cfg: DetectorConfig, debug: bool) -> DetectionResult:
    paths, scores, _masks = score_frames(frame_dir, cfg)
    result = find_onset(paths, scores, cfg, frame_dir)
    result = postprocess_detection_result(paths, scores, result, cfg)
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "result.json").write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
        write_scores_csv(out_dir / "scores.csv", scores)
        if debug:
            make_debug_sheet(paths, scores, result, out_dir / "debug_sheet.png", cfg)
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Frame-folder based film credit start detector")
    parser.add_argument("frames", help="Frame directory containing PNG/JPG images")
    parser.add_argument("--out", help="Output directory for result.json, scores.csv and debug_sheet.png")
    parser.add_argument("--debug", action="store_true", help="Write a compact visual debug sheet")
    parser.add_argument("--max-width", type=int, default=DetectorConfig.max_width)
    parser.add_argument("--text-threshold", type=float, default=DetectorConfig.text_threshold)
    parser.add_argument("--soft-threshold", type=float, default=DetectorConfig.soft_threshold)
    parser.add_argument("--lookahead", type=int, default=DetectorConfig.lookahead)
    parser.add_argument("--min-hits", type=int, default=DetectorConfig.min_hits)
    parser.add_argument("--preroll-frames", type=int, default=DetectorConfig.preroll_frames)
    parser.add_argument("--ocr-mode", choices=["none", "paddle"], default=DetectorConfig.ocr_mode)
    parser.add_argument("--ocr-stride", type=int, default=DetectorConfig.ocr_stride)
    parser.add_argument("--ocr-lang", default=DetectorConfig.ocr_lang)
    parser.add_argument("--sustain-window", type=int, default=DetectorConfig.sustain_window)
    parser.add_argument("--sustain-hits", type=int, default=DetectorConfig.sustain_hits)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    cfg = DetectorConfig(
        max_width=args.max_width,
        text_threshold=args.text_threshold,
        soft_threshold=args.soft_threshold,
        lookahead=args.lookahead,
        min_hits=args.min_hits,
        preroll_frames=args.preroll_frames,
        ocr_mode=args.ocr_mode,
        ocr_stride=args.ocr_stride,
        ocr_lang=args.ocr_lang,
        sustain_window=args.sustain_window,
        sustain_hits=args.sustain_hits,
    )
    result = detect_frame_dir(Path(args.frames), Path(args.out) if args.out else None, cfg, args.debug)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0 if result.status not in {"no_frames"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
