# -*- coding: utf-8 -*-
"""TAZE künye-yolu ölçümü (ASR/özet YOK) — kimlik kilit oranı + başarısızlık modları.
Her film: mevcut kodla tek_film_kunye koş → final yönetmen + cross_check kilit durumu."""
import os, sys, io, json, glob, re, subprocess, xml.etree.ElementTree as ET
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)

PY = r"C:\Users\TRT03\AppData\Local\Programs\Python\Python310\python.exe"
DB = r"E:\MITAS\Database"
OUT = r"E:\MITAS\outputs\CREDIT_HARDENING_FRESH_20260613.json"
env = dict(os.environ, MITAS_QC2="1", MITAS_QC2_WEB="1", MITAS_OCR_GLM_CONSENSUS="0")

# Çeşitli set: başlık-parçası (hastalık modlarını + temiz kontrolü kapsar)
WANT = [
    "HÜKÜMET KADIN 2", "ATTİLA MARCEL", "GİZEMLİ GÜÇ", "HERBIE", "ÇÖL",
    "YERÇEKİMİ", "JANDARMALAR ZORDA", "NAPOLYON", "DİKENLİ TELLER",
    "VASİYETNAME", "KADIN AFFETMEZ", "GEYİK ÇOCUK",
]

def find_hub(title):
    for d in glob.glob(os.path.join(DB, "*", "_DURUM.json")):
        try:
            j = json.load(open(d, encoding="utf-8"))
        except Exception:
            continue
        if (j.get("title") or "").strip().upper() == title.strip().upper():
            return os.path.dirname(d), j
    # gevşek: içeriyorsa
    for d in glob.glob(os.path.join(DB, "*", "_DURUM.json")):
        try:
            j = json.load(open(d, encoding="utf-8"))
        except Exception:
            continue
        if title.strip().upper() in (j.get("title") or "").strip().upper():
            return os.path.dirname(d), j
    return None, None

def xml_original(video):
    if not video:
        return None
    xmlp = re.sub(r"\.mp4$", ".xml", video, flags=re.I)
    if not os.path.exists(xmlp):
        return None
    try:
        txt = open(xmlp, encoding="utf-8", errors="ignore").read()
        for tag in ("ORIGINALTITLE", "ORIGINAL_TITLE", "OriginalName", "TITLE_ORIGINAL"):
            m = re.search(rf"<{tag}>(.*?)</{tag}>", txt, re.I | re.S)
            if m and m.group(1).strip():
                return m.group(1).strip()
    except Exception:
        pass
    return None

def stored_yon(hub):
    md = os.path.join(hub, "pdf", "kunye_teslim.md")
    if os.path.exists(md):
        for l in open(md, encoding="utf-8", errors="ignore"):
            if "Yönetmen:" in l:
                return l.split("Yönetmen:", 1)[1].strip()
    return ""

results = []
for w in WANT:
    hub, j = find_hub(w)
    if not hub:
        print(f"[atla] {w}: hub bulunamadı", flush=True)
        continue
    title = j.get("title"); trt = j.get("trt_id") or ""
    ym = re.match(r"(\d{4})", trt); year = ym.group(1) if ym else None
    orig = xml_original(j.get("video"))
    stored = stored_yon(hub)
    cmd = [PY, r"E:\MITAS\scripts\tek_film_kunye.py", "--clip", hub,
           "--title", title, "--profile", "film", "--out",
           os.path.join(r"E:\MITAS\outputs\_ch", re.sub(r"\W+", "_", title) + ".pdf")]
    if orig: cmd += ["--original", orig]
    if year: cmd += ["--year", year]
    os.makedirs(r"E:\MITAS\outputs\_ch", exist_ok=True)
    print(f"[koş] {title} (yıl={year}, orig={orig})...", flush=True)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300, env=env)
        raw = r.stdout or ""
        i = raw.find("{")
        d = None
        if i >= 0:
            try: d, _ = json.JSONDecoder().raw_decode(raw[i:])
            except Exception: d = None
        d = d or {}
        v4 = d.get("v4") or {}
        cc = (d.get("adimlar") or {}).get("cross_check") or {}
        row = {
            "title": title, "year": year, "original": orig,
            "stored_yon": stored,
            "fresh_yon": v4.get("yonetmen"),
            "yon_kaynak": cc.get("yonetmen_kaynak"),
            "verdict": cc.get("verdict"),
            "cast_ortusme": cc.get("cast_ortusme"),
            "kimlik_dogru": cc.get("kimlik_dogru"),
            "eslesen_film": cc.get("eslesen_film"),
            "fresh_cast_n": (v4.get("cast") if isinstance(v4.get("cast"), int) else len(v4.get("cast") or [])),
        }
    except subprocess.TimeoutExpired:
        row = {"title": title, "error": "timeout"}
    except Exception as e:
        row = {"title": title, "error": str(e)[:120]}
    results.append(row)
    print(f"   → fresh_yon={row.get('fresh_yon')} | kaynak={row.get('yon_kaynak')} | kilit={row.get('kimlik_dogru')} cast_ov={row.get('cast_ortusme')}", flush=True)

json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\n=== BİTTİ: {len(results)} film → {OUT} ===", flush=True)
# özet
locked = [r for r in results if r.get("kimlik_dogru") is True]
print(f"KİLİTLENDİ: {len(locked)}/{len(results)}", flush=True)
