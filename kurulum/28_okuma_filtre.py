#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OKUMA SETİ İNCELTME: paddle metin-tespitiyle footage/altyazı-only karelerini ele.

Amaç: Sonnet okuma maliyetini düşürmek (film başına ~140 kare → ~40-70).
Kural: karede alt %25 bandının ÜSTÜNDE en az 1 metin kutusu yoksa kare elenir
(altyazılar alt bantta; jenerik kartı/akışı üst bölgede kutu bırakır).
Güvenlik: filtre sonrası set <8 kareye düşecekse o sete filtre UYGULANMAZ
(stilize font / paddle-kör filmler korunur — POROROCA dersi).
Elenen kareler SİLİNMEZ → `_eledi_<set>/` altına taşınır (kanıt geri gelebilir).

Kullanım: venvs/ocr/bin/python kurulum/28_okuma_filtre.py --workers 6
"""
import argparse
import concurrent.futures as cf
import json
import os
import shutil
import sys
import time
from pathlib import Path

KOK = Path("/opt/mitas")
HASAT = KOK / "filmtest" / "kapanis_hasat"
MIN_KALAN = 8
ALT_BANT = 0.75          # y_top bunun üstündeyse (oransal) kutu "altyazı bölgesi"nde

sys.path.insert(0, str(KOK))
os.environ.setdefault("JENERIK_PADDLE_FAST_NO_DOC", "1")

_OCR = None


def _env_yukle():
    p = KOK / "mitas.env"
    if p.exists():
        for s in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = s.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def ocr_al():
    global _OCR
    if _OCR is None:
        from paddleocr import PaddleOCR
        root = Path(os.environ.get("MITAS_JENERIK_PADDLE_MODEL_ROOT")
                    or KOK / "models/ocr/paddle/official_models")
        kw = {"lang": "latin", "use_doc_orientation_classify": False,
              "use_doc_unwarping": False, "use_textline_orientation": False}
        d, r = root / "PP-OCRv5_server_det", root / "latin_PP-OCRv5_mobile_rec"
        if d.exists():
            kw["text_detection_model_name"] = "PP-OCRv5_server_det"
            kw["text_detection_model_dir"] = str(d)
        if r.exists():
            kw["text_recognition_model_name"] = "latin_PP-OCRv5_mobile_rec"
            kw["text_recognition_model_dir"] = str(r)
        _OCR = PaddleOCR(**kw)
    return _OCR


def kare_jenerik_mi(png: Path) -> bool:
    from core.pipelines.ocr.jenerik_frame_pool_detector import (
        extract_paddle_text_boxes, imread_unicode)
    img = imread_unicode(png)
    if img is None:
        return True                      # okunamayan kareyi ELEME (güvenli taraf)
    h = img.shape[0]
    try:
        boxes = extract_paddle_text_boxes(ocr_al().ocr(img))
    except Exception:
        return True
    for (x1, y1, x2, y2), _t, _s in boxes:
        if y1 < ALT_BANT * h:
            return True
    return False


def set_filtrele(sdir: Path) -> tuple[int, int]:
    kareler = sorted(sdir.glob("*.png"))
    if len(kareler) <= MIN_KALAN:
        return len(kareler), 0
    metinli = [i for i, f in enumerate(kareler) if kare_jenerik_mi(f)]
    if len(metinli) < 2:                 # paddle-kör film koruması: filtre iptal
        return len(kareler), 0
    tut = set()
    for i in metinli:                    # ±2 komşuluk marjı (paddle'ın kaçırdığı
        tut.update(range(max(0, i - 2), min(len(kareler), i + 3)))  # stilize kartlar)
    eledi = sdir.parent / f"_eledi_{sdir.name}"
    eledi.mkdir(exist_ok=True)
    at = [f for i, f in enumerate(kareler) if i not in tut]
    for f in at:
        shutil.move(str(f), str(eledi / f.name))
    return len(kareler) - len(at), len(at)


def film_filtrele(d: Path) -> dict:
    r = {"film": d.name}
    try:
        for ad in ("okuma_seti", "okuma_seti_giris"):
            s = d / ad
            if s.is_dir():
                kal, at = set_filtrele(s)
                r[ad] = {"kalan": kal, "elendi": at}
        (d / "filtre.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        r["hata"] = f"{type(e).__name__}: {e}"[:200]
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--films")
    a = ap.parse_args()
    _env_yukle()

    dizinler = sorted(
        d for d in HASAT.iterdir()
        if d.is_dir() and (d / "meta.json").is_file()
        and not (d / "okuma.json").is_file()          # okunmuş filme dokunma
        and not (d / "filtre.json").is_file())        # yeniden-başlatılabilir
    if a.films:
        keys = [s.strip() for s in a.films.split(",")]
        dizinler = [d for d in dizinler if any(k in d.name for k in keys)]

    print(f"{len(dizinler)} film filtrelenecek, workers={a.workers}", flush=True)
    t0, n, toplam_at = time.time(), 0, 0
    with cf.ProcessPoolExecutor(max_workers=a.workers) as ex:
        for r in ex.map(film_filtrele, dizinler, chunksize=4):
            n += 1
            at = sum(v.get("elendi", 0) for v in r.values() if isinstance(v, dict))
            toplam_at += at
            if r.get("hata"):
                print(f"[HATA] {r['film'][:60]} → {r['hata']}", flush=True)
            if n % 50 == 0:
                hiz = n / max(1e-9, time.time() - t0) * 3600
                print(f"  ... {n}/{len(dizinler)} (~{hiz:.0f} film/saat, {toplam_at} kare elendi)",
                      flush=True)
    print(f"BİTTİ: {n} film, {toplam_at} kare elendi, {(time.time()-t0)/60:.1f} dk", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
