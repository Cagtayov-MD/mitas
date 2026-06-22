#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
credit_kb_lookup.py — TEK FİLM: cross-check + yapımcı + TÜR + afiş (venvs/ocr python).

Video-okumadan gelen yönetmen/cast'i Wikidata+IMDb ile DOĞRULA; karelerde okunamayan
yapımcı'yı ve TÜR'ü otoriter kaynaktan çek; afişi indir. ASLA düzeltmez, raporlar+doldurur.

Çıktı: tek-satır JSON
  {verdict, eslesen_film, eslesen_yil, cast_ortusme, otoriter_yonetmen, otoriter_cast,
   yapimci[], tur_imdb, tur(TR, ilk 2), imdb_id, afis}

Kullanım (venvs/ocr python — duckdb burada):
  venvs/ocr/Scripts/python.exe scripts/credit_kb_lookup.py \
     --baslik "YABANCI MUHABİR" --orijinal "Foreign Correspondent" --yil 1940 \
     --yonetmen "Alfred Hitchcock" \
     --cast "Joel McCrea,Laraine Day,Herbert Marshall,George Sanders" \
     --afis-out "E:\\MITAS\\_102_afis_cache\\1940-0034-1-0000-00-1.jpg"
"""
import argparse, importlib.util, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credit_crosscheck as cc

# IMDb tür -> Türkçe (v4 TÜR için; ilk 2 alınır)
_TUR_TR = {
    "action": "Aksiyon", "adventure": "Macera", "animation": "Animasyon", "biography": "Biyografi",
    "comedy": "Komedi", "crime": "Suç", "documentary": "Belgesel", "drama": "Dram", "family": "Aile",
    "fantasy": "Fantastik", "film-noir": "Kara Film", "history": "Tarihi", "horror": "Korku",
    "music": "Müzik", "musical": "Müzikal", "mystery": "Gizem", "romance": "Romantik",
    "sci-fi": "Bilimkurgu", "science fiction": "Bilimkurgu", "sport": "Spor", "thriller": "Gerilim",
    "war": "Savaş", "western": "Western",
}

# Wikidata genre QID -> Türkçe (works_master.genre pipe-ayrık QID; yalnız YÜKSEK-GÜVEN eşlemeler).
# Doğrulama (2026-06-15): mitas.duckdb works_master genre dağılımı (894k iş) + bilinen film örnekleri
# (Dark Knight/Forrest Gump/Alien/Matrix/Inception/Saving Private Ryan + solo-genre filmleri) ile
# QID anlamı teyit edildi. qid_labels'ta genre-konsept QID'leri YOK → statik map zorunlu. Belirsiz/
# alt-tür (silent-film Q226730, comedy-drama Q859369, teen Q1146335, erotik Q185529/Q599558 vb.)
# KASTEN dışarıda — yanlış-tür yerine "—" (uydurma yok). IMDb-tür biçimiyle uyum: Title-Case, " / " ilk 2.
_WD_TUR_TR = {
    "Q130232": "Dram",            # drama film
    "Q188473": "Aksiyon",         # action film
    "Q157443": "Komedi",          # comedy film
    "Q471839": "Bilimkurgu",      # science fiction film
    "Q2484376": "Gerilim",        # thriller film
    "Q959790": "Suç",             # crime film
    "Q200092": "Korku",           # horror film
    "Q853630": "Korku",           # horror film (varyant)
    "Q1054574": "Romantik",       # romance film
    "Q860626": "Romantik Komedi", # romantic comedy
    "Q319221": "Macera",          # adventure film
    "Q369747": "Savaş",           # war film
    "Q93204": "Belgesel",         # documentary film
    "Q842256": "Müzikal",         # musical film
    "Q645928": "Tarihi",          # historical film
    "Q157394": "Fantastik",       # fantasy film
    "Q172980": "Western",         # western film
    "Q1200678": "Gizem",          # mystery film
    "Q185867": "Kara Film",       # film noir
    "Q202866": "Animasyon",       # animated film
    "Q2143665": "Aile",           # children's film
    "Q1361932": "Aile",           # children's/family film
}

def tur_to_tr(genres_csv, k=2):
    if not genres_csv:
        return None
    out = []
    for g in str(genres_csv).split(","):
        tr = _TUR_TR.get(g.strip().lower())
        if tr and tr not in out:
            out.append(tr)
    return " / ".join(out[:k]) if out else None

def wd_genre_to_tr(genre_pipe, k=2):
    """works_master.genre (pipe-ayrık Wikidata QID) -> Türkçe TÜR (ilk k bilinen, dağılım sırasını korur).
    Bilinmeyen QID atlanır; hiç bilinen yoksa None (uydurma yok)."""
    if not genre_pipe:
        return None
    out = []
    for q in str(genre_pipe).split("|"):
        tr = _WD_TUR_TR.get(q.strip())
        if tr and tr not in out:
            out.append(tr)
    return " / ".join(out[:k]) if out else None

def _wd_genre_lookup(wd, *, imdb_id=None, title_tr=None, original=None, year=None):
    """Wikidata works_master'dan TÜR (yerel, web yok). Öncelik: imdb_id (kesin eşleşme) → başlık+yıl.
    Sadece p31=Q11424 (film) satırları. Hata/DB-yok → None (graceful, eski davranış)."""
    if wd is None:
        return None
    # KADEME A: doğrulanmış imdb_id ile birebir (en güvenilir)
    if imdb_id:
        try:
            r = wd.execute(
                "SELECT genre FROM works_master WHERE imdb_id=? AND genre IS NOT NULL AND genre<>'' LIMIT 1",
                [imdb_id]).fetchone()
            tr = wd_genre_to_tr(r[0]) if r else None
            if tr:
                return tr
        except Exception:
            pass
    # KADEME B: başlık (label_tr, Türkçe-fold) + yıl yakınlığı — imdb_id yoksa/türsüzse
    try:
        import credit_crosscheck as _ccx
        sf_tr = _ccx._sqlfold("label_tr")
        sf_en = _ccx._sqlfold("label_en")
        sf_nm = _ccx._sqlfold("name")
        ft = _ccx._tfold(title_tr) if title_tr else None
        fo = _ccx._tfold(original) if original else None
        clauses, params = [], []
        if ft:
            clauses.append(f"{sf_tr}=?"); params.append(ft)
        if fo:
            clauses += [f"{sf_en}=?", f"{sf_nm}=?"]; params += [fo, fo]
        if not clauses:
            return None
        rows = wd.execute(
            "SELECT genre, publication_year FROM works_master "
            "WHERE (" + " OR ".join(clauses) + ") AND p31='Q11424' "
            "AND genre IS NOT NULL AND genre<>'' LIMIT 40", params).fetchall()
        if not rows:
            return None
        # yıl verildiyse en yakın yıllı satırı seç (yoksa ilk türlü satır)
        best = None
        if year:
            try:
                yi = int(year)
                best = min((r for r in rows if r[1] and str(r[1]).isdigit()),
                           key=lambda r: abs(int(r[1]) - yi), default=None)
                if best and abs(int(best[1]) - yi) > 3:   # 3 yıldan uzaksa güvenme → ilk satıra düş
                    best = None
            except Exception:
                best = None
        return wd_genre_to_tr((best or rows[0])[0])
    except Exception:
        return None

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Tek film: cross-check + yapımcı + TÜR + afiş")
    ap.add_argument("--baslik", required=True, help="Türkçe başlık")
    ap.add_argument("--orijinal", default=None)
    ap.add_argument("--yil", default=None)
    ap.add_argument("--yonetmen", default="", help="okunan yönetmen")
    ap.add_argument("--cast", default="", help="okunan cast, virgülle")
    ap.add_argument("--afis-out", default=None, help="afiş indirilecek dosya yolu (verilirse indirir)")
    a = ap.parse_args()

    rd = a.yonetmen.strip()
    rc = [x.strip() for x in a.cast.split(",") if x.strip()]
    kb = cc.CreditKB()

    # 1) yönetmen/cast doğrula
    r = kb.crosscheck(rd, rc, title_tr=a.baslik, original=a.orijinal, year=a.yil)
    out = {
        "verdict": r.get("verdict"), "eslesen_film": r.get("eslesen_film"),
        "eslesen_yil": r.get("eslesen_yil"), "cast_ortusme": r.get("cast_ortusme"),
        "otoriter_yonetmen": r.get("otoriter_yonetmen"), "otoriter_cast": r.get("otoriter_cast"),
        "okunan_yonetmen": rd,
    }

    # 2) yapımcı + TÜR (IMDb best-match)
    yapimci, tur_imdb, imdb_id = [], None, None
    # Wikidata crosscheck sonucundan imdb_id ve tmdb_id al (IMDb bulamazsa yedek)
    wd_imdb_id = r.get("wikidata_imdb_id")
    wd_tmdb_id = r.get("wikidata_tmdb_id")
    # KÖK SEBEP koruması: imdb_find başlık-tabanlıdır ve title-only YANLIŞ filmi (ör. Filipinli
    # "Red Flag" tt32033162) cands[0] olarak döndürebilir. crosscheck'in cast ile DOĞRULADIĞI film
    # (matched_imdb_id) BİRİNCİL otoritedir. imdb_find'in best'i YALNIZ kimlikle TUTARLIYSA (okunan
    # yönetmeni eşliyor VEYA zaten matched_imdb_id'ye eşit) kullanılır; aksi halde matched_imdb_id.
    matched_id = r.get("matched_imdb_id")
    cands = kb.imdb_find(title_tr=a.baslik, original=a.orijinal, year=a.yil)
    best = None
    for c in cands:                              # 1) okunan yönetmen + yıl ile TUTARLI aday
        if c.get("director") and rd and any(cc.name_match(rd, x) for x in c["director"]):
            if (not a.yil) or (c.get("year") and abs(int(c["year"]) - int(a.yil)) <= 1):
                best = c
                break
    if not best and matched_id:                  # 2) crosscheck'in DOĞRULADIĞI film (cast-teyitli) öncelik
        best = next((c for c in cands if c.get("id") == matched_id), None) \
               or {"id": matched_id, "director": r.get("otoriter_yonetmen") or []}
    # NOT: title-only cands[0] fallback'i KASTEN KALDIRILDI — kimlik doğrulanmadan (matched_id yok,
    # okunan yönetmen de tutmuyor) title-only YANLIŞ film TÜR/yapımcı/afiş'e sızıyordu (KÖK SEBEP).
    # Doğrulanmamışsa imdb_id boş kalır → TÜR/yapımcı boş, afiş gate zaten engeller.
    if best:
        imdb_id = best.get("id")
    if not imdb_id:                              # KADEME 1: hiçbiri tutmadıysa crosscheck'in (cast) bulduğu film
        imdb_id = matched_id
    # KİMLİK KAPISI (2026-06-22, BEKARLIK→Norman Lear): yapımcı + TÜR yalnız kimlik GÜÇLÜ kilitliyken KB'den
    # doldurulur ('AFİŞ KAPISI' 3) ile birebir aynı predikat). Boş-OCR'da crosscheck title-only YANLIŞ filmi
    # matched_imdb_id ile döndürür (read_cast=[] → cast-kapısı atlanır) → yanlış yapımcı/TÜR sızıyordu. imdb_id
    # KORUNUR (afiş kapısı onu zaten kimlik_dogrulandi ile süzer); yalnız yapımcı/TÜR EKSTRAKSİYONU kapılanır.
    # "yanlış > boş": kimlik yoksa yapımcı/TÜR boş (TÜR için XML a.tur fallback'i tek_film_kunye'de yine var).
    kimlik_dogrulandi = (r.get("verdict") == "TEYİT") or ((r.get("cast_ortusme") or 0) >= 3)
    _kb_fill_ok = kimlik_dogrulandi or os.environ.get(
        "MITAS_PRODUCER_IDENTITY_GATE", "1").strip().lower() in ("0", "false", "off", "no")
    if imdb_id and kb.imdb and _kb_fill_ok:
        try:
            rows = kb.imdb.execute(
                "SELECT nconst FROM principals WHERE tconst=? AND category='producer' ORDER BY ordering LIMIT 6",
                [imdb_id]).fetchall()
            yapimci = kb._imdb_names([x[0] for x in rows])
        except Exception:
            pass
        try:
            g = kb.imdb.execute("SELECT genres FROM titles WHERE tconst=?", [imdb_id]).fetchone()
            tur_imdb = g[0] if g else None
        except Exception:
            pass
    # Wikidata → IMDb geri besleme: imdb_find boşsa wd_imdb_id ile doğrudan sorgula (kimlik kapılı)
    if _kb_fill_ok and not tur_imdb and wd_imdb_id and kb.imdb:
        try:
            g = kb.imdb.execute("SELECT genres FROM titles WHERE tconst=?", [wd_imdb_id]).fetchone()
            if g and g[0]:
                tur_imdb = g[0]
                if not imdb_id:
                    imdb_id = wd_imdb_id
        except Exception:
            pass
    # tmdb_id: önce IMDb'den gelen best'ten, yoksa Wikidata'dan
    tmdb_id = wd_tmdb_id
    out["yapimci"] = yapimci
    out["tur_imdb"] = tur_imdb
    tur_tr = tur_to_tr(tur_imdb)
    tur_kaynak = "imdb" if tur_tr else None
    # KADEME 3 — Wikidata genre fallback (YEREL, web yok): IMDb türü boşsa works_master.genre'den
    # (QID→TR) doldur. ADDITIVE: yalnız IMDb-tür YOKKEN devreye girer; IMDb tutarsa DOKUNMAZ.
    # imdb_id (doğrulanmış) birincil anahtar, yoksa başlık+yıl. Çökme yok (graceful → tur_tr=None).
    # Kimlik kapısı (yapımcı ile aynı): kimlik kilitlenmemişse başlık+yıl yanlış-film TÜR'ü sızdırabilir.
    if _kb_fill_ok and not tur_tr:
        try:
            wd_tur = _wd_genre_lookup(kb.wd, imdb_id=(imdb_id or wd_imdb_id),
                                      title_tr=a.baslik, original=a.orijinal, year=a.yil)
            if wd_tur:
                tur_tr = wd_tur
                tur_kaynak = "wikidata"
        except Exception as e:
            sys.stderr.write(f"[uyari] wikidata tur fallback hatasi: {e}\n")
    out["tur"] = tur_tr
    out["tur_kaynak"] = tur_kaynak
    out["imdb_id"] = imdb_id

    # 3) afiş (istenirse)
    # AFİŞ KAPISI (KESİN İLKE 4 + Çağatay 2026-06-07: "afişi yönetmen+oyuncu TEYİT aldıktan SONRA,
    # doğru olduğuna EMİN olup çekeceğiz; yanlış afiş YOK"): id-tabanlı afiş indirme YALNIZ kimlik
    # GÜÇLÜ doğrulanmışsa verilir — verdict TEYİT (OCR yönetmeni KB ile eşleşti) VEYA ≥3 SIKI
    # cast örtüşmesi. (Eşik 2→3 yükseltildi: afiş en görünür yanlış-veri; "gerekli tedbir".)
    # Aksi halde id'ler VERİLMEZ → poster_fetch kadro-teyitli _search'e düşer; tutmazsa afiş YOK.
    # KÖK SEBEP: zayıf/yanlış kimlikte (title-only çakışma) yanlış filmin id'siyle yanlış afiş iniyordu.
    # (kimlik_dogrulandi yukarıda yapımcı/TÜR kapısıyla birlikte hesaplandı — aynı predikat.)
    afis_imdb_id = imdb_id if kimlik_dogrulandi else None
    afis_tmdb_id = tmdb_id if kimlik_dogrulandi else None
    out["afis"] = None
    if a.afis_out:
        try:
            spec = importlib.util.spec_from_file_location("pf", r"E:\MITAS\OCR-worktree\pdf-mitas\poster_fetch.py")
            pf = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(pf)
            os.makedirs(os.path.dirname(os.path.abspath(a.afis_out)), exist_ok=True)
            # POSTER-CACHE ZEHİRLENMESİ koruması: afis_out SABİT bir cache yolu (trt-anahtarlı).
            # Önceki YANLIŞ koşudan kalan bayat afiş orada duruyorsa, bu koşu afiş ÜRETMESE bile
            # (kimlik doğrulanmadı → id verilmedi → fetch None döner) eski dosya "var + >5KB"
            # kontrolünü geçip TESLİME sızardı (KÖK SEBEP: Red Flag afişi cache'e yazılmıştı).
            # Çözüm: (1) fetch'ten ÖNCE bayat dosyayı sil → yalnız bu koşu doldurabilsin;
            #        (2) out["afis"]'i fetch_poster'ın GERÇEK dönüşüne bağla (dosya-var'a değil).
            try:
                if os.path.exists(a.afis_out):
                    os.remove(a.afis_out)
            except OSError:
                pass
            res = pf.fetch_poster(a.baslik, a.afis_out, original=a.orijinal, year=a.yil,
                                  cast=rc, crew=None, tmdb_id=afis_tmdb_id, imdb_id=afis_imdb_id)
            if res and os.path.exists(a.afis_out) and os.path.getsize(a.afis_out) > 5000:
                out["afis"] = a.afis_out
        except Exception as e:
            sys.stderr.write(f"[uyari] afis indirilemedi: {e}\n")

    kb.close()
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
