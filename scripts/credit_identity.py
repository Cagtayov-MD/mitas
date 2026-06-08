# -*- coding: utf-8 -*-
"""credit_identity.py — KADRO-KONSENSÜS ile film kimliği (başlık DEĞİL, kadro hakem).

OCR'dan okunan oyuncu adlarını TMDB'de kişi olarak arar, filmografyalarını toplar;
EN ÇOK OCR-oyuncusunun kesiştiği filmi seçer. Yönetmen güçlü oy. Yıl KULLANILMAZ
(TRT yılı = katalog yılı; OCR © yılı güvenilmez/eksik — ölçülerek doğrulandı).

KESİN kapısı (Çağatay 2026-06-08):
  - >= 3 oyuncu oyu, YA DA yönetmen-eşleşti + >= 2 oyuncu oyu.
  - SERİ-BELİRSİZLİK: kadro birden çok filme güçlü işaret ediyorsa (2. aday >=3 ve tepeye
    yakın = sequel/aynı-kadro kümesi, örn. Star Wars) → TAHMİN ETME → KONTROL.
KESİN değilse → original-ad/afiş için kullanma (yanlış afiş > afiş yok).

resolve(cast, director) → dict | None:
  {original_title, tmdb_id, votes, director_match, ambiguous, status('KESIN'|'KONTROL')}
"""
from __future__ import annotations
import json, os, re, ssl, urllib.parse, urllib.request

_CTX = ssl.create_default_context(); _CTX.check_hostname = False; _CTX.verify_mode = ssl.CERT_NONE
_UA = {"User-Agent": "MITAS/1.0"}
_FOLD = str.maketrans({"İ":"I","ı":"i","Ş":"S","ş":"s","Ğ":"G","ğ":"g","Ç":"C","ç":"c","Ö":"O","ö":"o","Ü":"U","ü":"u"})
# OCR gürültüsü / rol etiketi / cümle = kişi adı DEĞİL.
_NOISE = re.compile(r"\b(AS|THE|AND|OF|REAL LIFE|DESTROY|EMPIRE|SPACE|GALACT|ENTIRE|HUSBAND|DIRECTED|PRODUCED|MUSIC|PHOTO|EDITOR|SCREENPLAY|STORY|BASED|PRESENTS|STARRING|WITH|A FILM)\b", re.I)


def _get(url: str):
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=20, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def is_name(s: str) -> bool:
    s = (s or "").strip().strip("-• ").strip()
    if not s or _NOISE.search(s):
        return False
    toks = [t for t in re.split(r"[\s\-]+", s) if t]
    if not (2 <= len(toks) <= 4):
        return False
    if any(any(ch.isdigit() for ch in t) for t in toks):
        return False
    if sum(len(t) for t in toks) > 40:
        return False
    return True


def _person_movies(name: str, key: str, cache: dict):
    q = name.translate(_FOLD).strip()
    if q in cache:
        return cache[q]
    out = {}
    try:
        pr = _get(f"https://api.themoviedb.org/3/search/person?api_key={key}&query={urllib.parse.quote(q)}")
        res = pr.get("results") or []
        if res:
            pid = res[0]["id"]
            cr = _get(f"https://api.themoviedb.org/3/person/{pid}/movie_credits?api_key={key}")
            for m in (cr.get("cast") or []):
                out[m["id"]] = (m.get("original_title") or m.get("title") or "", (m.get("release_date") or "")[:4])
            for m in (cr.get("crew") or []):
                if m.get("job") == "Director":
                    out[m["id"]] = (m.get("original_title") or m.get("title") or "", (m.get("release_date") or "")[:4])
    except Exception:
        pass
    cache[q] = out
    return out


def resolve(cast, director=None, *, tmdb_key: str | None = None, max_year=None) -> dict | None:
    """Kadro-konsensüs ile film kimliği. KESİN değilse status='KONTROL' döner (afişe kullanma).

    max_year: TRT katalog yılı (varsa). ERA-SANITY: çözülen film bundan ANLAMLI yeni olamaz
    (TRT bir filmi kataloglamışsa film o yıldan eski/eşittir) → anakronik eşleşme reddedilir
    (örn. eski TRT filmi 2025 yapımına oturmasın — YETİMLER vakası). Yıl AYRAÇ değil, TAVAN.
    """
    key = tmdb_key or os.environ.get("MITAS_TMDB") or os.environ.get("TMDB_API_KEY")
    if not key:
        return None
    voters = [c for c in (cast or []) if is_name(c)][:6]
    if len(voters) < 2:
        return None
    cache: dict = {}
    votes: dict = {}
    for nm in voters:
        for mid, (orig, yr) in _person_movies(nm, key, cache).items():
            cnt, o, y = votes.get(mid, (0, orig, yr))
            votes[mid] = (cnt + 1, orig, yr)
    dir_movies = set(_person_movies(director, key, cache).keys()) if (director and is_name(director)) else set()
    try:
        _ceil = int(max_year) + 2 if max_year else None
    except (TypeError, ValueError):
        _ceil = None
    ranked = []
    for mid, (cnt, orig, yr) in votes.items():
        if _ceil and yr and str(yr).isdigit() and int(yr) > _ceil:
            continue   # ERA-SANITY: TRT katalog yılından anlamlı yeni film = anakronik → reddet
        score = cnt + (3 if mid in dir_movies else 0)
        ranked.append((score, cnt, mid in dir_movies, mid, orig, yr))
    ranked.sort(reverse=True)
    if not ranked:
        return None
    score, cnt, dirmatch, mid, orig, yr = ranked[0]
    second_cnt = ranked[1][1] if len(ranked) > 1 else 0
    gate = (cnt >= 3) or (dirmatch and cnt >= 2)
    ambiguous = (second_cnt >= 3) and (second_cnt >= cnt - 1)   # seri/aynı-kadro kümesi → tahmin etme
    status = "KESIN" if (gate and not ambiguous) else "KONTROL"
    return {
        "original_title": orig, "tmdb_id": mid, "votes": cnt,
        "director_match": dirmatch, "ambiguous": ambiguous, "status": status,
    }
