#!/usr/bin/env python3
"""KONTROL TAKSONOMİSİ — KONTROL'e düşen her filmin SEBEBİNİ ADIMA bağlar (salt-okur).

Çağatay talimatı (2026-07-31 gece): "kontrole düşenlerde neden düşüyor, sorun
hangi adımda — net bilip fixlemek önemli. Kontrole düştü diye orda kalmasın."

KONTROL bir çöp kutusu değil KUYRUKTUR: bu araç kuyruğu sebep-sınıflarına böler,
her sınıf bir fix adayıdır; fix sonrası filmler from-hub ile yeniden koşulur
(scripts/from_hub_batch.py — video yeniden indirilmez, hub'daki kareler kullanılır).

SEBEP → ADIM eşlemesi `neden` metinlerindeki imzalardan çıkarılır (aşağıdaki
DESENLER). Eşleşmeyen sebep 'siniflandirilamadi' altında AYNEN listelenir —
sessizce yutulmaz; yeni sınıf görülünce DESENLER'e eklenir.

KULLANIM:
    python3 scripts/kontrol_taksonomi.py            # tablo
    python3 scripts/kontrol_taksonomi.py --json
    python3 scripts/kontrol_taksonomi.py --sinif kimlik   # o sınıftaki filmler
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
DB = PROJE / "Database"

# imza (küçük-harf arama) → (sınıf, sorumlu adım, fix-notu)
DESENLER: list[tuple[str, tuple[str, str, str]]] = [
    ("kimlik çelişkisi", ("kimlik", "QC2/kimlik (KB cross-check)",
                          "XML↔KB↔web kimliği uyuşmuyor — yabancı/az-bilinen film sınıfı")),
    ("kimlik kurulamadı", ("kimlik", "QC2/qc_block (web çapası)",
                           "cast-örtüşme<2 / web kilitlenemedi — kimlik kanıtı zayıf")),
    ("qc1 başarısız", ("kunye_kalite", "QC1 (okuma→rol)",
                       "yönetmen boş/cast<3 — okuma veya rol-eşleme yetersiz")),
    ("okunamadı", ("kunye_kalite", "OCR/okuma",
                   "okuma katmanı satır üretemedi")),
    ("motor_yok", ("teknik", "OCR motoru",
                   "okuyucu hiç koşamadı — env/kurulum arızası")),
    ("frame", ("teknik", "ÇÖZ/kare-sözleşmesi", "kare çıkarımı kusurlu")),
    ("afiş", ("afis", "afiş doğrulama", "poster teyidi başarısız")),
    ("poster", ("afis", "afiş doğrulama", "poster teyidi başarısız")),
    ("ses", ("ses_dil", "ASR/kanal-dil", "ses/dil doğrulama")),
    ("dil", ("ses_dil", "ASR/kanal-dil", "ses/dil doğrulama")),
    ("yönetmen", ("kunye_kalite", "rol-eşleme", "yönetmen alanı sorunlu")),
    ("cast", ("kunye_kalite", "rol-eşleme", "cast alanı sorunlu")),
    ("celiski", ("kimlik", "credit_validate", "KB/XML çelişki sinyali")),
]


def siniflandir(neden: str) -> tuple[str, str, str]:
    n = neden.lower()
    for imza, sonuc in DESENLER:
        if imza in n:
            return sonuc
    return ("siniflandirilamadi", "?", neden[:120])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sinif", default=None, help="yalnız bu sınıfın filmlerini listele")
    a = ap.parse_args()

    filmler: list[dict] = []
    for d in sorted(DB.iterdir()):
        durum = d / "_DURUM.json"
        if not d.is_dir() or not durum.is_file():
            continue
        try:
            j = json.loads(durum.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if str(j.get("karar", "")).lower() != "kontrol":
            continue
        nedenler = j.get("neden") or []
        siniflar = sorted({siniflandir(str(n))[0] for n in nedenler}) or ["neden_bos"]
        filmler.append({
            "film": d.name, "siniflar": siniflar, "nedenler": nedenler,
            "qc1": j.get("qc1"),
            "engine": None,  # aşağıda doldurulur
        })
        # okuma motoru: en yeni ocr işinin summary'sinden (hibrit mi paddle mı düştü?)
        ocrler = sorted((d / "ocr").glob("ocr-*/ocr_summary.json")) if (d / "ocr").is_dir() else []
        if ocrler:
            try:
                filmler[-1]["engine"] = json.loads(
                    ocrler[-1].read_text(encoding="utf-8")).get("engine")
            except Exception:  # noqa: BLE001
                pass

    # sınıf sayımı
    sayim: dict[str, int] = {}
    for f in filmler:
        for s in f["siniflar"]:
            sayim[s] = sayim.get(s, 0) + 1

    if a.sinif:
        secilen = [f for f in filmler if a.sinif in f["siniflar"]]
        if a.json:
            print(json.dumps(secilen, ensure_ascii=False, indent=1))
        else:
            print(f"=== sınıf: {a.sinif} — {len(secilen)} film ===")
            for f in secilen:
                print(f"\n  {f['film']}")
                print(f"    motor: {f['engine']}")
                for n in f["nedenler"]:
                    print(f"    - {n}")
        return 0

    if a.json:
        print(json.dumps({"kontrol_n": len(filmler), "sinif_sayim": sayim,
                          "filmler": filmler}, ensure_ascii=False, indent=1))
        return 0

    print(f"=== KONTROL TAKSONOMİSİ — {len(filmler)} film ===\n")
    adim_notu = {s: (adim, not_) for _, (s, adim, not_) in DESENLER}
    for s, n in sorted(sayim.items(), key=lambda kv: -kv[1]):
        adim, not_ = adim_notu.get(s, ("?", ""))
        print(f"  {s:<22} {n:>4} film   adım: {adim}")
        if not_:
            print(f"  {'':<22}        {not_}")
    yeni = [f for f in filmler if "siniflandirilamadi" in f["siniflar"]]
    if yeni:
        print(f"\n  ⚠ sınıflandırılamayan {len(yeni)} film — DESENLER'e sınıf eklenecek:")
        for f in yeni[:8]:
            print(f"    {f['film']}: {f['nedenler']}")
    print("\n  detay : python3 scripts/kontrol_taksonomi.py --sinif <ad>")
    print("  yeniden koşu (fix sonrası): scripts/from_hub_batch.py — hub kareleri, video indirmez")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
