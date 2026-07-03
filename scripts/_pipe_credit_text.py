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
import time
import debug_trace as dbg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _find_ocr(clip):
    if not clip:
        return None
    g = sorted(glob.glob(os.path.join(clip, "ocr", "*", "kunye.txt")), key=lambda p: os.path.getmtime(p))
    return g[-1] if g else None


def _dilim_lines(ocr_path):
    """K1-PRIMARY (Opus-panel aksiyonu 2026-07-03): dilim-OneOCR satırlarını BİRİNCİL okuma
    girdisine de kat — dilim yalnız doğrulama-kalkanında kalırsa İHTİRAS/Norton tipi kayıplar
    VL'nin (halüsinasyon riskli) önerisine muhtaç kalır; oysa satırlar OneOCR-otoritesiyle
    doğrudan LLM rol-eşlemesine girebilir ("okunamadı>yanlış" güvenli: OneOCR uydurmaz,
    additive satır yalnız recall artırır). RUN-SCOPE: dilim meta.ocr_job, --ocr yolundaki
    job klasörüyle ('ocr-XXXX' / '-fb' kardeşi baz alınır) eşleşmeli — bayat-dilim girmez.
    Kill-switch: MITAS_CREDIT_TEXT_DILIM=0. Döner: satır listesi ([] = katkı yok)."""
    if os.environ.get("MITAS_CREDIT_TEXT_DILIM", "1").strip().lower() in ("0", "false", "off", "no"):
        return []
    try:
        job_dir = os.path.basename(os.path.dirname(os.path.abspath(ocr_path)))
        base_job = job_dir[:-3] if job_dir.endswith("-fb") else job_dir
        clip = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(ocr_path))))
        md = os.path.join(clip, "master_dilim")
        txt = os.path.join(md, "dilim_oneocr.txt")
        meta_p = os.path.join(md, "dilim_oneocr.meta.json")
        if not (os.path.isfile(txt) and os.path.isfile(meta_p)):
            return []
        meta = json.load(open(meta_p, encoding="utf-8", errors="ignore"))
        if str(meta.get("ocr_job") or "") not in (base_job, job_dir):
            return []                                    # bayat damga → dahil etme
        out = []
        for ln in open(txt, encoding="utf-8", errors="ignore").read().splitlines():
            s = ln.strip()
            if s and not s.startswith("### DILIM-SINIRI"):
                out.append(s)
        return out
    except Exception:  # noqa: BLE001 — dilim katkısı ASLA okuma akışını bozmaz
        return []


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    started = time.perf_counter()
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
            dbg.emit("credit_text", "stage_completed", status="warn",
                     duration_ms=(time.perf_counter() - started) * 1000,
                     subject={"field": "ocr", "reason": "ocr_metni_yok"},
                     evidence={"clip": a.clip, "ocr_arg": a.ocr},
                     source={"module": "scripts/_pipe_credit_text.py"})
            print(json.dumps(out, ensure_ascii=False))
            return
        import credit_text_read as ctr
        lines, ocr_source = ctr.load_llm_lines_for_ocr(ocr)
        raw_context = ctr.load_raw_context_for_ocr(ocr)
        # K1-PRIMARY: dilim-OneOCR satırları hem LLM girdisine hem ham-bağlama ADDITIVE eklenir
        # (run-scope damga şartlı; _guard token-kümesi aynı metinden kurulduğu için tutarlı kalır).
        _dl = _dilim_lines(ocr)
        if _dl:
            lines = list(lines) + ["### MASTER-DILIM OKUMASI ###"] + _dl
            raw_context = list(raw_context or []) + _dl
            ocr_source = (ocr_source or "") + "+dilim"
        res = ctr.read_credits_auto(
            lines, a.title, dizi=(a.profile == "dizi"), raw_context_lines=raw_context
        ) or {}
        out = {"yonetmen": res.get("yonetmen", []), "yapimci": res.get("yapimci", []),
               "cast": res.get("cast", []), "guven": res.get("guven", "OKUNAMADI"),
               "model": res.get("model"), "ocr": os.path.basename(os.path.dirname(ocr)),
               "ocr_source": ocr_source,
               # PROPAGATION (FIX-C, 2026-06-23): Latin-dışı kaynak sinyalini DROP etme — qc_block'a
               # taşı (tek_film_kunye:644 → credit_qc_block:791 nonlatin_source gate → KONTROL).
               # Bu alanlar düşerse erken-romanize künye KONTROL'e gitmeden ONAYLI'ya sızar.
               "nonlatin_source": bool(res.get("nonlatin_source")),
               "translit_method": res.get("translit_method")}
        dbg.emit("credit_text", "candidate_read",
                 status="ok" if (out.get("yonetmen") or out.get("cast") or out.get("yapimci")) else "warn",
                 duration_ms=(time.perf_counter() - started) * 1000,
                 subject={"field": "credits", "after": out,
                          "reason": "LLM/text extraction from OCR lines"},
                 evidence={"ocr_source": ocr_source, "ocr_line_count": len(lines),
                           "raw_context_count": len(raw_context),
                           "model": out.get("model"), "guven": out.get("guven"),
                           "nonlatin_source": out.get("nonlatin_source"),
                           "translit_method": out.get("translit_method")},
                 source={"module": "scripts/_pipe_credit_text.py",
                         "input_paths": [ocr], "output_paths": []})
    except Exception as e:  # noqa: BLE001
        out["hata"] = f"{type(e).__name__}: {e}"
        dbg.emit("credit_text", "stage_completed", status="error",
                 duration_ms=(time.perf_counter() - started) * 1000,
                 subject={"field": "credits", "reason": "credit text extraction failed"},
                 evidence={"title": a.title, "profile": a.profile}, error=str(e),
                 source={"module": "scripts/_pipe_credit_text.py"})
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
