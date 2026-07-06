# -*- coding: utf-8 -*-
"""REGRESYON-GOLDEN (2026-07-06): bugünkü tüm künye-okuma fixlerini kapsayan bilinen-vaka testi.
Her değişiklikten SONRA koşulur → yeni-yanlış/regresyon yakalar. Metin-yolu (_pipe_credit_text),
gerçek OCR-çıktısı üzerinde, ollama gerektirir. Çıktı: PASS/FAIL tablosu + genel hüküm."""
import sys, glob, os, subprocess, json, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PY = r"C:\Users\TRT03\AppData\Local\Programs\Python\Python310\python.exe"
DB = r"E:\MITAS\Database"

# (film-deseni, başlık, beklenen-yönetmen-alt-dizgisi VEYA "" = boş-olmalı, açıklama)
VAKALAR = [
    ("*1990-0285*",            "TOPLU GÖSTERİLER",   "Minnelli",     "çok-varyant fuzzy: garble→KB-kanonik"),
    ("CENNETE GELD*",          "CENNETE GELDİK Mİ",  "Caldana",      "fabrikasyon-freni: temiz KB-yok isim korunur"),
    ("BAŞKAN VE MARI*",        "BAŞKAN VE MARI",     "Rochefoucauld","FR MISE EN SCENE + soy-bağlaç token-cap"),
    ("TILSIMLI*",              "TILSIMLI DÜNYA",     "",             "dublaj-freni: yön boş kalmalı"),
    ("HALIFAX*",               "HALIFAX",            "Cameron",      "devised-by fren + normal dolu"),
    ("BUZDAN GELEN*",          "BUZDAN GELEN SESLER","Johnson",      "rescue: DIRECTED & PHOTOGRAPHED kombine"),
    ("*1976-0184*",            "ANGOLA'DAN KAÇIŞ",   "Martinson",    "orta/baş-harf toleransı: ekran 'Leslie Martinson' → KB 'Leslie H. Martinson' köprü"),
]


def kunye_yon(patt, title):
    g = glob.glob(os.path.join(DB, patt))
    if not g:
        return None, "hub-yok"
    ks = sorted([q for q in glob.glob(os.path.join(g[0], "ocr", "ocr-*", "kunye.txt")) if "-fb" not in q],
                key=os.path.getmtime)
    if not ks:
        return None, "kunye-yok"
    r = subprocess.run([PY, r"E:\MITAS\scripts\_pipe_credit_text.py", "--ocr", ks[-1],
                        "--title", title, "--profile", "film"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    j = None
    for l in (r.stdout or "").strip().splitlines()[::-1]:
        try:
            j = json.loads(l); break
        except Exception:
            pass
    return (j or {}).get("yonetmen"), ((j or {}).get("guven") or "")[:40]


def main():
    print("=== REGRESYON-GOLDEN (künye-okuma) ===")
    gecti = 0
    for patt, title, bekle, aciklama in VAKALAR:
        yon, guv = kunye_yon(patt, title)
        yon_s = ", ".join(yon) if yon else ""
        if bekle == "":
            ok = (not yon)
        else:
            ok = bool(yon) and any(bekle.lower() in n.lower() for n in yon)
        gecti += ok
        print(f"  {'PASS' if ok else 'FAIL':4s} {title:22s} bekle={bekle or '(boş)':14s} → {yon_s or '(boş)':28s} | {aciklama}")
    print(f"\n=== SONUÇ: {gecti}/{len(VAKALAR)} — {'TEMİZ' if gecti == len(VAKALAR) else 'REGRESYON VAR!'}")
    return 0 if gecti == len(VAKALAR) else 1


if __name__ == "__main__":
    sys.exit(main())
