#!/usr/bin/env python3
"""ONARIM ADAYI — "hızlı AMA farklı" bir ikilem mi, yoksa yanlış mı kurulmuş?

`e1a201d5` docstring'i HIZ vaat ediyor ("Optimize edilmiş O(n) Otsu"). Ölçülen
yan etki ise CEVAP değişikliği. Bu betik üçüncü bir şıkkı sınar:

    O(n) histogram taraması + ≥3 kuralı ARAMA KISITI olarak (döngü İÇİNDE)

Eğer bu aday, 29 yüzeyin hepsinde ESKİ cevabı verirken YENİ'nin hızını
koruyorsa, ortada bir denge (hız↔doğruluk) YOKTUR — yalnızca kısıtın yanlış
yere konması vardır. O zaman karar "hangisi daha doğru okuyor" sorusuna
bağlı kalmadan verilebilir.

steve_nash.py'ye DOKUNULMAZ; aday burada, ölçüm modülünde durur.

    /opt/mitas/venvs/ocr/bin/python Allstar/nash/olcum/onarim_adayi.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
# Faz 3 sokumu (2026-08-14): harness/track_kunye/steve_nash.py SILINDI.
# Havuz algoritmasinin tek kopyasi artik kulenin icinde; uretim de
# (pilot_hat.havuz_derle_dizin) buraya devrediyor.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cv2  # noqa: E402
import havuz as sn  # noqa: E402  (eski adi: steve_nash)
from otsu_ayrisma import YATAK, YUZEYLER, film_esigi_eski  # noqa: E402

ONBELLEK = Path(__file__).resolve().parent / "farklar_onbellek.json"
CIKTI = Path(__file__).resolve().parent / "onarim_adayi.json"


def film_esigi_onarilmis(farklar: list[int], config: sn.HavuzConfig | None = None) -> int:
    """YENİ'nin O(n) histogram taraması + ESKİ'nin arama kısıtı.

    Tek yapısal fark `if wB < 3 or wF < 3: continue` satırıdır: ≥3 kuralı
    kazananı reddetmek için DEĞİL, dejenere adayı aday olmaktan çıkarmak için
    kullanılır — eski sürümdeki anlamı budur. `t <= tmin` atlaması da eski
    aramanın `range(min+1, max)` sınırını korur.
    """
    cfg = config or sn.HavuzConfig()
    if len(farklar) < 8:
        return cfg.esik_taban
    f = np.array(sorted(farklar), dtype=np.float64)
    hist, _ = np.histogram(f, bins=range(0, 257))
    total = len(f)
    sum_total = float(np.sum(np.arange(256) * hist))
    tmin = int(f.min())

    sumB, wB, max_var = 0.0, 0, -1.0
    en_iyi_esik = None
    for t in range(256):
        wB += int(hist[t])
        if wB == 0:
            continue
        wF = total - wB
        if wF == 0:
            break
        sumB += t * int(hist[t])
        if t <= tmin:            # eski arama t=min'i kapsamıyordu
            continue
        if wB < 3 or wF < 3:     # ← ARAMA KISITI (reddetme değil)
            continue
        mB = sumB / wB
        mF = (sum_total - sumB) / wF
        var = wB * wF * (mB - mF) ** 2
        if var > max_var:
            max_var, en_iyi_esik = var, t

    if en_iyi_esik is None:
        return max(2, int(np.percentile(f, 25)) + 2)
    sol, sag = f[f <= en_iyi_esik], f[f > en_iyi_esik]
    ayrim = (sag.mean() - sol.mean()) / (f.std() + 1e-6)
    if ayrim < cfg.otsu_ayirim_esigi:
        return max(2, int(np.percentile(f, 25)) + 2)
    return int(en_iyi_esik)


def onbellek_kur(cfg: sn.HavuzConfig) -> dict:
    if ONBELLEK.is_file():
        return json.loads(ONBELLEK.read_text(encoding="utf-8"))
    veri: dict = {}
    for p in sorted(x for x in YATAK.iterdir() if x.is_dir()):
        veri[p.name] = {}
        for ad, alt in YUZEYLER:
            d = p / alt
            if not d.is_dir() or not any(d.glob("*.png")):
                continue
            griler = []
            for q in sorted(d.glob("*.png")):
                im = cv2.imread(str(q))
                if im is not None:
                    griler.append(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
            if len(griler) < 2:
                continue
            temiz = sn.temporal_median(griler, cfg.medyan_pencere)
            imz = [sn.imza(g, cfg.imza_boyut) for g in temiz]
            veri[p.name][ad] = [sn.hamming(imz[i], imz[i + 1])
                                for i in range(len(imz) - 1)]
            print(f"  onbellek: {p.name[:38]:38s} {ad}", flush=True)
    ONBELLEK.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
    return veri


def sure(fn, farklar, tekrar: int = 30) -> float:
    t0 = time.perf_counter()
    for _ in range(tekrar):
        fn(farklar)
    return (time.perf_counter() - t0) / tekrar * 1000.0  # ms


def main() -> int:
    cfg = sn.HavuzConfig()
    veri = onbellek_kur(cfg)
    rapor = {"yuzeyler": [], "ozet": {}}
    esitsiz, hizlar = [], []
    print(f"\n{'film / yuzey':46s} {'eski':>5} {'yeni':>5} {'onar':>5}  durum")
    for film, yzl in veri.items():
        for yz, farklar in yzl.items():
            e = film_esigi_eski(farklar, cfg)
            y = sn.film_esigi(farklar, cfg)
            o = film_esigi_onarilmis(farklar, cfg)
            ok = (o == e)
            if not ok:
                esitsiz.append(f"{film}/{yz}")
            ms_e = sure(lambda x: film_esigi_eski(x, cfg), farklar)
            ms_y = sure(lambda x: sn.film_esigi(x, cfg), farklar)
            ms_o = sure(lambda x: film_esigi_onarilmis(x, cfg), farklar)
            hizlar.append((ms_e, ms_y, ms_o))
            rapor["yuzeyler"].append(
                {"film": film, "yuzey": yz, "n": len(farklar), "eski": e,
                 "yeni": y, "onarilmis": o, "onarim_eskiye_esit": ok,
                 "ms_eski": round(ms_e, 3), "ms_yeni": round(ms_y, 3),
                 "ms_onarilmis": round(ms_o, 3)})
            bayrak = "" if ok else "  ◀ ONARIM ESKİDEN FARKLI"
            fark = "  ◀ yeni ayrışıyor" if y != e else ""
            print(f"{(film[:34] + '/' + yz):46s} {e:5d} {y:5d} {o:5d}{bayrak}{fark}")

    te = sum(h[0] for h in hizlar); ty = sum(h[1] for h in hizlar)
    to = sum(h[2] for h in hizlar)
    rapor["ozet"] = {
        "yuzey_n": len(hizlar),
        "onarim_eskiye_esit_mi": not esitsiz,
        "esitsiz": esitsiz,
        "toplam_ms_eski": round(te, 2), "toplam_ms_yeni": round(ty, 2),
        "toplam_ms_onarilmis": round(to, 2),
        "hizlanma_onarim_vs_eski": round(te / to, 1) if to else None,
    }
    CIKTI.write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nonarım 29 yüzeyde eskiye eşit mi: "
          f"{'EVET' if not esitsiz else 'HAYIR → ' + str(esitsiz)}")
    print(f"toplam eşik hesabı: eski {te:.1f} ms | yeni {ty:.1f} ms | "
          f"onarılmış {to:.1f} ms   (onarım eskiden {te/to:.1f}× hızlı)")
    print(f"yazildi: {CIKTI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
