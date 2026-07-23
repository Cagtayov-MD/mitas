"""Jenerik başlangıç tespiti — v1 prototip (konsey-revize).

Tasarım: iki iz (scroll dy + statik kart nabzı) + ızgara-doğrulamalı hakemlik.
Konsey (GLM+Kimi, 2026-07-21) kararları uygulandı:
  - zemin-kararması SİNYALİ YOK (10 getiri / 17 zarar)
  - statik nabız ZAMAN-bazlı (fps-normalize), kare-sayısı değil
  - dy jitter-toleranslı: kümülatif monotonik kayma, kare-başı katı sabitlik değil
  - head-switching bandı TESPİT+kırp (kör 30px değil)
  - metin-ızgara (iki-sütun) yanlış-pozitif kalkanı: flicker/gate-weave/parçacık
    ELENIR çünkü ızgara üretmezler

Girdi: c_0001.png ... sıralı kare klasörü. Çıktı: {start_frame, ...}.
OCR YOK — bu katman OCR'dan bağımsız (OCR sadece opsiyonel doğrulayıcı).
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field

import numpy as np
from PIL import Image


# ── kare yükleme ─────────────────────────────────────────────────────────
def _kare_no(yol: str) -> int:
    """Dosya adından mutlak kare numarası (c_0027.png → 27). Klasörler c_0001'den
    başlamayabilir (BAJA c_0332, HANNA c_0018) — GT mutlak numara kullanıyor."""
    import re as _re
    m = _re.search(r"(\d+)(?=\.[a-zA-Z]+$)", yol)
    return int(m.group(1)) if m else 1


def kareler(dizin: str) -> list[str]:
    g = sorted(glob.glob(os.path.join(dizin, "*.png")))
    if not g:
        g = sorted(glob.glob(os.path.join(dizin, "*.jpg")))
    return g


def _gri(p: str, W: int = 320) -> np.ndarray:
    im = Image.open(p).convert("L")
    if im.width > W:
        im = im.resize((W, int(im.height * W / im.width)), Image.BILINEAR)
    return np.asarray(im, dtype=np.float32)


# ── head-switching bandı tespiti ─────────────────────────────────────────
def head_band_kirp(gri_kareler: list[np.ndarray], ornekle: int = 20) -> int:
    """VHS kafa-anahtarlama bandı: alt kenarda TÜM karelerde parlak/gürültülü
    satır grubu. Yüksekliğini döndür (kırpılacak alt piksel). Yoksa 0.

    Kör 30px yerine: alttan yukarı, satır-varyansı tüm karelerde anormal yüksekse
    (statik gürültü bandı) kırp. Konsey: 480p'de kör 30px agresif."""
    if not gri_kareler:
        return 0
    n = min(ornekle, len(gri_kareler))
    idx = np.linspace(0, len(gri_kareler) - 1, n).astype(int)
    yig = np.stack([gri_kareler[i] for i in idx])  # (n,H,W)
    h = yig.shape[1]
    # her satırın kareler-arası std'si — band satırları kareden kareye çok oynar
    satir_std = yig.std(axis=0).mean(axis=1)  # (H,)
    taban = np.median(satir_std[: int(h * 0.7)])  # üst %70 referans
    band = 0
    for y in range(h - 1, int(h * 0.85), -1):
        if satir_std[y] > taban * 3.0 + 1.0:
            band = h - y
        else:
            break
    return min(band, int(h * 0.12))


# ── dy: satır-profili çapraz-korelasyon ──────────────────────────────────
def dy_cift(a: np.ndarray, b: np.ndarray, max_shift: int = 40) -> tuple[int, float]:
    """İki karenin dikey kayması + korelasyon gücü."""
    pa = a.mean(axis=1)
    pb = b.mean(axis=1)
    pa = pa - pa.mean()
    pb = pb - pb.mean()
    na = np.linalg.norm(pa)
    nb = np.linalg.norm(pb)
    if na < 1e-6 or nb < 1e-6:
        return 0, 0.0
    en = (0, -1.0)
    for s in range(-max_shift, max_shift + 1):
        if s >= 0:
            x, y = pa[s:], pb[: len(pb) - s] if s else pb
        else:
            x, y = pa[: len(pa) + s], pb[-s:]
        m = min(len(x), len(y))
        if m < 40:
            continue
        r = float((x[:m] * y[:m]).sum() / (np.linalg.norm(x[:m]) * np.linalg.norm(y[:m]) + 1e-9))
        if r > en[1]:
            en = (s, r)
    return en


# ── metin-ızgara skoru (yanlış-pozitif kalkanı) ──────────────────────────
def metin_satir_skoru(a: np.ndarray) -> float:
    """Jenerik metni düzenli aralıklı yatay satır bantları yapar → satır-yoğunluk
    profilinin otokorelasyonunda tepe. Sahne düzensiz, tepe yok. izgara_skoru'dan
    daha ayırt edici (o doyuyordu). SINIR: başlık kartı/sahne-metni de yüksek verir
    — 'cast/crew mi' ayrımı için OCR/VLM gerekir (statik/görüntü-üzeri filmlerde)."""
    gx = np.abs(np.diff(a, axis=1))
    row = gx.mean(axis=1)
    if row.std() < 1e-3:
        return 0.0
    r = row - row.mean()
    ac = np.correlate(r, r, "full")[len(r) - 1:]
    ac = ac / (ac[0] + 1e-9)
    seg = ac[5:41]
    if len(seg) == 0:
        return 0.0
    tepe = float(seg.max())
    rn = row / (row.max() + 1e-9)
    nsat = int(((rn[1:-1] > rn[:-2]) & (rn[1:-1] > rn[2:]) & (rn[1:-1] > 0.35)).sum())
    return tepe * (1.0 if nsat >= 3 else 0.4)


def izgara_skoru(a: np.ndarray) -> float:
    """Jenerik metni: yatay satırlar + (çoğunlukla) iki dikey sütun.
    Flicker/gate-weave/parçacık bu yapıyı ÜRETMEZ. 0..1 skor.

    Yöntem: yüksek-kontrast kenar maskesi → satır-yoğunluğu düzenliliği +
    sütun-histogramı bimodalliği."""
    # yerel kontrast (metin kenarları)
    gx = np.abs(np.diff(a, axis=1))
    kenar = gx > (gx.mean() + 2 * gx.std())
    yog = kenar.mean()
    if yog < 0.002:
        return 0.0
    # satır profili: metin satırları düzenli tepe/vadi yapar
    satir = kenar.mean(axis=1)
    if satir.max() < 1e-6:
        return 0.0
    satir_n = satir / satir.max()
    tepe = ((satir_n[1:-1] > satir_n[:-2]) & (satir_n[1:-1] > satir_n[2:]) & (satir_n[1:-1] > 0.3)).sum()
    # sütun profili: iki-sütun jenerik → sol+sağ yoğunluk, orta boşluk
    sut = kenar.mean(axis=0)
    w = len(sut)
    sol = sut[: w // 3].mean()
    orta = sut[w // 3: 2 * w // 3].mean()
    sag = sut[2 * w // 3:].mean()
    iki_sutun = 1.0 if (sol > orta * 1.2 or sag > orta * 1.2) and orta < max(sol, sag) else 0.4
    return min(1.0, (tepe / 12.0) * 0.6 + iki_sutun * 0.4)


# ── ana dedektör ─────────────────────────────────────────────────────────
@dataclass
class Sonuc:
    start_frame: int
    yontem: str
    guven: float
    dy_medyan: float = 0.0
    notlar: str = ""
    seri: dict = field(default_factory=dict)


def tespit(dizin: str, fps: float = 25.0, stride: int = 2) -> Sonuc:
    """v2: iki iz → tek 'jenerik-aktivite' sinyali → ilk SÜRDÜRÜLEN uzun koşu.

    Konsey dersi: kaçan geri-tarama (v1) sahneye taşıyor → kaldırıldı. Onset,
    sürdürülen aktivite koşusunun BAŞI. Kısa sahne-metni yanlış-pozitifleri
    'uzun koşu' şartıyla elenir (banner/tabela kısa; jenerik ≥2 sn sürer)."""
    g = kareler(dizin)
    if len(g) < 10:
        return Sonuc(-1, "kare_yok", 0.0, notlar=f"{len(g)} kare")

    idx = list(range(0, len(g), stride))
    gk = [_gri(g[i]) for i in idx]
    band = head_band_kirp(gk)
    if band:
        gk = [k[: k.shape[0] - band] for k in gk]

    dys, corrs, izg = [], [], []
    for i in range(len(gk) - 1):
        s, r = dy_cift(gk[i], gk[i + 1])
        dys.append(s)
        corrs.append(r)
        izg.append(izgara_skoru(gk[i]))
    izg.append(izg[-1] if izg else 0.0)  # son kareye de skor
    dys = np.array(dys, dtype=np.float32)
    corrs = np.array(corrs, dtype=np.float32)
    izg = np.array(izg, dtype=np.float32)
    kf = np.array([np.abs(gk[i] - gk[i + 1]).mean() for i in range(len(gk) - 1)], dtype=np.float32)
    kf = np.append(kf, kf[-1] if len(kf) else 0.0)
    kf_med = float(np.median(kf)) if len(kf) else 1.0

    # ── v3: SCROLL-birincil. İlk UZUN sürdürülen scroll koşusu = onset ──
    # Sinyal keşfi (2026-07-21): scroll (dy>3, corr>0.85) TEMİZ ve güçlü; nerede
    # jenerik kayıyorsa onlarca kare dy~20 corr>0.9. "Statik" (dy=0+corr>0.9)
    # AYIRT EDİCİ DEĞİL — yavaş/durgun sahne de aynısını veriyor (VAHŞİ AFRİKA
    # idx0-215 hepsi 'statik' ama jenerik idx221). O yüzden statik onset ATILDI.
    n = len(gk)
    scroll = np.zeros(n, bool)
    for i in range(len(dys)):
        scroll[i] = (dys[i] > 3 and corrs[i] >= 0.85)

    W = max(6, int(fps * 0.5 / stride))          # ~0.5 sn pencere
    min_kosu = max(12, int(fps * 2.0 / stride))  # jenerik scroll ≥2 sn sürer
    bosluk_tol = W                                # koşu içi kısa kesinti toleransı

    def ilk_uzun_kosu(mask: np.ndarray) -> int | None:
        i = 0
        while i < n - W:
            if mask[i:i + W].mean() >= 0.6:
                j = i
                bosluk = 0
                while j < n and bosluk < bosluk_tol:
                    bosluk = 0 if mask[j] else bosluk + 1
                    j += 1
                if (j - i) >= min_kosu:
                    return i
                i = j
            else:
                i += 1
        return None

    onset = ilk_uzun_kosu(scroll)
    yontem = "scroll"

    # ── scroll over-shoot fix: statik-kart-önce-scroll ──
    # LALELER/ELMA/ÖRGÜT: jenerik STATİK KARTLA başlar, scroll sonra gelir. Scroll
    # onset kartı atlar (+30..+80 kare geç). Çözüm: onset'ten SINIRLI geriye yürü,
    # metin-var + statik (kayma yok) kareler boyunca; SAHNE KESMESİNDE dur (v1'in
    # kaçan geri-taramasının aksine sınırlı + kesme-durduruculu).
    if onset is not None and onset > 0:
        sinir = max(0, onset - int(fps * 5.0 / stride))  # en çok ~5 sn geri
        g = onset
        while g - 1 >= sinir:
            i = g - 1
            metin_var = izg[i] >= 0.5
            kayma_yok = abs(dys[i]) <= 3 if i < len(dys) else True
            sahne_kesme = kf[i] > kf_med * 2.5 if i < len(kf) else False
            if metin_var and kayma_yok and not sahne_kesme:
                g -= 1
            else:
                break
        if g < onset:
            onset = g
            yontem = "scroll+kart"

    if onset is None:
        # scroll yok → statik/görüntü-üzeri film. Sinyal-işleme burada YETERSİZ:
        # metin-satır/ızgara başlık kartı + sahne metnine de tetikliyor, "cast/crew mi"
        # ayrımı OCR/VLM ister (konsey: OCR doğrulayıcı). GEÇİCİ: izgara fallback,
        # DÜŞÜK güven damgasıyla — pipeline bunu OCR-doğrulamasına yönlendirmeli.
        metin = np.array([izg[i] >= 0.55 for i in range(n)], bool)
        onset = ilk_uzun_kosu(metin)
        yontem = "statik_metin_DÜŞÜK_GÜVEN"

    if onset is None:
        return Sonuc(-1, "sinyal_yok", 0.0,
                     notlar=f"scroll/metin koşusu yok; dy_med={np.median(np.abs(dys)):.1f} izg_max={izg.max():.2f}",
                     seri={"dy": dys.round(1).tolist(), "corr": corrs.round(2).tolist(), "izg": izg.round(2).tolist()})

    guven = float(max(corrs[onset:onset + W].mean(), izg[onset:onset + W].mean()))
    return Sonuc(
        start_frame=_kare_no(g[idx[onset]]),
        yontem=yontem,
        guven=guven,
        dy_medyan=float(np.median(dys[onset:onset + W])),
        notlar=f"onset_idx={onset} band_kirp={band} min_koşu={min_kosu}",
        seri={"dy": dys.round(1).tolist(), "corr": corrs.round(2).tolist(), "izg": izg.round(2).tolist()},
    )


def tespit_v4(dizin: str, fps: float = 25.0, stride: int = 2, ocr_stride: int = 1) -> Sonuc:
    """v4: kutu sinyali (PaddleOCR det) ANA ayırıcı + dy scroll hassasiyeti.

    Ölçüm (2026-07-21): kenar-yoğunluğu sahne kenarlarına doyuyor; PaddleOCR gerçek
    metni bulur (sahne 0-1 kutu, jenerik ≥2). Kutu geçişi (0→sürdürülen≥2) onset.
    Scroll bölgesinde dy ile kare-hassas ince ayar."""
    import credit_box as cb
    g = kareler(dizin)
    if len(g) < 10:
        return Sonuc(-1, "kare_yok", 0.0, notlar=f"{len(g)} kare")

    idx = list(range(0, len(g), stride))
    gk = [_gri(g[i]) for i in idx]
    band = head_band_kirp(gk)
    if band:
        gk = [k[: k.shape[0] - band] for k in gk]

    dys = []
    corrs = []
    for i in range(len(gk) - 1):
        s, r = dy_cift(gk[i], gk[i + 1])
        dys.append(s)
        corrs.append(r)
    dys = np.array(dys, dtype=np.float32)
    corrs = np.array(corrs, dtype=np.float32)

    # kutu sinyali (orijinal kareler üzerinden, stride'lı)
    alt_g = [g[i] for i in idx]
    jbayrak, say = cb.kutu_serisi(alt_g, stride=ocr_stride)
    n = len(gk)

    scroll = np.zeros(n, bool)
    for i in range(len(dys)):
        scroll[i] = (dys[i] > 3 and corrs[i] >= 0.85)

    # KUTU-BİRİNCİL: onset yalnız kutu-jenerik ile tetiklenir. Scroll-yalnız
    # tetikleme KALDIRILDI — sahne hareketi/letterbox/pan yanlış-tetikliyordu
    # (AFACAN kare9 scroll ama kutu yok; Kimi'nin letterbox/crawler uyarısı).
    # Scroll yalnızca kutu-doğrulanmış bölgede onset'i kare-hassas iyileştirir.
    aktif = jbayrak.copy()

    W = max(6, int(fps * 0.5 / stride))
    min_kosu = max(10, int(fps * 1.5 / stride))   # ≥1.5 sn (VAHŞİ görüntü-üzeri seyrek 2-kutu)
    bosluk_tol = max(4, int(fps * 0.6 / stride))

    onset = None
    i = 0
    while i < n - W:
        if aktif[i:i + W].mean() >= 0.55:
            j = i
            bosluk = 0
            while j < n and bosluk < bosluk_tol:
                bosluk = 0 if aktif[j] else bosluk + 1
                j += 1
            if (j - i) >= min_kosu:
                onset = i
                break
            i = j
        else:
            i += 1

    if onset is None:
        return Sonuc(-1, "sinyal_yok", 0.0,
                     notlar=f"kutu+scroll koşusu yok; max_kutu={int(say.max())}",
                     seri={"say": say.tolist()[:80]})

    # kutu-onset bulundu; scroll bu bölgede daha ERKEN başlıyorsa (kart→scroll),
    # scroll başına kadar geri çek — AMA kutu-yok bölgeye TAŞMA (13.CUMA frame3
    # regresyonu). Hem scroll HEM kutu-jenerik olan karelerde geri yürü.
    if onset < len(scroll):
        g2 = onset
        alt = max(0, onset - int(fps * 1.5 / stride))
        while g2 - 1 >= alt and g2 - 1 < len(scroll) and scroll[g2 - 1] and jbayrak[g2 - 1]:
            g2 -= 1
        onset = g2

    # ── VLM doğrulama (konsey tie-breaker): kutu-onset gerçekten cast/crew mi? ──
    # Epilog şiiri/başlık/sahne-metni de kutu üretir (UĞURSUZ). VLM okur; DEGIL ise
    # gerçek cast'e kadar İLERİ yürü. MITAS_JENERIK_VLM=1 ile açılır.
    if os.environ.get("MITAS_JENERIK_VLM") == "1":
        try:
            import credit_vlm as cv
            ileri, denendi = onset, 0
            while ileri < n and denendi < 12:
                if aktif[ileri]:
                    if cv.jenerik_mi(g[idx[ileri]]):
                        break
                    j = ileri
                    while j < n and aktif[j]:
                        j += 1
                    while j < n and not aktif[j]:
                        j += 1
                    ileri, denendi = j, denendi + 1
                else:
                    ileri += 1
            if ileri < n:
                onset = ileri
        except Exception:
            pass

    yontem = "kutu+scroll" if (onset < len(scroll) and scroll[onset:onset + W].any()) else "kutu"
    return Sonuc(
        start_frame=_kare_no(g[idx[onset]]),
        yontem=yontem,
        guven=float(corrs[onset:onset + W].mean()) if onset < len(corrs) else 0.5,
        dy_medyan=float(np.median(dys[onset:onset + W])) if onset < len(dys) else 0.0,
        notlar=f"onset_idx={onset} band={band} maxkutu={int(say.max())}",
        seri={"say": say.round().tolist(), "dy": dys.round(1).tolist()},
    )


def _statik_icerik_onset(g: list[str], idx: list[int], a: int, b: int,
                          adim: int = 2, azami_ileri: int = 30, azami_geri: int = 120
                          ) -> tuple[int, str]:
    """Statik-tip (scroll-dışı) kazanan koşuda içerik-çapalı onset (T5).

    Görev 5: koşu başı sık sık kredi-DIŞI metin taşır (epilog/ara-yazı/stüdyo
    kartı — atlas kanıtı: ERKEN_METIN vakaları KNUTE/TESS/KIZIL_HAYAT/...).
    Koşu sınırını onset saymak yerine İÇERİKTEN al:
      1) İleri-budama: koşu başından ileri, her `adim` örnek-karede bir, en çok
         `azami_ileri` örnek-kare — `kredi_karti_mi` False olduğu sürece ilerle;
         ilk True örnek-karesi aday-onset. Guard: budama koşu uzunluğunun
         yarısını geçemez — geçiyorsa (veya hiç bulunamazsa) DOKUNMA (OCR genel
         başarısızlığı işareti).
      2) Atlanan (adim-1) karede daha erken True olabilir — bulunan karadan 1
         örnek-kare geri de kontrol et, o da True ise onu al.
      3) Geri-genişletme: (budanmış) onset'ten geriye kare-kare (jbayrak şart
         DEĞİL) — `kredi_karti_mi` True ise geri çek; 2 ardışık False'ta dur;
         toplam ≤ `azami_geri` örnek-kare.

    Önbellek: her örnek-kare EN ÇOK BİR KEZ OCR'lanır (PaddleOCR-rec pahalı —
    aynı kare iki kez OCR'lanmasın)."""
    import credit_content as cc
    cache: dict[int, list[str]] = {}

    def satir(fi: int) -> list[str]:
        if fi not in cache:
            try:
                cache[fi] = cc.satirlar(g[idx[fi]])
            except Exception:
                cache[fi] = []
        return cache[fi]

    kosu_uzunluk = b - a
    azami_budama = kosu_uzunluk / 2.0

    bulunan = None
    fi = a
    denenen = 0
    while denenen < azami_ileri and fi <= b:
        if cc.kredi_karti_mi(satir(fi)):
            bulunan = fi
            break
        fi += adim
        denenen += 1

    if bulunan is None or (bulunan - a) > azami_budama:
        return a, "budama-yok(guard/bulunamadı)"

    if bulunan - 1 >= a and cc.kredi_karti_mi(satir(bulunan - 1)):
        bulunan -= 1

    onset = bulunan
    prob = bulunan
    ardisik_false = 0
    denenen = 0
    while denenen < azami_geri and prob - 1 >= 0:
        prob -= 1
        if cc.kredi_karti_mi(satir(prob)):
            onset = prob
            ardisik_false = 0
        else:
            ardisik_false += 1
            if ardisik_false >= 2:
                break
        denenen += 1

    return onset, f"budama={bulunan - a} genislet={bulunan - onset}"


def _ardisik_maks(mask) -> int:
    """Bool dizide en uzun ardışık True koşusunun uzunluğu (T4 scroll-tip ölçütü:
    ardışık scroll ≥16 örnek-kare)."""
    en = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        en = max(en, cur)
    return en


def _gecis_icerik_onayi(g: list[str], idx: list[int], cc_mod, a: int, b: int,
                         ornek: int = 8) -> bool:
    """T4 geri-birleştirme kapısı: ÖNCEKİ aday [a,b] gerçekten kredi içeriği mi.

    Aday zaten bir kutu-koşusu (jbayrak-sürdürülen) — burada yalnız ÇEKİRDEK
    ROL-KEYWORD (yönetmen/senaryo/görüntü/müzik/kurgu/oyuncu/yapımcı ...) arandığı
    doğrulanır. `kredi_karti_mi`'nin genel isim-listesi testi (isim≥3) YETERSİZ
    çıktı: BÜYÜK_TEHDİT/HAYATIMIN_ERKEĞİ regresyonu — mid-film bir "personel
    dosyası" ekran-arayüzü (DESCRIPTION/REMARKS/... gibi ALLCAPS OCR gürültüsü)
    isim≥3'ü rastlantısal geçiyor ama HİÇBİR rol-keyword'ü yok; UYKUNUN'un mid-
    film tarif-kartı ("Tarte aux Pommes") de aynı şekilde reddedilir. Buna karşın
    dört pozitif hedef (MESLEĞE_DÖNÜŞ/KARAVAN/"6"/DİPTEKİLER) örneklenen 8 karenin
    en az birinde gerçek rol-keyword taşıyor (DIRECTED BY / MUSIC BY / EDITOR /
    PRODUCER ...) — ölçüldü. Birden fazla örnek karede dener — tek karenin OCR'ı
    bozuk çıkabilir (geçiş bulanıklığı)."""
    n = min(ornek, b - a + 1)
    if n <= 0:
        return False
    for fi in sorted(set(int(x) for x in np.linspace(a, b, n))):
        try:
            satirlar = cc_mod.satirlar(g[idx[fi]])
        except Exception:
            continue
        if any(cc_mod._ROL.search(s) for s in satirlar):
            return True
    return False


def _scroll_kurtarma(g: list[str], idx: list[int], cc_mod, scroll: np.ndarray,
                      jbayrak: np.ndarray, n: int, fps: float, stride: int
                      ) -> tuple[int, int] | None:
    """Scroll-kurtarma (T6, plan Görev6/Adım2): HİÇBİR aday içerik-eşiğini
    geçemediyse son çare — filmin son %25'inde ≥8 sn SÜRDÜRÜLEN scroll+kutu
    koşusu VAR mı, ve o koşuda ≥1 _ROL_CEKIRDEK eşleşmesi var mı. Varsa kredi
    kabul (gazete/tabela/tek-intertitle KAYMAZ — gerekçe budur, sahte-pozitif
    riski düşük). `adaylar` listesindeki bir kutu-koşusuna denk gelmeyebilir
    (jbayrak-boşluk-toleransı farklı) — o yüzden ham scroll&jbayrak kesişiminde
    kendi ardışık-koşusunu arar."""
    baslangic = int(0.75 * (n - 1))
    min_kosu = max(16, int(fps * 8.0 / stride))
    aktif = scroll & jbayrak
    en_uzun = (0, -1, -1)  # (uzunluk, start, end)
    i = baslangic
    while i < n:
        if aktif[i]:
            j = i
            while j < n and aktif[j]:
                j += 1
            uzunluk = j - i
            if uzunluk > en_uzun[0]:
                en_uzun = (uzunluk, i, j - 1)
            i = j
        else:
            i += 1
    uzunluk, ks, ke = en_uzun
    if uzunluk < min_kosu:
        return None
    ornek = sorted(set(int(x) for x in np.linspace(ks, ke, min(8, ke - ks + 1))))
    for fi in ornek:
        try:
            satirlar = cc_mod.satirlar(g[idx[fi]])
        except Exception:
            continue
        if any(cc_mod._ROL_CEKIRDEK.search(s) for s in satirlar):
            return ks, ke
    return None


def tespit_v5(dizin: str, fps: float = 25.0, stride: int = 2, ocr_stride: int = 2) -> Sonuc:
    """v5: TAM FİLM için. Aday kutu-koşuları → OCR-içerik ile 'isim-listesi mi'
    doğrula → son-çapa+scroll ile seç → yoksa KREDİ YOK.

    Konsey (GLM, 2026-07-21): kutu var/yok yetmez. Tam filmde sahne-tabelası
    (BILLY saloon), ara-yazı (MODERN Chaplin), gazete kutu üretir ama İSİM-LİSTESİ
    DEĞİL. Krediyi ayıran: metin içeriği (rec) + scroll + son-çapa. Eski filmlerin
    ~%40'ı kapanış-kredisiz → güvenle 'YOK' dönülmeli."""
    import credit_box as cb
    import credit_content as cc
    g = kareler(dizin)
    if len(g) < 10:
        return Sonuc(-1, "kare_yok", 0.0, notlar=f"{len(g)} kare")

    idx = list(range(0, len(g), stride))
    gk = [_gri(g[i]) for i in idx]
    band = head_band_kirp(gk)
    if band:
        gk = [k[: k.shape[0] - band] for k in gk]
    # T4: max_shift 40→60 — hızlı-akan jenerikte kayma sınıra yapışıp korelasyonu
    # düşürüyordu (GLM tur-2 aliasing uyarısı). Yalnız v5'in KENDİ çağrısı;
    # tespit()/tespit_v4() dy_cift'i varsayılan max_shift=40 ile çağırmaya devam
    # eder — imzaları/davranışları DEĞİŞMEDİ.
    MAX_SHIFT_V5 = 60
    dys = []
    corrs = []
    for i in range(len(gk) - 1):
        s, r = dy_cift(gk[i], gk[i + 1], max_shift=MAX_SHIFT_V5)
        dys.append(s)
        corrs.append(r)
    dys = np.array(dys, dtype=np.float32)
    corrs = np.array(corrs, dtype=np.float32)
    n = len(gk)
    scroll = np.zeros(n, bool)
    for i in range(len(dys)):
        # aliasing gardı: dy sınıra yapışmışsa (gerçek kayma max_shift'i aşıyor,
        # arama sınırda kırpılıyor) VE korelasyon yine de güçlüyse scroll say.
        scroll[i] = (dys[i] > 3 and corrs[i] >= 0.85) or (
            abs(dys[i]) >= MAX_SHIFT_V5 - 2 and corrs[i] >= 0.85)

    alt_g = [g[i] for i in idx]
    jbayrak, say = cb.kutu_serisi(alt_g, stride=ocr_stride)

    # ── aday koşuları bul (sürdürülen kutu-jenerik, boşluk-toleranslı) ──
    min_kosu = max(6, int(fps * 1.0 / stride))
    bosluk_tol = max(4, int(fps * 0.8 / stride))
    adaylar = []
    i = 0
    while i < n:
        if jbayrak[i]:
            j = i
            bosluk = 0
            son = i
            while j < n and bosluk <= bosluk_tol:
                if jbayrak[j]:
                    bosluk = 0
                    son = j
                else:
                    bosluk += 1
                j += 1
            if son - i + 1 >= min_kosu:
                adaylar.append((i, son))
            i = j
        else:
            i += 1

    if not adaylar:
        return Sonuc(-1, "kredi_yok", 0.0,
                     notlar=f"kutu-koşusu yok; maxkutu={int(say.max())}",
                     seri={"adaylar": []})

    # ── her adayı OCR-içerikle değerlendir ──
    EŞIK = 0.6     # ≥2 sürdürülen-yoğun kare (gazete 1 karede kalır → elenir)
    # SON-ERİŞİM kuralı (konsey + gözlem): GERÇEK kapanış kredisi filmin SONUNA kadar
    # uzanır. Film-ortası metin insertı (MODERN arananıyor-afişi) daha erken biter,
    # ardından FİLM DEVAM EDER. Aday sonu son %18'e ulaşmıyorsa kredi değildir.
    SON_ERISIM = 0.82
    # SON_ERISIM gevşetmesi (T6, plan Görev6/Adım3): bazı gerçek kapanış kredileri
    # filmin en son birkaç saniyesine ULAŞMADAN biter (DOĞUM_GÜNÜN atlas kanıtı —
    # son_capa=0.74, yayın-sonu boş/logo kareleri kutu üretmiyor). Yalnız filmin
    # SON metin-koşusu (sonrasında başka aday YOK) VE kb≥0.9 (çok yüksek içerik
    # güveni) VE ≥1 _ROL_CEKIRDEK VARSA eşik 0.82→0.70'e gevşer. 0.70'i AŞAN
    # gevşetme YASAK (plan: film-ortası insert kapısı, kırmızı-çizgi riski).
    SON_ERISIM_GEVSEK = 0.70
    en_iyi = None
    kayitlar = []   # teşhis: aday başına {a,b,kare_a,kare_b,son_ok,kb,joint,roller} (T2)
    for widx, (a, b) in enumerate(adaylar):
        kare_a, kare_b = _kare_no(g[idx[a]]), _kare_no(g[idx[b]])
        son_capa_orani = b / max(1, n - 1)
        son_ok = son_capa_orani >= SON_ERISIM
        is_last = (widx == len(adaylar) - 1)
        gevsetme_aday = (not son_ok) and is_last and son_capa_orani >= SON_ERISIM_GEVSEK
        if not son_ok and not gevsetme_aday:
            # SON_ERISIM'e takıldı → içerik OCR'ı hiç ÇALIŞTIRMA (maliyet artmasın)
            kayitlar.append({"a": a, "b": b, "kare_a": kare_a, "kare_b": kare_b,
                              "son_ok": False, "kb": None, "joint": None, "roller": []})
            continue                     # filmin sonuna ulaşmıyor → kredi değil
        # en yoğun kutulu kareler + eşit örnekler (dense kredi karesini yakala)
        say_c = max(1, (b - a + 1))
        yogun = list(np.argsort(say[a:b + 1])[-5:] + a)
        esit = list(np.linspace(a, b, min(5, say_c)).astype(int))
        ornek = sorted(set(int(x) for x in yogun + esit))
        satir_onbellek: dict[int, list[str]] = {}

        def _satir_al(fi: int) -> list[str]:
            if fi not in satir_onbellek:
                try:
                    satir_onbellek[fi] = cc.satirlar(g[idx[fi]])
                except Exception:
                    satir_onbellek[fi] = []
            return satir_onbellek[fi]

        kare_satirlari = [_satir_al(fi) for fi in ornek]
        kb_max = cc.kredi_skoru_coklu(kare_satirlari)
        core_roller = sorted({m.lower() for sl in kare_satirlari for s in sl
                               for m in cc._ROL_CEKIRDEK.findall(s)})
        # Seyrek-kredi yolu (T6, plan Görev6/Adım4): bazı jenerikler kare-başına
        # 1-3 isim gösterir (KÜÇÜK_SİMBA/ROBOCOP/TAKTİKLER_SAVAŞI atlas kanıtı) —
        # varsayılan yogun_esik=4 hiç yakalamıyor. Ama gerçek kredi ile gazete/tabela
        # ayrımı hala gerekiyor: yalnız koşuda ≥2 FARKLI ÇEKİRDEK-rol varsa (tek
        # 'Yönetmen' intertitle'ı YETMEZ — sessiz-film kırmızı-çizgi senaryosu)
        # yogun_esik=2 ile yeniden skorla, büyük olanı al.
        # Dar örneklem (5 yoğun+5 eşit) rol-çeşitliliğini kaçırabilir (ROBOCOP
        # ölçümü: 'music'/'written' örneklemin dışında kaldı) — aday zaten
        # REDDEDİLECEKSE (kb_max<EŞIK) ve <2 çekirdek-rol bulunduysa, SADECE bu
        # durumda geniş örneklemle rol-çeşitliliğini yeniden ara (maliyet yalnız
        # başarısız adaylarda artar).
        if len(core_roller) < 2 and kb_max < EŞIK and (b - a + 1) > len(ornek):
            genis_idx = sorted(set(int(x) for x in np.linspace(a, b, min(16, say_c))))
            genis_satirlari = [_satir_al(fi) for fi in genis_idx]
            core_roller = sorted({m.lower() for sl in genis_satirlari for s in sl
                                   for m in cc._ROL_CEKIRDEK.findall(s)})
            if len(core_roller) >= 2:
                kare_satirlari = genis_satirlari
        if len(core_roller) >= 2:
            kb_seyrek = cc.kredi_skoru_coklu(kare_satirlari, yogun_esik=2)
            kb_max = max(kb_max, kb_seyrek)
        if gevsetme_aday and not (kb_max >= 0.9 and core_roller):
            # gevşetme hakkı kazanılmadı (kb<0.9 VEYA çekirdek-rol yok) — normal
            # SON_ERISIM'e takılmış gibi davran (kb'yi teşhis için sakla).
            kayitlar.append({"a": a, "b": b, "kare_a": kare_a, "kare_b": kare_b,
                              "son_ok": False, "kb": round(kb_max, 3), "joint": None,
                              "roller": []})
            continue
        scroll_var = bool(scroll[a:b + 1].any())
        yogunluk = min(1.0, float(say[a:b + 1].max()) / 8.0)
        joint = kb_max * (1.0 + 0.3 * scroll_var + 0.35 * son_capa_orani + 0.15 * yogunluk)
        roller = sorted({m.lower()
                          for sl in kare_satirlari for s in sl for m in cc._ROL.findall(s)})
        kayitlar.append({"a": a, "b": b, "kare_a": kare_a, "kare_b": kare_b,
                          "son_ok": True, "kb": round(kb_max, 3), "joint": round(joint, 3),
                          "roller": roller})
        if kb_max >= EŞIK and (en_iyi is None or joint > en_iyi[0]):
            en_iyi = (joint, a, b, kb_max, scroll_var)

    if en_iyi is None:
        kurtarma = _scroll_kurtarma(g, idx, cc, scroll, jbayrak, n, fps, stride)
        if kurtarma is not None:
            ks, ke = kurtarma
            kare_ks, kare_ke = _kare_no(g[idx[ks]]), _kare_no(g[idx[ke]])
            kayitlar.append({"a": ks, "b": ke, "kare_a": kare_ks, "kare_b": kare_ke,
                              "son_ok": True, "kb": 1.0, "joint": 1.0,
                              "roller": ["scroll_kurtarma"]})
            en_iyi = (1.0, ks, ke, 1.0, True)
        else:
            degerlendirilmis = [k for k in kayitlar if k["son_ok"]]
            if not degerlendirilmis:
                sebep = "tüm adaylar SON_ERISIM'e takıldı"
            else:
                en_iyi_kb = max(k["kb"] for k in degerlendirilmis)
                sebep = f"içerik-eşiği geçilemedi (en iyi kb={en_iyi_kb:.2f})"
            return Sonuc(-1, "kredi_yok", 0.0, notlar=sebep, seri={"adaylar": kayitlar})

    joint, a, b, kb, scroll_var = en_iyi
    # kazanan koşuda scroll-aktif kare oranı — statik/scroll ayrımı (T5) +
    # ardışık-scroll uzunluğu (T4 scroll-tip ölçütü, yalnız notlarda/teşhiste
    # kullanılır — bkz. aşağıdaki geri-birleştirme yorumu).
    scroll_orani = float(scroll[a:b + 1].mean()) if b >= a else 0.0
    ardisik_scroll = _ardisik_maks(scroll[a:b + 1]) if b >= a else 0

    # ── T4: geri-birleştirme — SON_ERISIM'e takılmış ÖNCEKİ adaylarla birleş ──
    # ÖNCE denenir (kazanan koşunun KENDİ başlangıcı `a`'dan) — içerik-çapalı
    # budama/genişletme yalnız birleştirme uygulanamazsa devreye girer (budama
    # onset'i `a`'dan uzaklaştırır; boşluk hesabı candidate-candidate mesafesine
    # değil budanmış noktaya göre yapılırsa DİPTEKİLER gibi vakalarda boşluk
    # yapay şekilde şişer — DİPTEKİLER'in gerçek boşluğu 28 örnek-kare ama budama
    # sonrası nokta kullanılırsa ~51 ölçülüyor, KISA_BOSLUK'u yanlışlıkla aşıyor).
    #
    # Atlas kanıtı (2. tur): MESLEĞE_DÖNÜŞ / KARAVAN / "6" / DİPTEKİLER aynı
    # kalıbı gösteriyor — gerçek-onset SON_ERISIM'e takılmış bir ÖNCEKİ adayın
    # içinde/başında, kazanan koşuyla arasında KISA bir boşluk var (16-38
    # örnek-kare, ölçüldü). Plan taslağı bu köprülemeyi "scroll-tip" (scroll_oran
    # ≥0.3 VEYA ardışık≥16) koşularla sınırlıyordu; ÖLÇÜM bunu çürüttü: bu dört
    # hedefin scroll_oran'ı 0.07-0.24, ardışık-maks 3-5 — İKİSİ DE eşiğin altında
    # (yalnız MESLEĞE_DÖNÜŞ=0.95 ve TAKKELİ_MELEK=0.86 "scroll-tip" eşiğini
    # geçiyor). Güvenlik scroll oranından değil aşağıdaki İKİ kapıdan geliyor:
    #   (1) KISA boşluk — HARİKA_KÖPEK_5'in önceki adayına boşluk ~84 örnek-kare,
    #       bloklanır (negatif-guard, sahne+tabela riski, atlas kanıtlı).
    #   (2) içerik-kapısı — İNİŞLİ_ÇIKIŞLI'nın boşluğu KISA (14) ama içerik
    #       CJK/şarkı-adı karışığı, kredi_karti_mi hiçbir örnekte geçmiyor →
    #       bloklanır.
    # Bu yüzden birleştirme "scroll-tip" şartı ARANMADAN, kazanan her koşu için
    # denenir; gerekçe atlasa da düşülmüştür (bkz. commit notu).
    KISA_BOSLUK = max(20, int(fps * 3.6 / stride))  # ~45 örnek-kare (38 geçmeli/84 engellenmeli — ölçüldü)
    TOPLAM_BUTCE = 120  # plan T4 — _statik_icerik_onset.azami_geri ile AYNI birim/büyüklük
    onset_birlesik, birlesme_notu = None, None
    try:
        w = adaylar.index((a, b))
    except ValueError:
        w = -1
    if w > 0:
        butce = TOPLAM_BUTCE
        onset_z = a
        k = w
        birlesenler = []
        while k > 0 and butce > 0:
            a_prev, b_prev = adaylar[k - 1]
            bosluk = onset_z - b_prev - 1
            if bosluk < 0 or bosluk > KISA_BOSLUK or bosluk > butce:
                break
            if not _gecis_icerik_onayi(g, idx, cc, a_prev, b_prev):
                break
            onset_z = a_prev
            butce -= bosluk
            k -= 1
            birlesenler.append(f"[{_kare_no(g[idx[a_prev]])}-{_kare_no(g[idx[b_prev]])}]")
        if onset_z < a:
            onset_birlesik = onset_z
            birlesme_notu = f"geri-birlesme={','.join(birlesenler)}"

    ek_not = ""
    if onset_birlesik is not None:
        onset = onset_birlesik
        ek_not = birlesme_notu
    elif scroll_orani >= 0.3:
        # SCROLL-tip koşu — Görev 4'ün alanı, burada DOKUNMA. Mevcut davranış:
        # scroll varsa kart→scroll geri-tarama.
        onset = a
        if scroll_var and onset < len(scroll):
            alt = max(0, onset - int(fps * 1.5 / stride))
            while onset - 1 >= alt and onset - 1 < len(scroll) and scroll[onset - 1] and jbayrak[onset - 1]:
                onset -= 1
    else:
        # STATİK-tip koşu (T5) — koşu sınırı değil İÇERİK çapası: ileri-budama
        # (koşu başı kredi-dışı metni atla) + geri-genişletme (kartın gerçek
        # başlangıcına geri çek). Atlas kanıtı: ERKEN_METIN (KNUTE/TESS/...).
        onset, ek_not = _statik_icerik_onset(g, idx, a, b)

    return Sonuc(
        start_frame=_kare_no(g[idx[onset]]),
        yontem="kutu+scroll+içerik" if scroll_var else "kutu+içerik",
        guven=round(kb, 2),
        dy_medyan=float(np.median(dys[a:b])) if a < len(dys) else 0.0,
        notlar=(f"aday={len(adaylar)} seçilen=[{_kare_no(g[idx[a]])}-{_kare_no(g[idx[b]])}] "
                f"kb={kb:.2f} joint={joint:.2f} scroll_oran={scroll_orani:.2f} "
                f"ardisik={ardisik_scroll}"
                + (f" {ek_not}" if ek_not else "")),
        seri={"adaylar": kayitlar},
    )


if __name__ == "__main__":
    import sys
    if "--v5" in sys.argv:
        fn = tespit_v5
    elif "--v4" in sys.argv:
        fn = tespit_v4
    else:
        fn = tespit
    r = fn([a for a in sys.argv[1:] if not a.startswith("--")][0])
    print(f"start={r.start_frame} yöntem={r.yontem} güven={r.guven:.2f}  {r.notlar}")
