"""Dynamic Credit Mosaic Engine v2 — Karışık statik+scroll jeneriği için tek geçişli mozaik.

Algoritma özeti:
  1. Top-hat morfolojisi → ham metin maskesi (OCR yok, arka plan bağımsız).
  2. Bağlı-bileşen filtreleme (CC_FILTER): yalnızca metin-çizgisi şekline uyan blobları tut
     (yükseklik [CC_MIN_H, CC_MAX_H] ve alan < CC_MAX_AREA_FRAC). Film sahnelerindeki
     yüzler/nesneler/posterler büyük bloblar üretir ve elenir. Hayatta kalan bloblar
     MIN_CC_BLOBS adetinden azsa kare NO_TEXT sayılır.
  3. Metin-maskeli faz korelasyonu → dy (dikey text hareketi).
  4. Üç sinyalle durum makinesi: dy_smoothed, text_band_diff, global_diff.
  5. Tuval yazma kuralları:
     - NO_TEXT    → yaz hiçbir şey.
     - STATIC     → en keskin kareyi tek blok olarak yaz (template-dedup ile).
     - SCROLL     → delta-append: her kare sadece yeni gelen satırları ekler.
     - CARD_SWAP  → mevcut statik kartı sonlandır, yeni kart başlat.
     - CUT        → boşluk bırak, kümülatif offset sıfırla.

v2 düzeltmeleri:
  - Sahne/jeneri ayrımı: CC filtresi → sadece ince yatay bloblar kalır.
  - MIN_SCROLL_SECTION_FRAMES: < 5 ardışık kare scroll → sahte flicker, atla.
  - CARD_SWAP_COOLDOWN_FRAMES: Kart değişiminden sonra N kare baskılama.

cv2 Turkish-İ tuzağı: imread/imwrite YERİNE her zaman fromfile+imdecode / imencode+tofile.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Sabitler (kalibrasyon noktaları)
# ---------------------------------------------------------------------------

# --- Metin maskesi ---
TOPHAT_KSIZE: int = 25          # Top-hat yapısal eleman boyutu (px); metnin kalınlığından büyük olmalı
MASK_DILATION: int = 6          # Maske dilatasyon (glifleri birleştir)
MIN_TEXT_RATIO: float = 0.003   # Minimum metin alan oranı → has_text (CC filtreden SONRA)

# --- v2: Bağlı-bileşen filtresi (CC_FILTER) ---
# Jeneri satırları ince VE YATAY GENIŞ'tir (w >> h, aspect w/h >= 2.0).
# Film sahneleri: ya büyük bloblar (h>40) ya da küçük kare bloblar (aspect ~1).
# Bu filtrenin amaci: YALNIZca yatay genis/ince "metin satiri" blob'lari tutmak.
CC_MIN_H: int = 6               # Blob minimum yüksekliği (px) — gürültüyü at
CC_MAX_H: int = 45              # Blob maximum yüksekliği (px) — büyük sahne nesnelerini at
CC_MIN_W: int = 50              # Blob minimum genişliği (px) — dar kare blobları at (sahneler)
CC_MIN_ASPECT: float = 1.8      # w/h >= bu değer → metin satiri; daha az → sahne blobu
CC_MAX_AREA_FRAC: float = 0.04  # Blob alanı kare toplam px'in bu oranından büyükse at
MIN_CC_BLOBS: int = 2           # Hayatta kalan blob sayısı bu altındaysa kare NO_TEXT
# Dikey blob kümelenme filtresi: gerçek jenerik metin satırları birbirine yakındır.
# Sahne falso-pozitiflerinde bloblar kare boyunca dağılır.
# Hayatta kalan blobların dikey merkez noktaları arasındaki maksimum mesafe (px):
CC_MAX_BLOB_VERT_SPREAD: int = 120  # Bu üstünde → bloblar dağınık → muhtemelen sahne

# --- Faz korelasyonu ---
DRIFT_N: int = 15               # Medyan yumuşatma penceresi (kare sayısı); artırıldı: gürültülü dy için
DY_CLIP: float = 12.0           # Ham dy bu mutlak değerden büyükse kırp (kötü faz-kor çözüm)

# --- Durum makinesi hysteresis ---
S_HI: float = 0.8               # |dy_sm| >= S_HI → scroll'a geç (px); düşürüldü: yavaş rulolar
S_LO: float = 0.3               # |dy_sm| < S_LO → static'e dön (px); düşürüldü
SCROLL_CONFIRM: int = 3         # Kaç ardışık text kare scroll sayılınca scroll confirm
STATIC_CONFIRM: int = 3         # Kaç ardışık text kare static sayılınca static confirm

# --- v2: Minimum scroll bölüm uzunluğu ---
MIN_SCROLL_SECTION_FRAMES: int = 20  # Bu kadar ardışık scroll karesi olmadan scroll bölümü geçersiz

# --- CARD_SWAP algılama ---
CARD_SWAP_DIFF_MIN: float = 30.0   # text_band_diff eşiği (yükselt: geçiş gürültüsünü eletle)
CARD_SWAP_GLOBAL_MAX: float = 25.0 # global_diff üst sınırı (gerçek cut değil, arka plan sabit)

# --- v2: CARD_SWAP baskılama penceresi ---
CARD_SWAP_COOLDOWN_FRAMES: int = 4  # Kart değişiminden sonra bu kadar kare boyunca CARD_SWAP baskıla

# --- CUT algılama ---
CUT_RESPONSE_MAX: float = 0.04  # faz korelasyon gücü bu altında → şüpheli cut
CUT_GLOBAL_MIN: float = 40.0    # global_diff bu üstünde → gerçek cut

# --- Scroll yazma ---
# Negatif dy = metin YUKARI kayıyor = yeni satırlar ALT'tan giriyor.
# Delta-append: her kare metin bandının ALT kısmından delta px okunur.
# Y_REF_FRAC artık kullanılmıyor (bottom-strip modu); ama referans için tutuluyor.
Y_REF_FRAC: float = 0.58        # (Eski referans — bottom-strip modu bunu kullanmaz)

# --- Statik blok yazma ---
STATIC_MIN_FRAMES: int = 6      # En az bu kadar kare olmadan statik blok yazılmaz
STATIC_PAD_PX: int = 8          # Metin bandına üst/alt dolgu (piksel)
DEDUP_MATCH_THRESH: float = 0.85  # Template dedup eşiği (TM_CCORR_NORMED)
DEDUP_CHECK_ROWS: int = 30       # Yeni bloktan bu kadar satır karşılaştırılır
DEDUP_CANVAS_ROWS: int = 120     # Canvas'ın son bu kadar satırında aranır

# --- Canvas ---
MAX_CANVAS_H: int = 80000
GAP_HEIGHT: int = 20
GAP_GRAY: int = 40

# --- Labeled çıktı ---
LABEL_STATIC_COLOR: tuple = (60, 180, 60)    # BGR yeşil
LABEL_SCROLL_COLOR: tuple = (60, 60, 220)    # BGR kırmızı
LABEL_GAP_COLOR: tuple = (120, 120, 120)     # Gri
LABEL_BAND_H: int = 4                         # Bölüm sınırı çizgi yüksekliği


# ---------------------------------------------------------------------------
# Veri yapıları
# ---------------------------------------------------------------------------

@dataclass
class MosaicResult:
    master_path: Path
    labeled_path: Path
    debug_path: Path
    canvas_size: tuple[int, int]          # (W, H)
    sections: list[dict[str, Any]] = field(default_factory=list)
    n_static_blocks: int = 0
    n_scroll_sections: int = 0
    n_card_swap_events: int = 0
    n_cut_events: int = 0
    runtime_sec: float = 0.0


# ---------------------------------------------------------------------------
# I/O yardımcıları  (Turkish-İ güvenli)
# ---------------------------------------------------------------------------

def _read(path: Path) -> np.ndarray | None:
    """BGR kare oku. cv2.imread KULLANMA (Türkçe-İ path tuzağı)."""
    try:
        buf = np.fromfile(str(path), np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _write(path: Path, img: np.ndarray) -> bool:
    """PNG yaz. cv2.imwrite KULLANMA."""
    try:
        ok, buf = cv2.imencode(".png", img)
        if ok:
            buf.tofile(str(path))
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Görüntü işleme yardımcıları
# ---------------------------------------------------------------------------

def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()


def _sharpness(gray: np.ndarray) -> float:
    """Laplacian varyansı → keskinlik skoru."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _hann2d(h: int, w: int) -> np.ndarray:
    return (
        np.hanning(h).reshape(-1, 1).astype(np.float32)
        * np.hanning(w).reshape(1, -1).astype(np.float32)
    )


def _phase_corr(
    g1: np.ndarray,
    g2: np.ndarray,
    hann: np.ndarray,
) -> tuple[float, float, float]:
    """Maskelenmiş gri kareler arasında faz korelasyonu → (dx, dy, response)."""
    try:
        (dx, dy), rsp = cv2.phaseCorrelate(
            g1.astype(np.float32) * hann,
            g2.astype(np.float32) * hann,
        )
        return float(dx), float(dy), float(rsp)
    except Exception:
        return 0.0, 0.0, 0.0


def _gdiff(g1: np.ndarray, g2: np.ndarray) -> float:
    """Tüm kare ortalama mutlak gri farkı."""
    return float(np.mean(np.abs(g1.astype(np.float32) - g2.astype(np.float32))))


def _text_band_diff(
    g1: np.ndarray,
    g2: np.ndarray,
    m1: np.ndarray | None,
    m2: np.ndarray | None,
) -> float:
    """Metin maskelerinin birleşimi içinde ortalama mutlak gri fark.
    Kart değişimini (text_band_diff) hesaplar.
    """
    if m1 is None and m2 is None:
        return 0.0
    union = np.zeros(g1.shape, dtype=np.uint8)
    if m1 is not None:
        union = cv2.bitwise_or(union, m1)
    if m2 is not None:
        union = cv2.bitwise_or(union, m2)
    mask_bool = union > 0
    if not mask_bool.any():
        return 0.0
    diff = np.abs(g1.astype(np.float32) - g2.astype(np.float32))
    return float(diff[mask_bool].mean())


def _build_tophat_mask(gray: np.ndarray) -> tuple[np.ndarray, int]:
    """Top-hat morfolojisi + CC filtresi ile metin maskesi oluştur (OCR'sız, BG-agnostik).

    v2: Bağlı bileşen analizi ile film sahnelerindeki büyük blob'lar elenir.
    Yalnızca metin-çizgisi şekline uyan bloblar (ince, dar yükseklikli) tutulur.

    Returns:
        (filtered_mask, n_surviving_blobs) — n_surviving_blobs < MIN_CC_BLOBS ise
        kare NO_TEXT sayılmalı.
    """
    # Yapısal eleman: geniş yatay + dikey dikdörtgen (metni değil arka planı modeller)
    k = max(3, TOPHAT_KSIZE | 1)  # tek sayı olsun
    se = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k // 3 + 1))

    # White top-hat = gray - morphological opening
    opened = cv2.morphologyEx(gray, cv2.MORPH_OPEN, se)
    tophat = cv2.subtract(gray, opened)

    # Otsu eşikleme
    _, mask = cv2.threshold(tophat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Dilatasyon: glifleri birleştir
    if MASK_DILATION > 0:
        dil_se = cv2.getStructuringElement(
            cv2.MORPH_RECT, (MASK_DILATION, MASK_DILATION // 2 + 1)
        )
        mask = cv2.dilate(mask, dil_se)

    # --- v2: Bağlı bileşen filtresi ---
    # Yalnızca metin-çizgisi şekline uyan bloblar tutulur:
    #   - Yükseklik [CC_MIN_H, CC_MAX_H] px — çok kısa gürültü ve çok büyük nesneler elenir.
    #   - Genişlik >= CC_MIN_W px — dar kare bloblar (sahne kenarları) elenir.
    #   - Aspect w/h >= CC_MIN_ASPECT — metin satırları yatay uzundur.
    #   - Alan <= CC_MAX_AREA_FRAC * frame — dev bloblar elenir.
    total_px = gray.shape[0] * gray.shape[1]
    max_area_px = int(CC_MAX_AREA_FRAC * total_px)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    # stats sütunları: LEFT, TOP, WIDTH, HEIGHT, AREA
    filtered_mask = np.zeros_like(mask)
    n_surviving = 0
    for lbl in range(1, n_labels):  # 0 = arka plan
        h_blob = int(stats[lbl, cv2.CC_STAT_HEIGHT])
        w_blob = int(stats[lbl, cv2.CC_STAT_WIDTH])
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        aspect = w_blob / max(1, h_blob)
        if (CC_MIN_H <= h_blob <= CC_MAX_H
                and w_blob >= CC_MIN_W
                and aspect >= CC_MIN_ASPECT
                and area <= max_area_px):
            filtered_mask[labels == lbl] = 255
            n_surviving += 1

    return filtered_mask, n_surviving


def _masked_gray(gray: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    if mask is None:
        return gray
    out = np.zeros_like(gray)
    out[mask > 0] = gray[mask > 0]
    return out


def _text_ratio(mask: np.ndarray, total_px: int) -> float:
    return float(np.count_nonzero(mask)) / max(1, total_px)


def _med(buf: list[float]) -> float:
    return float(np.median(buf)) if buf else 0.0


def _text_band_rows(mask: np.ndarray, pad: int = STATIC_PAD_PX) -> tuple[int, int]:
    """Maskedeki metin satırlarının min/max y koordinatı (+ dolgu)."""
    rows = np.any(mask > 0, axis=1)
    if not rows.any():
        return 0, mask.shape[0]
    r_min = int(np.argmax(rows))
    r_max = int(len(rows) - 1 - np.argmax(rows[::-1]))
    h = mask.shape[0]
    return max(0, r_min - pad), min(h, r_max + pad + 1)


DEDUP_MIN_KEEP: int = 20   # dedup sonrası en az bu kadar satır kalmalı; daha azsa dedup iptal

def _template_dedup(
    new_block: np.ndarray,
    canvas: np.ndarray,
    cy: int,
) -> int:
    """Yeni bloğun üst N satırını canvas'ın son M satırıyla karşılaştır.
    Güçlü eşleşme bulunursa örtüşen satır sayısını döndür (çıkarılacak).
    Hiç eşleşme yoksa 0 döner.
    Blok DEDUP_MIN_KEEP satırdan daha kısa kalacaksa dedup iptal edilir.
    """
    if cy < DEDUP_CHECK_ROWS or new_block.shape[0] < DEDUP_CHECK_ROWS:
        return 0
    # new_block'un üst DEDUP_CHECK_ROWS satırı
    tmpl = cv2.cvtColor(new_block[:DEDUP_CHECK_ROWS], cv2.COLOR_BGR2GRAY).astype(np.float32)
    # Canvas'ın son DEDUP_CANVAS_ROWS satırı
    search_start = max(0, cy - DEDUP_CANVAS_ROWS)
    region = cv2.cvtColor(
        canvas[search_start:cy], cv2.COLOR_BGR2GRAY
    ).astype(np.float32)
    if region.shape[0] < DEDUP_CHECK_ROWS:
        return 0
    try:
        result = cv2.matchTemplate(region, tmpl, cv2.TM_CCORR_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val >= DEDUP_MATCH_THRESH:
            # Eşleşme konumu canvas içinde: örtüşen satır sayısı
            match_y = search_start + max_loc[1]
            overlap = cy - match_y
            skip = max(0, min(overlap, new_block.shape[0] - 1))
            # Blok fazla kısalacaksa dedup iptal et
            if new_block.shape[0] - skip < DEDUP_MIN_KEEP:
                return 0
            return skip
    except Exception:
        pass
    return 0


# ---------------------------------------------------------------------------
# Ana motor
# ---------------------------------------------------------------------------

def run_dynamic_credit_mosaic(
    frames: list[Path],
    *,
    output_dir: Path,
    source_fps: float = 6.0,
) -> MosaicResult:
    """Karma jeneri (statik kart + scroll) için dinamik mozaik oluştur.

    Args:
        frames: Sıralı kare yolları (Path listesi).
        output_dir: master.png, debug.json, master_labeled.png çıktı dizini.
        source_fps: Kaynak FPS (debug.json'a yazılır).

    Returns:
        MosaicResult dataclass.
    """
    t0 = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)

    n = len(frames)
    if n == 0:
        raise ValueError("Kare listesi boş.")

    # Kare boyutunu belirle
    fh = fw = None
    for fp in frames:
        img0 = _read(fp)
        if img0 is not None:
            fh, fw = img0.shape[:2]
            break
    if fh is None:
        raise RuntimeError("Hiç kare okunamadı.")
    print(f"  [DynMosaic] Kare boyutu: {fw}x{fh}, toplam kare: {n}", flush=True)

    hann = _hann2d(fh, fw)
    total_px = fh * fw

    # Canvas
    canvas = np.zeros((MAX_CANVAS_H, fw, 3), dtype=np.uint8)
    cy = 0  # sonraki yazma satırı

    # Scroll delta-append durumu
    cum_offset: float = 0.0     # kümülatif metin hareketi (scroll bölümü içinde)
    written: float = 0.0        # canvas'a yazılmış kümülatif yükseklik (scroll bölümü içinde)

    # Durum makinesi
    state: str = "NO_TEXT"          # NO_TEXT | STATIC | SCROLL
    scroll_consecutive: int = 0     # ardışık scroll sinyal sayısı
    static_consecutive: int = 0     # ardışık static sinyal sayısı

    # Çalışma zamanı izleme
    dy_buf: list[float] = []
    prev_gray_r: np.ndarray | None = None
    prev_mask: np.ndarray | None = None

    # Statik birikim
    st_run: list[tuple[int, float, np.ndarray, np.ndarray | None]] = []
    # (frame_idx, sharpness, img, mask)
    st_start: int | None = None
    st_section_id: int | None = None

    # Bölüm listesi
    sections: list[dict] = []
    sec_id: int = 0
    n_static = 0
    n_scroll = 0
    n_card_swap = 0
    n_cut = 0

    # Scroll bölümü izleme
    sc_start: int | None = None
    sc_y0: int = 0
    sc_first_frame_written: bool = False

    # v2: scroll bölüm geçici birikim (MIN_SCROLL_SECTION_FRAMES kontrolü için)
    sc_pending_frames: int = 0      # mevcut scroll bölümünde sayılan kare sayısı

    # v2: CARD_SWAP baskılama
    card_swap_cooldown: int = 0     # bu > 0 iken CARD_SWAP ateşlenmez

    # Debug kare listesi
    debug_frames: list[dict] = []

    # ── İç yardımcılar ────────────────────────────────────────────────────

    def _gap() -> None:
        nonlocal cy
        h = min(GAP_HEIGHT, MAX_CANVAS_H - cy)
        if h > 0:
            canvas[cy:cy + h] = GAP_GRAY
            cy += h

    def _write_block_crop(
        img: np.ndarray, mask: np.ndarray | None
    ) -> tuple[int, int]:
        """Metin bandını (mask'tan) kırp, canvas'a yaz, (y0, y1) döndür."""
        nonlocal cy
        if mask is not None:
            r0, r1 = _text_band_rows(mask)
        else:
            r0, r1 = 0, img.shape[0]
        block = img[r0:r1]
        if block.shape[0] == 0:
            return cy, cy

        # Template dedup
        skip = _template_dedup(block, canvas, cy)
        if skip > 0:
            block = block[skip:]
        if block.shape[0] == 0:
            return cy, cy

        h = min(block.shape[0], MAX_CANVAS_H - cy)
        if h <= 0:
            return cy, cy
        y0 = cy
        canvas[cy:cy + h] = block[:h]
        cy += h
        return y0, cy

    def flush_static(end_idx: int) -> None:
        nonlocal sec_id, cy, n_static
        if not st_run:
            return
        if len(st_run) < STATIC_MIN_FRAMES:
            st_run.clear()
            return
        # En keskin kareyi seç
        best = max(st_run, key=lambda t: t[1])
        best_idx, _, best_img, best_mask = best
        y0, y1 = _write_block_crop(best_img, best_mask)
        sections.append({
            "section_id": sec_id, "kind": "static",
            "start_frame_idx": st_run[0][0], "end_frame_idx": end_idx,
            "start_y": y0, "end_y": y1, "frame_count": len(st_run),
            "best_frame_idx": best_idx,
        })
        sec_id += 1
        n_static += 1
        st_run.clear()

    def close_scroll(end_idx: int) -> None:
        nonlocal sec_id, n_scroll
        if sc_start is None:
            return
        sections.append({
            "section_id": sec_id, "kind": "scroll",
            "start_frame_idx": sc_start, "end_frame_idx": end_idx,
            "start_y": sc_y0, "end_y": cy,
            "frame_count": end_idx - sc_start + 1,
        })
        sec_id += 1
        n_scroll += 1

    # ── Kare-kare döngüsü ─────────────────────────────────────────────────

    for i, fp in enumerate(frames):
        img = _read(fp)
        if img is None:
            debug_frames.append({
                "frame_idx": i, "has_text": False, "text_ratio": 0.0, "n_blobs": 0,
                "dx": 0.0, "dy": 0.0, "dy_smoothed": 0.0,
                "response": 0.0, "global_diff": 0.0, "text_band_diff": 0.0,
                "state": state, "event": "read_error",
                "cum_offset": round(cum_offset, 2), "written": round(written, 2),
                "canvas_y": cy,
            })
            continue

        if img.shape[:2] != (fh, fw):
            img = cv2.resize(img, (fw, fh), interpolation=cv2.INTER_AREA)

        gray_r = _gray(img)

        # --- Metin maskesi (top-hat + CC filtresi) ---
        mask_raw, n_blobs = _build_tophat_mask(gray_r)
        tar = _text_ratio(mask_raw, total_px)
        # v2: hem oran hem blob sayısı koşulu
        has_text = tar >= MIN_TEXT_RATIO and n_blobs >= MIN_CC_BLOBS
        mask = mask_raw if has_text else None

        # --- Faz korelasyonu ---
        dx = dy = 0.0
        rsp = 1.0
        gdiff = 0.0
        tbd = 0.0

        if prev_gray_r is not None:
            # Metin-maskeli gri
            gm_prev = _masked_gray(prev_gray_r, prev_mask)
            gm_cur = _masked_gray(gray_r, mask)
            dx, dy, rsp = _phase_corr(gm_prev, gm_cur, hann)
            gdiff = _gdiff(prev_gray_r, gray_r)
            tbd = _text_band_diff(prev_gray_r, gray_r, prev_mask, mask)

        # --- Drift yumuşatma ---
        # Dikkat: önceki kare NO_TEXT ise faz korelasyonu bozuk olabilir (metin maskesi yok).
        # Bu durumda dy değerini buffer'a ekleme; sadece gerçek metin->metin geçişlerini kullan.
        # v2: Ham dy'yi DY_CLIP ile kırp — aşırı outlier'lar medyanı bozuyor.
        prev_had_text = prev_mask is not None
        if has_text and prev_had_text:
            dy_clipped = max(-DY_CLIP, min(DY_CLIP, dy))
            dy_buf.append(dy_clipped)
            if len(dy_buf) > DRIFT_N * 4:
                dy_buf.pop(0)
        dy_sm = _med(dy_buf[-DRIFT_N:]) if dy_buf else 0.0

        # --- Olay tespiti ---
        is_cut = (i > 0 and rsp < CUT_RESPONSE_MAX and gdiff > CUT_GLOBAL_MIN)
        # v2: CARD_SWAP baskılama penceresi — cooldown > 0 iken CARD_SWAP ateşlenmesin
        is_card_swap = (
            state == "STATIC"
            and abs(dy_sm) < S_LO
            and tbd > CARD_SWAP_DIFF_MIN
            and gdiff < CARD_SWAP_GLOBAL_MAX
            and card_swap_cooldown == 0
        )

        # Hareket sinyali
        moving = abs(dy_sm) >= S_HI
        still = abs(dy_sm) < S_LO

        # --- Durum geçişleri (hysteresis) ---
        event = "none"

        # v2: Her karede CARD_SWAP cooldown sayacını düşür
        if card_swap_cooldown > 0:
            card_swap_cooldown -= 1

        if not has_text:
            event = "no_text"
            scroll_consecutive = 0
            static_consecutive = 0
            dy_buf.clear()   # NO_TEXT'e geçince buffer temizle — stale dy değerlerini unut
            card_swap_cooldown = 0
            # v2: Scroll bölümü sona erdi — MIN_SCROLL_SECTION_FRAMES kontrol et
            if sc_start is not None:
                if sc_pending_frames >= MIN_SCROLL_SECTION_FRAMES:
                    close_scroll(i - 1)
                else:
                    # Çok kısa scroll: canvas'ta yazılanları geri al (sc_y0'dan itibaren)
                    cy = sc_y0
                sc_start = None
                sc_first_frame_written = False
                sc_pending_frames = 0
                cum_offset = 0.0
                written = 0.0
            state = "NO_TEXT"

        elif is_cut:
            event = "cut"
            n_cut += 1
            # Mevcut bölümleri kapat
            if st_start is not None:
                flush_static(i - 1)
                st_start = None
            if sc_start is not None:
                if sc_pending_frames >= MIN_SCROLL_SECTION_FRAMES:
                    close_scroll(i - 1)
                else:
                    cy = sc_y0
                sc_start = None
                sc_first_frame_written = False
                sc_pending_frames = 0
            if cy > 0:
                _gap()
            dy_buf.clear()
            cum_offset = 0.0
            written = 0.0
            scroll_consecutive = 0
            static_consecutive = 0
            card_swap_cooldown = 0
            state = "NO_TEXT"

        elif is_card_swap:
            event = "card_swap"
            n_card_swap += 1
            # v2: Cooldown başlat
            card_swap_cooldown = CARD_SWAP_COOLDOWN_FRAMES
            # Mevcut statik kartı yaz, yeni kartı başlat
            if st_start is not None:
                flush_static(i - 1)
                st_start = i
            st_run.append((i, _sharpness(gray_r), img.copy(), mask.copy() if mask is not None else None))

        else:
            # Hysteresis geçişleri
            if moving:
                scroll_consecutive += 1
                static_consecutive = 0
            elif still:
                static_consecutive += 1
                scroll_consecutive = 0
            else:
                # Hysteresis bandı içinde: mevcut durumu koru
                pass

            # dy_buf yeterince dolmadan scroll geçişi yapma (warmup guard)
            buf_ready = len(dy_buf) >= min(DRIFT_N, 4)

            if state != "SCROLL" and scroll_consecutive >= SCROLL_CONFIRM and buf_ready:
                # SCROLL'a gir
                if st_start is not None:
                    flush_static(i - 1)
                    st_start = None
                if sc_start is None:
                    sc_start = i
                    sc_y0 = cy
                    sc_first_frame_written = False
                    sc_pending_frames = 0
                    cum_offset = 0.0
                    written = 0.0
                state = "SCROLL"
                event = "scroll"

            elif state != "STATIC" and static_consecutive >= STATIC_CONFIRM:
                # STATIC'e gir
                if sc_start is not None:
                    # v2: MIN_SCROLL_SECTION_FRAMES kontrolü
                    if sc_pending_frames >= MIN_SCROLL_SECTION_FRAMES:
                        close_scroll(i - 1)
                    else:
                        cy = sc_y0  # Çok kısa: canvas'ı geri al
                    sc_start = None
                    sc_first_frame_written = False
                    sc_pending_frames = 0
                    cum_offset = 0.0
                    written = 0.0
                if st_start is None:
                    st_start = i
                state = "STATIC"
                event = "static"

            else:
                # Mevcut durumu sürdür
                if state == "SCROLL":
                    event = "scroll"
                elif state == "STATIC":
                    event = "static"
                else:
                    event = "no_text"

            # --- Tuval yazma ---
            if state == "STATIC" and event in ("static", "card_swap"):
                if st_start is None:
                    st_start = i
                st_run.append((i, _sharpness(gray_r), img.copy(), mask.copy() if mask is not None else None))

            elif state == "SCROLL":
                sc_pending_frames += 1
                if not sc_first_frame_written:
                    # Scroll bölümünün ilk karesi: tam metin bandını yaz
                    if mask is not None:
                        r0, r1 = _text_band_rows(mask)
                    else:
                        r0, r1 = 0, fh
                    block = img[r0:r1]
                    h = min(block.shape[0], MAX_CANVAS_H - cy)
                    if h > 0:
                        canvas[cy:cy + h] = block[:h]
                        cy += h
                    sc_first_frame_written = True
                    written = 0.0   # delta-append sayacı sıfır: ilk kareden sonra yeni piksel yok
                    cum_offset = 0.0
                else:
                    # Delta-append: metin yukarı kayıyor → yeni satırlar altta çıkıyor.
                    # Okuma noktası: mevcut karenin metin bandının ALT kenarından delta px okunur.
                    # Bu sayede her append tam olarak yeni gelen satırları alır.
                    cum_offset += abs(dy_sm)
                    delta = int(round(cum_offset - written))
                    if delta >= 1:
                        # Mevcut karenin metin band alt sınırı
                        if mask is not None:
                            _, r1_cur = _text_band_rows(mask, pad=0)
                        else:
                            r1_cur = fh
                        y_read_end = min(r1_cur, fh)
                        y_read_start = max(0, y_read_end - delta)
                        actual_delta = y_read_end - y_read_start
                        if actual_delta > 0:
                            strip = img[y_read_start:y_read_end, :]
                            h = min(actual_delta, MAX_CANVAS_H - cy)
                            if h > 0:
                                canvas[cy:cy + h] = strip[:h]
                                cy += h
                        written += delta

        # Debug kaydı
        debug_frames.append({
            "frame_idx": i,
            "has_text": has_text,
            "text_ratio": round(tar, 4),
            "n_blobs": n_blobs,
            "dx": round(dx, 3),
            "dy": round(dy, 3),
            "dy_smoothed": round(dy_sm, 3),
            "response": round(rsp, 4),
            "global_diff": round(gdiff, 2),
            "text_band_diff": round(tbd, 2),
            "state": state,
            "event": event,
            "cum_offset": round(cum_offset, 2),
            "written": round(written, 2),
            "canvas_y": cy,
        })

        prev_gray_r = gray_r
        prev_mask = mask

    # ── Son bölümleri kapat ───────────────────────────────────────────────
    if st_start is not None:
        flush_static(n - 1)
    if sc_start is not None:
        # v2: MIN_SCROLL_SECTION_FRAMES kontrolü
        if sc_pending_frames >= MIN_SCROLL_SECTION_FRAMES:
            close_scroll(n - 1)
        else:
            cy = sc_y0  # Çok kısa: geri al

    # ── Master PNG ────────────────────────────────────────────────────────
    master = canvas[:max(1, cy), :].copy()
    mh, mw = master.shape[:2]
    master_path = output_dir / "master.png"
    _write(master_path, master)
    print(f"  [DynMosaic] master.png: {mw}x{mh}px -> {master_path}", flush=True)

    # ── Master Labeled PNG ────────────────────────────────────────────────
    labeled = master.copy()
    for sec in sections:
        color = LABEL_STATIC_COLOR if sec["kind"] == "static" else LABEL_SCROLL_COLOR
        y0 = sec["start_y"]
        y1 = min(sec["end_y"], mh)
        # Üst çizgi
        labeled[max(0, y0):min(mh, y0 + LABEL_BAND_H), :] = color
        # Alt çizgi
        labeled[max(0, y1 - LABEL_BAND_H):y1, :] = color
    labeled_path = output_dir / "master_labeled.png"
    _write(labeled_path, labeled)
    print(f"  [DynMosaic] master_labeled.png -> {labeled_path}", flush=True)

    # ── debug.json ────────────────────────────────────────────────────────
    runtime = perf_counter() - t0
    dbg: dict[str, Any] = {
        "run_params": {
            "source_fps": source_fps,
            "n_frames": n,
            "frame_size_wh": [fw, fh],
            "TOPHAT_KSIZE": TOPHAT_KSIZE,
            "MASK_DILATION": MASK_DILATION,
            "MIN_TEXT_RATIO": MIN_TEXT_RATIO,
            "CC_MIN_H": CC_MIN_H,
            "CC_MAX_H": CC_MAX_H,
            "CC_MIN_W": CC_MIN_W,
            "CC_MIN_ASPECT": CC_MIN_ASPECT,
            "CC_MAX_AREA_FRAC": CC_MAX_AREA_FRAC,
            "MIN_CC_BLOBS": MIN_CC_BLOBS,
            "DRIFT_N": DRIFT_N,
            "DY_CLIP": DY_CLIP,
            "S_HI": S_HI,
            "S_LO": S_LO,
            "SCROLL_CONFIRM": SCROLL_CONFIRM,
            "STATIC_CONFIRM": STATIC_CONFIRM,
            "MIN_SCROLL_SECTION_FRAMES": MIN_SCROLL_SECTION_FRAMES,
            "CARD_SWAP_DIFF_MIN": CARD_SWAP_DIFF_MIN,
            "CARD_SWAP_GLOBAL_MAX": CARD_SWAP_GLOBAL_MAX,
            "CARD_SWAP_COOLDOWN_FRAMES": CARD_SWAP_COOLDOWN_FRAMES,
            "CUT_RESPONSE_MAX": CUT_RESPONSE_MAX,
            "CUT_GLOBAL_MIN": CUT_GLOBAL_MIN,
            "Y_REF_FRAC": Y_REF_FRAC,
            "STATIC_MIN_FRAMES": STATIC_MIN_FRAMES,
            "STATIC_PAD_PX": STATIC_PAD_PX,
            "DEDUP_MATCH_THRESH": DEDUP_MATCH_THRESH,
        },
        "canvas_size_wh": [mw, mh],
        "n_static_blocks": n_static,
        "n_scroll_sections": n_scroll,
        "n_card_swap_events": n_card_swap,
        "n_cut_events": n_cut,
        "runtime_sec": round(runtime, 2),
        "sections": sections,
        "frames": debug_frames,
    }
    debug_path = output_dir / "debug.json"
    debug_path.write_text(
        json.dumps(dbg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  [DynMosaic] debug.json -> {debug_path}", flush=True)

    return MosaicResult(
        master_path=master_path,
        labeled_path=labeled_path,
        debug_path=debug_path,
        canvas_size=(mw, mh),
        sections=sections,
        n_static_blocks=n_static,
        n_scroll_sections=n_scroll,
        n_card_swap_events=n_card_swap,
        n_cut_events=n_cut,
        runtime_sec=round(runtime, 2),
    )
