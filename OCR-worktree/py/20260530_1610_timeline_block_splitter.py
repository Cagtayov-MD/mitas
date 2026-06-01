"""20260530_1610 — Timeline block splitter (dy state machine) TEST.

Fikir: bir jenerik segmentini tek "scroll/statik" diye etiketleme. dy'yi zaman boyunca
ölç -> bir durum makinesi segmenti HOMOJEN bloklara bölsün ([STATİK][SCROLL][STATİK]...).
"Yarı scroll yarı statik" jenerik sorunu burada çözülür.

Çıktı: blok listesi (kare aralığı + tip + medyan hız) + ASCII zaman-çizgisi.
NOT: bu sadece HAREKET'e göre böler. Bir bloğun jenerik mi film mi olduğu = BEKÇİ'nin işi (ayrı).
"""
from __future__ import annotations
import sys, glob, argparse
from pathlib import Path
import cv2, numpy as np

DEF = r"E:\MITAS\outputs\ocr_4films_boxtrack_20260523\items\anjelik_ve_sultan_1968_end_credits\frames"

def rd(p): return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)

def med_filter(a, k=5):
    h = k // 2
    return np.array([np.median(a[max(0, i-h):i+h+1]) for i in range(len(a))])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default=DEF)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--static-th", type=float, default=1.3)   # |dy|< -> STATİK
    ap.add_argument("--scroll-th", type=float, default=2.5)   # |dy|> -> SCROLL (arası = deadband)
    ap.add_argument("--cut", type=float, default=40.0)        # |dy|> -> cut/sıçrama (sınır)
    ap.add_argument("--min-block", type=int, default=8)       # bundan kısa blok komşuya yutulur
    a = ap.parse_args()
    try: sys.stdout.reconfigure(encoding="utf-8")   # Windows cp1254 -> utf-8
    except Exception: pass

    frames = sorted(glob.glob(a.frames + r"\frame_*.png"),
                    key=lambda p: int(Path(p).stem.split("_")[-1]))[::a.stride]
    idxs = [int(Path(p).stem.split("_")[-1]) for p in frames]
    print(f"frames={len(frames)} stride={a.stride}  static<{a.static_th} scroll>{a.scroll_th} "
          f"cut>{a.cut} min_block={a.min_block}")

    # 1) dy per consecutive frame (full-frame phaseCorrelate)
    H = W = hann = prev = None
    ady = []
    for f in frames:
        g = cv2.cvtColor(rd(f), cv2.COLOR_BGR2GRAY).astype(np.float32)
        if H is None:
            H, W = g.shape; hann = cv2.createHanningWindow((W, H), cv2.CV_32F)
        dy = 0.0
        if prev is not None:
            (_, dy), _ = cv2.phaseCorrelate(prev*hann, g*hann)
        prev = g
        ady.append(abs(dy))
    ady = np.array(ady)
    is_cut = ady > a.cut
    adyc = np.clip(ady, 0, a.cut)
    sm = med_filter(adyc, 5)                       # spike temizliği

    # 2) per-frame label (deadband hysteresis)
    labels = []
    st = "S"
    for i, v in enumerate(sm):
        if is_cut[i]: st = "C"                     # cut/sıçrama
        elif v < a.static_th: st = "S"
        elif v > a.scroll_th: st = "R"
        else: pass                                 # deadband -> önceki state korunur
        labels.append("C" if is_cut[i] else st)

    # 3) runs
    runs = []
    s = 0
    for i in range(1, len(labels)+1):
        if i == len(labels) or labels[i] != labels[s]:
            runs.append([s, i-1, labels[s]]); s = i
    # 4) kısa blokları komşuya yut (cut hariç)
    changed = True
    while changed and len(runs) > 1:
        changed = False
        for j, r in enumerate(runs):
            if r[2] == "C": continue
            if (r[1]-r[0]+1) < a.min_block:
                nb = runs[j-1] if j > 0 else runs[j+1]
                nb[0] = min(nb[0], r[0]); nb[1] = max(nb[1], r[1])
                runs.pop(j); changed = True; break
    # birleşik aynı-tip ardışıkları birleştir
    merged = [runs[0]]
    for r in runs[1:]:
        if r[2] == merged[-1][2]: merged[-1][1] = r[1]
        else: merged.append(r)

    # 5) rapor
    name = {"S": "STATİK", "R": "SCROLL", "C": "CUT  "}
    print(f"\n{len(merged)} blok:")
    for r in merged:
        lo, hi = idxs[r[0]], idxs[r[1]]
        seg = ady[r[0]:r[1]+1]
        v = float(np.median(seg)) if len(seg) else 0.0
        print(f"  [{name[r[2]]}] frame {lo:5d}-{hi:5d}  ({r[1]-r[0]+1:4d} kare)  medyan|dy|={v:5.1f}")

    # 6) ASCII zaman-çizgisi (~90 sütun)
    n = len(labels); cols = min(90, n); ch = {"S": "_", "R": "#", "C": "|"}
    strip = "".join(ch[labels[int(i*n/cols)]] for i in range(cols))
    print(f"\nzaman-çizgisi (_=statik █=scroll |=cut):\n{strip}")

if __name__ == "__main__":
    main()
