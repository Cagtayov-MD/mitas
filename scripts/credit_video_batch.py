#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
credit_video_batch.py — credit_video_read'i bir film SERISI uzerinde kosar, her film icin
gercek kunye ciktisi (JSON) uretir. DEVAM-EDILEBILIR (resumable): cikti varsa atlar.

Production hattina (mitas_pipeline) DOKUNMAZ; bagimsiz batch. Cikti guvenildikten sonra
hatta gomulur (sonraki adim).

Kullanim:
  python scripts/credit_video_batch.py                         # tester serisi (kareleri olan tum filmler)
  python scripts/credit_video_batch.py --root <dir>            # <dir>/<film>/{giris,cikis}/frames yapisi
  python scripts/credit_video_batch.py --limit 10              # ilk 10 film
  python scripts/credit_video_batch.py --models gemma4:26b     # model override

Cikti: <out>/<film>.json  + <out>/_OZET.tsv (film, yonetmen, guven, #yapimci, #cast)
"""
import argparse
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credit_video_read as cv

DEFAULT_ROOT = r"E:\MITAS\OCR-worktree\tester"
DEFAULT_OUT = r"E:\MITAS\outputs\credit_video"

def safe(name):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)[:120]

def discover(root):
    """root altinda giris/frames veya cikis/frames olan film klasorleri."""
    films = []
    for d in sorted(glob.glob(os.path.join(root, "*"))):
        if not os.path.isdir(d):
            continue
        g = os.path.join(d, "giris", "frames")
        c = os.path.join(d, "cikis", "frames")
        if (os.path.isdir(g) and cv.list_frames(g)) or (os.path.isdir(c) and cv.list_frames(c)):
            films.append((os.path.basename(d), g if os.path.isdir(g) else None,
                          c if os.path.isdir(c) else None))
    return films

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Seri uzerinde video kunye okuma (resumable)")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--models", default=None)
    ap.add_argument("--force", action="store_true", help="var olan ciktiyi da yeniden uret")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    models = args.models.split(",") if args.models else None
    kb = cv.KB()
    films = discover(args.root)
    if args.limit:
        films = films[:args.limit]
    summary_path = os.path.join(args.out, "_OZET.tsv")
    if not os.path.exists(summary_path):
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write("film\tyonetmen\tguven\tn_yapimci\tn_cast\tsn\n")

    print(f"[batch] {len(films)} film | model={models or cv.MODELS} | out={args.out}", flush=True)
    done = skip = 0
    for i, (name, g, c) in enumerate(films, 1):
        outp = os.path.join(args.out, safe(name) + ".json")
        if os.path.exists(outp) and not args.force:
            skip += 1
            print(f"[{i}/{len(films)}] ATLA (var): {name}", flush=True)
            continue
        t0 = time.time()
        try:
            res = cv.read_credits(g, c, models=models, kb=kb)
        except Exception as e:
            print(f"[{i}/{len(films)}] HATA {name}: {type(e).__name__} {e}", flush=True)
            continue
        dt = round(time.time() - t0, 1)
        res["_film"] = name
        res["_sn"] = dt
        with open(outp, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(f"{name}\t{', '.join(res['yonetmen']) or 'okunamadı'}\t{res['guven']}\t"
                    f"{len(res['yapimci'])}\t{len(res['cast'])}\t{dt}\n")
        done += 1
        print(f"[{i}/{len(films)}] {name} -> yön={res['yonetmen'] or 'okunamadı'} "
              f"[{res['guven']}] yap={len(res['yapimci'])} cast={len(res['cast'])} ({dt}s)", flush=True)
    print(f"[batch] BITTI: {done} uretildi, {skip} atlandi -> {args.out}", flush=True)

if __name__ == "__main__":
    main()
