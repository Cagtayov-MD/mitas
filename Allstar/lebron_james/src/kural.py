"""Kulenin KENDİ çıktısı hakkındaki hükümleri. Motorun dışında, bilerek.

Buradakiler ağır bağımlılık taşımaz (ne Paddle ne cv2) — çünkü bunlar ölçüm
değil KARAR, ve kararların testi 11 GB'lık çalışma zamanı gerektirmemeli.
"""
from __future__ import annotations

# saglik.py ile aynı canavar-boy tavanı. Bunun üstü → ARIZA(BOY_ASIMI).
H_MAKS = 45000

# Çöküş dedektörünün alt sınırı: bundan az karede hüküm verilmez.
COKME_MIN_KARE = 20


def cokmus(manifest: dict, kare_sayisi: int, kare_h: int) -> bool:
    """Motor 20+ kareyi tek ekrana çökertmiş mi?

    master_png_monitor._lebron_cokmus'ün (satır 132-136) birebir aynısı.
    Üç koşul birlikte aranır:
      * segment == 1      → motor hiç bölmemiş
      * kare >= 20        → az karede tek segment MEŞRUDUR (gerçek tek kart)
      * boy <= 2 x kare_h → 20+ karelik jenerik iki ekrana sığmaz

    Üretimde bu çıktı reddedilir ("kötü master yerine hiç"). Kural kule içinde
    yaşar ki her tüketici aynı testi yeniden yazmak zorunda kalmasın.
    """
    if manifest.get("segment") != 1 or kare_sayisi < COKME_MIN_KARE:
        return False
    boy = (manifest.get("size") or [None, None])[1]
    return bool(boy) and kare_h > 0 and boy <= 2 * kare_h
