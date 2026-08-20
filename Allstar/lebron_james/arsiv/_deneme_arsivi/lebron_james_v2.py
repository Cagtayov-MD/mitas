#!/usr/bin/env python3
"""LEBRON JAMES v2 ENGINE (Akıllı Trim + AI Flashlight + 2D Phase Correlate + Static Card Split)

LeBron v1 avantajları KORUNUR:
- AI Flashlight (PaddleOCR detection-only maske)
- Akıllı Trim (baş/son kırpma)
- Hız (recognition yapmaz)
- CLI/standalone

İbrahimovic'tan TAŞINAN static motoru:
- koşu_platolari(): IoU istikrar platoları → her kart için temsilci
- PLATO_IOU eşiği: dissolve geçiş karesini atar
- Token/OCR doğrulama: AI Flashlight mask üzerinde _tokenlar() + metin_gibi()
- Micro-scroll detection: net_krip + tek yönlü → slit-scan'e yönlendir
"""
from __future__ import annotations

import cv2
import numpy as np
import os
import sys
import time
from pathlib import Path
from paddleocr import PaddleOCR

# ============================================================================
# SABİTLER (LeBron v1 + İbrahimovic static motoru)
# ============================================================================
MASK_ESIK = 110
VARLIK_ESIK = 60
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
H_MAKS = 45000

# İbrahimovic'tan: static kart split için
PLATO_IOU = 0.70          # IoU plato eşiği - altındakiler dissolve/geçiş sayılır
PLATO_IOU_TOL = 0.02      # plato genişliği toleransı (eşitlik bandı)

# OCR Motoru global olarak tembel yüklenir
_ocr_engine = None

def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        print("PaddleOCR AI Modeli yükleniyor (LeBron James v2)...", flush=True)
        _ocr_engine = PaddleOCR(lang='en')
    return _ocr_engine

def ai_flashlight_mask(img: np.ndarray) -> np.ndarray:
    """AI ile yazıları bulur, arka planı siyaha boğup orijinal gri pikselleri döndürür."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    maske = np.zeros((h, w), dtype=np.uint8)
    
    try:
        ocr = get_ocr_engine()
        results = ocr.predict(img)
        
        for res in results:
            if res is None:
                continue
            if isinstance(res, dict) and 'dt_polys' in res:
                for box in res['dt_polys']:
                    box_np = np.array(box, dtype=np.int32)
                    cv2.fillPoly(maske, [box_np], 255)
            elif isinstance(res, list):
                for item in res:
                    if isinstance(item, list) and len(item) == 2 and isinstance(item[1], tuple):
                        box_np = np.array(item[0], dtype=np.int32)
                        cv2.fillPoly(maske, [box_np], 255)
                    elif isinstance(item, np.ndarray):
                        box_np = item.astype(np.int32)
                        cv2.fillPoly(maske, [box_np], 255)
    except Exception:
        _, maske = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        
    maske = cv2.dilate(maske, np.ones((5, 5), np.uint8), iterations=2)
    masked_gray = cv2.bitwise_and(gray, gray, mask=maske)
    return masked_gray

def calculate_sharpness(gray):
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def _iou(m1: np.ndarray, m2: np.ndarray) -> float:
    kes = float(np.logical_and(m1 > 0, m2 > 0).sum())
    bir = float(np.logical_or(m1 > 0, m2 > 0).sum())
    return kes / bir if bir else 1.0

def _icerik_ncc(g1: np.ndarray, g2: np.ndarray, v1: np.ndarray, v2: np.ndarray) -> float:
    union = np.logical_or(v1 > 0, v2 > 0)
    if int(union.sum()) < MIN_MASKE_PX: return 0.0
    a, b = g1[union].astype(np.float32), g2[union].astype(np.float32)
    sa, sb = float(a.std()), float(b.std())
    if sa < 1e-3 or sb < 1e-3: return 0.0
    return float(((a - a.mean()) * (b - b.mean())).mean() / (sa * sb))

def _dy_dogrula(g1, g2, m1, dy):
    h = g1.shape[0]
    k = int(round(abs(dy)))
    if k <= 0 or k >= h: return None
    if dy < 0:
        sec = m1[k:, :] > 0
        a, b = g1[k:, :], g2[:h - k, :]
    else:
        sec = m1[:h - k, :] > 0
        a, b = g1[:h - k, :], g2[k:, :]
    if int(sec.sum()) < MIN_MASKE_PX: return None
    av, bv = a[sec].astype(np.float32), b[sec].astype(np.float32)
    sa, sb = float(av.std()), float(bv.std())
    if sa < 1e-3 or sb < 1e-3: return None
    return float(((av - av.mean()) * (bv - bv.mean())).mean() / (sa * sb))

def _fark_px(ga, gb):
    sa, sb_ = float(ga.std()), float(gb.std())
    if sb_ > 1e-3:
        gb = (gb - gb.mean()) * (sa / sb_) + ga.mean()
    return int((np.abs(ga - gb) > FARK_ESIK).sum())

def _tokenlar(idx: int, ai_griler: list, varliklar: list) -> list:
    """AI Flashlight mask üzerinde basit token sayısı (okunurluk kanıtı).
    İbrahimovic'te saglik.py'den geliyor; burada basitleştirilmiş versiyon."""
    mask = ai_griler[idx]
    varlik = varliklar[idx]
    if int(varlik.sum()) < MIN_MASKE_PX:
        return []
    # Metin piksel yoğunluğu ve bağlantılı bileşen sayısı
    num_labels, labels = cv2.connectedComponents(varlik.astype(np.uint8))
    # Her bileşen için piksel sayısı
    tokens = []
    for lbl in range(1, num_labels):
        comp_mask = (labels == lbl).astype(np.uint8)
        px = int(comp_mask.sum())
        if px > 20:  # min token boyutu
            tokens.append(lbl)
    return tokens

def metin_gibi(ai_gray: np.ndarray, varlik: np.ndarray) -> bool:
    """İçerik metin mi? (IoU yoğunluğu + token varlığı)"""
    if int(varlik.sum()) < MIN_MASKE_PX:
        return False
    # Metin konsantrasyonu: maske alanı / kutu alanı
    ys, xs = np.where(varlik > 0)
    if len(ys) == 0:
        return False
    h, w = varlik.shape
    bbox_area = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
    if bbox_area == 0:
        return False
    konsantrasyon = float(varlik.sum()) / bbox_area
    return konsantrasyon >= METIN_KONSANTRASYON

# ============================================================================
# STATIC KART SPLIT: İbrahimovic'in koşu_platolari + kosuyu_isle adaptasyonu
# ============================================================================
def kosu_platolari(kosu: list[int], varliklar: list[np.ndarray], ai_griler: list[np.ndarray]) -> list[int]:
    """Duraksama koşusundaki kart temsilcilerini döndür (IoU plato tepe tespiti).
    
    İbrahimovic mantığı: ardışık IoU'nun yerel tepeleri = kartın en stabil kareleri.
    Dissolve koruması: PLATO_IOU altındaki tepeler elenir (geçiş karesi).
    """
    if len(kosu) < 3:
        return [kosu[-1]] if kosu else []
    
    # Ardışık IoU hesapla
    iou_vals = [_iou(varliklar[a], varliklar[b]) for a, b in zip(kosu, kosu[1:])]
    
    # Her karenin istikrarı = bitişik çiftlerin en iyisi
    kare_s = [max(iou_vals[max(0, j - 1)], iou_vals[min(j, len(iou_vals) - 1)])
              for j in range(len(kosu))]
    
    # Yerel tepe tespiti (plato duyarlı: >= sol, > sağ)
    tepeler = []
    j = 0
    while j < len(kosu):
        k0 = j
        while j + 1 < len(kosu) and abs(kare_s[j + 1] - kare_s[k0]) <= PLATO_IOU_TOL:
            j += 1
        sol = kare_s[k0 - 1] if k0 > 0 else -1.0
        sag = kare_s[j + 1] if j < len(kosu) - 1 else -1.0
        if kare_s[k0] >= sol and kare_s[k0] > sag:
            orta = (k0 + j) // 2
            tepeler.append((kosu[orta], kare_s[k0]))
        j += 1
    
    # PLATO_IOU filtresi: dissolve/geçiş karelerini at
    saglam = [t for t, sk in tepeler if sk >= PLATO_IOU]
    return saglam if saglam else [t for t, _ in tepeler]


def cift_olc(olcum, bosluk_px, griler, varliklar, h, w):
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
                ayni = ncc >= 0.60 or (_iou(varliklar[i], varliklar[i + 1]) >= AYNI_IOU_GUCLU and ncc >= AYNI_NCC_TABAN)
                if ayni:
                    kayit["sinif"] = "duraksama"
        elif resp >= RESP_ESIK and abs(dy) < MIN_ADIM:
            ncc = _icerik_ncc(griler[i], griler[i + 1], varliklar[i], varliklar[i + 1])
            ayni = ncc >= 0.60 or (_iou(varliklar[i], varliklar[i + 1]) >= AYNI_IOU_GUCLU and ncc >= AYNI_NCC_TABAN)
            kayit["sinif"] = "duraksama" if ayni else "duraksama_belirsiz"
        else:
            # maske örtüşmesine bak
            iou = _iou(varliklar[i], varliklar[i + 1])
            if iou >= ORTUSME_DURAKSAMA:
                kayit["sinif"] = "duraksama"
            else:
                kayit["sinif"] = "kesme"
        out.append(kayit)
    return out

def _segment_kanvas(seg_im, seg_ofs):
    if len(seg_im) == 1:
        return seg_im[0]
    # Calculate canvas height to fit all frames with their offsets
    min_y = min(int(round(ofs)) for ofs in seg_ofs)
    max_y = max(int(round(ofs)) + im.shape[0] for im, ofs in zip(seg_im, seg_ofs))
    h = max_y - min_y
    w = max(im.shape[1] for im in seg_im)
    kanvas = np.zeros((h, w, 3), dtype=np.uint8)
    for im, ofs in zip(seg_im, seg_ofs):
        y = int(round(ofs)) - min_y
        kanvas[y:y+im.shape[0], :im.shape[1]] = im
    return kanvas

# ============================================================================
# ANA FONKSİYON
# ============================================================================
def compose_lebron_v2(slug: str, *, kare_dizini: str = None, ims: list = None) -> tuple:
    """LeBron v2: Static kart split + AI Flashlight + Smart Trim"""
    t0 = time.time()
    
    if ims is None:
        yollar = sorted(Path(kare_dizini).glob("*.png"))
        ims = [cv2.imread(str(p)) for p in yollar if cv2.imread(str(p)) is not None]
    
    if len(ims) < 2:
        return None, {"slug": slug, "durum": "kare_yok", "kare": len(ims)}
        
    h, w = ims[0].shape[:2]
    ims = [im for im in ims if im.shape[:2] == (h, w)]
    griler = [cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) for im in ims]
    
    # AI Flashlight maskeler (LeBron avantajı)
    ai_griler = []
    for im in ims:
        ai_griler.append(ai_flashlight_mask(im).astype(np.float32))
        
    varliklar = [(g > VARLIK_ESIK).astype(np.float32) for g in ai_griler]
    bosluk = [int((g > 0).sum()) for g in ai_griler]
    
    ciftler = cift_olc(ai_griler, bosluk, ai_griler, varliklar, h, w)
    
    # === AKILLI BIÇAK (TRIM) MANTIGI (LeBron avantajı) ===
    baslangic = 0
    tolerans = 50
    durma_toleransi = 125
    
    for idx_trim, c in enumerate(ciftler):
        if abs(c.get("dy", 0)) > 1.0:
            ileri = [abs(ciftler[j].get("dy", 0)) > 1.0 for j in range(idx_trim, min(idx_trim+10, len(ciftler)))]
            if sum(ileri) >= 5:
                baslangic = max(0, idx_trim - tolerans)
                break
                
    bitis = len(ciftler) - 1
    for idx_trim in range(baslangic, len(ciftler)):
        if abs(ciftler[idx_trim].get("dy", 0)) < 0.5:
            ileri = [abs(ciftler[j].get("dy", 0)) < 0.5 for j in range(idx_trim, min(idx_trim + durma_toleransi, len(ciftler)))]
            if len(ileri) == durma_toleransi and all(ileri):
                bitis = min(len(ciftler) - 1, idx_trim + tolerans)
                break

    ciftler = ciftler[baslangic:bitis]
    ims = ims[baslangic:bitis+1]
    griler = griler[baslangic:bitis+1]
    ai_griler = ai_griler[baslangic:bitis+1]
    varliklar = varliklar[baslangic:bitis+1]
    
    segmentler = []
    seg_im, seg_ofs, akum = [ims[0]], [0.0], 0.0
    seg_idx = [0]
    ref_idx = 0
    segment_kareler = []
    
    _taban_ornek = [(_fark_px(griler[i], griler[i + 1])) for i, c in enumerate(ciftler) if c["sinif"] in ("duraksama", "duraksama_bos", "duraksama_belirsiz")][:40]
    fark_taban = float(np.median(_taban_ornek)) if _taban_ornek else 500.0
    
    def ayni_icerik(a, b):
        return _fark_px(griler[a], griler[b]) <= max(FARK_TABAN_KATSAYI * fark_taban, FARK_MUTLAK_MIN)

    i = 0
    n_cift = len(ciftler)
    while i < n_cift:
        c = ciftler[i]
        if c["sinif"] == "kesme":
            if ayni_icerik(i + 1, ref_idx) or not metin_gibi(ai_griler[i+1], varliklar[i+1]):
                i += 1; continue
            segmentler.append((seg_im, seg_ofs))
            segment_kareler.append(seg_idx)
            seg_im, seg_ofs, akum = [ims[i + 1]], [0.0], 0.0
            seg_idx = [i + 1]
            ref_idx = i + 1
            i += 1
            continue
            
        if c["sinif"] == "scroll":
            # SÜREKLİLİK BEKÇİSİ (İbrahimovic)
            if ref_idx != i and not ayni_icerik(i, ref_idx):
                segmentler.append((seg_im, seg_ofs))
                segment_kareler.append(seg_idx)
                seg_im, seg_ofs, akum = [ims[i]], [0.0], 0.0
                seg_idx = [i]
                ref_idx = i
            akum += -c["dy"]
            seg_im.append(ims[i + 1])
            seg_ofs.append(akum)
            seg_idx.append(i + 1)
            ref_idx = i + 1
            i += 1
            continue
            
        # DURAKSAMA KOŞUSU: Static kart split (İbrahimovic mantığı)
        j = i
        kosu = []
        kosu_dylar = []
        while j < n_cift and ciftler[j]["sinif"] not in ("scroll", "kesme"):
            kosu.append(j + 1)
            kosu_dylar.append(ciftler[j]["dy"] if ciftler[j]["sinif"] == "duraksama" else 0.0)
            j += 1
            
        # Micro-scroll detection (İbrahimovic + LeBron)
        anlamli = [d for d in kosu_dylar if abs(d) > 0.3]
        ayni_yon = 0.0
        if anlamli:
            neg = sum(1 for d in anlamli if d < 0)
            pos = sum(1 for d in anlamli if d > 0)
            ayni_yon = max(neg, pos) / len(anlamli)
            
        net_krip = abs(sum(kosu_dylar))
        dinamik_esik = min(NET_KRIP_ESIK_YONLU, max(2.0, len(kosu) * 1.5))
        if kosu and net_krip >= dinamik_esik and ayni_yon >= 0.8:
            # Yavaş scroll → slit-scan'e ekle
            for k, dk in zip(kosu, kosu_dylar):
                akum += -dk
                seg_im.append(ims[k])
                seg_ofs.append(akum)
                seg_idx.append(k)
                ref_idx = k
            i = j
            continue
            
        # STATIC KART SPLIT: IoU plato tepeleri + Token doğrulama
        if kosu:
            adaylar = set(kosu_platolari(kosu, varliklar, ai_griler))
            # Kısa koşularda ek ızgara adayları (İbrahimovic)
            if len(kosu) >= 6:
                adaylar.update(kosu[::3])
            
            for tem in sorted(adaylar):
                # Aynı içerik kontrolü
                if ayni_icerik(tem, ref_idx):
                    # Daha iyi okunurluk varsa yükselt
                    if len(seg_im) == 1:
                        ta, tr = _tokenlar(tem, ai_griler, varliklar), _tokenlar(ref_idx, ai_griler, varliklar)
                        daha_iyi = (len(ta) > len(tr)) if (ta or tr) else (
                            float(varliklar[tem].sum()) > float(varliklar[ref_idx].sum()))
                        if daha_iyi:
                            seg_im[0] = ims[tem]
                            ref_idx = tem
                    continue
                # Metin kontrolü (AI Flashlight mask üzerinde)
                if not metin_gibi(ai_griler[tem], varliklar[tem]):
                    continue
                # Yeni kart sayfası aç
                segmentler.append((seg_im, seg_ofs))
                segment_kareler.append(seg_idx)
                seg_im, seg_ofs, akum = [ims[tem]], [0.0], 0.0
                seg_idx = [tem]
                ref_idx = tem
        i = j
        
    segmentler.append((seg_im, seg_ofs))
    segment_kareler.append(seg_idx)
    
    parcalar = [_segment_kanvas(si, so) for si, so in segmentler if si]
    kanvas = np.vstack(parcalar) if len(parcalar) > 1 else parcalar[0]
    
    if kanvas.shape[0] > H_MAKS:
        return None, {"slug": slug, "durum": "boy_asimi", "boy": int(kanvas.shape[0])}
        
    manifest = {
        "slug": slug,
        "durum": "OK",
        "mode": "lebron_james_v2",
        "kare": len(ims),
        "size": [int(kanvas.shape[1]), int(kanvas.shape[0])],
        "segment": len(parcalar),
        "segment_kareler": [len(si) for si, _ in segmentler if si],
        "sinif_sayimi": {s: sum(1 for c in ciftler if c.get("sinif") == s) for s in ("scroll", "duraksama", "kesme", "duraksama_bos", "duraksama_belirsiz")},
        "ciftler": ciftler,
        "olcum_yolu": "ai_flashlight",
        "sure_s": round(time.time() - t0, 2)
    }
    
    return kanvas, manifest


# ============================================================================
# CLI
# ============================================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LeBron James v2 Engine (Static Card Split + AI Flashlight)")
    parser.add_argument("--slug", type=str, default="test", help="Klip / film adı slug")
    parser.add_argument("--kare-dizini", type=str, required=True, help="Jenerik PNG karelerinin bulunduğu klasör")
    parser.add_argument("--out", type=str, default=None, help="Çıktı master PNG dosya yolu (isteğe bağlı)")
    args = parser.parse_args()

    print(f"[LeBron v2 CLI] İşleniyor: {args.kare_dizini}...")
    kanvas, manifest = compose_lebron_v2(args.slug, kare_dizini=args.kare_dizini)
    if kanvas is not None:
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(out_path), kanvas)
            print(f"[LeBron v2 CLI] Master PNG yazıldı: {out_path}")
        print(f"[LeBron v2 CLI] Başarılı! Boyut: {manifest.get('size')}, Segment: {manifest.get('segment')}, Süre: {manifest.get('sure_s')}s")
        print(f"  Sinif sayimi: {manifest.get('sinif_sayimi')}")
        print(f"  Segment kareleri: {manifest.get('segment_kareler')}")
    else:
        print(f"[LeBron v2 CLI] Başarısız: {manifest.get('durum')}, Sebep: {manifest.get('sebep', 'Bilinmiyor')}")
