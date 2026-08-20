#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NIM KÜNYE HATTI: okuma+birleştirme+özet tamamen NVIDIA API'de (Claude token=0).

Aşamalar (film başına):
  A) VISION (Llama-4 Maverick): filtreli kareler 8'li gruplarla → birebir transkript
     (kare adı + metin; footage=YOK). Ham çıktı nim_ham/'a kaydedilir (Fable QC kanıtı).
  B) METİN (DeepSeek-V4-Pro): transkriptler → okuma.json (Sonnet şemasıyla birebir;
     dublaj tuzağı/tahmin yasak/çelişki bayrağı kuralları promptta).
  C) METİN (DeepSeek-V4-Pro): başlık+yıl+künye → zengin.json {orijinal_ad, tur, ozet}.
     Özet: ozet_film_v2 kuralı (3-4 cümle, ~35-60 kelime, spoiler'lı, TEK paragraf) +
     yabancı özel adlar BÜYÜK-ASCII (İ kullanma!), Türkçe kelimeler normal.

Kullanım:
  venvs/ocr/bin/python kurulum/29_nim_okuma.py --workers 5            # okunmamışlar
  venvs/ocr/bin/python kurulum/29_nim_okuma.py --sadece-zengin        # okunmuşlara C
  ... --films 1963-0024 --force
"""
import argparse
import base64
import concurrent.futures as cf
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

KOK = Path("/opt/mitas")
HASAT = KOK / "filmtest" / "kapanis_hasat"
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
VLM = "meta/llama-4-maverick-17b-128e-instruct"
VLM_YEDEK = "nvidia/nemotron-nano-12b-v2-vl"
LLM = "meta/llama-4-maverick-17b-128e-instruct"
LLM_YEDEK = "meta/llama-3.3-70b-instruct"
GRUP = 8              # istek başına kare
_kilit = threading.Lock()

OKUMA_SEMA = """{"yonetmen":[{"ad":"","kare":"","guven":"yuksek|orta|dusuk"}],
"yapimci":[...aynı yapı...],"oyuncular":[...aynı yapı, jenerik sırasıyla, en çok 12...],
"orijinal_ad":"", "film_baslik_karti":"", "diger_kunye":[{"rol":"","ad":"","kare":""}],
"bayraklar":[""], "okunan_kare_sayisi":{"giris":0,"kapanis":0}}"""

KURALLAR = """KURALLAR:
- SADECE transkriptte YAZANI kullan; tahmin/tamamlama YASAK. Emin olunamayan harf yerine ?.
- Yönetmen etiketleri: YÖNETMEN/REJİSÖR/REJİ/DIRECTED BY/A FILM BY/RÉALISATION/MISE EN
  SCÈNE/REGIE/REGIA. Yapımcı: YAPIMCI/PRODÜKTÖR/PRODUCER(S)/PRODUCED BY (salt şirket
  kartıysa şirket adı; EXECUTIVE PRODUCER ancak düz yapımcı yoksa, bayrakla).
- TRT DUBLAJ TUZAĞI: SESLENDİRENLER/TÜRKÇE SESLENDİRME/DUBLAJ blokları filmin künyesi
  DEĞİL — alma, "dublaj_jenerigi_var" bayrağı ekle.
- Sarı altyazı satırları diyalogdur, künye değildir.
- TÜM adlar LATİN alfabesiyle yazılır: Kiril/Japonca/Arapça metni Latin'e translitere et,
  orijinal yazıyı EKLEME (parantezle bile). Aksanlı harf kullanma: PRÉJEAN değil PREJEAN.
- Giriş ve kapanış aynı alanda farklı isim veriyorsa alanı BOŞ bırak + "celiski:<alan>"."""


def anahtar() -> str:
    for satir in (KOK / "council_mcp" / ".env").read_text(encoding="utf-8").splitlines():
        if satir.startswith("NVIDIA_API_KEY="):
            return satir.split("=", 1)[1].strip()
    raise RuntimeError("NVIDIA_API_KEY yok")


KEY = anahtar()


def nim(model: str, messages: list, max_tokens: int = 3000, deneme: int = 6) -> str:
    veri = json.dumps({"model": model, "messages": messages, "temperature": 0.0,
                       "max_tokens": max_tokens}).encode()
    for i in range(deneme):
        try:
            req = urllib.request.Request(URL, data=veri, headers={
                "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read())
            return d["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < deneme - 1:
                time.sleep(min(60, 2 ** i * 3 + random.random() * 2))
                continue
            raise
        except Exception:
            if i < deneme - 1:
                time.sleep(5)
                continue
            raise
    return ""


def img_url(p: Path) -> dict:
    b = base64.b64encode(p.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b}"}}


def json_ayikla(s: str) -> dict:
    m = re.search(r"\{.*\}", s, re.DOTALL)
    return json.loads(m.group(0)) if m else {}


def transkript(kareler: list[Path], etiket: str) -> str:
    parcalar = []
    for i in range(0, len(kareler), GRUP):
        grup = kareler[i:i + GRUP]
        icerik = [{"type": "text", "text":
                   f"Bu {len(grup)} kare bir filmin {etiket} bölümünden. Kare adları sırayla: "
                   + ", ".join(k.name for k in grup) +
                   ". HER kare için 'KARE <ad>:' başlığıyla ekranda görünen TÜM jenerik/yazı "
                   "metnini BİREBİR yaz (satır düzenini koru). Yazı yoksa veya sadece film "
                   "sahnesiyse 'YOK' yaz. Ekran altındaki sarı altyazılar diyalogdur — "
                   "'ALTYAZI: <metin>' diye ayrı işaretle. Yorum ekleme."}]
        icerik += [img_url(k) for k in grup]
        try:
            parcalar.append(nim(VLM, [{"role": "user", "content": icerik}]))
        except Exception:
            parcalar.append(nim(VLM_YEDEK, [{"role": "user", "content": icerik}]))
    return "\n\n".join(parcalar)


def okuma_kur(film: str, yil: str, t_giris: str, t_kapanis: str, n_g: int, n_k: int) -> dict:
    prompt = (f"Bir filmin jenerik karelerinin transkriptleri aşağıda. Film dizin adı: {film} "
              f"(yıl ~{yil}).\n\n=== GİRİŞ ({n_g} kare) ===\n{t_giris}\n\n"
              f"=== KAPANIŞ ({n_k} kare) ===\n{t_kapanis}\n\n{KURALLAR}\n\n"
              f"SADECE şu şemada geçerli JSON döndür (başka metin yazma):\n{OKUMA_SEMA}")
    try:
        s = nim(LLM, [{"role": "user", "content": prompt}], 2500)
    except Exception:
        s = nim(LLM_YEDEK, [{"role": "user", "content": prompt}], 2500)
    o = json_ayikla(s)
    o.setdefault("bayraklar", []).append("kaynak:nim")
    o["okunan_kare_sayisi"] = {"giris": n_g, "kapanis": n_k}
    return o


def zengin_kur(baslik: str, yil: str, okuma: dict) -> dict:
    kunye_oz = json.dumps({k: okuma.get(k) for k in
                           ("yonetmen", "yapimci", "oyuncular", "orijinal_ad",
                            "film_baslik_karti", "diger_kunye")}, ensure_ascii=False)
    prompt = (f"TRT arşiv filmi: Türkçe başlık '{baslik}', yıl ~{yil}. Jenerikten okunan "
              f"künye: {kunye_oz}\n\nBu filmi kimliklendir (künye+başlık+yıl kanıtıyla) ve "
              "şu JSON'u döndür:\n"
              '{"kimlik":"filmin uluslararası adı ve yılı", "kimlik_guven":"yuksek|orta|dusuk",'
              ' "kimlik_gerekce":"1 cümle", "orijinal_ad":"", "tur":"tek kelime Türkçe tür",'
              ' "ozet":"", "yonetmen_bilgi":[""], "yapimci_bilgi":[""], "oyuncular_bilgi":[""]}\n\n'
              "GÖREV: Bu bir TRT arşiv filmi; büyük olasılıkla bilinen bir yapım. Başlık+yıl+"
              "kadro kanıtıyla filmi KESİN kimliklendir. Kimliklendirdiğinde (yuksek/orta):\n"
              "- yonetmen_bilgi: gerçek yönetmen(ler) — KİŞİ adı.\n"
              "- yapimci_bilgi: gerçek yapımcı KİŞİ(ler) — ŞİRKET ADI YAZMA.\n"
              "- oyuncular_bilgi: filmin BAŞROL/önemli 6-8 oyuncusu (billing sırası). ZORUNLU — "
              "bilinen filmde bunu MUTLAKA doldur, boş bırakma.\n"
              "- ozet: 3-4 tam cümle, 40-55 kelime, TEK paragraf. Konuyu DOĞRUDAN anlat ve "
              "filmin GERÇEK SONUNU açıkça söyle (kim kazandı/öldü/kavuştu — spoiler serbest). "
              "Muğlak/dolgu cümle YASAK ('ilişkileri değişir', 'belirsizdir' gibi). "
              "'anlatılır/konu alır' kalıbıyla değil, olayları GEÇMİŞ ZAMAN kişilerle anlat.\n"
              "SADECE gerçekten emin olduğun filmi doldur; kimlikten emin değilsen TÜM alanları "
              "boş bırak ve kimlik_guven=dusuk yap. UYDURMA MUTLAK YASAK.\n"
              "YAZIM: Yabancı özel adları özet+listede TAMAMEN BÜYÜK ASCII yaz (RIPPER, JULIET — "
              "Türkçe İ/aksan KULLANMA: PREJEAN, MEHRJUI). Türkçe kelimeler normal küçük harf.")
    try:
        s = nim(LLM, [{"role": "user", "content": prompt}], 1500)
    except Exception:
        s = nim(LLM_YEDEK, [{"role": "user", "content": prompt}], 1500)
    return json_ayikla(s)


def isle(d: Path, sadece_zengin: bool, force: bool) -> str:
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    baslik, yil = meta.get("baslik", d.name), d.name[:4]
    ok_j, zg_j = d / "okuma.json", d / "zengin.json"
    try:
        if not sadece_zengin and (force or not ok_j.is_file()):
            g = sorted((d / "okuma_seti_giris").glob("*.png")) if (d / "okuma_seti_giris").is_dir() else []
            k = sorted((d / "okuma_seti").glob("*.png")) if (d / "okuma_seti").is_dir() else []
            if not g and not k:
                return "kare_yok"
            t_g = transkript(g, "GİRİŞ (ilk 4 dakika)") if g else "(giriş seti yok)"
            t_k = transkript(k, "KAPANIŞ (son dakikalar)") if k else "(kapanış seti yok)"
            (d / "nim_ham").mkdir(exist_ok=True)
            (d / "nim_ham" / "transkript.txt").write_text(
                f"=== GIRIS ===\n{t_g}\n\n=== KAPANIS ===\n{t_k}", encoding="utf-8")
            o = okuma_kur(d.name, yil, t_g, t_k, len(g), len(k))
            if not o.get("yonetmen") and not o.get("oyuncular") and not o.get("yapimci"):
                o.setdefault("bayraklar", []).append("nim_bos_kunye")
            ok_j.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
        # zengin: yoksa VEYA eski-stil ise (oyuncular_bilgi anahtarı yoksa) yenile.
        eski_zengin = False
        if zg_j.is_file():
            try:
                eski_zengin = "oyuncular_bilgi" not in json.loads(zg_j.read_text(encoding="utf-8"))
            except Exception:
                eski_zengin = True
        if ok_j.is_file() and (force or not zg_j.is_file() or eski_zengin):
            o = json.loads(ok_j.read_text(encoding="utf-8"))
            z = zengin_kur(baslik, yil, o)
            if z:
                zg_j.write_text(json.dumps(z, ensure_ascii=False, indent=1), encoding="utf-8")
        return "ok"
    except Exception as e:  # noqa: BLE001
        return f"HATA:{type(e).__name__}:{str(e)[:120]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--films")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sadece-zengin", action="store_true")
    a = ap.parse_args()

    def zengin_eski(d: Path) -> bool:
        zj = d / "zengin.json"
        if not zj.is_file():
            return True
        try:
            return "oyuncular_bilgi" not in json.loads(zj.read_text(encoding="utf-8"))
        except Exception:
            return True

    dizinler = sorted(d for d in HASAT.iterdir() if d.is_dir() and (d / "meta.json").is_file())
    if a.sadece_zengin:
        dizinler = [d for d in dizinler if (d / "okuma.json").is_file()
                    and (a.force or zengin_eski(d))]
    else:                               # okuma yok VEYA zengin eski-stil (oyuncular_bilgi'siz)
        dizinler = [d for d in dizinler if a.force or not (d / "okuma.json").is_file()
                    or zengin_eski(d)]
    if a.films:
        keys = [s.strip() for s in a.films.split(",")]
        dizinler = [d for d in dizinler if any(k in d.name for k in keys)]
    if a.limit:
        dizinler = dizinler[:a.limit]

    print(f"{len(dizinler)} film → NIM (VLM={VLM.split('/')[-1]}, LLM={LLM.split('/')[-1]}, "
          f"workers={a.workers})", flush=True)
    t0 = time.time()
    say = {"ok": 0, "hata": 0}
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(isle, d, a.sadece_zengin, a.force): d for d in dizinler}
        for f in cf.as_completed(futs):
            r = f.result()
            if r.startswith("HATA"):
                say["hata"] += 1
                print(f"[HATA] {futs[f].name[:55]} {r}", flush=True)
            else:
                say["ok"] += 1
            n = say["ok"] + say["hata"]
            if n % 25 == 0:
                print(f"  ... {n}/{len(dizinler)} (~{n/max(1e-9,time.time()-t0)*3600:.0f} film/saat)",
                      flush=True)
    print(f"BİTTİ: {say['ok']} ok, {say['hata']} hata, {(time.time()-t0)/60:.1f} dk", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
