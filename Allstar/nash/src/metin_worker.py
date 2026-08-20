#!/usr/bin/env python3
"""Paddle full-OCR worker; normalize kutu, metin ve skor yazar.

Torch/DeepSeek ile ayni venv veya surecte calismaz. Worker tamamlanip GPU
bellek tamamen serbest kaldiktan sonra gerekiyorsa DeepSeek yuklenir.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def kirpim_keskinlestir(kirpim):
    """Kutu kırpımını 2× lanczos + unsharp(5x5, amount 1.0) ile büyütür.

    Çiçek Taksi 2026-08-19 ölçümü: 384×288 kaynakta 10-12px gliflerde
    boşluk/diyakritik kayıplarını düzeltir (ÜMİTYESIN→ÜMİT YESİN), zarar
    ölçülmedi. Kare-seviyesi ölçekleme dedektör geometrisini bozduğu için
    yalnız kırpım seviyesinde kullanılır.
    """
    import cv2
    buyuk = cv2.resize(kirpim, (kirpim.shape[1] * 2, kirpim.shape[0] * 2),
                       interpolation=cv2.INTER_LANCZOS4)
    bulanik = cv2.GaussianBlur(buyuk, (5, 5), 0)
    return cv2.addWeighted(buyuk, 2.0, bulanik, -1.0, 0)


def kirpim_olculeri(kirpim):
    """Izleme/temsilci secimi icin ucuz, modele bagimsiz kirpim olculeri."""
    import cv2
    if kirpim is None or not getattr(kirpim, "size", 0):
        return {"crop_dhash": None, "sharpness": 0.0, "contrast": 0.0}
    gri = (cv2.cvtColor(kirpim, cv2.COLOR_BGR2GRAY)
           if len(kirpim.shape) == 3 else kirpim)
    kucuk = cv2.resize(gri, (17, 8), interpolation=cv2.INTER_AREA)
    bits = (kucuk[:, 1:] > kucuk[:, :-1]).reshape(-1)
    dhash = 0
    for bit in bits:
        dhash = (dhash << 1) | int(bit)
    keskinlik = float(cv2.Laplacian(gri, cv2.CV_64F).var())
    return {"crop_dhash": dhash,
            "sharpness": round(keskinlik, 3),
            "contrast": round(float(gri.std()), 3)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--device", default="gpu")
    ap.add_argument("--model", default="PP-OCRv6_medium_det")
    ap.add_argument("--model-dir")
    ap.add_argument("--rec-model", default="latin_PP-OCRv5_mobile_rec")
    ap.add_argument("--rec-model-dir")
    ap.add_argument("--rec-batch", type=int, default=8)
    ap.add_argument("--det-thresh", type=float, default=0.2)
    ap.add_argument("--box-thresh", type=float, default=0.45)
    ap.add_argument("--unclip-ratio", type=float, default=1.4)
    ap.add_argument("--kirpim-keskinlestir", action="store_true",
                    help="kutu kırpımını 2x lanczos+unsharp ile yeniden oku")
    ap.add_argument("--no-mkldnn", action="store_true")
    a = ap.parse_args(argv)
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    try:
        import cv2
        import paddle
        from paddleocr import PaddleOCR
        yollar = json.loads(Path(a.input).read_text(encoding="utf-8"))
        if not isinstance(yollar, list):
            raise ValueError("input bir yol listesi degil")
        if hasattr(paddle.device.cuda, "reset_max_memory_reserved"):
            paddle.device.cuda.reset_max_memory_reserved()
        model = PaddleOCR(
            text_detection_model_name=a.model,
            text_detection_model_dir=a.model_dir,
            text_recognition_model_name=a.rec_model,
            text_recognition_model_dir=a.rec_model_dir,
            text_recognition_batch_size=max(1, a.rec_batch),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_det_thresh=a.det_thresh,
            text_det_box_thresh=a.box_thresh,
            text_det_unclip_ratio=a.unclip_ratio,
            text_rec_score_thresh=0.0,
            device=a.device,
            enable_hpi=False,
            precision="fp32",
            enable_mkldnn=not a.no_mkldnn)
    except Exception as exc:
        print(f"detector kurulamadi: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    t0 = time.monotonic()
    kareler = {}
    for ham_yol in yollar:
        p = Path(str(ham_yol))
        try:
            # Kareyi bir kez ac: eski yol ana surecte cv2 ile, Paddle icinde
            # ikinci kez decode ediyor ve tum tam-cozunurluk grileri RAM'de
            # tutuyordu. Ayni BGR ndarray hem OCR'a hem 17x16 dHash'e yeter.
            im = cv2.imread(str(p), cv2.IMREAD_COLOR)
            if im is None:
                kareler[p.name] = {
                    "boxes": [], "error_stage": "decode",
                    "error": "OpenCV kareyi acamadi",
                }
                continue
            yukseklik, genislik = im.shape[:2]
            gri = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
            kucuk = cv2.resize(gri, (17, 16), interpolation=cv2.INTER_AREA)
            bits = (kucuk[:, 1:] > kucuk[:, :-1]).reshape(-1)
            dhash = 0
            for bit in bits:
                dhash = (dhash << 1) | int(bit)

            sonuc = list(model.predict(im))
            ham = sonuc[0].json if sonuc and hasattr(sonuc[0], "json") else {}
            res = ham.get("res", ham) if isinstance(ham, dict) else {}
            polys = res.get("dt_polys") if isinstance(res, dict) else None
            kutular = []
            for poly in ([] if polys is None else polys):
                xs = [float(nokta[0]) for nokta in poly]
                ys = [float(nokta[1]) for nokta in poly]
                if not xs or not ys or genislik <= 0 or yukseklik <= 0:
                    continue
                x1, x2 = max(0.0, min(xs)), min(float(genislik), max(xs))
                y1, y2 = max(0.0, min(ys)), min(float(yukseklik), max(ys))
                if x1 < x2 and y1 < y2:
                    kutular.append([x1 / genislik, y1 / yukseklik,
                                    x2 / genislik, y2 / yukseklik])
            metinler = res.get("rec_texts") or []
            skorlar = res.get("rec_scores") or []
            rec_kutular = res.get("rec_boxes") or []
            satirlar = []
            for metin, skor, kutu in zip(metinler, skorlar, rec_kutular):
                if len(kutu) != 4:
                    continue
                x1, y1, x2, y2 = (float(x) for x in kutu)
                if not (0 <= x1 < x2 <= genislik and 0 <= y1 < y2 <= yukseklik):
                    continue
                ix1, iy1 = max(0, int(x1)), max(0, int(y1))
                ix2, iy2 = min(genislik, int(x2 + 0.999)), min(
                    yukseklik, int(y2 + 0.999))
                olculer = kirpim_olculeri(im[iy1:iy2, ix1:ix2])
                satirlar.append({
                    "text": str(metin), "score": float(skor),
                    "box": [x1 / genislik, y1 / yukseklik,
                            x2 / genislik, y2 / yukseklik], **olculer,
                })
            kareler[p.name] = {"boxes": kutular, "lines": satirlar,
                               "width": genislik, "height": yukseklik,
                               "dhash": dhash,
                               "luma_mean": round(float(gri.mean()), 3)}
        except Exception as exc:  # tek bozuk kare tum havuzu iptal etmez
            kareler[p.name] = {"boxes": [],
                               "error_stage": "predict",
                               "error": f"{type(exc).__name__}: {exc}"[:300]}
    peak = None
    try:
        peak = round(paddle.device.cuda.max_memory_reserved() / (1024 * 1024), 1)
    except Exception:
        pass
    belge = {"meta": {"model": a.model, "recognition_model": a.rec_model,
                       "device": a.device, "full_ocr": True,
                       "peak_vram_mb": peak,
                       "duration_s": round(time.monotonic() - t0, 3)},
             "frames": kareler}
    Path(a.output).write_text(json.dumps(belge, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
