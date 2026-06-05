#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ornek8_render.py — bugünkü 44 klipten EN SORUNLU 8'ini seç, yeni kodla yeniden-render et,
ÖNCE/SONRA karşılaştır. Database'i BOZMAZ (outputs/fix_verify/ornek8/'e yazar). GLOBAL python ile koş."""
import os, sys, glob, re, subprocess, datetime, json
sys.stdout.reconfigure(encoding="utf-8")
import fitz

DB = r"E:\MITAS\Database"
OUT = r"E:\MITAS\outputs\fix_verify\ornek8"
TK = r"E:\MITAS\scripts\tek_film_kunye.py"
PY = sys.executable  # global python (bu betik onunla koşuyor)
os.makedirs(OUT, exist_ok=True)
trt_re = re.compile(r"(\d{4})-(\d{3,4})-(\d)-(\d{4})-\d{2}-\d")

def fields(p):
    if not os.path.exists(p):
        return None
    t = fitz.open(p)[0].get_text(); flat = t.replace(" ", "")
    mt = re.search(r"F İ L M|D [İI] Z [İI]", t)
    prof = mt.group(0).replace(" ", "") if mt else "?"
    mtur = re.search(r"T Ü R\s*\n([^\n]+)", t)
    tur = mtur.group(1).strip() if mtur else "—"
    mc = re.search(r"O Y U N C U L A R\s*\n(.+?)\nY A P I M", t, re.S)
    cast = [c.strip() for c in (mc.group(1).split("\n") if mc else []) if c.strip()]
    dup = [x for x in set(cast) if cast.count(x) > 1]
    my = re.search(r"Y A P I M  E K [İI] B [İI](.+?)Ö Z E T", t, re.S)
    yap = re.sub(r"\s+", " ", my.group(1)).strip() if my else "?"
    ma = re.search(r"A N A  D İ L\s*\n([^\n]+)", t)
    return {"prof": prof, "tur": tur, "cast_n": len(cast), "dup": dup,
            "bolum": ("BÖLÜM" in flat), "latin_disi": [c for c in t if c in "Əə"],
            "amp": ("&" in yap), "yap": yap[:90], "ana_dil": (ma.group(1).strip() if ma else "?"),
            "afis": len(fitz.open(p)[0].get_images())}

def score(clipname, f):
    if not f:
        return -1
    s = 0
    m = trt_re.search(clipname)
    is_dizi = bool(m) and m.group(3) == "0"
    if f["tur"] == "—": s += 1
    if f["dup"]: s += 1
    if f["latin_disi"]: s += 2
    if f["amp"]: s += 1
    if is_dizi and (f["prof"] != "DİZİ" or not f["bolum"]): s += 2  # dizi ama profil/bölüm yanlış
    return s

# bugünkü klipler
thr = datetime.datetime(2026, 6, 5, 0, 0).timestamp()
clips = []
for d in glob.glob(os.path.join(DB, "*")):
    p = os.path.join(d, "pdf", "kunye.pdf")
    if os.path.isdir(d) and os.path.exists(p) and os.path.getmtime(p) >= thr and trt_re.search(os.path.basename(d)):
        clips.append(d)

scored = []
for d in clips:
    f = fields(os.path.join(d, "pdf", "kunye.pdf"))
    scored.append((score(os.path.basename(d), f), d, f))
scored.sort(key=lambda x: -x[0])

# en sorunlu 8 — ama en az 2 dizi garanti
pick, dizi_picked = [], 0
for sc, d, f in scored:
    m = trt_re.search(os.path.basename(d))
    if m and m.group(3) == "0":
        dizi_picked += 1
    pick.append((sc, d, f))
    if len(pick) >= 8:
        break
# eğer hiç dizi yoksa, listeden bir dizi ekle
if dizi_picked == 0:
    for sc, d, f in scored:
        m = trt_re.search(os.path.basename(d))
        if m and m.group(3) == "0" and (sc, d, f) not in pick:
            pick[-1] = (sc, d, f); break

print(f"=== {len(clips)} klipten en sorunlu {len(pick)} seçildi, yeniden-render ===", flush=True)
report = []
for i, (sc, d, fold) in enumerate(pick, 1):
    name = os.path.basename(d)
    m = trt_re.search(name)
    typ, bol = (m.group(3), m.group(4)) if m else ("1", "0000")
    prof = "dizi" if typ == "0" else "film"
    out_pdf = os.path.join(OUT, f"{i:02d}_{name[:40]}.pdf")
    cmd = [PY, TK, "--clip", d, "--out", out_pdf, "--profile", prof]
    if prof == "dizi":
        cmd += ["--bolum", f"{int(bol)}. BÖLÜM"]
    print(f"[{i}/{len(pick)}] {name[:55]} (skor={sc}, {prof})", flush=True)
    try:
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    except Exception as e:
        print("   render hata:", e, flush=True)
    fnew = fields(out_pdf)
    report.append((i, name, sc, prof, fold, fnew))

# ÖNCE/SONRA raporu
lines = ["# 8 ÖRNEK — ÖNCE (eski kod, Database) / SONRA (yeni kod)\n"]
for i, name, sc, prof, fo, fn in report:
    lines.append(f"\n## {i}. {name}  (skor={sc}, {prof})")
    if not fn:
        lines.append("  SONRA: render başarısız"); continue
    def cmp(k, lbl, fmt=str):
        a = fmt(fo.get(k)) if fo else "?"; b = fmt(fn.get(k))
        mark = "  ✓" if a != b else ""
        lines.append(f"  {lbl}: ÖNCE [{a}]  →  SONRA [{b}]{mark}")
    cmp("prof", "Profil"); cmp("bolum", "Bölüm", lambda v: "VAR" if v else "yok")
    cmp("tur", "TÜR"); cmp("cast_n", "Cast adet")
    cmp("dup", "Cast tekrar", lambda v: (v or "YOK") if v != "?" else "?")
    cmp("latin_disi", "Latin-dışı", lambda v: (v or "YOK") if v != "?" else "?")
    cmp("amp", "Yapımcı '&'", lambda v: "VAR" if v else "yok")
    cmp("ana_dil", "Ana dil"); cmp("afis", "Afiş(img)")
    lines.append(f"  Yapımcı SONRA: {fn['yap']}")
rp = os.path.join(OUT, "ONCE_SONRA.md")
open(rp, "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
print(f"\n=== RAPOR: {rp} ===")
print("ORNEK8_DONE")
