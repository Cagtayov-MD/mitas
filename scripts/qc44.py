#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""qc44.py — DUZELTILMIS_44 künyelerinin MEKANİK denetimi (sonra gözle açılacak şüpheliler).
Kontrol: afiş(afis.jpg) var mı · özet bozuk/kısa mı · özet BÜYÜK-HARF mi (v4) · SES&ALTYAZI var mı ·
Latin-harici (Kiril/Azeri) karakter var mı · ana_dil var mı. Çıktı: tablo + ŞÜPHELİ listesi."""
import os, sys, re, glob
sys.stdout.reconfigure(encoding="utf-8")
DEST = r"E:\MITAS\Mitas Output\DUZELTILMIS_44"
DB = r"E:\MITAS\Database"
META = ["TRANSKR", "TRANSCR", " ASR ", "GÜRÜLTÜ", "OKUNAMA", "ANLAŞILMAZ", "ANLAŞIL",
        "ÇIKARMAK MÜMKÜN", "ANLAMLI BİR OLAY", "YETERLİ OLAY", "BELİRSİZ DİL", "TESPİT EDİLEMEDİ"]
NONLATIN = re.compile(r"[Ѐ-ӿəƏ]")   # Kiril + Azeri ə/Ə
TRT = re.compile(r"(\d{4}-\d{3,4}-\d-\d{4})")


def resolve_db(name):
    clip = name.split("--", 1)[-1] if "--" in name else name
    if os.path.isdir(os.path.join(DB, clip)):
        return os.path.join(DB, clip)
    m = TRT.search(name)
    if m:
        g = glob.glob(os.path.join(DB, f"*{m.group(1)}*"))
        if g:
            return g[0]
    return None


def garbled(oz):
    u = " " + oz.upper() + " "
    return (len(oz) < 45) or any(w in u for w in META)


def parse_md(p):
    t = open(p, encoding="utf-8").read()
    mt = re.search(r"#\s*M[İI]TAS\s*[•·]\s*[^•·\n]+[•·]\s*(.+)", t)
    title = mt.group(1).strip() if mt else "?"
    ma = re.search(r"Ana dil:\s*(.+)", t)
    ad = ma.group(1).strip() if ma else "?"
    mo = re.search(r"##\s*Özet\s*\n(.+)", t, re.S)
    oz = re.sub(r"\s+", " ", mo.group(1)).strip() if mo else ""
    ses = ("SES" in t.upper() and "ALTYA" in t.upper())
    tur = bool(re.search(r"T[ÜU]R\s*[:•]", t.upper())) or ("TÜR" in t.upper())
    return title, ad, oz, ses, tur


rows, flags = [], []
names = sorted(n for n in os.listdir(DEST) if os.path.isdir(os.path.join(DEST, n)))
for name in names:
    dbd = resolve_db(name)
    if not dbd:
        flags.append((name[:48], "DB-DIR-YOK")); continue
    pdfd = os.path.join(dbd, "pdf")
    afis = os.path.exists(os.path.join(pdfd, "afis.jpg"))
    md = os.path.join(pdfd, "kunye_teslim.md")
    if not os.path.exists(md):
        flags.append((name[:48], "MD-YOK")); continue
    title, ad, oz, ses, tur = parse_md(md)
    g = garbled(oz)
    # özet büyük-harf mi? (harflerin çoğu büyük olmalı — v4)
    letters = [ch for ch in oz if ch.isalpha()]
    upper_ratio = (sum(ch.isupper() for ch in letters) / len(letters)) if letters else 1.0
    not_caps = upper_ratio < 0.85
    nonlatin = bool(NONLATIN.search(title)) or bool(NONLATIN.search(oz))
    issues = []
    if not afis: issues.append("AFİŞ-YOK")
    if g: issues.append("ÖZET-BOZUK")
    elif not_caps: issues.append(f"ÖZET-küçükharf({upper_ratio:.0%})")
    if not ses: issues.append("SES&ALTYAZI-YOK")
    if not tur: issues.append("TÜR-YOK")
    if nonlatin: issues.append("LATİN-HARİCİ")
    if ad in ("?", ""): issues.append("ANADİL-YOK")
    rows.append((title[:30], "afiş✓" if afis else "afiş✗", ad[:12], len(oz), "BOZUK" if g else ("küçük" if not_caps else "ok")))
    if issues:
        flags.append((title[:38] + " | " + os.path.basename(dbd)[:24], " · ".join(issues)))

print(f"=== QC44 — {len(names)} künye ===")
print(f"{'BAŞLIK':30} {'afiş':6} {'ana_dil':12} {'özet#':>5} {'özet'}")
for r in rows:
    print(f"{r[0]:30} {r[1]:6} {r[2]:12} {r[3]:>5} {r[4]}")
print(f"\n=== ŞÜPHELİ / SORUN ({len(flags)}) ===")
for f in flags:
    print(f"  ⚠ {f[0]:64} → {f[1]}")
if not flags:
    print("  (mekanik sorun yok — yine de gözle örnekleme yapılmalı)")
print("QC44_DONE")
