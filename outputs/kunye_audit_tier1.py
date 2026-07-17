# -*- coding: utf-8 -*-
"""Tier-1 yapısal künye denetimi: export/ONAYLI+KONTROL altındaki tüm PDF'leri
metin çıkar + alan ayrıştır + arıza-imzası bayrakla. Web YOK; saf deterministik.
Çıktı: konsol tablosu + outputs/kunye_audit_tier1.json (Tier-2 workflow girdisi)."""
import glob, json, os, re, unicodedata
from pypdf import PdfReader

BASE = r"E:\MITAS\Mitas Output\export"
DIRS = ["ONAYLI", "KONTROL"]

def fold(s):
    s = s or ""
    for a, b in (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),("Ğ","g"),
                 ("ğ","g"),("Ü","u"),("ü","u"),("Ö","o"),("ö","o"),("Ç","c"),("ç","c")):
        s = s.replace(a, b)
    return unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode().lower().strip()

# bölüm başlıkları (ascii-fold ile eşleşir)
HEADERS = ["ses & altyazi","ses&altyazi","anahtar sozcukler","oyuncular","yapim ekibi",
           "yonetmen","yapimci","ozet","orijinal","ozgun ad","tur","toplam sure",
           "trt kimlik","film","dizi","haber","belgesel"]

# jenerik-EKİP rol sözcükleri (cast'e sızan crew işareti)
CREW_WORDS = {"sound","mixer","music","muzik","ses","montaj","editor","kurgu","director of photography",
              "photography","goruntu","yapim","production","publicist","tanitim","makeup","makyaj",
              "costume","kostum","art director","sanat","gaffer","grip","assistant","yardimci",
              "supervisor","coordinator","accountant","muhasebe","first aid","saglik","casting"}

def lines_of(pdf):
    r = PdfReader(pdf)
    txt = "\n".join((p.extract_text() or "") for p in r.pages)
    return [l.strip() for l in txt.splitlines() if l.strip()]

def is_header(line):
    f = fold(line)
    return any(f == h or f.startswith(h) for h in HEADERS)

def section(lines, name, stop_names):
    """name başlığından sonra, stop başlıklarından birine kadarki satırlar."""
    out, cap = [], False
    for l in lines:
        f = fold(l)
        if not cap:
            if f == name or f.startswith(name):
                cap = True
            continue
        if any(f == s or f.startswith(s) for s in stop_names) or is_header(l):
            break
        out.append(l)
    return out

def looks_garble(tok):
    """tek-token isim, harf-dışı içeren, ya da çöp parça → şüpheli."""
    t = tok.strip()
    if not t: return True
    if any(c in t for c in "<>|/\\"): return True
    words = [w for w in re.split(r"\s+", t) if w]
    if len(words) == 1: return True          # tek kelime = bölünmüş/garble sinyali
    if re.search(r"\d", t): return True
    return False

def audit(pdf):
    lines = lines_of(pdf)
    fname = os.path.basename(pdf)
    rec = {"file": fname, "dir": os.path.basename(os.path.dirname(pdf))}

    # TRT kimlik & başlık
    m = re.search(r"\d{4}-\d{4}-\d-\d{4}-\d{2}-\d", fname)
    rec["trt_id"] = m.group(0) if m else ""
    rec["title"] = re.sub(r"^\S+\s+", "", fname.replace(".pdf","")).replace(" ONAYLI","").strip()

    # orijinal ad var mı?
    orig = section(lines, "orijinal", ["anahtar","oyuncular","ozet","yapim"]) or \
           section(lines, "ozgun ad", ["anahtar","oyuncular","ozet","yapim"])
    rec["orijinal_ad"] = " ".join(orig).strip()

    # oyuncular
    cast = section(lines, "oyuncular", ["yapim ekibi","yonetmen","yapimci","ozet"])
    rec["cast"] = cast

    # yapim ekibi → yönetmen / yapımcı
    yon = section(lines, "yonetmen", ["yapimci","ozet","oyuncular"])
    yap = section(lines, "yapimci", ["ozet","oyuncular","yonetmen"])
    def clean(v):
        v = [x for x in v if fold(x) not in ("","-","—") and x not in ("—","-","–")]
        return v
    rec["yonetmen"] = clean(yon)
    rec["yapimci"] = clean(yap)

    # ---- BAYRAKLAR ----
    flags = []
    if not rec["yonetmen"]: flags.append("YONETMEN-YOK")
    if not rec["yapimci"]: flags.append("YAPIMCI-YOK")
    if not rec["orijinal_ad"]: flags.append("ORIJINAL-AD-YOK")
    if not cast: flags.append("CAST-YOK")
    garble = [c for c in cast if looks_garble(c)]
    if garble: flags.append(f"GARBLE-CAST({len(garble)})")
    crew = [c for c in cast if any(w in fold(c) for w in CREW_WORDS)]
    if crew: flags.append(f"CREW-SIZINTI({len(crew)})")
    # ardışık tek-token (ROGER \n MOSTEY = bölünmüş isim)
    singles = [c for c in cast if len([w for w in c.split() if w])==1]
    if len(singles) >= 2: flags.append(f"BOLUNMUS-ISIM({len(singles)})")
    rec["garble_cast"] = garble
    rec["flags"] = flags
    rec["severity"] = len(flags) + (2 if "GARBLE-CAST" in " ".join(flags) else 0)
    return rec

def main():
    pdfs = []
    for d in DIRS:
        pdfs += sorted(glob.glob(os.path.join(BASE, d, "*.pdf")))
    recs = []
    for p in pdfs:
        try:
            recs.append(audit(p))
        except Exception as e:
            recs.append({"file": os.path.basename(p), "flags": [f"HATA:{type(e).__name__}"], "severity": 99})
    recs.sort(key=lambda r: -r.get("severity",0))

    print(f"Toplam {len(recs)} PDF denetlendi.\n")
    clean = [r for r in recs if not r.get("flags")]
    flagged = [r for r in recs if r.get("flags")]
    print(f"TEMİZ (yapısal): {len(clean)}   BAYRAKLI: {len(flagged)}\n")
    print(f"{'DURUM':<6} {'KLASÖR':<8} {'FİLM':<34} BAYRAKLAR")
    print("-"*100)
    for r in recs:
        st = "OK" if not r.get("flags") else "!!"
        print(f"{st:<6} {r.get('dir',''):<8} {r.get('title','')[:33]:<34} {', '.join(r.get('flags',[]))}")

    # özet sayım
    from collections import Counter
    c = Counter()
    for r in flagged:
        for f in r["flags"]:
            c[re.sub(r'\(.*\)','',f)] += 1
    print("\n=== BAYRAK SAYIMI ===")
    for k,v in c.most_common():
        print(f"  {k:<18} {v}")

    out = r"E:\MITAS\outputs\kunye_audit_tier1.json"
    with open(out,"w",encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False, indent=1)
    print(f"\nJSON → {out}")

if __name__ == "__main__":
    main()
