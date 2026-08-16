#!/usr/bin/env python3
"""F3c doğrulama aracı: "dikiş-tekrarı" ADAYLARINI (static_page hemen ardından
scroll_slit -- kept/skip'siz sırayla bitişik) manifest.json'lardan tarar + sayar.

Kullanım:
  dikis_tekrar_tara.py <masters_kok> [--json cikti.json] [--liste-yaz dosya.txt]

Çıktı: {"n_film": .., "aday_film_sayisi": .., "aday_filmler": [...],
        "seam_dup_dusen_film_sayisi": .., "seam_dup_toplam": ..,
        "detay": {film: {"aday_sayisi": N, "seam_dup_dusen": M, "olaylar": [...]}}}

"aday" = kept static_page bloğu, kept-sırada HEMEN ardından kept scroll_slit bloğu
(F3c'den ÖNCEKİ bir manifest'te bu her zaman "henüz test edilmemiş" demektir --
F3c'den SONRAKİ bir manifest'te ise F3c zaten KORUdu demektir, çünkü seam-dup
kararı düşürülenleri blocks'tan ÇIKARIR, "aday" olarak bir daha görünmezler).
"seam_dup_dusen" = manifest'te skip=="seam-dup" olan girdi sayısı (F3c'nin fiilen
düşürdüğü statik sayfalar -- yalnız F3c uygulanmış bir manifest'te > 0 olabilir).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def tekrar_adaylari(manifest: dict) -> list[dict]:
    """kept (skip'siz, h alanlı) blokları sırayla süzer; her ARDIŞIK
    (static_page, scroll_slit) çiftini "aday" olarak döner (index=static'in
    kept-sıradaki konumu, sonraki blok=scroll_slit)."""
    blocks = manifest.get("blocks") or []
    kept = [b for b in blocks if isinstance(b, dict) and b.get("h") is not None and "skip" not in b]
    adaylar = []
    for i in range(len(kept) - 1):
        a, b = kept[i], kept[i + 1]
        if a.get("kind") == "static_page" and b.get("kind") == "scroll_slit":
            adaylar.append({
                "static_h": a.get("h"), "static_run": a.get("run"), "static_src": a.get("src"),
                "slit_h": b.get("h"), "slit_run": b.get("run"),
            })
    return adaylar


def seam_dup_dusenler(manifest: dict) -> list[dict]:
    blocks = manifest.get("blocks") or []
    return [b for b in blocks if isinstance(b, dict) and b.get("skip") == "seam-dup"]


def tara(masters_kok: Path) -> dict:
    filmler = sorted(p for p in masters_kok.iterdir() if p.is_dir() and not p.name.startswith("_"))
    detay: dict[str, dict] = {}
    aday_filmler = []
    seam_dup_filmler = []
    seam_dup_toplam = 0
    n_okunan = 0
    for film_dir in filmler:
        manifest = _load_json(film_dir / "manifest.json")
        if manifest is None:
            continue
        n_okunan += 1
        adaylar = tekrar_adaylari(manifest)
        dusenler = seam_dup_dusenler(manifest)
        if adaylar or dusenler:
            detay[film_dir.name] = {
                "aday_sayisi": len(adaylar), "olaylar": adaylar,
                "seam_dup_dusen": len(dusenler),
                "seam_dup_kanit": [d.get("seam_kanit") for d in dusenler],
            }
        if adaylar:
            aday_filmler.append(film_dir.name)
        if dusenler:
            seam_dup_filmler.append(film_dir.name)
            seam_dup_toplam += len(dusenler)
    return {
        "masters_kok": str(masters_kok),
        "n_film_okunan": n_okunan,
        "aday_film_sayisi": len(aday_filmler),
        "aday_filmler": aday_filmler,
        "seam_dup_dusen_film_sayisi": len(seam_dup_filmler),
        "seam_dup_filmler": seam_dup_filmler,
        "seam_dup_toplam": seam_dup_toplam,
        "detay": detay,
    }


def _cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("masters_kok", type=Path)
    ap.add_argument("--json", dest="json_cikti", default=None)
    ap.add_argument("--liste-yaz", dest="liste_yaz", default=None,
                     help="aday_filmler listesini satır-başına-bir-slug dosyaya yaz (uret_ex --liste için)")
    args = ap.parse_args(argv)
    if not args.masters_kok.is_dir():
        print(f"Kök bulunamadı: {args.masters_kok}", file=sys.stderr)
        return 1
    sonuc = tara(args.masters_kok)
    print(f"okunan film: {sonuc['n_film_okunan']}")
    print(f"aday film sayısı (kept static_page -> kept scroll_slit bitişikliği): {sonuc['aday_film_sayisi']}")
    print(f"seam-dup DÜŞEN film sayısı: {sonuc['seam_dup_dusen_film_sayisi']}  (toplam düşen blok: {sonuc['seam_dup_toplam']})")
    if args.json_cikti:
        Path(args.json_cikti).write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"-> {args.json_cikti}")
    if args.liste_yaz:
        Path(args.liste_yaz).write_text("\n".join(sonuc["aday_filmler"]) + "\n", encoding="utf-8")
        print(f"-> {args.liste_yaz} ({len(sonuc['aday_filmler'])} slug)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
