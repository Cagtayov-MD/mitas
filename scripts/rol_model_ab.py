#!/usr/bin/env python3
"""ROL ÇIKARIMI MODEL A/B — aynı künye, farklı model, GERÇEK üretim promptu.

ÇAĞATAY İTİRAZI (2026-08-01) ve haklı çıkışı:
    "Bir filmde eşleşme kötü çıktı diye bu işi modelden almam; en fazla modeli
     değiştiririz. Gemma şu anda tam performans çalışabiliyor mu?"
BULGU: üretimdeki rol-çıkarım modeli `gemma-4-31b-it-qat-vision` **Q4_0** —
kütüphanedeki 30B sınıfı diğer HER model Q4_K_M. Q4_0 en eski/kaba 4-bit format
ve en çok bozduğu şey uzun-bağlam HATIRLAMA; düşen görev de tam o.
Üstelik VISION varyantı saf METİN işinde kullanılıyor — depo kendi notunda
"serbest-metinde dejenere oluyor" diyip özeti 26b'ye almış, rol çıkarımı hâlâ burada.

Bu betik model seçmez, ÖLÇER (no_engine_selection_before_benchmark).
Üretim promptunu ve şemasını credit_text_read'den İTHAL eder — kopyalamaz,
yoksa ölçtüğümüz şey üretim davranışı olmaz.

KULLANIM:
    python3 scripts/rol_model_ab.py --modeller gemma-4-31b-it-qat-vision:latest,gemma4:26b
    python3 scripts/rol_model_ab.py --liste            # yatağı göster, koşma
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
sys.path.insert(0, str(PROJE / "scripts"))

# YATAK: her satır (film-öneki, beklenen-yönetmen|None, not).
# Beklenen "None" ise yalnız KIYAS için — modeller arası fark bakılır.
YATAK = [
    ("YAZ TATİLİ",     "PETER YATES",  "bizim hata: koreograf HERBERT ROSS alınmış; doğru isim BİR ALT SATIRDA"),
    ("KARA GÜNLER",    None,           "bizim hata: 'NACH EINER GESCHICHTE VON' (hikâye yazarı) altındaki isim"),
    ("ÇİNGENE",        None,           "bizim hata: '2ème assistant réalisateur' altındaki isim"),
    ("KUTSAL HAZİNE",  "JOHN CONNICK", "gemma ATLADI (264 satırın 252.'si); ekran kanıtı g_0244.png"),
    ("EVE UÇUŞ",       None,           "yönetmen bulunamadı ama cast 15 doğru — kısmi başarı"),
    ("DELİ ORMANLI",   None,           "KONTROL GRUBU: ONAYLI çıkmıştı, bozulmamalı"),
]


def kunye_bul(onek: str) -> Path | None:
    d = next((p for p in sorted((PROJE / "Database").iterdir())
              if p.is_dir() and p.name.startswith(onek)), None)
    if not d:
        return None
    ks = sorted((d / "ocr").glob("ocr-*/kunye.txt")) if (d / "ocr").is_dir() else []
    return ks[-1] if ks else None


def kos(model: str, baslik: str, satirlar: list[str], ctr) -> dict:
    """ÜRETİMİN KENDİ giriş noktası: read_credits_auto (_pipe_credit_text.py:111 ile birebir).

    MITAS_CREDIT_TEXT_MODEL model_chain()'i TEK modele indirir (credit_text_read:2130),
    yani zincir füzyonu devre dışı → saf model karşılaştırması olur.
    """
    t0 = time.perf_counter()
    os.environ["MITAS_CREDIT_TEXT_MODEL"] = model
    try:
        res = ctr.read_credits_auto(satirlar, baslik, dizi=False,
                                    raw_context_lines=satirlar) or {}
    except Exception as e:  # noqa: BLE001
        return {"hata": f"{type(e).__name__}: {str(e)[:120]}",
                "sn": round(time.perf_counter() - t0, 1)}
    return {"yonetmen": res.get("yonetmen") or [],
            "yapimci_n": len(res.get("yapimci") or []),
            "cast_n": len(res.get("cast") or []),
            "guven": res.get("guven"),
            "sn": round(time.perf_counter() - t0, 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modeller", default="gemma-4-31b-it-qat-vision:latest,gemma4:26b")
    ap.add_argument("--liste", action="store_true")
    a = ap.parse_args()

    yatak = []
    for onek, bek, not_ in YATAK:
        k = kunye_bul(onek)
        if not k:
            print(f"  ATLA (künye yok): {onek}")
            continue
        sat = k.read_text(encoding="utf-8", errors="ignore").splitlines()
        yatak.append((onek, bek, not_, sat))

    print(f"=== YATAK: {len(yatak)} film ===")
    for onek, bek, not_, sat in yatak:
        print(f"   {onek:<18}{len(sat):>5} satır  beklenen={bek or '?':<14}{not_[:52]}")
    if a.liste:
        return 0

    import credit_text_read as ctr  # noqa: PLC0415 — ağır import yalnız koşuda

    # MODEL TAKASI BİR KEZ (pilot_hat deseni): önce TÜM filmler model A ile.
    sonuc: dict = {}
    for model in [m.strip() for m in a.modeller.split(",") if m.strip()]:
        print(f"\n--- MODEL: {model}")
        sonuc[model] = {}
        for onek, bek, not_, sat in yatak:
            r = kos(model, onek, sat, ctr)
            sonuc[model][onek] = r
            yon = r.get("yonetmen")
            isabet = ""
            if bek and yon:
                isabet = " ✓" if any(bek.lower() in str(y).lower() for y in yon) else " ✗"
            print(f"   {onek:<18}yön={str(yon)[:36]:<38}cast={r.get('cast_n')}"
                  f"  {r.get('sn')}sn{isabet}  {r.get('hata','')}")

    cikti = PROJE / "outputs" / "rol_model_ab.json"
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  rapor: {cikti}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
