#!/usr/bin/env python3
"""LEBRON JAMES ENGINE (Akıllı Trim + AI Flashlight + 2D Phase Correlate)
Orijinal İbrahimovic'in yerine geçen yeni yapay zeka odaklı master PNG oluşturucu.
"""
import cv2
import numpy as np
import os
import sys
import time
from pathlib import Path
from paddleocr import PaddleOCR

# Sabitler
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

# OCR Motoru global olarak tembel yüklenir
_ocr_engine = None

def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        print("PaddleOCR AI Modeli yükleniyor (LeBron James)...", flush=True)
        # Sadece tespit modelini (detection) kullan
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
    except Exception as exc:
        print(f"[LeBron] OCR HATA: {type(exc).__name__}: {exc} -> threshold(180) fallback", flush=True)
        _, maske = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        
    maske = cv2.dilate(maske, np.ones((5, 5), np.uint8), iterations=2)
    
    # FLAŞÖR MANTIGI: Sadece maske içindeki orijinal gri tonları al, geri kalanı 0 (siyah) yap
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
                if not ayni:
                    kayit["sinif"] = "duraksama_belirsiz"
        elif resp >= RESP_ESIK and abs(dy) < MIN_ADIM:
            kayit["sinif"] = "duraksama"
        else:
            kayit["sinif"] = "duraksama_belirsiz" if _iou(m1, m2) >= ORTUSME_DURAKSAMA else "kesme"
        out.append(kayit)
    return out

def _segment_kanvas(ims, ofsetler):
    h, w = ims[0].shape[:2]
    taban = min(ofsetler)
    ofs = [o - taban for o in ofsetler]
    toplam = int(round(max(ofs))) + h
    kanvas = np.zeros((toplam, w, 3), dtype=np.uint8)
    ofs_arr = np.array(ofs)
    for y in range(toplam):
        aday = np.where((ofs_arr <= y) & (y < ofs_arr + h))[0]
        if len(aday) == 0: continue
        best = aday[np.argmin(np.abs((y - ofs_arr[aday]) - h / 2))]
        kanvas[y] = ims[best][int(y - ofs_arr[best])]
    return kanvas

def metin_gibi(gray, mask):
    toplam = float(mask.sum())
    if toplam < MIN_MASKE_PX: return False
    prof = np.sort(mask.sum(axis=1))[::-1]
    ust = float(prof[: max(1, len(prof) // 8)].sum())
    return ust / toplam >= METIN_KONSANTRASYON

def compose_lebron(
    slug: str,
    kare_dizini: str | None = None,
    ims: list[np.ndarray] | None = None
) -> tuple[np.ndarray | None, dict]:
    """
    Ana Pipeline Arayüzü: LeBron James motorunu calistirir.
    Returns: (kanvas, manifest)
    """
    t0 = time.time()
    if ims is None:
        if not kare_dizini or not os.path.isdir(kare_dizini):
            return None, {"slug": slug, "durum": "kare_yok", "kare": 0, "sebep": "Klasor bulunamadi"}
        yollar = sorted(Path(kare_dizini).glob("*.png"))
        ims = [cv2.imread(str(p)) for p in yollar if cv2.imread(str(p)) is not None]
    
    if len(ims) < 2:
        return None, {"slug": slug, "durum": "kare_yok", "kare": len(ims)}
        
    h, w = ims[0].shape[:2]
    ims = [im for im in ims if im.shape[:2] == (h, w)]
    griler = [cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) for im in ims]
    
    ai_griler = []
    for i, im in enumerate(ims):
        ai_griler.append(ai_flashlight_mask(im).astype(np.float32))
        
    varliklar = [(g > VARLIK_ESIK).astype(np.float32) for g in ai_griler]
    bosluk = [int((g > 0).sum()) for g in ai_griler]
    
    ciftler = cift_olc(ai_griler, bosluk, ai_griler, varliklar, h, w)
    
    # === AKILLI BIÇAK (TRIM) MANTIGI ===
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
    ref_idx = 0
    
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
            seg_im, seg_ofs, akum = [ims[i + 1]], [0.0], 0.0
            ref_idx = i + 1; i += 1; continue
            
        if c["sinif"] == "scroll":
            if ref_idx != i and not ayni_icerik(i, ref_idx):
                segmentler.append((seg_im, seg_ofs))
                seg_im, seg_ofs, akum = [ims[i]], [0.0], 0.0
                ref_idx = i
            akum += -c["dy"]
            seg_im.append(ims[i + 1])
            seg_ofs.append(akum)
            ref_idx = i + 1; i += 1; continue
            
        j = i
        kosu = []
        kosu_dylar = []
        while j < n_cift and ciftler[j]["sinif"] not in ("scroll", "kesme"):
            kosu.append(j + 1)
            kosu_dylar.append(ciftler[j]["dy"] if ciftler[j]["sinif"] == "duraksama" else 0.0)
            j += 1
            
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
            
        if kosu:
            def _kare_kalite_puani(idx):
                s = calculate_sharpness(griler[idx])
                v = varliklar[idx] > 0
                std_c = float(ai_griler[idx][v].std()) if int(v.sum()) > MIN_MASKE_PX else 1.0
                return s * (1.0 + std_c / 50.0)

            tem = max(kosu, key=_kare_kalite_puani)
            if not ayni_icerik(tem, ref_idx) and metin_gibi(ai_griler[tem], varliklar[tem]):
                segmentler.append((seg_im, seg_ofs))
                seg_im, seg_ofs, akum = [ims[tem]], [0.0], 0.0
                ref_idx = tem
        i = j
        
    segmentler.append((seg_im, seg_ofs))
    
    def _gecerli_segment(si, so):
        if not si:
            return False
        if len(si) > 1:
            return True
        g = cv2.cvtColor(si[0], cv2.COLOR_BGR2GRAY)
        m = ai_flashlight_mask(si[0]).astype(np.float32)
        v = (m > VARLIK_ESIK).astype(np.float32)
        return metin_gibi(m, v)

    parcalar = [_segment_kanvas(si, so) for si, so in segmentler if _gecerli_segment(si, so)]
    if not parcalar:
        parcalar = [_segment_kanvas(si, so) for si, so in segmentler if si]
    if not parcalar:
        return None, {"slug": slug, "durum": "kare_yok", "kare": len(ims), "sebep": "Gecerli segment kalmadi"}
    kanvas = np.vstack(parcalar) if len(parcalar) > 1 else parcalar[0]
    
    if kanvas.shape[0] > H_MAKS:
        return None, {"slug": slug, "durum": "boy_asimi", "boy": int(kanvas.shape[0])}
        
    sinif_sayimi = {s: sum(1 for c in ciftler if c.get("sinif") == s) for s in ("scroll", "duraksama", "kesme", "duraksama_bos", "duraksama_belirsiz")}
    scroll_dyler = [abs(c["dy"]) for c in ciftler if c.get("sinif") == "scroll"]
    scroll_dy_medyan = float(np.median(scroll_dyler)) if scroll_dyler else 0.0

    manifest = {
        "slug": slug,
        "durum": "OK",
        "mode": "lebron_james",
        "kare": len(ims),
        "size": [int(kanvas.shape[1]), int(kanvas.shape[0])],
        "segment": len(parcalar),
        "segment_kareler": [len(si) for si, _ in segmentler if si],
        "sinif_sayimi": sinif_sayimi,
        "scroll_dy_medyan": round(scroll_dy_medyan, 2),
        "ciftler": ciftler,
        "olcum_yolu": "ai_flashlight",
        "sure_s": round(time.time() - t0, 2)
    }
    
    return kanvas, manifest


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LeBron James Engine (Akıllı Trim + AI Flashlight + 2D Phase Correlate)")
    parser.add_argument("--slug", type=str, default="test", help="Klip / film adı slug")
    parser.add_argument("--kare-dizini", type=str, required=True, help="Jenerik PNG karelerinin bulunduğu klasör")
    parser.add_argument("--out", type=str, default=None, help="Çıktı master PNG dosya yolu (isteğe bağlı)")
    args = parser.parse_args()

    print(f"[LeBron CLI] İşleniyor: {args.kare_dizini}...")
    kanvas, manifest = compose_lebron(args.slug, kare_dizini=args.kare_dizini)
    if kanvas is not None:
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(out_path), kanvas)
            print(f"[LeBron CLI] Master PNG yazıldı: {out_path}")
        print(f"[LeBron CLI] Başarılı! Boyut: {manifest.get('size')}, Segment: {manifest.get('segment')}, Süre: {manifest.get('sure_s')}s")
    else:
        print(f"[LeBron CLI] Başarısız: {manifest.get('durum')}, Sebep: {manifest.get('sebep', 'Bilinmiyor')}")

