#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_morning_audit.py — filmtest batch SONRASI kredi-kalite denetimi (non-GPU).
Her batch klibi için: v4 PDF'ten yön+cast çek → OCR metniyle karşılaştır:
  • HALÜSİNASYON: cast/yön ismi OCR metninde YOK mu? (kalkan bunu engellemeli — 0 beklenir)
  • cast sayısı, yön boş mu (okunamadı→Kontrol), olası karakter/şirket sızıntısı (kaba sezgi)
Çıktı: outputs/_morning_audit.json + ekrana özet + RED FLAG listesi.
"""
import glob, json, os, re, sys, unicodedata
import fitz

DB = r"E:\MITAS\Database"
_TR = str.maketrans("ışğçöüİI", "isgcoui i".replace(" ", ""))

def fold(s):
    s = (s or "").casefold().translate(str.maketrans("ışğçöü", "isgcou"))
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s)

def toks(s):
    return [t for t in fold(s).split() if len(t) > 2]

def pdf_cast_dir(pdf):
    t = "\n".join(p.get_text() for p in fitz.open(pdf))
    # harf-arası boşlukları normalize et
    def sect(start_pat, stops):
        m = re.search(start_pat, t)
        if not m: return []
        tail = t[m.end(): m.end()+1500]
        cut = len(tail)
        for s in stops:
            j = re.search(s, tail)
            if j and j.start() < cut: cut = j.start()
        names = []
        for ln in tail[:cut].splitlines():
            ln = re.sub(r"\s{2,}", " ", ln).strip()
            toks_ln = ln.split(" ")
            if toks_ln and all(len(x) == 1 for x in toks_ln if x):
                ln = "".join(toks_ln)
            if ln and len(fold(ln).replace(" ", "")) >= 3 and not re.fullmatch(r"[^A-Za-zÇĞİÖŞÜçğıöşü]+", ln):
                names.append(ln)
        return names[:10]
    cast = sect(r"O\s*Y\s*U\s*N\s*C\s*U\s*L\s*A\s*R", [r"Y\s*A\s*P\s*I\s*M", r"Ö\s*Z\s*E\s*T", r"S\s*E\s*S", r"A\s*N\s*A\s*H"])
    # yönetmen: "YAPIM EKİBİ" altında Yönetmen satırı
    yon = []
    m = re.search(r"Y[öo]netmen", t)
    if m:
        seg = t[m.end(): m.end()+120]
        line = seg.split("\n")[1] if "\n" in seg else seg
        if line.strip(): yon = [line.strip()]
    return cast, yon

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = []
    # YALNIZ batch (yeni-reader) klipleri: filmtest_batch_results.jsonl'deki hub'lar.
    batch_hubs = set()
    try:
        for ln in open(r"E:\MITAS\outputs\filmtest_batch_results.jsonl", encoding="utf-8"):
            ln = ln.strip()
            if ln:
                h = json.loads(ln).get("hub")
                if h:
                    batch_hubs.add(os.path.normcase(os.path.abspath(h)))
    except Exception:
        pass
    for d in sorted(glob.glob(os.path.join(DB, "*"))):
        if batch_hubs and os.path.normcase(os.path.abspath(d)) not in batch_hubs:
            continue
        pdf = os.path.join(d, "pdf", "kunye.pdf")
        ocrs = glob.glob(os.path.join(d, "ocr", "*", "kunye.txt"))
        if not os.path.exists(pdf) or not ocrs:
            continue
        name = os.path.basename(d)
        try:
            cast, yon = pdf_cast_dir(pdf)
            ocr_txt = open(max(ocrs, key=os.path.getmtime), encoding="utf-8", errors="ignore").read()
            ocr_tok = set(toks(ocr_txt))
            # halüsinasyon: cast/yön tokenları OCR'da var mı
            hall = []
            for nm in cast + yon:
                tk = toks(nm)
                if tk and not all(x in ocr_tok for x in tk):
                    hall.append(nm)
            rows.append({"film": name, "yon": yon, "cast_n": len(cast), "cast": cast,
                         "hallusinasyon": hall, "yon_bos": not yon})
        except Exception as e:
            rows.append({"film": name, "hata": str(e)})
    json.dump(rows, open(r"E:\MITAS\outputs\_morning_audit.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    hall_films = [r for r in rows if r.get("hallusinasyon")]
    print(f"# {len(rows)} künye denetlendi")
    print(f"# HALÜSİNASYON (OCR'da olmayan isim) olan film: {len(hall_films)}  (0 BEKLENİR — kalkan)")
    for r in hall_films:
        print(f"  RED FLAG {r['film']}: {r['hallusinasyon']}")
    print(f"# yön boş (okunamadı): {sum(1 for r in rows if r.get('yon_bos'))}/{len(rows)}")
    print(f"# cast<3: {sum(1 for r in rows if r.get('cast_n',9)<3)}")
    print("\n=== TÜM FİLMLER (yön | cast) ===")
    for r in rows:
        if r.get("hata"): print(f"  {r['film']}: HATA {r['hata']}"); continue
        print(f"  {r['film'][:55]}\n     YÖN={r['yon']} CAST={r['cast'][:6]}")

if __name__ == "__main__":
    main()
