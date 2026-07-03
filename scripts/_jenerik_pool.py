# -*- coding: utf-8 -*-
"""Create the parallel end-credit frame pool for MITAS.

Input stays untouched:
  Database/<film>/frames/cikis

Output is always created:
  Database/<film>/frames/cikis_jenerik

The pool is intentionally separate from the normal OneOCR path.  OneOCR keeps
reading the original frame folders; GLM/VL/master debug jobs can read this
filtered pool.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
import shutil
import sys
import time
from pathlib import Path


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJECT_ROOT = Path(r"E:\MITAS")
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("JENERIK_PADDLE_FAST_NO_DOC", "1")

from core.pipelines.ocr.jenerik_frame_pool_detector import (  # noqa: E402
    DetectorConfig,
    detect_frame_dir,
    list_images,
)


ACCEPT_STATUSES = {"already_in_credit"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _safe_reset_pool(pool_dir: Path) -> None:
    resolved = pool_dir.resolve()
    if resolved.name.lower() != "cikis_jenerik":
        raise ValueError(f"refusing to reset unexpected pool dir: {resolved}")
    if resolved.parent.name.lower() != "frames":
        raise ValueError(f"refusing to reset pool outside frames dir: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def _accept_review_enabled() -> bool:
    # #1 fix (2026-06-27): review_boundary_ambiguous = detektör ONAYLI kredi-çapası buldu ama sınır
    # muğlak (postprocess promote_result_to_anchor confirmed-anchor üzerinden üretir → start_pos GEÇERLİ).
    # Eskiden BOŞ havuz → master-PNG/VL/GLM kaybı (ALİTA/JUMP'ta CANLI doğrulandı). DEFAULT ON; kapat =0.
    return os.environ.get("MITAS_JENERIK_POOL_ACCEPT_REVIEW", "1").strip().lower() not in ("0", "false", "off", "no")


def _accepted(status: str) -> bool:
    if status in ACCEPT_STATUSES or status.startswith("found"):
        return True
    # review_scene_text / review_low_confidence = kredi-kanıtı YOK → havuza ALMA (footage riski).
    # Yalnız review_boundary_ambiguous (onaylı çapa, muğlak sınır) → doldur.
    return status == "review_boundary_ambiguous" and _accept_review_enabled()


def _oneocr_fallback_enabled() -> bool:
    # B kararı (Çağatay 2026-06-27): paddle başarısızsa (not_found/review-scene/low-conf) OneOCR-detektörü
    # dene → non-Latin/FR'yi kurtarır. OneOCR ~80sn/film yavaş ama YALNIZ paddle-başarısızlarında koşar
    # (paddle hızını korur, sadece gerekli ~%20'de OneOCR). DEFAULT ON; kapat =0.
    return os.environ.get("MITAS_JENERIK_ONEOCR_FALLBACK", "1").strip().lower() not in ("0", "false", "off", "no")


def create_pool(
    *,
    frames_dir: Path,
    pool_dir: Path,
    debug_root: Path,
    cfg: DetectorConfig,
    debug_sheet: bool,
) -> dict:
    started = time.perf_counter()
    detector_dir = debug_root / "detector"
    result = detect_frame_dir(frames_dir, detector_dir, cfg, debug_sheet)
    images = list_images(frames_dir)
    engine_used = "paddle"

    # OneOCR FALLBACK: paddle kredi-başlangıcı bulamadıysa OneOCR-detektörü dene (non-Latin/FR kurtarır).
    if not _accepted(result.status) and _oneocr_fallback_enabled():
        os.environ.setdefault("MITAS_JENERIK_LATIN_LC_NAMES", "1")
        os.environ.setdefault("MITAS_JENERIK_NONLATIN_NAMES", "1")
        try:
            from core.pipelines.ocr.jenerik_oneocr_detector import detect_frame_dir_oneocr
            oc = detect_frame_dir_oneocr(frames_dir, debug_root / "detector_oneocr", cfg)
            if _accepted(oc.status):
                result = oc
                engine_used = "oneocr"
        except Exception as exc:  # noqa: BLE001 — fallback hatası pipeline'ı bozmaz
            _append_jsonl(debug_root / "errors.jsonl",
                          {"ts": _now(), "stage": "oneocr_fallback", "error": f"{type(exc).__name__}: {exc}"})

    copied: list[dict] = []
    status = result.status
    start_pos = result.start_pos
    will_fill = (_accepted(status) and start_pos is not None
                 and 0 <= int(start_pos) < len(images))
    preserved_existing = False
    if will_fill:
        # Yeni kareler dolduracağız → bayat kareleri temizle, sonra doldur.
        _safe_reset_pool(pool_dir)
        for source in images[int(start_pos):]:
            target = pool_dir / source.name
            shutil.copy2(source, target)
            copied.append({"source": str(source), "target": str(target), "file": source.name})
    else:
        # Bu koşuda kredi-başlangıcı YOK. ÖNCEKİ başarılı havuzu YOK ETME — flaky/tekrar koşum
        # iyi havuzu silip master'ı kaybetmesin (2026-06-29). Havuz yoksa boş oluştur (dizin-var invariantı).
        preserved_existing = bool(pool_dir.is_dir() and list(pool_dir.glob("*.png")))
        pool_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "status": status,
        "engine": engine_used,
        "accepted": bool(copied),
        "preserved_existing_pool": preserved_existing,
        "input_frames": len(images),
        "pool_frames": len(copied),
        "source_frames_dir": str(frames_dir),
        "pool_dir": str(pool_dir),
        "start_pos": result.start_pos,
        "start_file": result.start_file,
        "first_text_pos": result.first_text_pos,
        "first_text_file": result.first_text_file,
        "confidence": result.confidence,
        "credit_type": result.credit_type,
        "reason": result.reason,
        "copied_files": copied,
        "detector": asdict(result),
        "duration_sec": round(time.perf_counter() - started, 3),
        "ts": _now(),
    }

    frames_manifest = frames_dir.parent / "jenerik_detection.json"
    _write_json(frames_manifest, manifest)
    _write_json(debug_root / "pool" / "manifest.json", manifest)
    _append_jsonl(debug_root / "events.jsonl", {
        "ts": _now(),
        "stage": "pool",
        "status": status,
        "input_frames": len(images),
        "pool_frames": len(copied),
        "start_file": result.start_file,
        "first_text_file": result.first_text_file,
    })
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build MITAS parallel jenerik frame pool")
    parser.add_argument("--frames", required=True, help="Database/<film>/frames/cikis")
    parser.add_argument("--pool", required=True, help="Database/<film>/frames/cikis_jenerik")
    parser.add_argument("--debug-root", required=True, help="Database/<film>/jenerik_debug")
    parser.add_argument("--debug-sheet", action="store_true")
    parser.add_argument("--max-width", type=int, default=DetectorConfig.max_width)
    parser.add_argument("--text-threshold", type=float, default=DetectorConfig.text_threshold)
    parser.add_argument("--soft-threshold", type=float, default=DetectorConfig.soft_threshold)
    parser.add_argument("--lookahead", type=int, default=DetectorConfig.lookahead)
    parser.add_argument("--min-hits", type=int, default=DetectorConfig.min_hits)
    parser.add_argument("--preroll-frames", type=int, default=DetectorConfig.preroll_frames)
    parser.add_argument("--ocr-mode", choices=["none", "paddle"], default="paddle")
    parser.add_argument("--ocr-stride", type=int, default=8)
    parser.add_argument("--ocr-lang", default=DetectorConfig.ocr_lang)
    parser.add_argument("--sustain-window", type=int, default=DetectorConfig.sustain_window)
    parser.add_argument("--sustain-hits", type=int, default=DetectorConfig.sustain_hits)
    return parser


def main(argv: list[str] | None = None) -> int:
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
    debug_root = Path(args.debug_root)
    try:
        manifest = create_pool(
            frames_dir=Path(args.frames),
            pool_dir=Path(args.pool),
            debug_root=debug_root,
            cfg=cfg,
            debug_sheet=args.debug_sheet,
        )
        print(json.dumps(manifest, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 - fail-safe caller logs and continues
        err = {
            "ts": _now(),
            "stage": "pool",
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
        _append_jsonl(debug_root / "errors.jsonl", err)
        print(json.dumps(err, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
