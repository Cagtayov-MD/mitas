"""Credit start/scroll detector for OCR routing.

This module is intentionally heuristic and explainable. It scans video windows,
computes text-density and motion-consistency signals, and groups likely credit
windows into candidate segments.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from statistics import median
from typing import Any, Iterable


@dataclass(frozen=True)
class CreditWindowScore:
    index: int
    start_seconds: float
    end_seconds: float
    credit_score: float
    text_density: float
    row_structure: float
    dark_ratio: float
    median_dx_per_frame: float
    median_dy_per_frame: float
    motion_consistency: float
    phase_response: float
    label: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CreditSegment:
    start_seconds: float
    end_seconds: float
    label: str
    confidence: float
    window_indices: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["window_indices"] = list(self.window_indices)
        return payload


@dataclass(frozen=True)
class CreditDetectionResult:
    video_path: str | None
    windows: tuple[CreditWindowScore, ...]
    segments: tuple[CreditSegment, ...]
    output_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_path": self.video_path,
            "windows": [window.to_dict() for window in self.windows],
            "segments": [segment.to_dict() for segment in self.segments],
            "first_credit_start_seconds": self.segments[0].start_seconds if self.segments else None,
        }


def detect_credit_segments(
    video_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
    window_seconds: float = 10.0,
    stride_seconds: float | None = None,
    sample_fps: float = 2.0,
    score_threshold: float = 0.42,
) -> CreditDetectionResult:
    """Scan a video and write candidate credit segments."""
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(f"OpenCV unavailable: {exc}") from exc

    path = Path(video_path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Video could not be opened: {path}")
    native_fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / native_fps if frame_count > 0 else None
    if end_seconds is None:
        end_seconds = duration if duration is not None else start_seconds + window_seconds
    stride = float(stride_seconds) if stride_seconds is not None else float(window_seconds)
    stride = max(0.5, stride)
    windows = []
    window_start = float(start_seconds)
    index = 0
    while window_start < float(end_seconds):
        window_end = min(float(end_seconds), window_start + window_seconds)
        frames = _read_video_window(cap, cv2, native_fps, window_start, window_end, sample_fps)
        windows.append(_score_window(frames, index=index, start_seconds=window_start, end_seconds=window_end, threshold=score_threshold))
        index += 1
        window_start += stride
    cap.release()

    result = CreditDetectionResult(str(path), tuple(windows), tuple(_group_segments(windows, threshold=score_threshold)))
    if output_dir is not None:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        output_path = output / "credit_detector.json"
        output_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        report_path = output / "credit_detector_report.md"
        report_path.write_text(_build_report(result), encoding="utf-8")
        result = CreditDetectionResult(result.video_path, result.windows, result.segments, output_path)
    return result


def detect_credit_segments_from_frames(
    frames: Iterable[str | Path],
    *,
    timestamps: Iterable[float] | None = None,
    video_path: str | None = None,
    window_seconds: float = 10.0,
    stride_seconds: float | None = None,
    score_threshold: float = 0.42,
) -> CreditDetectionResult:
    """Detect credit windows from already sampled frame paths."""
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(f"OpenCV unavailable: {exc}") from exc

    paths = [Path(path) for path in frames if Path(path).exists()]
    if timestamps is None:
        times = [float(index) for index, _path in enumerate(paths)]
    else:
        times = [float(value) for value in timestamps]
    images = []
    image_times = []
    for path, timestamp in zip(paths, times):
        image = _cv2_imread(path, cv2)
        if image is None:
            continue
        images.append(image)
        image_times.append(timestamp)
    windows: list[CreditWindowScore] = []
    if not images:
        return CreditDetectionResult(video_path, tuple(), tuple())
    start = min(image_times)
    end = max(image_times) + 1e-6
    window_start = start
    stride = float(stride_seconds) if stride_seconds is not None else float(window_seconds)
    stride = max(0.5, stride)
    index = 0
    while window_start <= end:
        window_end = window_start + window_seconds
        window_frames = [image for image, timestamp in zip(images, image_times) if window_start <= timestamp < window_end]
        if window_frames:
            windows.append(_score_window(window_frames, index=index, start_seconds=window_start, end_seconds=window_end, threshold=score_threshold))
            index += 1
        window_start += stride
    return CreditDetectionResult(video_path, tuple(windows), tuple(_group_segments(windows, threshold=score_threshold)))


def _read_video_window(cap: Any, cv2: Any, native_fps: float, start: float, end: float, sample_fps: float) -> list[Any]:
    frames = []
    step = 1.0 / max(sample_fps, 0.1)
    timestamp = start
    while timestamp < end:
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
        ok, frame = cap.read()
        if ok and frame is not None:
            frames.append(frame)
        timestamp += step
    return frames


def _cv2_imread(path: Path, cv2: Any) -> Any:
    import numpy as np

    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size > 0:
            image = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if image is not None:
                return image
    except Exception:
        pass
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


def _score_window(frames: list[Any], *, index: int, start_seconds: float, end_seconds: float, threshold: float) -> CreditWindowScore:
    if not frames:
        return CreditWindowScore(index, start_seconds, end_seconds, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "non_credit")
    import cv2
    import numpy as np

    resized = _resize_to_first(frames, cv2)
    grays = [cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame in resized]
    masks = [_text_like_mask(frame, cv2, np) for frame in resized]
    text_density = float(median([(mask > 0).sum() / mask.size for mask in masks]))
    row_structure = float(median([_row_structure_score(mask, np) for mask in masks]))
    dark_ratio = float(median([(gray < 34).sum() / gray.size for gray in grays]))
    motion = _text_motion(masks, cv2, np)

    density_score = min(1.0, text_density / 0.020)
    structured_density = density_score * row_structure
    dark_score = min(1.0, dark_ratio / 0.55)
    vertical_speed = abs(float(motion["median_dy_per_frame"]))
    horizontal_speed = abs(float(motion["median_dx_per_frame"]))
    scroll_score = min(1.0, vertical_speed / 1.2) * float(motion["motion_consistency"]) * min(1.0, float(motion["phase_response"]) / 0.25) * max(0.25, row_structure)
    static_motion_score = 1.0 if max(vertical_speed, horizontal_speed) < 0.35 else 0.35
    # Static credit cards are prone to false positives on film-scene overlays.
    # Require a genuinely dark field before static text can drive the label.
    static_text_score = 0.0 if dark_ratio < 0.35 else structured_density * static_motion_score
    strong_scroll_bonus = 0.0
    if vertical_speed >= 10.0 and float(motion["motion_consistency"]) >= 0.80 and (dark_ratio >= 0.12 or text_density >= 0.055):
        strong_scroll_bonus = 0.16
    credit_score = (0.56 * structured_density) + (0.14 * dark_score) + (0.22 * max(scroll_score, static_text_score)) + (0.08 * min(1.0, float(motion["phase_response"]) / 0.35) * max(0.25, row_structure))
    credit_score += strong_scroll_bonus
    credit_score = max(0.0, min(1.0, credit_score))

    if credit_score < threshold:
        label = "non_credit"
    elif scroll_score >= 0.32 and vertical_speed >= horizontal_speed * 1.35:
        label = "vertical_scroll_credit"
    elif scroll_score >= 0.32 and horizontal_speed > vertical_speed * 1.35:
        label = "horizontal_crawl_credit"
    elif static_text_score <= 0.0:
        label = "non_credit"
    else:
        label = "static_credit"
    return CreditWindowScore(
        index=index,
        start_seconds=round(float(start_seconds), 3),
        end_seconds=round(float(end_seconds), 3),
        credit_score=round(float(credit_score), 4),
        text_density=round(float(text_density), 5),
        row_structure=round(float(row_structure), 4),
        dark_ratio=round(float(dark_ratio), 5),
        median_dx_per_frame=round(float(motion["median_dx_per_frame"]), 4),
        median_dy_per_frame=round(float(motion["median_dy_per_frame"]), 4),
        motion_consistency=round(float(motion["motion_consistency"]), 4),
        phase_response=round(float(motion["phase_response"]), 4),
        label=label,
    )


def _text_motion(masks: list[Any], cv2: Any, np: Any) -> dict[str, float]:
    shifts_x = []
    shifts_y = []
    responses = []
    for left, right in zip(masks, masks[1:]):
        if int((left > 0).sum()) < 20 or int((right > 0).sum()) < 20:
            continue
        shift, response = cv2.phaseCorrelate(left.astype(np.float32) / 255.0, right.astype(np.float32) / 255.0)
        dx, dy = float(shift[0]), float(shift[1])
        if abs(dx) > left.shape[1] * 0.25 or abs(dy) > left.shape[0] * 0.25:
            continue
        shifts_x.append(dx)
        shifts_y.append(dy)
        responses.append(float(response))
    if not shifts_y:
        return {"median_dx_per_frame": 0.0, "median_dy_per_frame": 0.0, "motion_consistency": 0.0, "phase_response": 0.0}
    med_x = float(median(shifts_x))
    med_y = float(median(shifts_y))
    signs = [1 if value > 0 else -1 if value < 0 else 0 for value in shifts_y if abs(value) >= 0.25]
    if signs:
        positive = sum(1 for sign in signs if sign > 0)
        negative = sum(1 for sign in signs if sign < 0)
        consistency = max(positive, negative) / len(signs)
    else:
        consistency = 0.0
    return {
        "median_dx_per_frame": med_x,
        "median_dy_per_frame": med_y,
        "motion_consistency": float(consistency),
        "phase_response": float(median(responses)) if responses else 0.0,
    }


def _row_structure_score(mask: Any, np: Any) -> float:
    active = mask > 0
    if int(active.sum()) < 20:
        return 0.0
    height, width = mask.shape[:2]
    profile = active.sum(axis=1).astype(float)
    kernel_width = max(3, int(height * 0.012))
    kernel = np.ones(kernel_width) / kernel_width
    smooth = np.convolve(profile, kernel, mode="same")
    active_rows = smooth > max(2.0, width * 0.006)
    if not active_rows.any():
        return 0.0
    row_coverage = float(active_rows.sum() / max(1, height))
    mean_active = float(smooth[active_rows].mean())
    peak_strength = float(smooth.max()) / max(mean_active, 1.0)
    compactness = 1.0 - min(1.0, row_coverage / 0.55)
    peak_score = min(1.0, peak_strength / 3.5)
    return max(0.0, min(1.0, 0.60 * compactness + 0.40 * peak_score))


def _text_like_mask(image: Any, cv2: Any, np: Any) -> Any:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    blur = cv2.GaussianBlur(gray, (0, 0), 3)
    local = cv2.absdiff(gray, blur)
    local_threshold = max(6.0, float(local.mean()) + float(local.std()) * 0.95)
    bright_gate = gray > max(54.0, float(gray.mean()) + float(gray.std()) * 0.20)
    bright = ((local > local_threshold) & bright_gate).astype(np.uint8) * 255
    saturated = ((hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 72) & (local > max(5.0, local_threshold * 0.55))).astype(np.uint8) * 255
    edges = cv2.Canny(gray, 60, 160)
    mask = cv2.bitwise_or(bright, saturated)
    mask = cv2.bitwise_or(mask, cv2.bitwise_and(cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1), mask))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
    return _filter_components(mask, cv2, np)


def _filter_components(mask: Any, cv2: Any, np: Any) -> Any:
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=8)
    if count <= 1:
        return mask
    height, width = mask.shape[:2]
    filtered = np.zeros_like(mask)
    max_area = max(80, int(width * height * 0.035))
    for label in range(1, count):
        x, y, w, h, area = stats[label]
        if area < 3 or area > max_area:
            continue
        if w > width * 0.86 or h > height * 0.38:
            continue
        filtered[labels == label] = 255
    return filtered


def _resize_to_first(images: list[Any], cv2: Any) -> list[Any]:
    height, width = images[0].shape[:2]
    resized = []
    for image in images:
        if image.shape[:2] == (height, width):
            resized.append(image)
        else:
            resized.append(cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA))
    return resized


def _group_segments(windows: list[CreditWindowScore], *, threshold: float) -> list[CreditSegment]:
    segments: list[CreditSegment] = []
    current: list[CreditWindowScore] = []
    for window in windows:
        if window.credit_score >= threshold:
            current.append(window)
            continue
        if current:
            segments.append(_segment_from_windows(current))
            current = []
    if current:
        segments.append(_segment_from_windows(current))
    return _merge_close_segments(segments, windows, max_gap_seconds=5.0)


def _segment_from_windows(windows: list[CreditWindowScore]) -> CreditSegment:
    labels = [window.label for window in windows]
    scroll_count = sum(1 for label in labels if "scroll" in label or "crawl" in label)
    abs_dys = [abs(float(window.median_dy_per_frame)) for window in windows]
    consistencies = [float(window.motion_consistency) for window in windows]
    strong_segment_scroll = bool(abs_dys) and median(abs_dys) >= 8.0 and median(consistencies) >= 0.80
    if scroll_count >= max(1, len(labels) // 2 + 1) or strong_segment_scroll:
        label = "scrolling_credit"
    else:
        label = "static_or_mixed_credit"
    confidence = median([window.credit_score for window in windows])
    return CreditSegment(
        start_seconds=windows[0].start_seconds,
        end_seconds=windows[-1].end_seconds,
        label=label,
        confidence=round(float(confidence), 4),
        window_indices=tuple(window.index for window in windows),
    )


def _merge_close_segments(segments: list[CreditSegment], windows: list[CreditWindowScore], *, max_gap_seconds: float) -> list[CreditSegment]:
    if len(segments) <= 1:
        return segments
    by_index = {window.index: window for window in windows}
    merged: list[list[int]] = [[*segments[0].window_indices]]
    last_end = segments[0].end_seconds
    for segment in segments[1:]:
        if segment.start_seconds - last_end <= max_gap_seconds:
            merged[-1].extend(segment.window_indices)
        else:
            merged.append([*segment.window_indices])
        last_end = segment.end_seconds
    output: list[CreditSegment] = []
    for indices in merged:
        segment_windows = [by_index[index] for index in indices if index in by_index]
        if segment_windows:
            output.append(_segment_from_windows(segment_windows))
    return output


def _build_report(result: CreditDetectionResult) -> str:
    lines = [
        "# Credit Detector",
        "",
        f"- Video: {result.video_path}",
        f"- First credit start: {result.to_dict().get('first_credit_start_seconds')}",
        f"- Segments: {len(result.segments)}",
        "",
        "## Segments",
        "",
        "| start | end | label | confidence | windows |",
        "| ---: | ---: | --- | ---: | --- |",
    ]
    for segment in result.segments:
        lines.append(f"| {segment.start_seconds} | {segment.end_seconds} | {segment.label} | {segment.confidence} | {list(segment.window_indices)} |")
    lines.extend(["", "## Windows", "", "| # | start | end | score | label | density | rows | dark | dy | consistency |", "| ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |"])
    for window in result.windows:
        lines.append(
            f"| {window.index} | {window.start_seconds} | {window.end_seconds} | {window.credit_score} | {window.label} | "
            f"{window.text_density} | {window.row_structure} | {window.dark_ratio} | {window.median_dy_per_frame} | {window.motion_consistency} |"
        )
    return "\n".join(lines) + "\n"


@dataclass
class OpusProbeResult:
    t: float
    dark_ratio: float
    text_ratio: float
    avg_dy: float
    dy_std: float
    n_good: int

    @property
    def scroll_score(self) -> float:
        dark_s = min(1.0, self.dark_ratio / 0.50)
        text_s = min(1.0, self.text_ratio / 0.015)
        if self.n_good >= 3 and abs(self.avg_dy) > 0.8:
            snr = abs(self.avg_dy) / max(0.5, self.dy_std)
            motion_s = min(1.0, snr / 2.5)
        else:
            motion_s = 0.0
        return 0.25 * dark_s + 0.25 * text_s + 0.50 * motion_s

    @property
    def static_score(self) -> float:
        if self.dark_ratio < 0.35:
            return 0.0
        dark_s = min(1.0, self.dark_ratio / 0.60)
        text_s = min(1.0, self.text_ratio / 0.015)
        still_s = 1.0 if abs(self.avg_dy) < 0.5 else max(0.0, 1.0 - abs(self.avg_dy) / 3.0)
        return 0.30 * dark_s + 0.40 * text_s + 0.30 * still_s

    @property
    def is_credit(self) -> bool:
        return self.scroll_score >= 0.55 or self.static_score >= 0.60

    @property
    def credit_type(self) -> str:
        if self.scroll_score >= 0.55 and self.scroll_score >= self.static_score:
            return "scroll"
        if self.static_score >= 0.60:
            return "static"
        return "none"


class OpusCreditDetector:
    """Opus/tools-style credit detector used to trim broad last-N-minute windows.

    This intentionally lives beside the MITAS window scorer. Its job is not to
    replace all routing logic; it only finds the cleaner credit subsegment before
    row reconstruction and OCR experiments spend time on mixed scene/title cards.
    """

    dark_thresh = 30
    probe_sec = 10
    refine_sec = 2
    motion_dt = 0.4
    motion_n = 5
    min_credit = 20
    merge_gap = 30
    search_end_min = 15

    def detect(self, video_path: str | Path, *, search_end_min: float | None = None, verbose: bool = False) -> dict[str, Any]:
        import cv2
        import numpy as np

        path = Path(video_path)
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return self._no_result("video_not_opened")
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = total / fps if total > 0 else 0.0
        end_m = search_end_min if search_end_min is not None else self.search_end_min
        search_start = max(0.0, duration - float(end_m) * 60.0)
        probes = self._broad_scan(cap, cv2, np, fps, search_start, duration)
        segment = self._find_segment(probes, np)
        if segment is None and search_start > 0:
            probes = self._broad_scan(cap, cv2, np, fps, 0.0, duration)
            segment = self._find_segment(probes, np)
        if segment is None:
            cap.release()
            return self._no_result("not_found")
        raw_start, raw_end, ctype, speed, confidence = segment
        start = self._refine(cap, cv2, np, fps, raw_start - self.probe_sec, raw_start + self.probe_sec, "start", ctype)
        end = self._refine(cap, cv2, np, fps, raw_end - self.probe_sec, raw_end + self.probe_sec, "end", ctype)
        if ctype == "scroll":
            measured = self._measure_speed(cap, cv2, np, fps, start, end)
            if abs(measured) > 0.3:
                speed = measured
        cap.release()
        return {
            "found": True,
            "type": ctype,
            "start_sec": round(float(start), 3),
            "end_sec": round(float(end), 3),
            "scroll_speed": round(float(speed), 3),
            "confidence": round(float(confidence), 3),
            "strategy": "opus_credit_detector",
        }

    def _broad_scan(self, cap: Any, cv2: Any, np: Any, fps: float, start: float, end: float) -> list[OpusProbeResult]:
        probes = []
        t = float(start)
        while t <= float(end):
            probes.append(self._probe_at(cap, cv2, np, fps, t))
            t += self.probe_sec
        return probes

    def _find_segment(self, probes: list[OpusProbeResult], np: Any) -> tuple[float, float, str, float, float] | None:
        if not probes:
            return None
        flags = [probe.is_credit for probe in probes]
        gap_probes = int(np.ceil(self.merge_gap / self.probe_sec))
        merged = list(flags)
        for index, value in enumerate(merged):
            if not value and any(merged[index + 1 : index + 1 + gap_probes]):
                merged[index] = True
        runs: list[tuple[int, int]] = []
        start = None
        for index, value in enumerate(merged):
            if value and start is None:
                start = index
            elif not value and start is not None:
                runs.append((start, index - 1))
                start = None
        if start is not None:
            runs.append((start, len(merged) - 1))
        min_probes = max(2, int(np.ceil(self.min_credit / self.probe_sec)))
        valid = [(left, right) for left, right in runs if right - left + 1 >= min_probes]
        if not valid:
            return None
        last_t = probes[-1].t if probes else 1.0

        def score(pair: tuple[int, int]) -> float:
            left, right = pair
            length_w = (right - left + 1) / max(1, len(probes))
            pos_w = probes[right].t / max(1.0, last_t)
            credit_probes = [probes[i] for i in range(left, right + 1) if probes[i].is_credit]
            quality = float(np.mean([max(probe.scroll_score, probe.static_score) for probe in credit_probes])) if credit_probes else 0.0
            return length_w * 0.20 + pos_w * 0.60 + quality * 0.20

        left, right = max(valid, key=score)
        segment_probes = [probes[i] for i in range(left, right + 1) if probes[i].is_credit]
        if not segment_probes:
            return None
        scroll_votes = sum(1 for probe in segment_probes if probe.credit_type == "scroll")
        clear_scrolls = sum(1 for probe in segment_probes if probe.scroll_score >= 0.65)
        if clear_scrolls >= 2 or scroll_votes > len(segment_probes) / 2:
            ctype = "scroll"
        else:
            ctype = "static"
        speeds = [probe.avg_dy for probe in segment_probes if abs(probe.avg_dy) > 0.5]
        speed = float(np.median(speeds)) if ctype == "scroll" and speeds else 0.0
        if ctype == "scroll":
            confidence = float(np.mean([probe.scroll_score for probe in segment_probes]))
        else:
            confidence = float(np.mean([probe.static_score for probe in segment_probes]))
        return probes[left].t, probes[right].t, ctype, speed, confidence

    def _refine(self, cap: Any, cv2: Any, np: Any, fps: float, t0: float, t1: float, boundary: str, ctype: str) -> float:
        t0 = max(0.0, float(t0))
        t1 = max(t0, float(t1))
        probes = []
        t = t0
        while t <= t1:
            probes.append(self._probe_at(cap, cv2, np, fps, t))
            t += self.refine_sec
        if not probes:
            return t0 if boundary == "start" else t1
        if boundary == "start":
            for probe in probes:
                if (probe.scroll_score >= 0.55 if ctype == "scroll" else probe.static_score >= 0.55):
                    return probe.t
            return probes[0].t
        last_t = t0
        for probe in probes:
            if (probe.scroll_score >= 0.55 if ctype == "scroll" else probe.static_score >= 0.55):
                last_t = probe.t
        return last_t + self.refine_sec

    def _measure_speed(self, cap: Any, cv2: Any, np: Any, fps: float, start: float, end: float) -> float:
        dt_frames = max(1, int(round(0.2 * fps)))
        total = max(1.0, float(end) - float(start))
        speeds = []
        for frac in (0.25, 0.50, 0.75):
            t = float(start) + frac * total
            frames = self._read_frames(cap, cv2, fps, t, n=12, dt=0.2)
            if len(frames) < 3:
                continue
            avg_dy, _dy_std, n_good = self._motion_signals(frames, cv2, np, dt_frames)
            if n_good >= 3 and abs(avg_dy) > 0.3:
                speeds.append(avg_dy)
        if not speeds:
            return 0.0
        return float(max(speeds, key=abs))

    def _probe_at(self, cap: Any, cv2: Any, np: Any, fps: float, t: float) -> OpusProbeResult:
        frames = self._read_frames(cap, cv2, fps, t, n=self.motion_n, dt=self.motion_dt)
        if not frames:
            return OpusProbeResult(t, 0.0, 0.0, 0.0, 0.0, 0)
        dark_ratio, text_ratio = self._frame_signals(frames[0], cv2)
        dt_frames = max(1, int(round(self.motion_dt * fps)))
        avg_dy, dy_std, n_good = self._motion_signals(frames, cv2, np, dt_frames)
        return OpusProbeResult(float(t), dark_ratio, text_ratio, avg_dy, dy_std, n_good)

    def _read_frames(self, cap: Any, cv2: Any, fps: float, t: float, *, n: int, dt: float) -> list[Any]:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        frames = []
        for index in range(n):
            frame_index = int((float(t) + index * float(dt)) * fps)
            if total_frames > 0 and frame_index >= total_frames:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, float(frame_index))
            ok, frame = cap.read()
            if ok and frame is not None:
                frames.append(frame)
        return frames

    def _frame_signals(self, frame: Any, cv2: Any) -> tuple[float, float]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        total = max(1, gray.size)
        dark_ratio = float((gray < self.dark_thresh).sum()) / total
        threshold = max(50.0, float(gray.mean()) + 1.5 * float(gray.std()))
        text_ratio = float((gray > threshold).sum()) / total
        return dark_ratio, text_ratio

    def _text_mask_for_detection(self, gray: Any, cv2: Any, np: Any) -> Any | None:
        threshold = max(45.0, float(gray.mean()) + float(gray.std()))
        _ok, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.dilate(mask, np.ones((11, 11), np.uint8))
        return mask if mask.any() else None

    def _motion_signals(self, frames: list[Any], cv2: Any, np: Any, dt_frames: int = 1) -> tuple[float, float, int]:
        if len(frames) < 2:
            return 0.0, 0.0, 0
        dys = []
        prev = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
        pts = cv2.goodFeaturesToTrack(prev, mask=self._text_mask_for_detection(prev, cv2, np), maxCorners=40, qualityLevel=0.2, minDistance=10, blockSize=7)
        lk = dict(winSize=(21, 21), maxLevel=2, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.05))
        for frame in frames[1:]:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if pts is None or len(pts) < 4:
                pts = cv2.goodFeaturesToTrack(prev, mask=self._text_mask_for_detection(prev, cv2, np), maxCorners=40, qualityLevel=0.2, minDistance=10, blockSize=7)
            if pts is None:
                prev = gray
                continue
            nxt, status, _err = cv2.calcOpticalFlowPyrLK(prev, gray, pts, None, **lk)
            if nxt is None or status is None:
                prev = gray
                continue
            keep = status.ravel().astype(bool)
            if int(keep.sum()) >= 4:
                raw_dy = float(np.median(nxt[keep, 0, 1] - pts[keep, 0, 1]))
                dys.append(raw_dy / max(1, dt_frames))
                pts = nxt[keep].reshape(-1, 1, 2)
            prev = gray
        if not dys:
            return 0.0, 0.0, 0
        return float(np.mean(dys)), float(np.std(dys)) if len(dys) > 1 else 0.0, len(dys)

    def _text_mask(self, gray: Any, cv2: Any, np: Any) -> Any:
        bright = gray > max(50.0, float(gray.mean()) + float(gray.std()) * 0.35)
        edges = cv2.Canny(gray, 50, 150) > 0
        mask = (bright & edges).astype(np.uint8) * 255
        mask = cv2.dilate(mask, np.ones((2, 2), np.uint8), iterations=1)
        return mask

    def _no_result(self, reason: str) -> dict[str, Any]:
        return {
            "found": False,
            "type": "none",
            "start_sec": 0.0,
            "end_sec": 0.0,
            "scroll_speed": 0.0,
            "confidence": 0.0,
            "strategy": "opus_credit_detector",
            "reason": reason,
        }
