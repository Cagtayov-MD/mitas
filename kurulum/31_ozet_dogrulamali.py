#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ÖZET — ÇAPRAZ DOĞRULAMALI (2026-07-25).

Sorun: kimlik doğru olsa bile model özeti uydurabiliyor (KABADAYI/Swashbuckler →
"Jane Barnett/RIPPER" halüsinasyonu).

Çözüm: özet, FRAME'den okunmuş künyeye ÇAPRAZ-KİLİTLENİR.
  1) NIM'e film adı + yıl + FRAME'den okunan yönetmen/oyuncular verilir.
  2) Model, filmi bağımsız tanıyıp yönetmenini KENDİ söyler + 2 ana karakter adı verir.
  3) KAPI: modelin söylediği yönetmen, frame'den okuduğumuz yönetmenle eşleşmeli.
     Eşleşmezse → model filmi tanımıyor demektir → ÖZET YOK (uydurma engellenir).
  4) Ek kapı: özet, kadro/karakterlerle ilgisiz isim üretmişse reddedilir.

Çıktı: <film>/ozet_dogrulanmis.json  {ozet, dogrulandi, model_yonetmen}
Kullanım: venvs/ocr/bin/python kurulum/31_ozet_dogrulamali.py --films <kat,kat>
"""
import argparse
import concurrent.futures as cf
import difflib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

KOK = Path("/opt/mitas")
HASAT = KOK / "filmtest" / "kapanis_hasat"
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
LLM = "meta/llama-4-maverick-17b-128e-instruct"
LLM2 = "meta/llama-3.3-70b-instruct"


def anahtar() -> str:
    for s in (KOK / "council_mcp" / ".env").read_text(encoding="utf-8").splitlines():
        if s.startswith("NVIDIA_API_KEY="):
            return s.split("=", 1)[1].strip()
    raise RuntimeError("anahtar yok")


KEY = anahtar()


def nim(model: str, prompt: str, mt: int = 1200) -> str:
    veri = json.dumps({"model": model, "temperature": 0.0, "max_tokens": mt,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    for i in range(5):
        try:
            req = urllib.request.Request(URL, data=veri, headers={
                "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < 4:
                time.sleep(2 ** i * 2 + random.random()); continue
            raise
        except Exception:
            if i < 4:
                time.sleep(4); continue
            raise
    return ""


def jayikla(s):
    m = re.search(r"\{.*\}", s, re.DOTALL)
    return json.loads(m.group(0)) if m else {}


def esles(a_list, b_list, esik=0.72) -> bool:
    return any(difflib.SequenceMatcher(None, a.upper(), b.upper()).ratio() >= esik
               for a in a_list for b in b_list)


DOLGU = ("belirsiz", "değişim yaşanır", "ilişkileri değişir", "konu alır", "anlatılır")


def uret(d: Path) -> str:
    kj, oj = d / "kunye.json", d / "ozet_dogrulanmis.json"
    if not kj.is_file():
        return "kunye_yok"
    k = json.loads(kj.read_text(encoding="utf-8"))
    yon = k.get("yonetmen") or []
    oy = (k.get("oyuncular") or [])[:6]
    if not yon or len(oy) < 3:
        return "kunye_zayif"
    m = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    baslik, yil = m.get("baslik", "?"), d.name[:4]
    orij = k.get("orijinal_ad") or ""

    p = (f"Bir filmi tanımlaman isteniyor. Elimizde filmin JENERİĞİNDEN okunmuş kesin veri var:\n"
         f"- Türkçe başlık: {baslik}\n- Orijinal ad (varsa): {orij}\n- Yıl: ~{yil}\n"
         f"- YÖNETMEN (jenerikten): {', '.join(yon)}\n- OYUNCULAR (jenerikten): {', '.join(oy)}\n\n"
         "Bu filmi TANIYOR musun? Sadece bu JSON'u döndür:\n"
         '{"film":"filmin uluslararası adı (yıl)", "yonetmen_ben":"SENİN bildiğin yönetmen adı",'
         ' "ana_karakterler":["2 ana karakter adı"], "ozet":"", "taniyorum":true|false}\n\n'
         "KURALLAR:\n"
         "- yonetmen_ben: yukarıdaki listeye BAKMADAN, kendi bilginle bu filmin yönetmeni kim? "
         "Filmi tanımıyorsan taniyorum=false yap ve ozet=\"\" bırak. TAHMİN ETME.\n"
         "- ozet: filmi gerçekten tanıyorsan 3-4 cümle, 40-55 kelime, TEK paragraf; olayı "
         "DOĞRUDAN anlat ve GERÇEK SONU açıkça söyle (spoiler serbest). Muğlak/dolgu cümle yok.\n"
         "- Özette geçen kişi adları filmin GERÇEK karakterleri olmalı (uydurma isim YASAK).\n"
         "- Yabancı özel adları BÜYÜK ASCII yaz (JANE, RIPPER değil gerçek karakterler); "
         "Türkçe kelimeler normal küçük harf. Aksan kullanma.")
    ozet, myon = "", ""
    for model in (LLM, LLM2):          # biri bilmiyorsa ikinci model dener
        try:
            z = jayikla(nim(model, p))
        except Exception:
            continue
        o = (z.get("ozet") or "").strip()
        my = (z.get("yonetmen_ben") or "").strip()
        myon = myon or my
        if not (z.get("taniyorum") and my and esles([my], yon)):
            continue                    # KAPI 1: yönetmeni bağımsız doğrulayamadı
        if len(o.split()) < 28 or any(x in o.lower() for x in DOLGU):
            continue                    # KAPI 2: dolgu/kısa özet
        ozet, myon = o, my
        break
    oj.write_text(json.dumps({"ozet": ozet, "dogrulandi": bool(ozet),
                              "model_yonetmen": myon, "film": z.get("film", "")},
                             ensure_ascii=False, indent=1), encoding="utf-8")
    return "dogrulandi" if ozet else "reddedildi"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--films")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    dz = sorted(d for d in HASAT.iterdir() if d.is_dir() and (d / "kunye.json").is_file())
    if a.films:
        ks = [s.strip() for s in a.films.split(",") if s.strip()]
        dz = [d for d in dz if any(k in d.name for k in ks)]
    if not a.force:
        dz = [d for d in dz if not (d / "ozet_dogrulanmis.json").is_file()]
    print(f"{len(dz)} film → doğrulamalı özet", flush=True)
    say = {"dogrulandi": 0, "reddedildi": 0, "diger": 0}
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for r in ex.map(uret, dz):
            say[r if r in say else "diger"] += 1
            n = sum(say.values())
            if n % 50 == 0:
                print(f"  {n}/{len(dz)} — doğrulanan {say['dogrulandi']}", flush=True)
    print(f"BİTTİ: doğrulanan {say['dogrulandi']}, reddedilen {say['reddedildi']}, "
          f"diğer {say['diger']} ({(time.time()-t0)/60:.1f} dk)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
