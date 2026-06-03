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


def fetch_poster(title: str, out_path, *, original: str | None = None,
                 year: str | int | None = None, cast=None, crew=None,
                 also_query: str | None = None) -> str | None:
    """Güvenli afiş indir → out_path (jpg). Bulunamaz/belirsizse None.

    title      : TRT/Türkçe ad (yedek sorgu).
    original   : XML orijinal ad — BİRİNCİL sorgu (yabancı filmde IMDb bunu tanır).
    year       : varsa yıl-teyidi (çok sonuçta yedek ayraç — TRT yılı güvenilmez olabilir).
    cast, crew : parse edilmiş kadro — çok sonuçta ASIL ayraç (IMDb 's' eşleşmesi).
    also_query : ek aday.
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
                if len(data) < 5000:              # bozuk/çok küçük → atla
                    continue
                Path(out_path).parent.mkdir(parents=True, exist_ok=True)
                Path(out_path).write_bytes(data)
                return str(out_path)
            except Exception:  # noqa: BLE001
                continue
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
        cands = [x for x in tt if _norm(x.get("l")).startswith(o) or o.startswith(_norm(x.get("l")))]
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]
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
