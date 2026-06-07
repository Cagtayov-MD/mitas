#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Yeni OCR-metin okuyucuyla (VLM yok) tek_film_kunye'yi ÇOK filmde koş + v4 raporunu topla.
Mevcut-OCR'lı Database film klipleri (TRT tip=1) üzerinde geniş kredi-kalite denetimi.
Çıktı: outputs/_wire_audit.json + ekrana özet tablo.
"""
import glob, json, os, re, subprocess, sys

PY = r"C:\Users\TRT03\AppData\Local\Programs\Python\Python310\python.exe"
HERE = r"E:\MITAS\scripts"
DB = r"E:\MITAS\Database"
OUTDIR = r"E:\MITAS\outputs\_wire_audit"
os.makedirs(OUTDIR, exist_ok=True)

def discover():
    """ocr/kunye.txt olan, TRT tip=1 (film) klipler. Başlığı klasör adından çıkar."""
    out = []
    for d in sorted(glob.glob(os.path.join(DB, "*"))):
        if not os.path.isdir(d):
            continue
        if not glob.glob(os.path.join(d, "ocr", "*", "kunye.txt")):
            continue
        name = os.path.basename(d)
        m = re.search(r"(\d{4})-(\d{3,4})-(\d)-(\d{3,4})-(\d{2})-(\d)", name)
        if not m or m.group(3) != "1":   # yalnız FİLM (tip=1)
            continue
        title = name[m.end():].lstrip("-_ ").replace("_", " ").strip(" -_")
        title = re.sub(r"\s{2,}", " ", title) or name
        out.append((d, title))
    return out

def run_one(clip, title):
    out_pdf = os.path.join(OUTDIR, re.sub(r"\W+", "_", title)[:40] + ".pdf")
    cmd = [PY, os.path.join(HERE, "tek_film_kunye.py"), "--clip", clip, "--title", title,
           "--out", out_pdf, "--profile", "film"]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="ignore", timeout=300, env=env)
        t = p.stdout or ""
        i = t.find("{")
        j = json.JSONDecoder().raw_decode(t[i:])[0] if i >= 0 else {}
        a = j.get("adimlar", {})
        return {"title": title, "ok": True,
                "yon": (j.get("v4") or {}).get("yonetmen"),
                "yon_teyit": (a.get("cross_check") or {}).get("yon_ocr_teyit"),
                "yon_kaynak": (a.get("cross_check") or {}).get("yonetmen_kaynak"),
                "verdict": (a.get("cross_check") or {}).get("verdict"),
                "cast_ov": (a.get("cross_check") or {}).get("cast_ortusme"),
                "cast_okunan": (a.get("video_okuma") or {}).get("cast_okunan"),
                "cast_n": (j.get("v4") or {}).get("cast"),
                "afis": (j.get("v4") or {}).get("afis"),
                "tur": (j.get("v4") or {}).get("tur"),
                "model": (a.get("video_okuma") or {}).get("guven")}
    except Exception as e:
        return {"title": title, "ok": False, "hata": f"{type(e).__name__}: {e}"}

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    films = discover()
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else len(films)
    films = films[:lim]
    print(f"# {len(films)} film denetleniyor (yeni OCR-metin okuyucu, VLM yok)\n")
    results = []
    for i, (clip, title) in enumerate(films, 1):
        r = run_one(clip, title)
        results.append(r)
        if r["ok"]:
            print(f"[{i}/{len(films)}] {title}")
            print(f"    YÖN={r['yon']}  teyit={r['yon_teyit']}  verdict={r['verdict']}  cast_ov={r['cast_ov']}")
            print(f"    CAST({r['cast_n']})={r['cast_okunan']}")
            print(f"    afiş={r['afis']}  tür={r['tur']}")
        else:
            print(f"[{i}/{len(films)}] {title}  HATA: {r['hata']}")
        sys.stdout.flush()
    json.dump(results, open(os.path.join(r"E:\MITAS\outputs", "_wire_audit.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n# bitti → outputs/_wire_audit.json")

if __name__ == "__main__":
    main()
