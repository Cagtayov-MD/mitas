#!/usr/bin/env python3
"""F3c NCC-hiza esiginin GERCEK veriyle kalibrasyon kaniti (docs/MITAS_Master_Dup_
Kok_Sebep_Plani_v1.md "F3c KARARI" -- db_compose_master.py F3C_NCC_GATE yorumu).

25 rastgele aday filmde (data/master_ex_modfix_f3b_only -- F3c'den ONCEKI, hicbir
static_page dusurulmemis backup) statik+slit ciftini cikarir, NCC gate GECICI OLARAK
devre disi (0.0) birakilarak hiza+token kontrolu calistirilir, sonuclar (best_ncc,
match_ratio, tokens) yazdirilir. BULGU (bu kosunun sonucu, F3C_NCC_GATE=0.3'un
gerekcesi): yasli-adamlar-toplulugu token orani TAM 1.0 (6/6 isim) GERCEK dikis-
tekrari iken NCC yalniz 0.4811 -- 0.85 gibi siki bir NCC esigi bunu KACIRIRDI.
Ayrica NCC ile token-orani ZAYIF KORELE (birdy/stadin-cilginlari/tas-devri NCC=
0.88-0.91 AMA oran=0.0-0.54) -- NCC gercek karar mercii degil, token orani asil
kaniftir. Rastgele orneklem: random.seed(20260726), 195-aday havuzundan 25 film
(bkz. harness/master_dup/dikis_tekrar_tara.py --liste-yaz).

Calistir: /opt/mitas/venvs/ocr/bin/python harness/master_dup/kalibrasyon_f3c_ncc.py
"""
import argparse
import importlib.util
import json
import os
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("MITAS_PROJECT_ROOT", str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
spec = importlib.util.spec_from_file_location("mon_kalib", str(PROJECT_ROOT / "OCR-worktree" / "master_png_monitor.py"))
mon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mon
spec.loader.exec_module(mon)
dc = mon.dc

import dikis_tekrar_tara as dt

KOK = PROJECT_ROOT / "data" / "master_ex_modfix_f3b_only"

# Bu kosunun uretttigi ORIJINAL 25-film ornegi (random.seed(20260726), 195-aday
# havuzundan) -- tekrarlanabilirlik icin sabit; --n/--liste ile ozellestirilebilir.
ORNEK_25 = [
    "birdy", "kuzeyde", "van-gogh-sonsuzlugun-kapisinda", "kara-kedi", "tas-devri",
    "ekimin-ilk-pazartesisi", "stadin-cilginlari", "veronica-guerin", "demiryolu-cocuklari",
    "uzayli-kuklalar", "gercek-yalanlar", "babam-ve-ben", "new-york-new-york", "kanli-kita",
    "benimle-dans-et", "ozgurluge-kacis", "canim-kardesim-benim-uzaylilar-mi-gelmis",
    "komiser-cordier-ucuncu-yildiz", "sessiz-dokunus", "at-delisi", "philedelphia-gosterisi",
    "bekarliga-veda", "cinayet-yardimcisi", "yasli-adamlar-toplulugu", "baba-2",
]

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--kok", default=str(KOK), help="masters kok (varsayilan: master_ex_modfix_f3b_only)")
ap.add_argument("--n", type=int, default=None, help="ORNEK_25 yerine havuzdan rastgele N film (yeniden-kalibrasyon icin)")
ap.add_argument("--json-cikti", default=None)
args = ap.parse_args()

KOK = Path(args.kok)
if args.n:
    tum_aday = sorted(
        p.name for p in KOK.iterdir()
        if p.is_dir() and not p.name.startswith("_") and dt.tekrar_adaylari(dt._load_json(p / "manifest.json") or {})
    )
    random.seed(20260726)
    sample = random.sample(tum_aday, min(args.n, len(tum_aday)))
else:
    sample = ORNEK_25

sonuclar = []
for slug in sample:
    film_dir = KOK / slug
    manifest = dt._load_json(film_dir / "manifest.json")
    if manifest is None:
        print(f"{slug}: manifest yok")
        continue
    adaylar = dt.tekrar_adaylari(manifest)
    if not adaylar:
        print(f"{slug}: aday yok (beklenmedik)")
        continue
    # ilk adayi al (cogu filmde tek aday var)
    a = adaylar[0]
    png_path = film_dir / "reading_master.png"
    if not png_path.is_file():
        print(f"{slug}: png yok")
        continue
    png = cv2.cvtColor(np.array(Image.open(png_path).convert("RGB")), cv2.COLOR_RGB2BGR)
    # kumulatif y bul (basit -- ilk aday genelde ilk iki blok)
    sep = dc.SEP_PX
    y = 0
    static_y0 = static_y1 = slit_y0 = slit_y1 = None
    kept = [b for b in manifest.get("blocks") or [] if isinstance(b, dict) and b.get("h") is not None and "skip" not in b]
    for i in range(len(kept) - 1):
        b0, b1 = kept[i], kept[i + 1]
        if b0.get("kind") == "static_page" and b1.get("kind") == "scroll_slit":
            # y offsetini yeniden hesapla (kept listesindeki konuma gore)
            yy = 0
            for j in range(i):
                yy += kept[j]["h"] + sep
            static_y0, static_y1 = yy, yy + b0["h"]
            slit_y0 = static_y1 + sep
            slit_y1 = slit_y0 + b1["h"]
            break
    if static_y0 is None:
        print(f"{slug}: aday bulunamadi (kumulatif)")
        continue
    static_crop = png[static_y0:static_y1, :]
    slit_crop = png[slit_y0:slit_y1, :]
    static_gray = cv2.cvtColor(static_crop, cv2.COLOR_BGR2GRAY)
    slit_gray = cv2.cvtColor(slit_crop, cv2.COLOR_BGR2GRAY)

    # p.h tahmini icin native frame yuksekligi -- Ex_Frame kaynaginda degisken;
    # burada kalibrasyon amacli composer'in kendi guvenli varsayilani kullanilir
    # (production'da compose_reading_runaware HER ZAMAN gercek p.h'yi gecirir).
    hiza = dc._f3c_align_static_in_slit(static_gray, slit_gray, frame_h=dc.F3C_SEARCH_H_FALLBACK, ncc_gate=0.0)
    if hiza is None:
        print(f"{slug}: static_h={b0['h']:4d} hiza YOK (arama alani cok kucuk?)")
        continue
    best_y, best_ncc = hiza
    line_h = dc._atlas_line_height_estimate(static_gray)
    crop_y1 = min(slit_gray.shape[0], best_y + static_gray.shape[0] + line_h)
    slit_aligned = slit_gray[best_y:crop_y1, :]
    static_tokens = dc._f3c_seam_tokens(static_gray)
    slit_tokens = dc._f3c_seam_tokens(slit_aligned)
    ratio = len(static_tokens & slit_tokens) / len(static_tokens) if static_tokens else None
    print(f"{slug:45s} static_h={b0['h']:4d} best_y={best_y:4d} ncc={best_ncc:.4f} "
          f"ratio={ratio if ratio is None else round(ratio,3)} static_tok={sorted(static_tokens)[:6]} "
          f"matched={sorted(static_tokens & slit_tokens)[:6]}")
    sonuclar.append({
        "slug": slug, "static_h": b0["h"], "best_y": best_y, "ncc": best_ncc,
        "ratio": ratio, "static_tokens": sorted(static_tokens), "slit_tokens": sorted(slit_tokens),
    })

if args.json_cikti:
    json.dump(sonuclar, open(args.json_cikti, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"-> {args.json_cikti}")
print(f"\n-> {len(sonuclar)} film islendi")
