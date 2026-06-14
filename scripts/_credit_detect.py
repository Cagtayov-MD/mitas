# -*- coding: utf-8 -*-
"""Jenerik-sınır tespiti runner (venvs/ocr ile koşar — cv2 gerektirir).

mitas_pipeline (venvs/asr, cv2 YOK) bunu subprocess ile çağırır. OpusCreditDetector
videoyu tarayıp GİRİŞ + ÇIKIŞ jeneriğinin GERÇEK başlangıç/bitiş saniyelerini bulur;
stdout'a tek-satır JSON basar:
  {"opening": {found, type, start_sec, end_sec, scroll_speed, confidence, strategy},
   "closing": {found, type, start_sec, end_sec, scroll_speed, confidence, strategy}}
Herhangi bir hata → {"opening":{"found":false,...}, "closing":{"found":false,...}}
(pipeline fail-safe sabit pencereye düşer)."""
import sys, json, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # E:\MITAS → core paketi
sys.stdout.reconfigure(encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--open-search-min", type=float, default=12.0,
                    help="giriş: ilk N dakikayı tara (default 12)")
    ap.add_argument("--close-search-min", type=float, default=None,
                    help="çıkış: son N dakikayı tara (default 15)")
    a = ap.parse_args(argv)
    try:
        from core.pipelines.ocr.credit_detector import OpusCreditDetector
        res = OpusCreditDetector().detect_both(
            a.video,
            open_search_min=a.open_search_min,
            close_search_min=a.close_search_min,
        )
    except Exception as exc:  # noqa: BLE001 — asla çökme; pipeline fallback'e düşsün
        no = {"found": False, "type": "none", "start_sec": 0.0, "end_sec": 0.0,
              "scroll_speed": 0.0, "confidence": 0.0, "strategy": "opus_credit_detector",
              "error": f"{type(exc).__name__}: {exc}"}
        res = {"opening": no, "closing": no}
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
