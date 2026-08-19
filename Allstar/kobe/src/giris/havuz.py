"""(b) HAVUZ — giriş kare dizinindeki kredi-benzeri kareleri seçer.

Yaklaşım `scripts/giris_jenerik_havuzu.py`'den (3 bağımsız Sonnet + Opus
hakem, 2026-06-29): DOSYA KOPYALANMADI, sadece stratejisi taşındı — kaynak
33 KB, üretimde çalışıyor, dokunulmadı. Aletler Kobe'nin kendisi:
`src/kutu.py` (Paddle det, "kutu var mı") ve `src/icerik.py` ("kredi metni
mi"). Bkz. src/giris/TASARIM.md "(b) HAVUZ".

Karar, kare başına:
  1. kutu yok (n==0)          → footage, ALINMAZ
  2. tüm kutular alt-bantta   → altyazı/haber-bandı, ALINMAZ
     (kutu.kutu_analiz'in HAZIR `alt_only` alanı — yeni eşik UYDURULMADI)
  3. OCR patladı / boş döndü  → RECALL: KOŞULSUZ AL ("okunamadı > yanlış oku")
  4. OCR "çöp-desenli"        → RECALL: KOŞULSUZ AL (yanlış-dil OCR güvenilmez)
  5. ≥1 kredi-benzeri satır   → AL
  6. aksi halde               → altyazı/ara-yazı say, ALINMAZ

Dedup: içerik-imzası aynı olan kareler teke iner. Boş-imzalı (recall) kareler
asla birbirine dedup'lanmaz — recall garantisini bozmasın diye.
"""
from __future__ import annotations

import sys
from pathlib import Path

# E2: aletler (kutu/icerik) src/ortak/'ta — karar kodu değil, ölçüm yaparlar.
_ORTAK = Path(__file__).resolve().parents[1] / "ortak"
if str(_ORTAK) not in sys.path:
    sys.path.insert(0, str(_ORTAK))

import kutu    # noqa: E402
import icerik  # noqa: E402


def _kare_yollari(dizin: str | Path) -> list[str]:
    d = Path(dizin)
    yollar = sorted(str(p) for p in d.glob("*.png"))
    if not yollar:
        yollar = sorted(str(p) for p in d.glob("*.jpg"))
    return yollar


def icerik_kareleri(dizin: str | Path) -> list[str]:
    """Yalnız İÇERİK karelerinin yolları (kredi-benzeri ≥1 satır OKUNMUŞ).

    `_kare_karari`'nın recall karelerini (okunamadı→garanti) AYIKLAR —
    bitiş kuralı (bkz. bitis.py) yalnız gerçek sinyalle çalışır: kanıt
    taraması (2026-08-17, 36 film) GT bitişinden sonraki karelerin büyük
    bölümünün recall/izci olduğunu gösterdi."""
    secilen = []
    for yol in _kare_yollari(dizin):
        _, _, neden = _kare_karari(yol)
        if neden == "icerik":
            secilen.append(yol)
    return secilen


def _kare_karari(yol: str) -> tuple[bool, list[str], str]:
    """Tek kare → (al_mi, satirlar, neden). Recall önceliği: okunamadı > yanlış oku.

    neden: footage | recall_ocr | recall_bos | recall_cop | recall_altbant
           | icerik | icerik_yok
    — icerik_kareleri/bitis kuralı yalnız 'icerik' sınıfıyla çalışır (kalibrasyon
    buna göre yapıldı, 2026-08-17)."""
    a = kutu.kutu_analiz(yol)
    if a.get("n", 0) == 0:
        return False, [], "footage"
    # ALT BANT: eskiden burada KOŞULSUZ elenirdi — kare OCR'a hiç girmezdi.
    # Film jeneriğinde doğru (alt bantta tek satır = gömülü altyazı), DİZİ
    # açılışında yanlış: oyuncu ismi tam orada yazıyor. Ölçülen kayıp —
    # Çiçek Taksi b2 girişi, g_0030..g_0034: EROL GÜNAYDIN havuzdan tamamen
    # düştü. Aynı kusur Nash'te 2026-08-19'da düzeltilmişti (197b1f33e).
    # Artık karar konuma değil İÇERİĞE bakıyor; aşağıda sınıflanır.
    alt_bant = bool(a.get("alt_only"))
    try:
        satirlar = icerik.satirlar(yol)
    except Exception:
        return True, [], "recall_ocr"           # recall — OCR patladı
    if not satirlar:
        return True, [], "recall_bos"           # recall — bos OCR
    try:
        if icerik.cop_desenli_mi([satirlar]):
            return True, satirlar, "recall_cop"  # recall — güvenilmez (yanlış-dil) OCR
    except Exception:
        pass
    if icerik.kredi_benzeri(satirlar) > 0:
        # Alt bant karesi havuza GİRER (isim kaybolmasın) ama "icerik"
        # SAYILMAZ: icerik_kareleri() yalnız "icerik" döndürür, dolayısıyla
        # 36 filmde kalibre edilmiş bitiş şelalesi bu değişiklikten etkilenmez.
        return True, satirlar, "recall_altbant" if alt_bant else "icerik"
    # Kredi gibi görünmeyen alt bant metni (gerçek gömülü altyazı) yine elenir.
    return False, [], "icerik_yok"


def _imza(satirlar: list[str]) -> str | None:
    temiz = sorted(s.strip() for s in satirlar if s and s.strip())
    return "|".join(temiz) if temiz else None


def sec(dizin: str | Path, sinir: dict | None, config: dict | None = None) -> dict:
    """Giriş kare dizinini tarar, kredi-benzeri temsilci havuzu döner.

    `sinir`, sinir.bul()'un çıktısıdır — provenans için kanıtta taşınır, ama
    tarama ARALIĞINI kısıtlamaz: bu araç `giris_jenerik_havuzu.py` ile aynı
    tasarımı izler — sınır/pencere tahmini yapmaz, dizindeki HER kareyi kendi
    kutu/OCR ölçütüyle bağımsız sınıflar (düşük-güven sınırın kaçırdığı geç
    köşe kredisini de yakalar).

    Döner: {"kareler": [yol...], "taranan": N, "elenen_footage": N,
            "dedup_temsilci": N}
    """
    yollar = _kare_yollari(dizin)
    taranan = len(yollar)
    elenen = 0
    gorulen: set[str] = set()
    secilen: list[str] = []
    # Seçilen karenin HANGİ sınıfla girdiği tüketiciye taşınır. Gerekçe:
    # LeBron kayma birleştiricisidir; alt-bant kareleri aynı duran kartın
    # neredeyse aynı kopyalarıdır ve kayma ölçümünü sulandırır (ölçüldü
    # 2026-08-20: havuz 93→127 olunca master 6087 px / 21 segment yerine
    # 449 px / 1 segment'e çöktü). Nash ve Jordan kareyi TEK TEK okur,
    # onlara zararı yok. Sınıfı yazıyoruz ki her tüketici kendi kararını
    # versin — havuzdan atmak yerine.
    siniflar: dict[str, str] = {}
    for yol in yollar:
        al, satirlar, neden = _kare_karari(yol)
        if not al:
            elenen += 1
            continue
        imza = _imza(satirlar)
        if imza is not None:
            if imza in gorulen:
                continue
            gorulen.add(imza)
        secilen.append(yol)
        siniflar[Path(yol).name] = neden
    return {"kareler": secilen, "taranan": taranan,
            "elenen_footage": elenen, "dedup_temsilci": len(secilen),
            "siniflar": siniflar}
