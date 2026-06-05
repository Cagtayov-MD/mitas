#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""kunye_gozle_qc.py — DUZELTILMIS_44 künyelerini TEK TEK denetle: HARF + AFİŞ odaklı.
Katman 1 (metin/programatik): mojibake, Latin-dışı (Kiril/Ə/Yunan/Arap), kopuk-İ tek-harf, başlık/isim.
Katman 2 için: her künyenin onizleme.png yolunu listeler → ben GÖZLE açacağım.
Çıktı: DUZELTILMIS_44/GOZLE_QC.md + flag listesi. GLOBAL python."""
import os, sys, glob, re, json
sys.stdout.reconfigure(encoding="utf-8")
import fitz

SRC = r"E:\MITAS\Mitas Output\DUZELTILMIS_44"
DB = r"E:\MITAS\Database"

# Latin-dışı blok aralıkları (Türkçe Latin DIŞINDA olanlar)
def non_latin_chars(t):
    bad = []
    for ch in t:
        o = ord(ch)
        if (0x0400 <= o <= 0x04FF) or (0x0370 <= o <= 0x03FF) or (0x0600 <= o <= 0x06FF) \
           or ch in "ƏəŊŋ" or (0x4E00 <= o <= 0x9FFF):
            bad.append(ch)
    return sorted(set(bad))

MOJIBAKE = ["Ã", "Â", "�", "�", "Ä±", "Ã¶", "Ã§", "ÅŸ", "ÄŸ", "Ã¼", "â€"]

def fields(pdf):
    d = fitz.open(pdf); pg = d[0]; t = pg.get_text()
    # başlık (profil çipinden sonra)
    mt = re.search(r"F İ L M|D [İI] Z [İI]", t)
    title = "?"
    if mt:
        seg = [s.strip() for s in t[mt.end():mt.end()+90].split("\n") if s.strip()]
        title = seg[0] if seg else "?"
    # cast + crew bloğu
    mcc = re.search(r"O Y U N C U L A R(.+?)Ö Z E T", t, re.S)
    names_blob = mcc.group(1) if mcc else ""
    # afiş: gömülü görseller
    imgs = []
    for im in pg.get_images(full=True):
        try:
            info = d.extract_image(im[0])
            imgs.append((info.get("width", 0), info.get("height", 0), len(info.get("image", b""))))
        except Exception:
            pass
    big = [(w, h, sz) for (w, h, sz) in imgs if w > 100 and h > 100 and sz > 8000]
    afis_ok = bool(big)
    aspect = round(big[0][0] / big[0][1], 2) if big else 0
    # harf
    moj = [m for m in MOJIBAKE if m in t]
    nonlat = non_latin_chars(t)
    lone = [w for w in title.split() if len(w) == 1 and not w.isdigit()]
    return {"title": title, "moj": moj, "nonlat": nonlat, "lone": lone,
            "afis_ok": afis_ok, "afis_n": len(big), "aspect": aspect,
            "names": re.sub(r"\s+", " ", names_blob).strip()[:160]}

def onizleme(clipname):
    for base in (SRC, DB):
        p = os.path.join(base, clipname, "kunye_onizleme.png")
        if os.path.exists(p):
            return p
        p2 = os.path.join(DB, clipname, "pdf", "kunye_onizleme.png")
        if os.path.exists(p2):
            return p2
    return None

clips = sorted(glob.glob(os.path.join(SRC, "*")))
clips = [c for c in clips if os.path.isdir(c) and os.path.exists(os.path.join(c, "kunye.pdf"))]
print(f"=== {len(clips)} künye gözle-QC ===")
rows, flagged = [], []
for c in clips:
    name = os.path.basename(c)
    try:
        f = fields(os.path.join(c, "kunye.pdf"))
    except Exception as e:
        rows.append((name, f"HATA {type(e).__name__}", None)); flagged.append(name); continue
    harf_bad = bool(f["moj"] or f["nonlat"] or f["lone"])
    issues = []
    if f["moj"]: issues.append(f"MOJIBAKE{f['moj']}")
    if f["nonlat"]: issues.append(f"LATIN-DIŞI{f['nonlat']}")
    if f["lone"]: issues.append(f"KOPUK-HARF{f['lone']}")
    if not f["afis_ok"]: issues.append("AFİŞ-YOK")
    verdict = "TEMİZ" if not issues else "SORUNLU"
    if issues: flagged.append(name)
    rows.append((name, verdict, f, issues, onizleme(name)))

lines = ["# GÖZLE-QC (HARF + AFİŞ) — DUZELTILMIS_44\n"]
temiz = sum(1 for r in rows if len(r) > 1 and r[1] == "TEMİZ")
lines.append(f"TEMİZ {temiz} / {len(rows)}  ·  SORUNLU {len(rows)-temiz}\n")
for r in rows:
    if len(r) < 5:
        lines.append(f"[X] {r[0]}  {r[1]}"); continue
    name, verdict, f, issues, png = r
    lines.append(f"\n## [{verdict}] {name}")
    lines.append(f"  başlık: {f['title']}  | afiş: {'VAR' if f['afis_ok'] else 'YOK'} ({f['afis_n']}, oran {f['aspect']})")
    if issues: lines.append(f"  ⚠ {' · '.join(issues)}")
    lines.append(f"  png: {png}")
out = os.path.join(SRC, "GOZLE_QC.md")
open(out, "w", encoding="utf-8").write("\n".join(lines))
# flagged + tüm png yolları (gözle açmam için)
pngs = [r[4] for r in rows if len(r) >= 5 and r[4]]
json.dump({"flagged": flagged, "pngs": pngs, "temiz": temiz, "total": len(rows)},
          open(os.path.join(SRC, "GOZLE_QC.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"TEMİZ {temiz}/{len(rows)} · SORUNLU {len(rows)-temiz}")
print("flagged:", flagged)
print(f"RAPOR: {out}")
print("GOZLEQC_DONE")
