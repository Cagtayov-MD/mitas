#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""pipeline_timing.py — tam koşu süre raporu. Her Database/<clip>/_DURUM.json'daki
timings_sec'i okur: klip başına dk + aşama kırılımı + özet (ort/min/max). "Bir klip kaç dk."

Kullanım:  python scripts/pipeline_timing.py            # tüm Database
           python scripts/pipeline_timing.py --son 10   # en yeni 10 klip
"""
import argparse, glob, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"E:\MITAS\Database")
    ap.add_argument("--son", type=int, default=0)
    args = ap.parse_args()
    files = sorted(glob.glob(os.path.join(args.root, "*", "_DURUM.json")), key=os.path.getmtime, reverse=True)
    if args.son:
        files = files[:args.son]
    rows = []
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        t = d.get("timings_sec") or {}
        if not t.get("toplam"):
            continue
        rows.append({"clip": d.get("clip_id") or os.path.basename(os.path.dirname(f)),
                     "title": (d.get("title") or "")[:24], "sure": d.get("duration") or "—",
                     "karar": d.get("karar") or "—", "t": t})
    if not rows:
        print("timing verisi olan klip yok."); return
    print(f"{'clip':14} {'video':9} {'çöz':>5} {'ocr':>6} {'asr':>6} {'video_k':>7} {'pdf':>6} {'TOPLAM':>7} {'dk':>5} karar")
    print("=" * 95)
    tot = []
    for r in rows:
        t = r["t"]; top = t.get("toplam", 0); tot.append(top)
        print(f"{str(r['clip'])[:14]:14} {r['sure']:9} {t.get('coz',0):5.0f} {t.get('ocr',0):6.0f} "
              f"{t.get('asr',0):6.0f} {t.get('video_kunye',0):7.0f} {t.get('pdf',0):6.0f} "
              f"{top:7.0f} {top/60:5.1f} {r['karar']}")
    n = len(tot)
    print("=" * 95)
    print(f"KLİP: {n} | TOPLAM süre ort {sum(tot)/n/60:.1f} dk · min {min(tot)/60:.1f} · max {max(tot)/60:.1f} dk")
    print("Not: süre büyük oranda video UZUNLUĞUNA bağlı (OCR kare + ASR). video_kunye=0 → flag kapalıydı.")

if __name__ == "__main__":
    main()
