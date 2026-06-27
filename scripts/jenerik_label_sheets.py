# -*- coding: utf-8 -*-
"""ETİKETLEME YARDIMCISI — kapanış-karelerine POZİSYON-indeksli kontak-sayfası + boş etiket CSV.
Ground-truth'u HIZLI toplamak için. Detektör start_pos uzayı = sorted(kareler) 0-tabanlı pozisyon.

E:\\MITAS\\Database (frames/cikis):
  python scripts\\jenerik_label_sheets.py --n 15 --sample-evenly
F:\\REPO_GitHub\\DATABASE (exit_frames):
  python scripts\\jenerik_label_sheets.py --db-root "F:\\REPO_GitHub\\DATABASE" --frames-rel exit_frames --n 15 --sample-evenly

Çıktı: outputs/jenerik_label/NN_<safe>.png (numaralı) + label_template.csv (harness formatı:
  film,seg,gt,region,quad). SEN doldur: region=[a-b] (POZISYON) veya RED; gt=CORRECT/GENUINE_NORUN.
Sonra: python scripts\\jenerik_start_eval.py --csv outputs\\jenerik_label\\label_template.csv ...
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

DB = Path(r"E:\MITAS\Database")
OUT = Path(r"E:\MITAS\outputs\jenerik_label")
GOLD_CSV = Path(r"E:\MITAS\OCR-worktree\jenerik_verify_full60.csv")


def safe(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name)[:54]


def imread_u(p: Path):
    data = np.fromfile(str(p), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None


def frames_dir(film_dir: Path, frames_rel: str) -> Path:
    d = film_dir
    for part in frames_rel.replace("\\", "/").split("/"):
        d = d / part
    return d


def list_frames(film_dir: Path, frames_rel: str) -> list[Path]:
    fd = frames_dir(film_dir, frames_rel)
    if not fd.is_dir():
        return []
    def key(p: Path):
        n = re.findall(r"\d+", p.stem)
        return (int(n[-1]) if n else 0, p.name.lower())
    return sorted([p for p in fd.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg")], key=key)


def render_sheet(idx: int, film: str, frames: list[Path], step: int, out_png: Path, hint=None) -> None:
    sel = list(range(0, len(frames), step))
    if (len(frames) - 1) not in sel:
        sel.append(len(frames) - 1)
    tw, th, cols = 150, 104, 10
    rows = math.ceil(len(sel) / cols)
    sheet = np.full((rows * (th + 18) + 30, cols * tw, 3), 22, np.uint8)
    cv2.putText(sheet, f"#{idx}  {film[:60]}  | {len(frames)} kare | karo ustu = POZISYON",
                (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (255, 255, 255), 1, cv2.LINE_AA)
    for k, pos in enumerate(sel):
        img = imread_u(frames[pos])
        r, c = divmod(k, cols)
        y0, x0 = 30 + r * (th + 18), c * tw
        if img is not None:
            sheet[y0 + 16:y0 + 16 + th, x0:x0 + tw] = cv2.resize(img, (tw, th), interpolation=cv2.INTER_AREA)
        col = (0, 230, 0) if (hint is not None and abs(pos - hint) < step) else (210, 210, 0)
        cv2.putText(sheet, f"{pos}", (x0 + 3, y0 + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.46, col, 1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".png", sheet)
    if ok:
        out_png.parent.mkdir(parents=True, exist_ok=True)
        buf.tofile(str(out_png))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--step", type=int, default=10)
    ap.add_argument("--min-frames", type=int, default=120)
    ap.add_argument("--films", nargs="*", default=None)
    ap.add_argument("--db-root", default=str(DB))
    ap.add_argument("--frames-rel", default="frames/cikis")
    ap.add_argument("--sample-evenly", action="store_true")
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    dbroot = Path(args.db_root)
    frel = args.frames_rel

    labeled = {r["film"] for r in csv.DictReader(open(GOLD_CSV, encoding="utf-8-sig"))}
    if args.films:
        films = [dbroot / f for f in args.films]
    else:
        elig = []
        for d in sorted(dbroot.iterdir()):
            if not d.is_dir() or d.name in labeled or d.name.endswith((" 2", " 3")):
                continue
            if len(list_frames(d, frel)) >= args.min_frames:
                elig.append(d)
        if args.sample_evenly and len(elig) > args.n:
            stepf = len(elig) / args.n
            films = [elig[int(i * stepf)] for i in range(args.n)]
        else:
            films = elig[: args.n]

    rows = []
    for i, d in enumerate(films, start=1):
        frames = list_frames(d, frel)
        if not frames:
            continue
        hint = None
        jd = d / "frames" / "jenerik_detection.json"
        if jd.exists():
            try:
                hint = (json.loads(jd.read_text(encoding="utf-8")) or {}).get("start_pos")
            except Exception:
                hint = None
        out_png = OUT / f"{i:02d}_{safe(d.name)}.png"
        render_sheet(i, d.name, frames, args.step, out_png, hint)
        rows.append({"idx": i, "film": d.name, "seg": "cikis", "gt": "", "region": "", "quad": "",
                     "n_frames": len(frames), "db_root": str(dbroot), "frames_rel": frel,
                     "sheet": str(out_png)})
        print(f"  #{i:02d} {d.name[:48]:48s} {len(frames)} kare -> {out_png.name}")

    template = OUT / "label_template.csv"
    with template.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["idx", "film", "seg", "gt", "region", "quad",
                                          "n_frames", "db_root", "frames_rel", "sheet"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\n{len(rows)} numaralı sayfa -> {OUT}")
    print(f"şablon -> {template}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
