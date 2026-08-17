#!/usr/bin/env python3
"""GİRİŞ GT toplama aracı (G5'in hazırlığı) — motor TEKLİF eder, insan karar verir.

NE YAPAR: yataktaki her film için `giris.sinir.bul()` koşar, önerilen
başlangıç/bitiş sınırının ÇEVRESİNDE hangi karelere bakılacağını listeler,
`veri/gt_taslak.json` yazar. Çağatay tekliflere bakıp `veri/gt.json`'a
gerçek sınırları yazar (~30 sn/film hedefi, EKSIKLER G5 tarifi).

NE YAPMAZ: GT ÜRETMEZ. `gercek_*` alanları boş kalır — doldurulmadan
ölçüm (olc_giris.py) koşmaz. Motor önerisi GT OLAMAZ (döngüsel olur).

Kullanım:
  ../venv/bin/python gt_topla.py            # tüm yatak
  ../venv/bin/python gt_topla.py KOBRA      # ad-parçası eşleşen tek film
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

BURASI = os.path.dirname(os.path.abspath(__file__))            # Allstar/kobe/olcum/giris
SRC = os.path.join(os.path.dirname(os.path.dirname(BURASI)), "src")  # Allstar/kobe/src
sys.path.insert(0, SRC)          # from giris import sinir (giris kendi kök yolunu kurar)

from giris import sinir  # noqa: E402

YATAK = "/opt/mitas/Allstar/kobe/havuz/giris"
VERI = os.path.join(BURASI, "veri")
CEVRE = 10      # önerilen sınırın ± kaç karesi listelensin (insan gözü için)


def _kare_yollari(dizin: str) -> list[str]:
    return sorted(glob.glob(os.path.join(dizin, "*.png")))


def _cevre(yollar: list[str], kare: int | None) -> list[str]:
    """Önerilen karenin ±CEVRE komşuluğundaki dosya ADLARI (yol değil)."""
    if kare is None:
        return []
    import re
    adlar = []
    for y in yollar:
        m = re.search(r"(\d+)(?=\.[a-zA-Z]+$)", y)
        if m and abs(int(m.group(1)) - kare) <= CEVRE:
            adlar.append(os.path.basename(y))
    return adlar


def main() -> int:
    os.makedirs(VERI, exist_ok=True)
    tekil = None
    for i, a in enumerate(sys.argv):
        if a == "--film":
            tekil = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
    filmler = []
    for d in sorted(glob.glob(os.path.join(YATAK, "*/") )):
        if not tekil or tekil in os.path.basename(d.rstrip("/")):
            filmler.append(d.rstrip("/"))
    if not filmler:
        print(f"[hata] yatakta film yok: {YATAK} (once yatak_kur.sh)")
        return 1

    taslak = {"tarif": "gercek_bas_kare/gercek_bit_kare alanlarini Çağatay doldurur. "
                       "jenerik yoksa karar=jenerik_yok ve gercek_*=-1. KARE NO mutlaktır "
                       "(dosya adindaki sayi, 2 kare/sn).",
              "filmler": []}
    t0 = time.time()
    for d in filmler:
        ad = os.path.basename(d)
        yollar = _kare_yollari(d)
        t1 = time.time()
        b = sinir.bul(d)   # istisna firlatirsa arac durur — teklif üretilemiyorsa sessiz geçilmez
        kaynak = (b.get("kanit") or {}).get("sinir_kaynagi", "?")
        kayit = {
            "film": ad,
            "kare_sayisi": len(yollar),
            "oneri": {"bulundu": b.get("bulundu"),
                      "baslangic_kare": b.get("baslangic_kare"),
                      "bitis_kare": b.get("bitis_kare"),
                      "guven": b.get("guven"),
                      "sinir_kaynagi": kaynak},
            # ——— AŞAĞISI İNSAN DOLDURUR (gt.json'a kopyala-yaz) ———
            "karar": None,             # "jenerik_var" | "jenerik_yok"
            "gercek_bas_kare": None,   # jenerik yoksa -1
            "gercek_bit_kare": None,   # jenerik yoksa -1
            "aciklama": "",
        }
        if b.get("bulundu"):
            kayit["oneri"]["bak_bas"] = _cevre(yollar, b.get("baslangic_kare"))
            kayit["oneri"]["bak_bit"] = _cevre(yollar, b.get("bitis_kare"))
        else:
            # öneri yok → insan tüm pencereye dağınık baksın: 15 sn'de bir kare
            kayit["oneri"]["bak_serbest"] = [os.path.basename(y) for y in yollar[::30]]
        taslak["filmler"].append(kayit)
        print(f"[teklif] {ad}: bulundu={b.get('bulundu')} "
              f"bas={b.get('baslangic_kare')} bit={b.get('bitis_kare')} "
              f"guven={b.get('guven')} kaynak={kaynak} ({time.time()-t1:.1f}s)")

    cikti = os.path.join(VERI, "gt_taslak.json")
    with open(cikti, "w", encoding="utf-8") as f:
        json.dump(taslak, f, ensure_ascii=False, indent=1)
    print(f"\n{len(filmler)} film, {time.time()-t0:.0f} sn → {cikti}")
    print("SONRA: taslaği veri/gt.json olarak kopyala, gercek_* alanlari doldur, "
          "olc_giris.py koş.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
