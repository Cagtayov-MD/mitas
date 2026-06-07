#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_cast_override.json'dan adjudication adaylarını (non-OK) çıkar:
title + year + ocr_cast(md) + delivered_cast → candidates.json."""
import os, re, json

AUD = r"E:\MITAS\outputs\audit_cast_override.json"
ROOTS = {"Hazır": r"E:\MITAS\Mitas Output\Hazır", "Kontrol": r"E:\MITAS\Mitas Output\Kontrol"}
JUNK = {"1", "tester"}  # bilinen test klasörleri

def md_title_year(folder_path):
    md = os.path.join(folder_path, "kunye_teslim.md")
    title, year, trt = None, None, None
    if os.path.exists(md):
        t = open(md, encoding="utf-8", errors="ignore").read()
        m = re.search(r"#\s*M[İI]TAS.*?[•·]\s*(?:FİLM|DİZİ|FILM|DIZI)\s*[•·]\s*(.+)", t)
        if m: title = m.group(1).strip()
        m = re.search(r"ID:\s*([0-9]{4})-", t)
        if m: year = m.group(1)
        m = re.search(r"ID:\s*([0-9\-]+)", t)
        if m: trt = m.group(1).strip()
    return title, year, trt

def main():
    data = json.load(open(AUD, encoding="utf-8"))
    rows = data["all"]
    cands = []
    for r in rows:
        st = r.get("status")
        if st not in ("SUSPECT", "WEAK"):
            continue
        folder = r["folder"]; bucket = r["bucket"]
        if folder in JUNK:
            continue
        fp = os.path.join(ROOTS[bucket], folder)
        title, year, trt = md_title_year(fp)
        cands.append({
            "folder": folder, "bucket": bucket, "title": title, "year": year, "trt": trt,
            "status": st, "present_frac": r.get("present_frac"),
            "ocr_cast": r.get("md_cast") or [],           # v4-öncesi OCR kadrosu (teslim.md)
            "delivered_cast": r.get("cast") or [],        # teslim edilen v4 PDF kadrosu
        })
    op = r"E:\MITAS\outputs\audit_candidates.json"
    json.dump(cands, open(op, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"aday sayisi: {len(cands)}  → {op}")
    for c in cands:
        print(f"  [{c['status']}] {c['title']} ({c['year']})  ocr={len(c['ocr_cast'])} teslim={len(c['delivered_cast'])}")

if __name__ == "__main__":
    main()
