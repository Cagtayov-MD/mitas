"""SlitScan Panorama test koşucusu.

Kullanım:
    python run_slitscan_test.py
    python run_slitscan_test.py --cases 1980_son_metro_end_credits__closing 2000_x_men_end_credits__closing
    python run_slitscan_test.py --max-frames 200 --no-ocr

Çıktı: outputs/_slitscan_test_<timestamp>/<film>__<seg>/
"""

from __future__ import annotations

import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from time import perf_counter

# --- Proje kökünü sys.path'e ekle ---
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

FRAMES_BASE = PROJECT_ROOT / "outputs" / "_hakim_shadow_20films_20260529_1507" / "items"

DEFAULT_CASES = [
    "1980_son_metro_end_credits__closing",
    "1980_son_metro_end_credits__opening",
    "2000_x_men_end_credits__closing",
    "1989_kukla_adam_end_credits__closing",
]


def _find_frames_dir(film_seg: str) -> Path | None:
    """film__seg formatından kare dizinini bul."""
    if "__" not in film_seg:
        print(f"[HATA] Geçersiz format: {film_seg!r} (beklenen: <film>__<seg>)", file=sys.stderr)
        return None

    film, seg = film_seg.split("__", 1)

    # Olası yol 1: items/<film>_end_credits/frames/<seg>/
    candidate1 = FRAMES_BASE / f"{film}_end_credits" / "frames" / seg
    if candidate1.exists():
        return candidate1

    # Olası yol 2: items/<film>/frames/<seg>/
    candidate2 = FRAMES_BASE / film / "frames" / seg
    if candidate2.exists():
        return candidate2

    # Olası yol 3: items/<film>_end_credits/frames/ (seg=closing, direct)
    candidate3 = FRAMES_BASE / f"{film}_end_credits" / "frames"
    if candidate3.exists() and seg == "closing":
        frames_in = sorted(candidate3.glob("frame_*.png"), key=lambda p: p.stem)
        if frames_in:
            return candidate3

    print(f"[HATA] Kare dizini bulunamadı: {film_seg}", file=sys.stderr)
    print(f"  Denendi: {candidate1}", file=sys.stderr)
    print(f"  Denendi: {candidate2}", file=sys.stderr)
    print(f"  Denendi: {candidate3}", file=sys.stderr)
    return None


def _load_frames(frames_dir: Path, max_frames: int | None = None) -> list[Path]:
    """Kare dosyalarını sıralı listele."""
    frames = sorted(frames_dir.glob("frame_*.png"), key=lambda p: int(p.stem.split("_")[-1]))
    if max_frames is not None:
        frames = frames[:max_frames]
    return frames


def _dummy_paddle_engine() -> object:
    """--no-ocr modunda sahte engine (OCR yok, sadece görsel test)."""
    class _DummyEngine:
        def recognize(self, image_path, *, strategy, timestamp_seconds=None):
            return []
    return _DummyEngine()


def main() -> None:
    parser = argparse.ArgumentParser(description="SlitScan Panorama test koşucusu")
    parser.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="<film>__<seg> formatında test case listesi. Boş bırakılırsa varsayılan 4 case çalışır.",
    )
    parser.add_argument(
        "--ocr-stride",
        type=int,
        default=8,
        help="Text-gate seyrek OCR stride (varsayılan: 8)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=6.0,
        help="Kaynak FPS (varsayılan: 6.0)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Her case için maksimum kare sayısı (hızlı test için kısalt)",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="OCR'ı atla — sadece görsel slit-scan pipeline'ını test et",
    )
    args = parser.parse_args()

    cases = args.cases if args.cases else DEFAULT_CASES

    # --- Çıktı dizini ---
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_base = PROJECT_ROOT / "outputs" / f"_slitscan_test_{ts}"
    output_base.mkdir(parents=True, exist_ok=True)
    print(f"[SlitScan] Çıktı dizini: {output_base}")

    # --- PaddleOCR engine'i başlat (tek seferlik) ---
    if args.no_ocr:
        print("[SlitScan] --no-ocr modu: OCR atlanıyor.")
        paddle_engine = _dummy_paddle_engine()
    else:
        print("[SlitScan] PaddleOCR engine başlatılıyor...")
        t0 = perf_counter()
        try:
            from core.pipelines.ocr.credit_experiment import PaddleOcrEngine
            paddle_engine = PaddleOcrEngine()
            print(f"[SlitScan] PaddleOCR hazır ({perf_counter()-t0:.1f}s). Device: {paddle_engine.device}")
        except Exception as exc:
            print(f"[HATA] PaddleOCR başlatılamadı: {exc}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

    # --- SlitScan modülünü yükle ---
    from core.pipelines.ocr.slitscan.slitscan_panorama import run_slitscan_panorama

    # --- Her case çalıştır ---
    results_summary: list[dict] = []

    for case in cases:
        print(f"\n{'='*60}")
        print(f"[SlitScan] Case: {case}")
        frames_dir = _find_frames_dir(case)
        if frames_dir is None:
            results_summary.append({"case": case, "status": "HATA", "reason": "frames_dir_not_found"})
            continue

        all_frames = _load_frames(frames_dir)
        if not all_frames:
            print(f"  [HATA] Kare bulunamadı: {frames_dir}", file=sys.stderr)
            results_summary.append({"case": case, "status": "HATA", "reason": "no_frames"})
            continue

        frames = all_frames if args.max_frames is None else all_frames[:args.max_frames]
        print(f"  Kare sayısı: {len(frames)} (toplam: {len(all_frames)})")
        print(f"  Kare dizini: {frames_dir}")

        case_out = output_base / case
        case_out.mkdir(parents=True, exist_ok=True)

        t_case = perf_counter()
        try:
            result = run_slitscan_panorama(
                frames,
                output_dir=case_out,
                paddle_engine=paddle_engine,
                source_fps=args.fps,
                ocr_stride=args.ocr_stride,
            )
            elapsed = perf_counter() - t_case

            line_count = len(result.text_lines)
            section_count = len(result.sections)
            pano_path = result.panorama_path

            # Panorama boyutu
            import cv2
            import numpy as np
            buf = np.fromfile(str(pano_path), np.uint8)
            pano_img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            pano_size = f"{pano_img.shape[1]}x{pano_img.shape[0]}" if pano_img is not None else "?"

            print(f"  TAMAM — {elapsed:.1f}s | satır: {line_count} | bölüm: {section_count} | panorama: {pano_size}")
            print(f"  Panorama: {pano_path}")
            if result.text_lines:
                print(f"  İlk 5 satır:")
                for ln in result.text_lines[:5]:
                    print(f"    {ln.get('text','')!r}")

            results_summary.append({
                "case": case,
                "status": "OK",
                "line_count": line_count,
                "section_count": section_count,
                "panorama_size": pano_size,
                "runtime_sec": round(elapsed, 2),
                "panorama_path": str(pano_path),
            })

        except Exception as exc:
            import traceback
            elapsed = perf_counter() - t_case
            print(f"  [HATA] {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            results_summary.append({
                "case": case,
                "status": "HATA",
                "error": str(exc),
                "runtime_sec": round(elapsed, 2),
            })

    # --- Özet ---
    print(f"\n{'='*60}")
    print("[SlitScan] ÖZET:")
    for r in results_summary:
        status = r["status"]
        case = r["case"]
        if status == "OK":
            print(f"  {status:6s} | {case} | satır={r['line_count']} bölüm={r['section_count']} boyut={r['panorama_size']} {r['runtime_sec']}s")
        else:
            print(f"  {status:6s} | {case} | {r.get('reason') or r.get('error','')}")

    # Özet JSON
    summary_path = output_base / "test_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump({"cases": results_summary, "output_base": str(output_base)}, fh, ensure_ascii=False, indent=2)
    print(f"\n[SlitScan] Özet: {summary_path}")
    print(f"[SlitScan] Çıktı: {output_base}")


if __name__ == "__main__":
    main()
