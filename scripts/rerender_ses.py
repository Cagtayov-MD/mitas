#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""rerender_ses.py — SES-sorunlu (ana_dil≠TR+altyazı HAYIR) reprocess filmlerini tek_film_kunye ile
YENİDEN render et (reprocess'in iç v4-finalize'ı bazılarında başarısız → EF/Ə kaldı). md (taze SES) okunur,
v4 fix'leri (EF-filtre, Ə→E, dedup) uygulanır. temp→validate→replace (güvenli). GLOBAL python."""
import os, sys, glob, re, subprocess, shutil, datetime
sys.stdout.reconfigure(encoding="utf-8")
import fitz
DB = r"E:\MITAS\Database"
TK = r"E:\MITAS\scripts\tek_film_kunye.py"
PY = sys.executable
DEST = r"E:\MITAS\Mitas Output\DUZELTILMIS_44"
trt_re = re.compile(r"(\d{4})-(\d{3,4})-(\d)-(\d{4})-\d{2}-\d")
thr = datetime.datetime(2026, 6, 5, 0, 0).timestamp()

def adil(p):
    t = fitz.open(p)[0].get_text()
    ma = re.search(r"A N A  D İ L\s*\n([A-ZÇĞİÖŞÜ—]+)", t)
    al = re.search(r"A L T Y A Z I\s*\n([A-ZÇĞİÖŞÜ]+)", t)
    nl = [c for c in t if c in "Əə"]
    return (ma.group(1).strip() if ma else "?"), (al.group(1).strip() if al else "?"), nl

clips = [d for d in glob.glob(os.path.join(DB, "*"))
         if os.path.isdir(d) and os.path.exists(os.path.join(d, "pdf", "kunye.pdf"))
         and os.path.getmtime(os.path.join(d, "pdf", "kunye.pdf")) >= thr and trt_re.search(os.path.basename(d))]
done = 0
for d in clips:
    pdf = os.path.join(d, "pdf", "kunye.pdf")
    ad, alt, _ = adil(pdf)
    if not (ad not in ("TR", "—", "?") and alt == "HAYIR"):
        continue
    name = os.path.basename(d)
    m = trt_re.search(name); typ, bol = m.group(3), m.group(4)
    prof = "dizi" if typ == "0" else "film"
    tmp = os.path.join(d, "pdf", "kunye_re2.pdf")
    cmd = [PY, TK, "--clip", d, "--out", tmp, "--profile", prof]
    if prof == "dizi":
        cmd += ["--bolum", f"{int(bol)}. BÖLÜM"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    except Exception as e:
        print(f"X {name[:45]} HATA {type(e).__name__}", flush=True); continue
    if os.path.exists(tmp) and os.path.getsize(tmp) > 10000:
        os.replace(tmp, pdf)
        png = tmp.replace(".pdf", "_onizleme.png")
        if os.path.exists(png):
            os.replace(png, os.path.join(d, "pdf", "kunye_onizleme.png"))
        dd = os.path.join(DEST, name); os.makedirs(dd, exist_ok=True)
        for fn in ("kunye.pdf", "kunye_onizleme.png"):
            s = os.path.join(d, "pdf", fn)
            if os.path.exists(s):
                shutil.copy2(s, dd)
        ad2, _, nl2 = adil(pdf)
        done += 1
        print(f"OK {name[:45]} ses {ad}->{ad2} Latin-dışı={nl2 or 'YOK'}", flush=True)
    else:
        if os.path.exists(tmp):
            os.remove(tmp)
        print(f"X {name[:45]} render başarısız (eski korundu)", flush=True)
print(f"=== {done} SES-bad yeniden render ===")
print("RERENDER_DONE")
