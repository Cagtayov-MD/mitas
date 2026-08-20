#!/usr/bin/env python3
"""ESKİ kod referansını ÜRET — kapı bunu kullanır, tarihî JSON'ları değil.

NEDEN: `outputs/olcum_yatagi/.../olcum_kol_frame.json` 2026-07-31'de üretildi.
`e1a201d5` (2026-08-05) `film_esigi`'nin Otsu aramasını YENİDEN YAZDI ("O(n)
optimizasyonu") ve cevabı değiştirdi — eski arama her iki yanda ≥3 eleman
şartıyla kısıtlıydı, yenisi şartsız arayıp ≥3'ü sonradan reddediyor. MOBY DICK'te
eşik 28→13, sayfa 15→165. Tarihî JSON'a karşı ölçmek, taşımayı değil o commit'i
ölçer.

Taşıma kapısı eşyayı eşyayla kıyaslamalı: **kule vs BUGÜNKÜ üretim kodu.**

Koşum (üretimin kendi yorumlayıcısıyla — kulenin venv'iyle DEĞİL):
    /opt/mitas/venvs/ocr/bin/python olcum/referans_uret.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
sys.path.insert(0, str(PROJE / "harness" / "track_kunye"))

YATAK = PROJE / "outputs" / "olcum_yatagi" / "klipler"
CIKTI = Path(__file__).resolve().parent / "referans_eski.json"
# Uretimde Nash'in gercekten okudugu iki yuzey (_pipe_hibrit_okuma.kol_frame):
YUZEYLER = (("cikis", "frames/cikis_jenerik"), ("giris", "frames/giris"))


def main() -> int:
    import pilot_hat as ph
    if not YATAK.is_dir():
        print(f"HATA: olcum yatagi yok: {YATAK}", file=sys.stderr)
        return 2
    kayit: dict = {"uretildi": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "yorumlayici": sys.version.split()[0],
                   "kaynak": "harness/track_kunye/pilot_hat.havuz_derle_dizin",
                   "filmler": {}}
    for p in sorted(x for x in YATAK.iterdir() if x.is_dir()):
        film: dict = {}
        for ad, alt in YUZEYLER:
            d = p / alt
            if not d.is_dir() or not any(d.glob("*.png")):
                film[ad] = {"yok": True}
                continue
            t0 = time.time()
            secim, ist = ph.havuz_derle_dizin(d, "*.png")
            film[ad] = {"havuz": ist, "secim_n": len(secim),
                        "sure_sn": round(time.time() - t0, 1)}
            print(f"  {p.name[:40]:40s} {ad:5s} {json.dumps(ist)}", flush=True)
        kayit["filmler"][p.name] = film
    CIKTI.write_text(json.dumps(kayit, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"\nyazildi: {CIKTI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
