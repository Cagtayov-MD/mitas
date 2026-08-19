# -*- coding: utf-8 -*-
"""Kobe kulesi toplu çalıştırıcı.

sheriff/output/ altındaki tüm film klasörlerini tarar ve her film için
hem 'giris' hem 'cikis' bölümlerinde Kobe kulesini koşturur:
  kobe tek --kareler <output_koku>/<film_id>/<bolum> --film-id <film_id> --uret kare --bolum <bolum>

Kullanım:
  /home/cagatay/Programlar/mitas/Allstar/kobe/venv/bin/python run_kobe_all.py
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

KULE_KOK = Path(__file__).resolve().parent
SHERIFF_OUTPUT = Path("/home/cagatay/Programlar/mitas/Allstar/sheriff/output")
KOBE_EXEC = KULE_KOK / "kobe"
KOBE_OUT = KULE_KOK / "out"

def main():
    ap = argparse.ArgumentParser(description="Kobe kulesi toplu çalıştırıcı")
    ap.add_argument("--sheriff-output", type=Path, default=SHERIFF_OUTPUT, help="Sheriff output kök dizini")
    ap.add_argument("--atla-var", action="store_true", default=True, help="_TAMAM varsa atla")
    ap.add_argument("--force", action="store_true", help="Var olanları yeniden çalıştır")
    args = ap.parse_args()

    atla_var = args.atla_var and not args.force
    sheriff_output = args.sheriff_output

    if not sheriff_output.is_dir():
        sys.exit(f"[HATA] Sheriff output dizini bulunamadı: {sheriff_output}")

    film_dizinleri = sorted([d for d in sheriff_output.iterdir() if d.is_dir()])
    if not film_dizinleri:
        sys.exit(f"[HATA] {sheriff_output} içinde film dizini bulunamadı")

    print(f"[KOBE BATCH] Toplam {len(film_dizinleri)} film işlenecek.")
    print(f"  Kaynak: {sheriff_output}")
    print(f"  Çıktı : {KOBE_OUT}")
    print(f"  Atla  : {'Evet' if atla_var else 'Hayır'}\n")

    toplam_basarili = 0
    toplam_atlanan = 0
    toplam_ariza = 0
    t0_toplam = time.time()

    for i, film_dir in enumerate(film_dizinleri, 1):
        film_id = film_dir.name
        print(f"[{i}/{len(film_dizinleri)}] Film: {film_id}")

        for bolum in ("giris", "cikis"):
            kare_dir = film_dir / bolum
            if not kare_dir.is_dir():
                print(f"  - {bolum}: kare dizini yok, atlandı.")
                continue

            tamam_file = KOBE_OUT / film_id / bolum / "_TAMAM"
            if atla_var and tamam_file.exists():
                print(f"  — {bolum}: _TAMAM var, atlandı.")
                toplam_atlanan += 1
                continue

            cmd = [
                str(KOBE_EXEC), "tek",
                "--kareler", str(kare_dir),
                "--film-id", film_id,
                "--uret", "kare",
                "--bolum", bolum
            ]

            t0 = time.time()
            res = subprocess.run(cmd, capture_output=True, text=True)
            gecen = round(time.time() - t0, 1)

            if res.returncode == 0:
                toplam_basarili += 1
                # kobe.json oku
                json_file = KOBE_OUT / film_id / bolum / "kobe.json"
                durum_str = "OK"
                if json_file.exists():
                    import json
                    try:
                        data = json.loads(json_file.read_text(encoding="utf-8"))
                        durum_str = f"{data.get('durum')} (başlangıç={data.get('baslangic_kare')}, güven={data.get('guven')})"
                    except Exception:
                        pass
                print(f"  ✓ {bolum}: {durum_str} ({gecen}s)")
            else:
                toplam_ariza += 1
                err_msg = res.stderr.strip() or res.stdout.strip()
                print(f"  ✗ {bolum}: ARIZA ({gecen}s) -> {err_msg[:150]}")

    gecen_toplam = round(time.time() - t0_toplam, 1)
    print("\n" + "="*50)
    print(f"[KOBE BATCH ÖZET] Toplam Geçen Süre: {gecen_toplam}s")
    print(f"  Başarılı : {toplam_basarili}")
    print(f"  Atlanan  : {toplam_atlanan}")
    print(f"  Arıza    : {toplam_ariza}")

if __name__ == "__main__":
    main()
