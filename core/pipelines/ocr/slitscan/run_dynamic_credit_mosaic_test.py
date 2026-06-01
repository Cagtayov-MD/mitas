"""Dynamic Credit Mosaic test koşucusu.

Kullanım:
    python run_dynamic_credit_mosaic_test.py
    python run_dynamic_credit_mosaic_test.py --stride 3 --max-frames 200
    python run_dynamic_credit_mosaic_test.py --frames-dir E:\\MITAS\\outputs\\...\\frames\\opening

Çıktı: outputs/_sonmetro_dynamic_mosaic_poc_20260530/
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

# --- Proje kökünü sys.path'e ekle ---
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

# --- Varsayılan yollar ---
DEFAULT_FRAMES_DIR = (
    Path(r"E:\MITAS\outputs\_sonmetro_best_20260530\items\1980_son_metro_wide\frames\opening")
)
DEFAULT_OUTPUT_DIR = Path(r"E:\MITAS\outputs\_sonmetro_dynamic_mosaic_poc_20260530")
DEFAULT_FPS: float = 6.0


def _load_frames(
    frames_dir: Path,
    max_frames: int | None = None,
    stride: int = 1,
) -> list[Path]:
    """Kare dosyalarını sıralı yükle (isteğe bağlı stride ve max_frames)."""
    all_frames = sorted(
        frames_dir.glob("frame_*.png"),
        key=lambda p: int(p.stem.split("_")[-1]),
    )
    if stride > 1:
        all_frames = all_frames[::stride]
    if max_frames is not None:
        all_frames = all_frames[:max_frames]
    return all_frames


def _print_signal_stats(debug_path: Path) -> None:
    """debug.json'dan sinyal istatistiklerini yazdır (kalibrasyon için)."""
    try:
        data = json.loads(debug_path.read_text(encoding="utf-8"))
        frames = data.get("frames", [])
        if not frames:
            print("  [Kalibrasyon] debug.json boş.", flush=True)
            return

        text_frames = [f for f in frames if f.get("has_text")]
        print(f"\n  [Kalibrasyon] Metin kare sayısı: {len(text_frames)}/{len(frames)}", flush=True)

        if not text_frames:
            print("  [Kalibrasyon] Hiç metin karesi yok!", flush=True)
            return

        def _pct(vals: list[float], p: int) -> float:
            return float(np.percentile(vals, p)) if vals else 0.0

        def _stats(name: str, vals: list[float]) -> None:
            if not vals:
                return
            arr = np.array(vals)
            print(
                f"    {name:20s}: min={arr.min():.3f}  p25={_pct(vals,25):.3f}"
                f"  median={np.median(arr):.3f}  p75={_pct(vals,75):.3f}"
                f"  p95={_pct(vals,95):.3f}  max={arr.max():.3f}",
                flush=True,
            )

        _stats("dy",             [f["dy"] for f in text_frames])
        _stats("dy_smoothed",    [f["dy_smoothed"] for f in text_frames])
        _stats("response",       [f["response"] for f in text_frames])
        _stats("global_diff",    [f["global_diff"] for f in text_frames])
        _stats("text_band_diff", [f["text_band_diff"] for f in text_frames])
        _stats("text_ratio",     [f["text_ratio"] for f in text_frames])

        # Durum dağılımı
        from collections import Counter
        state_dist = Counter(f["state"] for f in frames)
        event_dist = Counter(f["event"] for f in frames)
        print(f"    state_dist: {dict(state_dist)}", flush=True)
        print(f"    event_dist: {dict(event_dist)}", flush=True)

        # Run params
        rp = data.get("run_params", {})
        print(f"\n  [RunParams] S_HI={rp.get('S_HI')} S_LO={rp.get('S_LO')}"
              f" CARD_SWAP_DIFF_MIN={rp.get('CARD_SWAP_DIFF_MIN')}"
              f" Y_REF_FRAC={rp.get('Y_REF_FRAC')}", flush=True)

    except Exception as e:
        print(f"  [Kalibrasyon] Hata: {e}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dynamic Credit Mosaic test koşucusu"
    )
    parser.add_argument(
        "--frames-dir",
        type=Path,
        default=DEFAULT_FRAMES_DIR,
        help=f"Kare dizini (varsayılan: {DEFAULT_FRAMES_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Çıktı dizini (varsayılan: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=DEFAULT_FPS,
        help=f"Kaynak FPS (varsayılan: {DEFAULT_FPS})",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maksimum kare sayısı (hızlı test için kısalt)",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=1,
        help="Her N. kareyi al (hızlı kalibrasyon için, örn: 3)",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Yalnızca mevcut debug.json'ı analiz et (yeniden çalıştırma yok)",
    )
    args = parser.parse_args()

    # -------------------------------------------------------------------
    if args.stats_only:
        debug_path = args.output_dir / "debug.json"
        if not debug_path.exists():
            print(f"[HATA] debug.json bulunamadı: {debug_path}", file=sys.stderr)
            sys.exit(1)
        _print_signal_stats(debug_path)
        return

    # --- Kare dizini kontrol ---
    if not args.frames_dir.exists():
        print(f"[HATA] Kare dizini bulunamadı: {args.frames_dir}", file=sys.stderr)
        sys.exit(1)

    frames = _load_frames(args.frames_dir, args.max_frames, args.stride)
    if not frames:
        print(f"[HATA] Kare bulunamadı: {args.frames_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"[DynMosaic] Kare sayısı: {len(frames)}", flush=True)
    print(f"[DynMosaic] Çıktı dizini: {args.output_dir}", flush=True)
    if args.stride > 1:
        print(f"[DynMosaic] Stride: {args.stride} (hızlı kalibrasyon)", flush=True)

    # --- Modülü yükle ---
    from core.pipelines.ocr.slitscan.dynamic_credit_mosaic import run_dynamic_credit_mosaic

    # --- Çalıştır ---
    t0 = perf_counter()
    try:
        result = run_dynamic_credit_mosaic(
            frames,
            output_dir=args.output_dir,
            source_fps=args.fps,
        )
        elapsed = perf_counter() - t0

        mw, mh = result.canvas_size
        print(f"\n[DynMosaic] TAMAM — {elapsed:.1f}s", flush=True)
        print(f"  master.png         : {mw}x{mh}px -> {result.master_path}", flush=True)
        print(f"  master_labeled.png : {result.labeled_path}", flush=True)
        print(f"  debug.json         : {result.debug_path}", flush=True)
        print(f"  Statik bloklar     : {result.n_static_blocks}", flush=True)
        print(f"  Scroll bölümleri   : {result.n_scroll_sections}", flush=True)
        print(f"  Kart değişimleri   : {result.n_card_swap_events}", flush=True)
        print(f"  Cut olayları       : {result.n_cut_events}", flush=True)

        # Kalibrasyon istatistikleri
        _print_signal_stats(result.debug_path)

        # Bölüm listesi
        print(f"\n  Bölümler ({len(result.sections)}):", flush=True)
        for sec in result.sections:
            kind = sec["kind"]
            s = sec["start_frame_idx"]
            e = sec["end_frame_idx"]
            y0 = sec["start_y"]
            y1 = sec["end_y"]
            fc = sec["frame_count"]
            print(f"    [{kind:6s}] kare {s:4d}-{e:4d} (n={fc:3d}) -> canvas y={y0}-{y1}", flush=True)

    except Exception as exc:
        import traceback
        elapsed = perf_counter() - t0
        print(f"[HATA] {exc} ({elapsed:.1f}s)", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
