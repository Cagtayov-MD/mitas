#!/usr/bin/env python3
"""Sağlık sınıflandırıcısı (Görev M7, MITAS_Master_Dup_Kok_Sebep_Plani_v1.md).

SAĞLIK TANIMI (5 kriter -- hepsi VE; taban koşusundan sonra kalibre edilip
kilitlenir, şu an plan dokümanındaki ilk tanım uygulanıyor):
  1. üretim OK       -> manifest.status == "OK", istisna yok, kept_blocks >= 1
  2. dup_oran <= 0.10 -> metrik.json (dup_metrik.py M1, F1/F1b/F1c SONRASI)
  3. boy makul       -> 300 <= H <= 45000 (canavar/boş master değil)
  4. imha-imzası YOK -> statik-sayfa (kind=="static_page") alanı > %70 VE
     >=2 "cılız" blok (h<25px) BİRLİKTE görülürse footage-üstü kayan yazının
     ezildiği şüphesi -> sağlıksız (bkz. M4b, F1c teşhisleri)
  5. doku_kapsami >= 0.05 -> kapkara/boş master değil

Girdi: BİR masters kökü -- her alt-klasör <FİLM>/{manifest.json, metrik.json,
reading_master.png} şemasında olmalı (uret.py VE uret_ex.py'nin ortak çıktı
şeması -- bu yüzden bu sınıflandırıcı hem `data/master_dup/masters_v2/` hem
`data/master_ex/` üzerinde DEĞİŞİKLİKSİZ çalışır).

Çıktı: film başına {saglikli: bool, ihlaller: [...]} + toplu sağlık oranı +
ihlal-sınıfı dağılımı (hangi kriter kaç filmi düşürüyor).

CLI:
  saglik.py <masters_kok> [--json cikti.json] [--dup-esik 0.10] ...
  saglik.py data/master_ex --json data/master_ex/saglik_ex.json
  saglik.py data/master_dup/masters_v2 --json data/master_dup/saglik_v2.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DUP_ESIK_VARSAYILAN = 0.10
H_MIN_VARSAYILAN = 300
H_MAKS_VARSAYILAN = 45000
DOKU_ESIK_VARSAYILAN = 0.05
STATIK_ORAN_ESIK_VARSAYILAN = 0.70
CILIZ_H_ESIK_VARSAYILAN = 25
CILIZ_MIN_SAYI_VARSAYILAN = 2

IHLAL_ETIKETLERI = {
    "manifest_yok": "manifest.json yok/okunamadı",
    "uretim_basarisiz": "üretim OK değil (status != OK, PNG eksik, ya da kept_blocks < 1)",
    "dup_oran_yuksek": "dup_oran eşik üstü (ya da metrik.json yok)",
    "boy_anormal": "H eşik dışı (canavar/boş boy)",
    "imha_imzasi": "statik-sayfa alanı > eşik VE >=N cılız blok (footage-üstü ezilme şüphesi)",
    "doku_kapsami_dusuk": "doku_kapsami eşik altı (kapkara/boş master)",
}


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def degerlendir(
    film_dir: Path,
    *,
    dup_esik: float = DUP_ESIK_VARSAYILAN,
    h_min: int = H_MIN_VARSAYILAN,
    h_maks: int = H_MAKS_VARSAYILAN,
    doku_esik: float = DOKU_ESIK_VARSAYILAN,
    statik_oran_esik: float = STATIK_ORAN_ESIK_VARSAYILAN,
    ciliz_h_esik: int = CILIZ_H_ESIK_VARSAYILAN,
    ciliz_min_sayi: int = CILIZ_MIN_SAYI_VARSAYILAN,
) -> dict:
    """Tek film klasörünü 5 kritere göre değerlendirir."""
    film = film_dir.name
    ihlaller: list[str] = []
    detay: dict = {}

    manifest = _load_json(film_dir / "manifest.json")
    if manifest is None:
        return {"film": film, "saglikli": False, "ihlaller": ["manifest_yok"], "detay": {}}

    metrik = _load_json(film_dir / "metrik.json")
    png_var = (film_dir / "reading_master.png").is_file()

    status = manifest.get("status")
    kept_blocks = manifest.get("kept_blocks")
    detay["status"] = status
    detay["kept_blocks"] = kept_blocks
    detay["png_var"] = png_var

    # --- Kriter 1: üretim OK ---
    if status != "OK" or not png_var or not kept_blocks or kept_blocks < 1:
        ihlaller.append("uretim_basarisiz")

    # metrik alanları (dup_oran, doku_kapsami, boy)
    dup_oran = metrik.get("dup_oran") if metrik else None
    doku_kapsami = metrik.get("doku_kapsami") if metrik else None
    boy = (metrik.get("boy") if metrik else None) or manifest.get("size")
    detay["dup_oran"] = dup_oran
    detay["doku_kapsami"] = doku_kapsami
    detay["boy"] = boy

    # --- Kriter 2: dup_oran ---
    if dup_oran is None or dup_oran > dup_esik:
        ihlaller.append("dup_oran_yuksek")

    # --- Kriter 3: boy ---
    h = boy[1] if boy and len(boy) == 2 else None
    if h is None or not (h_min <= h <= h_maks):
        ihlaller.append("boy_anormal")

    # --- Kriter 4: imha-imzası (statik-sayfa alanı + cılız blok birlikteliği) ---
    blocks = manifest.get("blocks") or []
    kept = [b for b in blocks if isinstance(b, dict) and b.get("h") is not None and not b.get("skip")]
    total_h = h if h is not None else (sum(b["h"] for b in kept) if kept else None)
    if kept and total_h:
        static_h = sum(b["h"] for b in kept if b.get("kind") == "static_page")
        static_oran = static_h / total_h
        ciliz_sayisi = sum(1 for b in kept if b["h"] < ciliz_h_esik)
    else:
        static_oran = 0.0
        ciliz_sayisi = 0
    detay["static_oran"] = round(static_oran, 4)
    detay["ciliz_blok_sayisi"] = ciliz_sayisi
    imha_supheli = (static_oran > statik_oran_esik) and (ciliz_sayisi >= ciliz_min_sayi)
    if imha_supheli:
        ihlaller.append("imha_imzasi")

    # --- Kriter 5: doku_kapsami ---
    if doku_kapsami is None or doku_kapsami < doku_esik:
        ihlaller.append("doku_kapsami_dusuk")

    return {
        "film": film,
        "saglikli": len(ihlaller) == 0,
        "ihlaller": ihlaller,
        "detay": detay,
    }


def olc_kok(masters_kok: Path, **kwargs) -> dict:
    filmler = sorted(p for p in masters_kok.iterdir() if p.is_dir())
    sonuclar = [degerlendir(p, **kwargs) for p in filmler]
    n = len(sonuclar)
    saglikli_n = sum(1 for s in sonuclar if s["saglikli"])
    dagilim: dict[str, int] = {}
    for s in sonuclar:
        for ihlal in s["ihlaller"]:
            dagilim[ihlal] = dagilim.get(ihlal, 0) + 1
    return {
        "masters_kok": str(masters_kok),
        "n": n,
        "saglikli_sayi": saglikli_n,
        "saglik_orani": round(saglikli_n / n, 4) if n else 0.0,
        "ihlal_dagilimi": dagilim,
        "sonuclar": sonuclar,
    }


def en_kotu_n(sonuc: dict, n: int = 15) -> list[dict]:
    """Sağlıksız filmleri ihlal-sayısına (çoktan aza) göre sıralar; en kötü N'i döner."""
    sagliksiz = [s for s in sonuc["sonuclar"] if not s["saglikli"]]
    sagliksiz.sort(key=lambda s: (-len(s["ihlaller"]), s["detay"].get("dup_oran") or 0.0, s["film"]))
    return sagliksiz[:n]


def _cli(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("masters_kok", type=Path, help="masters kökü (ör. data/master_ex veya data/master_dup/masters_v2)")
    ap.add_argument("--json", dest="json_cikti", default=None, help="Sonucu JSON olarak bu yola yaz")
    ap.add_argument("--dup-esik", type=float, default=DUP_ESIK_VARSAYILAN)
    ap.add_argument("--h-min", type=int, default=H_MIN_VARSAYILAN)
    ap.add_argument("--h-maks", type=int, default=H_MAKS_VARSAYILAN)
    ap.add_argument("--doku-esik", type=float, default=DOKU_ESIK_VARSAYILAN)
    ap.add_argument("--statik-oran-esik", type=float, default=STATIK_ORAN_ESIK_VARSAYILAN)
    ap.add_argument("--ciliz-h-esik", type=int, default=CILIZ_H_ESIK_VARSAYILAN)
    ap.add_argument("--ciliz-min-sayi", type=int, default=CILIZ_MIN_SAYI_VARSAYILAN)
    ap.add_argument("--en-kotu", type=int, default=15, help="konsolda gösterilecek en kötü N (varsayılan 15)")
    args = ap.parse_args(argv)

    if not args.masters_kok.is_dir():
        print(f"Kök bulunamadı: {args.masters_kok}", file=sys.stderr)
        return 1

    sonuc = olc_kok(
        args.masters_kok,
        dup_esik=args.dup_esik, h_min=args.h_min, h_maks=args.h_maks,
        doku_esik=args.doku_esik, statik_oran_esik=args.statik_oran_esik,
        ciliz_h_esik=args.ciliz_h_esik, ciliz_min_sayi=args.ciliz_min_sayi,
    )
    print(f"{sonuc['saglikli_sayi']}/{sonuc['n']} sağlıklı (%{sonuc['saglik_orani'] * 100:.1f})")
    print("İhlal dağılımı:", json.dumps(sonuc["ihlal_dagilimi"], ensure_ascii=False))
    print(f"\nEn kötü {args.en_kotu}:")
    for s in en_kotu_n(sonuc, args.en_kotu):
        print(f"  {s['film'][:55]:55} ihlaller={s['ihlaller']} dup={s['detay'].get('dup_oran')} "
              f"boy={s['detay'].get('boy')} static_oran={s['detay'].get('static_oran')} "
              f"ciliz={s['detay'].get('ciliz_blok_sayisi')}")

    if args.json_cikti:
        Path(args.json_cikti).write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n-> {args.json_cikti}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
