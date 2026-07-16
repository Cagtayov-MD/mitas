# -*- coding: utf-8 -*-
"""master_montage.py — TÜM master'ları KKF görsel-denetim (Aşama-2, Aşama-1 mantığı).
Her film satırı: [ÜST, %25, %50, %75, ALT] kesit + boyut/blok bilgisi. Collapse/truncation/footage/overlap görülür.
MITAS_MSEG=cikis|giris (hangi master). PER film/sayfa.
Kullanım: python master_montage.py <out_prefix> [@idfile | filmids...]
"""
import sys, os, glob, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

RUN = os.environ["MITAS_RUN_ROOT"]; DB = Path(RUN) / "Database"
SEG = os.environ.get("MITAS_MSEG", "cikis")
FN = "reading_master_runaware.png" if SEG == "cikis" else "giris_reading_master_runaware.png"
CW, CH, LBL, PER = 230, 300, 200, 7
try:
    F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    FS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
except Exception:
    F = FS = ImageFont.load_default()

def crops(im):
    w, h = im.size
    band = int(w * CH / CW)  # kesit yüksekliği (oranı koru)
    out = []
    for name, frac in [("ÜST", 0.0), ("%25", 0.25), ("%50", 0.5), ("%75", 0.72), ("ALT", 0.93)]:
        yy = min(max(0, int(h * frac)), max(0, h - band))
        c = im.crop((0, yy, w, min(h, yy + band))); c.thumbnail((CW - 4, CH - 4))
        out.append((name, c))
    return out

def make(fids, out):
    rows = [f for f in fids if (DB / f).is_dir()]
    W = LBL + 5 * CW; H = len(rows) * (CH + 8) + 4
    canvas = Image.new("RGB", (W, H), (14, 14, 14)); d = ImageDraw.Draw(canvas)
    y = 4
    for fid in rows:
        p = DB / fid / FN
        short = fid.split("-1-0000")[0].split("_")[-1][:20]
        cpool = len(list((DB / fid / "frames" / f"{SEG}_jenerik").glob("*.png")))
        d.text((5, y + CH//2 - 24), short, font=F, fill=(255, 235, 120))
        if not p.exists():
            d.text((5, y + CH//2), f"{SEG}: YOK\npool={cpool}", font=FS, fill=(255, 140, 140)); y += CH + 8; continue
        im = Image.open(p).convert("RGB"); w, h = im.size
        d.text((5, y + CH//2 - 2), f"{w}x{h}", font=FS, fill=(140, 200, 255))
        d.text((5, y + CH//2 + 16), f"pool={cpool}", font=FS, fill=(150, 150, 160))
        flag = ""
        if cpool > 20 and h < 200: flag = "ÇÖKMÜŞ!"
        elif h < 400: flag = "kısa?"
        if flag: d.text((5, y + CH//2 + 36), flag, font=F, fill=(255, 90, 90))
        x = LBL
        for name, c in crops(im):
            cv = Image.new("RGB", (CW, CH), (24, 24, 24)); cv.paste(c, ((CW - c.width)//2, (CH - c.height)//2))
            canvas.paste(cv, (x, y)); d.text((x + 2, y + 2), name, font=FS, fill=(120, 255, 120))
            x += CW
        y += CH + 8
    canvas.save(out); print(f"{out} ({len(rows)} film)")

if __name__ == "__main__":
    prefix = sys.argv[1]; ids = sys.argv[2:]
    if ids and ids[0].startswith("@"):
        ids = [l.strip() for l in open(ids[0][1:], encoding="utf-8") if l.strip()]
    if not ids:
        # SEG master'ı OLAN tüm filmler
        ids = []
        for cd in sorted(glob.glob(f"{RUN}/Database/*")):
            if (Path(cd) / FN).exists() or (Path(cd) / "frames" / f"{SEG}_jenerik").is_dir():
                ids.append(os.path.basename(cd))
    for gi in range(0, len(ids), PER):
        make(ids[gi:gi+PER], f"{prefix}_{gi//PER:02d}.png")
