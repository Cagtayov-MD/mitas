"""TÜM giriş karelerinin kontak sayfası + CLIP kredi-skoru overlay.
Amaç: GARY GRIMES / LEE MARVIN / MIRISCH gibi kartlar entry_frames'te VAR MI, ve CLIP onları yakaladı mı (recall testi).
Yeşil etiket = CLIP kredi (>=thr), kırmızı = footage. PIL (Türkçe-İ path güvenli).
"""
import sys, glob, argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.stdout.reconfigure(encoding="utf-8")

DB = Path(r"F:\REPO_GitHub\DATABASE")
PROBE = Path(r"E:\MITAS\OCR-worktree\clip_probe")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", default="ACEMİLER")
    ap.add_argument("--seg", default="giris")
    ap.add_argument("--sub", default="entry_frames")
    ap.add_argument("--cols", type=int, default=10)
    ap.add_argument("--tw", type=int, default=213)
    ap.add_argument("--thr", type=float, default=0.5)
    a = ap.parse_args()
    fd = [d for d in DB.iterdir() if a.film.lower() in d.name.lower()][0]
    safe = "".join(c if c.isalnum() else "_" for c in fd.name)[:40]
    frames = sorted(glob.glob(str(fd/a.sub/"*.png")))
    probpath = PROBE/safe/a.seg/"credit_prob.npy"
    probs = np.load(probpath) if probpath.exists() else np.zeros(len(frames))
    im0 = Image.open(frames[0]); W0, H0 = im0.size
    th = int(a.tw * H0 / W0)
    cols = a.cols; rows = (len(frames)+cols-1)//cols
    print(f"{fd.name}\n  kare={len(frames)} çöz={W0}x{H0} thumb={a.tw}x{th} grid={cols}x{rows}")
    canvas = Image.new("RGB", (cols*a.tw, rows*th), (15, 15, 15))
    d = ImageDraw.Draw(canvas)
    hi = 0
    for i, f in enumerate(frames):
        im = Image.open(f).convert("RGB").resize((a.tw, th))
        r, c = divmod(i, cols); x, y = c*a.tw, r*th
        canvas.paste(im, (x, y))
        p = probs[i] if i < len(probs) else 0.0
        cred = p >= a.thr; hi += int(cred)
        col = (60, 255, 60) if cred else (255, 70, 70)
        d.rectangle([x, y, x+58, y+13], fill=(0, 0, 0))
        d.text((x+2, y+2), f"#{i} {p:.2f}", fill=col)
        if cred: d.rectangle([x, y, x+a.tw-1, y+th-1], outline=(60, 255, 60), width=2)
    out = PROBE/safe/f"{a.seg}_contact_scores.png"
    canvas.save(out)
    print(f"  CLIP-kredi (>= {a.thr}) kare: {hi}/{len(frames)}")
    print(f"-> {out}")

if __name__ == "__main__":
    main()
