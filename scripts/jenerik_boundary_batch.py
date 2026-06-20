# -*- coding: utf-8 -*-
"""Toplu BAŞLANGIÇ-şeridi: bulunan her bölgenin start_frame'i etrafını (footage→ilk-kredi geçişi) çizer.
Montaj DEĞİL — start ÖNCESİ footage mı, start KARESİ ilk-kredi mi diye GÖZLE denetlemek için.
CSV'den (jenerik_verify_full60.csv) region=[a-b] okur, re-detect YOK."""
import sys, csv, re, glob
from pathlib import Path
sys.path.insert(0, r"E:\MITAS")
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np, cv2
from PIL import Image, ImageDraw
from core.pipelines.ocr.credit_detector import _cv2_imread

DB = Path(r"E:\MITAS\Database")
OUT = Path(r"E:\MITAS\OCR-worktree\jenerik_starts")
SPAN = 7


def render(film, seg, start, end):
    fd = [x for x in DB.iterdir() if x.name == film]
    if not fd:
        return None
    fdir = fd[0] / "frames" / seg
    paths = sorted(fdir.glob("*.png"))
    if not paths:
        return None
    lo = max(0, start - SPAN); hi = min(len(paths) - 1, start + SPAN)
    idxs = list(range(lo, hi + 1))
    tw, th = 150, 110
    canvas = Image.new("RGB", (len(idxs) * tw, th + 22), (15, 15, 15))
    d = ImageDraw.Draw(canvas)
    for k, fi in enumerate(idxs):
        img = _cv2_imread(paths[fi], cv2)
        if img is None:
            continue
        canvas.paste(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).resize((tw, th)), (k * tw, 22))
        isst = (fi == start)
        d.text((k * tw + 3, 4), f"{'>>START ' if isst else ''}#{fi}", fill=((0, 255, 0) if isst else (200, 200, 0)))
        if isst:
            d.rectangle([k * tw, 22, k * tw + tw - 1, th + 21], outline=(0, 255, 0), width=3)
    safe = "".join(c if c.isalnum() else "_" for c in film)[:46]
    OUT.mkdir(parents=True, exist_ok=True)
    outp = OUT / f"{safe}__{seg}__start{start}.png"
    canvas.save(outp)
    return outp


def main():
    csvp = r"E:\MITAS\OCR-worktree\jenerik_verify_full60.csv"
    rows = list(csv.DictReader(open(csvp, encoding="utf-8-sig")))
    n = 0
    manifest = []
    for r in rows:
        m = re.match(r"\[(\d+)-(\d+)\]", r["region"])
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        p = render(r["film"], r["seg"], a, b)
        if p:
            n += 1
            manifest.append({"film": r["film"], "seg": r["seg"], "start": a, "end": b,
                             "quad": r.get("quad", ""), "png": str(p)})
            print(f"  {n:3d} {r['film'][:34]:34s} {r['seg']:5s} start={a}", flush=True)
    import json
    json.dump(manifest, open(OUT / "_manifest.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n-> {n} başlangıç-şeridi: {OUT}")


if __name__ == "__main__":
    main()
