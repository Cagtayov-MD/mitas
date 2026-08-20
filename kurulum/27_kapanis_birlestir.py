#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KAPANIŞ BİRLEŞTİR: okuma.json'lar → kunye.json + QC tablosu.

- Kardeş parçaları katalogda (YYYY-NNNN) gruplar; künye grubun birleşimidir
  (tüm parçalar aynı kunye.json'u alır — her mp4 kaydına bir PDF).
- Çelişki (giriş≠kapanış / parçalar arası) → alan BOŞ + bayrak; hakem Fable.
- `_fable_patch.json` (HASAT kökünde) uygulanır: {katalog: {ozet, tur, orijinal_ad,
  yonetmen, yapimci, oyuncular, not}} — Fable'ın QC/bilgi katmanı. Patch alanları
  okumayı EZER (yazım düzeltmesi/hakem kararı).
- `_tablo.tsv` üretir: Fable'ın toplu tarama gözü.

Kullanım: venvs/ocr/bin/python kurulum/27_kapanis_birlestir.py [--films X,Y]
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path


def fuzzy_duzelt(okunan: list[str], gercek: list[str]) -> list[str]:
    """Okunan adı, %75+ benzer GERÇEK adla değiştir (yazım düzeltme — AVILDSON→AVILDSEN).
    Eşleşmeyen okunanlar aynen kalır; gerçek listeden EKLEME yapılmaz."""
    if not gercek:
        return okunan
    out = []
    for ad in okunan:
        en_iyi, oran = ad, 0.75
        for g in gercek:
            r = difflib.SequenceMatcher(None, ad.upper(), g.upper()).ratio()
            if r >= oran and r < 1.0:
                en_iyi, oran = g.upper(), r
        out.append(en_iyi)
    return out

HASAT = Path("/opt/mitas/filmtest/kapanis_hasat")
PATCH = HASAT / "_fable_patch.json"
TABLO = HASAT / "_tablo.tsv"


def guvenli(j: Path) -> dict:
    try:
        return json.loads(j.read_text(encoding="utf-8"))
    except Exception:
        return {}


COP = {"alan_yok", "yok", "-", "", "null", "none", "n/a", "okunamadi"}

# LATİN ZORUNLULUĞU (Çağatay 2026-07-24): PDF'e yalnız Latin alfabesi girer.
_KIRIL = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
          "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
          "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
          "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
          "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
          "ґ": "g", "є": "ye", "і": "i", "ї": "yi", "ђ": "dj", "ј": "j", "љ": "lj",
          "њ": "nj", "ћ": "c", "џ": "dz"}


def latinlestir(s: str | None) -> str | None:
    """Kiril→Latin translitere; CJK/Latin-dışı bloklar atılır; Ə→E; parantez artığı
    temizlenir. Türkçe karakterler ve Batı aksanları korunur."""
    if not s:
        return s
    out = []
    for ch in s:
        o = ord(ch)
        if 0x0400 <= o <= 0x04FF:                       # Kiril
            t = _KIRIL.get(ch.lower(), "")
            out.append(t.upper() if ch.isupper() and t else t)
        elif ch in "Əə":
            out.append("E" if ch == "Ə" else "e")
        elif o < 0x80 or ch in "ÇĞİÖŞÜçğıöşü":          # ASCII + Türkçe harfler aynen
            out.append(ch)
        elif o < 0x0250:                                 # Batı aksanı → ASCII (É→E, PRÉJEAN→PREJEAN)
            import unicodedata
            out.append("".join(c for c in unicodedata.normalize("NFKD", ch)
                               if ord(c) < 0x80))
        # diğerleri (CJK, Arap, vb.) → atılır
    r = re.sub(r"\(\s*\)", "", "".join(out))            # boşalan parantezler
    return re.sub(r"\s{2,}", " ", r).strip(" -|")


# YALNIZ yapısal şirket kelimeleri — marka adları (WARNER vb.) kişi adlarıyla
# karışabildiğinden ("Jack L. Warner") kasten dışarıda.
SIRKET_RE = re.compile(
    r"\b(PRODUCTIONS?|PICTURES?|FILMS?|FILM|STUDIOS?|CORPORATION|COMPANY|INC\.?|LTD\.?"
    r"|ENTERPRISES|TELEVISION|PRODUKTION|PRODUZIONE|KİNOSTUDİYASİ|KINOSTUDIYASI"
    r"|INTERNATIONAL|BROS\.?|METRO.GOLDWYN|MK2|GMBH)\b", re.IGNORECASE)


def sirket_mi(ad: str) -> bool:
    return bool(SIRKET_RE.search(ad or ""))


def bozuk_metin(s: str) -> bool:
    """Halüsinasyon/OCR-çöpü işareti: sesli-harfsiz uzun parça ('NHMKT'), çift-sesli
    baş ('DAARIUSH') gibi. SINEMA_TEZGAHI sınıfı sahte kimliği yakalar."""
    if not s:
        return False
    for tok in re.split(r"[\s.]+", s):
        t = re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşü]", "", tok)
        if len(t) >= 4 and not re.search(r"[aeıioöuüAEIİOÖUÜ]", t):
            return True                       # 4+ harf, sesli yok → çöp
    return bool(re.search(r"^([A-Za-z])\1{1,}", s))   # "DAARIUSH", "AAgac" tipi


def saf_latin(s: str) -> bool:
    """Kaynak ad zaten Latin mi (Kiril/CJK/Arap İÇERMİYOR mu)? Kimlik-dolgusunda
    yanlış-dilden kadro enjeksiyonunu (llama-70b Kiril oyuncu vakası) engeller."""
    return not any(0x0400 <= ord(c) <= 0x04FF or 0x0370 <= ord(c) <= 0x03FF
                   or 0x0600 <= ord(c) <= 0x06FF or ord(c) >= 0x3000 for c in s or "")


def kunye_latinlestir(k: dict) -> None:
    for alan in ("yonetmen", "yapimci", "oyuncular"):
        k[alan] = [x for x in (latinlestir(a) for a in k.get(alan) or []) if x]
    for alan in ("orijinal_ad", "ozet", "tur"):
        if k.get(alan):
            k[alan] = latinlestir(k[alan])


def temiz(v) -> str | None:
    v = (v or "").strip() if isinstance(v, str) else None
    if not v:
        return None
    v = v.strip("()[]{} .·-").strip()          # "(Darıuş Mehrcuı)" / "." çöp temizliği
    if len(v) < 3 or not any(c.isalpha() for c in v) or v.lower() in COP:
        return None
    return v


TUR_MAP = {"drama": "Dram", "dram": "Dram", "comedy": "Komedi", "komedi": "Komedi",
           "western": "Western", "savas": "Savaş", "savaş": "Savaş", "war": "Savaş",
           "muzikal": "Müzikal", "müzikal": "Müzikal", "musical": "Müzikal",
           "gerilim": "Gerilim", "thriller": "Gerilim", "korku": "Korku", "horror": "Korku",
           "macera": "Macera", "adventure": "Macera", "suc": "Suç", "suç": "Suç",
           "crime": "Suç", "animasyon": "Animasyon", "animation": "Animasyon",
           "tarih": "Tarih", "aile": "Aile", "fantastik": "Fantastik", "aksiyon": "Aksiyon",
           "romantik": "Dram", "romance": "Dram", "biyografi": "Dram", "belgesel": "Belgesel"}


def adlar(kayitlar, esik=("yuksek", "orta", "dusuk")) -> list[str]:
    out = []
    for k in kayitlar or []:
        ad = temiz(k.get("ad") if isinstance(k, dict) else k)
        guven = k.get("guven", "dusuk") if isinstance(k, dict) else "yuksek"
        if ad and guven in esik and ad not in out:
            out.append(ad)
    return out


def birlesir(uyeler: list[dict]) -> dict:
    """Grup üyelerinin okuma.json'larını tek künyede birleştir.
    Üyeler parça sırasında: giriş alanları İLK parçadan, kapanış son parçadan gelir
    ama pratikte alan bazında 'dolu olan kazanır; farklı dolular çelişki'."""
    kunye = {"yonetmen": [], "yapimci": [], "oyuncular": [],
             "orijinal_ad": None, "bayraklar": [], "kaynak_parcalar": []}
    for u in uyeler:
        o = u["okuma"]
        kunye["kaynak_parcalar"].append(u["dizin"].name)
        for b in o.get("bayraklar") or []:
            if b not in kunye["bayraklar"]:
                kunye["bayraklar"].append(b)
        for alan in ("yonetmen", "yapimci"):
            yeni = adlar(o.get(alan))
            if yeni:
                if kunye[alan] and set(a.upper() for a in yeni) != set(a.upper() for a in kunye[alan]):
                    if f"celiski:{alan}" not in kunye["bayraklar"]:
                        kunye["bayraklar"].append(f"celiski:{alan}")
                        kunye[f"_celiski_{alan}"] = [kunye[alan], yeni]
                else:
                    kunye[alan] = yeni
        yeni_oy = adlar(o.get("oyuncular"))
        if len(yeni_oy) > len(kunye["oyuncular"]):
            kunye["oyuncular"] = yeni_oy
        if temiz(o.get("orijinal_ad")) and not kunye["orijinal_ad"]:
            kunye["orijinal_ad"] = temiz(o["orijinal_ad"])
    # çelişkili alan boşaltılır — hakem patch'le karar verir
    for alan in ("yonetmen", "yapimci"):
        if f"celiski:{alan}" in kunye["bayraklar"]:
            kunye[alan] = []
    kunye["oyuncular"] = kunye["oyuncular"][:8]
    return kunye


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--films", help="virgüllü dizin filtresi")
    a = ap.parse_args()

    patch = guvenli(PATCH)
    # KİMLİK ONAY LİSTESİ (Fable elle doğruladı): bu kataloglarda okuma-kanıtı
    # aranmaz — NIM kimlik tahmini doğru kabul edilip kadro-dolgusu serbest.
    onay_f = HASAT / "_kimlik_onay.txt"
    onay = set()
    if onay_f.is_file():
        onay = {s.strip()[:9] for s in onay_f.read_text(encoding="utf-8").splitlines()
                if s.strip() and not s.startswith("#")}
    globals()["_ONAY"] = onay
    kmap_f = HASAT / "_yonetmen_kadrodan.json"
    globals()["_KADRO_YON"] = guvenli(kmap_f) if kmap_f.is_file() else {}
    dizinler = sorted(p for p in HASAT.iterdir()
                      if p.is_dir() and (p / "okuma.json").is_file())
    if a.films:
        keys = [s.strip() for s in a.films.split(",")]
        dizinler = [p for p in dizinler if any(k in p.name for k in keys)]

    gruplar: dict[str, list[dict]] = {}
    for p in dizinler:
        meta = guvenli(p / "meta.json")
        katalog = (meta.get("trt_id") or p.name)[:9]          # YYYY-NNNN
        gruplar.setdefault(katalog, []).append(
            {"dizin": p, "meta": meta, "okuma": guvenli(p / "okuma.json")})

    satirlar = []
    for katalog, uyeler in sorted(gruplar.items()):
        uyeler.sort(key=lambda u: u["dizin"].name)
        kunye = birlesir(uyeler)
        # OKUMA KANITI: jenerik gerçekten kimliği destekliyor mu? (yönetmen VEYA
        # temiz orijinal-ad VEYA ≥2 oyuncu okundu). Yoksa kimlik-tahmini çıplak
        # title-guess'tir (SINEMA_TEZGAHI halüsinasyonu) → oyuncu-dolgusu YAPILMAZ.
        okuma_kaniti = bool(kunye.get("yonetmen")
                            or (kunye.get("orijinal_ad") and len(kunye["orijinal_ad"]) >= 4)
                            or len(kunye.get("oyuncular") or []) >= 2)
        # === FRAME OTORİTESİ (Çağatay: "frameleri oku, ordan bul") ===
        # Jenerikten okunan temiz-Latin, bozuk-olmayan isim OTORİTEDİR; kimlik-tahmini
        # ve patch bunu EZEMEZ — yalnız boşluk doldurur. Frame ile çelişen tahmin/patch
        # title-guess sayılıp REDDEDİLİR (14 TEMMUZ = Gigi ama patch René Clair demişti).
        def _temizmi(x):
            return bool(x) and saf_latin(x) and not bozuk_metin(x)
        dublaj = "dublaj_jenerigi_var" in kunye["bayraklar"]   # dublaj kadrosu otorite DEĞİL
        frame_yon = [x for x in (kunye.get("yonetmen") or []) if _temizmi(x)]
        frame_oy = [x for x in (kunye.get("oyuncular") or []) if _temizmi(x)]
        fy_ok = bool(frame_yon) and not dublaj
        fo_ok = len(frame_oy) >= 3 and not dublaj

        def _celisir(a_list, b_list):     # iki isim-listesi hiç örtüşmüyor mu
            return not any(difflib.SequenceMatcher(None, a.upper(), b.upper()).ratio() > 0.6
                           for a in a_list for b in b_list)

        for u in uyeler:
            z = guvenli(u["dizin"] / "zengin.json")
            if not z or z.get("kimlik_guven") == "dusuk":
                continue
            z_yon = [temiz(x) for x in (z.get("yonetmen_bilgi") or []) if temiz(x) and saf_latin(x)]
            z_yap = [temiz(x) for x in (z.get("yapimci_bilgi") or [])
                     if temiz(x) and saf_latin(x) and not sirket_mi(x)]
            z_oy = [temiz(x) for x in (z.get("oyuncular_bilgi") or []) if temiz(x) and saf_latin(x)]
            # kimlik tutarlılığı: frame yönetmeni varken zengin FARKLI yönetmen diyorsa → misID
            misID = fy_ok and z_yon and _celisir(z_yon, frame_yon)
            if not misID:                                  # özet/tür/orijinal (frame vermez)
                for alan, kaynak in (("ozet", "ozet"), ("tur", "tur"), ("orijinal_ad", "orijinal_ad")):
                    if temiz(z.get(kaynak)) and not kunye.get(alan):
                        kunye[alan] = z[kaynak].strip()
            if not fy_ok and z_yon and not misID:          # yönetmen boşsa doldur
                kunye["yonetmen"] = z_yon
                kunye["bayraklar"].append("bilgi_tamamlama:yonetmen")
            if z_yap and (not kunye.get("yapimci") or all(sirket_mi(a) for a in kunye["yapimci"])):
                kunye["yapimci"] = z_yap
            # zengin frame-YÖNETMENİNİ doğruluyorsa (Minnelli=Minnelli) kimlik frame-kanıtlı →
            # o filmin temiz kadrosu, gürültülü frame kadrosunu (karakter-adı vb.) temizler.
            korrobore = fy_ok and z_yon and not _celisir(z_yon, frame_yon)
            if korrobore and z_oy:
                # BİRLEŞTİR (değiştirme YOK — METROLAND vakası: frame 5 oyuncu okumuşken
                # kimlik listesi 2 ise oyuncu kaybediyorduk). Frame kadrosu esas, yazımı
                # kimlikten düzeltilir, kimlikte olup frame'de olmayanlar EKLENİR.
                birlesik = fuzzy_duzelt(frame_oy, z_oy) if frame_oy else []
                for g in z_oy:
                    if not any(difflib.SequenceMatcher(None, g.upper(), b.upper()).ratio() > 0.75
                               for b in birlesik):
                        birlesik.append(g)
                kunye["oyuncular"] = birlesik[:8]
                kunye["bayraklar"].append("kadro_frame_dogrulanmis_kimlik")
            elif fo_ok and z_oy:                           # doğrulama yok → frame kadrosu, yazım düzelt
                kunye["oyuncular"] = fuzzy_duzelt(frame_oy, z_oy)
            elif not fo_ok and z_oy and not misID:         # frame kadrosu yetersiz → tahminle doldur
                if okuma_kaniti or katalog in globals().get("_ONAY", set()):
                    kunye["oyuncular"] = z_oy[:8]
                    kunye["bayraklar"].append("bilgi_tamamlama:oyuncular")
                elif "kimlik_dogrulanmamis" not in kunye["bayraklar"]:
                    kunye["bayraklar"].append("kimlik_dogrulanmamis")
            break

        # KADRODAN-YÖNETMEN (Fable, kadro-kanıtından tanıdı): frame-kadrosu var ama
        # yönetmen okunamadıysa, Fable'ın kadrodan tespit ettiği yönetmen eklenir.
        # Kadro frame-kanıtlı + yönetmen kadrodan belirlenmiş = güvenilir.
        kmap = globals().get("_KADRO_YON", {})
        if not fy_ok and fo_ok and katalog in kmap and kmap[katalog]:
            kunye["yonetmen"] = kmap[katalog] if isinstance(kmap[katalog], list) else [kmap[katalog]]
            kunye["bayraklar"].append("yonetmen_kadrodan_tespit")

        pt = patch.get(katalog) or {}
        # frame yönetmeniyle ÇELİŞEN patch = title-guess hatası → tümü reddedilir
        if pt.get("yonetmen") and fy_ok and _celisir(pt["yonetmen"], frame_yon):
            kunye["bayraklar"].append("patch_reddedildi_frame_celiskisi")
            pt = {}
        for alan in ("yonetmen", "yapimci", "oyuncular", "orijinal_ad", "ozet", "tur"):
            if alan not in pt:
                continue
            if alan == "yonetmen" and fy_ok:               # frame yönetmeni korunur
                continue
            if alan == "oyuncular" and fo_ok:              # frame kadrosu korunur
                continue
            kunye[alan] = pt[alan]
        if pt.get("not"):
            kunye["bayraklar"].append(f"not:{pt['not']}")
        if kunye.get("tur"):
            kunye["tur"] = TUR_MAP.get(kunye["tur"].strip().lower(), kunye["tur"].strip().title())
        # BOZUK-KİMLİK GERİ ÇEKME: kimlik-dolgulu filmde orijinal-ad veya oyuncu adı
        # bozuksa (sahte tanıma) → identity oyuncuları geri çek, film kapıda kalır.
        if ("bilgi_tamamlama:oyuncular" in kunye["bayraklar"] and katalog not in patch
                and (bozuk_metin(kunye.get("orijinal_ad") or "")
                     or any(bozuk_metin(x) for x in (kunye.get("oyuncular") or [])))):
            kunye["oyuncular"] = []
            kunye["orijinal_ad"] = None
            kunye["bayraklar"].append("kimlik_bozuk_geri_cekildi")
        # ÖZET KALİTE KAPISI (MEYDAN OKUYANLAR vakası): kısa/dolgu özet PDF'e giremez.
        oz = (kunye.get("ozet") or "").strip()
        if oz and katalog not in patch:
            dolgu = ("belirsiz" in oz.lower() or "değişim yaşanır" in oz.lower()
                     or "ilişkileri değişir" in oz.lower() or len(oz.split()) < 28)
            if dolgu:
                kunye["ozet"] = None
                kunye["bayraklar"].append("ozet_zayif_reddedildi")
        # SEKANS KORUMASI (Çağatay: "Buz Devri 1'e 2'nin özeti geliyor"): numaralı
        # devam filmlerinde özet/kimlik yanlış-numaraya kayabilir → ÖZETİ DÜŞÜR.
        # Kadro frame-kanıtlı kaldığı için künye sağlam; sadece takas-riskli özet gider.
        baslik_h = (uyeler[0]["meta"].get("baslik") or "").strip()
        if re.search(r"[\s\-]([1-9]|I{2,3}|IV|VI{0,2}|IX|X)\s*$", baslik_h):
            kunye["ozet"] = None
            kunye["bayraklar"].append("sekans_ozet_dusuruldu")
        kunye["yonetmen_frame"] = fy_ok      # yönetmen frame'den mi okundu (güven işareti)
        kunye_latinlestir(kunye)                # LATİN zorunluluğu — son kapı
        for u in uyeler:
            (u["dizin"] / "kunye.json").write_text(
                json.dumps(kunye, ensure_ascii=False, indent=1), encoding="utf-8")
        satirlar.append("\t".join([
            katalog, uyeler[0]["meta"].get("baslik", "?"),
            "|".join(kunye.get("yonetmen") or []) or "-",
            "|".join(kunye.get("yapimci") or []) or "-",
            str(len(kunye.get("oyuncular") or [])),
            kunye.get("orijinal_ad") or "-",
            ("P" if pt else "-") + ("O" if kunye.get("ozet") else "-"),
            ",".join(kunye.get("bayraklar") or []) or "-"]))

    TABLO.write_text("katalog\tbaslik\tyonetmen\tyapimci\toy_n\torijinal\tPO\tbayraklar\n"
                     + "\n".join(satirlar) + "\n", encoding="utf-8")
    print(f"{len(gruplar)} film ({len(dizinler)} kayıt) → kunye.json + {TABLO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
