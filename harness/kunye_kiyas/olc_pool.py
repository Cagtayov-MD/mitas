#!/usr/bin/env python3
"""Büyük-havuz ölçümü: tespit_v5 vs doğrulanmış 118-film GT.

Kapsam-farkındalıklı: kareleri henüz inmemiş filmleri atlar ve raporlar.
Kullanım:
  olc_pool.py                 # tüm mevcut filmler
  olc_pool.py --sadece-hatalar  # GT'de karar!=dogru olan 31 film
  olc_pool.py --film TAKKELİ    # ad-parçası eşleşen tek film (ayrıntılı)
"""
import glob, json, os, sys, time

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
import credit_onset as co

V = os.path.join(BURASI, "veri")
KOK = "/opt/mitas/data/jenerik_havuz/pool_frames"
TOL = 20


def norm(s: str) -> str:
    return s.replace("’", "'").split(" (")[0].strip()


def main() -> int:
    gt = json.load(open(f"{V}/dogrulama_sonuc.json", encoding="utf-8"))["filmler"]
    klas = {norm(os.path.basename(p.rstrip("/"))): p
            for p in sorted(glob.glob(f"{KOK}/*/"))}
    sadece_hata = "--sadece-hatalar" in sys.argv
    tekil = None
    if "--film" in sys.argv:
        tekil = sys.argv[sys.argv.index("--film") + 1]

    n_kapsam = n_dogru = 0
    kv = {"n": 0, "dogru": 0}   # kredi-var alt-küme
    ky = {"n": 0, "dogru": 0}   # kredi-yok alt-küme (KIRMIZI ÇİZGİ)
    hatalar, eksikler = [], []
    t0 = time.time()
    for x in gt:
        ad = norm(x["film"])
        if sadece_hata and x["karar"] == "dogru":
            continue
        if tekil and tekil not in ad:
            continue
        p = klas.get(ad)
        if not p or len(glob.glob(p + "*.png")) < 50:
            eksikler.append(ad)
            continue
        r = co.tespit_v5(p)
        go, pred = x["gercek_onset"], r.start_frame
        if go == -1:
            ky["n"] += 1
            ok = (pred == -1)
            ky["dogru"] += ok
        else:
            kv["n"] += 1
            ok = (pred != -1 and abs(pred - go) <= TOL)
            kv["dogru"] += ok
        n_kapsam += 1
        n_dogru += ok
        if not ok:
            hatalar.append({"film": ad, "gt": go, "tahmin": pred,
                            "sapma": (pred - go) if (go != -1 and pred != -1) else None,
                            "yontem": r.yontem, "notlar": r.notlar})
        if tekil:
            print(f"{ad}\n  gt={go} tahmin={pred} yöntem={r.yontem}\n  not={r.notlar}")
    hatalar.sort(key=lambda h: -abs(h["sapma"]) if h["sapma"] is not None else 0)
    rapor = {"kapsam": n_kapsam, "dogru": n_dogru,
             "genel": round(100 * n_dogru / max(1, n_kapsam), 1),
             "kredi_var": kv, "kredi_yok": ky,
             "eksik": len(eksikler), "sure_sn": round(time.time() - t0),
             "hatalar": hatalar}
    json.dump(rapor, open(f"{V}/olcum_son.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\nKAPSAM {n_kapsam} (eksik {len(eksikler)})  "
          f"GENEL {n_dogru}/{n_kapsam} = %{rapor['genel']}")
    print(f"  kredi-var: {kv['dogru']}/{kv['n']}   "
          f"kredi-yok: {ky['dogru']}/{ky['n']}  (kırmızı çizgi ≥30/31)")
    for h in hatalar[:40]:
        s = f"{h['sapma']:+d}" if h["sapma"] is not None else "  - "
        print(f"  {s:>5}  gt={h['gt']:>5} v5={h['tahmin']:>5}  {h['film'][:44]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
