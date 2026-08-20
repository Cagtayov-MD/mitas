#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""credit_validate_scale.py — credit_validate'i TÜM geçmiş batch'te koş (yeni koşu YOK).
35B-yön (log) + XML (sidecar) + OCR (kunye) + mitas.duckdb ile dağılım + bayrak listesi."""
import os, sys, json, glob, re, importlib.util
import xml.etree.ElementTree as ET
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")

HERE = r"E:\MITAS\scripts"; DB = "E:/MITAS/Database"
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("credit_validate", os.path.join(HERE, "credit_validate.py"))
cv = importlib.util.module_from_spec(spec); spec.loader.exec_module(cv)

def qwen_dir(folder):
    log = os.path.join(folder, "_log.jsonl")
    if not os.path.exists(log): return []
    for line in open(log, encoding="utf-8", errors="replace"):
        if "credit_text_completed" in line:
            try: return (json.loads(line).get("detail", {}) or {}).get("yonetmen") or []
            except Exception: pass
    return []

def xml_data(folder):
    cj = os.path.join(folder, "clip.json")
    if not os.path.exists(cj): return {}, ""
    src = (json.load(open(cj, encoding="utf-8")) or {}).get("source_path", "")
    xp = os.path.splitext(src)[0] + ".xml" if src else ""
    if not (xp and os.path.exists(xp)): return {}, ""
    out = {"yonetmen": [], "oyuncu": []}; title = ""
    try: root = ET.parse(xp).getroot()
    except Exception: return {}, ""
    for prop in root.iter("PROPERTY"):
        if prop.attrib.get("NAME") == "JT:V_ROLE:V_ROL":
            b = prop.find("BEAN")
            if b is None: continue
            d = {p.attrib.get("NAME"): (p.text or "") for p in b.findall("PROPERTY")}
            nm = (d.get("V_ROL_FIRST", "") + " " + d.get("V_ROL_LAST", "")).strip()
            rt = (d.get("V_ROLE_TYPE", "") or "").upper()
            if not nm: continue
            if "YÖNETMEN" in rt or "YONETMEN" in rt: out["yonetmen"].append(nm)
            elif "OYUNCU" in rt or "ROL" in rt: out["oyuncu"].append(nm)
        if prop.attrib.get("NAME") == "JT:EDC_DUBLIN_CORE:DC_DESCRIPTION":
            b = prop.find("BEAN")
            if b is not None:
                for p in b.findall("PROPERTY"):
                    if p.attrib.get("NAME") == "DM_TITLE": title = (p.text or "").strip()
    return out, title

def final_cast(folder):
    ft = [f for f in os.listdir(folder) if f.endswith(".txt") and "teknik" not in f]
    if not ft: return []
    raw = open(os.path.join(folder, ft[0]), encoding="utf-8", errors="replace").read()
    m = re.search(r"--- Oyuncular ---\n(.*?)(?=\n---)", raw, re.DOTALL)
    return [l.strip().lstrip("-").strip() for l in m.group(1).splitlines() if l.strip() and l.strip() != "-"] if m else []

def ocr_text(folder):
    g = sorted(glob.glob(os.path.join(folder, "ocr", "ocr-*", "kunye.txt")))
    return open(g[0], encoding="utf-8", errors="replace").read() if g else ""

# 14-15 Haziran, benzersiz trt
seen = {}
for d in sorted(os.listdir(DB)):
    p = os.path.join(DB, d)
    if not os.path.isdir(p): continue
    txts = [f for f in os.listdir(p) if f.endswith(".txt") and "teknik" not in f]
    if not txts: continue
    head = open(os.path.join(p, txts[0]), encoding="utf-8", errors="replace").read(400)
    if "15.06" not in head and "14.06" not in head: continue
    mm = re.search(r"(\d{4}-\d{4,5}-\d-\d{4}-\d{2}-\d)", d)
    trt = mm.group(1) if mm else d
    if trt not in seen: seen[trt] = p

kb = cv._KB()
print("KB bağlı:", kb.con is not None, "| film:", len(seen))
status_c = Counter(); conf_c = Counter()
src_cov = Counter()   # IMDb/Wiki kapsama
rows = []
for trt, folder in seen.items():
    qd = qwen_dir(folder)
    xr, xtitle = xml_data(folder)
    title = xtitle or os.path.basename(folder)
    ext = {"yonetmen": qd, "cast": final_cast(folder)}
    try:
        res = cv.validate(ext, xml_roles=xr, title=title, ocr_text=ocr_text(folder), kb=kb)
    except Exception as e:
        status_c["HATA"] += 1; continue
    d = res["yonetmen"]
    status_c[d["status"]] += 1; conf_c[d["confidence"]] += 1
    im = bool(res["kaynaklar"]["imdb"]["director"]); wk = bool(res["kaynaklar"]["wiki"]["director"])
    src_cov["IMDb" if im else "imdb-yok"] += 1
    src_cov["Wiki" if wk else "wiki-yok"] += 1
    if im and wk: src_cov["ikisi-de"] += 1
    elif im or wk: src_cov["yalniz-biri"] += 1
    else: src_cov["hicbiri"] += 1
    rows.append({"trt": trt, "film": os.path.basename(folder)[:40], "status": d["status"],
                 "conf": d["confidence"], "35b": qd, "value": d["value"],
                 "teyit": d["sources_confirm"], "celiski_aday": d["conflict_candidates"],
                 "imdb": res["kaynaklar"]["imdb"]["director"], "wiki": res["kaynaklar"]["wiki"]["director"],
                 "notes": d["notes"][:3]})

print("\n=== DURUM DAĞILIMI ===")
tot = sum(status_c.values())
for k, v in status_c.most_common():
    print(f"  {k:16s}: {v:4d}  (%{100*v/max(1,tot):.0f})")
print("\n=== GÜVEN ===", dict(conf_c))
print("=== KAYNAK KAPSAMA ===")
for k, v in src_cov.most_common():
    print(f"  {k:12s}: {v}")
cel = [r for r in rows if r["status"] == "CELISKI"]
print(f"\n=== CELISKI ({len(cel)}) — yanlış-pozitif denetimi için ilk 20 ===")
for r in cel[:20]:
    print(f"  {r['film']}: 35b={r['35b']} | IMDb={r['imdb']} Wiki={r['wiki']} | aday={r['celiski_aday']}")

json.dump({"status": dict(status_c), "conf": dict(conf_c), "src": dict(src_cov), "rows": rows},
          open("E:/MITAS/outputs/credit_validate_scale.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("\nDetay: outputs/credit_validate_scale.json")
