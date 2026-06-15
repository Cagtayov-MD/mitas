#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
kok_neden_fix1_harness.py — FIX-1 (MITAS_CREDIT_PARSE_V2) before/after kanıt harness'i.

Her filmin ocr/kunye.txt'ini parse_credits ile İKİ modda çalıştırır (v2=False vs v2=True),
yönetmen+yapımcı+cast diff'ini ölçer. GPU YOK, deterministik, saniyeler.

METRİK:
  - junk_removed   : v2'nin düşürdüğü VE _v2_reject_name=True olan (disclaimer/garble/şirket) = İYİ
  - regression     : v2'nin düşürdüğü AMA _v2_reject_name=False (gerçek-görünen isim) = RİSK
  - recovered      : v2'nin EKLEDİĞİ (inline 'UN FILM DE X' kurtarması) = İYİ
"""
import os, re, sys, glob, json, importlib.util
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")

PDFMITAS = r"E:\MITAS\OCR-worktree\pdf-mitas"
DB = "E:/MITAS/Database"

spec = importlib.util.spec_from_file_location("credit_parse", os.path.join(PDFMITAS, "credit_parse.py"))
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)


def load_films():
    """Tüm 14-15 Haziran filmleri (ocr/kunye.txt olanlar), benzersiz trt."""
    seen = {}
    for d in sorted(os.listdir(DB)):
        p = os.path.join(DB, d)
        if not os.path.isdir(p):
            continue
        # 14-15 Haziran mı? final txt üretim tarihinden
        txts = [f for f in os.listdir(p) if f.endswith(".txt") and "teknik" not in f]
        if not txts:
            continue
        raw = open(os.path.join(p, txts[0]), encoding="utf-8", errors="replace").read(400)
        if "15.06" not in raw and "14.06" not in raw:
            continue
        ocr = sorted(glob.glob(os.path.join(p, "ocr", "ocr-*", "kunye.txt")))
        if not ocr:
            continue
        trt, tip, _, title = cp.classify_trt(d)
        if trt in seen:
            continue
        seen[trt] = {"trt": trt, "film": d, "ocr": ocr[0], "title": title,
                     "dizi": (tip == "DİZİ")}
    return list(seen.values())


def run():
    films = load_films()
    print(f"Film (benzersiz, kunye.txt'li): {len(films)}\n")

    tot_junk = Counter()
    tot_reg = []          # regresyon adayları (film, alan, isim)
    tot_rec = []          # inline kurtarılan
    changed_films = 0
    field_changes = Counter()
    rows = []

    for f in films:
        lines = open(f["ocr"], encoding="utf-8", errors="ignore").read().splitlines()
        c0, cr0 = cp.parse_credits(lines, f["title"], dizi=f["dizi"], v2=False)
        c1, cr1 = cp.parse_credits(lines, f["title"], dizi=f["dizi"], v2=True)

        def crewmap(cr):
            return {rol: list(names) for rol, names in cr}
        m0, m1 = crewmap(cr0), crewmap(cr1)

        # cast fold kümeleri (overreach-fix tespiti: crew'den düşen ama cast'te olan = doğru taşıma)
        cast_folds = {cp.fold(x) for x in (c0 + c1)}
        film_changed = False
        tot_overreach = globals().setdefault("_ov", [])
        for alan, b, a in (("Yönetmen", m0.get("Yönetmen", []), m1.get("Yönetmen", [])),
                           ("Yapımcı", m0.get("Yapımcı", []), m1.get("Yapımcı", [])),
                           ("Cast", c0, c1)):
            bset = {cp.fold(x): x for x in b}
            aset = {cp.fold(x): x for x in a}
            dropped = [bset[k] for k in bset if k not in aset]
            added = [aset[k] for k in aset if k not in bset]
            for nm in dropped:
                if cp._v2_reject_name(nm):
                    tot_junk[alan] += 1                      # disclaimer/garble/şirket = çöp
                elif alan != "Cast" and cp.fold(nm) in cast_folds:
                    tot_overreach.append((f["film"][:35], alan, nm))  # crew→cast'te var = overreach-fix
                elif any(ch in nm for ch in '."') or nm.strip().startswith("-"):
                    tot_junk[alan] += 1                      # diyalog/altyazı punctuation = çöp
                else:
                    tot_reg.append((f["film"][:35], alan, nm))        # GERÇEK regresyon adayı
                film_changed = True
            for nm in added:
                if not cp._v2_reject_name(nm):
                    tot_rec.append((f["film"][:35], alan, nm))
                film_changed = True
            if dropped or added:
                field_changes[alan] += 1
        if film_changed:
            changed_films += 1
            rows.append({
                "film": f["film"], "trt": f["trt"],
                "yon_before": "; ".join(m0.get("Yönetmen", [])),
                "yon_after": "; ".join(m1.get("Yönetmen", [])),
                "yap_before": "; ".join(m0.get("Yapımcı", [])),
                "yap_after": "; ".join(m1.get("Yapımcı", [])),
                "cast_before": "; ".join(c0), "cast_after": "; ".join(c1),
            })

    _ov = globals().get("_ov", [])
    print("="*70)
    print(f"DEĞİŞEN FİLM: {changed_films}/{len(films)}")
    print(f"Alan-bazlı değişiklik: {dict(field_changes)}")
    print(f"\nJUNK_REMOVED (iyi, çöp/disclaimer/garble eleme): {sum(tot_junk.values())}  {dict(tot_junk)}")
    print(f"OVERREACH_FIX (iyi, crew'den çıktı ama cast'te DURUYOR): {len(_ov)}")
    print(f"RECOVERED (iyi, gerçek isim eklendi/kurtarıldı): {len(tot_rec)}")
    print(f"GERÇEK REGRESSION (RİSK, kaybolan gerçek isim): {len(tot_reg)}")
    print("="*70)
    if _ov:
        print("\n--- OVERREACH_FIX örnekleri (yanlış alandan çıktı, cast'te korundu) ---")
        for film, alan, nm in _ov[:12]:
            print(f"  {alan}↛: {nm}   ({film})")

    if tot_rec:
        print("\n--- RECOVERED örnekleri (inline 'UN FILM DE X') ---")
        for film, alan, nm in tot_rec[:15]:
            print(f"  +{alan}: {nm}   ({film})")

    if tot_reg:
        print(f"\n--- REGRESSION adayları ({len(tot_reg)}) — İNCELE ---")
        for film, alan, nm in tot_reg[:40]:
            print(f"  -{alan}: {nm}   ({film})")
    else:
        print("\n✓ REGRESSION = 0 (hiçbir gerçek-görünen isim düşmedi)")

    json.dump({"changed": changed_films, "n": len(films),
               "junk": dict(tot_junk), "recovered": tot_rec, "regression": tot_reg,
               "rows": rows},
              open("E:/MITAS/outputs/fix1_harness_sonuc.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\nDetay: outputs/fix1_harness_sonuc.json")


if __name__ == "__main__":
    run()
