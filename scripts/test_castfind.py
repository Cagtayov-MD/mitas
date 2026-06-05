#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_castfind.py — KADEME 1 ölçümü: TÜR'ü boş (un-identified) filmlerin okunan cast'iyle
credit_kb_lookup'ı (yeni cast_find) koş, kaçı YENİ tanındı (eslesen+TÜR+imdb_id) say.
venvs/ocr python ile koş (duckdb)."""
import sys, os, re, glob, json, subprocess, datetime
sys.stdout.reconfigure(encoding="utf-8")
import fitz
DB = r"E:\MITAS\Database"
KB = r"E:\MITAS\scripts\credit_kb_lookup.py"
PY = r"E:\MITAS\venvs\ocr\Scripts\python.exe"   # credit_kb_lookup duckdb ister (PY_OCR)
trt = re.compile(r"\d{4}-\d{3,4}-\d-\d{4}-\d{2}-\d")
thr = datetime.datetime(2026, 6, 5, 0, 0).timestamp()

def info(pdf):
    t = fitz.open(pdf)[0].get_text()
    mt = re.search(r"F İ L M|D [İI] Z [İI]", t)
    title = ([s.strip() for s in t[mt.end():mt.end()+80].split("\n") if s.strip()][0] if mt else "")
    mtur = re.search(r"T Ü R\s*\n([^\n]+)", t)
    tur = mtur.group(1).strip() if mtur else "—"
    mc = re.search(r"O Y U N C U L A R\s*\n(.+?)\nY A P I M", t, re.S)
    cast = [c.strip() for c in (mc.group(1).split("\n") if mc else []) if c.strip() and c.strip() != "—"]
    my = re.search(r"Y A P I M  E K [İI] B [İI](.+?)Ö Z E T", t, re.S)
    blob = my.group(1) if my else ""
    yon = re.search(r"Yönetmen\s*\n(.+?)(?=\nYapımcı|\Z)", blob, re.S)
    yonetmen = (yon.group(1).split("\n")[0].strip() if yon else "")
    return title, tur, yonetmen, cast

clips = [d for d in glob.glob(os.path.join(DB, "*"))
         if os.path.isdir(d) and os.path.exists(os.path.join(d, "pdf", "kunye.pdf"))
         and os.path.getmtime(os.path.join(d, "pdf", "kunye.pdf")) >= thr and trt.search(os.path.basename(d))]
unident = []
for d in clips:
    title, tur, yon, cast = info(os.path.join(d, "pdf", "kunye.pdf"))
    if tur in ("—", "") and cast:
        unident.append((title, yon, cast))
print(f"=== un-identified (TÜR boş) + cast'i olan: {len(unident)} film ===", flush=True)
yeni = 0
for title, yon, cast in unident:
    try:
        r = subprocess.run([PY, KB, "--baslik", title, "--yonetmen", yon, "--cast", ",".join(cast)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        o = json.loads([l for l in r.stdout.splitlines() if l.strip().startswith("{")][-1])
    except Exception as e:
        o = {"_err": type(e).__name__}
    ident = bool(o.get("eslesen_film")) and bool(o.get("imdb_id"))
    if ident:
        yeni += 1
    print(f"  {'YENİ ✓' if ident else '  --- '} {title[:26]:26} cast={cast[:2]} → eslesen={o.get('eslesen_film')!r} tür={o.get('tur')!r} imdb={o.get('imdb_id')} ov={o.get('cast_ortusme')}", flush=True)
print(f"=== KADEME 1 ile YENİ tanınan: {yeni}/{len(unident)} ===")
print("TEST_DONE")
