#!/usr/bin/env python3
"""GİRİŞ ölçüm scripti (G6) — olc_pool.py'nin giriş karşılığı.

GT (veri/gt.json, İNSAN doğrulaması — gt_topla.py taslağından doldurulur)
yoksa KOŞMAZ: "giriş çalışıyor" ile "giriş doğru okuyor" aynı şey değildir;
GT'siz sayı üretmek dürüst değildir.

METRİK ŞEKLİ ÇIKIŞTAN FARKLI (EKSIKLER G6 uyarısı): sınır İKİ uçlu —
başlangıç VE bitiş sapması ayrı ölçülür. Çıkışın asimetrik politikası
(erken≤120 / geç≤20) buraya KOPYALANMAZ:
  - girişte GEÇ başlangıç = jeneriğin başı (cast başı) kaçar — kayıp
  - girişte ERKEN başlangıç = film sahnesi havuza sızar — sahte veri
  yani iki yön de zararlı; asimetri başka biçimde konur.
KIRMIZI ÇİZGİ YOK — GT gelip dağılım görülünce Çağatay ile birlikte
konur. Bu script raporlar, hüküm vermez.

Kullanım:
  ../venv/bin/python olc_giris.py [--paralel 4] [--film AD]
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

BURASI = os.path.dirname(os.path.abspath(__file__))                  # olcum/giris
SRC = os.path.join(os.path.dirname(os.path.dirname(BURASI)), "src")  # Allstar/kobe/src
sys.path.insert(0, SRC)

VERI = os.path.join(BURASI, "veri")
YATAK = "/opt/mitas/Allstar/kobe/havuz/giris"


def _isci(gorev: tuple) -> dict:
    """Paralel işçi (spawn): sinir.bul koşar. GT'yi ASLA görmesin — yalnız ölçüm."""
    ad, d = gorev
    from giris import sinir
    b = sinir.bul(d)
    return {"film": ad,
            "bulundu": b.get("bulundu"),
            "bas": b.get("baslangic_kare"), "bit": b.get("bitis_kare"),
            "guven": b.get("guven"),
            "kaynak": (b.get("kanit") or {}).get("sinir_kaynagi")}


def main() -> int:
    gt_yolu = os.path.join(VERI, "gt.json")
    if not os.path.exists(gt_yolu):
        print("[hata] veri/gt.json YOK — giriş ölçümü GT'siz koşmaz (G5). "
              "Önce gt_topla.py, sonra insan doğrulaması.")
        return 1
    gt = {f["film"]: f for f in json.load(open(gt_yolu, encoding="utf-8"))["filmler"]
          if f.get("karar")}    # karar null olanlar (doldurulmamış) dışarıda kalır

    tekil, paralel = None, 1
    for i, a in enumerate(sys.argv):
        if a == "--film" and i + 1 < len(sys.argv):
            tekil = sys.argv[i + 1]
        if a == "--paralel" and i + 1 < len(sys.argv):
            paralel = max(1, int(sys.argv[i + 1]))

    isler = []
    for d in sorted(glob.glob(os.path.join(YATAK, "*/"))):
        ad = os.path.basename(d.rstrip("/"))
        if ad not in gt:
            continue
        if tekil and tekil not in ad:
            continue
        isler.append((ad, d.rstrip("/")))

    if not isler:
        print(f"[hata] GT ile yatak kesişimi boş — GT'de adı geçen filmler yatakta yok?")
        return 1

    t0 = time.time()
    if paralel > 1:
        import multiprocessing as mp
        havuz = mp.get_context("spawn").Pool(paralel)
        try:
            kayitlar = list(havuz.imap_unordered(_isci, isler))
        finally:
            havuz.close()
            havuz.join()
    else:
        kayitlar = [_isci(g) for g in isler]

    # ── metrik: iki uçlu sapma + red doğruluğu ──────────────────────────
    n = red_dogru = red_toplam = var_dogru = var_toplam = 0
    sapmalar = []
    for k in kayitlar:
        g = gt[k["film"]]
        n += 1
        if g["karar"] == "jenerik_yok":
            red_toplam += 1
            red_dogru += (not k["bulundu"])
            if k["bulundu"]:
                sapmalar.append({"film": k["film"], "kusur": "sahte_bulundu",
                                 "oneri_bas": k["bas"], "oneri_bit": k["bit"]})
        else:
            var_toplam += 1
            if not k["bulundu"]:
                sapmalar.append({"film": k["film"], "kusur": "kacirildi"})
                continue
            var_dogru += 1
            db = k["bas"] - g["gercek_bas_kare"]   # + = geç başlangıç (cast başı kaybı)
            dk = k["bit"] - g["gercek_bit_kare"]   # + = geç bitiş (sahne sızar)
            sapmalar.append({"film": k["film"], "bas_sapma": db, "bit_sapma": dk,
                             "kaynak": k["kaynak"], "guven": k["guven"]})

    def _istatistik(alan: str) -> dict:
        degerler = [s[alan] for s in sapmalar if s.get(alan) is not None]
        if not degerler:
            return {"n": 0}
        return {"n": len(degerler),
                "ort_mutlak": round(sum(abs(v) for v in degerler) / len(degerler), 1),
                "min": min(degerler), "maks": max(degerler)}

    rapor = {"kapsam": n, "sure_sn": round(time.time() - t0),
             "jenerik_var": {"n": var_toplam, "bulundu": var_dogru},
             "jenerik_yok_red": {"n": red_toplam, "dogru": red_dogru},
             "baslangic_sapma_kare": _istatistik("bas_sapma"),
             "bitis_sapma_kare": _istatistik("bit_sapma"),
             "kaynak_dagilimi": {k: sum(1 for r in kayitlar
                                        if r.get("kaynak") == k and r["bulundu"])
                                 for k in ("tespit", "sabit")},
             "not": "kırmızı çizgi YOK — dağılım görülünce Çağatay ile konur (G6)",
             "filmler": kayitlar, "sapmalar": sapmalar}
    cikti = os.path.join(VERI, "olcum_giris_son.json")
    json.dump(rapor, open(cikti, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"KAPSAM {n}  jenerik-var: {var_dogru}/{var_toplam} bulundu  "
          f"kredisiz-red: {red_dogru}/{red_toplam}")
    for alan, etiket in (("baslangic_sapma_kare", "başlangıç"),
                         ("bitis_sapma_kare", "bitiş")):
        s = rapor[alan]
        if s.get("n"):
            print(f"  {etiket} sapması: ort|Δ|={s['ort_mutlak']} kare, "
                  f"[{s['min']:+d} .. {s['maks']:+d}]")
    print(f"→ {cikti}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
