#!/usr/bin/env python3
"""Terfi edilen kanonik LeBron'u seçilmiş tarihî master'la karşılaştır.

Bu araç emekli ``magic`` modülünü yüklemez. 2026-08-18 seçim koşusunda
üretilmiş master PNG'leri sabit referans kabul eder; aktif ``derleyici`` aynı
karelerden yeniden üretir ve piksel/manifest özet paritesini ölçer.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np


KULE = Path(__file__).resolve().parents[1]
for _p in (KULE / "src", KULE):
    sys.path.insert(0, str(_p))

import derleyici  # noqa: E402
import yukleyici  # noqa: E402


def _yaz_json(yol: Path, veri: object) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(yol.suffix + ".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
    gecici.replace(yol)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--reference", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--devam", action="store_true")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    filmler = sorted(p for p in a.input.iterdir() if p.is_dir())
    sonuclar = []
    for sira, kareler in enumerate(filmler, 1):
        film = kareler.name
        kayit_yolu = a.out / film / "parite.json"
        if a.devam and kayit_yolu.is_file():
            kayit = json.loads(kayit_yolu.read_text(encoding="utf-8"))
            sonuclar.append(kayit)
            print(f"[atla {sira}/{len(filmler)}] {film}", flush=True)
            continue
        t0 = time.monotonic()
        ims, dosya_n = yukleyici.kareleri_yukle(kareler)
        referans_yolu = a.reference / film / "magic" / "master.png"
        referans_ozet_yolu = a.reference / film / "kiyas.json"
        referans = yukleyici.kare_oku(referans_yolu)
        try:
            master, manifest = derleyici.derle(film, ims=ims)
            hata = None
        except Exception as exc:
            master, manifest = None, {}
            hata = f"{type(exc).__name__}: {exc}"
        referans_ozet = {}
        if referans_ozet_yolu.is_file():
            belge = json.loads(referans_ozet_yolu.read_text(encoding="utf-8"))
            referans_ozet = (belge.get("engines") or {}).get("magic") or {}
        ozet_esitligi = {
            alan: manifest.get(alan) == referans_ozet.get(alan)
            for alan in ("durum", "segment", "olcum_yolu", "sinif_sayimi")
            if alan in referans_ozet
        }
        piksel_esit = bool(
            master is not None and referans is not None
            and master.shape == referans.shape
            and np.array_equal(master, referans))
        kayit = {
            "film_id": film,
            "frame_count": len(ims),
            "input_files": dosya_n,
            "durum": "OK" if hata is None else "ARIZA",
            "hata": hata,
            "pixel_identical": piksel_esit,
            "current_shape": list(master.shape) if master is not None else None,
            "reference_shape": (list(referans.shape)
                                if referans is not None else None),
            "manifest_mode": manifest.get("mode"),
            "manifest_summary_equal": ozet_esitligi,
            "manifest": manifest,
            "sure_sn": round(time.monotonic() - t0, 3),
        }
        if master is not None:
            hedef = a.out / film / "lebron" / "master.png"
            hedef.parent.mkdir(parents=True, exist_ok=True)
            yukleyici.yaz(hedef, master)
            kayit["current_master"] = str(hedef.resolve())
        _yaz_json(kayit_yolu, kayit)
        sonuclar.append(kayit)
        print(f"[{sira}/{len(filmler)}] {film}: "
              f"pixel={piksel_esit} mode={manifest.get('mode')} "
              f"sure={kayit['sure_sn']}s", flush=True)

    ozet = {
        "schema": "mitas.lebron-promotion-parity/v1",
        "input_root": str(a.input.resolve()),
        "reference_root": str(a.reference.resolve()),
        "output_root": str(a.out.resolve()),
        "film_count": len(sonuclar),
        "pixel_identical_count": sum(
            bool(x.get("pixel_identical")) for x in sonuclar),
        "lebron_mode_count": sum(
            x.get("manifest_mode") == "lebron" for x in sonuclar),
        "summary_equal_count": sum(
            bool(x.get("manifest_summary_equal"))
            and all(x["manifest_summary_equal"].values()) for x in sonuclar),
        "failed_films": [x["film_id"] for x in sonuclar
                         if not x.get("pixel_identical")],
        "films": sonuclar,
    }
    _yaz_json(a.out / "ozet.json", ozet)
    print(json.dumps({k: v for k, v in ozet.items() if k != "films"},
                     ensure_ascii=False, indent=2))
    derleyici.release_ocr_engine()
    return 0 if ozet["pixel_identical_count"] == len(sonuclar) else 1


if __name__ == "__main__":
    raise SystemExit(main())
