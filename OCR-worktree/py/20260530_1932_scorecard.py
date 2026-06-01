"""20260530_1932 — SCORECARD: tüm master'ları küçük önizlemeli kontak-sayfasına diz (giriş/çıkış ayrı).
Hızlı triage: temiz text-kolonu mu, footage-smear çöp mü, boş mu. Etiket: film / boyut / blok.
"""
import json, re
from pathlib import Path
import cv2, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

T = Path(r"E:\MITAS\OCR-worktree\tester")
summ = json.loads((T/"_SUMMARY.json").read_text(encoding="utf-8"))
TW, TH, COLS = 150, 460, 8   # thumb w,h ; grid sütun

def rd(p): return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
def short(f):
    t = f.split("-1-")[-1]
    return (t[:20]) if t else f[:20]

def sheet(seg):
    items = [e for e in summ if e.get("seg") == seg and e.get("master")]
    items.sort(key=lambda e: e.get("idx", 0))
    n = len(items); rows = (n + COLS - 1)//COLS
    fig, axes = plt.subplots(rows, COLS, figsize=(COLS*1.7, rows*2.4))
    fig.suptitle(f"SCORECARD — {seg.upper()}  ({n} master)  ·  E:/MITAS/OCR-worktree/tester", fontsize=12, y=0.997)
    axes = np.array(axes).reshape(rows, COLS)
    for ax in axes.flat: ax.axis("off")
    for i, e in enumerate(items):
        ax = axes[i//COLS, i%COLS]
        mp = T/e["film"]/seg/"master.png"
        img = rd(mp)
        if img is None: continue
        thumb = cv2.cvtColor(cv2.resize(img, (TW, TH)), cv2.COLOR_BGR2RGB)
        ax.imshow(thumb, aspect="auto")
        w, h = e["master"]; b = e.get("blocks", "?")
        ax.set_title(f"{short(e['film'])}\n{w}x{h} b{b}", fontsize=5.2, pad=1.5)
    out = T/f"_scorecard_{seg}.png"
    plt.tight_layout(rect=[0, 0, 1, 0.985]); plt.savefig(out, dpi=150); plt.close()
    print(f"{seg}: {n} master -> {out}")

for s in ["cikis", "giris"]:
    sheet(s)
print("done")
