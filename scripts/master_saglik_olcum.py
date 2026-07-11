# -*- coding: utf-8 -*-
"""MASTER-PNG SAĞLIK ÖLÇÜMÜ (Faz-2 ÖLÇÜM-MODU, konsey master-kapsama şartnamesi 2026-07-06).
SALT-OKUR — üretime/Database'e SIFIR dokunuş. Tüm filmlerin master'larını puanlar:
  - run-aware master (reading_master_runaware.png / giris_...) = Çağatay'ın sevdiği İYİ motor
  - kök-teslim master (<base> giris/cikis.png) = crop-stack/slit-scan, sık zayıf
Sağlık sinyalleri (manifest + boyut): yükseklik(px), kept_blocks, status.
AMAÇ: eşikleri VERİDEN koymak (konsey: 'önce ölç, kabul etme'). Kabul-kapısı UYGULANMAZ."""
from __future__ import annotations
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = r"E:\MITAS\Database"

# Sağlık eşikleri (ÖN-DEĞER, ölçümden sonra kalibre edilecek — şimdilik yalnız sınıflama):
MIN_YUKSEK = 200      # <200px = neredeyse-boş/bozuk (KÜÇÜK KAHRAMAN kök 13px vakası)
SUPHE_YUKSEK = 12000  # >12000px = footage-bloat/epilog-flood ŞÜPHESİ (alignment ile teyit — v2)


def _png_yukseklik(p):
    """PIL'siz PNG yükseklik (IHDR): baytları oku. Hata → None."""
    try:
        with open(p, "rb") as f:
            head = f.read(26)
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        # IHDR width(4) height(4) @ offset 16
        return int.from_bytes(head[20:24], "big")
    except Exception:  # noqa: BLE001
        return None


def _travel_cokuk(png_path):
    """HİBRİT-DY üretim bekçisi (şartname 2026-07-09): reading manifest'inde herhangi bir
    scroll_slit bloğunun travel_ratio'su < 0.5 ise master TRAVEL-ÇÖKÜK (Yedi Numara hayalet
    vakası 928/3796≈0.24 tek sayıyla yakalanır). Manifest yalnız bayrak='1' koşularında
    hybrid alanı taşır; yokluk = sinyal yok (False)."""
    try:
        mp = os.path.join(os.path.dirname(png_path),
                          os.path.basename(png_path).replace(".png", ".json"))
        if not os.path.exists(mp):
            return False
        with open(mp, encoding="utf-8", errors="ignore") as f:
            man = json.load(f) or {}
        for blk in man.get("blocks") or man.get("block_manifest") or []:
            hy = blk.get("hybrid") if isinstance(blk, dict) else None
            tr = (hy or {}).get("travel_ratio")
            if tr is not None and tr < 0.5:
                return True
    except Exception:  # noqa: BLE001 — bekçi ölçümü sınıflamayı asla bozmaz
        return False
    return False


def _saglik(p):
    """Bir master PNG dosyasının sağlık-sınıfı."""
    if not (p and os.path.exists(p)):
        return "YOK", None
    kb = os.path.getsize(p) // 1024
    h = _png_yukseklik(p)
    if h is None:
        return "BOZUK-PNG", kb
    if h < MIN_YUKSEK or kb < 30:
        return "NEREDEYSE-BOŞ", kb
    if h > SUPHE_YUKSEK:
        return "ŞÜPHE-BLOAT", kb
    if _travel_cokuk(p):
        return "TRAVEL-ÇÖKÜK", kb
    return "SAĞLIKLI", kb


def olc():
    hubs = [d for d in glob.glob(os.path.join(DB, "*")) if os.path.isdir(d)]
    say = {"run_aware": {}, "kok": {}}
    daha_iyi_run_aware = 0     # run-aware SAĞLIKLI ama kök NEREDEYSE-BOŞ/YOK (kanonik-karar kanıtı)
    incel = 0
    ornek = []
    for h in hubs:
        if not glob.glob(os.path.join(h, "ocr", "ocr-*", "kunye.txt")):
            continue
        incel += 1
        for seg, ra_name in (("giris", "giris_reading_master_runaware.png"),
                             ("cikis", "reading_master_runaware.png")):
            ra = os.path.join(h, ra_name)
            ra_s, ra_kb = _saglik(ra)
            say["run_aware"][ra_s] = say["run_aware"].get(ra_s, 0) + 1
            # kök-teslim (aynı segment)
            kok = [k for k in glob.glob(os.path.join(h, f"* {seg}.png")) if "reading_master" not in k]
            kok_s, kok_kb = _saglik(kok[0] if kok else None)
            say["kok"][kok_s] = say["kok"].get(kok_s, 0) + 1
            # run-aware iyi ama kök kötü → kanonik-karar bu filmi kurtarır
            if ra_s == "SAĞLIKLI" and kok_s in ("YOK", "NEREDEYSE-BOŞ", "BOZUK-PNG"):
                daha_iyi_run_aware += 1
                if len(ornek) < 15:
                    ornek.append((os.path.basename(h)[:38], seg, f"run-aware={ra_kb}KB kök={kok_s}"))
    print(f"=== MASTER SAĞLIK ÖLÇÜMÜ ({incel} film × 2 segment) — SALT-OKUR ===\n")
    print("RUN-AWARE master (senin sevdiğin motor):")
    for k, v in sorted(say["run_aware"].items(), key=lambda x: -x[1]):
        print(f"   {k:16s} {v}")
    print("\nKÖK-TESLİM master (crop-stack/slit-scan):")
    for k, v in sorted(say["kok"].items(), key=lambda x: -x[1]):
        print(f"   {k:16s} {v}")
    print(f"\n=== KANONİK-KARAR KANITI: run-aware SAĞLIKLI ama kök BOŞ/YOK: {daha_iyi_run_aware} segment ===")
    for f, seg, d in ornek:
        print(f"   {f:40s} {seg:6s} {d}")
    print(f"\nSONUÇ: run-aware'ı kanonik yapmak {daha_iyi_run_aware} segmenti anında 'sağlıklı-master'a çevirir.")


if __name__ == "__main__":
    olc()
