#!/usr/bin/env python3
"""M10 kapanış kanıt zinciri (orkestratör aracı).

1. Sağlık ×2 (determinizm)  2. FLIP kontrolü: K3-sonrası sağlıklı olup şimdi
sağlıksız düşen var mı (şart: 0)  3. G0: önceden-sağlıklı filmlerde atlas
ateşlemesi dökümü (hedef 0; her ateşleme listelenir — rec'e girip atılan dahil)
4. Özet JSON.  (bit-parite ayrı pytest ile koşulur.)
"""
import glob
import json
import os
import subprocess
import sys

BURASI = os.path.dirname(os.path.abspath(__file__))
EX = "/opt/mitas/data/master_ex"
ARSIV = f"{EX}/_k3_arsiv"
PY = "/opt/mitas/venvs/ocr/bin/python"


def saglik_olc() -> dict:
    r = subprocess.run([PY, f"{BURASI}/saglik.py", EX], capture_output=True,
                       text=True, timeout=1800)
    ilk = r.stdout.splitlines()[0] if r.stdout else ""
    payda = int(ilk.split("/")[1].split()[0]) if "/" in ilk else 0
    pay = int(ilk.split("/")[0]) if "/" in ilk else 0
    return {"ozet": ilk, "saglikli": pay, "toplam": payda, "cikti": r.stdout}


def saglikli_kume(kok: str) -> set:
    """saglik.py'nin JSON çıktısı varsa onu kullan; yoksa ihlal-listesinden türet."""
    r = subprocess.run([PY, f"{BURASI}/saglik.py", kok], capture_output=True,
                       text=True, timeout=1800)
    ihlalli = set()
    for sat in r.stdout.splitlines():
        sat = sat.strip()
        if "ihlaller=" in sat:
            ihlalli.add(sat.split()[0])
    tum = {os.path.basename(p.rstrip("/")) for p in glob.glob(f"{kok}/*/")
           if not os.path.basename(p.rstrip("/")).startswith("_")}
    return tum - ihlalli


def main() -> int:
    print("=== 1) Sağlık ×2 (determinizm) ===")
    a = saglik_olc()
    b = saglik_olc()
    print("koşu-1:", a["ozet"])
    print("koşu-2:", b["ozet"])
    determinist = a["ozet"] == b["ozet"]
    print("determinizm:", "OK" if determinist else "FARKLI ✗")

    print("\n=== 2) FLIP kontrolü (K3-sonrası sağlıklı → şimdi sağlıksız) ===")
    once = saglikli_kume(ARSIV)
    simdi = saglikli_kume(EX)
    dusen = sorted(once - simdi)
    print(f"K3-sonrası sağlıklı: {len(once)} | şimdi sağlıklı: {len(simdi)} | DÜŞEN: {len(dusen)}")
    for f in dusen[:20]:
        print("  DÜŞTÜ:", f)

    print("\n=== 3) G0: önceden-sağlıklı filmlerde atlas ateşlemesi ===")
    atesleyen = []
    for f in sorted(once):
        my = f"{EX}/{f}/manifest.json"
        try:
            m = json.load(open(my, encoding="utf-8"))
        except Exception:
            continue
        ag = [x for x in (m.get("atlas_gruplari") or []) if isinstance(x, dict)]
        if ag:
            gecen = sum(1 for x in ag if x.get("rec_dogrulama") == "gecti")
            atesleyen.append((f, len(ag), gecen))
    print(f"atlas-ateşleyen önceden-sağlıklı film: {len(atesleyen)} (hedef 0)")
    for f, n, g in atesleyen[:20]:
        print(f"  ATEŞLEDİ: {f} grup={n} geçen={g}")

    print("\n=== ÖZET ===")
    ozet = {
        "saglik": a["ozet"],
        "determinizm": determinist,
        "flip_sayisi": len(dusen),
        "flip_listesi": dusen,
        "g0_atesleyen": len(atesleyen),
        "g0_listesi": [f for f, _, _ in atesleyen],
    }
    json.dump(ozet, open(f"{EX}/kapanis_kaniti.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in ozet.items()
                      if k in ("saglik", "determinizm", "flip_sayisi", "g0_atesleyen")},
                     ensure_ascii=False))
    return 0 if (determinist and not dusen) else 1


if __name__ == "__main__":
    sys.exit(main())
