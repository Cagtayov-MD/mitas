#!/usr/bin/env python3
"""FÜZYON DENEYİ — 18 px tavanı gerçek mi, zamanı piksele çevirebilir miyiz?

SORU (Çağatay onayı, 2026-07-31): jenerik metni bu yatakta medyan 18 px SATIR
yüksekliğinde (harf gövdesi ~10-12 px). Modern OCR 40-60 px'de eğitiliyor.
Modeller birbirine yakın çıkıyor (297 vs 283 = %5) çünkü darboğaz modelde değil,
PİKSELDE olabilir. Ama statik kart onlarca karede SABİT duruyor — yani bilgi
tek karede yok ama ZAMANDA var. Hizalayıp birleştirmek çözünürlük kazandırır mı?

Kazandırıyorsa: yol füzyon/superresolution, model tartışması ikincil.
Kazandırmıyorsa: 18 px bir tavan, bunu bilerek plan yapılır.

DÖRT VARYANT, AYNI MODEL, AYNI KART:
  (a) tek   — segmentin orta karesi, olduğu gibi
  (b) ort   — N kare hizalı ortalama (gürültü azaltma, orijinal ölçek)
  (c) x2    — tek kare 2× büyütme (yeni bilgi YOK, yalnız enterpolasyon)
  (d) ort2x — 2× uzayda hizalı biriktirme  ← GERÇEK ADAY TEKNİK

(c) kontrol grubudur: eğer (c) de (a) kadar iyileşiyorsa kazanç füzyondan değil
sadece modelin büyük girdiyi sevmesinden geliyor demektir. (d)'nin (c)'yi
geçmesi gerekir ki füzyonun gerçek bilgi kattığı söylenebilsin.

KULLANIM:
  python3 scripts/olcum_fuzyon_deneyi.py --film "1955-0007-1-0000-00-1 BOZGUNCULAR"
  python3 scripts/olcum_fuzyon_deneyi.py --film "..." --segment 2
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
KLIPLER = PROJE / "outputs" / "olcum_yatagi" / "klipler"
OLLAMA = (os.environ.get("MITAS_OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("FUZYON_MODEL", "deepseek-ocr:latest")
ISTEM = "Free OCR."


def oku(png: Path, timeout: int = 300) -> tuple[list[str], float]:
    gov = {"model": MODEL, "prompt": ISTEM, "stream": False,
           "images": [base64.b64encode(png.read_bytes()).decode()],
           "options": {"temperature": 0.0, "num_predict": 2048, "num_ctx": 8192}}
    req = urllib.request.Request(f"{OLLAMA}/api/generate",
                                 data=json.dumps(gov).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        cevap = json.loads(r.read()).get("response", "") or ""
    sure = round(time.perf_counter() - t0, 2)
    satirlar = []
    for ln in cevap.splitlines():
        ln = ln.strip().strip("`").lstrip("#").strip().strip("*").strip()
        if len(ln) >= 2:
            satirlar.append(ln)
    return satirlar, sure


def segment_kareleri(clip: Path, hedef_segment: int | None) -> list[Path]:
    """Manifest'in segment_kareler alanından EN ÇOK KARELİ segmenti seç."""
    man = json.loads((clip / "reading_master_runaware_manifest.json")
                     .read_text(encoding="utf-8"))
    havuz = sorted((clip / "frames" / "cikis_jenerik").glob("*.png"))
    segler = man.get("segment_kareler") or []
    # DİKKAT: segment_kareler, segment BAŞLANGIÇ indekslerini taşıyor
    # (BOZGUNCULAR: [[0],[4],[16],[33],[34]]), segment İÇERİKLERİNİ değil.
    # Bir segment, kendi başlangıcından SONRAKİ başlangıca kadar sürer.
    # (İlk denemede bunu içerik sanıp 1 karelik "segment" almıştım.)
    baslar = []
    for g in segler:
        for x in (g if isinstance(g, list) else [g]):
            try:
                v = int(x)
            except (TypeError, ValueError):
                continue
            if 0 <= v < len(havuz):
                baslar.append(v)
    baslar = sorted(set(baslar))
    if not baslar:
        return []
    araliklar = [(baslar[i], (baslar[i + 1] if i + 1 < len(baslar) else len(havuz)))
                 for i in range(len(baslar))]
    if hedef_segment is not None and 0 <= hedef_segment < len(araliklar):
        a, b = araliklar[hedef_segment]
    else:
        if hedef_segment is not None:
            print(f"  segment {hedef_segment} yok; en kalabalık seçiliyor")
        a, b = max(araliklar, key=lambda t: t[1] - t[0])
    print(f"    segment aralığı: havuz[{a}:{b}] = {b - a} kare "
          f"(tüm segmentler: {[t[1]-t[0] for t in araliklar]})")
    return havuz[a:b]


def hizali_biriktir(kareler: list[Path], olcek: int = 1) -> np.ndarray:
    """Sub-piksel hizalayıp biriktir. olcek=2 → 2× uzayda birikim (asıl teknik).

    Duraksama karelerinde içerik SABİT ama telesine/analog aktarımda sub-piksel
    titreme ve gürültü var. Titreme varsa 2× uzayda hizalı birikim GERÇEK
    çözünürlük kazandırır (klasik çok-kareli superresolution); yoksa yalnız
    gürültü azalır — ikisi de değerli ama farklı şeyler.
    """
    ref = cv2.imread(str(kareler[0]))
    if ref is None:
        raise RuntimeError(f"okunamadı: {kareler[0]}")
    h, w = ref.shape[:2]
    H, W = h * olcek, w * olcek
    ref_g = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY).astype(np.float32)
    toplam = np.zeros((H, W, 3), np.float64)
    n = 0
    kaymalar = []
    for p in kareler:
        im = cv2.imread(str(p))
        if im is None or im.shape[:2] != (h, w):
            continue
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
        try:
            (dx, dy), _ = cv2.phaseCorrelate(ref_g, g)
        except Exception:
            dx, dy = 0.0, 0.0
        kaymalar.append((dx, dy))
        buyuk = cv2.resize(im, (W, H), interpolation=cv2.INTER_CUBIC) \
            if olcek > 1 else im.copy()
        M = np.float32([[1, 0, -dx * olcek], [0, 1, -dy * olcek]])
        hizali = cv2.warpAffine(buyuk, M, (W, H),
                                flags=cv2.INTER_CUBIC,
                                borderMode=cv2.BORDER_REPLICATE)
        toplam += hizali.astype(np.float64)
        n += 1
    if not n:
        raise RuntimeError("hiç kare birikmedi")
    ort = (toplam / n).clip(0, 255).astype(np.uint8)
    # Titreme gerçekten var mı? Yoksa (d) yalnız gürültü azaltıyor demektir.
    mags = [abs(dx) + abs(dy) for dx, dy in kaymalar]
    return ort, {"kare": n,
                 "kayma_medyan_px": round(float(np.median(mags)), 3),
                 "kayma_maks_px": round(float(np.max(mags)), 3)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", required=True)
    ap.add_argument("--segment", type=int, default=None)
    ap.add_argument("--maks-kare", type=int, default=24)
    a = ap.parse_args()

    clip = KLIPLER / a.film
    if not clip.is_dir():
        adaylar = list(KLIPLER.glob(f"*{a.film}*"))
        if not adaylar:
            print(f"HATA: klip yok: {a.film}")
            return 2
        clip = adaylar[0]

    out = clip / "fuzyon_deneyi"
    out.mkdir(parents=True, exist_ok=True)
    kareler = segment_kareleri(clip, a.segment)
    if len(kareler) < 3:
        print(f"HATA: segmentte yeterli kare yok ({len(kareler)})")
        return 3
    kareler = kareler[:a.maks_kare]

    ref = cv2.imread(str(kareler[0]))
    print(f"=== FÜZYON DENEYİ · {clip.name} ===")
    print(f"    segment karesi: {len(kareler)} kare, {ref.shape[1]}x{ref.shape[0]}")
    print(f"    {kareler[0].name} … {kareler[-1].name}")
    print(f"    model: {MODEL}")

    orta = kareler[len(kareler) // 2]

    # (a) tek kare
    pa = out / "a_tek.png"
    cv2.imwrite(str(pa), cv2.imread(str(orta)))
    # (b) hizalı ortalama, orijinal ölçek
    ob, ib = hizali_biriktir(kareler, olcek=1)
    pb = out / "b_ortalama.png"
    cv2.imwrite(str(pb), ob)
    # (c) tek kare 2× — KONTROL GRUBU (yeni bilgi yok)
    pc = out / "c_x2.png"
    tek = cv2.imread(str(orta))
    cv2.imwrite(str(pc), cv2.resize(tek, (tek.shape[1] * 2, tek.shape[0] * 2),
                                    interpolation=cv2.INTER_CUBIC))
    # (d) 2× uzayda hizalı birikim — ASIL ADAY
    od, idd = hizali_biriktir(kareler, olcek=2)
    pd = out / "d_ortalama_x2.png"
    cv2.imwrite(str(pd), od)

    print(f"    sub-piksel titreme: medyan {ib['kayma_medyan_px']} px, "
          f"maks {ib['kayma_maks_px']} px  ({ib['kare']} kare birikti)")
    if ib["kayma_medyan_px"] < 0.05:
        print("    ⚠ titreme ~0 → (d) gerçek superresolution DEĞİL, yalnız gürültü azaltma")

    sonuc = {}
    for ad, p in (("a_tek", pa), ("b_ortalama", pb), ("c_x2", pc), ("d_ortalama_x2", pd)):
        im = cv2.imread(str(p))
        print(f"\n--- ({ad}) {im.shape[1]}x{im.shape[0]} ---", flush=True)
        try:
            satirlar, sure = oku(p)
        except Exception as e:  # noqa: BLE001
            print(f"    HATA: {type(e).__name__}: {e}")
            sonuc[ad] = {"hata": str(e)[:200]}
            continue
        kar = sum(len(s) for s in satirlar)
        print(f"    {len(satirlar)} satır, {kar} karakter, {sure} sn")
        for s in satirlar[:14]:
            print(f"      | {s}")
        if len(satirlar) > 14:
            print(f"      | … +{len(satirlar) - 14} satır")
        sonuc[ad] = {"satir_n": len(satirlar), "karakter_n": kar,
                     "sure_sn": sure, "boyut": [im.shape[1], im.shape[0]],
                     "satirlar": satirlar}

    (out / "sonuc.json").write_text(json.dumps(
        {"film": clip.name, "kare_n": len(kareler), "titreme": ib,
         "titreme_x2": idd, "model": MODEL, "varyantlar": sonuc},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n=== KIYAS ===")
    print(f"{'varyant':<16}{'satır':>7}{'karakter':>10}{'sn':>7}")
    for ad in ("a_tek", "b_ortalama", "c_x2", "d_ortalama_x2"):
        r = sonuc.get(ad) or {}
        if "hata" in r:
            print(f"{ad:<16}{'HATA':>7}")
            continue
        print(f"{ad:<16}{r.get('satir_n',0):>7}{r.get('karakter_n',0):>10}"
              f"{r.get('sure_sn',0):>7.1f}")
    print(f"\n→ {out}")
    print("  YORUM KURALI: (d) > (c) ise füzyon GERÇEK bilgi katıyor.")
    print("               (d) ≈ (c) ise kazanç yalnız büyütmeden, füzyon boşa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
