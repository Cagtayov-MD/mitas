# -*- coding: utf-8 -*-
"""Jenerik BAŞLANGIÇ doğrulama şeridi — montaj-skoru değil, GERÇEK start_frame etrafı.

Dedektörün bulduğu start_frame'in çevresindeki kareleri (footage→ilk-kredi geçişi) SIRAYLA çizer,
böylece "başlangıç doğru mu" göz ile görülür. KREDI_dedigi (en-yoğun kare) montajının aksine.

Koşum:
  python scripts\jenerik_boundary.py --film "KAOS 2024-1349-1-0000-90-1" --seg cikis [--span 8]
  (start_frame otomatik dedektörden hesaplanır; --start ile elle de verilebilir)
"""
import sys, argparse, glob
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np, cv2
from PIL import Image, ImageDraw
from core.pipelines.ocr import jenerik_detector as jd
from core.pipelines.ocr.credit_detector import _cv2_imread

DB = Path(r"E:\MITAS\Database")
OUT = Path(r"E:\MITAS\OCR-worktree\jenerik_eval")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", required=True)
    ap.add_argument("--seg", choices=["giris", "cikis"], required=True)
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--span", type=int, default=8, help="start öncesi/sonrası kaç kare")
    ap.add_argument("--from", dest="frm", type=int, default=None, help="geniş-aralık: ilk kare")
    ap.add_argument("--to", type=int, default=None, help="geniş-aralık: son kare")
    ap.add_argument("--stride", type=int, default=1, help="geniş-aralıkta her N. kare")
    ap.add_argument("--no-clip", action="store_true")
    ap.add_argument("--no-ocr-refine", action="store_true")
    a = ap.parse_args()

    fd = [d for d in DB.iterdir() if a.film.lower() in d.name.lower()]
    if not fd:
        print("film yok:", a.film); return
    fdir = fd[0] / "frames" / a.seg
    paths = sorted(glob.glob(str(fdir / "*.png")))
    if not paths:
        print("kare yok:", fdir); return

    start = a.start
    region = None
    if start is None:
        ctx = None if a.no_clip else jd.load_clip()
        from _jenerik_detect import _build_ocr_read_fn
        ocr_fn = None if a.no_ocr_refine else _build_ocr_read_fn()
        region = jd.detect_from_frames(fdir, prefer=("first" if a.seg == "giris" else "last"),
                                       clip_ctx=ctx, ocr_read_fn=ocr_fn)
        if not region.get("found"):
            print(f"{a.seg}: KOŞU-YOK (kredi bulunamadı). near_miss={region.get('near_miss')}");
            start = 0
        else:
            start = region["start_frame"]
            print(f"{a.seg}: dedektör start_frame={start} ({region['quad_type']}, "
                  f"[{region['start_frame']}-{region['end_frame']}])")

    if a.frm is not None and a.to is not None:
        idxs = list(range(max(0, a.frm), min(len(paths) - 1, a.to) + 1, max(1, a.stride)))
        if start not in idxs and a.frm <= start <= a.to:
            idxs = sorted(set(idxs + [start]))   # start mutlaka görünsün
        suffix = f"_{a.frm}_{a.to}"
    else:
        lo = max(0, start - a.span); hi = min(len(paths) - 1, start + a.span)
        idxs = list(range(lo, hi + 1)); suffix = ""
    cols = len(idxs); tw, th = 150, 110
    canvas = Image.new("RGB", (cols * tw, th + 22), (15, 15, 15))
    d = ImageDraw.Draw(canvas)
    for k, fi in enumerate(idxs):
        img = _cv2_imread(Path(paths[fi]), cv2)
        if img is None: continue
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        canvas.paste(Image.fromarray(rgb).resize((tw, th)), (k * tw, 22))
        is_start = (fi == start)
        col = (0, 255, 0) if is_start else (200, 200, 0)
        d.text((k * tw + 3, 4), f"{'>>START ' if is_start else ''}#{fi}", fill=col)
        if is_start:
            d.rectangle([k * tw, 22, k * tw + tw - 1, th + 21], outline=(0, 255, 0), width=3)
    safe = "".join(c if c.isalnum() else "_" for c in fd[0].name)[:48]
    od = OUT / safe; od.mkdir(parents=True, exist_ok=True)
    outp = od / f"{a.seg}_BASLANGIC{suffix}.png"
    canvas.save(outp)
    print(f"-> {outp}  (yeşil çerçeve = dedektörün dediği BAŞLANGIÇ; solu footage, sağı kredi olmalı)")


if __name__ == "__main__":
    main()
