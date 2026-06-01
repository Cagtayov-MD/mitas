"""YOL 2 (genelleştirilmiş) — ham kareden TEXT-VELOCITY slit-scan + text-presence gate.

KARAR 3'ün YOL1-vs-YOL2 yarışı için. Hızı YAZIDAN ölçer (top-hat maske), oynayan zemini
yok sayar. Mixed segmentte (footage+credit iç içe) yazısız kareyi atlar (has_text gate) →
mini-bekçi. Tek filme gömülü değil; --frames/--out/--tag (+ ops. --lo/--hi) alır.
"""
from __future__ import annotations
import argparse, glob
from pathlib import Path
import cv2, numpy as np

SLIT_FRAC = 0.55       # sabit yatay çizgi (KARAR 1 ile aynı)
VMIN, VMAX = 1, 40     # v<1 = durdu/atla, v>40 = cut/atla
TOPHAT_K, TOPHAT_THR = 15, 22


def rd(p): return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
def wr(p, i):
    ok, b = cv2.imencode(".png", i)
    if ok: b.tofile(str(p))


def tophat(g):
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (TOPHAT_K, 5))
    th = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, k)
    _, m = cv2.threshold(th, TOPHAT_THR, 255, cv2.THRESH_BINARY)
    return m


def has_text(m):
    """geniş+kısa blob = yazı satırı (footage parıltısı elenir)."""
    n, _, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(m, np.ones((3, 3), np.uint8)), 8)
    for l in range(1, n):
        h = st[l, cv2.CC_STAT_HEIGHT]; w = st[l, cv2.CC_STAT_WIDTH]
        if 5 <= h <= 48 and w >= 40 and w / max(1, h) >= 1.5:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="film")
    ap.add_argument("--lo", type=int, default=None)
    ap.add_argument("--hi", type=int, default=None)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    fs = sorted(glob.glob(a.frames + r"/frame_*.png"),
                key=lambda p: int(Path(p).stem.split("_")[-1]))
    if a.lo is not None:
        hi = a.hi if a.hi is not None else 10**9
        fs = [f for f in fs if a.lo <= int(Path(f).stem.split("_")[-1]) <= hi]
    if not fs:
        print(f"[{a.tag}] frame yok: {a.frames}"); return

    H = W = hann = ref = None
    prev_mg = None; prev_any = False
    strips = []; vs = []; n_notext = 0; n_vrange = 0
    for f in fs:
        img = rd(f)
        if img is None: continue
        if H is None:
            H, W = img.shape[:2]
            hann = cv2.createHanningWindow((W, H), cv2.CV_32F); ref = round(SLIT_FRAC * H)
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); gf = g.astype(np.float32)
        m = tophat(g); txt = has_text(m)
        mdil = cv2.dilate(m, np.ones((11, 11), np.uint8))
        mg = gf.copy(); mg[mdil == 0] = 0.0           # zemini sıfırla → hız yazıdan
        dy = 0.0
        if prev_mg is not None and bool(mdil.any()) and prev_any:
            (_, dy), _ = cv2.phaseCorrelate(prev_mg * hann, mg * hann)
        prev_mg = mg; prev_any = bool(mdil.any())
        if not txt:
            n_notext += 1; continue                    # yazısız footage → atla (mini-bekçi)
        v = int(round(abs(dy)))
        if v < VMIN or v > VMAX:
            n_vrange += 1; continue                    # durdu / cut → atla
        strip = img[ref:ref + v, :].copy()
        if strip.shape[0] > 0:
            strips.append(strip); vs.append(v)
    if not strips:
        print(f"[{a.tag}] BOŞ — strip yok (skip_notext={n_notext}, skip_vrange={n_vrange})"); return
    master = np.vstack(strips)
    op = out / f"master_slitscan_{a.tag}.png"
    wr(op, master)
    print(f"[{a.tag}] frames={len(fs)} strip={len(strips)} skip_notext={n_notext} "
          f"skip_vrange={n_vrange} medv={int(np.median(vs))} "
          f"master={master.shape[1]}x{master.shape[0]} -> {op}")


if __name__ == "__main__":
    main()
