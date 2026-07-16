# -*- coding: utf-8 -*-
"""fine_strip.py — tek film, verilen aralıkta N kare eşit-örnekle tek görsele diz (ince teşhis).
Kullanım: python fine_strip.py <out.png> <film_id_parça> <start> <end> [cols]
"""
import sys, os, glob
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

RUN = os.environ["MITAS_RUN_ROOT"]
out, idpart, start, end = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
cols = int(sys.argv[5]) if len(sys.argv) > 5 else 10
seg = os.environ.get("MITAS_MSEG", "cikis")

cd = [d for d in glob.glob(f"{RUN}/Database/*") if idpart in os.path.basename(d)]
assert cd, f"film bulunamadı: {idpart}"
full = sorted(Path(cd[0], "frames", seg).glob("*.png"))
try:
    F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
except Exception:
    F = ImageFont.load_default()
CW, CH = 260, 150
idxs = [int(round(start + (end - start) * k / (cols - 1))) for k in range(cols)]
idxs = [i for i in idxs if 0 <= i < len(full)]
rows = (len(idxs) + cols - 1) // cols
W = cols * CW; H = rows * (CH + 20)
canvas = Image.new("RGB", (W, H), (12, 12, 12)); d = ImageDraw.Draw(canvas)
for k, i in enumerate(idxs):
    r, c = divmod(k, cols)
    x, y = c * CW, r * (CH + 20)
    try:
        im = Image.open(full[i]).convert("RGB"); im.thumbnail((CW-4, CH))
    except Exception:
        im = Image.new("RGB", (CW-4, CH), (40,40,40))
    canvas.paste(im, (x + (CW-im.width)//2, y))
    d.text((x+3, y+CH+2), f"#{i}", font=F, fill=(120,255,120))
canvas.save(out)
print(f"{out} — {os.path.basename(cd[0])[-30:]} [{start}..{end}] {len(idxs)} kare")
