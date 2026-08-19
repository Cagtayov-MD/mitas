"""CLI giriş noktası — python -m genel_sekreter

Alt komutlar:
  kontrol    — KONTROL analizi (tek-seferlik)
  onayli     — ONAYLI QC (tek-seferlik)
  performans — Performans ölçümü (tek-seferlik)
  gunluk     — Secretary günlük rapor (tek-seferlik)
  hepsi      — Tüm modülleri tek-seferlik çalıştır
  panel      — Web dashboard başlat (http://127.0.0.1:8898)
  json       — JSON çıktı (API test)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Paket importu
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    ap = argparse.ArgumentParser(
        prog="genel_sekreter",
        description="MITAS Genel Sekreter — Otomatik denetim ve raporlama",
    )
    ap.add_argument(
        "komut",
        choices=["kontrol", "onayli", "performans", "gunluk", "hepsi", "panel", "json"],
        help="Çalıştırılacak komut",
    )
    args = ap.parse_args()

    if args.komut == "kontrol":
        from genel_sekreter.ajan_kontrol import rapor_kontrol
        from genel_sekreter.rapor import emit_rapor
        md = rapor_kontrol()
        dosya = emit_rapor("kontrol_analiz", md)
        print(f"✅ KONTROL raporu: {dosya}")
        print(md[:500])

    elif args.komut == "onayli":
        from genel_sekreter.ajan_qc_dogrulama import rapor_onayli
        from genel_sekreter.rapor import emit_rapor
        md = rapor_onayli()
        dosya = emit_rapor("onayli_qc", md)
        print(f"✅ ONAYLI QC raporu: {dosya}")
        print(md[:500])

    elif args.komut == "performans":
        from genel_sekreter.ajan_performans import rapor_performans
        from genel_sekreter.rapor import emit_rapor
        md = rapor_performans()
        dosya = emit_rapor("performans", md)
        print(f"✅ Performans raporu: {dosya}")
        print(md[:500])

    elif args.komut == "gunluk":
        from genel_sekreter.secretary import yaz_ve_ekle
        dosya = yaz_ve_ekle()
        print(f"✅ Günlük rapor: {dosya}")

    elif args.komut == "hepsi":
        from genel_sekreter.ajan_kontrol import rapor_kontrol
        from genel_sekreter.ajan_qc_dogrulama import rapor_onayli
        from genel_sekreter.ajan_performans import rapor_performans
        from genel_sekreter.secretary import yaz_ve_ekle
        from genel_sekreter.rapor import emit_rapor

        print("📋 KONTROL analizi...")
        emit_rapor("kontrol_analiz", rapor_kontrol())
        print("✅ ONAYLI QC...")
        emit_rapor("onayli_qc", rapor_onayli())
        print("⚡ Performans...")
        emit_rapor("performans", rapor_performans())
        print("📝 Günlük rapor...")
        yaz_ve_ekle()
        print("✅ Tüm raporlar üretildi: docs/raporlar/gunluk/")

    elif args.komut == "panel":
        from genel_sekreter.panel import baslat_panel
        baslat_panel()

    elif args.komut == "json":
        from genel_sekreter.ajan_kontrol import analiz_kontrol
        from genel_sekreter.ajan_performans import olcum_performans
        from genel_sekreter.ajan_qc_dogrulama import spot_check
        data = {
            "kontrol": analiz_kontrol(),
            "performans": olcum_performans(),
            "onayli": spot_check(orneklem_pct=5),
        }
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
