# -*- coding: utf-8 -*-
"""montage_audit.py — KKF görsel re-audit. Film başına bir şerit:
[start-6, start-2, HAVUZ_BAŞI, +havuz%25, +havuz%60, HAVUZ_SONU]
Boş havuz → cikis son 6 karesi (THE END / footage teyidi).
Her şeridin solunda film adı + havuz bilgisi; her karenin altında index.
Kullanım: python montage_audit.py <out_prefix> <film_id_1> <film_id_2> ...  (id yoksa: hepsi)
"""
import sys, os, glob, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

RUN = os.environ["MITAS_RUN_ROOT"]
DB = Path(RUN) / "Database"
CW = 250          # tek kare genişliği
LBL = 340         # sol etiket şeridi
ROWH = 150        # satır yüksekliği (kare)
PAD = 4
PER = 7          # montaj başına film

try:
    F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
except Exception:
    F = FB = ImageFont.load_default()

def idx_of(name, allframes):
    try:
        return [p.name for p in allframes].index(name)
    except ValueError:
        return None

def load_small(p, w=CW, h=ROWH):
    try:
        im = Image.open(p).convert("RGB")
    except Exception:
        im = Image.new("RGB", (w, h), (40, 40, 40))
    im.thumbnail((w, h))
    canvas = Image.new("RGB", (w, h), (20, 20, 20))
    canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return canvas

SEG = os.environ.get("MITAS_MSEG", "cikis")  # cikis | giris

def build_row(fid):
    cd = DB / fid
    full = sorted((cd / "frames" / SEG).glob("*.png"))
    pool = sorted((cd / "frames" / f"{SEG}_jenerik").glob("*.png"))
    picks = []  # (label, path)
    if not full:
        return None
    if not pool:
        # boş havuz: son 6 kare
        tail = full[-6:]
        for p in tail:
            picks.append((f"#{full.index(p)}", p))
        info = f"POOL=0 (BOŞ)\nson 6 kare"
    else:
        i0 = idx_of(pool[0].name, full)
        i1 = idx_of(pool[-1].name, full)
        if i0 is None: i0 = 0
        if i1 is None: i1 = len(full) - 1
        plen = len(pool)
        if SEG == "giris":
            # giriş: kredi başta; havuzun SONUNDA footage başlıyor mu? [baş, iç, iç, SON-2, SON, SON+4(footage?)]
            cand = [
                (i0, "★BAŞ"),
                (min(len(full)-1, i0 + max(1, plen // 4)), "hav¼"),
                (min(len(full)-1, i0 + max(2, (plen * 3) // 5)), "hav⅗"),
                (i1, "SON★"),
                (min(len(full)-1, i1 + 3), "sonrası"),
                (min(len(full)-1, i1 + 8), "sonrası"),
            ]
        else:
            # çıkış: kredi sonda; havuzun BAŞINDA footage var mı? [öncesi, öncesi, BAŞ, iç, iç, son]
            cand = [
                (max(0, i0 - 6), "öncesi"),
                (max(0, i0 - 2), "öncesi"),
                (i0, "★BAŞ"),
                (min(len(full)-1, i0 + max(1, plen // 4)), "hav¼"),
                (min(len(full)-1, i0 + max(2, (plen * 3) // 5)), "hav⅗"),
                (i1, "SON"),
            ]
        for idx, tag in cand:
            picks.append((f"{tag} #{idx}", full[idx]))
        info = f"POOL={plen}\nbaş=#{i0} son=#{i1}"
    return picks, info

def make(fids, out):
    fids = [f for f in fids if (DB / f / "frames" / "cikis").is_dir()]
    n = len(fids)
    rowH = ROWH + 22
    W = LBL + 6 * (CW + PAD)
    H = n * (rowH + PAD) + 10
    canvas = Image.new("RGB", (W, H), (12, 12, 12))
    d = ImageDraw.Draw(canvas)
    y = 6
    for fid in fids:
        row = build_row(fid)
        short = fid.split("-1-0000")[0].split("_")[-1][:26]
        if not row:
            d.text((6, y), short + " (kare yok)", font=FB, fill=(255,120,120)); y += rowH + PAD; continue
        picks, info = row
        d.text((6, y + 4), short, font=FB, fill=(255, 235, 120))
        for li, line in enumerate(info.split("\n")):
            d.text((6, y + 26 + li*16), line, font=F, fill=(160, 200, 255))
        x = LBL
        for tag, p in picks:
            thumb = load_small(p)
            canvas.paste(thumb, (x, y))
            col = (120,255,120) if "BAŞ" in tag else ((255,180,80) if "önce" in tag else (200,200,200))
            d.text((x + 2, y + ROWH + 2), tag, font=F, fill=col)
            x += CW + PAD
        y += rowH + PAD
    canvas.save(out)
    print(f"{out} ({n} film, {W}x{H})")

if __name__ == "__main__":
    prefix = sys.argv[1]
    ids = sys.argv[2:]
    if ids and ids[0].startswith("@"):
        ids = [l.strip() for l in open(ids[0][1:], encoding="utf-8") if l.strip()]
    if not ids:
        ids = sorted(os.path.basename(p) for p in glob.glob(f"{RUN}/Database/*") if os.path.isdir(p))
    # PER'lik gruplara böl
    for gi in range(0, len(ids), PER):
        grp = ids[gi:gi+PER]
        make(grp, f"{prefix}_{gi//PER:02d}.png")
