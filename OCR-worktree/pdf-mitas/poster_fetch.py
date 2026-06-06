# -*- coding: utf-8 -*-
"""MITAS — afiş (poster) indirici (keysiz, GÜVENLİ eşleştirme).

IMDb Suggestion API ile başlıktan afiş çeker. SADECE güvenli tek aday indirilir:
  • tam-başlık + tek sonuç, VEYA
  • çok sonuç → bilinen OYUNCU/YÖNETMEN adıyla teyit (IMDb 's' alanı), VEYA
  • çok sonuç → YIL ile teyit.
Aksi halde None (yanlış afiş gitmesin → PDF'de afiş yok, ses/altyazı bloğu kalır).

YABANCI FİLM: TRT başlığı Türkçe ("SİYAH İNCİ") ama IMDb İngilizce ("Black Beauty").
→ `original` (XML orijinal ad) BİRİNCİL sorgu olarak verilir. TRT yılı çoğu zaman
katalog yılıdır (film yılı değil) → çok-sürümlü filmlerde yıl ayraç olarak YETMEZ;
bu yüzden ASIL ayraç parse edilmiş KADRO'dur (cast/crew → IMDb 's' alanı).

KİRLİ BAŞLIK: OCR/iş akışı eki içerir ("AHLAT AGACI son4dk"). IMDb suggestion API
böyle bir sorguya HİÇ sonuç dönmez. `_clean_title_for_search` test/OCR eklerini ve
parantez notlarını atar ("AHLAT AGACI"); hem ham hem temiz hali sorgulanır. Eşleşme
çekirdeği (exact-norm + kadro/yıl teyidi) DEĞİŞMEZ → yanlış afiş riski artmaz.
"""
from __future__ import annotations
import json
import re
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

# Turkce harfleri ASCII karsiligina indir (deterministik, yuksek-guven harita).
# Boylece TRT'nin Turkce orijinal adi ("Ahlat Agaci") ile IMDb'nin ASCII sakladigi
# baslik ("Ahlat Agaci") AYNI norm'a duser. Eski _norm Turkce harfleri tamamen
# atiyordu ("Agaci" -> "aac"), bu da temiz bir baslikta sessizce eslesmeyi bozuyordu.
_TR_FOLD = str.maketrans({
    "ı": "i", "İ": "i", "ğ": "g", "Ğ": "g", "ş": "s", "Ş": "s",
    "ç": "c", "Ç": "c", "ö": "o", "Ö": "o", "ü": "u", "Ü": "u",
})

# Baslik temizleme: OCR/test ekleri ("son 4 dk"), parantez notlari, sondaki "_12".
# Yalniz GUVENLI/yuksek-guven kaliplari atar; gercek baslik kelimesine dokunmaz.
_CLEAN_PATTERNS = [
    re.compile(r"\([^)]*\)"),                          # (parantez ici not)
    re.compile(r"\[[^\]]*\]"),                         # [koseli not]
    re.compile(r"\b(?:son|ilk)\s*\d+\s*(?:dk|dakika|sn|saniye|sa|saat)\b", re.I),
    re.compile(r"\b(?:giris|cikis|jenerik|fragman|tanitim|deneme|test|kopya|copy|sample)\b", re.I),
    re.compile(r"[_\-\s]+\d+\s*$"),                    # sondaki "_12" / "- 3" kuyrugu
]


def _get(url: str, binary: bool = False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=20, context=_CTX) as r:
        return r.read() if binary else r.read().decode("utf-8", "replace")


def _norm(s: str) -> str:
    # Once Turkce -> ASCII fold (kayipsiz/tutarli), sonra kucult + alnum disini at.
    return re.sub(r"[^a-z0-9]", "", (s or "").translate(_TR_FOLD).lower())


def _clean_title_for_search(title: str) -> str:
    """Kirli basligi IMDb sorgusuna uygun temiz bir ada indir.

    IMDb suggestion API kirli sorguya ("Ahlat Agaci son4dk") HIC sonuc donmez;
    test/OCR ekleri temizlenince ("Ahlat Agaci") dogru film gelir. Burada SADECE
    yuksek-guven kaliplar atilir (test eki, parantez notu, sondaki sayi kuyrugu);
    gercek baslik kelimeleri korunur. ASCII fold YAPILMAZ (sorgu okunur kalsin,
    IMDb Turkce karakteri kendi cozer); fold yalniz _norm eslestirmesinde.
    """
    if not title:
        return ""
    s = title
    for pat in _CLEAN_PATTERNS:
        s = pat.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" -_·.")
    return s


def _big(img: str) -> str:
    return (re.sub(r"(@+)\._V1_.*$", r"\1._V1_SX1000.jpg", img) if "._V1_" in img
            else re.sub(r"(@+)\.jpg$", r"\1._V1_SX1000.jpg", img))


def _names_norm(*groups) -> list:
    """cast/crew adlarını norm'lanmış, ayraç-için-güvenli (uzunluk≥6) listeye indir."""
    out = []
    for g in groups:
        if not g:
            continue
        items = g if isinstance(g, (list, tuple)) else [g]
        for it in items:
            # crew (rol, [adlar]) demeti de gelebilir
            vals = it[1] if isinstance(it, (list, tuple)) and len(it) == 2 else it
            vals = vals if isinstance(vals, (list, tuple)) else [vals]
            for nm in vals:
                n = _norm(nm)
                if len(n) >= 6:          # "katewinslet", "mackenziefoy"... kısa/çakışan adları ele
                    out.append(n)
    return out


def _cand_has_name(cand: dict, names_norm: list) -> bool:
    """aday IMDb kaydının 's' (başrol/özet) alanında bilinen bir ad geçiyor mu."""
    s = _norm(cand.get("s"))
    return bool(s) and any(n in s for n in (names_norm or []))


def _save_image(data: bytes, out_path) -> str | None:
    """Boyut/bütünlük kontrolünden geçen görseli diske yaz. Hatalıysa None."""
    if len(data) < 5000:
        return None
    try:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(data)
        return str(out_path)
    except Exception:
        return None


def _fetch_tmdb_poster(tmdb_id=None, imdb_id=None, title=None, original=None, year=None) -> bytes | None:
    """TMDB API ile afiş çek. MITAS_TMDB/TMDB_API_KEY env yoksa None.
    Sıra: tmdb_id → IMDb id (/find) → başlık araması (orijinal önce, sonra TR; yıl ile daralt)."""
    import os
    key = os.environ.get("MITAS_TMDB") or os.environ.get("TMDB_API_KEY")
    if not key:
        return None

    def _data(path):
        if not path:
            return None
        try:
            return _get(f"https://image.tmdb.org/t/p/w780{path}", binary=True)
        except Exception:
            return None

    try:
        if tmdb_id:
            meta = json.loads(_get(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={key}"))
            d = _data(meta.get("poster_path"))
            if d:
                return d
        if imdb_id:                                  # IMDb id → /find (DOĞRU endpoint; /movie/{tt} 404 verir)
            fr = json.loads(_get(f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={key}&external_source=imdb_id"))
            for kk in ("movie_results", "tv_results"):       # film + DİZİ (Diriliş = tv_results)
                for m in (fr.get(kk) or []):
                    d = _data(m.get("poster_path"))
                    if d:
                        return d
        for q in (original, title):                  # başlık araması (yabancı orijinal önce)
            if not q:
                continue
            for kind in ("movie", "tv"):             # FİLM ve DİZİ ara (Diriliş Ertuğrul = tv)
                url = (f"https://api.themoviedb.org/3/search/{kind}?api_key={key}"
                       f"&query={urllib.parse.quote(q)}&include_adult=false")
                if year:
                    url += (f"&year={year}" if kind == "movie" else f"&first_air_date_year={year}")
                res = (json.loads(_get(url)).get("results") or [])
                if res:
                    d = _data(res[0].get("poster_path"))
                    if d:
                        return d
    except Exception:
        return None
    return None


def _fetch_omdb_poster(imdb_id=None, title=None, year=None) -> bytes | None:
    """OMDb API ile afiş çek (IMDb/Amazon posteri). MITAS_OMDB/OMDB_API_KEY env yoksa None.
    IMDb id (i=) önce — en güveniliri; sonra başlık (t=) + yıl."""
    import os
    key = os.environ.get("MITAS_OMDB") or os.environ.get("OMDB_API_KEY")
    if not key:
        return None
    urls = []
    if imdb_id:
        urls.append(f"http://www.omdbapi.com/?i={imdb_id}&apikey={key}")
    if title:
        u = f"http://www.omdbapi.com/?t={urllib.parse.quote(title)}&apikey={key}"
        if year:
            u += f"&y={year}"
        urls.append(u)
    for u in urls:
        try:
            meta = json.loads(_get(u))
            poster = meta.get("Poster")
            if poster and poster != "N/A":
                data = _get(poster, binary=True)
                if data and len(data) >= 5000:
                    return data
        except Exception:
            continue
    return None


def _fetch_wikipedia_poster(title: str, original: str | None = None) -> bytes | None:
    """Wikipedia pageimages API ile afiş verisi çek (anahtarsız). TR + EN wiki dene."""
    titles_to_try = []
    if original:
        titles_to_try.append(("en", original))
        clean = _clean_title_for_search(original)
        if clean and clean != original:
            titles_to_try.append(("en", clean))
    if title:
        titles_to_try.append(("tr", title))
        titles_to_try.append(("en", title))
        clean = _clean_title_for_search(title)
        if clean and clean != title:
            titles_to_try.append(("tr", clean))
            titles_to_try.append(("en", clean))
    seen = set()
    for lang, t in titles_to_try:
        key = (lang, _norm(t))
        if key in seen:
            continue
        seen.add(key)
        try:
            enc = urllib.parse.quote(t)
            url = (f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=pageimages"
                   f"&format=json&piprop=original&titles={enc}")
            resp = json.loads(_get(url))
            pages = (resp.get("query") or {}).get("pages") or {}
            for page in pages.values():
                img_url = (page.get("original") or {}).get("source")
                if img_url:
                    data = _get(img_url, binary=True)
                    if data and len(data) >= 5000:
                        return data
        except Exception:
            continue
    return None


def fetch_poster(title: str, out_path, *, original: str | None = None,
                 year: str | int | None = None, cast=None, crew=None,
                 also_query: str | None = None, tmdb_id=None, imdb_id=None) -> str | None:
    """Güvenli afiş indir → out_path (jpg). Bulunamaz/belirsizse None.

    title      : TRT/Türkçe ad (yedek sorgu).
    original   : XML orijinal ad — BİRİNCİL sorgu (yabancı filmde IMDb bunu tanır).
    year       : varsa yıl-teyidi (çok sonuçta yedek ayraç — TRT yılı güvenilmez olabilir).
    cast, crew : parse edilmiş kadro — çok sonuçta ASIL ayraç (IMDb 's' eşleşmesi).
    also_query : ek aday.
    tmdb_id    : Wikidata'dan gelen TMDB film id'si (yedek zinciri için).
    """
    names = _names_norm(cast, crew)
    # Aday sorgular: orijinal ad (yabanci film) ve TRT/Turkce ad; her birinin
    # hem HAM hem TEMIZLENMIS hali denenir. Ham IMDb'de zaten temizse calisir;
    # temiz hali "son4dk" gibi test/OCR eklerini atip dogru filmi getirir.
    # _search exact-norm eslesmesi degismedigi icin yanlis afis riski ARTMAZ.
    queries = []
    for q in (original, title, also_query):       # orijinal ad önce (yabancı film)
        for variant in (q, _clean_title_for_search(q) if q else None):
            if variant and variant not in queries:
                queries.append(variant)
    for q in queries:
        pick = _search(q, year, names)
        if pick:
            img = (pick.get("i") or {}).get("imageUrl")
            if not img:
                continue
            try:
                data = _get(_big(img), binary=True)
                result = _save_image(data, out_path)
                if result:
                    return result
            except Exception:  # noqa: BLE001
                continue
    # --- Yedek zinciri: IMDb Suggestion başarısız ---
    # (a) TMDB (sadece env'de anahtar varsa)
    try:
        data = _fetch_tmdb_poster(tmdb_id, imdb_id, title, original, year)
        if data:
            result = _save_image(data, out_path)
            if result:
                return result
    except Exception:
        pass
    # (b) OMDb (env anahtarı varsa — IMDb/Amazon posteri)
    try:
        data = _fetch_omdb_poster(imdb_id, original or title, year)
        if data:
            result = _save_image(data, out_path)
            if result:
                return result
    except Exception:
        pass
    # (c) Wikipedia/Wikimedia (anahtarsız)
    try:
        data = _fetch_wikipedia_poster(title, original)
        if data:
            result = _save_image(data, out_path)
            if result:
                return result
    except Exception:
        pass
    return None


def _search(query: str, year=None, names_norm=None):
    """IMDb suggestion → güvenli tek aday. Çok sonuçta: kadro > yıl ile teyit. Yoksa None."""
    o = _norm(query)
    if len(o) < 2:
        return None
    fc = (re.sub(r"[^a-z0-9]", "", query.lower())[:1] or "x")
    try:
        d = json.loads(_get(f"https://v3.sg.media-imdb.com/suggestion/{fc}/{urllib.parse.quote(query)}.json")).get("d", [])
    except Exception:  # noqa: BLE001
        return None
    tt = [x for x in d if str(x.get("id", "")).startswith("tt") and (x.get("i") or {}).get("imageUrl")]
    cands = [x for x in tt if _norm(x.get("l")) == o]                       # tam başlık
    if not cands and len(o) >= 5:                                          # gevşek (uzun başlık)
        # FIX: o.startswith(imdb_norm) yönünde imdb_norm'un da en az 5 karakter olması şart;
        # kısa IMDb başlığı ("Siyah") uzun sorgunun ("siyahinci") öneki olarak yanlış afiş getirmesin.
        cands = [x for x in tt if _norm(x.get("l")).startswith(o)
                 or (len(_norm(x.get("l"))) >= 5 and o.startswith(_norm(x.get("l"))))]
    if not cands:
        return None
    # Tam başlık eşleşmesi (o == imdb_norm) → tek aday güvenli, direkt dön.
    # Gevşek eşleşme → tek aday bile olsa kadro/yıl teyidi istenir (yanlış afiş engeli).
    is_exact = [x for x in cands if _norm(x.get("l")) == o]
    if len(is_exact) == 1:
        return is_exact[0]
    if names_norm:                                                         # ASIL ayraç: kadro teyidi
        named = [x for x in cands if _cand_has_name(x, names_norm)]
        if len(named) == 1:
            return named[0]
        if len(named) > 1 and year:                                        # birden çok → yıl ile daralt
            ym = [x for x in named if str(x.get("y")) == str(year)]
            if len(ym) == 1:
                return ym[0]
    if year:                                                               # yedek: yıl ile teyit
        ym = [x for x in cands if str(x.get("y")) == str(year)]
        if len(ym) == 1:
            return ym[0]
    return None                                                            # belirsiz → yok


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "AHLAT AGACI son4dk"
    print("temiz başlık:", repr(_clean_title_for_search(t)))
    p = fetch_poster(t, r"E:\MITAS\OCR-worktree\pdf-mitas\_afis_test.jpg",
                     cast=["Kate Winslet", "Mackenzie Foy"])
    print("afiş:", p or "BULUNAMADI")
