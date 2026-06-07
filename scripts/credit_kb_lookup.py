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

def tur_to_tr(genres_csv, k=2):
    if not genres_csv:
        return None
    out = []
    for g in str(genres_csv).split(","):
        tr = _TUR_TR.get(g.strip().lower())
        if tr and tr not in out:
            out.append(tr)
    return " / ".join(out[:k]) if out else None

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
    if imdb_id and kb.imdb:
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
    # Wikidata → IMDb geri besleme: imdb_find boşsa wd_imdb_id ile doğrudan sorgula
    if not tur_imdb and wd_imdb_id and kb.imdb:
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
    out["tur"] = tur_to_tr(tur_imdb)
    out["imdb_id"] = imdb_id

    # 3) afiş (istenirse)
    # AFİŞ KAPISI (KESİN İLKE 4 + Çağatay 2026-06-07: "afişi yönetmen+oyuncu TEYİT aldıktan SONRA,
    # doğru olduğuna EMİN olup çekeceğiz; yanlış afiş YOK"): id-tabanlı afiş indirme YALNIZ kimlik
    # GÜÇLÜ doğrulanmışsa verilir — verdict TEYİT (OCR yönetmeni KB ile eşleşti) VEYA ≥3 SIKI
    # cast örtüşmesi. (Eşik 2→3 yükseltildi: afiş en görünür yanlış-veri; "gerekli tedbir".)
    # Aksi halde id'ler VERİLMEZ → poster_fetch kadro-teyitli _search'e düşer; tutmazsa afiş YOK.
    # KÖK SEBEP: zayıf/yanlış kimlikte (title-only çakışma) yanlış filmin id'siyle yanlış afiş iniyordu.
    kimlik_dogrulandi = (r.get("verdict") == "TEYİT") or ((r.get("cast_ortusme") or 0) >= 3)
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
