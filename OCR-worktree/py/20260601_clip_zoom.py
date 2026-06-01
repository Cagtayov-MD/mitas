"""Şüpheli film/seg için OKUNUR boyutta tanı-sayfası: kredi karelerinden eşit aralıkla 9 kare (yoksa en yüksek skorlu 9).
Amaç: yüksek-% gerçek jenerik mi / dağınık run footage FP mi / %0 giriş gerçekten boş mu?
"""
import sys, glob, importlib.util, argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.stdout.reconfigure(encoding="utf-8")
DB = Path(r"F:\REPO_GitHub\DATABASE"); REV = Path(r"E:\MITAS\OCR-worktree\clip_probe\_REVIEW15")
THR = 0.5

def safe_of(name): return "".join(c if c.isalnum() else "_" for c in name)[:40]

def sheet(film, seg, sub):
    fd = [d for d in DB.iterdir() if film.lower() in d.name.lower()][0]
    safe = safe_of(fd.name)
    frames = sorted(glob.glob(str(fd/sub/"*.png")))
    ps = np.load(REV/f"{safe}__{seg}.npy")
    cred = [i for i in range(len(ps)) if ps[i] >= THR]
    if cred:
        pick = [cred[int(round(k))] for k in np.linspace(0, len(cred)-1, min(9, len(cred)))]
        mode = f"kredi-setinden eşit-aralık ({len(cred)} kare)"
    else:
        pick = list(np.argsort(-ps)[:9]); pick.sort(); mode = "KREDİ YOK -> en yüksek skorlu 9 (eşik altı)"
    cols, tw, th = 3, 426, 240
    rows = (len(pick)+cols-1)//cols
    canvas = Image.new("RGB", (cols*tw, rows*th+20), (15, 15, 15))
    d = ImageDraw.Draw(canvas); d.text((4, 3), f"{fd.name}  /  {seg}  —  {mode}", fill=(255, 255, 0))
    for k, fi in enumerate(pick):
        im = Image.open(frames[fi]).convert("RGB").resize((tw, th)); r, c = divmod(k, cols)
        canvas.paste(im, (c*tw, r*th+20))
        col = (60, 255, 60) if ps[fi] >= THR else (255, 90, 90)
        d.rectangle([c*tw, r*th+20, c*tw+92, r*th+34], fill=(0, 0, 0))
        d.text((c*tw+2, r*th+21), f"#{fi} p={ps[fi]:.2f}", fill=col)
    out = REV/f"ZOOM_{safe}_{seg}.png"; canvas.save(out)
    print(f"-> {out}  ({mode})")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--targets", required=True,
        help="film|seg|sub virgülle: 'AFFEDİLMEYEN 1992|cikis|exit_frames,...'")
    for t in ap.parse_args().targets.split(","):
        film, seg, sub = t.split("|"); sheet(film.strip(), seg.strip(), sub.strip())
