#!/usr/bin/env python3
"""KONTROL KOHORTU A/B KIYASI — eski koşu vs bugünkü düzeltmelerle yeni koşu.

Çağatay: "Çıktıları birebir kıyaslarız — düzelttiklerimiz düzelmiş mi,
beklediklerimiz ne olmuş."

Aynı film, aynı video, tek değişken BUGÜNKÜ DÜZELTMELER (kohort hibritle okunmuştu).
Eski veri Database_kontrol_yedek_<ts>/Database/ altında; yeni veri Database/ altında.

BEKLENTİ TABLOSU aşağıda: bulgu defterindeki her fix'in HANGİ FİLMDE ne yapması
gerektiği önceden yazılı. Böylece "iyi görünüyor" değil, "beklediğimiz oldu mu"
sorusu cevaplanır — sonradan hikâye uydurmayı engeller.

KULLANIM:
    python3 scripts/kontrol_kiyas.py --yedek Database_kontrol_yedek_20260801_1130
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))

# ── ÖNCEDEN YAZILI BEKLENTİLER (bulgu defteri A15/A16/A11/A7 vb.) ──
BEKLENTI = {
    "1998-0325": ("KUTSAL HAZİNE", "yönetmen DOLMALI (JOHN HUNECK) — 500-satır kesmesi + "
                                   "giriş master körlüğü düzeldi; kart giriş master bant 0'da"),
    "1999-0355": ("KÜÇÜK KARDEŞLER", "Latin-dışı damgası KALKMALI — 'Судьба' saplantısı "
                                     "kutu_n=0 süzgeciyle temizlendi (%5.0 → %0.0 ölçüldü)"),
    "1996-0161": ("KAYGIYA MERHABA", "Latin-dışı damgası KALKMALI (%5.2 → %0.0)"),
    "1954-0056": ("KORKUYU BİLMEYEN", "Latin-dışı damgası KALKMALI (%3.3 → %0.6)"),
    "1972-0094": ("TUZSUZ DELİ BEKİR", "Latin-dışı damgası KALKMALI (%2.7 → %1.9)"),
    "1993-0371": ("ŞEHİR AVCISI", "Latin-dışı damgası KALMALI — gerçekten Çince (%20)"),
    "1989-0549": ("İKİ SÜVARİ", "Latin-dışı damgası KALMALI — gerçekten Kiril (%98)"),
    "1988-0520": ("ANNA KARENINA", "Latin-dışı KALMALI; ayrıca Kiril 'РЕЖИССЕРЫ' etiketi "
                                   "artık tanınıyor → yönetmen adayı çıkabilir"),
    "2025-1047": ("KOŞUCU", "Farsça 'کارگردان' etiketi artık tanınıyor → yönetmen çıkabilir"),
    "2010-9253": ("ALİE", "yönetmen MEŞRU BOŞ (kriz nedeniyle jenerikte yok) — dolmamalı; "
                          "ama giriş penceresi 240 sn oldu → YAPIMCI (03:16) artık okunmalı"),
    "1994-0000": ("BİR BÜROKRATIN", "Latin-dışı damgası KALKMALI; giriş havuzu 1 kare (ayrı sorun)"),
}

ALANLAR = ("karar", "neden", "qc1", "ocr_bucket", "ocr_lines")


def durum_oku(p: Path) -> dict | None:
    f = p / "_DURUM.json"
    if not f.is_file():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def yon_al(j: dict) -> str:
    q = j.get("qc1") or {}
    return "VAR" if q.get("yonetmen_var") else "yok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yedek", required=True, help="Database_kontrol_yedek_<ts> dizini")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    yedek = Path(a.yedek)
    if not yedek.is_absolute():
        yedek = PROJE / yedek
    eski_kok = yedek / "Database"
    if not eski_kok.is_dir():
        print(f"RED: {eski_kok} yok")
        return 1

    satirlar = []
    for eski_d in sorted(eski_kok.iterdir()):
        if not eski_d.is_dir():
            continue
        yeni_d = PROJE / "Database" / eski_d.name
        e, y = durum_oku(eski_d), durum_oku(yeni_d)
        trt = eski_d.name.split()[-1][:9] if eski_d.name else "?"
        ad = " ".join(eski_d.name.split()[:-1])[:24]
        if e is None:
            continue
        if y is None:
            satirlar.append({"film": ad, "trt": trt, "durum": "YENİ KOŞU YOK/EKSİK",
                             "eski_karar": e.get("karar"), "yeni_karar": None})
            continue
        ek, yk = str(e.get("karar")), str(y.get("karar"))
        ey, yy = yon_al(e), yon_al(y)
        en = set(str(x)[:44] for x in (e.get("neden") or []))
        yn = set(str(x)[:44] for x in (y.get("neden") or []))
        satirlar.append({
            "film": ad, "trt": trt,
            "eski_karar": ek, "yeni_karar": yk,
            "eski_yon": ey, "yeni_yon": yy,
            "cozulen": sorted(en - yn), "yeni_sorun": sorted(yn - en),
            "beklenti": BEKLENTI.get(trt[:9], ("", ""))[1],
        })

    if a.json:
        print(json.dumps(satirlar, ensure_ascii=False, indent=1))
        return 0

    kurtulan = [s for s in satirlar if s.get("eski_karar") == "Kontrol" and s.get("yeni_karar") == "Hazır"]
    yon_dolan = [s for s in satirlar if s.get("eski_yon") == "yok" and s.get("yeni_yon") == "VAR"]
    kotulesen = [s for s in satirlar if s.get("eski_karar") == "Hazır" and s.get("yeni_karar") == "Kontrol"]

    print(f"=== KONTROL KOHORTU A/B — {len(satirlar)} film ===\n")
    print(f"  KONTROL → ONAYLI          : {len(kurtulan)}")
    print(f"  yönetmen yok → VAR        : {len(yon_dolan)}")
    print(f"  GERİLEME (ONAYLI→KONTROL) : {len(kotulesen)}  {'⚠' if kotulesen else ''}")
    print()
    for s in satirlar:
        ok = "→ONAYLI ✓" if s in kurtulan else ""
        yd = " yön:DOLDU" if s in yon_dolan else ""
        print(f"  {s['film']:<26}{str(s.get('eski_karar')):<9}→ {str(s.get('yeni_karar')):<9}{ok}{yd}")
        for c in s.get("cozulen") or []:
            print(f"       ÇÖZÜLDÜ  - {c}")
        for n in s.get("yeni_sorun") or []:
            print(f"       ⚠ YENİ   + {n}")
        if s.get("beklenti"):
            print(f"       beklenti : {s['beklenti'][:96]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
