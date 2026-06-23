# -*- coding: utf-8 -*-
"""JENERİK (4-tip) başlangıç tespiti runner — venvs/ocr ile koşar (cv2 + opsiyonel CLIP).

Yeni bağımsız dedektör (core.pipelines.ocr.jenerik_detector). Mevcut _credit_detect.py'nin
GERİYE-UYUMLU çıktı şemasını korur (pipeline `type=="scroll"` kontrolü çalışır), üstüne
`quad_type` (bg/text × hareketli/sabit) + frame-sınırları ekler.

Girdi (biri zorunlu):
  --video PATH                          → {opening, closing} (mutlak saniye)
  --frames DIR  [--fps 2.0] [--window-start 0.0] [--prefer first|last]
  --film  FILM_DIR  [--fps 2.0]         → Database/<film> (frames/giris+cikis) → {opening, closing}

  --no-clip                             → CLIP'i devre dışı bırak (sadece sezgisel)

stdout → tek-satır JSON:
  {"opening": {found,type,quad_type,start_sec,end_sec,start_frame,end_frame,
               bg_motion,text_motion,confidence,low_conf,strategy}, "closing": {...}}
Hata → fail-safe: found=false (pipeline sabit pencereye düşer)."""

import os
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # E:\MITAS → core paketi
sys.path.insert(0, str(Path(__file__).resolve().parent))      # scripts/ → _pipe_ocr
sys.stdout.reconfigure(encoding="utf-8")


def _build_ocr_read_fn():
    """OneOCR motoru → ocr_read_fn(bgr)->satırlar (start OCR-geriye inceltme için). Yoksa None (sezgisel kalır)."""
    try:
        import cv2
        from PIL import Image
        from _pipe_ocr import build_engine
        eng, kind, err = build_engine()
        if eng is None:
            return None

        def _read(bgr, _eng=eng):
            res = _eng.recognize_pil(Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))
            out = []
            for ln in (res.get("lines") or []):
                t = (ln.get("text") if isinstance(ln, dict) else str(ln)).strip()
                if t:
                    out.append(t)
            if not out:
                out = [x.strip() for x in (res.get("text") or "").splitlines() if x.strip()]
            return out
        return _read
    except Exception:
        return None


def _no(reason: str) -> dict:
    return {"found": False, "type": "none", "quad_type": "none", "start_sec": 0.0,
            "end_sec": 0.0, "start_frame": None, "end_frame": None, "bg_motion": False,
            "text_motion": False, "confidence": 0.0, "low_conf": True,
            "strategy": "jenerik_detect_v1", "reason": reason}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--video")
    g.add_argument("--frames")
    g.add_argument("--film")
    ap.add_argument("--fps", type=float, default=2.0, help="kare çıkarım fps'i (NATİF fps DEĞİL)")
    ap.add_argument("--window-start", type=float, default=0.0, help="--frames için pencere başlangıç sn (offset)")
    ap.add_argument("--prefer", choices=["first", "last"], default="first", help="--frames için koşu tercihi")
    ap.add_argument("--open-search-min", type=float, default=12.0)
    ap.add_argument("--close-search-min", type=float, default=15.0)
    ap.add_argument("--no-clip", action="store_true")
    ap.add_argument("--debug", action="store_true",
                    help="TANI: per-frame skor (cs/clip/heur/present/nblob/row) + kosu reddetme nedenlerini "
                         "JSON'a ekle (sadece --frames). Davranis DEGISMEZ, mevcut return_debug'i disa verir.")
    ap.add_argument("--no-ocr-refine", action="store_true",
                    help="OCR-geriye başlangıç inceltmeyi kapat (sezgisel geri-çekme kalır)")
    ap.add_argument("--parallel", action="store_true",
                    help="--film/--video: giriş+çıkış 2 thread'de eşzamanlı (CLIP lock'lu, ayrı OCR motoru/cap)")
    a = ap.parse_args(argv)

    try:
        from core.pipelines.ocr import jenerik_detector as jd
        clip_ctx = None if a.no_clip else jd.load_clip()
        # OCR-geriye inceltme: asıl TOO_LATE fix. Default AÇIK; --no-ocr-refine veya MITAS_JENERIK_OCR_REFINE=0 ile kapanır.
        use_ocr = not a.no_ocr_refine and os.environ.get("MITAS_JENERIK_OCR_REFINE", "1") != "0"
        ocr_fn = _build_ocr_read_fn() if use_ocr else None

        if a.video:
            res = jd.detect_from_video(a.video, fps=a.fps,
                                       open_search_min=a.open_search_min,
                                       close_search_min=a.close_search_min,
                                       clip_ctx=clip_ctx, ocr_read_fn=ocr_fn,
                                       parallel=a.parallel,
                                       ocr_factory=(_build_ocr_read_fn if (use_ocr and a.parallel) else None))
        elif a.film:
            res = jd.detect_film_frames(
                a.film, fps=a.fps, clip_ctx=clip_ctx, ocr_read_fn=ocr_fn,
                parallel=a.parallel,
                ocr_factory=(_build_ocr_read_fn if (use_ocr and a.parallel) else None))
        else:  # --frames (tek klasör → istenen tarafa koy)
            if a.debug:
                region, _sigs, _runs = jd.detect_from_frames(
                    a.frames, fps=a.fps, window_start_sec=a.window_start,
                    prefer=a.prefer, clip_ctx=clip_ctx, ocr_read_fn=ocr_fn, return_debug=True)
                region["_debug"] = {
                    "n_frames": len(_sigs),
                    "n_present": sum(1 for s in _sigs if getattr(s, "present", False)),
                    "present_thr": 0.50,
                    "frames": [{"i": getattr(s, "idx", i),
                                "cs": round(float(getattr(s, "credit_score", 0.0)), 3),
                                "clip": (round(float(s.clip), 3) if getattr(s, "clip", None) is not None else None),
                                "heur": round(float(getattr(s, "heur", 0.0)), 3),
                                "present": bool(getattr(s, "present", False)),
                                "nblob": int(getattr(s, "n_blobs", 0)),
                                "row": round(float(getattr(s, "row_struct", 0.0)), 3)}
                               for i, s in enumerate(_sigs)],
                    "runs": [{k: r.get(k) for k in ("start_frame", "end_frame", "n_frames", "valid",
                              "invalid_reason", "confidence", "med_clip", "min_clip",
                              "med_row_struct", "med_n_blobs", "quad_type")} for r in _runs],
                }
            else:
                region = jd.detect_from_frames(a.frames, fps=a.fps,
                                               window_start_sec=a.window_start,
                                               prefer=a.prefer, clip_ctx=clip_ctx, ocr_read_fn=ocr_fn)
            if a.prefer == "last":
                res = {"opening": _no("frames_single_dir"), "closing": region}
            else:
                res = {"opening": region, "closing": _no("frames_single_dir")}
        res["clip_used"] = clip_ctx is not None
        res["ocr_refine_used"] = ocr_fn is not None
    except Exception as exc:  # noqa: BLE001 — asla çökme; pipeline fallback'e düşsün
        no = _no(f"{type(exc).__name__}: {exc}")
        res = {"opening": dict(no), "closing": dict(no), "clip_used": False}

    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
