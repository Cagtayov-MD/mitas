# -*- coding: utf-8 -*-
"""34 afişsiz film kök-neden teşhisi. PY_OCR (venvs/ocr) ile koş.
Her film: kimlik doğrulama (crosscheck) + IMDb aday + ÜRETİM fetch + KAPI-BYPASS fetch.
Kategori belirler ve outputs/afis_teshis.json yazar."""
import sys, os, json, re, importlib.util, tempfile
sys.path.insert(0, r"E:\MITAS\scripts")
import credit_crosscheck as cc

# poster_fetch yükle
spec = importlib.util.spec_from_file_location("pf", r"E:\MITAS\OCR-worktree\pdf-mitas\poster_fetch.py")
pf = importlib.util.module_from_spec(spec); spec.loader.exec_module(pf)

fields = json.load(open(r"E:\MITAS\outputs\afis_fields.json", encoding="utf-8"))
census = json.load(open(r"E:\MITAS\outputs\afis_census.json", encoding="utf-8"))["KONTROL"]
yok = [r for r in census if not r["has_poster"]]

kb = cc.CreditKB()
TMP = tempfile.gettempdir()

def fetch_try(title, original, year, cast, imdb_id=None, tmdb_id=None, tag="x"):
    out = os.path.join(TMP, f"afis_probe_{tag}.jpg")
    try:
        if os.path.exists(out): os.remove(out)
    except OSError: pass
    try:
        res = pf.fetch_poster(title, out, original=original, year=year, cast=cast or [],
                              imdb_id=imdb_id, tmdb_id=tmdb_id)
        if res and os.path.exists(out) and os.path.getsize(out) > 5000:
            from PIL import Image
            with Image.open(out) as im: w,h = im.size
            return {"ok": True, "w": w, "h": h, "portrait": h>w, "size": os.path.getsize(out)}
    except Exception as e:
        return {"ok": False, "err": str(e)[:120]}
    return {"ok": False}

results = []
for i, r in enumerate(yok):
    fn = r["file"]; trt = r["trt"]
    d = fields.get(fn, {})
    title = d.get("title") or fn
    original = d.get("subtitle")
    year = d.get("year")
    cast = d.get("cast") or []
    yon = (d.get("yonetmen") or [None])[0]
    rec = {"file": fn, "title": title, "original": original, "year": year,
           "cast_n": len(cast), "yon": yon}
    sys.stderr.write(f"[{i+1}/{len(yok)}] {title}\n"); sys.stderr.flush()

    # A) kimlik doğrulama (üretimdeki gate ile aynı)
    try:
        ch = kb.crosscheck(yon or "", cast, title_tr=title, original=original, year=year)
    except Exception as e:
        ch = {"verdict": f"HATA:{e}"}
    verdict = ch.get("verdict")
    cast_ov = ch.get("cast_ortusme") or 0
    matched_id = ch.get("matched_imdb_id")
    rec["verdict"] = verdict
    rec["cast_ortusme"] = cast_ov
    kimlik = (verdict == "TEYİT") or (cast_ov >= 3)
    rec["kimlik_dogrulandi"] = kimlik

    # B) IMDb aday var mı (film tanınıyor mu)
    try:
        cands = kb.imdb_find(title_tr=title, original=original, year=year)
    except Exception:
        cands = []
    rec["imdb_aday_n"] = len(cands)
    best_imdb = matched_id or (cands[0].get("id") if cands else None)
    rec["best_imdb_id"] = best_imdb

    # C) ÜRETİM fetch (gate'e uygun: id YALNIZ kimlik doğrulanmışsa)
    prod = fetch_try(title, original, year, cast,
                     imdb_id=(best_imdb if kimlik else None), tag="prod")
    rec["uretim_fetch"] = prod

    # D) KAPI-BYPASS fetch (id zorla ver — afiş GERÇEKTEN var mı?)
    byp = fetch_try(title, original, year, cast, imdb_id=best_imdb, tag="byp") if best_imdb else {"ok": False, "no_id": True}
    rec["bypass_fetch"] = byp

    # kategori
    if not cast and not yon:
        cat = "UST_AKIS_OKUMA_YOK"      # kadro+yönetmen hiç okunamadı
    elif prod.get("ok") and prod.get("portrait"):
        cat = "URETILEBILIR_SIMDI"       # şimdi üretirdi (orijinal koşu stale/geçici)
    elif prod.get("ok") and not prod.get("portrait"):
        cat = "YATAY_REDDEDILDI"         # bulundu ama yatay → poster_ok red
    elif not kimlik and byp.get("ok") and byp.get("portrait"):
        cat = "KAPI_BLOKE_AFIS_VAR"      # kimlik doğrulanmadı ama afiş bulunabilir
    elif kimlik and byp.get("ok") and not prod.get("ok"):
        cat = "FETCH_MANTIK_BOSLUGU"     # kimlik OK, bypass buldu, üretim bulamadı
    elif byp.get("ok") and byp.get("portrait"):
        cat = "BULUNUR_AMA_URETIM_YOK"
    else:
        cat = "AFIS_BULUNAMADI"          # hiçbir yoldan portre afiş yok
    rec["kategori"] = cat
    results.append(rec)
    # incremental
    json.dump(results, open(r"E:\MITAS\outputs\afis_teshis.json","w",encoding="utf-8"),
              ensure_ascii=False, indent=1)

kb.close()
# özet
from collections import Counter
c = Counter(r["kategori"] for r in results)
print("\n=== KATEGORİ DAĞILIMI (34 afişsiz) ===")
for k,v in c.most_common():
    print(f"  {v:2d}  {k}")
print("\n[yazıldı] outputs/afis_teshis.json")
