# -*- coding: utf-8 -*-
"""credit_identity_test.py — KADRO-KONSENSÜS ile film kimliği (başlık DEĞİL).

Database'deki işlenmiş filmlerin OCR kadrosunu (kunye_teslim.md) okur; her ismi TMDB'de
kişi olarak arar, filmografyalarını toplar; EN ÇOK OCR-oyuncusunun kesiştiği filmi seçer
(yönetmen güçlü oy). Yıl KULLANILMAZ (TRT yılı güvenilmez). Çıktı: TR başlık → orijinal ad.
Ölçüm amaçlı; outputs/credit_identity_test.csv yazar.
"""
from __future__ import annotations
import csv, json, os, re, sys, time, urllib.parse, urllib.request, ssl
from pathlib import Path

DB = Path(r"E:\MITAS\Database")
OUT = Path(r"E:\MITAS\outputs\credit_identity_test.csv")
KEY = os.environ.get("MITAS_TMDB") or os.environ.get("TMDB_API_KEY") or ""
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 50
_CTX = ssl.create_default_context(); _CTX.check_hostname = False; _CTX.verify_mode = ssl.CERT_NONE
_UA = {"User-Agent": "MITAS/1.0"}

_FOLD = str.maketrans({"İ":"I","ı":"i","Ş":"S","ş":"s","Ğ":"G","ğ":"g","Ç":"C","ç":"c","Ö":"O","ö":"o","Ü":"U","ü":"u"})
# OCR gürültüsü / rol etiketi / cümle olan satırları ele (kişi adı değil).
_NOISE = re.compile(r"\b(AS|THE|AND|OF|REAL LIFE|DESTROY|EMPIRE|SPACE|GALACT|ENTIRE|HUSBAND|DIRECTED|PRODUCED|MUSIC|PHOTO|EDITOR|SCREENPLAY|STORY|BASED|PRESENTS|STARRING|WITH|A FILM)\b", re.I)

def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=20, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def is_name(s: str) -> bool:
    s = s.strip().strip("-• ").strip()
    if not s or _NOISE.search(s): return False
    toks = [t for t in re.split(r"[\s\-]+", s) if t]
    if not (2 <= len(toks) <= 4): return False            # ad-soyad (2-4 kelime)
    if any(any(ch.isdigit() for ch in t) for t in toks): return False
    if sum(len(t) for t in toks) > 40: return False       # cümle değil
    return True

def parse_md(md: Path):
    t = md.read_text(encoding="utf-8", errors="replace")
    cast = []
    m = re.search(r"## Oyuncular(.*?)(\n##|\Z)", t, re.S)
    if m:
        for ln in m.group(1).splitlines():
            ln = ln.strip().lstrip("-•").strip()
            if is_name(ln): cast.append(ln)
    director = ""
    d = re.search(r"Yönetmen:\s*(.+)", t)
    if d:
        cand = d.group(1).split(",")[0].strip()
        if is_name(cand): director = cand
    return cast[:6], director

_pcache = {}
def person_movies(name: str):
    q = name.translate(_FOLD).strip()
    if q in _pcache: return _pcache[q]
    out = {}
    try:
        pr = _get(f"https://api.themoviedb.org/3/search/person?api_key={KEY}&query={urllib.parse.quote(q)}")
        res = pr.get("results") or []
        if res:
            pid = res[0]["id"]
            cr = _get(f"https://api.themoviedb.org/3/person/{pid}/movie_credits?api_key={KEY}")
            for m in (cr.get("cast") or []):
                out[m["id"]] = (m.get("original_title") or m.get("title") or "", (m.get("release_date") or "")[:4])
            for m in (cr.get("crew") or []):      # yönetmen için crew de
                if m.get("job") == "Director":
                    out[m["id"]] = (m.get("original_title") or m.get("title") or "", (m.get("release_date") or "")[:4])
    except Exception:
        pass
    _pcache[q] = out
    return out

def resolve(cast, director):
    voters = list(cast)
    votes = {}   # movie_id -> (count, orig, year)
    for nm in voters:
        for mid, (orig, yr) in person_movies(nm).items():
            c, o, y = votes.get(mid, (0, orig, yr))
            votes[mid] = (c + 1, orig, yr)
    dir_movies = set(person_movies(director).keys()) if director else set()
    ranked = []
    for mid, (cnt, orig, yr) in votes.items():
        score = cnt + (3 if mid in dir_movies else 0)   # yönetmen = +3 güçlü oy
        ranked.append((score, cnt, mid in dir_movies, orig, yr))
    ranked.sort(reverse=True)
    if not ranked:
        return None, 0, len(voters)
    second_cnt = ranked[1][1] if len(ranked) > 1 else 0   # 2. adayın OYUNCU oyu (seri-belirsizlik tespiti)
    return ranked[0], second_cnt, len(voters)

def main():
    if not KEY:
        print("MITAS_TMDB yok"); return
    dirs = [d for d in DB.iterdir() if d.is_dir() and (d / "_DURUM.json").exists()]
    rows = []
    n = 0
    for d in dirs:
        if n >= LIMIT: break
        md = next((p for p in d.rglob("kunye_teslim.md")), None) or next((p for p in d.rglob("kunye*.md")), None)
        if not md: continue
        try:
            durum = json.loads((d / "_DURUM.json").read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        cast, director = parse_md(md)
        if len(cast) < 2:
            rows.append((durum.get("trt_id",""), durum.get("title",""), "(kadro<2 - OCR yetersiz)", 0, False, "", "KONTROL")); n += 1; continue
        best, second_cnt, nv = resolve(cast, director)
        if best:
            score, cnt, dirmatch, orig, yr = best
            # KESIN kapisi: 3 oyuncu OY, YA DA yonetmen + 2 oyuncu. (yonetmen bari 3->2 indirir, asla 2'nin altina degil)
            gate = (cnt >= 3) or (dirmatch and cnt >= 2)
            # SERI-BELIRSIZLIK: kadro birden cok filme guclu isaret ediyorsa (2. aday >=3 ve tepeye yakin)
            # = sequel/ayni-kadro kumesi (Star Wars) -> yil/yonetmen yoksa TAHMIN ETME -> KONTROL.
            ambiguous = (second_cnt >= 3) and (second_cnt >= cnt - 1)
            status = "KESIN" if (gate and not ambiguous) else "KONTROL"
            orig2 = orig + (" [belirsiz-seri]" if (gate and ambiguous) else "")
            rows.append((durum.get("trt_id",""), durum.get("title",""), orig2, cnt, dirmatch, yr, status))
        else:
            rows.append((durum.get("trt_id",""), durum.get("title",""), "(eslesme yok)", 0, False, "", "KONTROL"))
        n += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.writer(h); w.writerow(["trt","tr_baslik","orijinal_resolved","oyuncu_oyu","yonetmen_eslesti","yil","durum"])
        for r in rows: w.writerow(list(r) + [""] * (7 - len(r)))

    kesin = sum(1 for r in rows if len(r) >= 7 and r[6] == "KESIN")
    kontrol = len(rows) - kesin
    print(f"== KADRO-KONSENSUS KIMLIK (kapi: 3 oyuncu YA DA yonetmen+2) -- {len(rows)} film ==")
    print(f"  KESIN   : {kesin}")
    print(f"  KONTROL : {kontrol}")
    print(f"  CSV: {OUT}")

if __name__ == "__main__":
    main()
