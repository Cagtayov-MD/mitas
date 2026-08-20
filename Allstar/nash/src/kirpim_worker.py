#!/usr/bin/env python3
"""Secilmis metin izlerini ikinci Paddle modeli ve Tesseract ile yeniden oku."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path


def _kes(im, box, padding: int = 2):
    h, w = im.shape[:2]
    x1, y1, x2, y2 = (float(v) for v in box)
    ix1 = max(0, int(x1 * w) - padding)
    iy1 = max(0, int(y1 * h) - padding)
    ix2 = min(w, int(x2 * w + 0.999) + padding)
    iy2 = min(h, int(y2 * h + 0.999) + padding)
    return im[iy1:iy2, ix1:ix2]


def _keskinlestir(kirpim):
    import cv2
    buyuk = cv2.resize(kirpim, (kirpim.shape[1] * 2, kirpim.shape[0] * 2),
                       interpolation=cv2.INTER_LANCZOS4)
    bulanik = cv2.GaussianBlur(buyuk, (5, 5), 0)
    return cv2.addWeighted(buyuk, 2.0, bulanik, -1.0, 0)


def _fold(metin: str) -> str:
    s = unicodedata.normalize("NFKD", (metin or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)
                   and c.isalnum())


def _tesseract_tek(png: bytes, dil: str, psm: int) -> tuple[str, str | None]:
    try:
        sonuc = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", dil, "--psm", str(psm)],
            input=png, capture_output=True, shell=False, timeout=15)
    except Exception as exc:
        return "", f"{type(exc).__name__}: {exc}"[:200]
    if sonuc.returncode:
        return "", sonuc.stderr.decode("utf-8", "replace")[-200:]
    return " ".join(sonuc.stdout.decode("utf-8", "replace").split()), None


def _tesseract(kirpim, dil: str, psm: int) -> tuple[str, str | None]:
    import cv2
    ok, png = cv2.imencode(".png", _keskinlestir(kirpim))
    if not ok:
        return "", "png_encode"
    metin, hata = _tesseract_tek(png.tobytes(), dil, psm)
    # Dar tek satırlarda psm=7 bazen tamamen boş döner; psm=13 aynı görselde
    # ÜMİT YESİN/EŞREF KOLÇAK gibi temiz sonucu verir. Yalnız boşlukta denenir.
    if not metin and psm != 13:
        yedek, yedek_hata = _tesseract_tek(png.tobytes(), dil, 13)
        if yedek:
            return yedek, None
        hata = hata or yedek_hata
    return metin, hata


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--device", default="gpu:0")
    ap.add_argument("--model", default="PP-OCRv6_medium_rec")
    ap.add_argument("--model-dir")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--padding", type=int, default=2)
    ap.add_argument("--tesseract", action="store_true")
    ap.add_argument("--tesseract-lang", default="tur")
    ap.add_argument("--tesseract-psm", type=int, default=7)
    ap.add_argument("--tesseract-tavan", type=int, default=120)
    a = ap.parse_args(argv)
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    try:
        import cv2
        import paddle
        from paddleocr import TextRecognition
        istekler = json.loads(Path(a.input).read_text(encoding="utf-8"))
        if not isinstance(istekler, list):
            raise ValueError("input istek listesi degil")
        model = TextRecognition(
            model_name=a.model, model_dir=a.model_dir,
            device=a.device, enable_hpi=False)
    except Exception as exc:
        print(f"kirpim modeli kurulamadi: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2

    t0 = time.monotonic()
    kirpimlar, kayitlar = [], []
    onbellek = {}
    for istek in istekler:
        try:
            yol = str(istek["path"])
            if yol not in onbellek:
                onbellek[yol] = cv2.imread(yol, cv2.IMREAD_COLOR)
            im = onbellek[yol]
            if im is None:
                raise ValueError("OpenCV kareyi acamadi")
            kirpim = _kes(im, istek["box"], max(0, a.padding))
            if not kirpim.size:
                raise ValueError("bos kirpim")
            kirpimlar.append(kirpim)
            kayitlar.append({"id": istek["id"],
                             "primary_text": str(istek.get("primary_text", "")),
                             "tesseract_eligible": bool(
                                 istek.get("tesseract_eligible", True))})
        except Exception as exc:
            kayitlar.append({"id": istek.get("id"),
                             "error": f"{type(exc).__name__}: {exc}"[:200]})

    # Hatali istekler kayitlar'da durur; model listesinde yalniz kirpim vardir.
    basarili = [x for x in kayitlar if "error" not in x]
    try:
        normal = list(model.predict(kirpimlar, batch_size=max(1, a.batch)))
        keskinler = [_keskinlestir(x) for x in kirpimlar]
        keskin = list(model.predict(keskinler, batch_size=max(1, a.batch)))
        for kayit, nsonuc, ksonuc in zip(basarili, normal, keskin):
            nr = nsonuc.json.get("res", {})
            kr = ksonuc.json.get("res", {})
            kayit.update({
                "secondary_text": str(nr.get("rec_text", "")),
                "secondary_score": float(nr.get("rec_score", 0.0)),
                "secondary_sharp_text": str(kr.get("rec_text", "")),
                "secondary_sharp_score": float(kr.get("rec_score", 0.0)),
            })
    except Exception as exc:
        print(f"kirpim tanima: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    tess_var = bool(a.tesseract and shutil.which("tesseract"))
    tess_n = 0
    tess_hata_n = 0
    if tess_var and a.tesseract_tavan > 0:
        # Once Paddle tanıyıcılarının ayrıştığı izler, sonra kalanlar. Böylece
        # tavanlı uzun scroll'da hakem en belirsiz kırpımlara gider.
        sirali = sorted((
            (kayit, kirpim) for kayit, kirpim in zip(basarili, kirpimlar)
            if kayit.get("tesseract_eligible", True)), key=lambda x: (
            _fold(x[0].get("primary_text", ""))
            == _fold(x[0].get("secondary_text", "")),
            -abs(len(_fold(x[0].get("primary_text", "")))
                 - len(_fold(x[0].get("secondary_text", ""))))))
        for kayit, kirpim in sirali[:max(0, a.tesseract_tavan)]:
            metin, hata = _tesseract(kirpim, a.tesseract_lang, a.tesseract_psm)
            kayit["tesseract_text"] = metin
            if hata:
                kayit["tesseract_error"] = hata
                tess_hata_n += 1
            tess_n += 1

    peak = None
    try:
        peak = round(paddle.device.cuda.max_memory_reserved() / (1024 * 1024), 1)
    except Exception:
        pass
    belge = {
        "meta": {"model": a.model, "device": a.device,
                 "duration_s": round(time.monotonic() - t0, 3),
                 "request_n": len(istekler), "success_n": len(basarili),
                 "tesseract_available": tess_var, "tesseract_n": tess_n,
                 "tesseract_error_n": tess_hata_n, "peak_vram_mb": peak},
        "results": kayitlar,
    }
    Path(a.output).write_text(json.dumps(belge, ensure_ascii=False),
                              encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
