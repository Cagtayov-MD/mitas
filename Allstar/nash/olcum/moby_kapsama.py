#!/usr/bin/env python3
"""MOBY DICK kapsama sondajı — yeni eşik ESKİNİN OKUDUĞU kareleri düşürüyor mu,
yoksa yerine yakın-eşini mi koyuyor?

"Kare düştü" tek başına kayıp DEĞİLDİR: aynı kartın komşu karesi seçildiyse
içerik durur. Ölçülen: düşen her karenin, YENİ seçimde kalan en yakın karesine
imza (Hamming) mesafesi. Mesafe ~0 ise içerik duruyor; mesafe eski eşiğin (28)
üstündeyse GERÇEKTEN farklı bir kart okunmadan gitti.

Tarihî `olcum_kol_frame.json` düşen karelerin ESKİ koşuda ürettiği SATIRLARI de
tutuyor — kaybın metin karşılığı böyle görünür.

    /opt/mitas/venvs/ocr/bin/python Allstar/nash/olcum/moby_kapsama.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
sys.path.insert(0, str(PROJE / "harness" / "track_kunye"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cv2  # noqa: E402
import steve_nash as sn  # noqa: E402
from otsu_ayrisma import havuz_sabit_esikle, tavan_uygula  # noqa: E402

FILM = "2011-2205-1-0000-50-1 MOBY DICK 1"
KLIP = PROJE / "outputs" / "olcum_yatagi" / "klipler" / FILM
TARIHI = KLIP / "olcum_kol_frame.json"
CIKTI = Path(__file__).resolve().parent / "moby_kapsama.json"


def main() -> int:
    cfg = sn.HavuzConfig()
    d = KLIP / "frames" / "cikis_jenerik"
    yollar = sorted(d.glob("*.png"))
    griler, gecerli = [], []
    for p in yollar:
        im = cv2.imread(str(p))
        if im is None:
            continue
        griler.append(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
        gecerli.append(p)
    ad2idx = {p.name: i for i, p in enumerate(gecerli)}

    temiz = sn.temporal_median(griler, cfg.medyan_pencere)
    imzalar = [sn.imza(g, cfg.imza_boyut) for g in temiz]

    secimler = {}
    for etiket, e in (("eski", 28), ("yeni", 13)):
        sonuc, ekler = havuz_sabit_esikle(griler, e)
        adlar = [gecerli[i].name for i in sorted(set(sonuc.sayfalar) | set(ekler))]
        secimler[etiket] = {"tam": adlar, "tavan": tavan_uygula(adlar, 100)}

    # Tarihî koşunun GERÇEKTEN okuduğu kareler (26) — kıyasın sol tarafı bu.
    th = json.loads(TARIHI.read_text(encoding="utf-8"))
    tarihi_kayit: dict[str, list[str]] = {}
    for r in th["kayitlar"]:
        tarihi_kayit.setdefault(r["kaynak"], []).append(r["text"])
    okunan_eski = sorted(tarihi_kayit)

    yeni_tavan = secimler["yeni"]["tavan"]
    yeni_idx = sorted(ad2idx[a] for a in yeni_tavan if a in ad2idx)

    rapor = {"film": FILM,
             "eski_secim_n": len(secimler["eski"]["tam"]),
             "yeni_secim_n": len(secimler["yeni"]["tam"]),
             "yeni_tavan_sonrasi_n": len(yeni_tavan),
             "tarihi_okunan_n": len(okunan_eski),
             "tarihi_satir_n": th["satir_n"],
             "dusenler": []}

    for ad in okunan_eski:
        if ad in set(yeni_tavan):
            continue
        i = ad2idx.get(ad)
        if i is None:
            continue
        # YENİ seçimde kalan en yakın kare (imza mesafesine göre)
        en = min(yeni_idx, key=lambda j: sn.hamming(imzalar[i], imzalar[j]))
        mesafe = sn.hamming(imzalar[i], imzalar[en])
        satirlar = tarihi_kayit[ad]
        rapor["dusenler"].append({
            "kare": ad, "idx": i, "satir_n": len(satirlar),
            "en_yakin_kalan": gecerli[en].name, "en_yakin_idx": en,
            "imza_mesafe": mesafe,
            "icerik_duruyor_mu": mesafe <= 5,
            "gercekten_farkli_kart": mesafe > 28,
            "satirlar": satirlar[:12],
        })

    rapor["dusen_n"] = len(rapor["dusenler"])
    rapor["dusen_satir_toplam"] = sum(x["satir_n"] for x in rapor["dusenler"])
    rapor["icerigi_duran"] = sum(1 for x in rapor["dusenler"] if x["icerik_duruyor_mu"])
    rapor["gercek_kayip"] = sum(1 for x in rapor["dusenler"] if x["gercekten_farkli_kart"])

    CIKTI.write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"eski secim={rapor['eski_secim_n']}  yeni secim={rapor['yeni_secim_n']}"
          f" → tavan sonrasi {rapor['yeni_tavan_sonrasi_n']}")
    print(f"tarihi koşuda OKUNAN kare={rapor['tarihi_okunan_n']}, "
          f"satir={rapor['tarihi_satir_n']}")
    print(f"\nYENİ seçimde bulunmayan okunmuş kare: {rapor['dusen_n']}"
          f"  (toplam {rapor['dusen_satir_toplam']} satır taşıyorlardı)")
    print(f"  içeriği yakın-eşinde duran (mesafe<=5): {rapor['icerigi_duran']}")
    print(f"  GERÇEKTEN farklı kart (mesafe>28)     : {rapor['gercek_kayip']}\n")
    for x in rapor["dusenler"]:
        bayrak = "OK " if x["icerik_duruyor_mu"] else ("KAYIP" if x["gercekten_farkli_kart"] else "?  ")
        print(f"  {bayrak} {x['kare']} (idx {x['idx']:3d}) → en yakın kalan "
              f"{x['en_yakin_kalan']} mesafe={x['imza_mesafe']:3d}  "
              f"{x['satir_n']} satır")
        for s in x["satirlar"][:3]:
            print(f"        | {s[:70]}")
    print(f"\nyazildi: {CIKTI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
