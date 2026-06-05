#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""refetch_afis.py — afişi EKSİK künyeleri TMDB ile yeniden çek (MITAS_TMDB env şart).
video-okumayı ATLAR: mevcut künyeden cast/yönetmen/yapımcı çıkarıp --video-credits ile geçer
→ GPU yok, hızlı, cast korunur; tek_film_kunye cross-check'i (TMDB afiş) + render'ı yeniler.
Çıkarım boşsa TAM video-okumaya düşer (cast'i silmesin). GLOBAL python + MITAS_TMDB env."""
import os, sys, glob, re, subprocess, shutil, datetime, json
sys.stdout.reconfigure(encoding="utf-8")
import fitz
DB = r"E:\MITAS\Database"
TK = r"E:\MITAS\scripts\tek_film_kunye.py"
PY = sys.executable
DEST = r"E:\MITAS\Mitas Output\DUZELTILMIS_44"
trt_re = re.compile(r"(\d{4})-(\d{3,4})-(\d)-(\d{4})-\d{2}-\d")
thr = datetime.datetime(2026, 6, 5, 0, 0).timestamp()

def has_afis(pdf):
    try:
        d = fitz.open(pdf); pg = d[0]
    except Exception:
        return False
    for im in pg.get_images(full=True):
        try:
            info = d.extract_image(im[0])
            if info.get("width", 0) > 100 and info.get("height", 0) > 100 and len(info.get("image", b"")) > 8000:
                return True
        except Exception:
            pass
    return False

def extract_credits(pdf):
    t = fitz.open(pdf)[0].get_text()
    mc = re.search(r"O Y U N C U L A R\s*\n(.+?)\nY A P I M", t, re.S)
    cast = [c.strip() for c in (mc.group(1).split("\n") if mc else []) if c.strip() and c.strip() != "—"]
    my = re.search(r"Y A P I M  E K [İI] B [İI](.+?)Ö Z E T", t, re.S)
    blob = my.group(1) if my else ""
    yon = re.search(r"Yönetmen\s*\n(.+?)(?=\nYapımcı|\Z)", blob, re.S)
    yap = re.search(r"Yapımcı\s*\n(.+)", blob, re.S)
    def nm(b):
        return [x.strip() for x in (b.split("\n") if b else []) if x.strip() and x.strip() != "—"]
    return {"cast": cast, "yonetmen": nm(yon.group(1) if yon else ""), "yapimci": nm(yap.group(1) if yap else "")}

clips = [d for d in glob.glob(os.path.join(DB, "*"))
         if os.path.isdir(d) and os.path.exists(os.path.join(d, "pdf", "kunye.pdf"))
         and os.path.getmtime(os.path.join(d, "pdf", "kunye.pdf")) >= thr and trt_re.search(os.path.basename(d))]
target = [d for d in clips if not has_afis(os.path.join(d, "pdf", "kunye.pdf"))]
print(f"=== afişi eksik {len(target)}/{len(clips)} → TMDB ile yeniden ({'KEY VAR' if os.environ.get('MITAS_TMDB') else 'KEY YOK!'}) ===", flush=True)
got = 0
for d in sorted(target):
    name = os.path.basename(d); pdf = os.path.join(d, "pdf", "kunye.pdf")
    m = trt_re.search(name); typ, bol = m.group(3), m.group(4); prof = "dizi" if typ == "0" else "film"
    vc = extract_credits(pdf)
    tmp = os.path.join(d, "pdf", "kunye_afis.pdf")
    cmd = [PY, TK, "--clip", d, "--out", tmp, "--profile", prof]
    if vc["cast"]:                                   # cast çıkarıldı → video-okumayı ATLA (hızlı, korur)
        cmd += ["--video-credits", json.dumps(vc, ensure_ascii=False)]
    if prof == "dizi":
        cmd += ["--bolum", f"{int(bol)}. BÖLÜM"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    except Exception as e:
        print(f"X {name[:44]} HATA {type(e).__name__}", flush=True); continue
    if os.path.exists(tmp) and os.path.getsize(tmp) > 10000:
        afis_now = has_afis(tmp)
        os.replace(tmp, pdf)
        png = tmp.replace(".pdf", "_onizleme.png")
        if os.path.exists(png):
            os.replace(png, os.path.join(d, "pdf", "kunye_onizleme.png"))
        dd = os.path.join(DEST, name); os.makedirs(dd, exist_ok=True)
        for fn in ("kunye.pdf", "kunye_onizleme.png"):
            s = os.path.join(d, "pdf", fn)
            if os.path.exists(s):
                shutil.copy2(s, dd)
        got += 1 if afis_now else 0
        print(f"{'AFİŞ ✓' if afis_now else 'afiş yok'}  {name[:44]}", flush=True)
    else:
        if os.path.exists(tmp):
            os.remove(tmp)
        print(f"X {name[:44]} render başarısız (eski korundu)", flush=True)
print(f"=== {got}/{len(target)} afiş geldi ===")
print("REFETCH_DONE")
