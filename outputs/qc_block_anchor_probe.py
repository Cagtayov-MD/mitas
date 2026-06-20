# -*- coding: utf-8 -*-
"""qc_block_anchor_probe.py — ÇAPA-3 (yönetmen-önce kilit) hedefli ölçüm.

Teşhiste 'okunabilir yönetmen ama kilit yok' çıkan filmleri tek tek qc_credit_block'tan
geçirir; director-anchor'ın artık kilitleyip kilitlemediğini + tier'ını (strong/weak) gösterir.
"""
import os, re, sys, glob, importlib.util
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.pop("MITAS_TMDB", None); os.environ.pop("TMDB_API_KEY", None)
import credit_qc_block as q
import credit_crosscheck as cc
_spec = importlib.util.spec_from_file_location("ab", os.path.join(HERE, "qc_block_ab_batch.py"))
ab = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ab)

# Teşhisten: okunabilir-yönetmen-ama-kilit-yok adayları (title-fragment)
FILMS = ["SEVGİLİ ANGELO", "ALTIN YUMURTLAYAN TAVUK", "AKREBİN LANETİ", "BATIDAN GELEN ADAM",
         "BAŞARININ BEDELİ", "BİR SEVGİ İSTİYORUM", "ARTİSTLER TATİLDE", "PARALEL YAŞAMLAR"]


def _find(frag):
    for d in glob.glob(os.path.join(ROOT, "Database", "*")):
        if frag.lower().replace("i̇", "i") in os.path.basename(d).lower().replace("i̇", "i"):
            return d
    return None


def main():
    kb = cc.CreditKB()
    try:
        for frag in FILMS:
            folder = _find(frag)
            if not folder:
                print(f"• {frag}: klasör bulunamadı"); continue
            txts = [p for p in glob.glob(os.path.join(folder, "*.txt")) if not p.endswith("_teknik.txt")]
            if not txts:
                print(f"• {frag}: .txt yok"); continue
            title, year = ab._parse_folder(os.path.basename(folder))
            yon, cast, yap, ozet = ab._parse_txt(txts[0])
            res = q.qc_credit_block(yon, cast, yap, title=title, year=year, ozet=ozet,
                                    afis_yolu=(os.path.join(folder, "afis.jpg")
                                               if os.path.exists(os.path.join(folder, "afis.jpg")) else None), kb=kb)
            anchor = [x for x in res["kaynak_izi"] if x.get("adim") == "director_anchor"]
            kanit = anchor[0].get("kanit") if anchor else "—"
            print(f"• {title} ({year})")
            print(f"    OCR-yön: {yon}")
            print(f"    → {res['karar']}/{res['kontrol_tip'] or '-'} | kilit={'E' if res['kimlik']['locked'] else 'h'}"
                  f" | method={res['kimlik']['method']} | yön={res['temiz_yon']} | cast={res['floor']['ulasilan']}")
            print(f"    çapa: {kanit}")
    finally:
        kb.close()


if __name__ == "__main__":
    main()
