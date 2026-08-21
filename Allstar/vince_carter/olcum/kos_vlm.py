#!/usr/bin/env python3
"""VLM kanalını GERÇEK klip/kare dizini üzerinde koşturan ölçüm CLI'ı (FAZ 2).

Model BİR KEZ yüklenir ve İSTENEN TÜM FAZLARDA kullanılır — 17 GB'ı faz
başına yeniden okumak saçmadır (kanarya ölçümü: soğuk yükleme 8,7 sn).

Kullanım::

    ./venv/bin/python olcum/kos_vlm.py \
        --klip "/yol/dost_eller_40m50s_bitiş.mp4" \
        --film-id dost_eller --faz 0,4 --cikti-dizin olcum/veri/dost_eller

Çıktı (``--cikti-dizin`` altına):
    <film_id>_faz<N>.json   tam sonuç (satırlar + elenen + gruplar + kanıt)
    <film_id>_faz<N>.txt    yalnız satır metinleri, ekran sırasıyla
    <film_id>_ozet.json     fazlar arası karşılaştırma + koşu künyesi
    kareler/                reçete kareleri + kare_manifesti.json (KANIT)

Bu betik PUANLAMA YAPMAZ — GT ile karşılaştırma Faz 3'ün işidir
(``olcum/puan.py`` + birleştirici). Burada yalnız kanalın kendi çıktısı ve
fazlar arası kaba örtüşme raporlanır.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

import yaml

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(KULE / "src"))

from hazirlik import kare_dizininden_hazirla, kayma_hizi, videodan_hazirla  # noqa: E402
from kanal_vlm import Motor, imza, kos  # noqa: E402


def _fazlari_coz(deger: str) -> list[int]:
    fazlar = []
    for parca in str(deger).split(","):
        parca = parca.strip()
        if not parca:
            continue
        try:
            f = int(parca)
        except ValueError:
            raise SystemExit(f"gecersiz faz: {parca!r}")
        if f < 0:
            raise SystemExit("faz negatif olamaz")
        if f not in fazlar:
            fazlar.append(f)
    if not fazlar:
        raise SystemExit("--faz en az bir deger ister")
    return fazlar


def _ortusme(a: list[str], b: list[str]) -> dict:
    """İki fazın satır dizileri ne kadar örtüşüyor? KABA ölçü.

    Asıl hizalama Faz 3'te (BIRLESTIRICI.md adım 2: SequenceMatcher + bulanık
    tur, Türkçe katlamalı). Burada yalnız imza-eşitliği üzerinden çoklu-küme
    kesişimi + dizi benzerlik oranı — "iki faz aynı şeyi mi okudu" sorusunun
    ucuz cevabı.
    """
    ia, ib = [imza(x) for x in a], [imza(x) for x in b]
    sayac: dict[str, int] = {}
    for x in ib:
        sayac[x] = sayac.get(x, 0) + 1
    ortak = 0
    for x in ia:
        if sayac.get(x, 0) > 0:
            sayac[x] -= 1
            ortak += 1
    return {
        "ortak_satir": ortak,
        "yalniz_ilk_fazda": len(ia) - ortak,
        "yalniz_ikinci_fazda": len(ib) - ortak,
        "difflib_orani": round(SequenceMatcher(None, ia, ib).ratio(), 4),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="kos_vlm", description="VLM kanalini gercek veriyle kostur (FAZ 2)")
    kaynak = ap.add_mutually_exclusive_group(required=True)
    kaynak.add_argument("--klip", help="jenerik videosu (mp4/mkv/...)")
    kaynak.add_argument("--kareler", help="hazir kare dizini")
    ap.add_argument("--film-id", required=True)
    ap.add_argument("--faz", default="0,4", help="virgulle ayrilmis faz listesi")
    ap.add_argument("--cikti-dizin", required=True)
    n = ap.parse_args(argv)

    fazlar = _fazlari_coz(n.faz)
    cfg = yaml.safe_load((KULE / "config.yaml").read_text(encoding="utf-8"))
    cikti = Path(n.cikti_dizin)
    cikti.mkdir(parents=True, exist_ok=True)

    # Model yolu config'te kule köküne GÖRELİ (config.yaml notu) — mutlaklaştır.
    m = dict(cfg.get("model", {}))
    m["yol"] = str((KULE / m.get("yol", "model/qwen3-vl-8b")).resolve())
    cfg["model"] = m

    # ── 1) kareler (tek görsel reçete, iki girdi yolu da aynı) ──────────
    kare_dizini = cikti / "kareler"
    t0 = time.time()
    if n.klip:
        manifest = videodan_hazirla(n.klip, kare_dizini, cfg)
    else:
        manifest = kare_dizininden_hazirla(n.kareler, kare_dizini, cfg)
    hazirlik_sn = round(time.time() - t0, 2)
    kayma = kayma_hizi(manifest)
    print(f"[kare] {manifest['kare_sayisi']} kare, {hazirlik_sn} sn, "
          f"kayma={kayma}, fps_varsayimi={manifest['fps_varsayimi']}")

    # ── 2) model BİR KEZ, tüm fazlar o yüklemeyle ───────────────────────
    t0 = time.time()
    motor = Motor(m["yol"], dtype=str(m.get("dtype", "bfloat16")),
                  uretim=cfg.get("uretim", {}),
                  gorsel=cfg.get("gorsel"),
                  aygit=str(m.get("aygit", "cuda:0"))).yukle()
    yukleme_sn = round(time.time() - t0, 2)
    print(f"[model] yuklendi: {yukleme_sn} sn")

    sonuclar: dict[int, dict] = {}
    try:
        for faz in fazlar:
            t0 = time.time()
            sonuc = kos(manifest, kare_dizini, cfg, faz=faz, motor=motor)
            sonuclar[faz] = sonuc
            k = sonuc["kanit"]
            print(f"[faz {faz}] grup={k['grup_sayisi']} satir={k['satir_sayisi']} "
                  f"elenen={k['elenen_sayisi']} {k['elenen_sebep']} "
                  f"dejenerasyon={k['dejenerasyon_satir']} "
                  f"sure={k['sure_sn']}s vram={k['vram_tepe']} "
                  f"retry={k['retry_sayisi']}")

            (cikti / f"{n.film_id}_faz{faz}.json").write_text(
                json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
            (cikti / f"{n.film_id}_faz{faz}.txt").write_text(
                "\n".join(s["metin"] for s in sonuc["satirlar"]) + "\n",
                encoding="utf-8")
            print(f"[faz {faz}] toplam {round(time.time() - t0, 2)} sn")
    finally:
        motor.kapat()

    # ── 3) fazlar arası kaba karşılaştırma ──────────────────────────────
    karsilastirma = {}
    for i, a in enumerate(fazlar):
        for b in fazlar[i + 1:]:
            anahtar = f"faz{a}_faz{b}"
            karsilastirma[anahtar] = _ortusme(
                [s["metin"] for s in sonuclar[a]["satirlar"]],
                [s["metin"] for s in sonuclar[b]["satirlar"]])
            print(f"[karsilastirma] {anahtar}: {karsilastirma[anahtar]}")

    ozet = {
        "film_id": n.film_id,
        "kaynak": n.klip or n.kareler,
        "kare_sayisi": manifest["kare_sayisi"],
        "fps": manifest["fps"],
        "fps_varsayimi": manifest["fps_varsayimi"],
        "kayma_hizi": kayma,
        "hazirlik_sn": hazirlik_sn,
        "model_yukleme_sn": yukleme_sn,
        "fazlar": {str(f): sonuclar[f]["kanit"] for f in fazlar},
        "karsilastirma": karsilastirma,
    }
    (cikti / f"{n.film_id}_ozet.json").write_text(
        json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[bitti] {cikti}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
