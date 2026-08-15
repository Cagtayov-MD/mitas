"""STEVE NASH (framehavuz / Havuz v2) — Production Ready & Backward-Compatible.
Kanadalı efsane oyun kurucu & asist kralı STEVE NASH motoru.
Ön temizlik ve kare seçici pipeline (LeBron James master kompozitörüne asist yapar).

Kısıtlamalar: Modele gidecek karede Sharpen, Contrast, Deblur, Binarizasyon YOK. 
Sadece filtreleme, gruplama ve en temsilci orijinal kareyi seçme işlemi yapılır."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import cv2
import numpy as np

@dataclass(frozen=True)
class HavuzConfig:
    """Tüm sihirli sayıları dışarıdan yönetilebilir hale getiren konfigürasyon."""
    imza_boyut: int = 16
    esik_taban: int = 24
    medyan_pencere: int = 3
    birikim_k: float = 3.0
    dev_grup_limit: int = 20
    iceriksiz_std_esigi: float = 3.0
    alarm_medyan_esigi: float = 90.0
    alarm_oran_esigi: float = 0.3
    alarm_min_kare: int = 20
    otsu_ayirim_esigi: float = 0.8
    ikinci_gecis_katsayi: float = 2.0
    kde_sig_vadi_esigi: float = 0.5
    kde_tepe_yuzde: float = 0.1

@dataclass
class HavuzIstatistik:
    kare_sayisi: int
    fark_medyani: float
    fark_iqr: float
    esik: int
    birikim_esigi: int
    grup_sayisi: int
    alarm: bool

@dataclass
class HavuzSonucu:
    sayfalar: list[int] = field(default_factory=list)  # Geriye dönük uyumluluk için 'sayfalar' olarak kaldı
    istatistik: HavuzIstatistik | None = None
    _imzalar: list[int] = field(default_factory=list, repr=False)  # Cache

def imza(gri: np.ndarray, boyut: int = 16) -> int:
    k = cv2.resize(gri, (boyut + 1, boyut), interpolation=cv2.INTER_AREA)
    bits = (k[:, 1:] > k[:, :-1]).astype(np.uint8).ravel()
    h = 0
    for b in bits:
        h = (h << 1) | int(b)
    return h

def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")

def temporal_median(griler: list[np.ndarray], pencere: int = 3) -> list[np.ndarray]:
    if pencere < 2 or len(griler) < 2:
        return list(griler)
    yarim = pencere // 2
    out = []
    for i in range(len(griler)):
        a, b = max(0, i - yarim), min(len(griler), i + yarim + 1)
        out.append(np.median(np.stack(griler[a:b]), axis=0).astype(np.uint8))
    return out

def film_esigi(farklar: list[int], config: HavuzConfig = HavuzConfig()) -> int:
    """O(n) histogram-Otsu — ≥3 kuralı ARAMA KISITI olarak (döngünün İÇİNDE).

    ⚠ Bu kısıtı döngüden çıkarıp sona taşımayın. `e1a201d5` (2026-08-05) tam
    bunu yaptı ("Optimize edilmiş O(n) Otsu" notuyla) ve HIZ değil CEVAP
    değiştirdi: ≥3, dejenere adayı elemek yerine KAZANANI reddeder oldu;
    reddedince de Otsu'dan büsbütün vazgeçip `p25+2`'ye düşüyordu — bimodallikle
    ilgisi olmayan bir sayıya. MOBY DICK'te eşik 28→13, grup 15→165, okunan
    sayfa 26→100. Yönü veriye bağlıydı: ölçüm yatağında 25/29 yüzeyde
    fazla-okuma (maliyet), 3/29'da AZ-okuma (sessiz içerik kaybı). Beş ay
    sessiz kaldı; hata vermiyor.

    Kısıt döngüde iken hem eski/doğru cevap korunur hem O(n) hız alınır:
    29/29 yüzeyde naif aramanın birebir cevabı, ondan 5.5× hızlı.
    Ölçüm: `Allstar/nash/olcum/{otsu_ayrisma,onarim_adayi}.py`,
    gerekçe: `docs/GUNLUK.md` 2026-08-14.
    """
    if len(farklar) < 8:
        return config.esik_taban
    f = np.array(sorted(farklar), dtype=np.float64)
    hist, _ = np.histogram(f, bins=range(0, 257))
    total = len(f)
    sum_total = float(np.sum(np.arange(256) * hist))
    tmin = int(f.min())

    sumB = 0.0
    wB = 0
    max_var = -1.0
    en_iyi_esik = None
    for t in range(256):
        wB += int(hist[t])
        if wB == 0: continue
        wF = total - wB
        if wF == 0: break
        sumB += t * int(hist[t])
        if t <= tmin: continue          # arama aralığı [min+1, max-1]
        if wB < 3 or wF < 3: continue   # ← KISIT: dejenere bölme ADAY OLAMAZ
        mB = sumB / wB
        mF = (sum_total - sumB) / wF
        var = wB * wF * (mB - mF) ** 2
        if var > max_var:
            max_var, en_iyi_esik = var, t

    if en_iyi_esik is None:
        return max(2, int(np.percentile(f, 25)) + 2)
    sol, sag = f[f <= en_iyi_esik], f[f > en_iyi_esik]
    ayrim = (sag.mean() - sol.mean()) / (f.std() + 1e-6)
    if ayrim < config.otsu_ayirim_esigi:
        return max(2, int(np.percentile(f, 25)) + 2)
    return int(en_iyi_esik)

def film_esigi_kde(farklar: list[int], config: HavuzConfig = HavuzConfig()) -> int:
    """KDE-vadisi yöntemi - Orijinal koddan geri getirildi."""
    if len(farklar) < 8:
        return config.esik_taban
    f = np.array(farklar, dtype=np.float64)
    hist, kenarlar = np.histogram(f, bins=max(4, int(f.max() - f.min()) + 1))
    cekirdek = np.exp(-0.5 * (np.linspace(-2, 2, 5) ** 2))
    duz = np.convolve(hist.astype(np.float64), cekirdek / cekirdek.sum(), mode="same")
    tepeler = [i for i in range(1, len(duz) - 1)
               if duz[i] >= duz[i - 1] and duz[i] >= duz[i + 1]
               and duz[i] > config.kde_tepe_yuzde * float(duz.max())]
    if len(tepeler) < 2:
        return int(np.percentile(f, 90))
    a, b = tepeler[0], tepeler[-1]
    vadi = a + int(np.argmin(duz[a:b + 1]))
    if duz[vadi] > config.kde_sig_vadi_esigi * min(duz[a], duz[b]):
        return int(np.percentile(f, 90))
    return int(kenarlar[vadi])

def _temsilci(grup: list[int], keskinlikler: list[float]) -> int:
    med = float(np.median([keskinlikler[i] for i in grup]))
    return min(grup, key=lambda i: abs(keskinlikler[i] - med))

def havuz_derle(griler: list[np.ndarray], config: HavuzConfig | None = None, 
                *, medyan_pencere: int | None = None, birikim_k: float | None = None, 
                esik_yontemi: str = "otsu") -> HavuzSonucu:
    """Ana Pipeline - Backward-compatible imza."""
    # Config yönetimi (Hem eski parametre hem yeni config destekler)
    cfg = config if config is not None else HavuzConfig()
    if medyan_pencere is not None: cfg = replace(cfg, medyan_pencere=medyan_pencere)
    if birikim_k is not None: cfg = replace(cfg, birikim_k=birikim_k)

    n = len(griler)
    if n == 0:
        return HavuzSonucu()
    
    # VALIDATION
    if any(g is None for g in griler):
        raise ValueError("Hata: Frame listesinde None değer var.")
    shapes = {g.shape for g in griler}
    if len(shapes) > 1:
        raise ValueError(f"Hata: Çözünürlük uyumsuzluğu: {shapes}")

    if n == 1:
        return HavuzSonucu([0], HavuzIstatistik(1, 0.0, 0.0, cfg.esik_taban, 0, 1, False), [imza(griler[0], cfg.imza_boyut)])

    # HAZIRLIK
    temiz = temporal_median(griler, cfg.medyan_pencere)
    keskinlikler = [float(cv2.Laplacian(g, cv2.CV_32F).var()) for g in griler]
    imzalar = [imza(g, cfg.imza_boyut) for g in temiz]
    ardisik = [hamming(imzalar[i], imzalar[i + 1]) for i in range(n - 1)]
    
    # EŞİK HESAPLAMA
    if esik_yontemi == "kde":
        esik = film_esigi_kde(ardisik, cfg)
    else:
        try:
            esik = film_esigi(ardisik, cfg)
        except TypeError:
            esik = film_esigi(ardisik)
    birikim_esigi = min(90, max(esik + 4, int(cfg.birikim_k * esik)))

    # GRUPLAMA
    gruplar: list[list[int]] = [[0]]
    grup_acilis = imzalar[0]
    for i in range(1, n):
        ard = hamming(imzalar[i], imzalar[i - 1])
        birikim = hamming(imzalar[i], grup_acilis)
        if ard > esik or birikim > birikim_esigi:
            gruplar.append([i])
            grup_acilis = imzalar[i]
        else:
            gruplar[-1].append(i)

    bolunmus: list[list[int]] = []
    for g in gruplar:
        if len(g) <= cfg.dev_grup_limit:
            bolunmus.append(g)
        else:
            for b in range(0, len(g), cfg.dev_grup_limit):
                bolunmus.append(g[b:b + cfg.dev_grup_limit])
    gruplar = bolunmus

    # TEMSİLCİ SEÇİMİ
    sayfalar = []
    for g in gruplar:
        aday = _temsilci(g, keskinlikler)
        if float(griler[aday].std()) < cfg.iceriksiz_std_esigi:
            aday = max(g, key=lambda i: float(griler[i].std()))
        if float(griler[aday].std()) >= cfg.iceriksiz_std_esigi:
            sayfalar.append(aday)

    # ALARM VE KURTARMA
    f = np.array(ardisik, dtype=np.float64)
    fark_medyani = float(np.median(f))
    alarm = bool(fark_medyani >= cfg.alarm_medyan_esigi and 
                 len(sayfalar) > cfg.alarm_oran_esigi * n and 
                 n >= cfg.alarm_min_kare)
    
    if alarm:
        kume: list[list[int]] = [[sayfalar[0]]]
        for a, b in zip(sayfalar, sayfalar[1:]):
            if hamming(imzalar[a], imzalar[b]) <= 2 * esik:
                kume[-1].append(b)
            else:
                kume.append([b])
        sayfalar = sorted({k[0] for k in kume} | {k[-1] for k in kume})

    ist = HavuzIstatistik(
        kare_sayisi=n, fark_medyani=fark_medyani,
        fark_iqr=float(np.percentile(f, 75) - np.percentile(f, 25)),
        esik=esik, birikim_esigi=birikim_esigi,
        grup_sayisi=len(gruplar), alarm=alarm)
        
    return HavuzSonucu(sayfalar, ist, imzalar)


def ikinci_gecis(griler: list[np.ndarray], sonuc: HavuzSonucu, config: HavuzConfig = HavuzConfig()) -> list[int]:
    """Delta-enerji sigortası - Fallback (Yedek) mekanizmalı."""
    if sonuc.istatistik is None or len(sonuc.sayfalar) < 1:
        return []
    
    # GÜVENLİK: Eğer _imzalar cache'i boşsa (örn. JSON'dan okunduysa) yeniden hesapla.
    imzalar = sonuc._imzalar
    if len(imzalar) != len(griler):
        temiz = temporal_median(griler, config.medyan_pencere)
        imzalar = [imza(g, config.imza_boyut) for g in temiz]
        
    esik = max(1, sonuc.istatistik.esik)
    sinir = config.ikinci_gecis_katsayi * (esik ** 2)
    
    ekler: list[int] = []
    noktalar = sorted(set(sonuc.sayfalar))
    araliklar = list(zip(noktalar, noktalar[1:]))
    if noktalar[-1] < len(griler) - 1:
        araliklar.append((noktalar[-1], len(griler) - 1))
        
    for a, b in araliklar:
        if b - a < 2: continue
        farklar = [(hamming(imzalar[i], imzalar[i + 1]), i + 1) for i in range(a, b - 1)]
        enerji = float(sum(d * d for d, _ in farklar))
        if enerji > sinir:
            ekler.append(max(farklar)[1])
            
    return sorted(set(ekler) - set(noktalar))

