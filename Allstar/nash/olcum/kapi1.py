#!/usr/bin/env python3
"""KAPI 1 — taşıma kapısı (Faz 1) → entegrasyon kapısı (Faz 3 sonrası).

⚠ ANLAMI DEĞİŞTİ. Faz 3 sökümünden (2026-08-14) sonra üretim
(`pilot_hat.havuz_derle_dizin`) kulenin kendi `secim.havuz_derle_dizin`'ine
DEVREDİYOR — yani kıyasın iki tarafı artık AYNI KOD. Bu kapı bundan böyle
"iki bağımsız uygulama aynı cevabı veriyor mu"yu ölçmez; **üretimin
yorumlayıcısından (venvs/ocr) kuleye giden zincirin ayakta olduğunu** ölçer.
Görevini Faz 1'de yaptı: taşımanın sadık olduğunu 29/29 sapma sıfır ile
kanıtladı, e1a201d5 kusurunu o kanıt açığa çıkardı.

Kule, BUGÜNKÜ üretim koduyla aynı sayıları veriyor mu?

Nash'in havuz yarısı saf numpy/cv2: model yok, ağ yok, rastgelelik yok. Doğru
taşındıysa aynı karelerde aynı sayıları vermek ZORUNDA.

İKİ ÖLÇÜM, İKİSİ AYNI ŞEY DEĞİL:

  1. ASIL KAPI (sert) — kule vs `olcum/referans_eski.json`
     Referans BUGÜNKÜ üretim kodundan (`pilot_hat.havuz_derle_dizin`,
     `venvs/ocr`) üretildi. Eşyayı eşyayla kıyaslar. Sapma > 0 → taşıma hatalı
     veya venv pini yanlış. İLERLENMEZ.

  2. TARİHÎ SAPMA (bilgi) — kule vs `outputs/olcum_yatagi/.../olcum_kol_frame.json`
     O dosyalar 2026-07-31'de üretildi; `e1a201d5` (2026-08-05) `film_esigi`'nin
     Otsu aramasını yeniden yazdı ve CEVABI DEĞİŞTİRDİ. Buradaki fark taşımanın
     değil o commit'in eseridir — kapıyı DÜŞÜRMEZ, ama raporlanır ki görünmez
     kalmasın.

Koşum:  Allstar/nash/venv/bin/python olcum/kapi1.py
Önce :  /opt/mitas/venvs/ocr/bin/python olcum/referans_uret.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KULE / "src"))

import secim as secim_mod  # noqa: E402

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
YATAK = PROJE / "outputs" / "olcum_yatagi" / "klipler"
REFERANS = KULE / "olcum" / "referans_eski.json"
ALANLAR = ("kare", "esik", "grup", "alarm", "sayfa", "ikinci_gecis_ek")
YUZEYLER = (("cikis", "frames/cikis_jenerik"), ("giris", "frames/giris"))
# Havuz istatistigi ornekleme ONCESI hesaplanir; bu ayarlar kapiyi etkilemez.
AYAR = {"tavan": 100, "son_kare_zorla": True, "ham_kuyruk": 0}


def _tarihi_havuz(film_dizin: Path) -> dict | None:
    p = film_dizin / "olcum_kol_frame.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("havuz")
    except Exception:
        return None


def kos() -> int:
    if not REFERANS.is_file():
        print(f"HATA: referans yok: {REFERANS}\n"
              f"Once: /opt/mitas/venvs/ocr/bin/python olcum/referans_uret.py",
              file=sys.stderr)
        return 2
    ref = json.loads(REFERANS.read_text(encoding="utf-8"))
    print(f"KAPI 1 · referans {ref['uretildi']} (python {ref['yorumlayici']})\n")

    kiyaslanan = sapan = 0
    sapmalar: list[dict] = []
    tarihi_sapma: list[dict] = []

    for film_ad, yuzeyler in sorted(ref["filmler"].items()):
        for ad, alt in YUZEYLER:
            r = yuzeyler.get(ad) or {}
            if r.get("yok"):
                continue
            t0 = time.time()
            s = secim_mod.sec(YATAK / film_ad / alt, AYAR, "*.png")
            sure = time.time() - t0
            bizim = (s.kanit or {}).get("havuz")
            etiket = f"{film_ad[:34]:34s} {ad:5s}"

            if bizim is None:
                sapan += 1
                sapmalar.append({"film": film_ad, "yuzey": ad,
                                 "sebep": s.hata or "havuz_yok"})
                print(f"  [SAPMA] {etiket} havuz uretilmedi ({s.hata})")
                continue

            kiyaslanan += 1
            fark = {a: (r["havuz"].get(a), bizim.get(a)) for a in ALANLAR
                    if r["havuz"].get(a) != bizim.get(a)}
            if fark:
                sapan += 1
                sapmalar.append({"film": film_ad, "yuzey": ad, "fark": fark})
                print(f"  [SAPMA] {etiket} {fark}")
            else:
                print(f"  [ayni ] {etiket} kare={bizim['kare']:4d} "
                      f"esik={bizim['esik']:3d} sayfa={bizim['sayfa']:4d} "
                      f"+{bizim['ikinci_gecis_ek']:2d}  {sure:4.1f}s")

            # Tarihi sapma — yalniz cikis yuzeyinde referans var.
            if ad == "cikis":
                th = _tarihi_havuz(YATAK / film_ad)
                if th:
                    tf = {a: (th.get(a), bizim.get(a)) for a in ALANLAR
                          if th.get(a) != bizim.get(a)}
                    if tf:
                        tarihi_sapma.append({"film": film_ad, "fark": tf})

    print(f"\n{'=' * 72}")
    print(f"ASIL KAPI   kiyaslanan: {kiyaslanan}   SAPAN: {sapan}")
    if tarihi_sapma:
        print(f"\nTARIHI SAPMA (e1a201d5, 2026-08-05 — kapiyi dusurmez): "
              f"{len(tarihi_sapma)} film")
        for t in tarihi_sapma:
            print(f"  · {t['film']}: {t['fark']}")

    rapor = {"zaman": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "referans_uretildi": ref["uretildi"],
             "kiyaslanan": kiyaslanan, "sapan": sapan, "sapmalar": sapmalar,
             "tarihi_sapma": tarihi_sapma}
    (KULE / "raporlar").mkdir(exist_ok=True)
    (KULE / "raporlar" / "kapi1.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")

    if sapan:
        print("\nKAPI 1 GECILMEDI — tasima hatali veya venv pini yanlis.")
        return 1
    print("\nKAPI 1 GECILDI — havuz bit duzeyinde ayni.")
    return 0


if __name__ == "__main__":
    sys.exit(kos())
