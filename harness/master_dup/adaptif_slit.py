#!/usr/bin/env python3
"""Footage-üstü / değişken-hızlı kayan jenerik için ADAPTİF SLIT master üretimi.

NEDEN VAR: Üretim kompozitörü (db_compose_master.compose_reading_runaware)
scroll/statik kararını ve slit ofsetlerini TÜM-KARE faz-korelasyonuyla verir;
künye hareketli footage üstünde kayarken zemin hareketi ölçümü domine eder →
"statik" yanılgısı / bozuk ofsetler → tekrarlı-karmakarışık master (mod_denetim
F3b SONRASI bile 13 filmde mod_hatasi=True). Bu modül o sınıf için kareden
bağımsız, METİN-MASKELİ ve KARE-BAŞI ölçülen ofsetlerle gerçek slit kurar.

Doğrulanan öncüller (2026-07-26, scratchpad prototipleri):
  * benimle-dans-et (sabit-hız, footage-üstü): metin-maskeli global-Y + satır-
    seçimli slit → okunur panorama (Çağatay kabul etti).
  * gercek-yalanlar (DEĞİŞKEN-hız, duraksamalı): sabit-hız varsayımı ağır tekrar
    üretti (TIA CARRERE ×6); kare-başı ölçülen dy + duraksama-atlama tekrarı
    tamamen giderdi (Çağatay: "son gelenler şahane").

ALGORİTMA
  1. Her ardışık kare çifti için metin-maskesi (gray>MASK_ESIK) üzerinde Hanning
     pencereli cv2.phaseCorrelate → (dy, resp). Maske metni öne çıkarır; zemin
     footage'ı karanlık/orta tonlarda kaldığından ölçümü domine edemez.
  2. Çift sınıflandırma:
       SCROLL  resp>=RESP_ESIK ve MIN_ADIM<=|dy|<=MAKS_ADIM_ORAN*H
       DURAKSAMA resp>=RESP_ESIK ve |dy|<MIN_ADIM  (veya iki maske de boş)
       KESME/BELİRSİZ  aksi → maske örtüşmesine bak: maskeler yüksek örtüşüyorsa
         DURAKSAMA (içerik aynı, ölçüm zayıf), örtüşmüyorsa KESME (içerik
         korelasyonsuz DEĞİŞTİ — kart geçişi / sahne kesmesi).
  3. KESME'lerde segment kapatılır; segment içinde işaretli kümülatif ofsetler,
     kanvasın her satırı için "o satırı KARE MERKEZİNE en yakın gören kare"
     seçilir (satır-seçimli gerçek slit — karışım yok, çift-pozlama yok).
     Duraksama çiftleri ofset katkısı 0 → aynı içerik İKİNCİ kez eklenmez
     (tekrar üretmez); kesmede yeni segment TAM kare ile başlar (içerik kaybı
     yok). Segmentler dikey istiflenir.
  3b. DISSOLVE BEKÇİSİ (Çağatay'ın fikri, 2026-07-26): duraksama sırasında yazı
     YAVAŞ geçişle (dissolve) değişirse ardışık çiftler hep "benzer" görünür —
     hareket yok, sert kesme yok → yeni yazı kanvasa hiç girmezdi (kayıp).
     Çözüm: harekete değil İÇERİK KİMLİĞİNE bak — duraksamadaki her kare, son
     kanvasa-girmiş karenin maskesiyle (referans) karşılaştırılır; IoU
     AYRISMA_IOU altına düşerse içerik değişmiştir → "bir alt satıra in, yeni
     yazıyı yaz": segment kapat, yeni kareyle yeni sayfa aç.
  4. Arka plan OLDUĞU GİBİ bırakılır (maskeleme/karartma YOK) — Çağatay kararı
     (2026-07-26): "yazı gelsin, arka plan crop/hayalet kalmış sorun değil";
     orijinal piksel = orijinal tipografi.

Üretim korpusuna DOKUNMAZ — çıktı ayrı köke yazılır (--cikti-kok). Kabul kapısı
ayrı: footage_qc.py (sadakat text_recall + dup_metrik dup_oran, üretim OCR
motoruyla). Bu ayrım kasıtlı: kompozisyon ucuz/cv2-saf, QC pahalı/OCR'lı.

Kullanım:
  venv=/opt/mitas/venvs/ocr/bin/python
  $venv adaptif_slit.py --slug gercek-yalanlar --cikti-kok /opt/mitas/outputs/footage_pano
  $venv adaptif_slit.py --liste slugs.txt --cikti-kok ...   # toplu
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# üretim det+rec motorları (F1c altyapısı) — TEMBEL yüklenir ve YALNIZ
# duraksama-temsilcisi kimlik kararlarında kullanılır (scroll yolu OCR'sız).
# Motor yüklenemezse geometrik fark fallback'i devrededir (script bağımsız kalır).
_DC = None
_DC_DENENDI = False


def _dc_al():
    global _DC, _DC_DENENDI
    if _DC_DENENDI:
        return _DC
    _DC_DENENDI = True
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        import saglik
        _DC = saglik._uret_mod()._dc()
    except Exception:
        _DC = None
    return _DC

EX_KARE_ROOT = Path("/home/cagatay/Ex_Frame")
EX_SUFFIX = "-exit_frames"

MASK_ESIK = 110          # gray>110: parlak künye harfleri (benimle/gercek doğrulandı)
VARLIK_ESIK = 60         # gray>60: SOLUK kart yazısı dahil "ekranda içerik var mı"
                         # maskesi (karadeniz açılış kartları 110'da görünmezdi —
                         # ölçüm 110'da kalır, varlık/kimlik kararları 60'ta verilir)
RESP_ESIK = 0.05         # phaseCorrelate response tabanı (üretim cut_resp ile aynı ruh)
MIN_ADIM = 2.0           # |dy| bunun altı → duraksama (içerik zaten kanvasta)
MAKS_ADIM_ORAN = 0.85    # |dy| > 0.85*H → korelasyon sıçraması/kesme adayı
MIN_MASKE_PX = 400       # maske bundan seyrekse ölçüm güvenilmez (metin yok sayılır)
ORTUSME_DURAKSAMA = 0.55 # belirsiz çiftte maske-örtüşme (IoU) bunun üstü → duraksama
AYNI_IOU_GUCLU = 0.60    # "aynı içerik" için güçlü konum-örtüşmesi eşiği; tek başına
                         # yetmez, nötr-üstü NCC ister (aşağıya bkz). Eski AYRISMA_IOU
                         # =0.35 kuralı kucuk-dev-adam'da FARKLI metinli ama AYNI
                         # yerleşimli kartları (IoU 0.39-0.42, NCC eksi!) "aynı" sayıp
                         # kart2 sayfasını yuttu — IoU konum ölçer, içerik ölçmez.
AYNI_NCC_TABAN = 0.20    # güçlü IoU'ya eşlik etmesi gereken asgari içerik-NCC
KIMLIK_IOU = 0.45        # parlaklığa-uyarlanan harf-maskesi IoU'su bunun üstündeyse
                         # aynı kart (fade halleri dahil); farklı metin ~0.15-0.25'te kalır
AYNILIK_NCC = 0.60       # içerik-NCC bunun ÜSTÜndeyse aynı içeriğin parlaklık
                         # değişimidir (fade) → yeni sayfa AÇMA (beklenmedik-miras
                         # "THE END ×4" kusuru gözle yakalandı; IoU fade'e karşı kör)
PLATO_IOU = 0.75         # ardışık varlık-IoU bunun ÜSTÜnde seyrederse "istikrarlı
                         # koşu" (kart tutuluyor); dissolve/fade bu eşiği tutturamaz
KUCUK_DY_ESIK = 8.0      # |dy| bunun altındaki "scroll" çiftlerinde içerik-aynılığı
                         # şartı aranır (farklı kartların sahte-scroll yapışmasını önler)
NET_KRIP_ESIK_YONLU = 10.0  # duraksama koşusunun NET sürüklenmesi bunu aşar VE
                         # işaret tutarlılığı >=0.8 ise "yavaş-sürünme" → mikro-scroll
                         # panoraması (parti); karışık-işaretli tutma gürültüsü
                         # (kucuk-dev 0.73) plato yolunda kalır
DOGRULAMA_NCC = 0.50     # scroll dy'si kaydırılmış-NCC ile bunun altında kalırsa
                         # ölçüm desteksiz → scroll sayma (aydaki-adam dikiş-kayması)
MASKE_KAPSAMA_ESIK = 0.25  # parlaklık maskesinin medyan kare-kapsaması bunu aşarsa
                         # maske yozlaşmıştır (parlak zemin, korelasyon statik zemine
                         # kilitlenir — parti) → ölçüm Sobel kenar-maskesi yoluna geçer
FARK_ESIK = 30           # normalize-farkta "değişmiş piksel" eşiği (gri birim)
FARK_TABAN_KATSAYI = 3.0 # fark_px > katsayı×film-gren-tabanı → İÇERİK DEĞİŞTİ
FARK_MUTLAK_MIN = 800    # gren-tabanı sıfıra yakınken alt koruma (px)
METIN_KONSANTRASYON = 0.35  # sobel satır-profilinin en yoğun %12.5 satırı toplamın
                         # bu oranını taşımalı ki kare "metin içeriyor" sayılsın
TOKEN_CONF_ESIK = 0.40   # kimlik tokenına girecek rec kutusunun asgari güveni
TOKEN_MIN_GUVEN = 3      # iki tarafta da en az bu kadar token yoksa token hükmü
                         # güvenilmez (loş-kart OCR kararsızlığı) → geometrik fark
TOKEN_KAPSAMA = 0.60     # |kesişim|/min(|a|,|b|) bunun üstünde → AYNI kart
                         # (soluk↔parlak fade'de OCR bazı tokenları düşürse de
                         # kapsama-oranı dayanıklı; farklı kartlarda ~0)
H_MAKS = 45000           # saglik.py ile aynı canavar-boy tavanı

# ---- İYİLEŞTİRME BAYRAKLARI (varsayılan KAPALI = eski davranış bit-birebir) ---- #
# Her biri bağımsız açılıp kapatılabilir; benchmark_iyilestirmeler.py ile test edilir.
IYIL_OTSU = os.environ.get("MITAS_IYIL_OTSU", "0") == "1"
IYIL_DY_SMOOTH = os.environ.get("MITAS_IYIL_DY_SMOOTH", "0") == "1"
IYIL_FUZZY = os.environ.get("MITAS_IYIL_FUZZY", "0") == "1"
IYIL_SUBPX = os.environ.get("MITAS_IYIL_SUBPX", "0") == "1"


def _median_filtre(vals: list[float], pencere: int = 3) -> list[float]:
    """Simetrik pencereli median filtre (scipy bağımlılığı olmadan).
    Scroll dy dizisindeki film greni / codec titremesinden kaynaklanan
    aykırı tepeleri bastırır; monoton kaymayı korur."""
    n = len(vals)
    yarim = pencere // 2
    sonuc = []
    for i in range(n):
        bas = max(0, i - yarim)
        bit = min(n, i + yarim + 1)
        sonuc.append(float(np.median(vals[bas:bit])))
    return sonuc


def _fuzzy_token_kesisim(ta: set[str], tb: set[str]) -> int:
    """Levenshtein ≤ 1 toleranslı token eşleştirmesi.
    OCR gürültüsü (DIRECTOR → DIRECT0R, SMITH → SM1TH) tek-karakter
    hataları üretir; birebir küme kesişimi bunları kaçırır."""
    eslesme = 0
    tb_list = list(tb)
    for a in ta:
        for b in tb_list:
            if a == b:
                eslesme += 1
                break
            if len(a) >= 4 and abs(len(a) - len(b)) <= 1:
                # basit Levenshtein ≤ 1 kontrolü (substitution + 1-char len diff)
                fark = sum(1 for ca, cb in zip(a, b) if ca != cb)
                fark += abs(len(a) - len(b))  # uzunluk farkı da 1 edit
                if fark <= 1:
                    eslesme += 1
                    break
    return eslesme


def kareleri_yukle(slug: str, kare_dizini: str | None = None) -> list[np.ndarray]:
    d = Path(kare_dizini) if kare_dizini else EX_KARE_ROOT / f"{slug}{EX_SUFFIX}"
    yollar = sorted(d.glob("exit_*.png")) or sorted(d.glob("*.png"))
    return [im for p in yollar if (im := cv2.imread(str(p))) is not None]


def metin_maskesi(im: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    if IYIL_OTSU:
        # Otsu: filmin kendi histogram dağılımından optimal eşik.
        # Sabit 110 soluk filmlerde kaçırıyor, parlak filmlerde şişiriyor;
        # Otsu her karenin ışık koşuluna otomatik adapte olur.
        esik, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return (gray > esik).astype(np.float32)
    return (gray > MASK_ESIK).astype(np.float32)


def varlik_maskesi(im: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    return (gray > VARLIK_ESIK).astype(np.float32)


def _iou(m1: np.ndarray, m2: np.ndarray) -> float:
    kes = float(np.logical_and(m1 > 0, m2 > 0).sum())
    bir = float(np.logical_or(m1 > 0, m2 > 0).sum())
    return kes / bir if bir else 1.0  # ikisi de boş → "aynı" say (duraksama)


def _icerik_ncc(g1: np.ndarray, g2: np.ndarray, v1: np.ndarray, v2: np.ndarray) -> float:
    """Parlaklıktan bağımsız içerik benzerliği: varlık-BİRLEŞKESİ pikselleri
    üzerinde Pearson korelasyonu. Aynı kart soluk↔parlak → yüksek; farklı
    metin/kart → düşük. (Fade, IoU'yu kör eder — maske boyu değişir; NCC
    normalize ettiği için fade'e dayanıklı.)"""
    union = np.logical_or(v1 > 0, v2 > 0)
    if int(union.sum()) < MIN_MASKE_PX:
        return 0.0  # kıyaslanacak içerik yok → "farklı" say
    a, b = g1[union].astype(np.float32), g2[union].astype(np.float32)
    sa, sb = float(a.std()), float(b.std())
    if sa < 1e-3 or sb < 1e-3:
        return 0.0
    return float(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb))


def _dy_dogrula(g1: np.ndarray, g2: np.ndarray, m1: np.ndarray, dy: float) -> float | None:
    """Ölçülen dy'yi bağımsız kanıtla sına: g1'in METİN pikselleri dy kadar
    kaydırılınca g2'de aynı değerleri buluyor mu (Pearson, yalnız metin
    konumlarında)? Dokulu zeminde faz-korelasyonun 'kilitlendiği' YANLIŞ dy'ler
    düşük çıkar (aydaki-adam dikiş-kayması satır yutmuştu — gözle yakalandı).
    TÜM-gri üzerinde yapılmaz: footage filmlerinde zemin korelasyonu domine
    edip GEÇERLİ scroll'u reddediyordu (benimle-dans-et 2298→4939 bozulması).
    None = metin kanıtı yetersiz, hüküm verme (ölçüme dokunma)."""
    h = g1.shape[0]
    k = int(round(abs(dy)))
    if k <= 0 or k >= h:
        return None
    if dy < 0:  # içerik yukarı kaydı: g1'in k.satırı → g2'nin 0.satırı
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


def sobel_metin_maskesi(gray: np.ndarray) -> np.ndarray:
    """Kenar-enerjisi maskesi (mod_denetim._metin_maske ile aynı): parlak-zeminli
    filmlerde parlaklık eşiği yozlaşır (gökyüzü/duvar maskeyi doldurur, korelasyon
    statik zemine kilitlenir — parti vakası, çift dökümüyle kanıtlandı). Düz parlak
    alanların gradyanı yoktur; yazı kenarları güçlü gradyandır — maske metinde kalır.
    mod_denetim bu maskeyle parti'yi doğru ölçmüştü (kayan=0.74, dy_med=48)."""
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    mag = cv2.magnitude(gx, gy)
    m = (mag > (mag.mean() + mag.std())).astype(np.uint8)
    return cv2.dilate(m, np.ones((7, 7), np.uint8))


def cift_olc(olcum: list[np.ndarray], bosluk_px: list[int],
             griler: list[np.ndarray], varliklar: list[np.ndarray],
             h: int, w: int) -> list[dict]:
    """Ardışık çiftleri ölç ve sınıfla → [{dy, resp, sinif}, ...] (N-1 adet).

    `olcum[i]`: korelasyona giren float görüntü (standart yol: ikili parlaklık
    maskesi; sobel yolu: maskeli gri değerler). `bosluk_px[i]`: o karenin
    metin-piksel sayısı (boşluk kararı)."""
    han = cv2.createHanningWindow((w, h), cv2.CV_32F)
    out: list[dict] = []
    for i in range(len(olcum) - 1):
        m1, m2 = olcum[i], olcum[i + 1]
        px1, px2 = bosluk_px[i], bosluk_px[i + 1]
        if px1 < MIN_MASKE_PX or px2 < MIN_MASKE_PX:
            # metin yok(a yakın) → slit'e katacak içerik yok; duraksama say
            out.append({"dy": 0.0, "resp": 0.0, "sinif": "duraksama_bos"})
            continue
        (_, dy), resp = cv2.phaseCorrelate(m1 * han, m2 * han)
        kayit = {"dy": round(float(dy), 2), "resp": round(float(resp), 4)}
        if resp >= RESP_ESIK and MIN_ADIM <= abs(dy) <= MAKS_ADIM_ORAN * h:
            dogru = _dy_dogrula(griler[i], griler[i + 1], m1, dy)
            kayit["dogrulama"] = None if dogru is None else round(dogru, 3)
            # NOT: dogrulama SINIFI DEĞİŞTİRMEZ — yalnız teşhis (tüm-gri ve
            # metin-piksel varyantları sağlıklı filmleri bozmuştu, geri alındı).
            kayit["sinif"] = "scroll"
            # KÜÇÜK-DY SAHTE-SCROLL BEKÇİSİ (kucuk-dev-adam Frankenstein-sayfası,
            # gözle + kontak-tabloyla kanıtlandı): iki FARKLI kart arasındaki
            # geçiş 2-6px'lik "scroll" ölçülebiliyor (resp bile yüksek) — farklı
            # kartları slit'e yapıştırıp ara satırları YOK EDER. Aynı kartın
            # gerçek sürüklenmesi (drift) içerik-aynılığını korur; farklı kart
            # koruyamaz. Yalnız |dy|<=KUCUK_DY_ESIK çiftlerine uygulanır — büyük
            # dy'li gerçek akış scrollarına (benimle 34px, karadeniz 128px) dokunmaz.
            if abs(dy) <= KUCUK_DY_ESIK:
                ncc = _icerik_ncc(griler[i], griler[i + 1], varliklar[i],
                                  varliklar[i + 1])
                ayni = ncc >= AYNILIK_NCC or (
                    _iou(varliklar[i], varliklar[i + 1]) >= AYNI_IOU_GUCLU
                    and ncc >= AYNI_NCC_TABAN)
                if not ayni:
                    kayit["sinif"] = "duraksama_belirsiz"
        elif resp >= RESP_ESIK and abs(dy) < MIN_ADIM:
            kayit["sinif"] = "duraksama"
        else:
            # ölçüm güvenilmez: içerik AYNI mı (duraksama) DEĞİŞTİ mi (kesme)?
            kayit["sinif"] = ("duraksama_belirsiz"
                              if _iou(m1, m2) >= ORTUSME_DURAKSAMA else "kesme")
        out.append(kayit)
    return out


def _segment_kanvas(ims: list[np.ndarray], ofsetler: list[float]) -> np.ndarray:
    """Satır-seçimli slit: her kanvas satırını kare-merkezine en yakın kaynaktan al.

    Ofsetler işaretli-kümülatif; taban 0'a çekilir (negatif yön = aşağı kayan
    jenerik de aynı matematikle çalışır).

    IYIL_SUBPX=1 iken sub-pixel bilinear interpolasyon: kümülatif ofset float
    olarak korunur, piksel-arası satırlar komşu iki satırın ağırlıklı ortalamasıyla
    hesaplanır → tırtıklanma/basamak artifaktları kaybolur."""
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
        frac_y = y - ofs_arr[best]
        if IYIL_SUBPX:
            y_int = int(frac_y)
            y_kesir = frac_y - y_int
            if y_kesir < 0.01 or y_int + 1 >= h:
                kanvas[y] = ims[best][y_int]
            else:
                # bilinear: komşu iki satırın ağırlıklı ortalaması
                kanvas[y] = (ims[best][y_int].astype(np.float32) * (1.0 - y_kesir)
                             + ims[best][y_int + 1].astype(np.float32) * y_kesir
                             ).astype(np.uint8)
        else:
            kanvas[y] = ims[best][int(frac_y)]
    return kanvas


def compose_adaptif(slug: str, kare_dizini: str | None = None,
                    ims: list[np.ndarray] | None = None) -> tuple[np.ndarray | None, dict]:
    """`ims` verilirse kareler diskten OKUNMAZ. Üretim hattı (master_png_monitor)
    kendi seçtiği kare listesini önceden yükleyip geçirir; böylece bu modül
    Ex_Frame klasör düzenine bağlı kalmaz. `ims=None` → eski davranış aynen."""
    t0 = time.time()
    if ims is None:
        ims = kareleri_yukle(slug, kare_dizini)
    if len(ims) < 2:
        return None, {"slug": slug, "durum": "kare_yok", "kare": len(ims)}
    h, w = ims[0].shape[:2]
    ims = [im for im in ims if im.shape[:2] == (h, w)]
    griler = [cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) for im in ims]
    maskeler = [(g > MASK_ESIK).astype(np.float32) for g in griler]    # ölçüm (dy)
    varliklar = [(g > VARLIK_ESIK).astype(np.float32) for g in griler] # kimlik/varlık
    # ölçüm yolu KARARI (film-bazlı, parti-sınıfı fix'i): parlaklık maskesi kareyi
    # dolduruyorsa (median kapsama > eşik) korelasyon statik parlak zemine kilitlenir
    # → Sobel kenar-maskeli GRİ ile ölç (mod_denetim'in parti'de kanıtlı yolu).
    # Kapsaması düşük filmler (benimle/gercek/karadeniz... 14 doğrulanmış film)
    # MEVCUT yoldan hiç ayrılmaz.
    kapsama = float(np.median([m.mean() for m in maskeler[:: max(1, len(maskeler) // 10)]]))
    if kapsama > MASKE_KAPSAMA_ESIK:
        olcum_yolu = "sobel"
        sobeller = [sobel_metin_maskesi(g) for g in griler]
        olcum = [np.where(sb > 0, g, 0).astype(np.float32)
                 for sb, g in zip(sobeller, griler)]
        bosluk = [int(sb.sum()) for sb in sobeller]
    else:
        olcum_yolu = "parlaklik"
        olcum = maskeler
        bosluk = [int(m.sum()) for m in maskeler]
    ciftler = cift_olc(olcum, bosluk, griler, varliklar, h, w)

    # ---- İYİLEŞTİRME: dy Smoothing (median filtre) ---- #
    # Scroll olarak sınıflandırılmış ardışık çiftlerin dy değerlerine
    # 3'lü pencereli median filtre uygular. Film greni / codec titremesinden
    # kaynaklanan ±3-5 px sapmayı bastırır, monoton kaymayı korur.
    # Kesme/duraksama sınırlarına DOKUNMAZ.
    if IYIL_DY_SMOOTH:
        _i = 0
        while _i < len(ciftler):
            if ciftler[_i]["sinif"] == "scroll":
                _j = _i
                while _j < len(ciftler) and ciftler[_j]["sinif"] == "scroll":
                    _j += 1
                if _j - _i >= 3:
                    _dyler = [ciftler[_k]["dy"] for _k in range(_i, _j)]
                    _yumusak = _median_filtre(_dyler, 3)
                    for _k, _dy in zip(range(_i, _j), _yumusak):
                        ciftler[_k]["dy_ham"] = ciftler[_k]["dy"]
                        ciftler[_k]["dy"] = round(_dy, 2)
                _i = _j
            else:
                _i += 1

    # ---- PLATO MİMARİSİ (v4) --------------------------------------------- #
    # Gözle yakalanan iki kayıp sınıfı bunu zorunlu kıldı:
    #   * kucuk-dev-adam: dissolve ANI karesi (iki kartın hayalet karışımı)
    #     sayfa temsilcisi olup ardılı kartı NCC'yle bastırdı → satırlar kayboldu.
    #   * karadeniz benzeri fade zincirlerinde art arda yarım-kart sayfaları.
    # Kural (Çağatay: "alta in, yaz, YENİ HAMLE BEKLE"): sayfa ancak İSTİKRARLI
    # içerikten basılır. Duraksama koşuları önce PLATOLARA bölünür (ardışık
    # varlık-IoU >= PLATO_IOU olan kareler tek plato; geçiş/blend kareleri plato
    # sınırında kalır), her platonun temsilcisi EN DOLU karedir; temsilci, kanvasa
    # en son giren içerikle AYNI ise (IoU veya parlaklık-bağımsız NCC) sayfa
    # basılmaz (fade-tekrarı değil), FARKLIYSA "bir alt satıra in, yeni sayfa".
    segmentler: list[tuple[list[np.ndarray], list[float]]] = []
    segment_kareler: list[list[int]] = []  # teşhis: her segmentin kare indeksleri
    seg_im, seg_ofs, akum = [ims[0]], [0.0], 0.0
    seg_idx: list[int] = [0]
    ref_idx = 0  # kanvasa en son giren karenin indeksi
    dissolve_kesme = 0

    def _fark_px(a: int, b: int) -> int:
        """Parlaklık-NORMALİZE piksel-farkı (v15 tek benzerlik ölçüsü).

        NCC/IoU/kimlik üçlüsü statik-zemin kartlarında (jetgiller/totoro/
        hayat-agaci/havaci — zemin kartlar arasında AYNI, yalnız yazı değişiyor)
        zemine domine olup kartları "aynı" sayıyordu; 427-koşu gözle doğrulanmış
        gerileme sınıfı. Fark ise zemini kendiliğinden düşürür: b, a'nın
        parlaklık istatistiğine normalize edilir (fade nötrlenir), kalan mutlak
        fark yalnız DEĞİŞEN içeriktir (eski yazı + yeni yazı pikselleri)."""
        ga = griler[a].astype(np.float32)
        gb = griler[b].astype(np.float32)
        sa, sb_ = float(ga.std()), float(gb.std())
        if sb_ > 1e-3:
            gb = (gb - gb.mean()) * (sa / sb_) + ga.mean()
        return int((np.abs(ga - gb) > FARK_ESIK).sum())

    # filmin gren-tabanı: hareketsiz (duraksama) çiftlerin fark'ı = saf
    # gürültü/gren. Karar eşiği filme göre kendini kalibre eder. NOT: kar/yağmur
    # gibi sürekli-hareketli zeminlerde bu taban kart-değişimiyle AYNI mertebeye
    # çıkar (hayat-agaci: komşu-çift 7-11k px ≈ kart farkı — ölçümle kanıtlandı);
    # bu yüzden fark yalnız FALLBACK'tir, birincil kimlik TOKEN karşılaştırmasıdır.
    _taban_ornek = [(_fark_px(i, i + 1))
                    for i, c in enumerate(ciftler) if c["sinif"] == "duraksama"][:40]
    fark_taban = float(np.median(_taban_ornek)) if _taban_ornek else 500.0

    token_onbellek: dict[int, set[str]] = {}

    def _tokenlar(a: int) -> set[str]:
        """Karenin det+rec token kümesi (üretim F1c motorları; kimlik kararı için).
        Motor yoksa/patlarsa boş küme döner (geometrik fallback devreye girer)."""
        if a in token_onbellek:
            return token_onbellek[a]
        toks: set[str] = set()
        dc = _dc_al()
        if dc is not None:
            try:
                boxes = dc._f1b_det_boxes(griler[a])
                if boxes:
                    rec = dc._f1c_rec_boxes(griler[a], dc._f1b_boxes_sorted(boxes))
                    for text, conf in rec:
                        if conf < TOKEN_CONF_ESIK:
                            continue
                        for t in text.split():
                            if len(t) >= 3:
                                toks.add(t)
            except Exception:
                toks = set()
        token_onbellek[a] = toks
        return toks

    def ayni_icerik(a: int, b: int) -> bool:
        """Kart kimliği (v16): BİRİNCİL kanıt = metin tokenları. Üç geometrik
        vekil de birer gerçek sınıfta battı (IoU: aynı-yerleşim farklı-metin;
        NCC/kimlik: statik-zemin dominasyonu; normalize-fark: kar yağışı) —
        hepsi gözle + ölçümle belgelendi. Metnin kimliğini metin okur:
        iki kare de token veriyorsa kapsama-oranı karar verir; token yoksa
        (logo/çizim/ultra-soluk) geometrik fark fallback'i.

        IYIL_FUZZY=1 iken Levenshtein ≤ 1 toleranslı eşleştirme: OCR'ın
        tek-karakter hataları (0↔O, 1↔I, M↔W) yanlış 'farklı kart' kararına
        yol açmaz."""
        ta, tb = _tokenlar(a), _tokenlar(b)
        if min(len(ta), len(tb)) >= TOKEN_MIN_GUVEN:
            if IYIL_FUZZY:
                eslesme = _fuzzy_token_kesisim(ta, tb)
                return eslesme / min(len(ta), len(tb)) >= TOKEN_KAPSAMA
            return len(ta & tb) / min(len(ta), len(tb)) >= TOKEN_KAPSAMA
        # az-token: OCR loş karede aynı kartı her okuyuşta farklı çıkarabilir
        # (havaci 46-sayfa patlaması) → token hükmü güvenilmez, geometrik fark
        return _fark_px(a, b) <= max(FARK_TABAN_KATSAYI * fark_taban, FARK_MUTLAK_MIN)

    def metin_gibi(a: int) -> bool:
        """Sayfa-açılış kapısı: temsilcide GERÇEK metin var mı? Birincil kanıt
        det+rec (>=2 token); motor yoksa satır-profili sezgiseli (metin kenar
        enerjisini satırlarda yoğunlaştırır, gök/doku greni yaymaz)."""
        if _dc_al() is not None:
            return len(_tokenlar(a)) >= 2
        sob = sobel_metin_maskesi(griler[a]).astype(np.float32)
        toplam = float(sob.sum())
        if toplam < MIN_MASKE_PX:
            return False
        prof = np.sort(sob.sum(axis=1))[::-1]
        ust = float(prof[: max(1, len(prof) // 8)].sum())
        return ust / toplam >= METIN_KONSANTRASYON

    def koşu_platolari(kareler: list[int]) -> list[int]:
        """Duraksama koşusundaki kart temsilcilerini döndür (sayfa adayları).

        Dört deneme sonrası yerleşen ilke (kucuk-dev-adam dissolve-zinciri +
        karadeniz grenli soluk kartlar, ikisi de gözle yakalandı): temsilci
        GEÇİŞTEN EN UZAK kare olmalı, ama sabit istikrar-EŞİĞİ kullanılamaz —
        grenli soluk kartın ardışık-IoU'su dissolve'la aynı banda düşüyor.
        Eşik yerine ŞEKİL: dolu-koşu içinde istikrar eğrisinin (ardışık varlık-
        IoU) YEREL TEPELERİ tutulan kartların ortasıdır; dissolve daima çukurda
        kalır. Boş kareler koşuyu böler (siyah-aralıklı kartlar doğal ayrılır).
        Kısa koşularda (<3 kare) tepe tanımsız → son kare (oturmuş içerik)."""
        temsilciler: list[int] = []
        kosu: list[int] = []

        def kosuyu_isle(kosu: list[int]) -> None:
            if not kosu:
                return
            if len(kosu) < 3:
                temsilciler.append(kosu[-1])
                return
            s = [_iou(varliklar[a], varliklar[b]) for a, b in zip(kosu, kosu[1:])]
            # kare k'nin istikrarı = bitişik çiftlerinin en iyisi (uçlarda tek çift)
            kare_s = [max(s[max(0, j - 1)], s[min(j, len(s) - 1)])
                      for j in range(len(kosu))]
            # Yerel tepe, DÜZ PLATO duyarlı: eşit-istikrar bölgesi tek tepe sayılır
            # ve temsilcisi ORTA karedir. ('>=sol, >sag' saf kuralı platonun SON
            # karesini seçiyordu — son kare geçişe komşudur; kucuk-dev-adam'da
            # kart2 platosu yerine 19. kare (parlama) seçildi, segment_kareler
            # dökümüyle kanıtlandı.)
            tepeler: list[tuple[int, float]] = []
            j = 0
            while j < len(kosu):
                k0 = j
                while j + 1 < len(kosu) and abs(kare_s[j + 1] - kare_s[k0]) <= 0.02:
                    j += 1
                sol = kare_s[k0 - 1] if k0 > 0 else -1.0
                sag = kare_s[j + 1] if j < len(kosu) - 1 else -1.0
                if kare_s[k0] >= sol and kare_s[k0] > sag:
                    orta = (k0 + j) // 2
                    tepeler.append((kosu[orta], kare_s[orta]))
                j += 1
            # GEÇİŞ-KARESİ FİLTRESİ (kucuk-dev-adam kare-20 vakası, IoU/NCC
            # dökümüyle kanıtlandı): istikrarı PLATO_IOU altındaki "tepe" aslında
            # iki kart arası karışım anıdır — sayfa TEMSİLCİSİ OLAMAZ. Ama koşuda
            # hiçbir kare eşiği tutturamıyorsa (grenli soluk kartlar — karadeniz,
            # v5'in bu yüzden kaybettiği sınıf) filtresiz tepelere geri düşülür:
            # filtre temsilci SEÇİMİNİ inceltir, içerik ATLAMAZ.
            saglam = [t for t, sk in tepeler if sk >= PLATO_IOU]
            temsilciler.extend(saglam if saglam else [t for t, _ in tepeler])

        for k in kareler:
            if float(varliklar[k].sum()) >= MIN_MASKE_PX:
                kosu.append(k)
                continue
            kosuyu_isle(kosu)
            kosu = []
        kosuyu_isle(kosu)
        return temsilciler

    i = 0
    n_cift = len(ciftler)
    while i < n_cift:
        c = ciftler[i]
        if c["sinif"] == "kesme":
            # KESME de kimlik+metin kapılarından geçer (affedilmeyenler "THE END
            # ×5": fade/pozlama sıçramaları kesme sayılıp her seferinde sorgusuz
            # sayfa açıyordu — tam-çözünürlük okumayla doğrulandı).
            if ayni_icerik(i + 1, ref_idx) or not metin_gibi(i + 1):
                # aynı içerik veya metinsiz sahne: kanvasa yeni sayfa YOK.
                # ref DEĞİŞMEZ (ref = kanvasa en son giren içerik) — sonraki
                # metinli/farklı kart normal yoldan sayfalanır.
                i += 1
                continue
            segmentler.append((seg_im, seg_ofs)); segment_kareler.append(seg_idx)
            seg_im, seg_ofs, akum = [ims[i + 1]], [0.0], 0.0
            seg_idx = [i + 1]
            ref_idx = i + 1
            i += 1
            continue
        if c["sinif"] == "scroll":
            # SÜREKLİLİK BEKÇİSİ (kucuk-dev-adam Frankenstein-sayfası, kontak-
            # tabloyla kanıtlandı): duraksama koşusu sırasında içerik sessizce
            # değişmiş ama sayfalanamamışsa (kart2→kart3, plato tepesi koşu
            # sonuna denk gelmedi), scroll'un eklediği kare son-entegre kareyle
            # DİKİLEMEZ — önce mevcut sayfayı kapat, çiftin İLK karesiyle yeni
            # segment aç, scroll o segmentte devam etsin. Kesintisiz scroll'da
            # ref_idx == i olduğundan bu dal hiç tetiklenmez (sıfır etki).
            if ref_idx != i and not ayni_icerik(i, ref_idx):
                segmentler.append((seg_im, seg_ofs)); segment_kareler.append(seg_idx)
                seg_im, seg_ofs, akum = [ims[i]], [0.0], 0.0
                seg_idx = [i]
                ref_idx = i
                dissolve_kesme += 1
            # üretimde künye yukarı kayar → içerik kanvasta AŞAĞI ilerler; işaret
            # ne olursa olsun kümülatif eksen tutarlı kalır (taban-çekme telafi eder)
            akum += -c["dy"]  # phaseCorrelate: yukarı kayan içerikte dy<0 → +yön
            seg_im.append(ims[i + 1])
            seg_ofs.append(akum)
            seg_idx.append(i + 1)
            ref_idx = i + 1
            i += 1
            continue
        # duraksama koşusu: [i+1 .. j] ardışık scroll/kesme-olmayan kareler
        j = i
        kosu: list[int] = []
        kosu_dylar: list[float] = []
        while j < n_cift and ciftler[j]["sinif"] not in ("scroll", "kesme"):
            kosu.append(j + 1)
            kosu_dylar.append(ciftler[j]["dy"] if ciftler[j]["sinif"] == "duraksama" else 0.0)
            j += 1
        # YAVAŞ-SÜRÜNME SINIFI (parti, gözle yakalandı: kare başına ~1.5px <
        # MIN_ADIM → hepsi "duraksama", liste akıp gitti, sadece kuyruk kaldı):
        # koşunun NET sürüklenmesi anlamlı VE TEK YÖNLÜ ise bu bir tutma değil
        # MİKRO-SCROLL'dur → koşu kareleri ölçülen küsuratlı dy'lerle panoramaya
        # eklenir. Gerçek tutmalar (kucuk-dev kart-kayması: karışık işaret, oran
        # 0.73) plato yoluna gider. Sabit 20px eşiği yetmedi: parti'de araya
        # giren scroll çiftleri koşuyu ~12'lik parçalara bölüp net'i 18'e düşürdü.
        anlamli = [d for d in kosu_dylar if abs(d) > 0.3]
        ayni_yon = (max(sum(1 for d in anlamli if d < 0),
                        sum(1 for d in anlamli if d > 0)) / len(anlamli)
                    if anlamli else 0.0)
        net_krip = abs(sum(kosu_dylar))
        if kosu and net_krip >= NET_KRIP_ESIK_YONLU and ayni_yon >= 0.8:
            for k, dk in zip(kosu, kosu_dylar):
                akum += -dk
                seg_im.append(ims[k])
                seg_ofs.append(akum)
                ref_idx = k
            i = j
            continue
        # sayfa ADAYLARI: geometrik istikrar tepeleri + (uzun koşularda) TOKEN
        # yoklama ızgarası. Parlak/dolu-varlık filmlerde (jetgiller göğü, karlı
        # hayat-agaci) istikrar eğrisi dümdüz kalıp koca koşudan 1-2 tepe
        # çıkarıyordu → kartlar yutuluyordu (427-koşu gözle doğrulandı). Izgara
        # adayları token-kimliğe sorulur; karışım kareleri token-KAPSAMA
        # sayesinde kendiliğinden elenir (karışım, referans kartın tokenlarını
        # İÇERİR → "aynı" → sayfa açmaz; saf yeni kart içermez → açar).
        adaylar = set(koşu_platolari(kosu))
        if len(kosu) >= 6:
            adaylar.update(kosu[::3])
        for tem in sorted(adaylar):
            if ayni_icerik(tem, ref_idx):
                # aynı içeriğin daha iyi hali tek-kareli kart sayfasını yükseltir:
                # token sayısı (okunurluk kanıtı) > varlık toplamı (parlak filmde kör)
                if len(seg_im) == 1:
                    ta, tr = _tokenlar(tem), _tokenlar(ref_idx)
                    daha_iyi = (len(ta) > len(tr)) if (ta or tr) else (
                        float(varliklar[tem].sum()) > float(varliklar[ref_idx].sum()))
                    if daha_iyi:
                        seg_im[0] = ims[tem]
                        ref_idx = tem
                continue
            if not metin_gibi(tem):
                continue  # metinsiz içerik (gök/doku) sayfa açamaz — affedilmeyenler çöpü
            segmentler.append((seg_im, seg_ofs)); segment_kareler.append(seg_idx)
            seg_im, seg_ofs, akum = [ims[tem]], [0.0], 0.0
            seg_idx = [tem]
            ref_idx = tem
            dissolve_kesme += 1
        i = j
    segmentler.append((seg_im, seg_ofs)); segment_kareler.append(seg_idx)

    # derleme filtresi: TEK-kareli ve metinsiz segmentler (açılış gökyüzü tabanı
    # gibi) master'a girmez — ama her şey elenirse en az bir parça tutulur.
    secilen = [(si, so) for (si, so), idxs in zip(segmentler, segment_kareler)
               if si and (len(si) > 1 or metin_gibi(idxs[0]))]
    if not secilen:
        secilen = [(si, so) for si, so in segmentler if si]
    parcalar = [_segment_kanvas(si, so) for si, so in secilen]
    kanvas = np.vstack(parcalar) if len(parcalar) > 1 else parcalar[0]
    if kanvas.shape[0] > H_MAKS:
        return None, {"slug": slug, "durum": "boy_asimi", "boy": int(kanvas.shape[0])}

    sinif_sayimi: dict[str, int] = {}
    for c in ciftler:
        sinif_sayimi[c["sinif"]] = sinif_sayimi.get(c["sinif"], 0) + 1
    manifest = {
        "slug": slug, "durum": "OK", "mode": "adaptif_slit",
        "kare": len(ims), "size": [int(kanvas.shape[1]), int(kanvas.shape[0])],
        "segment": len(parcalar), "dissolve_kesme": dissolve_kesme,
        "olcum_yolu": olcum_yolu, "maske_kapsama": round(kapsama, 3),
        "segment_kareler": segment_kareler,
        "sinif_sayimi": sinif_sayimi,
        "scroll_dy_medyan": round(float(np.median(
            [abs(c["dy"]) for c in ciftler if c["sinif"] == "scroll"] or [0.0])), 2),
        "ciftler": ciftler, "sure_s": round(time.time() - t0, 2),
    }
    return kanvas, manifest


def calistir(slug: str, cikti_kok: Path, kare_dizini: str | None = None) -> dict:
    kanvas, manifest = compose_adaptif(slug, kare_dizini)
    d = cikti_kok / slug
    d.mkdir(parents=True, exist_ok=True)
    if kanvas is not None:
        cv2.imwrite(str(d / "reading_master.png"), kanvas)
    (d / "adaptif_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--liste", help="satır başına bir slug içeren dosya")
    ap.add_argument("--cikti-kok", required=True)
    ap.add_argument("--kare-dizini", help="Ex_Frame yerine özel kare klasörü (--slug ile)")
    args = ap.parse_args(argv)
    kok = Path(args.cikti_kok)
    sluglar = ([args.slug] if args.slug else
               [s.strip() for s in Path(args.liste).read_text().splitlines() if s.strip()])
    for s in sluglar:
        m = calistir(s, kok, args.kare_dizini)
        boy = m.get("size", ["-", "-"])[1] if m.get("size") else "-"
        print(f"{s:40s} {m['durum']:10s} boy={boy} segment={m.get('segment','-')} "
              f"sinif={m.get('sinif_sayimi','-')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
