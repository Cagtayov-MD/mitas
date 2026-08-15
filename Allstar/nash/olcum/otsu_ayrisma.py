#!/usr/bin/env python3
"""OTSU AYRIŞMA ÖLÇÜMÜ — `e1a201d5`'in `film_esigi` yeniden yazımı NE değiştirdi?

Bu bir ÖLÇÜM işidir, düzeltme değil. `harness/track_kunye/steve_nash.py`
DEĞİŞTİRİLMEZ: üretim modülü olduğu gibi ithal edilir; sayfa kümesi kıyası için
`film_esigi` YALNIZ süreç-içi maymun-yamalanır (disktekine dokunulmaz).

SORU. `e1a201d5` (2026-08-05) docstring'inde "Optimize edilmiş O(n) Otsu" diyor
— yani hız. Ama cevabı da değiştiriyor:

  ESKİ: aday taraması `t ∈ [min+1, max-1]` VE her iki yanda ≥3 eleman ŞARTIYLA.
        ≥3 bir ARAMA KISITI: dejenere bölmeler aday bile olamaz.
  YENİ: aday taraması `t ∈ [0,256)` şartsız; ≥3 kontrolü aramadan SONRA,
        kazananı REDDETMEK için → reddedilirse p25+2 geri-düşüşü.

Bu ikisi eşdeğer değil. ≥3'ü kısıttan redde taşımak, "en iyi dejenere-olmayan
bölmeyi seç"i "en iyi bölme dejenereyse Otsu'dan vazgeç"e çevirir.

ÖLÇÜLEN. Her film × yüzey için: iki eşik, hangi kapının tetiklediği, ham Otsu
argmax'ı, geri-düşüş değeri; ayrışan yüzeylerde GERÇEK `havuz_derle` iki eşikle
koşturulup seçilen kare kümeleri ve kapsama (yeni ⊇ eski?) çıkarılır.

Koşum (üretimin kendi yorumlayıcısıyla — kulenin venv'iyle DEĞİL):
    /opt/mitas/venvs/ocr/bin/python Allstar/nash/olcum/otsu_ayrisma.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
sys.path.insert(0, str(PROJE / "harness" / "track_kunye"))

import cv2  # noqa: E402
import steve_nash as sn  # noqa: E402

YATAK = PROJE / "outputs" / "olcum_yatagi" / "klipler"
CIKTI = Path(__file__).resolve().parent / "otsu_ayrisma.json"
YUZEYLER = (("cikis", "frames/cikis_jenerik"), ("giris", "frames/giris"))
# scripts/_pipe_hibrit_okuma.py: MAX_SAYFA_CIKIS / MAX_SAYFA_GIRIS
TAVAN = {"cikis": 100, "giris": 100}


# ── ESKİ sürüm: `git show e1a201d5^:harness/track_kunye/messi.py` birebir ────
# Tek uyarlama: sabitler config'ten okunur. Eski dosyada ESIK_TABAN=24 ve
# ayrım kapısı 0.8 sabitti; bugünkü HavuzConfig varsayılanları da 24 ve 0.8 —
# yani kıyas sabit-farkıyla değil, YALNIZ arama mantığıyla ayrışıyor.
def film_esigi_eski(farklar: list[int], config: sn.HavuzConfig | None = None) -> int:
    cfg = config or sn.HavuzConfig()
    if len(farklar) < 8:
        return cfg.esik_taban
    f = np.array(sorted(farklar), dtype=np.float64)
    en_iyi_esik, en_iyi_var = None, -1.0
    for t in range(int(f.min()) + 1, int(f.max())):
        sol, sag = f[f <= t], f[f > t]
        if len(sol) < 3 or len(sag) < 3:
            continue                      # ← ARAMA KISITI
        arasi = len(sol) * len(sag) * (sol.mean() - sag.mean()) ** 2
        if arasi > en_iyi_var:
            en_iyi_var, en_iyi_esik = arasi, t
    if en_iyi_esik is None:
        return max(2, int(np.percentile(f, 25)) + 2)
    sol, sag = f[f <= en_iyi_esik], f[f > en_iyi_esik]
    ayrim = (sag.mean() - sol.mean()) / (f.std() + 1e-6)
    if ayrim < cfg.otsu_ayirim_esigi:
        return max(2, int(np.percentile(f, 25)) + 2)
    return int(en_iyi_esik)


def teshis(farklar: list[int], cfg: sn.HavuzConfig) -> dict:
    """İki sürümün İÇ durumunu çıkar: hangi aday kazandı, hangi kapı tetikledi."""
    f = np.array(sorted(farklar), dtype=np.float64)
    geri_dusus = max(2, int(np.percentile(f, 25)) + 2)
    d: dict = {
        "n": len(farklar), "min": int(f.min()), "max": int(f.max()),
        "p25": float(np.percentile(f, 25)), "medyan": float(np.median(f)),
        "p75": float(np.percentile(f, 75)), "std": float(f.std()),
        "geri_dusus_p25_arti2": geri_dusus,
        "kutu_disi_256_ustu": int((f >= 256).sum()),  # yeni histogramın düşürdüğü
    }

    def puan(t: int) -> tuple[float, int, int]:
        sol, sag = f[f <= t], f[f > t]
        if len(sol) == 0 or len(sag) == 0:
            return -1.0, len(sol), len(sag)
        return (len(sol) * len(sag) * (sol.mean() - sag.mean()) ** 2,
                len(sol), len(sag))

    def ayrim_of(t: int) -> float:
        sol, sag = f[f <= t], f[f > t]
        if len(sol) == 0 or len(sag) == 0:
            return -1.0
        return float((sag.mean() - sol.mean()) / (f.std() + 1e-6))

    # Beraberlikte üretim kodu İLK (en küçük t) adayı tutar (`>` katı) — max()
    # ise en büyük t'yi seçerdi. Sadakat için ilk-maks aranır.
    def ilk_maks(ts):
        en_t, en_var = None, -1.0
        for t in ts:
            v = puan(t)[0]
            if v > en_var:
                en_var, en_t = v, t
        return en_t

    # YENİ: kısıtsız argmax (üretim kodunun histogram taramasıyla aynı sonuç)
    y_t = ilk_maks(range(int(f.min()), int(f.max())))
    if y_t is None:
        y_t = cfg.esik_taban
    y_var, y_sol, y_sag = puan(y_t)
    y_ayrim = ayrim_of(y_t)
    if y_sol < 3 or y_sag < 3:
        y_yol, y_sonuc = "geri_dusus(>=3 kapisi)", geri_dusus
    elif y_ayrim < cfg.otsu_ayirim_esigi:
        y_yol, y_sonuc = "geri_dusus(ayrim kapisi)", geri_dusus
    else:
        y_yol, y_sonuc = "otsu", int(y_t)
    d["yeni"] = {"ham_argmax": int(y_t), "sol_n": int(y_sol), "sag_n": int(y_sag),
                 "ayrim": round(y_ayrim, 3), "yol": y_yol, "sonuc": y_sonuc}

    # ESKİ: kısıtlı argmax (aday kümesi ≥3/≥3 ile daraltılmış)
    e_aday = [t for t in range(int(f.min()) + 1, int(f.max()))
              if puan(t)[1] >= 3 and puan(t)[2] >= 3]
    e_t = ilk_maks(e_aday)
    if e_t is None:
        d["eski"] = {"ham_argmax": None, "yol": "geri_dusus(aday yok)",
                     "sonuc": geri_dusus}
    else:
        e_var, e_sol, e_sag = puan(e_t)
        e_ayrim = ayrim_of(e_t)
        if e_ayrim < cfg.otsu_ayirim_esigi:
            e_yol, e_sonuc = "geri_dusus(ayrim kapisi)", geri_dusus
        else:
            e_yol, e_sonuc = "otsu", int(e_t)
        d["eski"] = {"ham_argmax": int(e_t), "sol_n": int(e_sol),
                     "sag_n": int(e_sag), "ayrim": round(e_ayrim, 3),
                     "yol": e_yol, "sonuc": e_sonuc}
    return d


def havuz_sabit_esikle(griler, sabit: int):
    """GERÇEK üretim `havuz_derle`'sini sabit eşikle koştur (süreç-içi yama)."""
    orij = sn.film_esigi
    sn.film_esigi = lambda farklar, config=sn.HavuzConfig(): int(sabit)
    try:
        sonuc = sn.havuz_derle(griler)
        ekler = sn.ikinci_gecis(griler, sonuc)
    finally:
        sn.film_esigi = orij
    return sonuc, ekler


def tavan_uygula(secim: list, tavan: int) -> list:
    """_pipe_hibrit_okuma.py'deki stride kırpması — birebir."""
    if len(secim) <= tavan:
        return list(secim)
    adim = len(secim) / tavan
    return [secim[int(i * adim)] for i in range(tavan)]


def yuzey_olc(d: Path, yuzey: str, cfg: sn.HavuzConfig) -> dict:
    yollar = sorted(d.glob("*.png"))
    griler, gecerli = [], []
    for p in yollar:
        im = cv2.imread(str(p))
        if im is None:
            continue
        griler.append(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
        gecerli.append(p)
    if len(griler) < 2:
        return {"yok": True, "kare": len(griler)}

    temiz = sn.temporal_median(griler, cfg.medyan_pencere)
    imzalar = [sn.imza(g, cfg.imza_boyut) for g in temiz]
    ardisik = [sn.hamming(imzalar[i], imzalar[i + 1]) for i in range(len(griler) - 1)]

    esik_yeni = sn.film_esigi(ardisik, cfg)
    esik_eski = film_esigi_eski(ardisik, cfg)
    t = teshis(ardisik, cfg)
    # ÖZ-DENETİM: teşhis yeniden-kurulumu GERÇEK fonksiyonların cevabını birebir
    # vermiyorsa teşhis kurgudur. (Kapı eşyayı eşyayla kıyaslamalı — GUNLUK dersi
    # burada kendi aracıma uygulanıyor.)
    t["sadik"] = bool(t["yeni"]["sonuc"] == int(esik_yeni)
                      and t["eski"]["sonuc"] == int(esik_eski))
    out: dict = {"kare": len(griler), "esik_yeni": int(esik_yeni),
                 "esik_eski": int(esik_eski),
                 "ayristi": bool(esik_yeni != esik_eski),
                 "teshis": t}

    if esik_yeni != esik_eski:
        kumeler = {}
        for etiket, e in (("yeni", esik_yeni), ("eski", esik_eski)):
            sonuc, ekler = havuz_sabit_esikle(griler, e)
            idx = sorted(set(sonuc.sayfalar) | set(ekler))
            adlar = [gecerli[i].name for i in idx]
            kumeler[etiket] = {
                "esik": int(e),
                "birikim_esigi": int(sonuc.istatistik.birikim_esigi),
                "grup": int(sonuc.istatistik.grup_sayisi),
                "sayfa": len(sonuc.sayfalar),
                "ikinci_gecis_ek": len(ekler),
                "secim_n": len(adlar),
                "secim": adlar,
                "tavan_sonrasi": tavan_uygula(adlar, TAVAN[yuzey]),
            }
        y, e = set(kumeler["yeni"]["secim"]), set(kumeler["eski"]["secim"])
        yt, et = (set(kumeler["yeni"]["tavan_sonrasi"]),
                  set(kumeler["eski"]["tavan_sonrasi"]))
        out["kume"] = kumeler
        out["kapsama"] = {
            "yeni_ustkume_mu": e.issubset(y),
            "eskide_olup_yenide_olmayan": sorted(e - y),
            "tavan_sonrasi_yeni_ustkume_mu": et.issubset(yt),
            "tavan_sonrasi_kaybolan": sorted(et - yt),
        }
    return out


def main() -> int:
    cfg = sn.HavuzConfig()
    if not YATAK.is_dir():
        print(f"HATA: olcum yatagi yok: {YATAK}", file=sys.stderr)
        return 2
    kayit: dict = {"uretildi": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "yorumlayici": sys.version.split()[0],
                   "eski_kaynak": "e1a201d5^:harness/track_kunye/messi.py",
                   "yeni_kaynak": "harness/track_kunye/steve_nash.py (calisan)",
                   "filmler": {}}
    ayrisan = []
    for p in sorted(x for x in YATAK.iterdir() if x.is_dir()):
        film: dict = {}
        for ad, alt in YUZEYLER:
            d = p / alt
            if not d.is_dir() or not any(d.glob("*.png")):
                film[ad] = {"yok": True}
                continue
            t0 = time.time()
            r = yuzey_olc(d, ad, cfg)
            r["sure_sn"] = round(time.time() - t0, 1)
            film[ad] = r
            if r.get("ayristi"):
                ayrisan.append((p.name, ad, r["esik_eski"], r["esik_yeni"]))
                bayrak = "  ◀ AYRIŞTI"
            else:
                bayrak = ""
            print(f"  {p.name[:38]:38s} {ad:5s} "
                  f"esik eski={r.get('esik_eski')!s:>4} yeni={r.get('esik_yeni')!s:>4}"
                  f"{bayrak}", flush=True)
        kayit["filmler"][p.name] = film
    kayit["ayrisan"] = [{"film": a, "yuzey": b, "eski": c, "yeni": d_}
                        for a, b, c, d_ in ayrisan]
    sadakatsiz = [f"{fn}/{yz}" for fn, yzl in kayit["filmler"].items()
                  for yz, r in yzl.items()
                  if isinstance(r, dict) and "teshis" in r
                  and not r["teshis"]["sadik"]]
    kayit["teshis_sadakatsiz"] = sadakatsiz
    if sadakatsiz:
        print(f"\n!! TEŞHİS SADAKATSİZ ({len(sadakatsiz)}): yeniden-kurulum "
              f"gerçek fonksiyonu vermiyor → teşhis GEÇERSİZ", file=sys.stderr)
        for s in sadakatsiz:
            print(f"   {s}", file=sys.stderr)
    CIKTI.write_text(json.dumps(kayit, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"\nAYRIŞAN yüzey: {len(ayrisan)}")
    for a, b, c, d_ in ayrisan:
        print(f"  {a} / {b}: {c} → {d_}")
    print(f"yazildi: {CIKTI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
