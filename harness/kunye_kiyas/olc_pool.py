#!/usr/bin/env python3
"""Büyük-havuz ölçümü: tespit_v5 vs doğrulanmış 118-film GT.

Kapsam-farkındalıklı: kareleri henüz inmemiş filmleri atlar ve raporlar.
Kullanım:
  olc_pool.py                 # tüm mevcut filmler
  olc_pool.py --sadece-hatalar  # GT'de karar!=dogru olan 31 film
  olc_pool.py --film TAKKELİ    # ad-parçası eşleşen tek film (ayrıntılı)
  olc_pool.py --paralel 6       # 6 işçi süreçle (spawn; det-önbellekle birleşince hızlı)
"""
import glob, json, os, sys, time

os.environ.setdefault("OMP_NUM_THREADS", "4")   # paralel işçilerde çekirdek taşmasını önle

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
import figo as co

V = os.path.join(BURASI, "veri")
KOK = "/opt/mitas/data/jenerik_havuz/pool_frames"
TOL = 20


def norm(s: str) -> str:
    return s.replace("’", "'").split(" (")[0].strip()


def _isci(gorev: tuple) -> dict:
    """Paralel işçi: (film_adi, klasor, gercek_onset) → ölçüm kaydı.
    spawn ile taze süreçte koşar; paddle her işçide bir kez init olur."""
    ad, p, go = gorev
    import figo as co_w
    r = co_w.tespit_v5(p)
    return {"film": ad, "gt": go, "tahmin": r.start_frame,
            "yontem": r.yontem, "notlar": r.notlar}


def _isci_yerel(co_mod, gorev: tuple) -> dict:
    ad, p, go = gorev
    r = co_mod.tespit_v5(p)
    return {"film": ad, "gt": go, "tahmin": r.start_frame,
            "yontem": r.yontem, "notlar": r.notlar}


def main() -> int:
    gt = json.load(open(f"{V}/dogrulama_sonuc.json", encoding="utf-8"))["filmler"]
    try:  # kaynak dosyası yanlış-içerikli filmler (görsel teyitli) ölçüm dışı
        dis = {norm(f) for f in json.load(open(f"{V}/dislanan.json", encoding="utf-8"))["filmler"]}
    except Exception:
        dis = set()
    gt = [x for x in gt if norm(x["film"]) not in dis]
    klas = {norm(os.path.basename(p.rstrip("/"))): p
            for p in sorted(glob.glob(f"{KOK}/*/"))}
    sadece_hata = "--sadece-hatalar" in sys.argv
    tekil = None
    if "--film" in sys.argv:
        tekil = sys.argv[sys.argv.index("--film") + 1]
    paralel = 1
    if "--paralel" in sys.argv:
        paralel = max(1, int(sys.argv[sys.argv.index("--paralel") + 1]))

    n_kapsam = n_dogru = 0
    kv = {"n": 0, "dogru": 0}   # kredi-var alt-küme
    ky = {"n": 0, "dogru": 0}   # kredi-yok alt-küme (KIRMIZI ÇİZGİ)
    hatalar, eksikler, isler = [], [], []
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
        isler.append((ad, p, x["gercek_onset"]))

    if paralel > 1 and not tekil:
        import multiprocessing as mp
        havuz = mp.get_context("spawn").Pool(paralel)
        try:
            kayitlar = list(havuz.imap_unordered(_isci, isler))
        finally:
            havuz.close()
            havuz.join()
    else:
        kayitlar = [_isci_yerel(co, g) for g in isler]

    for k in kayitlar:
        go, pred = k["gt"], k["tahmin"]
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
            hatalar.append({**k, "sapma": (pred - go) if (go != -1 and pred != -1) else None})
        if tekil:
            print(f"{k['film']}\n  gt={go} tahmin={pred} yöntem={k['yontem']}\n  not={k['notlar']}")
    hatalar.sort(key=lambda h: -abs(h["sapma"]) if h["sapma"] is not None else 0)
    # ÜRETİM SKORU (Çağatay politikası 2026-07-23): ERKEN kabul edilebilir
    # (fazla kare zararsız), GEÇ kabul edilemez (cast'in başı atlanır).
    # Asimetrik tolerans: erken ≤120 kare (60 sn) OK, geç ≤20 kare OK.
    ERKEN_TOL, GEC_TOL = 120, 20
    uretim_dogru = n_dogru
    for h in hatalar:
        s = h.get("sapma")
        if s is not None and -ERKEN_TOL <= s <= GEC_TOL:
            uretim_dogru += 1          # simetrikte hata, üretimde kabul
    rapor = {"kapsam": n_kapsam, "dogru": n_dogru,
             "genel": round(100 * n_dogru / max(1, n_kapsam), 1),
             "uretim": {"dogru": uretim_dogru,
                        "pct": round(100 * uretim_dogru / max(1, n_kapsam), 1),
                        "erken_tol": ERKEN_TOL, "gec_tol": GEC_TOL},
             "kredi_var": kv, "kredi_yok": ky,
             "eksik": len(eksikler), "sure_sn": round(time.time() - t0),
             "hatalar": hatalar}
    json.dump(rapor, open(f"{V}/olcum_son.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\nKAPSAM {n_kapsam} (eksik {len(eksikler)})  "
          f"GENEL {n_dogru}/{n_kapsam} = %{rapor['genel']}"
          f"   ÜRETİM {uretim_dogru}/{n_kapsam} = %{rapor['uretim']['pct']}"
          f" (erken≤{ERKEN_TOL} OK / geç≤{GEC_TOL})")
    print(f"  kredi-var: {kv['dogru']}/{kv['n']}   "
          f"kredi-yok: {ky['dogru']}/{ky['n']}  (kırmızı çizgi ≥29/30)")
    for h in hatalar[:40]:
        s = f"{h['sapma']:+d}" if h["sapma"] is not None else "  - "
        print(f"  {s:>5}  gt={h['gt']:>5} v5={h['tahmin']:>5}  {h['film'][:44]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
