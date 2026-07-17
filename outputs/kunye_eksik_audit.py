#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KÜNYE EKSİKLİK DENETİMİ — E:\\MITAS\\Database tüm filmler.
Orijinal pipeline çıktısını (kunye_teslim.md == kunye.pdf) okur.
Flag: yönetmen BOŞ  OR  yapımcı BOŞ  OR  gerçek-cast sayısı <= 6  OR  hiç çıktı yok.
Sadece TESPİT — düzeltme yok. kunye_fixed.pdf sadece metadata (zaten-onarıldı işareti).
"""
import os, re, json, glob

DB = r"E:\MITAS\Database"
OUT = r"E:\MITAS\outputs\kunye_eksik_audit.json"

EMPTY_TOKENS = {"", "-", "—", "–", "...", "…", "—,", "yok", "bilinmiyor"}

def is_empty(s):
    if s is None:
        return True
    t = s.strip().strip(".,;:").strip()
    # sadece tire/uzun-tire/boşluk/noktalama
    t2 = re.sub(r"[\s\-—–.,;:]+", "", t)
    if t2 == "":
        return True
    if t.lower() in EMPTY_TOKENS:
        return True
    return False

def parse_md(path):
    """kunye_teslim.md -> {oyuncular:[...], yonetmen:str, yapimci:str, tur, dil, sure, baslik, uretim}"""
    txt = open(path, encoding="utf-8", errors="replace").read()
    lines = txt.splitlines()
    res = {"oyuncular": [], "yonetmen": "", "yapimci": "", "tur": "", "ana_dil": "",
           "sure": "", "baslik": "", "uretim": "", "ozet_var": False, "altyazi": ""}
    # başlık
    for ln in lines[:3]:
        m = re.match(r"#\s*MİTAS\s*•\s*\w+\s*•\s*(.+)", ln)
        if m:
            res["baslik"] = m.group(1).strip()
        m2 = re.match(r"Üretim:\s*(.+)", ln)
        if m2:
            res["uretim"] = m2.group(1).strip()
    # tür / süre / çözünürlük satırı
    for ln in lines:
        m = re.search(r"Tür:\s*([^·]+)", ln)
        if m:
            res["tur"] = m.group(1).strip()
        m = re.search(r"Süre:\s*([0-9:]+)", ln)
        if m:
            res["sure"] = m.group(1).strip()
    # bölümlere ayır
    sect = None
    for ln in lines:
        h = re.match(r"##\s*(.+)", ln)
        if h:
            sect = h.group(1).strip().lower()
            continue
        if sect is None:
            continue
        if sect.startswith("oyuncular"):
            m = re.match(r"-\s*(.*)$", ln)
            if m:
                res["oyuncular"].append(m.group(1).strip())
        elif sect.startswith("yapım ekibi") or sect.startswith("yapim ekibi"):
            m = re.match(r"-\s*Yönetmen:\s*(.*)$", ln)
            if m:
                res["yonetmen"] = m.group(1).strip()
            m = re.match(r"-\s*Yapımcı:\s*(.*)$", ln)
            if m:
                res["yapimci"] = m.group(1).strip()
        elif sect.startswith("ses"):
            m = re.match(r"-\s*Ana dil:\s*(.*)$", ln)
            if m:
                res["ana_dil"] = m.group(1).strip()
            m = re.match(r"-\s*Altyazı:\s*(.*)$", ln)
            if m:
                res["altyazi"] = m.group(1).strip()
        elif sect.startswith("özet") or sect.startswith("ozet"):
            t = ln.strip()
            if t and not t.startswith("(") and "AYRI BİR ADIMDA" not in t and "HAM TRANSCRİPT" not in t:
                res["ozet_var"] = True
    return res

def count_frames(folder, sub):
    p = os.path.join(folder, "frames", sub)
    if not os.path.isdir(p):
        return -1  # -1 = klasör yok
    try:
        return len([f for f in os.listdir(p) if f.lower().endswith((".png", ".jpg", ".jpeg"))])
    except Exception:
        return -2

def ocr_info(folder):
    info = {"job": None, "kunye_txt": False, "ocr_ham": False, "ocr_raw_all": False,
            "bucket": None, "kunye_lines": 0}
    ocrdir = os.path.join(folder, "ocr")
    if not os.path.isdir(ocrdir):
        return info
    jobs = [d for d in glob.glob(os.path.join(ocrdir, "ocr-*")) if os.path.isdir(d)]
    if not jobs:
        return info
    job = max(jobs, key=lambda d: os.path.getmtime(d))
    info["job"] = os.path.basename(job)
    kt = os.path.join(job, "kunye.txt")
    if os.path.isfile(kt):
        info["kunye_txt"] = True
        try:
            info["kunye_lines"] = sum(1 for _ in open(kt, encoding="utf-8", errors="replace"))
        except Exception:
            pass
    info["ocr_ham"] = os.path.isfile(os.path.join(job, "ocr_ham.txt"))
    info["ocr_raw_all"] = os.path.isfile(os.path.join(job, "ocr_raw_all.txt"))
    sj = os.path.join(job, "ocr_summary.json")
    if os.path.isfile(sj):
        try:
            d = json.load(open(sj, encoding="utf-8", errors="replace"))
            info["bucket"] = d.get("bucket") or d.get("kademe") or d.get("durum")
        except Exception:
            pass
    return info

rows = []
folders = [os.path.join(DB, d) for d in os.listdir(DB) if os.path.isdir(os.path.join(DB, d))]
folders.sort()

for folder in folders:
    name = os.path.basename(folder)
    pdfdir = os.path.join(folder, "pdf")
    md = os.path.join(pdfdir, "kunye_teslim.md")
    kpdf = os.path.join(pdfdir, "kunye.pdf")
    fpdf = os.path.join(pdfdir, "kunye_fixed.pdf")
    row = {
        "folder": name,
        "has_md": os.path.isfile(md),
        "has_kunye_pdf": os.path.isfile(kpdf),
        "has_fixed_pdf": os.path.isfile(fpdf),
        "frames_giris": count_frames(folder, "giris"),
        "frames_cikis": count_frames(folder, "cikis"),
    }
    row.update({"ocr_" + k: v for k, v in ocr_info(folder).items()})

    if not row["has_md"]:
        # orijinal çıktı yok -> NO_OUTPUT (en ağır)
        row.update({
            "no_output": True,
            "yonetmen": "", "yapimci": "", "oyuncular": [], "real_cast": 0,
            "yon_bos": True, "yap_bos": True, "cast_az": True,
            "tur": "", "ana_dil": "", "sure": "", "baslik": "", "ozet_var": False,
            "altyazi": "",
        })
        row["flag"] = True
        row["flag_reasons"] = ["NO_OUTPUT"]
        rows.append(row)
        continue

    p = parse_md(md)
    real_cast = [c for c in p["oyuncular"] if not is_empty(c)]
    yon_bos = is_empty(p["yonetmen"])
    yap_bos = is_empty(p["yapimci"])
    cast_az = len(real_cast) <= 6

    reasons = []
    if yon_bos:
        reasons.append("YONETMEN_BOS")
    if yap_bos:
        reasons.append("YAPIMCI_BOS")
    if cast_az:
        reasons.append(f"CAST_AZ({len(real_cast)})")

    row.update({
        "no_output": False,
        "baslik": p["baslik"], "tur": p["tur"], "ana_dil": p["ana_dil"],
        "sure": p["sure"], "uretim": p["uretim"], "altyazi": p["altyazi"],
        "ozet_var": p["ozet_var"],
        "yonetmen": p["yonetmen"], "yapimci": p["yapimci"],
        "oyuncular": real_cast, "real_cast": len(real_cast),
        "yon_bos": yon_bos, "yap_bos": yap_bos, "cast_az": cast_az,
        "flag": bool(reasons), "flag_reasons": reasons,
    })
    rows.append(row)

# özet istatistik
total = len(rows)
flagged = [r for r in rows if r["flag"]]
no_out = [r for r in rows if r.get("no_output")]
yon = [r for r in rows if r["yon_bos"] and not r.get("no_output")]
yap = [r for r in rows if r["yap_bos"] and not r.get("no_output")]
castaz = [r for r in rows if r["cast_az"] and not r.get("no_output")]
clean = [r for r in rows if not r["flag"]]

summary = {
    "toplam_klasor": total,
    "flagli": len(flagged),
    "temiz": len(clean),
    "no_output": len(no_out),
    "yonetmen_bos": len(yon),
    "yapimci_bos": len(yap),
    "cast_6_alti": len(castaz),
    "fixed_pdf_var_flagli": sum(1 for r in flagged if r["has_fixed_pdf"]),
}

json.dump({"summary": summary, "rows": rows}, open(OUT, "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

print(json.dumps(summary, ensure_ascii=False, indent=2))
print("\n--- FLAG SEBEP DAĞILIMI ---")
from collections import Counter
c = Counter()
for r in flagged:
    key = tuple(sorted(set(x.split("(")[0] for x in r["flag_reasons"])))
    c[key] += 1
for k, v in c.most_common():
    print(f"  {v:4d}  {' + '.join(k)}")
print(f"\nJSON -> {OUT}")
