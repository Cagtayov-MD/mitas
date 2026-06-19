#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_pipe_credit_text.py — mitas_pipeline subprocess runner: OneOCR ham metninden künye okuma.

KURAL (Çağatay 2026-06-08): Okuma OneOCR+GLM ile yapılır (isim kaynağı OCR metni).
LLM yalnız ROL-EŞLEME yapar (credit_text_read; pikselden OKUMAZ → halüsinasyon yasak, kalkanlı).
VLM (credit_video_read) okuması DEVRE DIŞI — bu modül onun YERİNE geçer (aynı JSON şeması, drop-in).
Qwen girdisi `kunye.txt` değil, mümkünse daha az kayıplı `ocr_ham.txt` olur; normalizasyon ve
kaçak filtreleri Qwen SONRASINDA uygulanır.

Çıktı (tek-satır JSON, _pipe_credit_video ile AYNI): {"yonetmen":[],"yapimci":[],"cast":[],"guven":...}
Model zinciri: MITAS_CREDIT_TEXT_MODEL override → yoksa DeepSeek (anahtar varsa) → qwen3:8b (yerel fallback).
ASLA çökmez (ocr yok / ollama kapalı / hata → guven=OKUNAMADI).
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _find_ocr(clip):
    if not clip:
        return None
    g = sorted(glob.glob(os.path.join(clip, "ocr", "*", "kunye.txt")), key=lambda p: os.path.getmtime(p))
    return g[-1] if g else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr", default=None, help="OneOCR+GLM kunye.txt yolu (birincil)")
    ap.add_argument("--clip", default=None, help="klip dizini (ocr/*/kunye.txt aranır)")
    ap.add_argument("--title", default="")
    ap.add_argument("--profile", default="film")
    a = ap.parse_args()

    out = {"yonetmen": [], "yapimci": [], "cast": [], "guven": "OKUNAMADI"}
    try:
        ocr = a.ocr if (a.ocr and os.path.exists(a.ocr)) else _find_ocr(a.clip)
        if not ocr or not os.path.exists(ocr):
            out["hata"] = "ocr_metni_yok"
            print(json.dumps(out, ensure_ascii=False))
            return
        import credit_text_read as ctr
        lines, ocr_source = ctr.load_llm_lines_for_ocr(ocr)
        raw_context = ctr.load_raw_context_for_ocr(ocr)
        res = ctr.read_credits_auto(
            lines, a.title, dizi=(a.profile == "dizi"), raw_context_lines=raw_context
        ) or {}
        out = {"yonetmen": res.get("yonetmen", []), "yapimci": res.get("yapimci", []),
               "cast": res.get("cast", []), "guven": res.get("guven", "OKUNAMADI"),
               "model": res.get("model"), "ocr": os.path.basename(os.path.dirname(ocr)),
               "ocr_source": ocr_source}
    except Exception as e:  # noqa: BLE001
        out["hata"] = f"{type(e).__name__}: {e}"
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
