"""FRAMEHAVUZ (Havuz v2) — maks-verim kare seçicisi.

Terminoloji (Çağatay, 2026-07-30): pipeline üç havuz katmanı taşır —
  1. dk-havuzu      : frames/cikis (son N dakika, ham 1.5fps)
  2. jenerik-havuzu : frames/cikis_jenerik (onset sonrası, _jenerik_pool v5)
  3. FRAMEHAVUZ     : bu modülün çıktısı — jenerik-havuzundan derlenen
     sadeleştirilmiş okuma havuzu (dedup + temsilci + sigorta).
Spec: docs/superpowers/specs/2026-07-30-havuz-v2-design.md.

Saf görüntü-işleme: OCR yok, ağ yok. Gri kare listesi girer, seçilen kare
indeksleri + istatistik çıkar. Kaçırmamak > az sayfa."""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


def imza(gri: np.ndarray, boyut: int = 16) -> int:
    k = cv2.resize(gri, (boyut + 1, boyut), interpolation=cv2.INTER_AREA)
    bits = (k[:, 1:] > k[:, :-1]).astype(np.uint8).ravel()
    h = 0
    for b in bits:
        h = (h << 1) | int(b)
    return h


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


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
    sayfalar: list[int] = field(default_factory=list)
    istatistik: HavuzIstatistik | None = None


ESIK_TABAN = 24   # yalnız geri-düşüş: fark verisi yetersizse


def film_esigi(farklar: list[int]) -> int:
    """Film-bazlı eşik: 1D-Otsu; bimodallik zayıfsa p25+2 (kaçırmamak önceliği).
    Kanıt: sabit eşik hayat-agaci'da (fark dili 6-25) havuzu 4 sayfaya düşürdü;
    Otsu'ya geçiş 40 sayfa / Farsça 19→227 satır getirdi (2026-07-30)."""
    if len(farklar) < 8:
        return ESIK_TABAN
    f = np.array(sorted(farklar), dtype=np.float64)
    en_iyi_esik, en_iyi_var = None, -1.0
    for t in range(int(f.min()) + 1, int(f.max())):
        sol, sag = f[f <= t], f[f > t]
        if len(sol) < 3 or len(sag) < 3:
            continue
        arasi = len(sol) * len(sag) * (sol.mean() - sag.mean()) ** 2
        if arasi > en_iyi_var:
            en_iyi_var, en_iyi_esik = arasi, t
    if en_iyi_esik is None:
        return max(2, int(np.percentile(f, 25)) + 2)
    sol, sag = f[f <= en_iyi_esik], f[f > en_iyi_esik]
    ayrim = (sag.mean() - sol.mean()) / (f.std() + 1e-6)
    if ayrim < 0.8:
        return max(2, int(np.percentile(f, 25)) + 2)
    return int(en_iyi_esik)


def film_esigi_kde(farklar: list[int]) -> int:
    """KDE-vadisi (konsey adayı): histogram + Gauss yumuşatma, iki tepe
    arasındaki ilk yerel minimum. Tek tepe → p90 (yalnız sert sıçrama sayfa
    açar; gerisi drift). scipy'siz — numpy convolve."""
    if len(farklar) < 8:
        return ESIK_TABAN
    f = np.array(farklar, dtype=np.float64)
    # Binleme kök-sebep fix'i (Task 9 tur-2 ölçümü): dar tam-sayı desteğine
    # sabit-8 kutu açmak değerleri boşluklu dağıtıp SAHTE çift-tepe üretiyordu
    # (aralık=3 → kutu 0/2/5/7 dolu, aralar boş). Kutu sayısı desteğe uyar.
    hist, kenarlar = np.histogram(f, bins=max(4, int(f.max() - f.min()) + 1))
    cekirdek = np.exp(-0.5 * (np.linspace(-2, 2, 5) ** 2))
    duz = np.convolve(hist.astype(np.float64), cekirdek / cekirdek.sum(), mode="same")
    # Tepe-kütle filtresi (Task 9 ölçümü): 4-değerli ayrık küme histogram
    # binlemesinde sahte mini-tepe üretip vadi dalını yanlış tetikliyordu —
    # tepe, en yüksek tepenin en az %10'u kadar kütle taşımalı.
    tepeler = [i for i in range(1, len(duz) - 1)
               if duz[i] >= duz[i - 1] and duz[i] >= duz[i + 1]
               and duz[i] > 0.1 * float(duz.max())]
    if len(tepeler) < 2:
        return int(np.percentile(f, 90))
    a, b = tepeler[0], tepeler[-1]
    vadi = a + int(np.argmin(duz[a:b + 1]))
    # Sığ-vadi bekçisi (Otsu'nun ayrim<0.8 bekçisinin KDE simetriği): vadi,
    # tepelerin yarısından sığ değilse gerçek bimodallik yok → p90 (tek-küme).
    if duz[vadi] > 0.5 * min(duz[a], duz[b]):
        return int(np.percentile(f, 90))
    return int(kenarlar[vadi])


def temporal_median(griler: list[np.ndarray], pencere: int = 3) -> list[np.ndarray]:
    """Zaman-medyanı: kar/grén/interlace gibi kare-bağımsız gürültüyü İMZADAN
    siler (konsey: 'bunu en başa alın — kirli veride eşik çöp üretir').
    Yalnız SİNYAL hesabında kullanılır; okumaya orijinal kare gider."""
    if pencere < 2 or len(griler) < 2:
        return list(griler)
    yarim = pencere // 2
    out = []
    for i in range(len(griler)):
        a, b = max(0, i - yarim), min(len(griler), i + yarim + 1)
        out.append(np.median(np.stack(griler[a:b]), axis=0).astype(np.uint8))
    return out


def _temsilci(grup: list[int], keskinlikler: list[float]) -> int:
    """Grubun MEDYAN keskinliğine en yakın üyesi — iki ucu da (flaş=düşük
    Laplacian, aşırı-gren=yüksek) doğal dışlar; ayrı P95 kesmesi GEREKMEZ
    (katı `< p95` özdeş-kare gruplarında filtreyi tersine çeviriyordu)."""
    med = float(np.median([keskinlikler[i] for i in grup]))
    return min(grup, key=lambda i: abs(keskinlikler[i] - med))


def havuz_derle(griler: list[np.ndarray], *, medyan_pencere: int = 3,
                birikim_k: float = 3.0, esik_yontemi: str = "otsu") -> HavuzSonucu:
    """Çift-sinyal gruplama (spec §2):
    - ardışık-fark KAYAN çapayla → yavaş kayma/pan tek grup kalır (GLM bug fix'i)
    - grup-açılış imzasına BİRİKİM → fade yakalanır (Fable'ın konsey-itirazı)
    Kapanış: ardisik > esik VEYA birikim > birikim-eşiği (90 tavanlı — bkz. satır-içi
    yorum). SAYFA SAYISINA tavan yok; dev sessiz gruplar 20-kare dilimlere bölünür."""
    n = len(griler)
    if n == 0:
        return HavuzSonucu([], HavuzIstatistik(0, 0.0, 0.0, ESIK_TABAN, 0, 0, False))
    if n == 1:
        return HavuzSonucu([0], HavuzIstatistik(1, 0.0, 0.0, ESIK_TABAN, 0, 1, False))

    temiz = temporal_median(griler, medyan_pencere)
    keskinlikler = [float(cv2.Laplacian(g, cv2.CV_32F).var()) for g in griler]
    imzalar = [imza(g) for g in temiz]
    ardisik = [hamming(imzalar[i], imzalar[i + 1]) for i in range(n - 1)]
    esik = (film_esigi_kde(ardisik) if esik_yontemi == "kde"
            else film_esigi(ardisik))
    birikim_esigi = min(90, max(esik + 4, int(birikim_k * esik)))
    # 90 = rastgelelik-merkezi sınırı (bkz. alarm sabiti): birikim bundan öteye
    # "içerik değişti"den başka anlam taşıyamaz; yüksek-eşikli filmde (Otsu 46)
    # 3×esik=138 max-fark 112'nin üstünde kalıp fade sinyalini KAPATIYORDU.

    gruplar: list[list[int]] = [[0]]
    grup_acilis = imzalar[0]
    for i in range(1, n):
        ard = hamming(imzalar[i], imzalar[i - 1])     # kayan çapa
        birikim = hamming(imzalar[i], grup_acilis)     # fade sinyali
        if ard > esik or birikim > birikim_esigi:
            gruplar.append([i])
            grup_acilis = imzalar[i]
        else:
            gruplar[-1].append(i)

    DEV_GRUP = 20
    bolunmus: list[list[int]] = []
    for g in gruplar:
        if len(g) <= DEV_GRUP:
            bolunmus.append(g)
        else:
            # Dev sessiz grup (van-gogh 253-kare vakası): sürünen içerik eşik-altı
            # kalıp tek sayfaya iniyordu — kaçırmamak ilkesi periyodik temsilci ister.
            for b in range(0, len(g), DEV_GRUP):
                bolunmus.append(g[b:b + DEV_GRUP])
    gruplar = bolunmus

    # İçeriksiz-kare kapısı: düz flaş/boş kart (std≈0) sayfa olamaz — beyaz
    # flaş DÜŞÜK Laplacian verir (kenarsız), P95-üstü varsayımı YANLIŞTI
    # (Task 5 ölçümü; GLM'in P95 önerisi bu ölçümle yanlışlandı).
    sayfalar = []
    for g in gruplar:
        aday = _temsilci(g, keskinlikler)
        if float(griler[aday].std()) < 3.0:
            aday = max(g, key=lambda i: float(griler[i].std()))   # loş-kart kurtarma
        if float(griler[aday].std()) >= 3.0:
            sayfalar.append(aday)
    f = np.array(ardisik, dtype=np.float64)
    fark_medyani = float(np.median(f))
    # 90.0 ≈ 0.35×256; bağımsız-rastgele imza çiftleri Binom(256,0.5)→merkez
    # 128'e yapışır; gerçek içerik geçişleri medyanı buraya taşıyamaz
    # (ölçüm: fırtına 119-127, normal 0).
    alarm = bool(fark_medyani >= 90.0 and len(sayfalar) > 0.3 * n and n >= 20)
    if alarm:
        # Kurtarma (spec §6): seçici ayırt edemiyor — sayfaları imza-zinciriyle
        # kümele, her kümeden BAŞ+SON kalsın (fade uçları korunur). 'Hepsini oku'
        # israfı yerine kapsam-koruyan indirgeme (GLM: 500→20).
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
    return HavuzSonucu(sayfalar, ist)


def ikinci_gecis(griler: list[np.ndarray], sonuc: HavuzSonucu, *,
                 medyan_pencere: int = 3) -> list[int]:
    """Delta-enerji kapsama sigortası (spec §7): iki seçili sayfa arasında
    elenen karelerde birikmiş fark-enerjisi 'kaçmış içerik' imzasıdır —
    aralıktan en yüksek-farklı kareyi geri çağır. Konsey: 'tavansız dünyada
    daha da kritik; OCR kalite sigortası'."""
    if sonuc.istatistik is None or len(sonuc.sayfalar) < 1:
        return []
    temiz = temporal_median(griler, medyan_pencere)
    imzalar = [imza(g) for g in temiz]
    esik = max(1, sonuc.istatistik.esik)
    sinir = 2.0 * (esik ** 2)
    ekler: list[int] = []
    noktalar = sorted(set(sonuc.sayfalar))
    araliklar = list(zip(noktalar, noktalar[1:]))
    if noktalar[-1] < len(griler) - 1:
        araliklar.append((noktalar[-1], len(griler) - 1))
    for a, b in araliklar:
        if b - a < 2:
            continue
        farklar = [(hamming(imzalar[i], imzalar[i + 1]), i + 1)
                   for i in range(a, b - 1)]
        enerji = float(sum(d * d for d, _ in farklar))
        if enerji > sinir:
            ekler.append(max(farklar)[1])
    return sorted(set(ekler) - set(noktalar))
