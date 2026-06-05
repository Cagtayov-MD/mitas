#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""refix_44.py — bugünkü ~41 künyeyi YENİ kodla düzelt:
  - SES-sorunlu (ana_dil∉{TR,—} + altyazı HAYIR) + API key + kaynak → mitas_pipeline TAM yeniden-işle (SES dahil)
  - diğerleri → tek_film_kunye re-render (montaj fix; hızlı, ASR yok, md özetini korur)
  Database'i validate-before-replace ile günceller + Mitas Output/DUZELTILMIS_44'e toplar.
ÇALIŞTIR: GLOBAL python + ANTHROPIC_API_KEY env (reprocess özeti için)."""
import os, sys, glob, re, subprocess, shutil, datetime
sys.stdout.reconfigure(encoding="utf-8")
import fitz

ROOT = r"E:\MITAS"
DB = r"E:\MITAS\Database"
TK = r"E:\MITAS\scripts\tek_film_kunye.py"
PIPE = r"E:\MITAS\scripts\mitas_pipeline.py"
PY_PDF = sys.executable
PY_ASR = r"E:\MITAS\venvs\asr\Scripts\python.exe"
DEST = r"E:\MITAS\Mitas Output\DUZELTILMIS_44"
os.makedirs(DEST, exist_ok=True)
trt_re = re.compile(r"(\d{4})-(\d{3,4})-(\d)-(\d{4})-\d{2}-\d")
HAS_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))

def ana_dil_alt(p):
    try:
        t = fitz.open(p)[0].get_text()
    except Exception:
        return "?", "?"
    ma = re.search(r"A N A  D İ L\s*\n([A-ZÇĞİÖŞÜ—]+)", t)
    al = re.search(r"A L T Y A Z I\s*\n([A-ZÇĞİÖŞÜ]+)", t)
    return (ma.group(1).strip() if ma else "?"), (al.group(1).strip() if al else "?")

def profile_bolum(name):
    m = trt_re.search(name)
    if not m:
        return "film", None
    typ, bol = m.group(3), m.group(4)
    return ("dizi", f"{int(bol)}. BÖLÜM") if typ == "0" else ("film", None)

def find_source(clipdir):
    for ext in ("*.mp4", "*.mxf", "*.MP4", "*.MXF"):
        g = glob.glob(os.path.join(clipdir, "source", ext))
        if g:
            return g[0]
    return None

thr = datetime.datetime(2026, 6, 5, 0, 0).timestamp()
clips = [d for d in glob.glob(os.path.join(DB, "*"))
         if os.path.isdir(d) and os.path.exists(os.path.join(d, "pdf", "kunye.pdf"))
         and os.path.getmtime(os.path.join(d, "pdf", "kunye.pdf")) >= thr and trt_re.search(os.path.basename(d))]
clips.sort()
print(f"=== {len(clips)} klip | API key={'VAR' if HAS_KEY else 'YOK'} ===", flush=True)

report = []
for i, d in enumerate(clips, 1):
    name = os.path.basename(d)
    pdf = os.path.join(d, "pdf", "kunye.pdf")
    ad, alt = ana_dil_alt(pdf)
    ses_bad = (ad not in ("TR", "—", "?")) and (alt == "HAYIR")
    prof, bol = profile_bolum(name)
    src = find_source(d)
    method, ok = "", False
    try:
        if ses_bad and HAS_KEY and src:
            method = f"reprocess({ad})"
            subprocess.run([PY_ASR, PIPE, "--video", src, "--profile", "film_dizi", "--no-copy-source"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           cwd=ROOT, timeout=5400)
            ok = os.path.exists(pdf)
        else:
            method = "render" + (f"(SES {ad} elde)" if ses_bad else "")
            tmp = os.path.join(d, "pdf", "kunye_refix.pdf")
            cmd = [PY_PDF, TK, "--clip", d, "--out", tmp, "--profile", prof]
            if bol:
                cmd += ["--bolum", bol]
            subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
            if os.path.exists(tmp) and os.path.getsize(tmp) > 10000:
                os.replace(tmp, pdf)
                png = tmp.replace(".pdf", "_onizleme.png")
                if os.path.exists(png):
                    os.replace(png, os.path.join(d, "pdf", "kunye_onizleme.png"))
                ok = True
            elif os.path.exists(tmp):
                os.remove(tmp)
        if ok:
            dd = os.path.join(DEST, name)
            os.makedirs(dd, exist_ok=True)
            for fn in ("kunye.pdf", "kunye_onizleme.png"):
                s = os.path.join(d, "pdf", fn)
                if os.path.exists(s):
                    shutil.copy2(s, dd)
    except Exception as e:
        method += f" HATA:{type(e).__name__}"
    ad2, _ = ana_dil_alt(pdf)
    report.append((i, name[:46], method, "OK" if ok else "X", f"{ad}->{ad2}"))
    print(f"[{i}/{len(clips)}] {'OK' if ok else 'X '} {method:20} {name[:46]}", flush=True)

nok = sum(1 for r in report if r[3] == "OK")
lines = ["# 41 KÜNYE DÜZELTME RAPORU\n", f"API key: {'VAR' if HAS_KEY else 'YOK'} · Başarı: {nok}/{len(report)}\n"]
for i, n, m, s, ses in report:
    lines.append(f"[{s}] {i:02d} {m:22} ses:{ses:11} {n}")
open(os.path.join(DEST, "RAPOR.md"), "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
print(f"\n=== KLASÖR: {DEST} ===")
print("REFIX44_DONE")
