# -*- coding: utf-8 -*-
"""credit_qc_gates.py — QC2 graft mantığı (McGrady KULE KOPYASI, 2026-08-18).

scripts/credit_qc_gates.py'den farklar:
  • _looks_garble/_only_persons import'u kule-içi garble modülünden (scripts/
    credit_text_read yok — core.lexicon bağımlılığı yasak),
  • web_identity ağ katmanı: URL'ler urlencode ile kurulur (api_key asla URL
    metnine birleştirilmez); istem ÖNCE protokol+host izinlistesi VE çözülen
    IP'lerin tamamı Genel-IP denetiminden geçer (özel/loopback/link-local
    adres = istek yapılmaz — SSRF kapalı). Karar mantığı scripts/ ile birebir.
  Kalan mantık scripts/ orijinaliyle birebir.

Turnuva-sentezi cerrahi graftların ÇEKİRDEK mantığı:
  GRAFT-1: garble = "imza-yokluğu" kapısı. Bir OCR cast ismi KB-otoriter_cast'ten
           (cross-cast dahil) name_match/name_close imzası taşımıyorsa + kimlik
           KİLİTLİ ise → SUSPECT (KONTROL-işaretle, SİLME).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credit_crosscheck as cc  # name_match / name_close / CreditKB / crosscheck

try:
    from garble import _looks_garble  # kule-içi garble dedektörü (credit_text_read sökümü)
except Exception:
    def _looks_garble(_s):
        return False


def kb_signature(name, kb_cast):
    """İsim KB-otoriter_cast'te (cross-cast dahil) name_match VEYA name_close imzası taşıyor mu."""
    for a in (kb_cast or []):
        if cc.name_match(name, a) or cc.name_close(name, a):
            return a
    return None


def garble_no_signature_gate(read_cast, kb_cast, *, vl_cast=None, identity_locked=True):
    """GRAFT-1. Her OCR cast ismi için imza durumu + suspect kararı.
    suspect = kimlik KİLİTLİ + KB imzası YOK + VL imzası YOK → KONTROL-işaretle (silme)."""
    vl_cast = vl_cast or []
    rows = []
    for n in read_cast:
        kb_hit = kb_signature(n, kb_cast)
        vl_hit = any(cc.name_match(n, a) for a in vl_cast)
        suspect = bool(identity_locked) and (kb_hit is None) and (not vl_hit)
        rows.append({
            "isim": n, "kb_imza": kb_hit, "vl_imza": vl_hit,
            "suspect": suspect, "eski_looks_garble": bool(_looks_garble(n)),
        })
    return rows


def identity_first_cast(read_cast, kb_cast, *, vl_cast=None, max_out=8):
    """GRAFT-1 RAFİNE (kimlik-önce, ölçümle doğrulandı): kimlik KİLİTLİ varsayımıyla TEMİZ cast üret.
      • KB-imzalı OCR ismi → KANONİK KB yazımıyla tut (Cimcir→Cemcir)
      • imzasız OCR ismi → DÜŞ (garble: GEORCE STOAD / LEONARDO SEVERİNİ temizlenir)
      • KB otoriter_cast'ten OCR'da olmayanları SONA ekle (tamamlama), max_out'a kadar
    OCR sırası korunur (jenerik-otorite); KB yalnız kanonikler + tamamlar, EZMEZ.
    Döndürür: {temiz_cast, dususler, kaynak_izi}.

    KULE NOTU (2026-08-18): pipeline'da drop+add KALDIRILDI (OCR-otorite kanunu
    2026-06-13). Kule bu fonksiyonu çağırır ama çıktısını YALNIZ ÖNERİ olarak
    raporlar — motor.py tüketiciye temiz_cast'i EZDİRMEZ."""
    vl_cast = vl_cast or []
    out, iz, dususler = [], [], []
    used = set()
    for n in read_cast:
        exact = next((a for a in (kb_cast or []) if cc.name_match(n, a)), None)
        if exact:                                # TEYİTLİ → OCR yazımını TUT (Türkçe diakritik korunur)
            k = cc.fold(exact)
            if k not in used:
                out.append(n); used.add(k); iz.append({"isim": n, "kaynak": "ocr-teyitli"})
            continue
        close = next((a for a in (kb_cast or []) if cc.name_close(n, a)), None)
        if close:                                # MISREAD → KB kanonik yazımıyla düzelt
            k = cc.fold(close)
            if k not in used:
                out.append(close); used.add(k); iz.append({"isim": close, "kaynak": "kb-yazim-duzelt", "ocr_ham": n})
            continue
        if any(cc.name_match(n, x) for x in vl_cast):  # VL teyitli → tut
            out.append(n); iz.append({"isim": n, "kaynak": "ocr+vl"})
            continue
        dususler.append(n)                       # imzasız → garble/şüpheli → düş
    for a in (kb_cast or []):                    # KB tamamlama (OCR'da olmayan)
        if len(out) >= max_out:
            break
        k = cc.fold(a)
        if k not in used and not any(cc.name_match(a, o) for o in out):
            out.append(a); used.add(k); iz.append({"isim": a, "kaynak": "kb-tamamla"})
    return {"temiz_cast": out[:max_out], "dususler": dususler, "kaynak_izi": iz}


try:
    from garble import _only_persons as _op
except Exception:
    def _op(names):  # fallback: geçer her şey (yalnız None/boş-string filtre)
        return [n for n in (names or []) if n and str(n).strip()]


def identity_first_producer(read_yap, kb_yap, *, max_out=3):
    """GRAFT-P: yapımcı garble temizleme (identity_first_cast MİRROR'u, yapımcı-özgü).
      • KB-imzalı (name_match/name_close) OCR yapımcısını TUT (OCR yazımı veya KB kanonik).
      • İmzasız OCR yapımcısını DÜŞ (garble + şirket isimleri).
      • KB yapımcılarından (kb_yap) OCR'da olmayanları SONA ekle (tamamla), max_out=3.
      • KİŞİ-ONLY: _only_persons ile kurum/marka/studio/garble son süzgeçten geçer.
    Döndürür: {"temiz_yapimci": [...], "dususler": [...]}.

    KULE NOTU: pipeline'da KALDIRILDI (OCR-otorite); kule YALNIZ ÖNERİ olarak raporlar."""
    out, dususler, used = [], [], set()
    for n in (read_yap or []):
        exact = next((a for a in (kb_yap or []) if cc.name_match(n, a)), None)
        if exact:                               # TEYİTLİ → OCR yazımını koru
            k = cc.fold(exact)
            if k not in used:
                out.append(n); used.add(k)
            continue
        close = next((a for a in (kb_yap or []) if cc.name_close(n, a)), None)
        if close:                               # MISREAD → KB kanonik yazımıyla düzelt
            k = cc.fold(close)
            if k not in used:
                out.append(close); used.add(k)
            continue
        dususler.append(n)                      # imzasız → garble/şirket → düş
    for a in (kb_yap or []):                    # KB tamamlama (OCR'da olmayan)
        if len(out) >= max_out:
            break
        k = cc.fold(a)
        if k not in used and not any(cc.name_match(a, o) for o in out):
            out.append(a); used.add(k)
    # KİŞİ-ONLY son süzgeç: kurum/marka/studio/garble kalırsa at
    out = _op(out)[:max_out]
    return {"temiz_yapimci": out, "dususler": dususler}


def director_decision(read_director, cross, *, locked_min=2):
    """GRAFT-4 (kimlik-önce yönetmen). cross = crosscheck() çıktısı.
      verdict==TEYİT → OCR yönetmeni TUT (kanonik OCR).
      OCR boş + kimlik-KİLİTLİ + otoriter_yonetmen → KB-FILL (kırmızı-çizgi reconcile).
      verdict==ÇELİŞKİ (OCR yanlış, ör. Scorsese cameo) + kimlik-KİLİTLİ → KB ile DEĞİŞTİR.
      kimlik zayıf / KB-yön yok → '' (KONTROL).
    Döndürür: {yonetmen, kaynak, kontrol}.

    KULE NOTU: ÖLÇÜM-ONLY — kule bunu KARAR olarak UYGULAMAZ, raporda taşır."""
    verdict = cross.get("verdict")
    ov = cross.get("cast_ortusme", 0) or 0
    auth = cross.get("otoriter_yonetmen") or []
    locked = ov >= locked_min
    if verdict == "TEYİT":
        return {"yonetmen": read_director, "kaynak": "ocr-teyitli", "kontrol": False}
    if (not read_director) and locked and auth:
        return {"yonetmen": auth[0], "kaynak": "kb-fill(kimlik-kilitli)", "kontrol": False}
    if verdict == "ÇELİŞKİ" and locked and auth:
        return {"yonetmen": auth[0], "kaynak": "kb-degistir(celiski: OCR='" + str(read_director) + "')", "kontrol": False}
    return {"yonetmen": "", "kaynak": "okunamadı(kimlik-zayıf/KB-yok)", "kontrol": True}


# ───────────────── WEB/KÖPRÜ KİMLİK KATMANI (QC2 katman-b) ─────────────────
# TMDB dışına HİÇ çıkılmaz: protokol https + host izinlistesi tekil + Genel-IP zorunlu.
_TMDB_HOST = "api.themoviedb.org"


def _tmdb_url(yol, params):
    """İzinli TMDB URL'i kur: değerler urlencode ile bağlanır (asla metne
    birleştirilmez); şema/host doğrulanır, beklenen dışına düşülürse None."""
    import urllib.parse
    url = "https://" + _TMDB_HOST + yol + "?" + urllib.parse.urlencode(params)
    parca = urllib.parse.urlsplit(url)
    if parca.scheme != "https" or parca.hostname != _TMDB_HOST:
        return None
    return url


def _dis_ip_genel_mi(host) -> bool:
    """Host'un çözülen TÜM IP'leri Genel-IP mi (özel/loopback/link-local = False)."""
    import ipaddress
    import socket
    try:
        bilgiler = socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except Exception:
        return False
    for b in bilgiler:
        try:
            ip = ipaddress.ip_address(b[4][0])
        except Exception:
            return False
        if not ip.is_global:
            return False
    return True


def web_identity(title, original, year, ocr_director, summary, kb):
    """Kimlik cast-örtüşmesiyle KURULAMAZSA (cast boş/çöp) alternatif çapalar dene.

    ÇAPA-1 — YÖNETMEN-ÇAPASI (KB, ucuz): OCR bir yönetmen okuduysa → başlık adaylarını
    çek, her adayın yönetmeniyle ocr_director karşılaştır → eşleşen aday = doğru film.

    ÇAPA-2 — WEB/TMDB-ÇAPASI (yönetmen de yoksa): TMDB başlık(TR+orijinal)+yıl araması
    → güvenli tek-eşleşme (yıl ±2 + başlık-fold) → imdb_id/tmdb_id al → KB imdb_credits.

    Döndürür: {"locked": True, "method": "director"|"tmdb", "imdb_id": str,
               "tmdb_id": str|None, "director": [str], "cast": [str], "kaynak_izi": str}
    ya da {"locked": False, "method": None, "kaynak_izi": str}

    FAIL-SAFE: her exception yakalanır, locked=False döner (kule akışı ASLA bozulmaz).
    """
    try:
        import re as _re

        def _yfold(s):
            for a, b in (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),("Ğ","g"),("ğ","g"),
                         ("Ü","u"),("ü","u"),("Ö","o"),("ö","o"),("Ç","c"),("ç","c")):
                s = s.replace(a, b)
            return s.lower().strip()

        # ── ÇAPA-1: YÖNETMEN-ÇAPASI ──
        if ocr_director and ocr_director.strip():
            cands = []
            try:
                cands = kb.imdb_find(title_tr=title, original=original, year=year)
            except Exception:
                pass
            if not cands:
                try:
                    cands = kb.wd_find(title_tr=title, original=original, year=year)
                except Exception:
                    pass
            for cand in cands:
                cand_dirs = cand.get("director") or []
                if any(cc.name_match(ocr_director, d) or cc.name_close(ocr_director, d)
                       for d in cand_dirs):
                    # yıl uyumu (±3 yıl — TRT katalog yılı kayması için gevşek)
                    if year:
                        cand_yr = cand.get("year")
                        try:
                            if cand_yr and abs(int(cand_yr) - int(year)) > 3:
                                continue
                        except Exception:
                            pass
                    imdb_id = cand.get("imdb_id") or cand.get("id")
                    # cast çek
                    dir_list, cast_list = [], []
                    try:
                        if imdb_id and kb.imdb:
                            dir_list, cast_list = kb.imdb_credits(imdb_id)
                    except Exception:
                        pass
                    if not dir_list:
                        dir_list = cand_dirs
                    if not cast_list:
                        cast_list = cand.get("cast") or []
                    return {
                        "locked": True,
                        "method": "director",
                        "imdb_id": imdb_id,
                        "tmdb_id": cand.get("tmdb_movie_id"),
                        "director": dir_list,
                        "cast": cast_list,
                        "kaynak_izi": (
                            "yönetmen-çapası: OCR='" + str(ocr_director) + "' → "
                            + str(cand.get("name") or cand.get("tr"))
                            + " (" + str(cand.get("year")) + ") [" + str(imdb_id) + "]"
                        ),
                    }

        # ── ÇAPA-2: TMDB-ÇAPASI ──
        import os as _os
        tmdb_key = _os.environ.get("MITAS_TMDB") or _os.environ.get("TMDB_API_KEY")
        if tmdb_key:
            import json as _json
            import urllib.request as _ur
            import ssl as _ssl

            # KULE NOTU: üretim kalıbının devamı — TRT ağ ortamındaki TLS-kesme
            # nedeniyle doğrulama kapalı (bilinçli; scripts/ birebir).
            _ctx = _ssl.create_default_context()
            _ctx.check_hostname = False
            _ctx.verify_mode = _ssl.CERT_NONE
            _ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

            # URL-önbellek: doğruluk-nötr (yalnız HTTP gövdesi saklanır).
            try:
                import web_cache as _wcache
            except Exception:  # noqa: BLE001
                _wcache = None

            def _get(url):
                """İstek ÖNCESİ SSRF denetimi: https + izinli host + Genel-IP."""
                import urllib.parse as _up
                parca = _up.urlsplit(url)
                if parca.scheme != "https" or parca.hostname != _TMDB_HOST:
                    raise ValueError("izin disi istek hedefi")
                if not _dis_ip_genel_mi(parca.hostname):
                    raise ValueError("izin disi IP")
                if _wcache is not None:
                    _c = _wcache.get(url)
                    if _c is not None:
                        return _json.loads(_c.decode("utf-8", "replace"))
                req = _ur.Request(url, headers=_ua)
                with _ur.urlopen(req, timeout=20, context=_ctx) as r:
                    data = r.read()
                if _wcache is not None:
                    _wcache.put(url, data)
                return _json.loads(data.decode("utf-8", "replace"))

            # sıralı arama: orijinal önce, sonra TR başlık
            candidates_tmdb = []
            for kind in ("movie", "tv"):
                for q in ([original, title] if original else [title]):
                    if not q:
                        continue
                    params = {"api_key": tmdb_key, "query": q, "include_adult": "false"}
                    if year:
                        params["year" if kind == "movie" else "first_air_date_year"] = str(year)
                    url = _tmdb_url("/3/search/" + kind, params)
                    if url is None:
                        continue
                    try:
                        res = _get(url).get("results") or []
                        candidates_tmdb.extend(res)
                    except Exception:
                        pass

            # güvenli tek-eşleşme: yıl ±2 + başlık-fold uyumu
            matched_tmdb = None
            for item in candidates_tmdb:
                item_yr_raw = item.get("release_date") or item.get("first_air_date") or ""
                item_yr = None
                m = _re.match(r"(\d{4})", str(item_yr_raw))
                if m:
                    item_yr = int(m.group(1))
                if year and item_yr:
                    try:
                        if abs(int(year) - item_yr) > 2:
                            continue
                    except Exception:
                        pass
                # başlık fold uyumu
                item_title = item.get("title") or item.get("name") or ""
                if original:
                    if _yfold(item_title) == _yfold(original) or _yfold(item_title) == _yfold(title or ""):
                        matched_tmdb = item
                        break
                elif title:
                    if _yfold(item_title) == _yfold(title):
                        matched_tmdb = item
                        break

            if matched_tmdb:
                tmdb_id_found = str(matched_tmdb.get("id") or "")
                imdb_id_found = None
                dir_list, cast_list = [], []

                # TMDB → IMDb id (external_ids endpoint)
                for tur in ("movie", "tv"):
                    url = _tmdb_url("/3/" + tur + "/" + tmdb_id_found + "/external_ids",
                                    {"api_key": tmdb_key})
                    if url is None:
                        continue
                    try:
                        imdb_id_found = _get(url).get("imdb_id")
                        if imdb_id_found:
                            break
                    except Exception:
                        continue

                # KB imdb_credits (duckdb üzerinden)
                if imdb_id_found and kb.imdb:
                    try:
                        dir_list, cast_list = kb.imdb_credits(imdb_id_found)
                    except Exception:
                        pass

                # KB'den gelmediyse TMDB credits endpoint'i dene
                if not cast_list:
                    for tur in ("movie", "tv"):
                        url = _tmdb_url("/3/" + tur + "/" + tmdb_id_found + "/credits",
                                        {"api_key": tmdb_key})
                        if url is None:
                            continue
                        try:
                            cr = _get(url)
                            cast_list = [p["name"] for p in (cr.get("cast") or [])[:10]]
                            if tur == "movie":
                                dir_list = [p["name"] for p in (cr.get("crew") or [])
                                            if p.get("job") == "Director"][:3]
                            if cast_list:
                                break
                        except Exception:
                            continue

                return {
                    "locked": True,
                    "method": "tmdb",
                    "imdb_id": imdb_id_found,
                    "tmdb_id": tmdb_id_found,
                    "director": dir_list,
                    "cast": cast_list,
                    "kaynak_izi": (
                        "tmdb-çapası: '" + str(matched_tmdb.get('title') or matched_tmdb.get('name'))
                        + "' (tmdb=" + tmdb_id_found + ", imdb=" + str(imdb_id_found) + ")"
                    ),
                }

        return {"locked": False, "method": None, "kaynak_izi": "çapa bulunamadı (KB+TMDB)"}

    except Exception as _exc:  # noqa: BLE001 — FAIL-SAFE
        return {"locked": False, "method": None, "kaynak_izi": "web_identity hata: " + str(_exc)}


# ───────────────── ÖLÇÜM (çok-örnekli: garble vaka + temiz altın-set) ─────────────────
TESTS = [
    {"ad": "SİLAHŞÖRE DAVET [garble vaka]", "title": "SİLAHŞÖRE DAVET",
     "orig": "Invitation to a Gunfighter", "yil": 1964,
     "cast": ["YUL BRYNNER", "GEORCE STOAD ALRRDED", "CLIFFORD DAVID MIKE KELLIN",
              "GEORGE SEGAL", "ALFRED RYDER", "JANICE RULE", "BRAD DEXTER"]},
    {"ad": "AHLAT AĞACI [temiz altın]", "title": "AHLAT AĞACI",
     "orig": "The Wild Pear Tree", "yil": 2018,
     "cast": ["Doğu Demirkol", "Murat Cemcir", "Bennu Yıldırımlar",
              "Hazar Ergüçlü", "Serkan Keskin", "Tamer Levent"]},
    {"ad": "DİRİLİŞ ERTUĞRUL [temiz altın]", "title": "DİRİLİŞ ERTUĞRUL",
     "orig": "Dirilis: Ertugrul", "yil": 2014,
     "cast": ["Engin Altan Düzyatan", "Serdar Gökhan", "Hülya Darcan",
              "Kaan Taşaner", "Cavit Çetin Güner", "Didem Balçın"]},
    {"ad": "VANINA VANINI [garble vaka]", "title": "VANINA VANINI",
     "orig": "Vanina Vanini", "yil": 1961,
     "cast": ["SANDRA MILO", "LAURENT TERZIEFF", "LMARTINE CAROLF",
              "DIEGO FABE STENDHAL", "LEONARDO SEVERİNİ", "PAOLO STOPPA"]},
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    kb = cc.CreditKB()
    print("GRAFT-1 ÖLÇÜM — garble imza-yokluğu kapısı\n" + "=" * 64)
    for t in TESTS:
        r = kb.crosscheck("", t["cast"], title_tr=t["title"], original=t["orig"], year=t["yil"])
        otoriter = r.get("otoriter_cast") or []
        ov = r.get("cast_ortusme", 0)
        locked = ov >= 2
        print("\n=== " + t["ad"] + " ===")
        print("  verdict=" + str(r['verdict']) + " eslesen=" + str(r.get('eslesen_film'))
              + " cast_ortusme=" + str(ov) + " kimlik_KİLİT=" + str(locked))
        print("  KB otoriter_cast: " + str(otoriter))
        # RAFİNE: kimlik-önce temiz cast (limit 14 — gerçek alt-sıra oyuncuyu da imzaya al)
        ref = identity_first_cast(t["cast"], otoriter, max_out=14)
        print("  HAM OCR cast:  " + str(t["cast"]))
        print("  TEMİZ cast:    " + str(ref['temiz_cast']))
        if ref["dususler"]:
            print("  DÜŞENLER (imzasız→garble/şüpheli): " + str(ref['dususler']))

    # ── GRAFT-4: yönetmen KB-fill ölçümü ──
    print("\n\nGRAFT-4 ÖLÇÜM — yönetmen KB-fill (kimlik-önce)\n" + "=" * 64)
    DTESTS = [
        {"ad": "DERİNLİKLERDE [OCR-boş→fill bekle]", "title": "DERİNLİKLERDE", "orig": "Sub Down", "yil": 1997,
         "yon": "", "cast": ["Gabrielle Anwar", "Stephen Baldwin", "Tom Conti", "Chris Mulkey", "Tony Plana"]},
        {"ad": "GECEYARISINA DOĞRU [Scorsese yanlış→değiştir bekle]", "title": "GECEYARISINA DOĞRU",
         "orig": "Round Midnight", "yil": 1986, "yon": "Martin Scorsese",
         "cast": ["Dexter Gordon", "François Cluzet", "Lonette McKee", "Herbie Hancock"]},
        {"ad": "AHLAT AĞACI [teyit→koru bekle]", "title": "AHLAT AĞACI", "orig": "The Wild Pear Tree", "yil": 2018,
         "yon": "Nuri Bilge Ceylan", "cast": ["Doğu Demirkol", "Murat Cemcir", "Bennu Yıldırımlar", "Hazar Ergüçlü"]},
    ]
    for t in DTESTS:
        cross = kb.crosscheck(t["yon"], t["cast"], title_tr=t["title"], original=t["orig"], year=t["yil"])
        d = director_decision(t["yon"], cross)
        print("\n=== " + t["ad"] + " ===")
        print("  OCR-yön='" + t["yon"] + "'  verdict=" + str(cross.get('verdict'))
              + "  cast_ortusme=" + str(cross.get('cast_ortusme'))
              + "  KB-yön=" + str(cross.get('otoriter_yonetmen')))
        print("  -> KARAR: yönetmen='" + str(d['yonetmen']) + "'  kaynak=" + d['kaynak']
              + "  kontrol=" + str(d['kontrol']))
    kb.close()


if __name__ == "__main__":
    main()
