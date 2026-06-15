#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
kok_neden_lock_olcum.py — A-mı-B-mi karar ÖLÇÜMÜ (tamamen YEREL, web yok).

Yanlış/eksik-yönetmenli filmlerde kimlik KİLİT-ORANINI ölçer:
  - OCR-cast ile mi kilitlenebiliyor (mevcut yöntem)
  - XML-cast (TEMİZ, TRT kataloğu) ile DAHA ÇOK kilitlenebiliyor mu (A için sinyal)
Ayrıca XML-yönetmeninin IMDb-crew ve OCR ile uyumunu sayar.

Çalıştır: venvs/ocr/Scripts/python.exe (duckdb burada).
"""
import os, sys, json, glob, importlib.util
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding="utf-8")
import duckdb

PDFMITAS = r"E:\MITAS\OCR-worktree\pdf-mitas"
HERE = r"E:\MITAS\scripts"
DB = "E:/MITAS/Database"
IMDB = os.environ.get("MITAS_IMDB_DUCKDB", r"Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb")

def _load(n,p):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
cp=_load("credit_parse", os.path.join(PDFMITAS,"credit_parse.py"))
sys.path.insert(0, HERE)
try:
    import credit_crosscheck as ccx
    OVERLAP=ccx.cast_overlap
except Exception:
    def OVERLAP(a,b):  # fold-tabanlı basit yedek: ortak ≥2-token isim
        fa={cp.fold(x) for x in a}; fb={cp.fold(x) for x in b}
        return len(fa & fb)

con=duckdb.connect(IMDB, read_only=True)

def parse_xml(xmlpath):
    """sidecar XML → {dir:[], cast:[], title_orig, title_tr}"""
    out={"dir":[],"cast":[],"title_orig":"","title_tr":""}
    try:
        root=ET.parse(xmlpath).getroot()
    except Exception:
        return out
    for prop in root.iter("PROPERTY"):
        if prop.attrib.get("NAME")=="JT:V_ROLE:V_ROL":
            bean=prop.find("BEAN")
            if bean is None: continue
            d={p.attrib.get("NAME"):(p.text or "") for p in bean.findall("PROPERTY")}
            nm=(d.get("V_ROL_FIRST","")+" "+d.get("V_ROL_LAST","")).strip()
            rt=(d.get("V_ROLE_TYPE","") or "").upper()
            if not nm: continue
            if "YÖNETMEN" in rt or "YONETMEN" in rt:
                out["dir"].append(nm)
            elif "OYUNCU" in rt or "ROL" in rt:
                out["cast"].append(nm)
        if prop.attrib.get("NAME")=="JT:EDC_DUBLIN_CORE:DC_DESCRIPTION":
            bean=prop.find("BEAN")
            if bean is not None:
                for p in bean.findall("PROPERTY"):
                    if p.attrib.get("NAME")=="DM_TITLE": out["title_orig"]=(p.text or "").strip()
                    if p.attrib.get("NAME")=="DM_SUBTITLE": out["title_tr"]=(p.text or "").strip()
    return out

def imdb_candidates(title, limit=6):
    if not title: return []
    return con.execute("""
        SELECT t.tconst, t.primaryTitle, t.startYear, r.numVotes
        FROM titles t LEFT JOIN ratings r ON r.tconst=t.tconst
        WHERE t.titleType IN ('movie','tvMovie') AND
          (strip_accents(lower(t.primaryTitle))=strip_accents(lower(?))
           OR strip_accents(lower(t.originalTitle))=strip_accents(lower(?)))
        ORDER BY r.numVotes DESC NULLS LAST LIMIT ?""",[title,title,limit]).fetchall()

def imdb_cast(tconst):
    rows=con.execute("""SELECT n.primaryName FROM principals p JOIN names n ON p.nconst=n.nconst
                        WHERE p.tconst=? AND p.category IN ('actor','actress')""",[tconst]).fetchall()
    return [r[0] for r in rows]

def imdb_director(tconst):
    c=con.execute("SELECT directors FROM crew WHERE tconst=?",[tconst]).fetchone()
    if not c or not c[0]: return []
    out=[]
    for nc in str(c[0]).split(","):
        nm=con.execute("SELECT primaryName FROM names WHERE nconst=?",[nc.strip()]).fetchone()
        if nm: out.append(nm[0])
    return out

def name_eq(a,b):
    return cp.fold(a)==cp.fold(b) or (a and b and cp.fold(a).split()[-1]==cp.fold(b).split()[-1] and len(cp.fold(a).split()[-1])>3)

# --- yanlış/eksik-yönetmenli filmler (kok_neden verdict'lerinden) ---
SRC="E:/MITAS/outputs/kok_neden"
BAD={"S2_ROLE_OVERREACH","S2_ROLE_UNMATCHED","S1_OCR_GARBLE","S0_FRAME_MISSING","S1_STITCH_DROP","S5_LLM_HALLUCINATION"}
films=[]
for f in os.listdir(SRC):
    if not f.endswith(".json"): continue
    try: v=json.load(open(os.path.join(SRC,f),encoding="utf-8"))
    except: continue
    if (v.get("director") or {}).get("root_cause") in BAD:
        films.append(v)

def find_folder(trt):
    for d in os.listdir(DB):
        if trt in d: return os.path.join(DB,d)
    return None

stats={"n":0,"xml_dir":0,"xml_cast2":0,"imdb_found":0,
       "lock_ocr":0,"lock_xml":0,"lock_either":0,"lock_xml_only":0,
       "xmldir_imdb_match":0,"xmldir_ocr_match":0}
rows=[]
for v in films:
    trt=v["trt"]; folder=find_folder(trt)
    if not folder: continue
    cj=os.path.join(folder,"clip.json")
    if not os.path.exists(cj): continue
    src=(json.load(open(cj,encoding="utf-8")) or {}).get("source_path","")
    xmlp=os.path.splitext(src)[0]+".xml" if src else ""
    if not (xmlp and os.path.exists(xmlp)): continue
    X=parse_xml(xmlp)
    stats["n"]+=1
    if X["dir"]: stats["xml_dir"]+=1
    if len(X["cast"])>=2: stats["xml_cast2"]+=1

    # OCR cast (final txt Oyuncular)
    ocr_cast=[]
    ft=[f for f in os.listdir(folder) if f.endswith(".txt") and "teknik" not in f]
    if ft:
        raw=open(os.path.join(folder,ft[0]),encoding="utf-8",errors="replace").read()
        import re
        mo=re.search(r"--- Oyuncular ---\n(.*?)(?=\n---)",raw,re.DOTALL)
        if mo: ocr_cast=[l.strip().lstrip("-").strip() for l in mo.group(1).splitlines() if l.strip() and l.strip()!="-"]

    # IMDb adayları: önce XML orijinal başlık, sonra TR başlık
    cands=imdb_candidates(X["title_orig"]) or imdb_candidates(X["title_tr"])
    best=None
    lock_ocr=lock_xml=False
    for (tconst,ptitle,yr,votes) in cands:
        ic=imdb_cast(tconst)
        if not ic: continue
        if OVERLAP(ocr_cast,ic)>=2: lock_ocr=True; best=best or tconst
        if OVERLAP(X["cast"],ic)>=2: lock_xml=True; best=tconst
    if cands: stats["imdb_found"]+=1
    if lock_ocr: stats["lock_ocr"]+=1
    if lock_xml: stats["lock_xml"]+=1
    if lock_ocr or lock_xml: stats["lock_either"]+=1
    if lock_xml and not lock_ocr: stats["lock_xml_only"]+=1

    # XML yönetmeni IMDb-crew ve OCR ile uyumlu mu (kilitli adayda)
    if best and X["dir"]:
        idir=imdb_director(best)
        if any(name_eq(a,b) for a in X["dir"] for b in idir): stats["xmldir_imdb_match"]+=1
        ocr_dir=(v.get("director") or {}).get("evidence","")  # kaba; OCR dir bilgisi
    if X["dir"] and (v.get("director") or {}):
        pass
    rows.append({"trt":trt,"film":v.get("film","")[:35],"xml_dir":X["dir"],
                 "xml_cast_n":len(X["cast"]),"lock_ocr":lock_ocr,"lock_xml":lock_xml})

n=max(1,stats["n"])
print(f"\n{'='*60}\nYANLIŞ/EKSİK-YÖNETMENLİ FİLM: {stats['n']}")
print(f"{'='*60}")
print(f"XML'de yönetmen VAR        : {stats['xml_dir']}/{n}  (%{100*stats['xml_dir']/n:.0f})")
print(f"XML'de ≥2 oyuncu VAR       : {stats['xml_cast2']}/{n}  (%{100*stats['xml_cast2']/n:.0f})")
print(f"IMDb'de başlık eşleşti     : {stats['imdb_found']}/{n}  (%{100*stats['imdb_found']/n:.0f})")
print(f"\n--- KİLİT-ORANI (kimlik kurulabiliyor mu) ---")
print(f"OCR-cast ile kilit         : {stats['lock_ocr']}/{n}  (%{100*stats['lock_ocr']/n:.0f})  [mevcut]")
print(f"XML-cast ile kilit         : {stats['lock_xml']}/{n}  (%{100*stats['lock_xml']/n:.0f})  [A]")
print(f"İkisinden biri ile         : {stats['lock_either']}/{n}  (%{100*stats['lock_either']/n:.0f})")
print(f">> XML'in EKSTRA açtığı     : {stats['lock_xml_only']} film (OCR kilitleyemedi, XML kilitledi)")
print(f"\n--- XML yönetmeni güvenilir mi ---")
print(f"XML-dir = IMDb-crew (kilitli): {stats['xmldir_imdb_match']}")
json.dump({"stats":stats,"rows":rows}, open("E:/MITAS/outputs/lock_olcum_sonuc.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
print("\nDetay: outputs/lock_olcum_sonuc.json")
