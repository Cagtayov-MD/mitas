# -*- coding: utf-8 -*-
"""Kobe kulesi toplu çalıştırıcı.

sheriff/output/ altındaki tüm film klasörlerini tarar ve her film için
hem 'giris' hem 'cikis' bölümlerinde Kobe kulesini koşturur:
  kobe tek --kareler <output_koku>/<film_id>/<bolum> --film-id <film_id> --uret kare --bolum <bolum>

Kullanım:
  /home/cagatay/Programlar/mitas/Allstar/kobe/venv/bin/python run_kobe_all.py --isci 4
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import subprocess
import sys
import time
from pathlib import Path

KULE_KOK = Path(__file__).resolve().parent
SHERIFF_OUTPUT = Path("/home/cagatay/Programlar/mitas/Allstar/sheriff/output")
KOBE_EXEC = KULE_KOK / "kobe"
KOBE_OUT = KULE_KOK / "out"
ISCI_TAVANI = 4


def _isci_sayisi(value: str) -> int:
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("isci sayisi tamsayi olmali") from exc
    if not 1 <= count <= ISCI_TAVANI:
        raise argparse.ArgumentTypeError(f"isci sayisi 1-{ISCI_TAVANI} arasinda olmali")
    return count


def _calistir(job: tuple[str, str, Path]) -> dict:
    film_id, bolum, kare_dir = job
    cmd = [
        str(KOBE_EXEC), "tek",
        "--kareler", str(kare_dir),
        "--film-id", film_id,
        "--uret", "kare",
        "--bolum", bolum,
    ]
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    result = {"film_id": film_id, "bolum": bolum, "returncode": res.returncode,
              "gecen_sn": round(time.time() - t0, 1),
              "stdout": res.stdout, "stderr": res.stderr}
    if res.returncode == 0:
        json_file = KOBE_OUT / film_id / bolum / "kobe.json"
        result["durum"] = "OK"
        if json_file.exists():
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                result["durum"] = (
                    f"{data.get('durum')} (başlangıç={data.get('baslangic_kare')}, "
                    f"güven={data.get('guven')})")
            except (OSError, json.JSONDecodeError):
                pass
    else:
        result["durum"] = "ARIZA"
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Kobe kulesi toplu çalıştırıcı")
    ap.add_argument("--sheriff-output", type=Path, default=SHERIFF_OUTPUT, help="Sheriff output kök dizini")
    ap.add_argument("--atla-var", action="store_true", default=True, help="_TAMAM varsa atla")
    ap.add_argument("--force", action="store_true", help="Var olanları yeniden çalıştır")
    ap.add_argument("--isci", type=_isci_sayisi, default=ISCI_TAVANI,
                    help=f"Paralel Kobe işi (1-{ISCI_TAVANI}, varsayılan: {ISCI_TAVANI})")
    args = ap.parse_args(argv)

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
    print(f"  Atla  : {'Evet' if atla_var else 'Hayır'}")
    print(f"  İşçi  : {args.isci}/{ISCI_TAVANI}\n")

    toplam_basarili = 0
    toplam_atlanan = 0
    toplam_ariza = 0
    t0_toplam = time.time()

    jobs: list[tuple[str, str, Path]] = []
    for film_dir in film_dizinleri:
        film_id = film_dir.name
        for bolum in ("giris", "cikis"):
            kare_dir = film_dir / bolum
            if not kare_dir.is_dir():
                print(f"  - {film_id}/{bolum}: kare dizini yok, atlandı.")
                continue

            tamam_file = KOBE_OUT / film_id / bolum / "_TAMAM"
            if atla_var and tamam_file.exists():
                print(f"  — {film_id}/{bolum}: _TAMAM var, atlandı.")
                toplam_atlanan += 1
                continue
            jobs.append((film_id, bolum, kare_dir))

    with cf.ThreadPoolExecutor(max_workers=args.isci,
                               thread_name_prefix="kobe-batch") as executor:
        futures = {executor.submit(_calistir, job): job for job in jobs}
        for done, future in enumerate(cf.as_completed(futures), 1):
            result = future.result()
            film_id, bolum = result["film_id"], result["bolum"]
            if result["returncode"] == 0:
                toplam_basarili += 1
                print(f"[{done}/{len(jobs)}] ✓ {film_id}/{bolum}: "
                      f"{result['durum']} ({result['gecen_sn']}s)", flush=True)
            else:
                toplam_ariza += 1
                err_msg = result["stderr"].strip() or result["stdout"].strip()
                print(f"[{done}/{len(jobs)}] ✗ {film_id}/{bolum}: ARIZA "
                      f"({result['gecen_sn']}s) -> {err_msg[:150]}", flush=True)

    gecen_toplam = round(time.time() - t0_toplam, 1)
    print("\n" + "="*50)
    print(f"[KOBE BATCH ÖZET] Toplam Geçen Süre: {gecen_toplam}s")
    print(f"  Başarılı : {toplam_basarili}")
    print(f"  Atlanan  : {toplam_atlanan}")
    print(f"  Arıza    : {toplam_ariza}")

if __name__ == "__main__":
    main()
