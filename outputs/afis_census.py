# -*- coding: utf-8 -*-
"""Afiş census — her KONTROL PDF'inde afiş var mı, boyut/oran, cache durumu.
Çıktı: outputs/afis_census.json + ekrana özet tablo."""
import fitz, os, re, json, sys, glob

KONTROL = r"E:\MITAS\Mitas Output\export\KONTROL"
YEDEK   = r"E:\MITAS\Mitas Output\export\_KONTROL_orijinal_yedek"
CACHE   = r"E:\MITAS\_102_afis_cache"

def trt_from_name(fn):
    # "2008-1074-1-0000-72-1 AMİRAL.pdf" -> "2008-1074-1-0000-72-1"
    m = re.match(r"^(\d{4}-\d{4}-\d-\d{4}-\d{2}-\d)", fn)
    return m.group(1) if m else None

def analyze_pdf(path):
    """Sayfa-0'daki gömülü rasterleri çıkar; afiş = en büyük portre görsel."""
    info = {"images": [], "poster": None, "n_images": 0, "err": None}
    try:
        doc = fitz.open(path)
        pg = doc[0]
        imgs = pg.get_images(full=True)
        info["n_images"] = len(imgs)
        recs = []
        for im in imgs:
            xref = im[0]
            try:
                px = fitz.Pixmap(doc, xref)
                w, h = px.width, px.height
                # alfa/küçük logoları ele
                recs.append({"xref": xref, "w": w, "h": h, "area": w*h,
                             "portrait": h > w, "ratio": round(w/h, 3) if h else 0})
                px = None
            except Exception as e:
                recs.append({"xref": xref, "err": str(e)})
        # afiş adayı: portre + alan > 20000 (küçük ikon değil), en büyük alan
        cands = [r for r in recs if r.get("portrait") and r.get("area", 0) > 20000]
        cands.sort(key=lambda r: -r["area"])
        if cands:
            info["poster"] = cands[0]
        # yatay büyük görsel var mı (frame-grab şüphesi)?
        land = [r for r in recs if not r.get("portrait", True) and r.get("area", 0) > 50000]
        info["landscape_big"] = land[0] if land else None
        info["images"] = recs
        doc.close()
    except Exception as e:
        info["err"] = str(e)
    return info

def cache_dims(trt):
    if not trt: return None
    p = os.path.join(CACHE, trt + ".jpg")
    if not os.path.exists(p): return {"exists": False}
    try:
        from PIL import Image
        with Image.open(p) as im:
            w, h = im.size
        sz = os.path.getsize(p)
        return {"exists": True, "w": w, "h": h, "size": sz,
                "portrait": h > w, "ratio": round(w/h,3) if h else 0,
                "poster_ok": (sz > 5000 and h > w)}
    except Exception as e:
        return {"exists": True, "err": str(e), "size": os.path.getsize(p)}

def run(folder, label):
    rows = []
    pdfs = sorted(glob.glob(os.path.join(folder, "*.pdf")))
    for p in pdfs:
        fn = os.path.basename(p)
        trt = trt_from_name(fn)
        a = analyze_pdf(p)
        c = cache_dims(trt)
        rows.append({"file": fn, "trt": trt,
                     "has_poster": bool(a["poster"]),
                     "poster": a["poster"],
                     "landscape_big": a.get("landscape_big"),
                     "n_images": a["n_images"],
                     "err": a["err"],
                     "cache": c})
    return rows

if __name__ == "__main__":
    out = {}
    for folder, label in [(KONTROL, "KONTROL")]:
        rows = run(folder, label)
        out[label] = rows
        n = len(rows)
        has = sum(1 for r in rows if r["has_poster"])
        print(f"\n=== {label}: {n} PDF ===")
        print(f"  Afiş VAR : {has}")
        print(f"  Afiş YOK : {n-has}")
        # afiş yok ama cache'te dosya var (uyumsuzluk)
        yok_cache_var = [r for r in rows if not r["has_poster"] and r["cache"] and r["cache"].get("exists")]
        print(f"  Afiş YOK ama cache'te jpg VAR: {len(yok_cache_var)}")
        # cache'te yatay (poster_ok fail) olanlar
        cache_yatay = [r for r in rows if r["cache"] and r["cache"].get("exists") and not r["cache"].get("portrait", True)]
        print(f"  Cache jpg YATAY (poster_ok red): {len(cache_yatay)}")
    with open(r"E:\MITAS\outputs\afis_census.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n[yazıldı] outputs/afis_census.json")
