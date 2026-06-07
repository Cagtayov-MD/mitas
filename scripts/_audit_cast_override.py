#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Blast-radius taraması: teslim edilen v4 künyelerde 'yanlış-film cast override' kurbanlarını bul.

Sinyal: teslim edilen kunye.pdf (v4 final) OYUNCULAR listesindeki isimlerin
RAW OCR (kunye.txt — ekranda jenerikte GERÇEKTEN yazan) içinde olup olmadığı.
OCR = ground truth (jenerik otorite). Teslim kadrosunun büyük kısmı OCR'da YOKSA
→ kadro dış (yanlış) bir filmden ENJEKTE edilmiş → KURBAN (eski buggy kod).

Sadece-okuma. fitz ile PDF metni çıkarır. Global Python310 (fitz) ile koşulmalı.
"""
import os, re, sys, json

sys.path.insert(0, r"E:\MITAS\OCR-worktree\pdf-mitas")
try:
    import name_normalize as nn
    def fold(s): return nn.ascii_fold(s or "").upper()
except Exception:
    def fold(s):
        s = (s or "").upper()
        rep = {"İ":"I","I":"I","Ş":"S","Ğ":"G","Ü":"U","Ö":"O","Ç":"C","Â":"A","Î":"I","Û":"U"}
        for a,b in rep.items(): s = s.replace(a,b)
        return re.sub(r"[^A-Z0-9 ]+"," ", s)

import fitz

ROOTS = [r"E:\MITAS\Mitas Output\Hazır", r"E:\MITAS\Mitas Output\Kontrol"]

def pdf_text(p):
    try:
        d = fitz.open(p); t = "\n".join(pg.get_text() for pg in d); d.close(); return t
    except Exception as e:
        return ""

def extract_cast(pdf_t):
    """OYUNCULAR ile bir sonraki BÜYÜK-HARF başlık arasındaki isim satırları."""
    up = pdf_t
    i = up.find("OYUNCULAR")
    if i < 0:
        # bazı render'larda harf-arası boşluklu: 'O Y U N C U L A R'
        m = re.search(r"O\s*Y\s*U\s*N\s*C\s*U\s*L\s*A\s*R", up)
        if not m: return []
        i = m.end()
    else:
        i += len("OYUNCULAR")
    tail = up[i:i+1200]
    # sonraki bölüm başlıkları (harf-arası boşluk toleranslı)
    stops = ["YAPIM", "Y A P I M", "ÖZET", "Ö Z E T", "OZET", "SES", "S E S", "TÜR", "TOPLAM"]
    cut = len(tail)
    for s in stops:
        j = tail.find(s)
        if 0 <= j < cut: cut = j
    block = tail[:cut]
    names = []
    for ln in block.splitlines():
        ln = re.sub(r"\s{2,}", " ", ln).strip()
        # harf-arası tek-boşluk render'ı sıkıştır (S A M -> SAM) ancak çok-kelimeli korunur:
        if ln and len(ln) >= 3 and not ln.isdigit():
            # eğer satır 'S A M  W...' gibi tamamen tek-harf+boşluk ise birleştir
            toks = ln.split(" ")
            if toks and all(len(t) == 1 for t in toks if t):
                ln = "".join(toks)
            if ln and ln not in ("—","-") and not re.fullmatch(r"[^A-Za-zÇĞİÖŞÜçğıöşü]+", ln):
                names.append(ln)
    # boşları/çok-kısa parçaları ele
    return [n for n in names if len(fold(n).replace(" ","")) >= 3][:12]

def name_in_ocr(name, ocr_fold):
    toks = [t for t in fold(name).split() if len(t) > 2]
    if not toks: return False
    # anlamlı tokenların ÇOĞU (>=ceil(n/2), en az 1) OCR metninde geçsin
    hit = sum(1 for t in toks if t in ocr_fold)
    need = max(1, (len(toks)+1)//2)
    return hit >= need

def parse_md_cast(md_path):
    """kunye_teslim.md '## Oyuncular' altındaki '- ISIM' satırları (v4 ÖNCESİ OCR kadrosu)."""
    if not os.path.exists(md_path): return None
    try:
        t = open(md_path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return None
    m = re.search(r"##\s*Oyuncular\s*\n(.*?)(?:\n##|\Z)", t, re.S)
    if not m: return []
    out = []
    for ln in m.group(1).splitlines():
        ln = ln.strip()
        if ln.startswith("-"):
            nm = ln.lstrip("-").strip()
            if nm and nm != "—": out.append(nm)
    return out

def name_in_list(name, ref_fold_list):
    """isim, referans kadro (fold edilmiş tam-satır listesi) içinde token-eşleşiyor mu."""
    toks = [t for t in fold(name).split() if len(t) > 2]
    if not toks: return False
    for ref in ref_fold_list:
        reftoks = set(t for t in ref.split() if len(t) > 2)
        hit = sum(1 for t in toks if t in reftoks)
        if hit >= max(1, (len(toks)+1)//2):
            return True
    return False

def main():
    rows = []
    for root in ROOTS:
        if not os.path.isdir(root): continue
        bucket = os.path.basename(root)
        for name in sorted(os.listdir(root)):
            d = os.path.join(root, name)
            if not os.path.isdir(d): continue
            pdf = os.path.join(d, "kunye.pdf")
            txt = os.path.join(d, "kunye.txt")
            rec = {"bucket": bucket, "folder": name, "has_pdf": os.path.exists(pdf),
                   "has_ocr": os.path.exists(txt)}
            if not os.path.exists(pdf):
                rec.update(status="NO_PDF"); rows.append(rec); continue
            pt = pdf_text(pdf)
            cast = extract_cast(pt)
            rec["cast_n"] = len(cast); rec["cast"] = cast
            if not os.path.exists(txt):
                rec.update(status="NO_OCR"); rows.append(rec); continue
            try:
                ocr = open(txt, encoding="utf-8", errors="ignore").read()
            except Exception:
                ocr = ""
            ocr_fold = fold(ocr)
            if len(cast) < 2:
                rec.update(status="CAST_LT2"); rows.append(rec); continue
            # ikincil sinyal: ham OCR rulosunda var mı (gürültülü — yalnız bilgi)
            present_ocr = [n for n in cast if name_in_ocr(n, ocr_fold)]
            rec["ocr_frac"] = round(len(present_ocr)/len(cast), 2)
            # BİRİNCİL sinyal: teslim (v4) kadrosu, v4-ÖNCESİ OCR kadrosunda (teslim.md) var mı?
            md_cast = parse_md_cast(os.path.join(d, "kunye_teslim.md"))
            if md_cast is None or len(md_cast) < 2:
                # teslim.md kadrosu yok → yalnız OCR-rulo sinyaline düş
                frac = rec["ocr_frac"]; rec["ref"] = "ocr_roll"
                rec["absent"] = [n for n in cast if n not in present_ocr]
            else:
                ref_fold = [fold(x) for x in md_cast]
                present_md = [n for n in cast if name_in_list(n, ref_fold)]
                frac = len(present_md)/len(cast)
                rec["ref"] = "teslim_md"; rec["md_cast_n"] = len(md_cast)
                rec["md_cast"] = md_cast
                rec["absent"] = [n for n in cast if n not in present_md]
            rec["present_frac"] = round(frac, 2)
            # KURBAN sinyali: teslim kadrosunun çoğu v4-öncesi OCR kadrosunda YOK (override)
            rec["status"] = "SUSPECT" if frac < 0.34 else ("WEAK" if frac < 0.6 else "OK")
            rows.append(rec)
    # özet
    susp = [r for r in rows if r.get("status") == "SUSPECT"]
    weak = [r for r in rows if r.get("status") == "WEAK"]
    nopdf = [r for r in rows if r.get("status") == "NO_PDF"]
    noocr = [r for r in rows if r.get("status") == "NO_OCR"]
    out = {"total": len(rows), "suspect": len(susp), "weak": len(weak),
           "no_pdf": len(nopdf), "no_ocr": len(noocr),
           "ok": len([r for r in rows if r.get("status")=="OK"]),
           "cast_lt2": len([r for r in rows if r.get("status")=="CAST_LT2"]),
           "suspects": susp, "weaks": weak}
    op = r"E:\MITAS\outputs\audit_cast_override.json"
    json.dump({"summary": {k:out[k] for k in ("total","suspect","weak","ok","cast_lt2","no_pdf","no_ocr")},
               "suspects": susp, "weaks": weak, "all": rows}, open(op,"w",encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps({k:out[k] for k in ("total","suspect","weak","ok","cast_lt2","no_pdf","no_ocr")}, ensure_ascii=False))
    # Tip A (KATASTROFİK: teslim.md GERÇEK kadro vardı → v4 BAŞKA filmle EZDİ)
    # Tip B (void-fill: teslim.md boş/okunamadı → KB doldurdu, doğru olabilir)
    for r in susp + weak:
        ref = r.get("ref"); mdn = r.get("md_cast_n", 0)
        r["tip"] = "A_KATASTROFIK" if (ref == "teslim_md" and mdn >= 3) else "B_VOID_FILL"
    tipA = [r for r in susp+weak if r["tip"] == "A_KATASTROFIK"]
    tipB = [r for r in susp+weak if r["tip"] == "B_VOID_FILL"]
    print(f"\n>>> Tip A (KATASTROFİK override): {len(tipA)}  |  Tip B (void-fill): {len(tipB)}")
    print("\n=== Tip A — KATASTROFİK (OCR gerçek kadro okudu, v4 BAŞKA filmle ezdi) ===")
    for r in tipA:
        print(f"[{r['bucket']}] {r['folder']}  frac={r.get('present_frac')}")
        print(f"    OCR/teslim okudu : {r.get('md_cast')}")
        print(f"    TESLİM (yanlış?) : {r.get('cast')}")
    print("\n=== Tip B — void-fill (OCR boş/okunamadı → KB doldurdu) ===")
    for r in tipB:
        print(f"[{r['bucket']}] {r['folder']}  frac={r.get('present_frac')}  ref={r.get('ref')} mdn={r.get('md_cast_n',0)}  cast={r.get('cast')}")
    print(f"\nFULL: {op}")

if __name__ == "__main__":
    main()
