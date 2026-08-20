# -*- coding: utf-8 -*-
"""LeBron kulesi toplu çalıştırıcı.

Kobe'nin `out/` dizinini tarayarak kare havuzu oluşturulmuş tüm filmleri 
LeBron'a (derleyiciye) gönderir ve oluşturulan master PNG'leri
`out_masters/` klasörüne kopyalar.
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

KOBE_OUT = Path("/home/cagatay/Programlar/mitas/Allstar/kobe/out")
LEBRON_KULE = Path("/home/cagatay/Programlar/mitas/Allstar/lebron_james")
LEBRON_EXEC = LEBRON_KULE / "lebron"
LEBRON_OUT_MASTERS = LEBRON_KULE / "out"

def main():
    if not KOBE_OUT.is_dir():
        sys.exit(f"[HATA] Kobe çıktı dizini yok: {KOBE_OUT}")
    
    LEBRON_OUT_MASTERS.mkdir(parents=True, exist_ok=True)
    
    film_dizinleri = sorted([d for d in KOBE_OUT.iterdir() if d.is_dir()])
    print(f"[LEBRON BATCH] {len(film_dizinleri)} film kontrol edilecek.")
    
    toplam_master = 0
    t0_toplam = time.time()
    
    for i, film_dir in enumerate(film_dizinleri, 1):
        film_id = film_dir.name
        print(f"\n[{i}/{len(film_dizinleri)}] {film_id}")
        
        hedef_film_klasoru = LEBRON_OUT_MASTERS / film_id
        
        for bolum in ("giris", "cikis"):
            kareler_yolu = film_dir / bolum / "kareler"
            if not kareler_yolu.is_dir():
                print(f"  - {bolum}: kareler dizini yok, atlandı.")
                continue
                
            cmd = [
                str(LEBRON_EXEC), "tek",
                "--kareler", str(kareler_yolu),
                "--film-id", film_id,
                "--bolum", bolum
            ]
            
            t0 = time.time()
            # LeBron çalıştırılıyor
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(LEBRON_KULE))
            gecen = round(time.time() - t0, 1)
            
            # LeBron okuyucu fazında olmadığı için ARIZA dönebilir, 
            # ancak master.png kompozisyon aşamasında oluşturulmuş olabilir.
            beklenen_master = LEBRON_KULE / "out" / film_id / bolum / "master.png"
            
            if beklenen_master.exists():
                hedef_film_klasoru.mkdir(parents=True, exist_ok=True)
                kopya_yolu = hedef_film_klasoru / f"{bolum}_master.png"
                shutil.copy2(beklenen_master, kopya_yolu)
                
                print(f"  ✓ {bolum}: Master PNG kopyalandı ({gecen}s) -> {kopya_yolu.name}")
                toplam_master += 1
            else:
                hata_msg = (res.stdout.strip() + "\n" + res.stderr.strip())[:200]
                print(f"  ✗ {bolum}: Master PNG OLUŞTURULAMADI ({gecen}s). Cikti:\n{hata_msg}")

    gecen_toplam = round(time.time() - t0_toplam, 1)
    print("\n" + "="*50)
    print(f"[LEBRON BATCH ÖZET] Toplam Süre: {gecen_toplam}s")
    print(f"  Üretilen ve kopyalanan master PNG sayısı: {toplam_master}")

if __name__ == "__main__":
    main()
