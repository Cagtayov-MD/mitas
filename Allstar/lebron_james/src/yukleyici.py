"""Kare listeleme / okuma / yazma — motorun DIŞINDA, bilerek.

Bu dosya PaddleOCR'a dokunmaz; cv2 yalnız gerçekten görüntü okunurken TEMBEL
import edilir. Sebep: sıralama kuralı kulenin en sessiz kusuruydu (spec 1.4a)
ve testi GPU'suz koşabilmeli. Motorun içine gömülü kalsaydı sıralamayı test
etmek için 11 GB'lık çalışma zamanı gerekirdi.
"""
from __future__ import annotations

import re
from pathlib import Path

DESEN = ("*.png", "*.jpg", "*.jpeg")


def nat_sort_key(yol: str | Path):
    """Dosya adındaki SON sayıya göre sırala.

    db_compose_master.nat_sort_key'in birebir aynısı — üretimin sıralaması
    budur (master_png_monitor.py:326 bu anahtarla sıralıyor). Kaynak motor
    ise düz `sorted()` kullanıyordu; sıfır dolgulu adlarda ikisi aynı sonucu
    verdiği için fark bugüne kadar görünmedi. Dolgusuz adda (kare_9 vs
    kare_10) sözlük sırası kareleri yanlış diziyor ve master SESSİZCE bozuluyor.
    """
    ad = Path(yol).name
    sayilar = re.findall(r"\d+", ad)
    return (int(sayilar[-1]) if sayilar else -1, ad)


ALT_BANT_SINIFI = "recall_altbant"


def _alt_bant_adlari(d: Path) -> set[str]:
    """Kobe'nin `_sinif.json` manifestosundan alt-bant kurtarmalarını oku.

    NEDEN AYIKLIYORUZ: LeBron bir KAYMA birleştiricisidir. Alt-bant
    kurtarmaları aynı DURAN kartın neredeyse aynı kopyalarıdır; havuza
    girdiklerinde kayma ölçümünü sulandırırlar. Ölçüldü (2026-08-20,
    Çiçek Taksi b2 girişi): havuz 93→127 kareye çıkınca master
    6087 px / 21 segment yerine 449 px / 1 segment'e ÇÖKTÜ.

    Bu kareler ATILMIYOR — Kobe'nin havuzunda duruyorlar ve Nash ile
    Jordan onları okuyor (ikisi de kareyi TEK TEK okur, kaymaya ihtiyaç
    duymaz). Yalnız LeBron'un birleştirmesinden çıkarılıyorlar.
    Manifesto yoksa hiçbir şey ayıklanmaz — eski davranış aynen sürer.
    """
    m = d / "_sinif.json"
    if not m.is_file():
        return set()
    try:
        import json
        veri = json.loads(m.read_text(encoding="utf-8"))
    except Exception:                                     # noqa: BLE001
        return set()
    if not isinstance(veri, dict):
        return set()
    return {ad for ad, sinif in veri.items() if sinif == ALT_BANT_SINIFI}


def kareler(dizin: str | Path) -> list[Path]:
    """Dizindeki kare dosyaları — DOĞAL sırada. Okumaz, yalnız listeler.

    Kobe manifestosu varsa alt-bant kurtarmaları ELENİR (bkz.
    `_alt_bant_adlari` gerekçesi).
    """
    d = Path(dizin)
    if not d.is_dir():
        return []
    bulunan: list[Path] = []
    for desen in DESEN:
        bulunan.extend(d.glob(desen))
    alt_bant = _alt_bant_adlari(d)
    if alt_bant:
        bulunan = [p for p in bulunan if p.name not in alt_bant]
    return sorted(bulunan, key=nat_sort_key)


def kare_oku(yol: str | Path):
    """Unicode-güvenli okuma.

    cv2.imread non-ASCII yolda (İHTİRAS'taki 'İ') SESSİZCE None döner —
    üretim bu yüzden imdecode(fromfile(...)) kullanıyor
    (db_compose_master.rd_cached). Kule aynısını yapar.
    """
    import cv2
    import numpy as np
    try:
        return cv2.imdecode(np.fromfile(str(yol), np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None


def kareleri_yukle(dizin: str | Path):
    """(görüntüler, bulunan_dosya_sayisi). Her dosya BİR KEZ okunur.

    Kaynak motor her PNG'yi iki kez imread ediyordu (biri koşulda, biri
    listede) — 659 karelik havuzda 1318 disk okuması (spec 1.4b).

    İkinci dönüş değeri "dizinde dosya var mıydı" sorusunu cevaplar; main.py
    bununla GIRDI_HATASI ile KARE_OKUNAMADI'yı ayırır.
    """
    yollar = kareler(dizin)
    ims = []
    for p in yollar:
        im = kare_oku(p)
        if im is not None:
            ims.append(im)
    return ims, len(yollar)


def yaz(yol: str | Path, goruntu) -> None:
    """PNG yaz — unicode-güvenli (db_compose_master.wr ile aynı)."""
    import cv2
    ok, kodlu = cv2.imencode(".png", goruntu)
    if not ok:
        raise RuntimeError(f"PNG encode basarisiz: {yol}")
    kodlu.tofile(str(yol))
