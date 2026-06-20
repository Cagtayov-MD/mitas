# -*- coding: utf-8 -*-
"""yanlis_okuma_bul.py — OCR YANLIŞ OKUMALARINI bul: ne okumuş ↔ gerçekte ne.

Kimlik KESİNLEŞEN (cast≥2 KB-örtüşme) filmlerde KB-gerçek yönetmen+cast biliniyor.
OCR'ın okuduğu (ham .txt) ile KB-gerçeği karşılaştırır; yönetmen yanlış-okuma / çöp /
okunamadı ve cast garble vakalarını OCR ↔ GERÇEK olarak listeler.

HIZ: doğrudan crosscheck (qc_block + director-anchor overhead'i YOK — bulucu zaten yalnız
cast-kilitli filmlerle ilgileniyor). Çalıştır: python outputs/yanlis_okuma_bul.py [N]
"""
import os, re, sys, glob, importlib.util
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import credit_crosscheck as cc
from credit_text_read import _valid_person_name, _looks_garble, _only_persons
_spec = importlib.util.spec_from_file_location("ab", os.path.join(HERE, "qc_block_ab_batch.py"))
ab = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ab)


def _dir_match(ocr, reals):
    return any(cc.name_match(ocr, r) or cc.name_close(ocr, r) for r in (reals or []))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    folders = [d for d in sorted(glob.glob(os.path.join(ROOT, "Database", "*"))) if os.path.isdir(d)]
    kb = cc.CreditKB()
    yanlis_yon, okunamadi, cop_yon, cast_garble = [], [], [], []
    olculen = kilitli = 0
    try:
        for folder in folders:
            if olculen >= n:
                break
            title, year = ab._parse_folder(os.path.basename(folder))
            if not title:
                continue
            txts = [p for p in glob.glob(os.path.join(folder, "*.txt")) if not p.endswith("_teknik.txt")]
            if not txts:
                continue
            try:
                yon, cast, yap, ozet = ab._parse_txt(txts[0])
            except Exception:
                continue
            olculen += 1
            id_cast = (_only_persons(cast) or cast)[:12]
            try:
                cross = kb.crosscheck(yon[0] if yon else "", id_cast, title_tr=title, year=year)
            except Exception:
                continue
            cast_ov = int(cross.get("cast_ortusme", 0) or 0)
            if not (cross.get("verdict") == "TEYİT" or cast_ov >= 2):   # yalnız KESİN kilit
                continue
            kilitli += 1
            real_yon = cross.get("otoriter_yonetmen") or []
            real_cast = cross.get("otoriter_cast") or []
            ocr_dir = (yon[0].strip() if yon and yon[0].strip() else None)
            if real_yon:
                if not ocr_dir:
                    okunamadi.append((title, year, real_yon[0]))
                elif _dir_match(ocr_dir, real_yon):
                    pass  # DOĞRU okumuş
                elif (not _valid_person_name(ocr_dir)) or _looks_garble(ocr_dir):
                    cop_yon.append((title, year, ocr_dir, real_yon[0]))
                    print(f"  [ÇÖP-YÖN] {title} ({year}): OCR='{ocr_dir[:42]}' → GERÇEK={real_yon[0]}", flush=True)
                else:
                    yanlis_yon.append((title, year, ocr_dir, real_yon[0]))
                    print(f"  [YANLIŞ-YÖN] {title} ({year}): OCR='{ocr_dir}' → GERÇEK='{real_yon[0]}'", flush=True)
            if real_cast:
                kayip = [c for c in cast if c and str(c).strip() and _valid_person_name(c)
                         and not any(cc.name_match(c, r) or cc.name_close(c, r) for r in real_cast)]
                if kayip:
                    cast_garble.append((title, year, kayip[:4], real_cast[:5]))
    finally:
        kb.close()

    print(f"\n{'='*100}\nÖLÇÜLEN: {olculen} film | KİMLİK KİLİTLİ (gerçek biliniyor): {kilitli}\n{'='*100}")
    print(f"\n### 🔴 YÖNETMEN YANLIŞ OKUMA ({len(yanlis_yon)}) — OCR geçerli-ad okumuş ama GERÇEK farklı")
    for t, y, ocr, real in yanlis_yon:
        print(f"  • {t} ({y})\n        OCR okumuş : {ocr}\n        GERÇEK     : {real}")
    print(f"\n### 🟠 YÖNETMEN ÇÖP ({len(cop_yon)}) — OCR yönetmen alanına isim-dışı şey okumuş")
    for t, y, ocr, real in cop_yon[:18]:
        print(f"  • {t} ({y})  OCR='{ocr[:45]}'  →  GERÇEK: {real}")
    print(f"\n### ⚪ YÖNETMEN OKUNAMADI ({len(okunamadi)}) — OCR boş, GERÇEK biliniyor")
    for t, y, real in okunamadi[:18]:
        print(f"  • {t} ({y})  →  GERÇEK: {real}")
    print(f"\n### 🟡 CAST YANLIŞ/GARBLE ({len(cast_garble)}) — OCR cast'i KB-gerçeğe eşleşmiyor")
    for t, y, kayip, real in cast_garble[:18]:
        print(f"  • {t} ({y})\n        OCR (eşleşmeyen): {kayip}\n        GERÇEK cast    : {real}")


if __name__ == "__main__":
    main()
