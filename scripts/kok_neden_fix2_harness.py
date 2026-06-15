#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
kok_neden_fix2_harness.py — FIX-2 (MITAS_CREDIT_PREFER_TEXT) yönetmen-ekseni kanıtı.

3 mod karşılaştırır (gerçek qwen yönetmeni _log.jsonl'den):
  1) ŞİMDİ        : parse_credits(v2=off) + qwen AUGMENT (parse-önce)   [production şu an]
  2) FIX-1        : parse_credits(v2=on)  + qwen AUGMENT (parse-önce)
  3) FIX-1+FIX-2  : qwen BİRİNCİL + parse(v2=on)'un TEMİZ yedek isimleri
Metrik: her modda yönetmen alanındaki ÇÖP isim (disclaimer/garble/şirket) sayısı.
"""
import os, json, glob, sys, importlib.util
sys.stdout.reconfigure(encoding="utf-8")

PDFMITAS = r"E:\MITAS\OCR-worktree\pdf-mitas"
DB = "E:/MITAS/Database"
spec = importlib.util.spec_from_file_location("credit_parse", os.path.join(PDFMITAS, "credit_parse.py"))
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)


def qwen_dir_from_log(folder):
    log = os.path.join(folder, "_log.jsonl")
    if not os.path.exists(log):
        return None
    for line in open(log, encoding="utf-8", errors="replace"):
        if "credit_text_completed" in line:
            try:
                det = json.loads(line).get("detail", {})
                return det.get("yonetmen")
            except Exception:
                pass
    return None


def merge_augment(parse_dir, qwen_dir):                    # parse-önce + qwen
    return cp._dedup(list(parse_dir) + list(qwen_dir or []))


def merge_prefer(parse_dir_v2on, qwen_dir, cast_folds):     # SUPPLEMENT: qwen-önce + parse'in TEMİZ isimleri
    if not qwen_dir:
        return list(parse_dir_v2on)
    clean = [n for n in parse_dir_v2on if not cp._v2_reject_name(n)]   # kimlik-çapası: OCR yönetmeni düşmez
    return cp._dedup(list(qwen_dir) + clean)


def junk_count(names):
    return sum(1 for n in names if cp._v2_reject_name(n))


def run():
    seen = {}
    for d in sorted(os.listdir(DB)):
        p = os.path.join(DB, d)
        if not os.path.isdir(p):
            continue
        txts = [f for f in os.listdir(p) if f.endswith(".txt") and "teknik" not in f]
        if not txts:
            continue
        head = open(os.path.join(p, txts[0]), encoding="utf-8", errors="replace").read(400)
        if "15.06" not in head and "14.06" not in head:
            continue
        ocr = sorted(glob.glob(os.path.join(p, "ocr", "ocr-*", "kunye.txt")))
        if not ocr:
            continue
        trt, tip, _, title = cp.classify_trt(d)
        if trt in seen or tip == "DİZİ":
            continue
        seen[trt] = (d, p, ocr[0], title)

    tot = {"now": 0, "fix1": 0, "fix12": 0}
    changed = []
    for trt, (d, folder, ocrp, title) in seen.items():
        lines = open(ocrp, encoding="utf-8", errors="ignore").read().splitlines()
        c0, cr0 = cp.parse_credits(lines, title, dizi=False, v2=False)
        c1, cr1 = cp.parse_credits(lines, title, dizi=False, v2=True)
        pdir0 = dict(cr0).get("Yönetmen", [])
        pdir1 = dict(cr1).get("Yönetmen", [])
        qd = qwen_dir_from_log(folder)

        cast_folds = {cp.fold(c) for c in c1}
        m_now = merge_augment(pdir0, qd)
        m_f1 = merge_augment(pdir1, qd)
        m_f12 = merge_prefer(pdir1, qd, cast_folds)
        tot["now"] += junk_count(m_now)
        tot["fix1"] += junk_count(m_f1)
        tot["fix12"] += junk_count(m_f12)

        if junk_count(m_now) != junk_count(m_f12) or m_now != m_f12:
            changed.append((d[:38], "; ".join(m_now), "; ".join(m_f1), "; ".join(m_f12), qd))

    print(f"Film (film-profili, qwen-loglu): {len(seen)}\n")
    print("YÖNETMEN alanındaki TOPLAM ÇÖP isim (disclaimer/garble/şirket):")
    print(f"  1) ŞİMDİ        (parse-v2off + qwen-augment): {tot['now']}")
    print(f"  2) FIX-1        (parse-v2on  + qwen-augment): {tot['fix1']}")
    print(f"  3) FIX-1+FIX-2  (qwen-birincil + temiz-yedek): {tot['fix12']}")
    print(f"\nDeğişen film: {len(changed)}\n")
    print("--- Örnek (ŞİMDİ → FIX-1 → FIX-1+FIX-2) ---")
    for d, now, f1, f12, qd in changed[:25]:
        print(f"\n{d}")
        print(f"  ŞİMDİ      : {now[:95]}")
        print(f"  FIX-1      : {f1[:95]}")
        print(f"  FIX-1+FIX-2: {f12[:95]}")

    json.dump({"totals": tot, "changed": [
        {"film": d, "now": now, "fix1": f1, "fix12": f12, "qwen": qd} for d, now, f1, f12, qd in changed]},
        open("E:/MITAS/outputs/fix2_harness_sonuc.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\nDetay: outputs/fix2_harness_sonuc.json")


if __name__ == "__main__":
    run()
