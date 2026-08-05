#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""credit_validate_test.py — credit_validate'i GERÇEK veriyle dene (venvs/ocr python)."""
import os, sys, json, glob, importlib.util
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding="utf-8")

HERE = r"E:\MITAS\scripts"
DB = "E:/MITAS/Database"
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
    try:
        root = ET.parse(xp).getroot()
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
    import re
    ft = [f for f in os.listdir(folder) if f.endswith(".txt") and "teknik" not in f]
    if not ft: return []
    raw = open(os.path.join(folder, ft[0]), encoding="utf-8", errors="replace").read()
    m = re.search(r"--- Oyuncular ---\n(.*?)(?=\n---)", raw, re.DOTALL)
    return [l.strip().lstrip("-").strip() for l in m.group(1).splitlines() if l.strip() and l.strip() != "-"] if m else []

def ocr_text(folder):
    g = sorted(glob.glob(os.path.join(folder, "ocr", "ocr-*", "kunye.txt")))
    return open(g[0], encoding="utf-8", errors="replace").read() if g else ""

# test filmleri: çeşitli vaka (teyit / çelişki / boş / overreach)
TARGETS = ["1981-0312","2001-9241","2011-1068","2015-1082","1973-1008",
           "2024-1273","2016-1002","2024-1285","2017-1043-1-0000-90"]
kb = cv._KB()
print("KB (mitas.duckdb) bağlı:", kb.con is not None, "\n")
for t in TARGETS:
    folder = next((os.path.join(DB, d) for d in os.listdir(DB) if t in d), None)
    if not folder: print(f"[{t}] klasör yok"); continue
    qd = qwen_dir(folder)
    xr, xtitle = xml_data(folder)
    title = xtitle or os.path.basename(folder)
    extracted = {"yonetmen": qd, "cast": final_cast(folder)}
    res = cv.validate(extracted, xml_roles=xr, title=title, ocr_text=ocr_text(folder), kb=kb)
    d = res["yonetmen"]
    print(f"### {os.path.basename(folder)[:42]}")
    print(f"  35B-yön: {qd}  | XML-yön: {xr.get('yonetmen')}  | başlık: {title[:30]}")
    print(f"  → DURUM: {d['status']} ({d['confidence']})  teyit={d['sources_confirm']}")
    print(f"     kaynaklar: IMDb={res['kaynaklar']['imdb']['director']}({res['kaynaklar']['imdb']['strength']}) "
          f"Wiki={res['kaynaklar']['wiki']['director']}({res['kaynaklar']['wiki']['strength']})")
    if d["conflict_candidates"]: print(f"     ÇELİŞKİ adayları: {d['conflict_candidates']}")
    if d["notes"]: print(f"     not: {d['notes']}")
    print(f"     YÖN değer: {d['value']}  | QC1: {res['qc1']}")
    print()
