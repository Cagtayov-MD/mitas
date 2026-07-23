#!/usr/bin/env python3
"""v5 üretim izleme — Database'deki jenerik_detection.json'lardan v5 telemetri özeti.

Sürekli-iyileştirme döngüsünün gözü (2026-07-23, Çağatay: "filmleri izleyip sürece
katacağız"): her üretim koşusu manifest'e v5-vs-eski-CV kaydı düşürür; bu araç
birikeni özetler ve İNCELEME ADAYLARINI (büyük ayrışma / kredi_yok / fail-safe
düşüşü) listeler. Salt-okur — hiçbir üretim dosyasına yazmaz.

Kullanım:
  v5_izleme.py                  # özet + inceleme adayları
  v5_izleme.py --esik 40        # ayrışma eşiği (kare, varsayılan 40)
  v5_izleme.py --json ÇIKTI.json
"""
import argparse
import glob
import json
import os
import sys

DB = os.environ.get("MITAS_DB", "/opt/mitas/Database")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esik", type=int, default=40,
                    help="v5 ile eski-CV ayrışma eşiği (kare)")
    ap.add_argument("--json", help="özeti JSON olarak da yaz")
    a = ap.parse_args()

    kayitlar = []
    for p in sorted(glob.glob(f"{DB}/*/frames/jenerik_detection.json")):
        try:
            m = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        film = os.path.basename(os.path.dirname(os.path.dirname(p)))
        kayitlar.append({"film": film, "engine": m.get("engine"),
                         "status": m.get("status"), "start_pos": m.get("start_pos"),
                         "cv_start": m.get("cv_start_pos"),
                         "havuz": m.get("pool_frames"), "ts": m.get("ts")})

    v5li = [k for k in kayitlar if k["engine"] == "v5_onset"]
    eski = [k for k in kayitlar if k["engine"] != "v5_onset"]
    print(f"TOPLAM manifest: {len(kayitlar)}  |  v5_onset: {len(v5li)}  |  eski-motor: {len(eski)}")

    adaylar = []
    for k in v5li:
        if k["start_pos"] is not None and k["cv_start"] is not None:
            fark = int(k["start_pos"]) - int(k["cv_start"])
            if abs(fark) >= a.esik:
                adaylar.append({**k, "sebep": f"ayrışma {fark:+d} kare (v5 vs eski-CV)"})
    for k in eski:
        # bayrak açıkken eski motora düşenler = v5 kredi_yok/hata dedi → ilgi listesi
        adaylar.append({**k, "sebep": f"v5 devre dışı kaldı (engine={k['engine']}, status={k['status']})"})

    if adaylar:
        print(f"\nİNCELEME ADAYLARI ({len(adaylar)}):")
        for k in adaylar:
            print(f"  {k['film'][:52]:<53} start={str(k['start_pos']):>5}  {k['sebep']}")
    else:
        print("\nİnceleme adayı yok — v5 ile eski-CV uyumlu.")

    if a.json:
        json.dump({"toplam": len(kayitlar), "v5": len(v5li), "eski": len(eski),
                   "adaylar": adaylar}, open(a.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"\nJSON yazıldı: {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
