"""MAGIC — birleşik kompozitör ADAYI: lebron iskeleti + ibrahimovic'in
kanıtlanmış dört mekanizması (Çağatay 2026-08-15: "ikisini birleştireceğiz").

Köken: lebron zaten ibrahimovic'in ölçüm çekirdeğinin (`_iou`, `_icerik_ncc`,
`_dy_dogrula`, `cift_olc`, `_segment_kanvas`) devamıydı — 2026-08-04'te
birincil yapıldı ama birucum ölçüm kaydı yoktu (GUNLUK 2026-08-11). Magic,
lebron'un İYİ yanlarını aynen tutar ve ibrahimovic'in belgeli arıza sınıflarını
düzelten dört mekanizmayı üstüne koyar:

  LEBRON'DAN KALAN (dokunulmaz):                       Ne kazandırır:
    AI el-feneri maskesi (Paddle det poligon)           içeriğe duyarlı metin izolasyonu
    2D faz-korelasyonu + küçük-dy sahte-scroll bekçisi  kucuk-dev-adam Frankenstein sayfası
    AKILLI BIÇAK (baş/son kırpma)                       jenerik dışı çöp kareler
    dinamik mikro-scroll eşiği min(10, max(2, 1.5·n))   parti sınıfı yavaş sürünme
    unicode yükleme + nat-sort + tek okuma              İHTİRAS 'İ', kare_9/kare_10

  İBRAHİMOVİC'TEN PORTE EDİLEN (kaynak yorumlarıyla):   Ne düzeltir:
    1. PLATO v4 + dissolve bekçisi (koşu_platolari)     kucuk-dev-adam dissolve-zinciri,
                                                         karadeniz fade yarım-kartları
    2. TOKEN-KİMLİKLİ ayni_icerik (birincil kanıt)      statik zemin (jetgiller/totoro):
                                                         NCC/IoU zemine domine oluyordu
    3. SOBEL yedek yolu (2 tetik)                       parti parlak zemin + OCR patlama
                                                         anında kaba threshold(180) yerine
    4. TOKEN IZGARA sondajı (koşu ≥ 6 → her 3.)         düz istikrar eğrisi kart yutması
                                                         (427-koşu vakası)

KULE İÇİ TOKEN MOTORU: ibrahimovic tokenları üretim F1b/F1c'e `saglik`
yan-kapısıyla alıyordu (bilinen borç). Magic aynı Paddle'ı KULENİN İÇİNDEN
alır (`derleyici.get_ocr_engine`) — yan kapı yok, borç taşınmaz.

TEST DİKİŞLERİ (okuyucudaki `sor` deseni): `flashlight` ve `token_saglayici`
geri-çağrıları enjekte edilebilir → magic'in KARAR mantığı GPU'suz test edilir.
Paddle'a dokunan tek yol `_varsayilan_*` sarmalayıcılarıdır.

ABLASYON: derle(..., ozellikler={"plato": False, ...}) — kıyas koşusu
(kompozitor_kiyas.py) özellik kapalı varyantları ayrı motor olarak ölçer.

BU DOSYA ADAYDIR: hiçbir çalışma-zamanı dosyası onu import etmez
(test_izolasyon kilidi). Ölçüm kazanırsa src/'ye terfi eder; terfi edene
kadar config.yaml'a girmez. derleyici.py'ye DOKUNULMAZ — sadakat kapısının
parite iddiası bozulamaz.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# aday → src yönü serbesttir (yasak olan tersi). src/ yolu burada garanti
# edilir ki magic hem testlerden hem ölçüm yatağından aynı şekilde açılsın.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from kural import H_MAKS

# ---- LEBRON sabitleri (derleyici.py'den — birebir) ------------------------ #
RESP_ESIK = 0.05
MIN_ADIM = 0.5
MAKS_ADIM_ORAN = 0.85
MIN_MASKE_PX = 400
ORTUSME_DURAKSAMA = 0.55
AYNI_IOU_GUCLU = 0.60
AYNI_NCC_TABAN = 0.20
KUCUK_DY_ESIK = 3.0
NET_KRIP_ESIK_YONLU = 10.0
FARK_ESIK = 30
FARK_TABAN_KATSAYI = 3.0
FARK_MUTLAK_MIN = 800
METIN_KONSANTRASYON = 0.35
VARLIK_ESIK = 60

# ---- İBRAHİMOVİC'TEN PORTE EDİLEN sabitler (aday/ibrahimovic.py'den) ------ #
MASKE_KAPSAMA_ESIK = 0.25  # PARLAKLIK maskesi kareyi dolduruyorsa ölçüm
                           # yozlaşmış (parti). Dikkat: eşik parlaklık tabanına
                           # ölçülüdür — el-feneri maskesi sağlıklı filmde bile
                           # 0.2-0.5 doluşur (dilate kutuları); oradan ölçülürse
                           # sağlıklı film sobel'e düşer (acemiler dersi,
                           # 2026-08-17: MGM kartı yutuldu, recall 0.857→0.753)
MASK_ESIK = 110            # parlak künye harfleri (benimle/gercek doğrulandı)
PLATO_IOU = 0.75           # ardışık varlık-IoU bunun üstü = istikrarlı koşu
TOKEN_CONF_ESIK = 0.40     # kimlik tokenına girecek rec kutusunun asgari güveni
TOKEN_MIN_GUVEN = 3        # iki tarafta da en az bu token yoksa token hükmü
TOKEN_KAPSAMA = 0.60       # |kesişim|/min(|a|,|b|) bunun üstü → AYNI kart
TOKEN_YENI_ESIK = 0.25     # BENİMLE DERSİ (2026-08-17): gelen karenin
                           # referansta OLMAYAN token oranı bunun altındaysa
                           # tekrar-baskısıdır (jetgiller: yenisi ≈ 0, yalnız
                           # OCR greni); üstündeyse KART YENİ İÇERİK TAŞIYOR
                           # (benimle: "UNIT PRODUCTION MANAGER" kartı önceki
                           # kartın adlarını + kendi bloğunu taşıyordu —
                           # kapsama 0.6+ çıkıp sayfa yutuldu, recall
                           # 0.786→0.738)
TOKEN_YENI_KESKI_ESIK = 0.05  # AYNI hükmün KESME/SÜREKLİLİK bağlamındaki
                           # keskin eşiği (gece dersi: benimle'nin son kartı
                           # scroll-kuyruğuyla 0.92 kapsama + 0.14 yeni
                           # taşıyordu — KESME bağlamında bu YENİ SAYFADIR;
                           # token vetosu orada yalnız neredeyse-birebir
                           # tekrara (≤0.05) tanınır)
IZGARA_ADIM = 3            # uzun duraksama koşusunda token sondaj adımı
IZGARA_MIN_KOSU = 6        # sondaj bunun altındaki koşularda gerekmez

# ---- ablasyon bayrakları (varsayılan: hepsi AÇIK) ------------------------- #
OZELLIKLER = {"plato": True, "token_kimlik": True, "sobel": True, "izgara": True}


# --------------------------------------------------------------------------- #
# küçük saf yardımcılar — derleyici.py'den KOPYA (oradan import bütün paddle
# yığınını sürükler; adayın testi GPU'suz kalmalı. Terfi edilirse ortak hafif
# modüle çıkarılırlar — o ayrı bir iş, derleyici.py'ye dokunmadan yapılmaz).
# --------------------------------------------------------------------------- #
def _iou(m1, m2):
    kes = float(np.logical_and(m1 > 0, m2 > 0).sum())
    bir = float(np.logical_or(m1 > 0, m2 > 0).sum())
    return kes / bir if bir else 1.0


def _icerik_ncc(g1, g2, v1, v2):
    union = np.logical_or(v1 > 0, v2 > 0)
    if int(union.sum()) < MIN_MASKE_PX:
        return 0.0
    a, b = g1[union].astype(np.float32), g2[union].astype(np.float32)
    sa, sb = float(a.std()), float(b.std())
    if sa < 1e-3 or sb < 1e-3:
        return 0.0
    return float(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb))


def _dy_dogrula(g1, g2, m1, dy):
    h = g1.shape[0]
    k = int(round(abs(dy)))
    if k <= 0 or k >= h:
        return None
    if dy < 0:
        sec = m1[k:, :] > 0
        a, b = g1[k:, :], g2[:h - k, :]
    else:
        sec = m1[:h - k, :] > 0
        a, b = g1[:h - k, :], g2[k:, :]
    if int(sec.sum()) < MIN_MASKE_PX:
        return None
    av, bv = a[sec].astype(np.float32), b[sec].astype(np.float32)
    sa, sb = float(av.std()), float(bv.std())
    if sa < 1e-3 or sb < 1e-3:
        return None
    return float(((av - av.mean()) * (bv - bv.mean())).mean() / (sa * sb))


def _fark_px(ga, gb):
    sa, sb_ = float(ga.std()), float(gb.std())
    if sb_ > 1e-3:
        gb = (gb - gb.mean()) * (sa / sb_) + ga.mean()
    return int((np.abs(ga - gb) > FARK_ESIK).sum())


def calculate_sharpness(gray):
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def _segment_kanvas(ims, ofsetler):
    h, w = ims[0].shape[:2]
    taban = min(ofsetler)
    ofs = [o - taban for o in ofsetler]
    toplam = int(round(max(ofs))) + h
    kanvas = np.zeros((toplam, w, 3), dtype=np.uint8)
    ofs_arr = np.array(ofs)
    for y in range(toplam):
        aday = np.where((ofs_arr <= y) & (y < ofs_arr + h))[0]
        if len(aday) == 0:
            continue
        best = aday[np.argmin(np.abs((y - ofs_arr[aday]) - h / 2))]
        kanvas[y] = ims[best][int(y - ofs_arr[best])]
    return kanvas


def cift_olc(olcum, bosluk_px, griler, varliklar, h, w):
    """Ardışık çiftleri ölç ve sınıfla — lebron'un cift_olc'u (birebir kopya;
    2D faz-korelasyon + küçük-dy sahte-scroll bekçisi)."""
    han = cv2.createHanningWindow((w, h), cv2.CV_32F)
    out = []
    for i in range(len(olcum) - 1):
        m1, m2 = olcum[i], olcum[i + 1]
        px1, px2 = bosluk_px[i], bosluk_px[i + 1]
        if px1 < MIN_MASKE_PX or px2 < MIN_MASKE_PX:
            out.append({"dy": 0.0, "resp": 0.0, "sinif": "duraksama_bos"})
            continue

        (_, dy), resp = cv2.phaseCorrelate(m1 * han, m2 * han)
        kayit = {"dy": round(float(dy), 2), "resp": round(float(resp), 4)}

        if resp >= RESP_ESIK and MIN_ADIM <= abs(dy) <= MAKS_ADIM_ORAN * h:
            dogru = _dy_dogrula(griler[i], griler[i + 1], m1, dy)
            kayit["dogrulama"] = None if dogru is None else round(dogru, 3)
            kayit["sinif"] = "scroll"
            if abs(dy) <= KUCUK_DY_ESIK:
                ncc = _icerik_ncc(griler[i], griler[i + 1], varliklar[i], varliklar[i + 1])
                ayni = ncc >= 0.60 or (_iou(varliklar[i], varliklar[i + 1]) >= AYNI_IOU_GUCLU
                                       and ncc >= AYNI_NCC_TABAN)
                if not ayni:
                    kayit["sinif"] = "duraksama_belirsiz"
        elif resp >= RESP_ESIK and abs(dy) < MIN_ADIM:
            kayit["sinif"] = "duraksama"
        else:
            kayit["sinif"] = "duraksama_belirsiz" if _iou(m1, m2) >= ORTUSME_DURAKSAMA else "kesme"
        out.append(kayit)
    return out


# --------------------------------------------------------------------------- #
# ibrahimovic'ten taşınan mekanizmeler — modül düzeyinde SAF tutulurlar ki
# testleri sentetik veriyle, GPU'suz koşsun.
# --------------------------------------------------------------------------- #
def sobel_metin_maskesi(gray):
    """Kenar-enerjisi maskesi (ibrahimovic.sobel_metin_maskesi — birebir).

    Parlak-zeminli filmlerde parlaklık/eşik maskesi yozlaşır (gökyüzü/duvar
    maskeyi doldurur, korelasyon statik zemine kilitlenir — parti vakası).
    Düz parlak alanın gradyanı yoktur; yazı kenarları güçlü gradyandır.
    """
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    mag = cv2.magnitude(gx, gy)
    m = (mag > (mag.mean() + mag.std())).astype(np.uint8)
    return cv2.dilate(m, np.ones((7, 7), np.uint8))


def token_ayni(ta: set, tb: set, kesin: bool = False) -> bool | None:
    """Token-kimlik hükmü: kapsama-oranı + yeni-içerik ayrımcısı.
    None = token kanıtı yetersiz (TOKEN_MIN_GUVEN altı) → çağıran geometrik
    fallback'e düşer.

    `ta` GELEN kare, `tb` referans — ayni_icerik'in bütün çağrı biçimlerinde
    (kesme/candidate/süreklilik) ilk argüman gelen karedir.

    `kesin=False` (aday döngüsü): tekrar-baskısı eşiği gevşek — kapsama
    yüksek + yeni ≤ TOKEN_YENI_ESIK → aynı kart (jetgiller: aynı kartın
    yeniden çevrimi, yeni token ≈ 0).
    `kesin=True` (kesme/süreklilik): 'aynı' için neredeyse-birebir tekrar
    gerekir (yeni ≤ TOKEN_YENI_KESKI_ESIK) — KESME zaten ölçümün 'içerik
    değişti' demesi; benimle'nin son kartı scroll-kuyruğuyla 0.92 kapsama
    + 0.14 yeni taşıyordu ve YENİ SAYFAYDI (gece dersi)."""
    if min(len(ta), len(tb)) < TOKEN_MIN_GUVEN:
        return None
    if len(ta & tb) / min(len(ta), len(tb)) < TOKEN_KAPSAMA:
        return False
    esik = TOKEN_YENI_KESKI_ESIK if kesin else TOKEN_YENI_ESIK
    return len(ta - tb) / len(ta) <= esik


def kosu_platolari(kareler, varliklar, keskinlikler=None) -> list[int]:
    """Duraksama koşusunun kart temsilcileri — PLATO v4 (ibrahimovic'ten).

    Temsilci GEÇİŞTEN EN UZAK kare olmalı ama sabit istikrar-EŞİĞİ kullanılamaz
    (grenli soluk kartın ardışık-IoU'su dissolve'la aynı banda düşer). Eşik
    yerine ŞEKİL: istikrar eğrisinin (ardışık varlık-IoU) YEREL TEPELERİ tutulan
    kartların ortasıdır; dissolve daima çukurda kalır. Boş kareler koşuyu böler.

    Magic farkı: platonun orta karesi yerine (ibrahimovic) plato İÇİNDE en
    keskin kare seçilir — lebron'un kalite ölçütü plato sınırları içinde eşitlik
    bozucu. Plato istikrarlı olduğu için keskinlik burada geçiş-karesi seçmez;
    ölçüm aksini söylerse geri alınır.

    keskinlikler=None → saf ibrahimovic davranışı (plato-orta kare).
    """
    temsilciler: list[int] = []
    kosu: list[int] = []

    def kosuyu_isle(kosu: list[int]) -> None:
        if not kosu:
            return
        if len(kosu) < 3:
            temsilciler.append(kosu[-1])
            return
        s = [_iou(varliklar[a], varliklar[b]) for a, b in zip(kosu, kosu[1:])]
        kare_s = [max(s[max(0, j - 1)], s[min(j, len(s) - 1)]) for j in range(len(kosu))]
        # DÜZ plato duyarlılığı: eşit-istikrar bölgesi tek tepe sayılır.
        # ('>=sol, >sag' saf kuralı platonun SON karesini seçiyordu — son kare
        # geçişe komşudur; kucuk-dev-adam'da kart2 platosu yerine 19. kare
        # (parlama) seçildi, segment_kareler dökümüyle kanıtlandı.)
        tepeler: list[tuple[list[int], float]] = []
        j = 0
        while j < len(kosu):
            k0 = j
            while j + 1 < len(kosu) and abs(kare_s[j + 1] - kare_s[k0]) <= 0.02:
                j += 1
            sol = kare_s[k0 - 1] if k0 > 0 else -1.0
            sag = kare_s[j + 1] if j < len(kosu) - 1 else -1.0
            if kare_s[k0] >= sol and kare_s[k0] > sag:
                tepeler.append((kosu[k0:j + 1], kare_s[k0]))
            j += 1
        # GEÇİŞ-KARESİ FİLTRESİ (kucuk-dev-adam kare-20 vakası): istikrarı
        # PLATO_IOU altındaki "tepe" aslında iki kart arası karışım anıdır —
        # sayfa TEMSİLCİSİ OLAMAZ. Ama koşuda hiçbir kare eşiği tutturamıyorsa
        # (grenli soluk kartlar — karadeniz) filtresiz tepelere geri düşülür:
        # filtre temsilci SEÇİMİNİ inceltir, içerik ATLAMAZ.
        saglam = [bolge for bolge, sk in tepeler if sk >= PLATO_IOU]
        for bolge in (saglam if saglam else [bolge for bolge, _ in tepeler]):
            if keskinlikler is None:
                temsilciler.append(bolge[(len(bolge) - 1) // 2])
            else:
                temsilciler.append(max(bolge, key=lambda k: keskinlikler[k]))

    for k in kareler:
        if float(varliklar[k].sum()) >= MIN_MASKE_PX:
            kosu.append(k)
            continue
        kosuyu_isle(kosu)
        kosu = []
    kosuyu_isle(kosu)
    return temsilciler


def adaylar_hesapla(kosu, varliklar, keskinlikler=None, *,
                    plato=True, izgara=True) -> list[int]:
    """Duraksama koşusunun sayfa ADAYLARı: plato temsilcileri + (uzun koşuda)
    token sondaj ızgarası. Izgara adayları token-kimliğe sorulur; karışım
    kareleri token-KAPSAMA sayesinde kendiliğinden elenir (karışım, referans
    kartın tokenlarını İÇERİR → "aynı" → sayfa açmaz; saf yeni kart → açar).

    plato=False → lebron davranışı: koşunun en keskin TEK karesi."""
    if not kosu:
        return []
    if not plato:
        return [max(kosu, key=lambda k: keskinlikler[k])] if keskinlikler else [kosu[-1]]
    adaylar = list(dict.fromkeys(kosu_platolari(kosu, varliklar, keskinlikler)))
    if izgara and len(kosu) >= IZGARA_MIN_KOSU:
        adaylar.extend(k for k in kosu[::IZGARA_ADIM] if k not in adaylar)
    return sorted(set(adaylar))


# --------------------------------------------------------------------------- #
# varsayılan sağlayıcılar — Paddle'a DOKUNAN tek yerler (tembel import).
# Testler bu sarmalayıcıları hiç çağırmaz; kendi sahte sağlayıcılarını verir.
# --------------------------------------------------------------------------- #
def el_feneri_govde(img, predict, sobel_acik: bool):
    """AI el-feneri gövdesi: lebron'un ai_flashlight_mask'i + TEK fark — OCR
    istisnası anında kaba threshold(180) yerine (sobel açıksa) Sobel kenar
    yolu. `predict` geri-çağrısı test dikişidir (sahte motor → GPU'suz sınama).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    maske = np.zeros((h, w), dtype=np.uint8)
    try:
        for res in predict(img):
            if res is None:
                continue
            if isinstance(res, dict) and 'dt_polys' in res:
                for box in res['dt_polys']:
                    cv2.fillPoly(maske, [np.array(box, dtype=np.int32)], 255)
            elif isinstance(res, list):
                for item in res:
                    if isinstance(item, list) and len(item) == 2 and isinstance(item[1], tuple):
                        cv2.fillPoly(maske, [np.array(item[0], dtype=np.int32)], 255)
                    elif isinstance(item, np.ndarray):
                        cv2.fillPoly(maske, [item.astype(np.int32)], 255)
    except Exception as exc:
        if sobel_acik:
            print(f"[magic] OCR HATA: {type(exc).__name__}: {exc} -> Sobel yedek yolu",
                  flush=True)
            return np.where(sobel_metin_maskesi(gray) > 0, gray, 0)
        _, maske = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

    maske = cv2.dilate(maske, np.ones((5, 5), np.uint8), iterations=2)
    return cv2.bitwise_and(gray, gray, mask=maske)


def _varsayilan_el_feneri(sobel_acik: bool):
    """Varsayılan el-feneri: kulenin Paddle'ı. Sadakat kapısının altındaki
    derleyici.py'ye dokunmadan aynı motoru kullanır."""
    from derleyici import get_ocr_engine

    def isik(img, _idx):
        return el_feneri_govde(img, get_ocr_engine().predict, sobel_acik)

    return isik


def _varsayilan_token_saglayici():
    """Kule içi det+rec token kümesi — ibrahimovic'in saglik yan-kapısı YOK.
    Sağlayıcı (görüntü, indeks) alır; motor ölürse/patlarsa boş küme döner
    (çağıran geometrik fallback'e düşer; 'yazı yok' ile 'okuyamadık'
    karışmaz — ayni_icerik yine fark tabanına gider)."""
    from derleyici import get_ocr_engine

    def sor(img, _idx):
        toks: set[str] = set()
        try:
            ocr = get_ocr_engine()
            for res in ocr.predict(img):
                if res is None:
                    continue
                ciftler = []
                if isinstance(res, dict):
                    ciftler = list(zip(res.get("rec_texts") or [],
                                       res.get("rec_scores") or []))
                elif isinstance(res, list):
                    for item in res:
                        if isinstance(item, list) and len(item) == 2 \
                                and isinstance(item[1], tuple):
                            ciftler.append(item[1])
                for metin, conf in ciftler:
                    if conf is None or float(conf) < TOKEN_CONF_ESIK:
                        continue
                    for t in str(metin).split():
                        if len(t) >= 3:
                            toks.add(t)
        except Exception:
            return set()
        return toks

    return sor


def fark_tabani(ciftler: list[dict], griler: list[np.ndarray]) -> float:
    """Filmin gren-tabanı: HAREKETSİZ çiftlerin piksel-farkı = saf gürültü
    (lebron/ibrahimovic ortak yolu).

    İKİ REDDEDİLEN yol (ölçümle, 2026-08-17 gece):
      * kesme-çiftlerinden fallback (hayat-agaci fırtınası için denenmişti):
        benimle-dans-et'te 51 scroll + 2 kesme var, kesme farkları GERÇEK
        içerik değişimi (39-57k px) → taban 45k'ye şişti → kimlik öldü,
        son kart yutuldu (recall 0.786→0.738). Kesme çifti gren DEĞİL,
        değişimdir — tabana girmez.
      * hayat-agaci fırtınasının gerçek ilacı metin kapısındaydı: halüsinasyon
        token'ları (≥2) profilden geçemeyen gren karelerini 'metin' sanıyordu;
        metin_gibi artık yalnız profile karar verir (aşağıda)."""
    ornek = [_fark_px(griler[i], griler[i + 1]) for i, c in enumerate(ciftler)
             if c["sinif"] in ("duraksama", "duraksama_bos", "duraksama_belirsiz")][:40]
    return float(np.median(ornek)) if ornek else 500.0


def metin_profili(gray, metin_maskesi) -> bool:
    """Sayfa-açılış kapısının GEOMETRİK kolu (lebron.metin_gibi ile aynı
    fikir): satır-profilin en yoğun %12.5'i toplamın METIN_KONSANTRASYON'unu
    taşıyorsa bu kare 'metin sayfası'dır (gök/doku greni yayılır, yazı toplanır)."""
    toplam = float(metin_maskesi.sum())
    if toplam < MIN_MASKE_PX:
        return False
    prof = np.sort(metin_maskesi.sum(axis=1))[::-1]
    ust = float(prof[: max(1, len(prof) // 8)].sum())
    return ust / toplam >= METIN_KONSANTRASYON


# --------------------------------------------------------------------------- #
# ana motor
# --------------------------------------------------------------------------- #
def derle(
    slug: str,
    kare_dizini: str | None = None,
    ims: list[np.ndarray] | None = None,
    *,
    ozellikler: dict | None = None,
    flashlight=None,
    token_saglayici=None,
) -> tuple[np.ndarray | None, dict]:
    """Kareleri master kanvasa bağlar — (kanvas, manifest). Lebron'un derle()
    akışı; duraksama-koşusu dalı ibrahimovic'in plato+ızgara mantığıyla, kimlik
    hükümleri token-birincil, ölçüm yolu film-bazlı Sobel'e düşebilir."""
    t0 = time.time()
    oz = {**OZELLIKLER, **(ozellikler or {})}

    if ims is None:
        if not kare_dizini or not os.path.isdir(kare_dizini):
            return None, {"slug": slug, "durum": "kare_yok", "kare": 0,
                          "sebep": "Klasor bulunamadi"}
        from yukleyici import kareleri_yukle
        ims, _ = kareleri_yukle(kare_dizini)
    if len(ims) < 2:
        return None, {"slug": slug, "durum": "kare_yok", "kare": len(ims)}

    h, w = ims[0].shape[:2]
    ims = [im for im in ims if im.shape[:2] == (h, w)]
    griler = [cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) for im in ims]

    isik = flashlight if flashlight is not None else _varsayilan_el_feneri(oz["sobel"])
    tokenler = token_saglayici if token_saglayici is not None else _varsayilan_token_saglayici()

    token_onbellek: dict[int, set] = {}

    def _tokenlar(i: int) -> set:
        if i not in token_onbellek:
            token_onbellek[i] = set(tokenler(ims[i], i) or ())
        return token_onbellek[i]

    # --- ölçüm yolu kararı — ÇİFT-ÖLÇÜM YARIŞMASI (üç ders, 2026-08-17):
    # Ders 1 (acemiler): karar PARLAKLIK kapsamasından verilir, el-fenerinin
    #   doluluğundan değil — fener maskesi sağlıklı filmde bile 0.2-0.5 doludur.
    # Ders 2 (totoro): parlaklık kapsaması yüksek diye koşulsuz sobel'e geçmek
    #   YANLIŞ — sobel zemin dokusunu da maskeler; 2D korelasyon statik zemin
    #   kenarına kilitlenir (totoro: fener scroll=7, sobel scroll=0; master
    #   7624→1920, recall 0.24→0.006).
    # Ders 3 (jetgiller): "fener hiç hareket bulamadıysa" kurtarması da YETMEZ
    #   — fener sınırda 3 scroll bulabiliyor (kapsama 0.872'de) ve zayıf master
    #   üretiyor; sobel aynı filmde kayarı düzgün takip ediyor.
    # ÇÖZÜM: kapsama yozsa İKİ substrat da ölçülür; daha ÇOK scroll çifti
    #   bulan kazanır (eşitlikte fener). totoro 7-0 fener · jetgiller
    #   3-ÇOK sobel · hayat 75-7 fener · parti 0-ÇOK sobel — dört ders de
    #   doğru tarafa düşer.
    ai_griler = [np.asarray(isik(im, i), dtype=np.uint8) for i, im in enumerate(ims)]
    ornek_adim = max(1, len(griler) // 10)
    kapsama = float(np.median([(g > MASK_ESIK).mean() for g in griler[::ornek_adim]]))

    fener_olcum = [g.astype(np.float32) for g in ai_griler]
    fener_bosluk = [int((g > 0).sum()) for g in ai_griler]
    fener_varlik = [(g > VARLIK_ESIK).astype(np.float32) for g in ai_griler]
    ciftler = cift_olc(fener_olcum, fener_bosluk, griler, fener_varlik, h, w)
    olcum_yolu = "ai_flashlight"
    sobel_kurtarma = False

    if oz["sobel"] and kapsama > MASKE_KAPSAMA_ESIK:
        sobeller = [sobel_metin_maskesi(g) for g in griler]
        sob_olcum = [np.where(sb > 0, g, 0).astype(np.float32)
                     for sb, g in zip(sobeller, griler)]
        sob_bosluk = [int(sb.sum()) for sb in sobeller]
        sob_varlik = [(g > VARLIK_ESIK).astype(np.float32) for g in griler]
        sob_ciftler = cift_olc(sob_olcum, sob_bosluk, griler, sob_varlik, h, w)
        fener_scroll = sum(1 for c in ciftler if c["sinif"] == "scroll")
        sob_scroll = sum(1 for c in sob_ciftler if c["sinif"] == "scroll")
        if sob_scroll > fener_scroll:
            olcum, bosluk = sob_olcum, sob_bosluk
            varliklar, metin_maskeleri = sob_varlik, [sb.astype(np.float32) for sb in sobeller]
            ciftler = sob_ciftler
            olcum_yolu = "sobel"
            sobel_kurtarma = True
    if olcum_yolu == "ai_flashlight":
        olcum, bosluk, varliklar = fener_olcum, fener_bosluk, fener_varlik
        metin_maskeleri = fener_varlik

    # === AKILLI BIÇAK (TRIM) — lebron'dan birebir ===
    baslangic = 0
    tolerans = 50
    durma_toleransi = 125

    for idx_trim, c in enumerate(ciftler):
        if abs(c.get("dy", 0)) > 1.0:
            ileri = [abs(ciftler[j].get("dy", 0)) > 1.0
                     for j in range(idx_trim, min(idx_trim + 10, len(ciftler)))]
            if sum(ileri) >= 5:
                baslangic = max(0, idx_trim - tolerans)
                break

    bitis = len(ciftler) - 1
    for idx_trim in range(baslangic, len(ciftler)):
        if abs(ciftler[idx_trim].get("dy", 0)) < 0.5:
            ileri = [abs(ciftler[j].get("dy", 0)) < 0.5
                     for j in range(idx_trim, min(idx_trim + durma_toleransi, len(ciftler)))]
            if len(ileri) == durma_toleransi and all(ileri):
                bitis = min(len(ciftler) - 1, idx_trim + tolerans)
                break

    ciftler = ciftler[baslangic:bitis]
    ims = ims[baslangic:bitis + 1]
    griler = griler[baslangic:bitis + 1]
    olcum = olcum[baslangic:bitis + 1]
    varliklar = varliklar[baslangic:bitis + 1]
    metin_maskeleri = metin_maskeleri[baslangic:bitis + 1]
    token_onbellek.clear()  # indeksler kaydı: eski anahtarlar geçersiz

    # filmin gren-tabanı (fark_tabani: hayat-agaci dersi yukarıda)
    fark_taban = fark_tabani(ciftler, griler)

    def ayni_icerik(a: int, b: int, kesin: bool = False) -> bool:
        """Kart kimliği — token 'AYNI' hükmü kesindir ama KESKİNLİĞİ bağlama
        göre değişir; 'FARKLI' hükmü tek başına YETMEZ (hayat-agaci dersi:
        halüsinasyon token'ları 36 sayfa açtı). Yani token DEDUP
        güçlendirir, sayfa AÇMAZ:

          token AYNI (bağlama göre eşikle) → aynı (jetgiller: statik zeminde
            piksel-farkı aynı kartı 'farklı' sanıp tekrar basıyordu)
          token FARKLI veya yetersiz → piksel-farkı karar verir

        `kesin=True` (kesme/süreklilik bağlamı): 'aynı' için neredeyse-birebir
        tekrar gerekir (yeni ≤ TOKEN_YENI_KESKI_ESIK) — KESME zaten ölçümün
        'içerik değişti' demesi; benimle'nin son kartı scroll-kuyruğuyla 0.14
        yeni token taşıyordu ve YENİ SAYFAYDI (gece dersi).
        `kesin=False` (aday döngüsü): tekrar-baskısı eşiği gevşek (0.25)."""
        if oz["token_kimlik"] and token_ayni(_tokenlar(a), _tokenlar(b),
                                           kesin=kesin) is True:
            return True
        return _fark_px(griler[a], griler[b]) <= max(FARK_TABAN_KATSAYI * fark_taban,
                                                     FARK_MUTLAK_MIN)

    def metin_gibi(i: int) -> bool:
        """Sayfa-açılış kapısı — YALNIZ satır profili (lebron'unki; gece dersi
        2026-08-17: token kısayolu halüsinasyona açıktı — hayat-agaci'nin
        gren kareleri 2+ sahte token üretip fırtınanın 36 sayfasını 'metinli'
        sanmıştı. Profil greni yayılır, yazıyı satırlara toplanır.)"""
        return metin_profili(griler[i], metin_maskeleri[i])

    keskinlikler = [calculate_sharpness(g) for g in griler]

    segmentler = []
    seg_im, seg_ofs, akum = [ims[0]], [0.0], 0.0
    ref_idx = 0
    dissolve_kesme = 0

    i = 0
    n_cift = len(ciftler)
    while i < n_cift:
        c = ciftler[i]
        if c["sinif"] == "kesme":
            # kesme de kimlik+metin kapılarından geçer (affedilmeyenler
            # "THE END ×5": fade sıçramaları sorgusuz sayfa açıyordu)
            if ayni_icerik(i + 1, ref_idx, kesin=True) or not metin_gibi(i + 1):
                i += 1
                continue
            segmentler.append((seg_im, seg_ofs))
            seg_im, seg_ofs, akum = [ims[i + 1]], [0.0], 0.0
            ref_idx = i + 1
            i += 1
            continue

        if c["sinif"] == "scroll":
            # SÜREKLİLİK BEKÇİSİ (kucuk-dev-adam): duraksama koşusunda içerik
            # sessizce değişmişse scroll son kareyle DİKİLEMEZ — önce sayfayı
            # kapat, çiftin İLK karesiyle yeni segment aç. Kesintisiz scroll'da
            # ref_idx == i olduğundan bu dal hiç tetiklenmez.
            if ref_idx != i and not ayni_icerik(i, ref_idx, kesin=True):
                segmentler.append((seg_im, seg_ofs))
                seg_im, seg_ofs, akum = [ims[i]], [0.0], 0.0
                ref_idx = i
                dissolve_kesme += 1
            akum += -c["dy"]
            seg_im.append(ims[i + 1])
            seg_ofs.append(akum)
            ref_idx = i + 1
            i += 1
            continue

        # duraksama koşusu: [i+1 .. j]
        j = i
        kosu = []
        kosu_dylar = []
        while j < n_cift and ciftler[j]["sinif"] not in ("scroll", "kesme"):
            kosu.append(j + 1)
            kosu_dylar.append(ciftler[j]["dy"] if ciftler[j]["sinif"] == "duraksama" else 0.0)
            j += 1

        # YAVAŞ-SÜRÜNME (parti): koşunun NET sürüklenmesi anlamlı VE TEK YÖNLÜyse
        # mikro-scroll panoramadır — küsuratlı dy'lerle ekle. Lebron'un DİNAMİK
        # eşiği (sabit 20px parti'de yetmiyordu: scroll çiftleri koşuyu bölüp
        # net'i düşürüyordu).
        anlamli = [d for d in kosu_dylar if abs(d) > 0.3]
        ayni_yon = 0.0
        if anlamli:
            neg = sum(1 for d in anlamli if d < 0)
            pos = sum(1 for d in anlamli if d > 0)
            ayni_yon = max(neg, pos) / len(anlamli)
        net_krip = abs(sum(kosu_dylar))
        dinamik_esik = min(NET_KRIP_ESIK_YONLU, max(2.0, len(kosu) * 1.5))
        if kosu and net_krip >= dinamik_esik and ayni_yon >= 0.8:
            for k, dk in zip(kosu, kosu_dylar):
                akum += -dk
                seg_im.append(ims[k])
                seg_ofs.append(akum)
                ref_idx = k
            i = j
            continue

        # sayfa adayları: plato temsilcileri + token ızgara sondajı
        # (plato=False → lebron'un tek-en-keskin karesi)
        for tem in adaylar_hesapla(kosu, varliklar, keskinlikler,
                                   plato=oz["plato"], izgara=oz["izgara"]):
            if ayni_icerik(tem, ref_idx):
                # aynı içeriğin daha iyi hali TEK-kareli sayfayı yükseltir:
                # token sayısı (okunurluk kanıtı) > varlık toplamı (parlak
                # filmde kör) — ibrahimovic'in yerinde-yükseltmesi
                if len(seg_im) == 1:
                    ta, tr = _tokenlar(tem), _tokenlar(ref_idx)
                    daha_iyi = (len(ta) > len(tr)) if (ta or tr) else (
                        float(varliklar[tem].sum()) > float(varliklar[ref_idx].sum()))
                    if daha_iyi:
                        seg_im[0] = ims[tem]
                        ref_idx = tem
                continue
            if not metin_gibi(tem):
                continue  # metinsiz içerik (gök/doku) sayfa açamaz
            segmentler.append((seg_im, seg_ofs))
            seg_im, seg_ofs, akum = [ims[tem]], [0.0], 0.0
            ref_idx = tem
            dissolve_kesme += 1
        i = j

    segmentler.append((seg_im, seg_ofs))

    def _gecerli_segment(si, so):
        if not si:
            return False
        if len(si) > 1:
            return True
        # tek-kare segment: hangi ölçüm yolundaysak o yolun metin kanıtı
        g = cv2.cvtColor(si[0], cv2.COLOR_BGR2GRAY)
        if olcum_yolu == "sobel":
            return metin_profili(g, sobel_metin_maskesi(g).astype(np.float32))
        m = np.asarray(isik(si[0], 0), dtype=np.uint8)
        v = (m > VARLIK_ESIK).astype(np.float32)
        return metin_profili(m, v)

    parcalar = [_segment_kanvas(si, so) for si, so in segmentler if _gecerli_segment(si, so)]
    if not parcalar:
        parcalar = [_segment_kanvas(si, so) for si, so in segmentler if si]
    if not parcalar:
        return None, {"slug": slug, "durum": "kare_yok", "kare": len(ims),
                      "sebep": "Gecerli segment kalmadi"}
    kanvas = np.vstack(parcalar) if len(parcalar) > 1 else parcalar[0]

    if kanvas.shape[0] > H_MAKS:
        return None, {"slug": slug, "durum": "boy_asimi", "boy": int(kanvas.shape[0])}

    sinif_sayimi = {s: sum(1 for c in ciftler if c.get("sinif") == s)
                    for s in ("scroll", "duraksama", "kesme", "duraksama_bos",
                              "duraksama_belirsiz")}
    scroll_dyler = [abs(c["dy"]) for c in ciftler if c.get("sinif") == "scroll"]
    scroll_dy_medyan = float(np.median(scroll_dyler)) if scroll_dyler else 0.0

    manifest = {
        "slug": slug,
        "durum": "OK",
        "mode": "magic",
        "kare": len(ims),
        "size": [int(kanvas.shape[1]), int(kanvas.shape[0])],
        "segment": len(parcalar),
        "segment_kareler": [len(si) for si, _ in segmentler if si],
        "dissolve_kesme": dissolve_kesme,
        "sinif_sayimi": sinif_sayimi,
        "scroll_dy_medyan": round(scroll_dy_medyan, 2),
        "ciftler": ciftler,
        "olcum_yolu": olcum_yolu,
        "maske_kapsama": round(kapsama, 3),
        "sobel_kurtarma": sobel_kurtarma,
        "ozellikler": oz,
        "sure_s": round(time.time() - t0, 2)
    }
    return kanvas, manifest
