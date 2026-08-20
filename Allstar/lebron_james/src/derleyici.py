"""LEBRON — seçilmiş birleşik kompozitör.

2026-08-18'de 437 filmlik ölçümde ``magic`` deney adıyla seçilen motor artık
kuledeki tek kanonik LeBron derleyicisidir. Deney adı çalışma zamanına,
manifestlere veya yeni raporlara sızmaz.

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
yan-kapısıyla alıyordu (bilinen borç). LeBron aynı Paddle'ı doğrudan kendi
modülünden alır; yan kapı ve dairesel import yoktur.

TEST DİKİŞLERİ (okuyucudaki `sor` deseni): `flashlight` ve `token_saglayici`
geri-çağrıları enjekte edilebilir → LeBron'un karar mantığı GPU'suz test edilir.
Paddle'a dokunan tek yol `_varsayilan_*` sarmalayıcılarıdır.

ABLASYON: derle(..., ozellikler={"plato": False, ...}) — kıyas koşusu
(kompozitor_kiyas.py) özellik kapalı varyantları ayrı motor olarak ölçer.

TERFİ (2026-08-18, Çağatay): 437 filmlik gece koşusunda deney motoru 370
sağlıklı / 0.586 recall medyan / 0.000 dup medyan ile eski LeBron'un
356 / 0.578 / 0.007 sonucunu geçti. Eski motor ``arsiv/legacy_derleyici.py``
altında yalnız kıyas içindir.
"""
from __future__ import annotations

import os
import time
import gc

import cv2
import numpy as np
from paddleocr import PaddleOCR

from kural import H_MAKS, cokmus  # noqa: F401

# Motor arayüzü: kare yardımcıları yükleyiciden yeniden ihraç edilir.
from yukleyici import kare_oku, kareler, kareleri_yukle, yaz  # noqa: F401

_ocr_engine = None


def get_ocr_engine():
    """Kompozisyon, token kimliği ve bant kutusu için tek Paddle örneği."""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = PaddleOCR(lang="en")
    return _ocr_engine


def release_ocr_engine() -> None:
    """Ollama yüklenmeden önce Paddle nesnesini ve CUDA cache'ini bırak."""
    global _ocr_engine
    _ocr_engine = None
    gc.collect()
    try:
        import paddle
        paddle.device.cuda.empty_cache()
    except Exception:
        pass


DEJENERE_KUTU_ORAN = 0.6


def kutu_sayisi(img: np.ndarray) -> int | None:
    """Pikseldeki geçerli metin kutusu sayısı; ölçülemezse ``None``."""
    if img is None:
        return None
    try:
        alan = img.shape[0] * img.shape[1]
        n = 0
        for res in get_ocr_engine().predict(img):
            if res is None:
                continue
            kutular = []
            if isinstance(res, dict) and "dt_polys" in res:
                kutular = list(res["dt_polys"])
            elif isinstance(res, list):
                for item in res:
                    if (isinstance(item, list) and len(item) == 2
                            and isinstance(item[1], tuple)):
                        kutular.append(item[0])
                    elif isinstance(item, np.ndarray):
                        kutular.append(item)
            for box in kutular:
                pts = np.array(box, dtype=np.float64).reshape(-1, 2)
                en = float(pts[:, 0].max() - pts[:, 0].min())
                boy = float(pts[:, 1].max() - pts[:, 1].min())
                if en * boy < DEJENERE_KUTU_ORAN * alan:
                    n += 1
        return n
    except Exception:
        return None


def paddle_satir_kaniti(img: np.ndarray) -> dict | None:
    """Paddle'ın tek ``predict`` çağrısından bant kanıtını çıkar.

    Free OCR metnin birincil kaynağı olmaya devam eder.  Bu kayıt yalnız o
    metnin pikseldeki açık, satır-düzeyi karşılığını bulmak içindir.  Kutular
    ``kutu_sayisi`` ile aynı dejenere-kutu kapısından geçer; tanınmayan veya
    güveni okunamayan bir kutu satır kanıtı olarak yayınlanmaz.
    """
    if img is None:
        return None
    try:
        h, w = img.shape[:2]
        alan = h * w
        kutu_n = 0
        satirlar = []
        for res in get_ocr_engine().predict(img):
            if res is None:
                continue
            if isinstance(res, dict):
                kutular = list(res.get("dt_polys") or [])
                metinler = list(res.get("rec_texts") or [])
                guvenler = list(res.get("rec_scores") or [])
            elif isinstance(res, list):
                # Eski Paddle sonucu: [[polygon, (text, confidence)], ...]
                kutular, metinler, guvenler = [], [], []
                for item in res:
                    if (isinstance(item, list) and len(item) == 2
                            and isinstance(item[1], tuple)):
                        kutular.append(item[0])
                        metinler.append(item[1][0] if item[1] else "")
                        guvenler.append(item[1][1] if len(item[1]) > 1 else None)
                    elif isinstance(item, np.ndarray):
                        kutular.append(item)
            else:
                continue
            for index, box in enumerate(kutular):
                pts = np.asarray(box, dtype=np.float64).reshape(-1, 2)
                en = float(pts[:, 0].max() - pts[:, 0].min())
                boy = float(pts[:, 1].max() - pts[:, 1].min())
                if en * boy >= DEJENERE_KUTU_ORAN * alan:
                    continue
                kutu_n += 1
                metin = str(metinler[index]).strip() if index < len(metinler) else ""
                guven = guvenler[index] if index < len(guvenler) else None
                try:
                    guven = float(guven)
                except (TypeError, ValueError):
                    guven = None
                if not metin or guven is None:
                    continue
                x0 = max(0, min(w - 1, int(np.floor(pts[:, 0].min()))))
                y0 = max(0, min(h - 1, int(np.floor(pts[:, 1].min()))))
                x1 = max(1, min(w, int(np.ceil(pts[:, 0].max()))))
                y1 = max(1, min(h, int(np.ceil(pts[:, 1].max()))))
                if x0 < x1 and y0 < y1:
                    satirlar.append({"text": metin, "confidence": guven,
                                     "bbox": [x0, y0, x1, y1]})
        return {"kutu_n": kutu_n, "satirlar": satirlar,
                "width": int(w), "height": int(h)}
    except Exception:
        return None

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

SEG_KAPSAMA_DUSUR = 0.80   # SINIF-A (2026-08-18, Çağatay onayı): segmentin
                           # token'larının bu oranı ÖNCEKİ segmentlerde zaten
                           # varsa segment sayfalanmaz — okuma masterında
                           # tekrar gürültüdür (dr-doolithl: REX HARRISON 2×,
                           # beyaz-kugu-İ: cast 4×; "aslında sorun yok ama
                           # tekrar da istenmez" — Çağatay)
SEG_MIN_TOKEN = 3          # bundan az tokenlu segment düşürülemez (kanıt yetersiz)
SEG_ORNEKLEM = 6           # çok kareli segmentte en çok bu kadar kare örneklenir
SUBSTRAT_SAPMA_KATSAYI = 1.5  # SINIF-B: sobel'in dy-sapması fenerin bu katını
                           # geçerse scroll sayısı fazla olsa da YANLIŞ
                           # ölçüyordur (altin-adam: sobel seçildi, recall
                           # 0.30→0.01; ask-sarkisi 0.51→0.27)
SUBSTRAT_SAPMA_TABAN = 0.10   # göreli sapmada mutlak taban — fenerin sapması
                           # tam 0 çıkınca (kusursuz akış) çarpım sıfıra
                           # düşüp sobeli hep kaybettirmesin; gerçek akışların
                           # doğal dy titreşimi ~0.05-0.15 bandındadır
SUBSTRAT_SAPMA_TAVAN = 0.35   # sobel'in KENDİ tutarlılık tavanı — bunun
                           # üstündeki dy-sapması dağınıklığıyla "scroll"
                           # bulmak ölçüm değil uydurmadır (altin-adam:
                           # sobel 11 'scroll', jitter 0.77, dys -117..+19 —
                           # kesmeleri scroll sanıyordu, recall 0.30→0.01)

# ---- ablasyon bayrakları (varsayılan: hepsi AÇIK) ------------------------- #
OZELLIKLER = {"plato": True, "token_kimlik": True, "sobel": True, "izgara": True,
              "fold_dedup": True}


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


def _segment_kanvas_haritali(ims, ofsetler, kaynak_haritasi):
    """Pixel-identical `_segment_kanvas` plus one provenance row per master row.

    Mapping is produced while the exact same winning source row is selected;
    there is no later image similarity guess.  Consecutive rows are RLE'd.
    """
    h, w = ims[0].shape[:2]
    taban = min(ofsetler)
    ofs = [o - taban for o in ofsetler]
    toplam = int(round(max(ofs))) + h
    kanvas = np.zeros((toplam, w, 3), dtype=np.uint8)
    ofs_arr = np.array(ofs)
    rows = []
    for y in range(toplam):
        aday = np.where((ofs_arr <= y) & (y < ofs_arr + h))[0]
        if len(aday) == 0:
            rows.append(None)
            continue
        best = int(aday[np.argmin(np.abs((y - ofs_arr[aday]) - h / 2))])
        source_y = int(y - ofs_arr[best])
        kanvas[y] = ims[best][source_y]
        rows.append((kaynak_haritasi.get(id(ims[best])), source_y))
    rle = []
    for master_y, row in enumerate(rows):
        if row is None:
            continue
        source, source_y = row
        if (rle and rle[-1]["source_path"] == source
                and rle[-1]["master_y1"] == master_y
                and rle[-1]["source_y1"] == source_y):
            rle[-1]["master_y1"] += 1
            rle[-1]["source_y1"] += 1
        else:
            rle.append({"master_y0": master_y, "master_y1": master_y + 1,
                        "source_path": source, "source_y0": source_y,
                        "source_y1": source_y + 1, "width": w, "height": h})
    return kanvas, rle


def _cokme_kurtarma_parcalari(secili_segmentler, kaynak_haritasi,
                              chunk_boyutu: int = 12):
    """Çöken tek masterı zaman sırasını koruyan küçük masterlara böl.

    Bu yol yalnız normal kompozisyon kural.cokmus hükmüne girecekse çağrılır.
    Her alt parça aynı piksel seçicisiyle üretilir; dolayısıyla yeni bir
    kompozitör ya da sonradan tahmin edilmiş bir layout haritası yoktur.
    """
    parcalar, layout_map = [], []
    master_y = 0
    for segment_images, segment_offsets in secili_segmentler:
        for bas in range(0, len(segment_images), chunk_boyutu):
            images = segment_images[bas:bas + chunk_boyutu]
            offsets = segment_offsets[bas:bas + chunk_boyutu]
            if not images:
                continue
            parca, rows = _segment_kanvas_haritali(images, offsets, kaynak_haritasi)
            parcalar.append(parca)
            for row in rows:
                kayit = dict(row)
                kayit["master_y0"] += master_y
                kayit["master_y1"] += master_y
                layout_map.append(kayit)
            master_y += int(parca.shape[0])
    return parcalar, layout_map


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


def scroll_duzlugu(ciftler: list[dict]) -> float | None:
    """Scroll sınıflı dy'lerin medyana göre göreli medyan-sapması.
    Düşük = tutarlı akış (gerçek jenerik kayması dy'leri birbirine yakın);
    yüksek = dağınık ölçüm (kesmelerin yanlış-scroll'ı, zemin kilitlenmesi).
    <3 scroll → None (kanıt yetersiz)."""
    dys = [abs(c["dy"]) for c in ciftler if c["sinif"] == "scroll"]
    if len(dys) < 3:
        return None
    med = float(np.median(dys))
    if med < 1e-6:
        return None
    return float(np.median([abs(d - med) for d in dys])) / med


def substrat_karari(fener_ciftler: list[dict], sob_ciftler: list[dict]) -> str:
    """SINIF-B yarışma kriteri (altin-adam/ask-sarkisi dersi, 2026-08-18):
    'çok scroll bulan kazanır' tek başına YANLIŞ — sobel bazen DAHA FAZLA ama
    dağınık/uydurma scroll buluyor. Yeni kural:
      * sobel daha çok scroll bulmadıysa fener (dokunma);
      * fener hiç scroll bulamadıysa sobel (orijinal kurtarma, parti sınıfı);
      * ikisi de bulduysa: sobel'in dy-sapması fenerin SAPMA_KATSAYI katını
        geçiyorsa ölçüm dağınıktır → fener; geçmiyorsa sobel (jetgiller'de
        sobel 12 tutarlı scroll buldu, fener 3).
    """
    fs = sum(1 for c in fener_ciftler if c["sinif"] == "scroll")
    ss = sum(1 for c in sob_ciftler if c["sinif"] == "scroll")
    if ss <= fs:
        return "fener"
    if fs == 0:
        return "sob"
    fj, sj = scroll_duzlugu(fener_ciftler), scroll_duzlugu(sob_ciftler)
    if sj is not None and sj > SUBSTRAT_SAPMA_TAVAN:
        return "fener"  # dağınık sobel: ölçüm değil uydurma (altin-adam)
    if fj is None or sj is None:
        return "sob"  # tutarlılık kanıtı yoksa scroll sayısına kalır
    return "sob" if sj <= max(fj * SUBSTRAT_SAPMA_KATSAYI, SUBSTRAT_SAPMA_TABAN) else "fener"


def segment_dusur(segmentler, token_fonk, *, esik: float = SEG_KAPSAMA_DUSUR,
                  orneklem: int = SEG_ORNEKLEM):
    """SINIF-A post-pass: içerik-kapsaması segment fold-dedup.

    Segmentler SIRAYLA dolaşulur; her segmentin temsili token kümesi
    (≤ orneklem kare) hesaplanır. Token'larının `esik` oranı önceki
    KORUNAN segmentlerin birikiminde zaten varsa segment DÜŞÜRÜLÜR — okuma
    masterında tekrar gürültüdür. Az-tokenlu segmentler (logo/çizim) kanıt
    yetersizliğinden DÜŞÜRÜLEMEZ; her şey düşerse ilk segment korunur.

    Dönen: (kalan_segmentler, dusurulen_kayitlari) — kayıtlar manifeste
    'segment_dusuren' olarak yazılır (kanıt kültürü: elesen görünür kalır).
    """
    kalan, dusurulen = [], []
    birikim: set = set()
    for si, so in segmentler:
        adim = max(1, len(si) // orneklem)
        ornek = si[::adim][:orneklem]
        toks: set = set()
        for im in ornek:
            toks |= set(token_fonk(im) or ())
        if (len(toks) >= SEG_MIN_TOKEN and birikim
                and len(toks & birikim) / len(toks) >= esik):
            dusurulen.append({"kare": len(si), "token": len(toks),
                              "kapsama": round(len(toks & birikim) / len(toks), 3)})
            continue
        kalan.append((si, so))
        birikim |= toks
    if not kalan and segmentler:
        kalan = [segmentler[0]]
    return kalan, dusurulen


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
            print(f"[lebron] OCR HATA: {type(exc).__name__}: {exc} -> Sobel yedek yolu",
                  flush=True)
            return np.where(sobel_metin_maskesi(gray) > 0, gray, 0)
        _, maske = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

    maske = cv2.dilate(maske, np.ones((5, 5), np.uint8), iterations=2)
    return cv2.bitwise_and(gray, gray, mask=maske)


def _varsayilan_el_feneri(sobel_acik: bool):
    """Varsayılan el-feneri: kulenin tek Paddle örneği."""

    def isik(img, _idx):
        return el_feneri_govde(img, get_ocr_engine().predict, sobel_acik)

    return isik


def _varsayilan_token_saglayici():
    """Kule içi det+rec token kümesi — ibrahimovic'in saglik yan-kapısı YOK.
    Sağlayıcı (görüntü, indeks) alır; motor ölürse/patlarsa boş küme döner
    (çağıran geometrik fallback'e düşer; 'yazı yok' ile 'okuyamadık'
    karışmaz — ayni_icerik yine fark tabanına gider)."""
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

    kaynaklar = None
    # Kobe manifestosu: hangi kare kaç kareyi temsil ediyor. Tek-kare
    # kapısı bunu kullanır (bkz. _gecerli_segment). Manifesto yoksa boş
    # kalır ve kapı eski davranışını aynen sürdürür.
    temsil_haritasi: dict[str, int] = {}
    _kardes_genisletme = False
    _ardisik_aralik = False
    if ims is None:
        if not kare_dizini or not os.path.isdir(kare_dizini):
            return None, {"slug": slug, "durum": "kare_yok", "kare": 0,
                          "sebep": "Klasor bulunamadi"}
        from yukleyici import temsil_sayilari as _temsil
        from yukleyici import genisletildi_mi as _genis
        from yukleyici import ardisik_aralik_mi as _ardisik
        temsil_haritasi = _temsil(kare_dizini)
        _kardes_genisletme = _genis(kare_dizini)
        _ardisik_aralik = _ardisik(kare_dizini)
        from yukleyici import kare_oku as _kare_oku, kareler as _kareler
        ims, kaynaklar = [], []
        for yol in _kareler(kare_dizini):
            im = _kare_oku(yol)
            if im is not None:
                ims.append(im)
                kaynaklar.append(str(yol.resolve()))
    else:
        kaynaklar = [f"synthetic://frame-{i:06d}" for i in range(len(ims))]
    if len(ims) < 2:
        return None, {"slug": slug, "durum": "kare_yok", "kare": len(ims)}

    h, w = ims[0].shape[:2]
    pairs = [(im, source) for im, source in zip(ims, kaynaklar)
             if im.shape[:2] == (h, w)]
    ims = [pair[0] for pair in pairs]
    kaynaklar = [pair[1] for pair in pairs]
    kaynak_haritasi = {id(im): source for im, source in pairs}

    # Girişte ardışık ham zaman serisini kayan-kapanış motoruna vermek farklı
    # statik kartları aynı zeminde birleştirip kaybettiriyor (Parmak Damgası
    # b2: 300 kare -> 3 segment). Girişe özel yol yalnız Paddle'ın pikselde
    # doğruladığı yazılı TAM kareleri seçer; kaynak havuza dokunmaz.
    if _ardisik_aralik:
        from giris_planlayici import master_uret as _giris_master_uret
        analizler = [paddle_satir_kaniti(im) for im in ims]
        return _giris_master_uret(slug, ims, kaynaklar, analizler, H_MAKS)

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
        # SINIF-B: yarışma dy-tutarlılığıyla kırılır (altin-adam/ask-sarkisi
        # dersi — "çok scroll" tek başına yanlış seçiyordu)
        if substrat_karari(ciftler, sob_ciftler) == "sob":
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

    # BIÇAK, ARDIŞIK GİRİŞ ARALIĞINDA SUSAR (Çağatay 2026-08-20).
    # Bıçak "jenerik, kaymanın başladığı yerde başlar" varsayar ve öncesini
    # çöp footage sayıp keser. Film jeneriğinde doğru; DİZİ açılışında
    # felaket: oyuncu kartları DURUR (dy≈0), bıçak onları geçip ekip
    # bölümündeki kaymadan başlatır — KADRONUN TAMAMI kesilir.
    # Kobe giriş manifestosu ``mod=ardisik_aralik`` dediğinde sınırı zaten
    # Kobe bulmuştur; LeBron'un ikinci kez hareketten sınır araması hem
    # gereksiz hem statik kartlar için yıkıcıdır. Eski kardeş-genişletme
    # manifestoları da geriye uyum için aynı güvenli yolu kullanır.
    # Ölçüldü (Çiçek Taksi b2 girişi, ardışık kareler):
    #     bıçak açık   → 119 kare / 13 segment /  3.921 px /  0 isim
    #     bıçak kapalı → 250 kare / 53 segment / 15.596 px / 16 isim
    bicak_pasif = _ardisik_aralik or _kardes_genisletme
    if bicak_pasif:
        baslangic, bitis = 0, len(ciftler) - 1
    bicak_bilgisi = {
        "aktif": not bicak_pasif,
        "neden": ("kobe_ardisik_aralik" if _ardisik_aralik else
                  "eski_kardes_genisletme" if _kardes_genisletme else
                  "varsayilan"),
        "baslangic_cifti": int(baslangic),
        "bitis_cifti": int(bitis),
    }
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

    # === SINIF-A: segment fold-dedup (2026-08-18) ===
    # İçerik-kapsaması: bir segmentin token'ları öncekilerde zaten varsa
    # saygı duyulan tekrar DEĞİLDİR, okuma gürültüsüdür — düşürülür, kanıtı
    # manifest'e yazılır. (dr-doolithl: aynı kadro iki segment; beyaz-kugu'da
    # ibrahimovic'in cast'i 4× basmasının magic'teki karşılığı bu kapıdır.)
    segment_dusuren = []
    if oz.get("fold_dedup", True) and len(segmentler) > 1:
        idx_harita = {id(im): i for i, im in enumerate(ims)}
        kalan, segment_dusuren = segment_dusur(
            segmentler,
            lambda im: _tokenlar(idx_harita[id(im)]) if id(im) in idx_harita else set())
        segmentler = kalan

    def _gecerli_segment(si, so):
        if not si:
            return False
        if len(si) > 1:
            return True
        # TEK KARE — AMA DEDUP TEMSİLCİSİ Mİ? (Çağatay'ın bulgusu 2026-08-20)
        # Bu kapının asıl sorduğu şey "yazı ekranda SÜRDÜ mü?"; kare sayısı
        # bunun VEKİLİYDİ. Kobe dedup'ı aynı metni okuyan kareleri tek
        # temsilciye indirince vekil bozuldu: 5 kare süren kart da, 1 karede
        # parlayan da "1 kare" görünür oldu. Ölçülen kayıp — EROL GÜNAYDIN
        # beş karede de AYNI okundu, tek temsilciye indi, burada elendi.
        # Kartın kusuru doğru okunmasıydı.
        # Çare kareyi çoğaltmak DEĞİL (havuzu şişirir, derleyiciyi çökertir:
        # 128 kare → 1 segment / 449 px, ölçüldü); Kobe'nin zaten bildiği
        # gerçek sayıyı sormak. Eşik yeni değil — kapının kendi >1 eşiği.
        if temsil_haritasi:
            yol = kaynak_haritasi.get(id(si[0]))
            if yol and temsil_haritasi.get(os.path.basename(yol), 1) > 1:
                return True
        # gerçekten tek kare: hangi ölçüm yolundaysak o yolun metin kanıtı
        g = cv2.cvtColor(si[0], cv2.COLOR_BGR2GRAY)
        if olcum_yolu == "sobel":
            return metin_profili(g, sobel_metin_maskesi(g).astype(np.float32))
        m = np.asarray(isik(si[0], 0), dtype=np.uint8)
        v = (m > VARLIK_ESIK).astype(np.float32)
        return metin_profili(m, v)

    secili_segmentler = [(si, so) for si, so in segmentler if _gecerli_segment(si, so)]
    if not secili_segmentler:
        secili_segmentler = [(si, so) for si, so in segmentler if si]
    if not secili_segmentler:
        return None, {"slug": slug, "durum": "kare_yok", "kare": len(ims),
                      "sebep": "Gecerli segment kalmadi"}
    parcalar = []
    layout_map = []
    master_y = 0
    for segment_images, segment_offsets in secili_segmentler:
        parca, rows = _segment_kanvas_haritali(
            segment_images, segment_offsets, kaynak_haritasi)
        parcalar.append(parca)
        for row in rows:
            row = dict(row)
            row["master_y0"] += master_y
            row["master_y1"] += master_y
            layout_map.append(row)
        master_y += int(parca.shape[0])
    kanvas = np.vstack(parcalar) if len(parcalar) > 1 else parcalar[0]

    # Normal yolun görüntüsü ve künyesi burada bitmiş olur.  Sadece mevcut
    # üretim kapısının "çok kare + tek, çok kısa segment" dediği durumda
    # zaman-bounded alt masterlara geri düşeriz.  Böylece sağlıklı filmlerde
    # normal kompozitör byte/pixel olarak aynen kalır.
    normal_boy = int(kanvas.shape[0])
    normal_segment = len(parcalar)
    cokme_kurtarma = {
        "triggered": False,
        "original_frames": len(ims),
        "original_segments": normal_segment,
        "original_height": normal_boy,
    }
    if cokmus({"segment": normal_segment,
               "size": [int(kanvas.shape[1]), normal_boy]}, len(ims), h):
        chunk_boyutu = 12
        kurtarilan_parcalar, kurtarilan_layout = _cokme_kurtarma_parcalari(
            secili_segmentler, kaynak_haritasi, chunk_boyutu)
        if not kurtarilan_parcalar:
            # Bu noktaya pratikte gelinemez; yine de çöküşü METIN_YOK'a
            # dönüştürmek yerine görünür bir derleme arızası bırakırız.
            return None, {"slug": slug, "durum": "cokme_kurtarma_ariza",
                          "kare": len(ims), "sebep": "Kurtarma parcasi yok",
                          "collapse_recovery": {**cokme_kurtarma,
                                                "triggered": True,
                                                "strategy": "temporal_chunk_stack"}}
        parcalar, layout_map = kurtarilan_parcalar, kurtarilan_layout
        kanvas = np.vstack(parcalar) if len(parcalar) > 1 else parcalar[0]
        cokme_kurtarma = {
            **cokme_kurtarma,
            "triggered": True,
            "chunk_size": chunk_boyutu,
            "chunk_count": len(parcalar),
            "recovered_height": int(kanvas.shape[0]),
            "strategy": "temporal_chunk_stack",
        }

    if kanvas.shape[0] > H_MAKS:
        return None, {"slug": slug, "durum": "boy_asimi", "boy": int(kanvas.shape[0]),
                      "collapse_recovery": cokme_kurtarma}

    sinif_sayimi = {s: sum(1 for c in ciftler if c.get("sinif") == s)
                    for s in ("scroll", "duraksama", "kesme", "duraksama_bos",
                              "duraksama_belirsiz")}
    scroll_dyler = [abs(c["dy"]) for c in ciftler if c.get("sinif") == "scroll"]
    scroll_dy_medyan = float(np.median(scroll_dyler)) if scroll_dyler else 0.0

    manifest = {
        "slug": slug,
        "durum": "OK",
        "mode": "lebron",
        "kare": len(ims),
        "size": [int(kanvas.shape[1]), int(kanvas.shape[0])],
        "segment": len(parcalar),
        "segment_kareler": [len(si) for si, _ in segmentler if si],
        "layout_map_version": "mitas.master-layout/v1",
        "layout_map": layout_map,
        "segment_dusuren": segment_dusuren,
        "dissolve_kesme": dissolve_kesme,
        "sinif_sayimi": sinif_sayimi,
        "scroll_dy_medyan": round(scroll_dy_medyan, 2),
        "ciftler": ciftler,
        "olcum_yolu": olcum_yolu,
        "maske_kapsama": round(kapsama, 3),
        "sobel_kurtarma": sobel_kurtarma,
        "girdi_modu": "ardisik_aralik" if _ardisik_aralik else "standart",
        "bicak": bicak_bilgisi,
        "collapse_recovery": cokme_kurtarma,
        "ozellikler": oz,
        "sure_s": round(time.time() - t0, 2)
    }
    return kanvas, manifest
