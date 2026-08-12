#!/usr/bin/env python3
"""Det-önbelleği ısıtıcı: tüm pool_frames filmlerinde tespit_v5'in kullandığı
kare örüntüsüyle (idx=0,2,4.. + kutu_serisi stride=2) SALT-DET koşar.
Ölçüm JSON'larına dokunmaz; sadece _det_cache.json dosyalarını doldurur."""
import glob
import multiprocessing as mp
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "4")
BURASI = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src")            # Allstar/kobe/src
sys.path.insert(0, BURASI)

KOK = "/opt/mitas/data/jenerik_havuz/pool_frames"


def isit(dizin: str) -> str:
    sys.path.insert(0, BURASI)
    import kutu as cb
    import motor as co
    g = co.kareler(dizin)
    if len(g) < 50:
        return f"[atla] {os.path.basename(dizin.rstrip('/'))}"
    t = time.time()
    idx = list(range(0, len(g), 2))
    alt_g = [g[i] for i in idx]
    cb.kutu_serisi(alt_g, stride=2)
    return f"[ok] {os.path.basename(dizin.rstrip('/'))[:40]} {round(time.time()-t,1)}s"


if __name__ == "__main__":
    dizinler = sorted(glob.glob(f"{KOK}/*/"))
    n_isci = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    havuz = mp.get_context("spawn").Pool(n_isci)
    try:
        for s in havuz.imap_unordered(isit, dizinler):
            print(s, flush=True)
    finally:
        havuz.close()
        havuz.join()
    print("ISITMA BİTTİ")
