# -*- coding: utf-8 -*-
"""JENERİK dedektörü GÖRSEL-QC aracı (etiketsiz) — clip_probe görselleştirme kalıbı.

Her film için giriş+çıkış kare-klasörünü dedektörden geçirir, şunları üretir:
  1. timeline.png   — kare-başına credit_score şeridi (yeşil=kredi/kırmızı=footage)
                      + altta koşular quad_type rengiyle + SEÇİLEN koşu sınır çizgileri.
  2. KREDI_dedigi.png  — en yüksek skorlu 16 kare montajı.
  3. FOOTAGE_dedigi.png — en düşük skorlu 16 kare montajı.
  4. summary satırı (stdout): opening/closing quad_type + güven + frame-aralığı.

trt_id ile dedup (` 2`/` 3` kopya klasörleri atlanır). Çıktı ASCII-güvenli klasöre.
Koşum (venvs/ocr):
  python scripts\jenerik_eval.py --films "ALFA GEÇİDİ" "AMELIA" "ACI ÇİKOLATA" ...
  python scripts\jenerik_eval.py --auto 20        # Database'den ilk 20 (dedup) film
  python scripts\jenerik_eval.py --no-clip ...    # sadece sezgisel
"""

import sys
import re
import glob
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402
import cv2  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from core.pipelines.ocr import jenerik_detector as jd  # noqa: E402
from core.pipelines.ocr.credit_detector import _cv2_imread  # noqa: E402

DB = Path(r"E:\MITAS\Database")
OUT = Path(r"E:\MITAS\OCR-worktree\jenerik_eval")

QUAD_COLOR = {  # RGB
    "bg_static_text_static": (70, 200, 70),
    "bg_static_text_scroll": (70, 160, 230),
    "bg_moving_text_static": (230, 180, 60),
    "bg_moving_text_scroll": (220, 90, 200),
    "mixed": (200, 200, 200),
    "none": (90, 90, 90),
}
TRT_RE = re.compile(r"(\d{4}-\d{4}-\d+-\d{4}-\d+-\d+)")


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name)[:48]


def _trt(name: str):
    m = TRT_RE.search(name)
    return m.group(1) if m else name


def timeline_png(sigs, runs_meta, chosen, path: Path, h_top=46, h_bot=16):
    n = len(sigs)
    if n == 0:
        return
    img = np.zeros((h_top + h_bot, n, 3), np.uint8)
    for x, s in enumerate(sigs):
        p = s.credit_score
        img[:h_top, x] = (int(230 * (1 - p)), int(200 * p), 30)  # RGB yeşil↔kırmızı
    for r in runs_meta:
        col = QUAD_COLOR.get(r["quad_type"], (120, 120, 120))
        if not r["valid"]:
            col = tuple(int(c * 0.35) for c in col)  # geçersiz koşu → soluk
        img[h_top:, r["start_frame"]:r["end_frame"] + 1] = col
    pim = Image.fromarray(img).resize((max(n, 480), h_top + h_bot), Image.NEAREST)
    d = ImageDraw.Draw(pim)
    sx = pim.width / n
    if chosen and chosen.get("start_frame") is not None:
        for fx in (chosen["start_frame"], chosen["end_frame"] + 1):
            X = int(fx * sx)
            d.line([(X, 0), (X, pim.height)], fill=(255, 255, 0), width=2)
    pim.save(path)


def montage(paths, sigs, order_idx, path: Path, cols=4, tw=176, th=120):
    sel = order_idx[:16]
    rows = (len(sel) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * tw, rows * th), (18, 18, 18))
    d = ImageDraw.Draw(canvas)
    for k, fi in enumerate(sel):
        img = _cv2_imread(paths[fi], cv2)
        if img is None:
            continue
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        im = Image.fromarray(rgb).resize((tw, th))
        r, c = divmod(k, cols)
        canvas.paste(im, (c * tw, r * th))
        s = sigs[fi]
        tag = f"#{fi} cs{s.credit_score:.2f}"
        if s.clip is not None:
            tag += f" clip{s.clip:.2f}"
        d.text((c * tw + 3, r * th + 2), tag, fill=(255, 255, 0))
    canvas.save(path)


def _seg_paths(frame_dir: Path):
    p = sorted(frame_dir.glob("*.png")) or sorted(frame_dir.glob("*.jpg"))
    return p


def eval_segment(film_dir: Path, sub: str, prefer: str, outdir: Path, clip_ctx,
                 summary_only: bool = False) -> dict:
    trt = _trt(film_dir.name)
    base = {"film": film_dir.name, "trt": trt, "seg": sub, "found": False,
            "type": "none", "quad_type": "none", "start_frame": "", "end_frame": "",
            "start_sec": "", "end_sec": "", "confidence": 0.0, "low_conf": True,
            "n_frames": 0, "n_runs": 0, "n_valid": 0, "reason": ""}
    fdir = film_dir / "frames" / sub
    if not fdir.is_dir():
        print(f"  {sub}: klasör yok")
        base["reason"] = "no_dir"
        return base
    region, sigs, runs_meta = jd.detect_from_frames(
        fdir, prefer=prefer, clip_ctx=clip_ctx, return_debug=True)
    nv = sum(1 for r in runs_meta if r["valid"])
    nm = region.get("near_miss")
    base.update(n_frames=len(sigs), n_runs=len(runs_meta), n_valid=nv,
                reason=region.get("reason", ""),
                nm_conf=(nm["confidence"] if nm else ""), nm_clip=(nm["med_clip"] if nm else ""),
                nm_minclip=(nm.get("min_clip") if nm else ""), nm_frames=(nm["n_frames"] if nm else ""),
                nm_reason=(nm["reason"] if nm else ""), nm_recoverable=(nm.get("recoverable") if nm else ""))
    if not sigs:
        print(f"  {sub}: kare yok")
        return base
    if not summary_only:
        paths = _seg_paths(fdir)
        od = outdir / sub
        od.mkdir(parents=True, exist_ok=True)
        timeline_png(sigs, runs_meta, region, od / "timeline.png")
        order = list(np.argsort([-s.credit_score for s in sigs]))
        montage(paths, sigs, order, od / "KREDI_dedigi.png")
        montage(paths, sigs, order[::-1], od / "FOOTAGE_dedigi.png")
    if region.get("found"):
        base.update(found=True, type=region["type"], quad_type=region["quad_type"],
                    start_frame=region["start_frame"], end_frame=region["end_frame"],
                    start_sec=region["start_sec"], end_sec=region["end_sec"],
                    confidence=region["confidence"], low_conf=region["low_conf"])
        print(f"  {sub}: {len(sigs)} kare | {region['quad_type']} "
              f"[{region['start_frame']}–{region['end_frame']}] "
              f"conf={region['confidence']:.2f}{' LOW' if region['low_conf'] else ''} "
              f"| {len(runs_meta)} koşu ({nv} geçerli)")
    else:
        nmtxt = ""
        if nm:
            kurt = "KURTARILABILIR (title)" if nm.get("recoverable") else "belirsiz/footage"
            nmtxt = (f" | near-miss: {nm['n_frames']}kare cs={nm['confidence']:.2f} "
                     f"med_clip={nm['med_clip']} min_clip={nm.get('min_clip')} → {kurt}")
        print(f"  {sub}: {len(sigs)} kare | KOŞU YOK ({len(runs_meta)} aday, {nv} geçerli){nmtxt}")
    return base


def find_films(args) -> list[Path]:
    seen = set()
    out = []
    if args.films:
        for q in args.films:
            cand = [d for d in DB.iterdir() if d.is_dir() and q.lower() in d.name.lower()]
            for c in sorted(cand):
                t = _trt(c.name)
                if t in seen:
                    continue
                seen.add(t)
                out.append(c)
                break
    n = args.auto or args.sample
    if n:
        # Tüm uygun (dedup) filmler → ESKİDEN-YENİYE çeşitlilik için EŞİT-ARALIK örnekle
        eligible = []
        for d in sorted(DB.iterdir()):
            if not d.is_dir() or not (d / "frames" / "giris").is_dir():
                continue
            t = _trt(d.name)
            if t in seen:
                continue
            seen.add(t)
            eligible.append(d)
        if args.sample and len(eligible) > n:
            step = len(eligible) / n
            out += [eligible[int(i * step)] for i in range(n)]
        else:
            out += eligible[:n]
    return out


def _aggregate(rows: list[dict]) -> str:
    from collections import Counter
    lines = ["", "=" * 60, "ÖZET (aggregate)"]
    for seg in ("giris", "cikis"):
        sub = [r for r in rows if r["seg"] == seg]
        if not sub:
            continue
        found = [r for r in sub if r["found"]]
        low = [r for r in found if r["low_conf"]]
        quad = Counter(r["quad_type"] for r in found)
        coarse = Counter(r["type"] for r in found)
        lines.append(f"\n[{seg}] {len(sub)} film | bulundu {len(found)} "
                     f"({100*len(found)/max(1,len(sub)):.0f}%) | düşük-güven {len(low)} | "
                     f"koşu-yok {len(sub)-len(found)}")
        lines.append(f"   kaba: {dict(coarse)}")
        lines.append(f"   4-tip: {dict(quad)}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--films", nargs="*", default=[])
    ap.add_argument("--auto", type=int, default=0, help="Database'den ilk N film (dedup)")
    ap.add_argument("--sample", type=int, default=0, help="Database'i baştan-sona EŞİT-ARALIK N film")
    ap.add_argument("--no-clip", action="store_true")
    ap.add_argument("--summary-only", action="store_true", help="görsel üretme, sadece CSV+özet (hızlı)")
    a = ap.parse_args()

    films = find_films(a)
    if not films:
        print("film bulunamadı. --films / --auto / --sample ver.")
        return
    clip_ctx = None if a.no_clip else jd.load_clip()
    OUT.mkdir(parents=True, exist_ok=True)
    mode = "ÖZET- only" if a.summary_only else "görsel"
    print(f"CLIP: {'AÇIK' if clip_ctx else 'KAPALI (sezgisel)'} | {len(films)} film | "
          f"mod={mode} | çıktı: {OUT}\n")
    rows = []
    for i, fd in enumerate(films, 1):
        print(f"### [{i}/{len(films)}] {fd.name}")
        outdir = OUT / _safe(fd.name)
        rows.append(eval_segment(fd, "giris", "first", outdir, clip_ctx, a.summary_only))
        rows.append(eval_segment(fd, "cikis", "last", outdir, clip_ctx, a.summary_only))

    import csv
    csv_path = OUT / "_results.csv"
    cols = ["film", "trt", "seg", "found", "type", "quad_type", "start_frame", "end_frame",
            "start_sec", "end_sec", "confidence", "low_conf", "n_frames", "n_runs", "n_valid", "reason",
            "nm_conf", "nm_clip", "nm_minclip", "nm_frames", "nm_reason", "nm_recoverable"]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})
    agg = _aggregate(rows)
    print(agg)
    (OUT / "_ozet.txt").write_text(agg, encoding="utf-8")
    print(f"\n-> CSV: {csv_path}\n-> görseller: {OUT}")


if __name__ == "__main__":
    main()
