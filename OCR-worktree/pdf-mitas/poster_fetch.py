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


# URL-önbellek (hız #2, 2026-07-05): web_isit.py boş pencerede doldurur; karar mantığı
# DEĞİŞMEZ — yalnız HTTP yanıtı diskten döner. Modül yoksa sessizce cache'siz devam.
try:
    import web_cache as _wcache
except Exception:  # noqa: BLE001
    try:
        import os as _o
        import sys as _s
        _s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.dirname(_o.path.dirname(
            _o.path.abspath(__file__)))), "scripts"))
        import web_cache as _wcache
    except Exception:  # noqa: BLE001
        _wcache = None


def _get(url: str, binary: bool = False):
    if _wcache is not None:
        _c = _wcache.get(url)
        if _c is not None:
            return _c if binary else _c.decode("utf-8", "replace")
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=20, context=_CTX) as r:
        data = r.read()
    if _wcache is not None:
        _wcache.put(url, data)
    return data if binary else data.decode("utf-8", "replace")


def _norm(s: str) -> str:
    # Once Turkce -> ASCII fold (kayipsiz/tutarli), sonra kucult + alnum disini at.
    return re.sub(r"[^a-z0-9]", "", (s or "").translate(_TR_FOLD).lower())


# ── VERSİYON/SEKEL AYRACI (Çağatay 2026-06-14) ──────────────────────────────────
# Yıl GÜVENİLMEZ (TRT katalog yılı) → versiyon ayrımında KULLANILMAZ. Bunun yerine
# okunan başlıktaki sekel imzası ("KORSANLARI-2-...", "/2", "ROCKY II") + alt-başlık
# ("DEAD MAN'S CHEST" / "ÖLÜ ADAMIN SANDIĞI") AYRAÇ yapılır. Sekel imzası YOKSA guard
# tamamen ATIL (sıradan film hiç etkilenmez). Aktifken YALNIZ aday ELER → asla yeni
# yanlış afiş üretmez; en kötü hâlde afiş yok ("yanlış afiş > afiş yok" ilkesi).
# Karayip Korsanları 1↔2 gibi sekel karışmasını keser (KÖK: title-only matcher'a
# sekel/versiyon ayırt etme görevi VERİLMEMİŞTİ — bu o görevi atar).
_VER_ROMAN = {"ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9}


def _vfold(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").translate(_TR_FOLD).lower())


def _version_seq(text: str):
    f = " " + _vfold(text)
    m = re.search(r"[\/\-\s\.]\s*([2-9])(?![0-9])", f)        # ayraç+tek hane 2-9 (yıl/çok haneli değil)
    if m:
        return int(m.group(1))
    mr = re.search(r"\b(ii|iii|iv|v|vi|vii|viii|ix)\b", f)    # roman II-IX
    return _VER_ROMAN[mr.group(1)] if mr else None


def _version_subs(s: str) -> list:
    if not s:
        return []
    m = re.search(r"[\/\-\s\.]\s*[2-9](?![0-9])[\s\-\/:]*(.+)$", " " + s)   # numara SONRASI (ham; tire korunur)
    tail = m.group(1) if (m and m.group(1).strip()) else ""
    if not tail:
        parts = re.split(r"\s*[:/]\s*|\s+-\s+|(?<=\w)-(?=\w)", s)           # ayraç SONRASI son parça
        if len(parts) > 1:
            tail = parts[-1]
    return [w for w in _vfold(tail).split() if len(w) >= 4]                 # franchise tabanı hariç, anlamlı kelime


def _version_sig(title: str, original: str | None = None) -> dict:
    """Okunan başlık+orijinalden versiyon imzası: {seq, subs, active}. seq yoksa active=False (atıl)."""
    seq = _version_seq(" ".join(t for t in (title, original) if t))
    subs = []
    for s in (title, original):
        for w in _version_subs(s or ""):
            if w not in subs:
                subs.append(w)
    return {"seq": seq, "subs": subs, "active": bool(seq)}


def _version_ok(sig, cand_title) -> bool:
    """Aday IMDb başlığı okunan versiyonla tutarlı mı (sekel-no VEYA alt-başlık örtüşmesi). Atıl ise daima True."""
    if not sig or not sig.get("active"):
        return True
    cf = _vfold(cand_title)
    seq = sig.get("seq")
    if seq:
        rom = {2: "ii", 3: "iii", 4: "iv", 5: "v", 6: "vi", 7: "vii", 8: "viii", 9: "ix"}[seq]
        if re.search(r"(?<![a-z0-9])%d(?![0-9])" % seq, cf) or re.search(r"\b%s\b" % rom, cf):
            return True
    subs = sig.get("subs") or []
    if subs and any(s in cf for s in subs):
        return True
    return False


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


def _fetch_tmdb_poster(tmdb_id=None, imdb_id=None, title=None, original=None, year=None, vsig=None) -> bytes | None:
    """TMDB API ile afiş çek. MITAS_TMDB/TMDB_API_KEY env yoksa None.
    Sıra: tmdb_id → IMDb id (/find) → başlık araması (orijinal önce, sonra TR; yıl ile daralt).
    vsig verilirse (C8 MITAS_POSTER_VER_GATE) versiyon-tutarsız adaylar elenir; vsig.active=False → byte-identical."""
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

    # C8 — MITAS_POSTER_VER_GATE: versiyon/sekel ayraci (id-tabanlı yolda da uygula).
    # vsig.active=False ise _ver_ok_rec her zaman True → davranis BYTE-IDENTICAL (OFF gibi).
    _vgate = os.environ.get("MITAS_POSTER_VER_GATE", "1").strip().lower() not in ("0", "false", "off", "no")

    def _ver_ok_rec(rec):
        if not (_vgate and vsig and vsig.get("active")):
            return True
        cand = " ".join(str(rec.get(k) or "") for k in ("title", "original_title", "name", "original_name"))
        try:
            return _version_ok(vsig, cand)
        except Exception:
            return True

    try:
        if tmdb_id:
            meta = json.loads(_get(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={key}"))
            if _ver_ok_rec(meta):
                d = _data(meta.get("poster_path"))
                if d:
                    return d
        if imdb_id:                                  # IMDb id → /find (DOĞRU endpoint; /movie/{tt} 404 verir)
            fr = json.loads(_get(f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={key}&external_source=imdb_id"))
            for kk in ("movie_results", "tv_results"):       # film + DİZİ (Diriliş = tv_results)
                for m in (fr.get(kk) or []):
                    if _ver_ok_rec(m):
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
                # Title-only taramasında: ilk versiyon-uygun adayda kabul et (red → atla)
                for rec in res:
                    if _ver_ok_rec(rec):
                        d = _data(rec.get("poster_path"))
                        if d:
                            return d
                        break  # versiyon-uygun aday bulundu ama poster yok → sonraki query'ye geç
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
    vsig = _version_sig(title, original)   # sekel/versiyon ayracı (yıl kullanılmaz; sekel-imzası yoksa atıl)
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
        pick = _search(q, year, names, vsig)
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
    # KADRO-TEYİTLİ KAPI (KESİN İLKE 4): id-tabanlı dış aramalar (tmdb_id / imdb_id → TMDB /find)
    # YALNIZ kimlik doğrulanmışsa çalışır — çünkü credit_kb_lookup bu id'leri SADECE doğrulanmış
    # kimlikte verir; verilmediyse (None) BAŞLIK-tabanlı dış arama KADRO-KONTROLSÜZdür → yanlış afiş
    # riski. Doğrulanmış-id yoksa, başlık-tabanlı TMDB/OMDb/Wikipedia fallback'leri ATLA: tek geçerli
    # yol yukarıdaki kadro-teyitli IMDb _search; tutmadıysa afiş YOK.
    have_verified_id = bool(tmdb_id or imdb_id)
    if have_verified_id:
        # (a) TMDB (sadece env'de anahtar varsa) — doğrulanmış id ile
        try:
            data = _fetch_tmdb_poster(tmdb_id, imdb_id, title, original, year, vsig=vsig)
            if data:
                result = _save_image(data, out_path)
                if result:
                    return result
        except Exception:
            pass
        # (b) OMDb (env anahtarı varsa — IMDb/Amazon posteri) — doğrulanmış imdb_id ile
        try:
            data = _fetch_omdb_poster(imdb_id, original or title, year)
            if data:
                result = _save_image(data, out_path)
                if result:
                    return result
        except Exception:
            pass
        # (c) Wikipedia/Wikimedia (anahtarsız) — kimlik doğrulanmışken başlıkla afiş
        try:
            data = _fetch_wikipedia_poster(title, original)
            if data:
                result = _save_image(data, out_path)
                if result:
                    return result
        except Exception:
            pass
    return None


def _search(query: str, year=None, names_norm=None, vsig=None):
    """IMDb suggestion → güvenli tek aday. Çok sonuçta: kadro > yıl ile teyit. Yoksa None.
    vsig verilirse (sekel/versiyon imzası aktif) → versiyon-tutarsız adaylar ELENİR (Karayip 1↔2)."""
    # KADRO-ZORUNLU KAPI (Çağatay 2026-06-14): kadro/crew sinyali HİÇ yoksa başlık-tabanlı eşleşme YAPMA.
    # Boş-kadroda tek-exact başlık körlemesine dönüyordu → "şans ile yürümez": doğrulayacak isim yoksa
    # afiş YOK. AKIL OYUNLARI (boş kadro + "Beautiful Mind" → yanlış Kore dizisi) tam buradan sızmıştı;
    # remake'lerde de (Notre Dame 1955/1996) tek ayraç güvenilmez yıl kalıyordu. Kimlik BAŞKA yolla
    # (yönetmen-TEYİT / web-çapa) doğrulanmışsa afiş yine gelir: fetch_poster'ın id-tabanlı yolu AYRIDIR.
    if not names_norm:
        return None
    o = _norm(query)
    if len(o) < 2:
        return None
    fc = (re.sub(r"[^a-z0-9]", "", query.lower())[:1] or "x")
    try:
        d = json.loads(_get(f"https://v3.sg.media-imdb.com/suggestion/{fc}/{urllib.parse.quote(query)}.json")).get("d", [])
    except Exception:  # noqa: BLE001
        return None
    tt = [x for x in d if str(x.get("id", "")).startswith("tt") and (x.get("i") or {}).get("imageUrl")]
    # VERSİYON AYRACI: okunan başlıkta sekel imzası varsa (KORSANLARI-2-/ROCKY II), aday başlığı
    # o versiyonla tutarsızsa ELE (yanlış sekel afişini keser). İmza yoksa _version_ok hep True → atıl.
    if vsig and vsig.get("active"):
        tt = [x for x in tt if _version_ok(vsig, x.get("l"))]
        if not tt:
            return None
    cands = [x for x in tt if _norm(x.get("l")) == o]                       # tam başlık
    if not cands and len(o) >= 5:                                          # gevşek (uzun başlık)
        # FIX: o.startswith(imdb_norm) yönünde imdb_norm'un da en az 5 karakter olması şart;
        # kısa IMDb başlığı ("Siyah") uzun sorgunun ("siyahinci") öneki olarak yanlış afiş getirmesin.
        cands = [x for x in tt if _norm(x.get("l")).startswith(o)
                 or (len(_norm(x.get("l"))) >= 5 and o.startswith(_norm(x.get("l"))))]
    if not cands:
        return None
    # Tam başlık eşleşmesi (o == imdb_norm) → kural olarak güvenli tek aday.
    # ANCAK yabancı-başlık tuzağı: gerçek film (ör. "Ahlat Ağacı") IMDb'de farklı
    # başlıkla ("The Wild Pear Tree") kayıtlıyken, aynı adı taşıyan ALAKASIZ bir yapım
    # tek-exact olarak kazanıyordu. Kadro biliniyor + exact adayın 's' alanı DOLU ama
    # kadrodan kimse geçmiyorsa (POZİTİF çelişki) → havuzda kadrosu TUTAN adayı tercih et;
    # net değilse yanlış afiş yerine None. ('s' boşsa kanıt yok → exact'e DOKUNMA, regresyon-güvenli.)
    is_exact = [x for x in cands if _norm(x.get("l")) == o]
    if len(is_exact) == 1:
        ex = is_exact[0]
        if names_norm and (ex.get("s") or "").strip() and not _cand_has_name(ex, names_norm):
            named = [x for x in tt if _cand_has_name(x, names_norm)]
            if len(named) == 1:
                return named[0]
            return None  # kadro çelişiyor + tek-net alternatif yok → afiş YOK (yıl ile TAHMİN YOK)
        return ex
    if names_norm:                                                         # ASIL ayraç: kadro teyidi
        named = [x for x in cands if _cand_has_name(x, names_norm)]
        if len(named) == 1:
            return named[0]
    # YIL-TABANLI VERSİYON SEÇİMİ KALDIRILDI (Çağatay 2026-06-14): TRT yılı GÜVENİLMEZ (katalog yılı).
    # Kadro (remake'te farklı kadro) ya da versiyon-imzası (sekelde numara/alt-başlık) tek adaya
    # indiremiyorsa, güvenilmez yıla düşüp versiyon seçmek = ŞANS. 85↔99 remake / Karayip 1-2-3 yanlış
    # eşleşmesi tam buradan sızıyordu (kanıt: Hunchback yanlış-yıl→yanlış versiyon; Pirates year=2017
    # → 5. film). Deterministik kural: tek adaya KADRO/VERSİYON ile inemiyorsak → afiş YOK.
    return None


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "AHLAT AGACI son4dk"
    print("temiz başlık:", repr(_clean_title_for_search(t)))
    p = fetch_poster(t, r"E:\MITAS\OCR-worktree\pdf-mitas\_afis_test.jpg",
                     cast=["Kate Winslet", "Mackenzie Foy"])
    print("afiş:", p or "BULUNAMADI")
