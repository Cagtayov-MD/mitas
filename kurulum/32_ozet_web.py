#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ÖZET — İNTERNETTEN (Wikipedia), KİMLİK KANITLI (2026-07-25).

Çağatay kuralı: "filmden emin olduktan sonra filmin internetten özetini bulacaksın".
Model hafızasından özet YASAK (halüsinasyon kaynağı) — özet GERÇEK metinden üretilir.

Akış (film başına):
  1) Frame'den okunmuş künye: orijinal ad / başlık + yıl + YÖNETMEN + kadro.
  2) Wikipedia'da ara (tr → en). Aday makalelerin tam metni çekilir.
  3) KİMLİK KANITI: makalede bizim frame-yönetmenimiz VEYA ≥2 frame-oyuncumuz
     geçmeli. Geçmiyorsa yanlış makale → atlanır (özet YOK).
  4) Konu/Plot bölümü ayıklanır → NIM bu GERÇEK metni 3-4 cümleye indirir
     (uydurma imkânsız: kaynak metin veriliyor, "metinde yoksa yazma" kuralı).
  5) <film>/ozet_web.json  {ozet, kaynak_url, kanit}

Kullanım: venvs/ocr/bin/python kurulum/32_ozet_web.py --films <kat,...> --workers 8
"""
import argparse
import concurrent.futures as cf
import difflib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

KOK = Path("/opt/mitas")
HASAT = KOK / "filmtest" / "kapanis_hasat"
NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
LLM = "meta/llama-4-maverick-17b-128e-instruct"
UA = {"User-Agent": "MITAS-arsiv/1.0 (https://trt.net.tr; cagtayovsky@gmail.com) python-urllib",
      "Accept": "application/json"}
PLOT_BAS = re.compile(
    r"^==+\s*(Konu|Özet|Öykü|Plot|Synopsis|Story|Premise|Résumé|Intrigue|Handlung|"
    r"Inhalt|Trama|Argumento|Sinopsis|Сюжет|Fabuła|Zápletka)\s*==+\s*$", re.I | re.M)


def anahtar() -> str:
    for s in (KOK / "council_mcp" / ".env").read_text(encoding="utf-8").splitlines():
        if s.startswith("NVIDIA_API_KEY="):
            return s.split("=", 1)[1].strip()
    raise RuntimeError("anahtar yok")


KEY = anahtar()


import threading

_wiki_kilit = threading.Lock()      # TEK eşzamanlı istek (429 kökünü kesiyor)
_son_istek = [0.0]
ARALIK = 0.5                        # saniye/istek (uyumlu UA ile yüksek kota)


class HizSiniri(Exception):
    """Ağ/hız-sınırı hatası: 'film bulunamadı' DEĞİL → sonuç yazılmaz, tekrar denenir."""


def _get(url: str, timeout: int = 25):
    son = None
    for i in range(3):          # kısa deneme: takılmadan hızlı vazgeç, sonra tekrar tur
        try:
            with _wiki_kilit:
                bekle = ARALIK - (time.time() - _son_istek[0])
                if bekle > 0:
                    time.sleep(bekle)
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    d = json.loads(r.read())
                _son_istek[0] = time.time()
            return d
        except urllib.error.HTTPError as e:
            son = e
            if e.code in (429, 503, 502):
                time.sleep(min(15, 3 * (2 ** i)) + random.random() * 2)
                continue
            raise HizSiniri(str(e)) from e
        except Exception as e:
            son = e
            time.sleep(3 + i * 2)
    raise HizSiniri(f"tekrar denenecek: {son}")


def wiki_girisler(dil: str, basliklar: list[str]) -> dict[str, str]:
    """TEK istekte çok sayfanın GİRİŞ paragrafı (exintro+exlimit=max çalışır).
    Kimlik kanıtı ('directed by X, starring Y') zaten giriştedir → ucuz eleme."""
    if not basliklar:
        return {}
    u = (f"https://{dil}.wikipedia.org/w/api.php?action=query&prop=extracts&exintro=1"
         f"&explaintext=1&exlimit=max&format=json&redirects=1"
         f"&titles={urllib.parse.quote('|'.join(basliklar[:5]))}")
    sf = _get(u).get("query", {}).get("pages", {}) or {}
    return {p.get("title", ""): (p.get("extract", "") or "") for p in sf.values()}


def wiki_ara_metin(dil: str, sorgu: str, limit: int = 3,
                   anahtar: str = "") -> list[tuple[str, str]]:
    """Arama (1 istek) → BAŞLIK KAPISI (bedava, istek yok) → yalnız geçenlerin metni.
    Başlık kapısını metin indirmeden uygulamak istek sayısını ~3× düşürür."""
    u = (f"https://{dil}.wikipedia.org/w/api.php?action=query&list=search&format=json"
         f"&srlimit={limit + 3}&srsearch={urllib.parse.quote(sorgu)}")
    basliklar = [x["title"] for x in _get(u).get("query", {}).get("search", [])]
    secili = [t for t in basliklar
              if "disambiguation" not in t.lower() and "anlam ayrımı" not in t.lower()
              and not KOTU_TIP.search(t)
              and (not anahtar or baslik_esles(t, anahtar))][:3]
    return [(t, "") for t in secili]        # metin sonra: önce ucuz giriş elemesi


ROMEN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}


def _seri_no(s: str):
    """Başlıktaki sekans numarası: 'Baba 2', 'Part II', 'Rocky IV' → 2/2/4; yoksa None."""
    m = re.search(r"\b(?:part|bölüm|chapter)?\s*([2-9]|1[0-9])\b\s*$", (s or "").strip(), re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(?:part|bölüm)?\s*(i{1,3}|iv|vi{0,3}|ix|x)\b\s*$", (s or "").strip(), re.I)
    if m:
        return ROMEN.get(m.group(1).lower())
    return None


def baslik_esles(makale_basligi: str, anahtar: str) -> bool:
    """Frame'den okunan film adı ile Wikipedia makale adı aynı filmi mi gösteriyor?
    Sekans numarası FARKLIYSA reddedilir (Baba 1 ≠ Baba 2 — kadro ikisinde de aynı)."""
    if not anahtar or len(anahtar) < 3:
        return False
    mb = re.sub(r"\((?:[^)]*film[^)]*|\d{4})\)", "", makale_basligi, flags=re.I).strip()
    a_no, m_no = _seri_no(anahtar), _seri_no(mb)
    if (a_no or m_no) and a_no != m_no:
        return False                       # sekans numarası uyuşmuyor → farklı film
    na, nm = _norm(anahtar), _norm(mb)
    if not na or not nm:
        return False
    return (difflib.SequenceMatcher(None, na, nm).ratio() >= 0.78
            or na in nm or nm in na)


FILM_ISARET = re.compile(
    r"\b(is|was) an? [^.]{0,60}\b(film|movie)\b|\bfilm directed by\b|\byönetmenliğini\b|"
    r"\b(film|filmi)dir\b|\bsinema filmi\b|"
    r"\bfilm [^.]{0,40}(réalisé|français|italien|allemand)\b|\bfilm von\b|"
    r"\bSpielfilm\b|\bfilm [^.]{0,30}diretto da\b|\bpelícula[^.]{0,40}dirigida\b|"
    r"\b(художественный )?фильм\b", re.I)
KOTU_TIP = re.compile(r"\((novel|book|play|opera|song|album|TV series|video game|"
                      r"roman|kitap|oyun)\)", re.I)


def wiki_metin(dil: str, baslik: str) -> str:
    u = (f"https://{dil}.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1"
         f"&format=json&redirects=1&titles={urllib.parse.quote(baslik)}")
    sf = _get(u).get("query", {}).get("pages", {})
    return next(iter(sf.values())).get("extract", "") or ""


def _norm(s: str) -> str:
    return re.sub(r"[^a-z ]", "", (s or "").lower()
                  .replace("ı", "i").replace("ş", "s").replace("ğ", "g")
                  .replace("ü", "u").replace("ö", "o").replace("ç", "c"))


def gecer_mi(metin: str, adlar: list[str]) -> list[str]:
    """Makalede geçen adları BULANIK eşleştirmeyle bul — OCR varyantlarını yakalar
    (MEREDETH↔Meredith, DeCARLO↔De Carlo). Kimlik kanıtının gücünü belirler."""
    # makaledeki büyük-harfle başlayan 2-3 kelimelik ad öbekleri
    obekler = re.findall(r"[A-ZÇĞİÖŞÜ][\w'’.-]+(?:\s+[A-ZÇĞİÖŞÜ][\w'’.-]+){1,2}", metin)
    havuz = {_norm(o) for o in obekler}
    havuz_metin = _norm(metin)
    bulunan = []
    for a in adlar:
        na = _norm(a)
        if len(na) < 6:
            continue
        if na in havuz_metin:
            bulunan.append(a); continue
        if any(difflib.SequenceMatcher(None, na, h).ratio() >= 0.85 for h in havuz):
            bulunan.append(a); continue
        # soyad + ilk harf eşleşmesi (ad kısaltılmış/farklı yazılmış olabilir)
        p = na.split()
        if len(p) >= 2 and len(p[-1]) > 4 and any(
                p[-1] in h and h.split()[0][:1] == p[0][:1] for h in havuz):
            bulunan.append(a)
    return bulunan


def plot_ayikla(metin: str) -> str:
    m = PLOT_BAS.search(metin)
    if m:
        kalan = metin[m.end():]
        son = re.search(r"^==+[^=]+==+\s*$", kalan, re.M)
        blok = kalan[:son.start()] if son else kalan
        if len(blok.split()) >= 40:
            return blok.strip()[:6000]
    # plot bölümü yoksa: giriş paragrafları (çoğu makalede konu özeti içerir)
    giris = metin.split("\n==")[0]
    return giris.strip()[:6000] if len(giris.split()) >= 60 else ""


def nim(prompt: str, mt: int = 700) -> str:
    veri = json.dumps({"model": LLM, "temperature": 0.0, "max_tokens": mt,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    for i in range(4):
        try:
            req = urllib.request.Request(NIM_URL, data=veri, headers={
                "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < 3:
                time.sleep(2 ** i * 2 + random.random()); continue
            raise
        except Exception:
            if i < 3:
                time.sleep(3); continue
            raise
    return ""


DOLGU = ("belirsiz", "konu alır", "anlatılmaktadır", "ele alır")


def ozetle(kaynak: str, baslik: str) -> str:
    p = (f"Aşağıda '{baslik}' filminin ansiklopedi maddesinden alınmış GERÇEK konu metni var.\n\n"
         f"--- KAYNAK METİN ---\n{kaynak[:5000]}\n--- SON ---\n\n"
         "Bu metne DAYANARAK Türkçe özet yaz. Sadece şu JSON: {\"ozet\":\"\"}\n"
         "KURALLAR:\n"
         "- 3-4 cümle, 40-55 kelime, TEK paragraf.\n"
         "- Olayı doğrudan anlat ve filmin SONUNU açıkça söyle (spoiler serbest).\n"
         "- SADECE kaynak metinde yazanı kullan. Metinde olmayan olay/isim EKLEME.\n"
         "- Kaynakta konu anlatılmıyorsa ozet=\"\" bırak.\n"
         "- Yabancı özel adları BÜYÜK ASCII yaz (aksan/Türkçe İ kullanma); "
         "Türkçe kelimeler normal küçük harf.")
    try:
        m = re.search(r"\{.*\}", nim(p), re.DOTALL)
        return (json.loads(m.group(0)).get("ozet") or "").strip() if m else ""
    except Exception:
        return ""


def isle(d: Path) -> str:
    kj = d / "kunye.json"
    if not kj.is_file():
        return "kunye_yok"
    k = json.loads(kj.read_text(encoding="utf-8"))
    yon = k.get("yonetmen") or []
    oy = (k.get("oyuncular") or [])[:6]
    if not yon or len(oy) < 3:
        return "zayif"
    try:
        return _isle(d, k, yon, oy)
    except HizSiniri:
        return "agir_hata"          # sonuç YAZILMAZ → sonraki turda tekrar denenir


def _isle(d: Path, k: dict, yon: list, oy: list) -> str:
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    yil = d.name[:4]
    orij = (k.get("orijinal_ad") or "").strip()
    tr = (meta.get("baslik") or "").strip()

    # BAŞLIK ANAHTARI: önce frame'den okunan orijinal ad / başlık kartı, yoksa TRT başlığı
    anahtar_ad = (orij or k.get("film_baslik_karti") or tr or "").strip()
    sorgular = [("en", f"{orij} {yil} film"), ("tr", f"{tr} {yil} filmi"),
                ("en", f"{orij} film"), ("tr", f"{tr} filmi {yon[0]}")]
    # ÇOK DİLLİ: arşivin çoğu Avrupa yapımı — makale kendi dilinde olabilir
    for dl in ("fr", "it", "de", "es", "ru"):
        if orij:
            sorgular.append((dl, f"{orij} {yon[0]}"))
    if orij and orij.upper() != tr.upper():
        sorgular.append(("en", f"{orij} film {yon[0]}"))
    else:
        sorgular.append(("en", f"{yon[0]} {oy[0]} film"))

    # HIZLI YOL: arama yapmadan doğrudan başlıkla sayfa dene (1 istek).
    # Wikipedia yönlendirmeleri çoğu ad varyantını çözer → aramaya gerek kalmaz.
    dogrudan = []
    for dil, ad in (("en", orij), ("tr", tr), ("en", f"{orij} ({yil} film)"),
                    ("fr", orij), ("it", orij), ("de", orij)):
        if ad and len(ad) > 3 and (dil, ad) not in dogrudan:
            dogrudan.append((dil, ad))
    for dil, ad in dogrudan[:4]:
        try:
            metin = wiki_metin(dil, ad)
        except HizSiniri:
            raise
        if len(metin) < 400 or not FILM_ISARET.search(metin[:700]):
            continue
        k_yon, k_oy = gecer_mi(metin, yon), gecer_mi(metin, oy)
        m_y0 = re.search(r"\b(1[89]\d{2}|20[0-2]\d)\b", metin[:500])
        yil0 = bool(m_y0) and abs(int(m_y0.group(1)) - int(yil)) <= 2
        if not (k_yon and (len(k_oy) >= 2 or yil0) and baslik_esles(ad, anahtar_ad)):
            continue
        plot = plot_ayikla(metin)
        if plot:
            oz = ozetle(plot, ad)
            if oz and len(oz.split()) >= 25 and not any(x in oz.lower() for x in DOLGU):
                (d / "ozet_web.json").write_text(json.dumps({
                    "ozet": oz, "kaynak": f"{dil}.wikipedia:{ad}",
                    "kanit_yonetmen": k_yon, "kanit_oyuncu": k_oy},
                    ensure_ascii=False, indent=1), encoding="utf-8")
                return "ok"

    for dil, sorgu in sorgular[:7]:              # arama: en fazla 2 sorgu (maliyet kontrolü)
        s = re.sub(r"\b(film|filmi)\b|\d{4}", "", sorgu).strip()
        if len(s) < 3:
            continue
        adaylar = [t for t, _ in wiki_ara_metin(dil, sorgu, 3, anahtar_ad)
                   if not KOTU_TIP.search(t)
                   and not any(difflib.SequenceMatcher(None, _norm(t), _norm(a)).ratio() > 0.8
                               for a in yon + oy)]     # kişi-sayfası (Tarkovsky) elenir
        if not adaylar:
            continue
        girisler = wiki_girisler(dil, adaylar)         # TEK istekte tüm girişler
        for t in adaylar:
            giris = girisler.get(t, "")
            if len(giris) < 120 or not FILM_ISARET.search(giris[:700]):
                continue                                # FİLM makalesi değil (ucuz eleme)
            # kimlik kanıtı ÖNCE girişte aranır (istek yok); zayıfsa tam metne bakılır
            k_yon = gecer_mi(giris, yon)
            k_oy = gecer_mi(giris, oy)
            metin = giris
            if not (k_yon and len(k_oy) >= 2):
                metin = wiki_metin(dil, t)              # yalnız gerekirse tam metin
                if len(metin) < 300:
                    continue
                k_yon = gecer_mi(metin, yon)
                k_oy = gecer_mi(metin, oy)
            elif len(metin) < 800:
                metin = wiki_metin(dil, t)              # plot için tam metin şart
            # YIL KANITI: makalenin girişindeki yapım yılı (çok dilli makalelerde
            # kadro listesi düz-metne gelmiyor; yıl+yönetmen+başlık üçlüsü kimliği
            # kadro kadar kesin sabitler — remake yılla, sekans numarayla ayrılır).
            m_y = re.search(r"\b(1[89]\d{2}|20[0-2]\d)\b", metin[:500])
            yil_uyum = bool(m_y) and abs(int(m_y.group(1)) - int(yil)) <= 2
            # KESİN KİMLİK — iki bağımsız anahtar birlikte:
            #  (a) BAŞLIK: frame'den okunan ad ile makale adı eşleşmeli + sekans
            #      numarası aynı olmalı → Baba 1 / Baba 2 karışması biter
            #      (kadro aynı olduğu için kadro tek başına sekansı AYIRAMAZ).
            #  (b) KADRO: yönetmen + ≥2 oyuncu → yeniden-çevrim/sürüm karışması biter
            #      (1936 ↔ 1996 Romeo: kadro farklı).
            if not baslik_esles(t, anahtar_ad):
                continue
            # (a) yönetmen + ≥2 oyuncu  VEYA  (b) yönetmen + YIL uyumu
            if not (k_yon and (len(k_oy) >= 2 or yil_uyum)):
                continue
            # YIL KAPISI (eski katalog = yapım yılı): 1996 Romeo+Juliet ≠ 1936 Cukor
            if int(yil) <= 2000:
                m_yil = re.search(r"\b(1[89]\d{2}|20[0-2]\d)\b", metin[:400])
                if m_yil and abs(int(m_yil.group(1)) - int(yil)) > 4:
                    continue
            plot = plot_ayikla(metin)
            if not plot:
                continue
            oz = ozetle(plot, t)
            if oz and len(oz.split()) >= 25 and not any(x in oz.lower() for x in DOLGU):
                (d / "ozet_web.json").write_text(json.dumps({
                    "ozet": oz, "kaynak": f"{dil}.wikipedia:{t}",
                    "kanit_yonetmen": k_yon, "kanit_oyuncu": k_oy},
                    ensure_ascii=False, indent=1), encoding="utf-8")
                return "ok"
    (d / "ozet_web.json").write_text(json.dumps({"ozet": "", "kaynak": "", "kanit_yonetmen": [],
                                                 "kanit_oyuncu": []}, ensure_ascii=False),
                                     encoding="utf-8")
    return "bulunamadi"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--films")
    ap.add_argument("--films-file")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    dz = sorted(d for d in HASAT.iterdir() if d.is_dir() and (d / "kunye.json").is_file())
    if a.films_file:
        a.films = open(a.films_file).read().strip()
    if a.films:
        ks = [s.strip() for s in a.films.split(",") if s.strip()]
        dz = [d for d in dz if any(k in d.name for k in ks)]
    if not a.force:
        dz = [d for d in dz if not (d / "ozet_web.json").is_file()]
    print(f"{len(dz)} film → web özeti", flush=True)
    say = {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for r in ex.map(isle, dz):
            say[r] = say.get(r, 0) + 1
            n = sum(say.values())
            if n % 50 == 0:
                print(f"  {n}/{len(dz)} — bulunan {say.get('ok',0)}", flush=True)
    print(f"BİTTİ: {say} ({(time.time()-t0)/60:.1f} dk)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
