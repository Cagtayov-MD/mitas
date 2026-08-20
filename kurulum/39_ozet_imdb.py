#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ÖZET — IMDb + OMDb (2026-07-26). Wikipedia'nın kapsamı yetmediği için ana kaynak bu.

Akış (film başına):
  1) IMDb suggestion (keysiz) ile ara: frame'den okunan orijinal ad + yıl.
     → aday tt-id'ler, İngilizce başlık, yıl, kadro parçası.
  2) OMDb (tt-id ile) → Director, Actors, Year, Plot (tam).
  3) KİMLİK KANITI — üç kilit birlikte:
       BAŞLIK: sekans numarası aynı (Baba 1 ≠ Baba 2)
       YIL: OMDb yılı ile katalog yılı ±3
       KADRO/YÖNETMEN: frame'den okunan yönetmen VEYA ≥1 oyuncu OMDb ile eşleşmeli
  4) NIM, OMDb'nin GERÇEK konu metnini 3-4 cümleye indirir (uydurma imkânsız).
  5) <film>/ozet_web.json (aynı şema — mevcut hat değişmeden çalışır)

Kullanım: venvs/ocr/bin/python kurulum/39_ozet_imdb.py --films-file <liste> --workers 4
"""
import argparse
import concurrent.futures as cf
import difflib
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

KOK = Path("/opt/mitas")
HASAT = KOK / "filmtest" / "kapanis_hasat"
NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
LLM = "meta/llama-4-maverick-17b-128e-instruct"
UA = {"User-Agent": "Mozilla/5.0 (MITAS-arsiv; cagtayovsky@gmail.com)"}
OMDB_KEYS = ["trilogy", "4a3b711b", "e19f9bdb"]     # kamuya açık demo anahtarları
_kilit = threading.Lock()
_son = [0.0]
ARALIK = 0.4


def _get(url: str, timeout: int = 20):
    for i in range(3):
        try:
            with _kilit:
                b = ARALIK - (time.time() - _son[0])
                if b > 0:
                    time.sleep(b)
                d = json.loads(urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=timeout).read())
                _son[0] = time.time()
            return d
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and i < 2:
                time.sleep(3 * (i + 1) + random.random())
                continue
            return {}
        except Exception:
            if i < 2:
                time.sleep(2)
                continue
            return {}
    return {}


def imdb_ara(sorgu: str) -> list[dict]:
    q = urllib.parse.quote(sorgu.strip()[:60])
    if not q:
        return []
    d = _get(f"https://v3.sg.media-imdb.com/suggestion/x/{q}.json")
    return [x for x in (d.get("d") or []) if str(x.get("id", "")).startswith("tt")]


def omdb(tt: str) -> dict:
    for k in OMDB_KEYS:
        d = _get(f"http://www.omdbapi.com/?i={tt}&plot=full&apikey={k}")
        if d.get("Response") == "True":
            return d
    return {}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z ]", "", (s or "").lower()
                  .replace("ı", "i").replace("ş", "s").replace("ğ", "g")
                  .replace("ü", "u").replace("ö", "o").replace("ç", "c")
                  .replace("é", "e").replace("è", "e").replace("ó", "o")
                  .replace("á", "a").replace("í", "i").replace("ú", "u")
                  .replace("ä", "a").replace("ë", "e").replace("ï", "i"))


def ad_esles(a: str, liste: list[str], esik: float = 0.82) -> bool:
    na = _norm(a)
    if len(na) < 5:
        return False
    for b in liste:
        nb = _norm(b)
        if not nb:
            continue
        if na == nb or na in nb or nb in na:
            return True
        if difflib.SequenceMatcher(None, na, nb).ratio() >= esik:
            return True
        pa, pb = na.split(), nb.split()
        if pa and pb and len(pa[-1]) > 3 and pa[-1] == pb[-1]:   # soyad + ilk harf
            if pa[0][:1] == pb[0][:1]:
                return True
    return False


ROMEN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}


def _seri_no(s: str):
    s = (s or "").strip()
    m = re.search(r"\b(?:part|bölüm|chapter)?\s*([2-9]|1[0-9])\s*$", s, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(?:part|bölüm)?\s*(i{1,3}|iv|vi{0,3}|ix|x)\s*$", s, re.I)
    return ROMEN.get(m.group(1).lower()) if m else None


def nim(prompt: str, mt: int = 700) -> str:
    key = None
    for s in (KOK / "council_mcp" / ".env").read_text(encoding="utf-8").splitlines():
        if s.startswith("NVIDIA_API_KEY="):
            key = s.split("=", 1)[1].strip()
    veri = json.dumps({"model": LLM, "temperature": 0.0, "max_tokens": mt,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    for i in range(3):
        try:
            req = urllib.request.Request(NIM_URL, data=veri, headers={
                "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"] or ""
        except Exception:
            time.sleep(3)
    return ""


DOLGU = ("belirsiz", "konu alır", "anlatılmaktadır", "ele alır")


def ozetle(plot: str, baslik: str) -> str:
    p = (f"Aşağıda '{baslik}' filminin IMDb konu metni var.\n\n--- KAYNAK ---\n{plot[:4000]}\n"
         "--- SON ---\n\nBu metne DAYANARAK Türkçe özet yaz. Sadece JSON: {\"ozet\":\"\"}\n"
         "KURALLAR: 3-4 cümle, 40-55 kelime, TEK paragraf. Olayı doğrudan anlat, filmin "
         "SONUNU açıkça söyle (spoiler serbest). SADECE kaynakta yazanı kullan, olay/isim "
         "EKLEME. Yabancı özel adları BÜYÜK ASCII yaz (aksan/Türkçe İ yok); Türkçe kelimeler "
         "normal küçük harf. Muğlak/dolgu cümle yasak.")
    try:
        m = re.search(r"\{.*\}", nim(p), re.DOTALL)
        return (json.loads(m.group(0)).get("ozet") or "").strip() if m else ""
    except Exception:
        return ""


def isle(dizin_ad: str) -> str:
    d = HASAT / dizin_ad
    kj = d / "kunye.json"
    if not kj.is_file():
        return "kunye_yok"
    k = json.loads(kj.read_text(encoding="utf-8"))
    yon = k.get("yonetmen") or []
    oy = (k.get("oyuncular") or [])[:8]
    if not yon or len(oy) < 3:
        return "zayif"
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    yil = int(dizin_ad[:4])
    orij = (k.get("orijinal_ad") or "").strip()
    tr = (meta.get("baslik") or "").strip()
    anahtar = orij or tr

    adaylar = []
    for s in (orij, tr, f"{orij} {yil}", f"{tr} {yil}"):
        if not s.strip():
            continue
        for it in imdb_ara(s):
            if it["id"] not in [a["id"] for a in adaylar]:
                adaylar.append(it)
        if len(adaylar) >= 8:
            break

    for it in adaylar[:8]:
        iy = it.get("y")
        if iy and abs(int(iy) - yil) > 3 and yil <= 2000:
            continue                                    # YIL KİLİDİ (eski katalog)
        # SEKANS KİLİDİ: numaralar aynı olmalı
        if _seri_no(anahtar) != _seri_no(it.get("l", "")):
            if _seri_no(anahtar) or _seri_no(it.get("l", "")):
                continue
        o = omdb(it["id"])
        if not o or not (o.get("Plot") or "").strip() or o.get("Plot") == "N/A":
            continue
        o_yon = [x.strip() for x in (o.get("Director") or "").split(",") if x.strip()]
        o_oy = [x.strip() for x in (o.get("Actors") or "").split(",") if x.strip()]
        # KADRO KANITI: frame yönetmeni VEYA frame oyuncusu OMDb ile eşleşmeli
        k_yon = [y for y in yon if ad_esles(y, o_yon)]
        k_oy = [a for a in oy if ad_esles(a, o_oy)]
        if not (k_yon or len(k_oy) >= 1):
            continue
        try:
            o_yil = int(re.search(r"\d{4}", o.get("Year") or "").group(0))
        except Exception:
            o_yil = None
        if o_yil and yil <= 2000 and abs(o_yil - yil) > 3:
            continue
        oz = ozetle(o["Plot"], o.get("Title", ""))
        if oz and len(oz.split()) >= 25 and not any(x in oz.lower() for x in DOLGU):
            (d / "ozet_web.json").write_text(json.dumps({
                "ozet": oz, "kaynak": f"imdb:{it['id']} omdb:{o.get('Title')} ({o.get('Year')})",
                "kanit_yonetmen": k_yon, "kanit_oyuncu": k_oy,
                "omdb_yonetmen": o_yon, "omdb_oyuncu": o_oy},
                ensure_ascii=False, indent=1), encoding="utf-8")
            return "ok"
    return "bulunamadi"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--films-file")
    ap.add_argument("--films")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.films_file:
        a.films = open(a.films_file).read().strip()
    hedef = [s.strip() for s in (a.films or "").split(",") if s.strip()]
    dz = [d.name for d in sorted(HASAT.iterdir())
          if d.is_dir() and any(h in d.name for h in hedef)] if hedef else []
    if a.limit:
        dz = dz[:a.limit]
    print(f"{len(dz)} film → IMDb/OMDb özeti", flush=True)
    say = {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for r in ex.map(isle, dz):
            say[r] = say.get(r, 0) + 1
            n = sum(say.values())
            if n % 50 == 0:
                print(f"  {n}/{len(dz)} bulunan={say.get('ok',0)}", flush=True)
    print(f"BİTTİ: {say} ({(time.time()-t0)/60:.1f} dk)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
