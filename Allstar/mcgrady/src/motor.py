# -*- coding: utf-8 -*-
"""motor.py — McGrady kule orkestrasyonu: künye adayı → kimlik/öneri/garble/afiş raporu.

Akış (plan onaylı, 2026-08-18):
  1. KB crosscheck (cast örtüşmesi) → kimlik kilidi
  2. kilitlenemediyse: profile=film → ÇAPA-1 yönetmen-çapası (KB) → ÇAPA-2 TMDB
     (internet kule çıkışından); profile=dizi → web katmanı ATLANIR (dizide
     internet çapası gereksiz kararı — teknik ekip internette yok, cast TRT
     kaynağında)
  3. kanonikleştirme ÖNERİLERİ (OCR-otorite: veri EZMEZ, tüketici uygular)
  4. garble raporu (imza-yokluğu — SİLME YOK)
  5. yönetmen kararı (deferans: doldurma yok, ÖNERİ var)
  6. afiş: poster_fetch + poster_ok kapısı (>5KB + portre w<h)

Her katman kendi try/except'i içinde — tek katman hatası kanıta yazılır, koşu
ARIZA'ya devrilmez. ARIZA yalnız gerçek koşu arızasında (DB, motor eksik).
"""
from __future__ import annotations

import time


class MotorArizasi(Exception):
    """ARIZA'ya çevrilmek üzere yukarı atılır — koşu devam edemez."""

    def __init__(self, sinif: str, mesaj: str) -> None:
        super().__init__(mesaj)
        self.sinif, self.mesaj = sinif, mesaj


def _poster_ok(yol) -> dict:
    """AFİŞ KAPISI (QC2-sistemik): geçerli afiş = dosya var + >5KB + PORTRE (w<h).
    Yatay frame-grab/backdrop RED ('afiş yerine foto' tuzağı). PIL yoksa
    boyut-kontrolüne düşer (fail-safe)."""
    import os
    try:
        if not (yol and os.path.exists(yol) and os.path.getsize(yol) > 5000):
            return {"yol": None, "gecerli": False, "neden": "dosya yok ya da <5KB"}
        try:
            from PIL import Image
            with Image.open(yol) as im:
                w, h = im.size
        except Exception:
            return {"yol": str(yol), "gecerli": True, "neden": "boyut kontrolu (PIL yok)"}
        if w >= h:
            return {"yol": None, "gecerli": False,
                    "neden": "yatay/kare görsel afiş değil (w=" + str(w) + " h=" + str(h) + ")"}
        return {"yol": str(yol), "gecerli": True, "neden": "portre"}
    except Exception as e:
        return {"yol": None, "gecerli": False, "neden": "poster_ok hatası: " + str(e)}


def calistir(paket: dict, config: dict | None = None, afis_dizini=None) -> dict:
    """Bir girdi paketi → sonuç sözlüğü (sozlesme.Cikti alanlarının kaynağı).

    Döndürür: {durum, kimlik, oneriler, yonetmen, web_oneri, garble, afis,
              karar_onerileri, kanit}
    MotorArizasi: DB bağlanamadı / motor eksik (koşu arızası).
    """
    config = config or {}
    kanit = {"adimlar": {}}
    baslik = paket.get("baslik") or {}
    title = baslik.get("tr")
    original = baslik.get("orijinal")
    year = baslik.get("yil")
    yon_list = [y for y in (paket.get("yonetmen") or []) if y and y.strip()]
    cast = [c for c in (paket.get("cast") or []) if c and c.strip()]
    yap = [p for p in (paket.get("yapimci") or []) if p and p.strip()]
    ocr_yonetmen = yon_list[0] if yon_list else ""

    # ── KB bağlantısı ────────────────────────────────────────────────────────
    try:
        import credit_crosscheck as cc
    except ImportError as e:
        raise MotorArizasi("MOTOR_EKSIK",
                           "credit_crosscheck modulu yok (Mimosa blogu — DURUM.md bkz): " + str(e))
    try:
        import credit_qc_gates as gates
    except ImportError as e:
        raise MotorArizasi("MOTOR_EKSIK",
                           "credit_qc_gates modulu yok (Mimosa blogu — DURUM.md bkz): " + str(e))

    t0 = time.time()
    kb = cc.CreditKB()
    try:
        if not kb.db_hazir():
            raise MotorArizasi("DB", "Wikidata/IMDb duckdb baglanamadi (zemin yollari config.yaml)")

        # ── 1. KB crosscheck → kimlik kilidi ────────────────────────────────
        try:
            cross = kb.crosscheck(ocr_yonetmen, cast, title_tr=title,
                                  original=original, year=year)
        except Exception as e:
            raise MotorArizasi("DB", "crosscheck hatasi: " + type(e).__name__ + ": " + str(e))
        kanit["adimlar"]["crosscheck"] = {
            "verdict": cross.get("verdict"), "kaynak": cross.get("kaynak"),
            "eslesen_film": cross.get("eslesen_film"), "eslesen_yil": cross.get("eslesen_yil"),
            "cast_ortusme": cross.get("cast_ortusme"), "neden": cross.get("neden"),
        }
        otoriter_cast = cross.get("otoriter_cast") or []
        auth_yon = cross.get("otoriter_yonetmen") or []
        cast_ov = cross.get("cast_ortusme", 0) or 0
        kimlik_dogru = (cross.get("verdict") == "TEYİT") or (cast_ov >= 2)

        kimlik = None
        web_oneri = None
        web = {"locked": False, "method": None, "kaynak_izi": ""}

        if kimlik_dogru:
            kimlik = {
                "method": "cast-ortusme",
                "imdb_id": cross.get("matched_imdb_id"),
                "tmdb_id": cross.get("wikidata_tmdb_id"),
                "kaynak_izi": ("KB crosscheck: " + str(cross.get("eslesen_film"))
                               + " (" + str(cross.get("eslesen_yil")) + ") ov="
                               + str(cast_ov)),
                "cast_ortusme": cast_ov,
                "versiyon_teyitli": True,
            }

        # ── 2. çapalar (yalnız kilitlenemediyse; dizi'de web ATLANIR) ───────
        if not kimlik_dogru:
            if paket.get("profile") == "dizi":
                kanit["adimlar"]["web"] = {"method": None,
                                           "neden": "dizi profili — web katmanı bilerek atlandı"}
            elif config.get("web", True):
                try:
                    web = gates.web_identity(title, original, year,
                                             ocr_director=(ocr_yonetmen or None),
                                             summary=None, kb=kb)
                except Exception as e:
                    web = {"locked": False, "method": None,
                           "kaynak_izi": "web_identity hata: " + str(e)}
                if web.get("locked"):
                    kimlik = {
                        "method": web.get("method"),
                        "imdb_id": web.get("imdb_id"),
                        "tmdb_id": web.get("tmdb_id"),
                        "kaynak_izi": web.get("kaynak_izi"),
                        "cast_ortusme": 0,
                        "versiyon_teyitli": web.get("method") == "director",
                    }
                    # web cast referansı: ÖNERİ olarak taşınır, ASLA ezmez (OCR-otorite).
                    web_oneri = {
                        "method": web.get("method"),
                        "kaynak_izi": web.get("kaynak_izi"),
                        "imdb_id": web.get("imdb_id"), "tmdb_id": web.get("tmdb_id"),
                        "web_yonetmen": (web.get("director") or [])[:3],
                        "cast_oneri": (web.get("cast") or [])[:8],
                    }
                else:
                    web_oneri = {"method": None, "kaynak_izi": web.get("kaynak_izi"),
                                 "neden": "çapa kilitlenemedi → KONTROL (yanlış>boş)"}
                kanit["adimlar"]["web"] = {"method": web.get("method"),
                                           "kaynak_izi": web.get("kaynak_izi")}
            else:
                kanit["adimlar"]["web"] = {"method": None, "neden": "config: web kapalı"}

        kilitli = kimlik is not None
        durum = "DOGRULANDI" if kilitli else "KILITLENEMEDI"

        # ── 3. kanonikleştirme ÖNERİLERİ (OCR-otorite: EZME YOK) ────────────
        oneriler = []
        try:
            for nm in cast:
                exact = next((a for a in otoriter_cast if cc.name_match(nm, a)), None)
                if exact:
                    continue          # sıkı teyit — yazım korunur, öneri gerekmez
                close = next((a for a in otoriter_cast if cc.name_close(nm, a)), None)
                if close:
                    oneriler.append({"alan": "cast", "ocr": nm, "kanonik": close,
                                     "kaynak": "kb-yazim-duzelt"})
                    continue
                if config.get("fuzzy_dbqc", False):
                    pencere = next((a for a in otoriter_cast
                                    if cc.name_close_window(nm, a, 0.80)), None)
                    if pencere:
                        oneriler.append({"alan": "cast", "ocr": nm, "kanonik": pencere,
                                         "kaynak": "kb-gomulu-pencere(0.80)"})
            # yapımcı önerisi YOK: KB crosscheck otoriter yapımcı listesi döndürmez
            # (pipeline'daki yapımcı fill'i ayrı kapıydı ve kule kapsamı dışında).
        except Exception as e:
            kanit["adimlar"]["kanonik_hata"] = str(e)

        # ── 4. garble raporu (SİLME YOK) ────────────────────────────────────
        garble = []
        try:
            garble = gates.garble_no_signature_gate(cast, otoriter_cast,
                                                    identity_locked=kilitli)
        except Exception as e:
            kanit["adimlar"]["garble_hata"] = str(e)

        # ── 5. yönetmen kararı (deferans: ÖNERİ) ────────────────────────────
        if ocr_yonetmen and cross.get("verdict") == "TEYİT":
            yonetmen = {"ocr": ocr_yonetmen, "karar": ocr_yonetmen,
                        "kaynak": "ocr-teyitli", "kontrol_onerisi": False}
        elif ocr_yonetmen and cross.get("verdict") == "ÇELİŞKİ" and kilitli and auth_yon:
            yonetmen = {"ocr": ocr_yonetmen, "karar": auth_yon[0],
                        "kaynak": "kb-degistir-onerisi(celiski)", "kontrol_onerisi": True}
        elif (not ocr_yonetmen) and kilitli and auth_yon:
            yonetmen = {"ocr": None, "karar": auth_yon[0],
                        "kaynak": "kb-fill-onerisi(kimlik-kilitli)", "kontrol_onerisi": True}
        elif kilitli and web_oneri and web_oneri.get("web_yonetmen"):
            yonetmen = {"ocr": ocr_yonetmen or None,
                        "karar": web_oneri["web_yonetmen"][0],
                        "kaynak": "web-onerisi(" + str(web_oneri.get("method")) + ")",
                        "kontrol_onerisi": True}
        else:
            yonetmen = {"ocr": ocr_yonetmen or None, "karar": None,
                        "kaynak": "okunamadı(kimlik-zayıf/KB-yok)", "kontrol_onerisi": True}

        # ── 6. afiş (kilitli film + poster_fetch varsa) ─────────────────────
        afis = {"yol": None, "gecerli": False, "neden": "kosul yok (kilit yok ya da afis kapalı)"}
        if kilitli and config.get("afis", True) and afis_dizini is not None:
            try:
                import poster_fetch
                afis_dizini.mkdir(parents=True, exist_ok=True)
                hedef = afis_dizini / "afis.jpg"
                yol = poster_fetch.fetch_poster(
                    title or original, hedef,
                    original=original, year=year,
                    cast=(otoriter_cast or (web.get("cast") or []))[:8],
                    tmdb_id=kimlik.get("tmdb_id"), imdb_id=kimlik.get("imdb_id"))
                if yol:
                    afis = _poster_ok(yol)
                else:
                    afis = {"yol": None, "gecerli": False, "neden": "poster_fetch bulamadi"}
            except ImportError:
                afis = {"yol": None, "gecerli": False,
                        "neden": "poster_fetch modulu yok (Mimosa blogu — DURUM.md bkz)"}
            except Exception as e:
                afis = {"yol": None, "gecerli": False, "neden": "afis hatasi: " + str(e)}

        # ── 7. karar önerileri (tüketici uygular) ───────────────────────────
        karar_onerileri = []
        if durum == "KILITLENEMEDI":
            karar_onerileri.append("kimlik kurulamadı (KB + çapalar kilitlenemedi) → KONTROL")
        if kimlik and kimlik.get("method") == "tmdb":
            karar_onerileri.append("versiyon cast-teyitsiz (web title+year kilidi — insan onayı)")
        if any(g.get("suspect") for g in garble):
            adet = sum(1 for g in garble if g.get("suspect"))
            karar_onerileri.append("cast garble şüphesi x" + str(adet)
                                   + " (OCR-otorite — KB-imzasız isim, insan teyidi)")
        if yonetmen.get("kontrol_onerisi"):
            karar_onerileri.append("yönetmen kararı insan teyidi bekliyor ("
                                   + str(yonetmen.get("kaynak")) + ")")

        kanit["adimlar"]["sure_sn"] = round(time.time() - t0, 1)
        return {
            "durum": durum, "kimlik": kimlik, "oneriler": oneriler,
            "yonetmen": yonetmen, "web_oneri": web_oneri, "garble": garble,
            "afis": afis, "karar_onerileri": karar_onerileri, "kanit": kanit,
        }
    finally:
        kb.close()
