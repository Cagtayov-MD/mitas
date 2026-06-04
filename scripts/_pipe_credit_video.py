#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_pipe_credit_video.py — mitas_pipeline subprocess runner: VİDEO-tabanlı künye okuma.

credit_video_read.read_credits'i production kare klasörleriyle çağırır, TEK-SATIR JSON basar:
  {"yonetmen":[...], "yapimci":[...], "cast":[...], "guven":"..."}
ASLA çökmez (hata/ollama-kapalı -> guven=OKUNAMADI). _pipe_ocr.py subprocess-JSON kalıbı.
Çalıştırma: OCR/global python (PIL+duckdb+urllib gerekir). GPU: ollama gemma4:26b+qwen2.5vl:7b.
"""
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def ollama_up(base="http://127.0.0.1:11434"):
    try:
        urllib.request.urlopen(base + "/api/tags", timeout=5)
        return True
    except Exception:
        return False

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--giris", default=None)
    ap.add_argument("--cikis", default=None)
    ap.add_argument("--models", default=None)
    args = ap.parse_args()

    out = {"yonetmen": [], "yapimci": [], "cast": [], "guven": "OKUNAMADI"}
    try:
        if not ollama_up():
            out["hata"] = "ollama_kapali"
            print(json.dumps(out, ensure_ascii=False)); return
        import credit_video_read as cv
        models = args.models.split(",") if args.models else None
        g = args.giris if (args.giris and os.path.isdir(args.giris)) else None
        c = args.cikis if (args.cikis and os.path.isdir(args.cikis)) else None
        if not g and not c:
            out["hata"] = "kare_klasoru_yok"
            print(json.dumps(out, ensure_ascii=False)); return
        res = cv.read_credits(g, c, models=models)
        out = {"yonetmen": res.get("yonetmen", []), "yapimci": res.get("yapimci", []),
               "cast": res.get("cast", []), "guven": res.get("guven", "OKUNAMADI")}
    except Exception as e:
        out["hata"] = f"{type(e).__name__}: {e}"
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
