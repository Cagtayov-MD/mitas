# -*- coding: utf-8 -*-
"""Tier-1 consensus demosu: OneOCR + GLM-OCR master'i okur.

Ortak okunan satir -> GECER. Ayrisan satir -> SUPHELI -> kirpilir (VLM'e bu gider).
Amac: 'koca frame degil, avuc dolusu kirpim gidiyor'u GORSEL gostermek.

Master cok uzun -> seritlere bolunur, her serit iki motorla okunur.

Kullanim (ocr venv):
  venvs/ocr/Scripts/python.exe scripts/_consensus_demo.py "<master.png>" "<outdir>"
"""
from __future__ import annotations
import sys, time, base64, json, re, difflib, urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, r"E:\MITAS")
from PIL import Image, ImageOps, ImageEnhance  # noqa: E402
from core.pipelines.ocr.credit_experiment import OneOcrEngine, PaddleOcrEngine  # noqa: E402

OLLAMA = "http://localhost:11434/api/generate"
GLM = "glm-ocr:latest"
MASTER = Path(sys.argv[1])
OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
STRIP_H = 1400
MATCH = 0.70  # fuzzy benzerlik esigi (>= => ortak)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9çğıöşü]", "", s.lower())


def box_of(r):
    for k in ("bbox", "box", "polygon", "points", "quad", "poly", "rect"):
        v = r.get(k)
        if v:
            return v
    return None


def rect(box):
    import numpy as np
    a = np.array(box, dtype=float).reshape(-1)
    xs, ys = a[0::2], a[1::2]
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def glm_lines(img_path: Path) -> list[str]:
    payload = {"model": GLM, "prompt": "Read ALL text in this image. Output every visible text line, one per line, plain text only. No commentary.",
               "images": [base64.b64encode(img_path.read_bytes()).decode()], "stream": False,
               "options": {"temperature": 0, "num_predict": 700, "repeat_penalty": 1.3}}
    req = urllib.request.Request(OLLAMA, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=150) as r:
            resp = json.loads(r.read()).get("response", "")
        return [l.strip() for l in resp.splitlines() if l.strip()]
    except Exception as exc:
        print(f"    [GLM atlandı: {type(exc).__name__}]")
        return []


def main():
    t0 = time.time()
    im = Image.open(MASTER).convert("RGB")
    W, H = im.size
    print(f"MASTER {W}x{H} | şerit {STRIP_H}px -> {-(-H // STRIP_H)} şerit")
    eng = OneOcrEngine()
    eng2 = PaddleOcrEngine()  # ikinci okuyucu: deterministik, hizli (GLM bulk'ta asiliyordu)

    lines = []  # (x0,gy0,x1,gy1, text, agree, ratio, gmatch)
    one_t = glm_t = 0.0
    y = 0
    si = 0
    while y < H:
        strip = im.crop((0, y, W, min(H, y + STRIP_H)))
        sp = OUT / f"_strip_{si:02d}.png"; strip.save(sp)
        t = time.time(); recs = eng.recognize(sp, strategy="consensus"); one_t += time.time() - t
        t = time.time(); precs = eng2.recognize(sp, strategy="consensus2"); glm_t += time.time() - t
        gl = [str(r.get("text", "")).strip() for r in precs if str(r.get("text", "")).strip()]
        gnorm = [norm(g) for g in gl]
        for r in recs:
            txt = str(r.get("text", "")).strip()
            if len(norm(txt)) < 2:
                continue
            b = box_of(r)
            if not b:
                continue
            x0, ly0, x1, ly1 = rect(b)
            nt = norm(txt)
            ratio, gmatch = 0.0, ""
            for g, gn in zip(gl, gnorm):
                rr = difflib.SequenceMatcher(None, nt, gn).ratio()
                if rr > ratio:
                    ratio, gmatch = rr, g
            lines.append((x0, y + ly0, x1, y + ly1, txt, ratio >= MATCH, round(ratio, 2), gmatch))
        si += 1; y += STRIP_H
        print(f"  şerit {si}/{-(-H//STRIP_H)}  OneOCR {len(recs)} | Paddle {len(gl)} satır")

    agree = [l for l in lines if l[5]]
    susp = [l for l in lines if not l[5]]
    print("\n" + "=" * 60)
    print(f"TOPLAM OneOCR satır : {len(lines)}")
    print(f"ORTAK (geçer)       : {len(agree)}  (%{100*len(agree)//max(1,len(lines))})")
    print(f"ŞÜPHELİ (VLM'e kırp) : {len(susp)}  (%{100*len(susp)//max(1,len(lines))})")
    print("\nşüpheli örnekler (OneOCR metni | en yakın Paddle | benzerlik):")
    for x0, gy0, x1, gy1, txt, ok, rr, gm in susp[:15]:
        print(f"  '{txt[:34]}'  |  '{gm[:28]}'  |  {rr}")

    # şüpheli kırpımları master'dan kes -> 3x büyüt + kontrast -> OKUNUR montaj
    SCALE = 3
    pad = 6
    crop_dir = OUT / "kirpimlar"; crop_dir.mkdir(exist_ok=True)
    proc = []
    for i, (x0, gy0, x1, gy1, txt, ok, rr, gm) in enumerate(susp):
        c = im.crop((max(0, x0 - pad), max(0, gy0 - pad), min(W, x1 + pad), min(H, gy1 + pad)))
        if c.width <= 5 or c.height <= 5:
            continue
        big = c.resize((c.width * SCALE, c.height * SCALE), Image.LANCZOS)
        big = ImageOps.autocontrast(big, cutoff=1)
        big = ImageEnhance.Brightness(big).enhance(1.5)
        big.save(crop_dir / f"susp_{i:03d}.png")
        proc.append((big, txt, gm))
    if proc:
        SHOW = proc[:24]  # okunur örneklem
        cw = max(b.width for b, _, _ in SHOW)
        gap = 18
        montage = Image.new("RGB", (cw + 24, sum(b.height + gap for b, _, _ in SHOW) + 24), (20, 20, 20))
        yy = 12
        for b, txt, gm in SHOW:
            montage.paste(b, (12, yy)); yy += b.height + gap
        mp = OUT / "_SUPHELI_OKUNUR.png"
        montage.save(mp)
        print(f"\nOKUNUR MONTAJ (ilk {len(SHOW)}/{len(proc)}): {mp}  ({montage.size[0]}x{montage.size[1]})")

    print("=" * 60)
    print(f"ZAMAN: toplam {time.time()-t0:.0f}s | OneOCR {one_t:.0f}s | Paddle {glm_t:.0f}s")
    print(f"ÇIKTI: {OUT}")


if __name__ == "__main__":
    main()
