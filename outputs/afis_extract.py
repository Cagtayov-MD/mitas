# -*- coding: utf-8 -*-
"""PDF alan çıkarımı + afiş montaj. Her künye PDF'ten title/original/tur/cast/crew/year.
Çıktı: outputs/afis_fields.json + outputs/afis_montaj_*.png (afişli olanlar)."""
import fitz, os, re, json, glob, sys

KONTROL = r"E:\MITAS\Mitas Output\export\KONTROL"

def _despace(s):
    """'O Y U N C U L A R' -> 'OYUNCULAR' (label tespiti)."""
    return re.sub(r"\s+", "", s).upper()

LABELS = {"MİTAS","İÇERİKKÜNYEBELGESİ","SES&ALTYAZI","ANADİL","ALTYAZI","TÜR",
          "TOPLAMSÜRE","TRTKİMLİK","ANAHTARSÖZCÜKLER","OYUNCULAR","YAPIMEKİBİ","ÖZET"}
CHAN = re.compile(r"^\d\.KANAL$")
ROLE = {"Yapımcı","Yönetmen","Yapımcılar","Yönetmenler"}

def parse_pdf(path):
    doc = fitz.open(path)
    pg = doc[0]
    raw = [l.strip() for l in pg.get_text().splitlines() if l.strip()]
    doc.close()
    # bölümlere ayır
    d = {"title":None,"subtitle":None,"tur":None,"cast":[],"yonetmen":[],"yapimci":[],
         "ana_dil":None,"altyazi":None,"keywords":[],"has_ozet":True}
    sec = None
    pending_role = None
    title_lines = []
    for ln in raw:
        dl = _despace(ln)
        if dl in LABELS:
            sec = dl
            pending_role = None
            continue
        if CHAN.match(dl):
            sec = "CHAN"; continue
        if ln in ("Otomatik üretilmiş künye belgesi","Sayfa  1 / 1"):
            continue
        if ln.startswith("Üretim:") or ln.startswith("Sayfa"):
            continue
        if re.match(r"^\d+x\d+$", ln):  # çözünürlük
            continue
        if _despace(ln) in ("FİLM","DİZİ"):
            sec = "TITLE"; d["profile"]=_despace(ln); continue
        # değer satırları
        if sec == "ANADİL": d["ana_dil"]=d["ana_dil"] or ln
        elif sec == "ALTYAZI": d["altyazi"]=d["altyazi"] or ln
        elif sec == "TÜR": d["tur"]=d["tur"] or ln
        elif sec == "TITLE":
            if ln != "—": title_lines.append(ln)
        elif sec == "ANAHTARSÖZCÜKLER":
            if ln != "—":
                d["keywords"] += [x.strip() for x in re.split(r"[;,]", ln) if x.strip()]
        elif sec == "OYUNCULAR":
            if ln != "—": d["cast"].append(ln)
        elif sec == "YAPIMEKİBİ":
            if ln in ROLE:
                pending_role = ln.rstrip("lar").rstrip("ler") if ln.endswith(("lar","ler")) else ln
                pending_role = "Yönetmen" if ln.startswith("Yönetmen") else "Yapımcı"
                continue
            if ln == "—": continue
            if pending_role == "Yönetmen": d["yonetmen"].append(ln)
            elif pending_role == "Yapımcı": d["yapimci"].append(ln)
        elif sec == "ÖZET":
            if "AYRI BİR ADIMDA" in ln.upper() or "ÜRETİLECEKTİR" in ln.upper():
                d["has_ozet"]=False
    if title_lines:
        d["title"]=title_lines[0]
        if len(title_lines)>1: d["subtitle"]=title_lines[1]
    return d

def trt_year(fn):
    m=re.match(r"^(\d{4})-",fn); return m.group(1) if m else None

if __name__=="__main__":
    rows={}
    for p in sorted(glob.glob(os.path.join(KONTROL,"*.pdf"))):
        fn=os.path.basename(p)
        try:
            d=parse_pdf(p)
        except Exception as e:
            d={"err":str(e)}
        d["file"]=fn
        d["year"]=trt_year(fn)
        d["trt"]=re.match(r"^(\d{4}-\d{4}-\d-\d{4}-\d{2}-\d)",fn).group(1)
        rows[fn]=d
    json.dump(rows, open(r"E:\MITAS\outputs\afis_fields.json","w",encoding="utf-8"),
              ensure_ascii=False, indent=1)
    # özet
    ncast=sum(1 for d in rows.values() if d.get("cast"))
    nyon=sum(1 for d in rows.values() if d.get("yonetmen"))
    print("PDF sayısı:",len(rows))
    print("Kadro VAR :",ncast,"| Kadro BOŞ:",len(rows)-ncast)
    print("Yönetmen VAR:",nyon,"| Yönetmen BOŞ:",len(rows)-nyon)
    print("[yazıldı] outputs/afis_fields.json")
