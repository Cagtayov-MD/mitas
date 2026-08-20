"""Rule-based OCR pipeline selector for credit/video-text segments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PipelineRecommendation:
    roi: str
    preprocess: tuple[str, ...]
    temporal: str
    ocr: str
    parser: str
    steps: tuple[str, ...]
    fallback_pipelines: tuple[str, ...]
    why: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: list(value) if isinstance(value, tuple) else value for key, value in payload.items()}


def select_credit_pipeline(profile: Mapping[str, Any]) -> PipelineRecommendation:
    """Convert a router profile into an executable OCR strategy recommendation.

    This function is intentionally deterministic and conservative. It does not
    run OCR; it only explains which existing pipeline family should be tried.
    """
    background = _decision_value(profile.get("background"), default="unknown")
    text_motion = _decision_value(profile.get("text_motion"), default="unknown")
    layout = _decision_value(profile.get("layout"), default="unknown")
    difficulty = profile.get("difficulty") or {}
    difficulty_labels = set(difficulty.get("labels") or [])
    difficulty_score = float(difficulty.get("score") or 0.0)

    preprocess: list[str] = []
    steps: list[str] = []
    why: list[str] = []
    fallback: list[str] = []

    roi = "full_frame"
    parser = "plain_line_parser"
    temporal = "frame_ensemble"

    if background in {"moving_scene", "camera_motion", "transition"}:
        preprocess.extend(["text_mask", "background_suppression"])
        steps.append("text_mask_extraction")
        why.append(f"background={background} needs text/background separation")

    if "low_contrast" in difficulty_labels:
        preprocess.extend(["clahe", "contrast_boost"])
        why.append("low_contrast detected")
    if "blur_or_lowres" in difficulty_labels:
        preprocess.extend(["upscale2x", "sharpen"])
        why.append("blur_or_lowres detected")
    if "shadow_or_outline" in difficulty_labels:
        preprocess.extend(["edge_enhance", "outline_aware_threshold"])
        why.append("shadow_or_outline detected")
    if "background_clutter" in difficulty_labels:
        preprocess.append("adaptive_threshold")
        why.append("background_clutter detected")

    if text_motion == "vertical_scroll":
        temporal = "row_reconstruct"
        steps.extend(["scroll_compensation", "center_strip_composite", "row_detection"])
        why.append("vertical text motion detected")
    elif text_motion == "horizontal_crawl":
        temporal = "horizontal_stitching"
        steps.extend(["crawl_tracking", "temporal_stitching"])
        why.append("horizontal text motion detected")
    elif text_motion == "static_card":
        # Router emits: flat_static, image_static, moving_scene, camera_motion, unknown.
        # "static" is accepted as a normalized alias for callers that emit it.
        if background in {"moving_scene", "camera_motion", "transition"}:
            temporal = "temporal_variance_masking"
            steps.extend(["temporal_variance_mask", "text_layer_extraction"])
            fallback.extend(["temporal_median_fusion", "best_frame_selection", "temporal_voting"])
            why.append("static text on moving background → variance masking")
        elif background in {"flat_static", "image_static", "static"}:
            temporal = "temporal_median_fusion"
            steps.extend(["temporal_median_stack", "noise_reduction"])
            fallback.extend(["best_frame_selection", "temporal_voting"])
            why.append("static text on static background → median fusion")
        else:
            # Unknown BG: variance masking is the safer default. It also denoises
            # a truly static BG (less optimally than median), but is robust if BG
            # turns out to be moving.
            temporal = "temporal_variance_masking"
            steps.extend(["temporal_variance_mask", "text_layer_extraction"])
            fallback.extend(["temporal_median_fusion", "best_frame_selection", "temporal_voting"])
            why.append("static text + unknown background → variance masking (conservative)")
    elif text_motion == "mixed":
        temporal = "segment_then_route"
        steps.append("split_mixed_credit_segments")
        fallback.extend(["row_reconstruct", "best_frame_selection"])
        why.append("mixed text motion detected")
    else:
        temporal = "temporal_voting"
        fallback.append("frame_ocr")
        why.append("text motion uncertain")

    if layout == "lower_third":
        roi = "bottom_35"
        parser = "lower_third_parser"
        why.append("layout=lower_third")
    elif layout == "multi_column":
        roi = "text_region"
        parser = "column_aware_parser"
        steps.append("column_clustering")
        why.append("layout=multi_column")
    elif layout == "center_single_column":
        roi = "center_text_region"
        parser = "block_role_name_parser"
        why.append("layout=center_single_column")
    elif layout == "role_name_same_line":
        roi = "text_region"
        parser = "inline_role_name_parser"
        why.append("layout=role_name_same_line")

    if difficulty_score >= 0.66:
        fallback.append("vlm_review_candidate")
        why.append("hard difficulty score")

    return PipelineRecommendation(
        roi=roi,
        preprocess=tuple(dict.fromkeys(preprocess)),
        temporal=temporal,
        ocr="paddle_ppocrv5",
        parser=parser,
        steps=tuple(dict.fromkeys([*steps, "ocr", "temporal_fusion", parser])),
        fallback_pipelines=tuple(dict.fromkeys(fallback)),
        why=tuple(dict.fromkeys(why)),
    )


def _decision_value(value: Any, *, default: str) -> str:
    if isinstance(value, Mapping):
        return str(value.get("type") or value.get("value") or default)
    if value:
        return str(value)
    return default
