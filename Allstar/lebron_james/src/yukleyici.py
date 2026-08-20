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


KARDES_TAVANI = 3      # kart başına yüklenecek EN FAZLA kare


def _manifest_ham(d: Path) -> dict:
    """``_sinif.json`` dosyasını sözlük olarak oku; hata LeBron'u durdurmaz."""
    m = d / "_sinif.json"
    if not m.is_file():
        return {}
    try:
        import json
        veri = json.loads(m.read_text(encoding="utf-8"))
    except Exception:                                     # noqa: BLE001
        return {}
    return veri if isinstance(veri, dict) else {}


def _manifest(d: Path) -> tuple[dict[str, dict], Path | None]:
    """Kobe'nin `_sinif.json`'ını normalleştirerek oku → (kayıtlar, kaynak).

    Üç biçim desteklenir (geriye uyum):
      * düz     `{ad: "sinif"}`
      * sözlük  `{ad: {"sinif":…, "temsil_kare": N}}`
      * sarmalı `{"kaynak": …, "kareler": {ad: {…, "temsil": [...]}}}`
    Manifesto yoksa/bozuksa boş döner — kule DURMAZ, ek bilgiden yararlanamaz.
    """
    veri = _manifest_ham(d)
    if not veri:
        return {}, None
    kaynak = None
    if "kareler" in veri and isinstance(veri.get("kareler"), dict):
        ham_kaynak = veri.get("kaynak")
        kaynak = Path(ham_kaynak) if ham_kaynak else None
        veri = veri["kareler"]
    cikti: dict[str, dict] = {}
    for ad, k in veri.items():
        if isinstance(k, dict):
            cikti[ad] = {"sinif": k.get("sinif"),
                         "temsil_kare": int(k.get("temsil_kare") or 1),
                         "temsil": list(k.get("temsil") or [ad])}
        else:
            cikti[ad] = {"sinif": k, "temsil_kare": 1, "temsil": [ad]}
    return cikti, kaynak


def ardisik_aralik_mi(dizin: str | Path) -> bool:
    """Kobe'nin girişte hiç kare silmeden sınır aralığını verdiğini bildirir."""
    return _manifest_ham(Path(dizin)).get("mod") == "ardisik_aralik"


def temsil_sayilari(dizin: str | Path) -> dict[str, int]:
    """Dosya adı → o karenin TEMSİL ETTİĞİ kare sayısı."""
    return {ad: k["temsil_kare"] for ad, k in _manifest(Path(dizin))[0].items()}


def genisletildi_mi(dizin: str | Path) -> bool:
    """Kardeş kareler yüklendi mi? Derleyici bıçağı buna göre susar."""
    kayit, kaynak = _manifest(Path(dizin))
    return bool(kaynak and kaynak.is_dir()
                and any(len(k["temsil"]) > 1 for k in kayit.values()))


def kareler(dizin: str | Path) -> list[Path]:
    """Dizindeki kare dosyaları — DOĞAL sırada. Okumaz, yalnız listeler.

    Yeni Kobe giriş sözleşmesinde dizin zaten ardışık sınır aralığıdır ve
    hiçbir genişletme yapılmaz. Aşağıdaki KARDEŞ GENİŞLETME yalnız eski,
    seyrek manifestoları okuyabilmek içindir: Kobe dedup'ı aynı kartın 8
    karesini 1 temsilciye indiriyor. Derleyici ise ardışıklığa dayanır —
    tek kareden sayfa açamaz. Manifesto kardeşlerin ADRESİNİ taşıyorsa
    onları KAYNAKTAN yükleriz; kare çoğaltılmaz, geri getirilir.

    ÖLÇÜLDÜ (Çiçek Taksi b2 girişi): genişletme + bıçak kapalı ile master
    3.921 px / 0 isim yerine 15.596 px / **16 isim**. Kadronun tamamı.

    Kart başına `KARDES_TAVANI` kareyle sınırlıdır — hepsini almak havuzu
    gereksiz şişirir, ölçümde 3 ile 8 arasında fark çıkmadı.
    Manifesto yoksa/kaynak erişilemezse eski davranış aynen sürer.
    """
    d = Path(dizin)
    if not d.is_dir():
        return []
    bulunan: list[Path] = []
    for desen in DESEN:
        bulunan.extend(d.glob(desen))
    kayit, kaynak = _manifest(d)
    if not (kayit and kaynak and kaynak.is_dir()):
        return sorted(bulunan, key=nat_sort_key)

    secili: dict[str, Path] = {}
    for p in bulunan:
        secili.setdefault(p.name, p)
        for kardes in (kayit.get(p.name, {}).get("temsil") or [])[:KARDES_TAVANI]:
            if kardes in secili:
                continue
            aday = kaynak / kardes
            if aday.is_file():
                secili[kardes] = aday
    return sorted(secili.values(), key=nat_sort_key)


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
