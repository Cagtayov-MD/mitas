"""BoxMotionTrack — Çağatay'ın box-takip panorama motoru.

Algoritma özeti (PRENSIPLER.md §3):
  1. Seyrek OCR (her OCR_STRIDE karede) ile box seed'le / yenile.
  2. Her karede box-içi Lucas-Kanade optik akışı ile box'ları sürükle.
  3. Aktif box'ların dy medyanı = panorama kayması.
  4. Kümülatif ofset ile ekran şeridini tuvale yapıştır (akan faz) ya da
     en net kareyi blok olarak ekle (statik faz).
  5. Handoff: box üst %15'e girince düşür; seyrek OCR alttan yeni ekler.
  6. Cut/dissolve: global fark veya ani box kaybı → yeni bölüm, boşluk bırak.
  7. Drift çapası: seyrek OCR pozisyonuyla tracking tahmini ara ara senkronla.
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
# Ayarlanabilir sabitler
# ---------------------------------------------------------------------------
OCR_STRIDE: int = 8          # Her kaçıncı karede OCR çalıştırılır
STATIC_EPS: float = 0.8      # |medyan dy| < bu değer → statik faz (piksel)
HANDOFF_TOP_RATIO: float = 0.15  # Box'un üstü frame yüksekliğinin bu oranının altına girince düşür
CUT_GLOBAL_DIFF: float = 45.0    # İki kare arası ortalama piksel farkı bu değeri geçerse cut
CUT_BOXLOSS_RATIO: float = 0.70  # Aktif box'ların bu oranı aniden kaybolursa cut
LK_WINSIZE: int = 21         # Lucas-Kanade pencere boyutu
LK_MAX_LEVEL: int = 3        # Piramit seviyeleri
LK_MAX_FEATURES: int = 100   # Box başına maksimum feature
MIN_GOOD_FEATURES: int = 3   # Box başı LK için asgari geçerli feature
BOX_MARGIN: int = 4          # Box ROI'yi biraz büyüt (feature kenardan kaçmasın)
ANCHOR_EVERY: int = 40       # Her kaç karede bir drift çapası çalıştır
STATIC_BLOCK_MIN_FRAMES: int = 6  # Blok olarak kaydedilmesi için asgari statik kare sayısı
CANVAS_WIDTH: int = 800      # Panorama canvas genişliği
MAX_CANVAS_HEIGHT: int = 30000   # Panorama maximum yüksekliği (güvenlik)
MIN_FRAME_DIFF_FOR_STRIP: float = 1.5  # Şerit yapıştırmak için asgari |dy|

# Text-mask ayarları (Fix 2 & 3)
TEXT_MASK_DILATION: int = 8      # Text box maskesini kaç px genişlet (yazı kenarını kap)
TEXT_MASK_MIN_BOX_AREA: int = 50 # Bu px² altındaki kutuları maskeden dışla (gürültü)


# ---------------------------------------------------------------------------
# Veri yapıları
# ---------------------------------------------------------------------------
@dataclass
class ActiveBox:
    """Takip edilen tek bir metin kutusu."""
    box_id: int
    # Mevcut karedeki pozisyon [x, y, w, h]
    x: float
    y: float
    w: float
    h: float
    text: str
    confidence: float
    # Lucas-Kanade için feature noktaları (None → henüz hesaplanmamış)
    features: np.ndarray | None = None  # shape (N, 1, 2) float32
    lost_frames: int = 0
    age: int = 0  # kaç kare yaşadı


@dataclass
class BoxTrackResult:
    panorama_path: Path
    text_lines: list[dict[str, Any]]
    sections: list[dict[str, Any]]
    debug: dict[str, Any]


# ---------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ---------------------------------------------------------------------------
def _imread_safe(path: Path) -> np.ndarray | None:
    """Windows Turkish-İ yol güvenceli okuma."""
    try:
        buf = np.fromfile(str(path), np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def _imwrite_safe(path: Path, img: np.ndarray) -> bool:
    """Windows Turkish-İ yol güvenceli yazma."""
    try:
        ok, buf = cv2.imencode(".png", img)
        if ok:
            buf.tofile(str(path))
            return True
    except Exception:
        pass
    return False


def _bbox_to_xywh(bbox: list[float] | None) -> tuple[float, float, float, float] | None:
    """bbox [x, y, w, h] formatını döndür. None → None."""
    if bbox and len(bbox) >= 4:
        return float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
    return None


def _box_roi(img: np.ndarray, x: float, y: float, w: float, h: float, margin: int = BOX_MARGIN) -> tuple[int, int, int, int]:
    """Box'u biraz büyüterek geçerli ROI koordinatları döndür."""
    H, W = img.shape[:2]
    x1 = max(0, int(x) - margin)
    y1 = max(0, int(y) - margin)
    x2 = min(W, int(x + w) + margin)
    y2 = min(H, int(y + h) + margin)
    return x1, y1, x2, y2


def _extract_features_in_box(gray: np.ndarray, x: float, y: float, w: float, h: float) -> np.ndarray | None:
    """Box içinde goodFeaturesToTrack; koordinatlar tam görüntüye göre."""
    x1, y1, x2, y2 = _box_roi(gray, x, y, w, h)
    if x2 <= x1 or y2 <= y1:
        return None
    roi = gray[y1:y2, x1:x2]
    if roi.size == 0:
        return None
    pts = cv2.goodFeaturesToTrack(
        roi,
        maxCorners=LK_MAX_FEATURES,
        qualityLevel=0.05,
        minDistance=3,
        blockSize=5,
    )
    if pts is None or len(pts) == 0:
        return None
    # ROI-lokal koordinatları global görüntü koordinatlarına çevir
    pts[:, 0, 0] += x1
    pts[:, 0, 1] += y1
    return pts.astype(np.float32)


def _track_box_lk(
    prev_gray: np.ndarray,
    cur_gray: np.ndarray,
    box: ActiveBox,
) -> tuple[float | None, float | None, np.ndarray | None]:
    """Lucas-Kanade ile box'u sürükle. Döner: (dx, dy, yeni_features)."""
    if box.features is None or len(box.features) == 0:
        # Feature yeniden hesapla
        pts = _extract_features_in_box(prev_gray, box.x, box.y, box.w, box.h)
        if pts is None or len(pts) < MIN_GOOD_FEATURES:
            return None, None, None
        box.features = pts

    pts0 = box.features
    lk_criteria = (
        cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01
    )
    pts1, status, _ = cv2.calcOpticalFlowPyrLK(
        prev_gray,
        cur_gray,
        pts0,
        None,
        winSize=(LK_WINSIZE, LK_WINSIZE),
        maxLevel=LK_MAX_LEVEL,
        criteria=lk_criteria,
    )
    if pts1 is None or status is None:
        return None, None, None

    good_mask = status.flatten() == 1
    if good_mask.sum() < MIN_GOOD_FEATURES:
        return None, None, None

    good0 = pts0[good_mask]
    good1 = pts1[good_mask]

    displacements = good1 - good0
    dx = float(np.median(displacements[:, 0, 0]))
    dy = float(np.median(displacements[:, 0, 1]))

    # Feature pozisyonlarını güncelle (sadece geçerliler)
    new_features = good1.reshape(-1, 1, 2).astype(np.float32)
    return dx, dy, new_features


def _box_center_y(box: ActiveBox) -> float:
    return box.y + box.h / 2.0


def _global_frame_diff(prev_gray: np.ndarray, cur_gray: np.ndarray) -> float:
    """İki kare arası ortalama mutlak piksel farkı."""
    diff = cv2.absdiff(prev_gray, cur_gray)
    return float(np.mean(diff))


def _image_sharpness(gray: np.ndarray) -> float:
    """Laplacian varyansı ile görüntü netliği."""
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(lap.var())


def _match_ocr_to_active_boxes(
    records: list[dict[str, Any]],
    active_boxes: list[ActiveBox],
    *,
    iou_thresh: float = 0.3,
    dist_thresh: float = 60.0,
) -> tuple[list[ActiveBox], list[dict[str, Any]]]:
    """Yeni OCR sonuçlarını aktif box'larla eşleştir.

    Döner: (güncellenmiş_boxes, eşleşmeyen_yeni_kayıtlar).
    """
    matched_new_indices = set()

    for box in active_boxes:
        best_idx = -1
        best_score = -1.0
        for i, rec in enumerate(records):
            if i in matched_new_indices:
                continue
            xywh = _bbox_to_xywh(rec.get("bbox"))
            if xywh is None:
                continue
            nx, ny, nw, nh = xywh
            # Merkez mesafesi
            cx1, cy1 = box.x + box.w / 2, box.y + box.h / 2
            cx2, cy2 = nx + nw / 2, ny + nh / 2
            dist = ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5
            # IoU
            ix1 = max(box.x, nx)
            iy1 = max(box.y, ny)
            ix2 = min(box.x + box.w, nx + nw)
            iy2 = min(box.y + box.h, ny + nh)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            union = box.w * box.h + nw * nh - inter
            iou = inter / union if union > 0 else 0.0
            score = iou * 2.0 - dist / dist_thresh
            if score > best_score and (iou >= iou_thresh or dist < dist_thresh * 0.5):
                best_score = score
                best_idx = i

        if best_idx >= 0:
            matched_new_indices.add(best_idx)
            rec = records[best_idx]
            xywh = _bbox_to_xywh(rec.get("bbox"))
            if xywh:
                # Box pozisyonunu OCR çapasıyla güncelle (drift azalt)
                box.x, box.y, box.w, box.h = xywh
                box.features = None  # Feature'ları yenile
            box.text = str(rec.get("text") or box.text)

    unmatched = [records[i] for i in range(len(records)) if i not in matched_new_indices]
    return active_boxes, unmatched


def _add_new_boxes_from_records(
    records: list[dict[str, Any]],
    active_boxes: list[ActiveBox],
    next_id: int,
    frame_height: int,
    *,
    top_skip_ratio: float = HANDOFF_TOP_RATIO,
) -> tuple[list[ActiveBox], int]:
    """Eşleşmeyen OCR kayıtlarından yeni box'lar oluştur.
    Zaten üst bölgede olanları ekleme (zaten gidiyorlar).
    """
    for rec in records:
        xywh = _bbox_to_xywh(rec.get("bbox"))
        if xywh is None:
            continue
        x, y, w, h = xywh
        if w < 5 or h < 5:
            continue
        # Üst %15'te ise ekleme
        if y < frame_height * top_skip_ratio:
            continue
        new_box = ActiveBox(
            box_id=next_id,
            x=x, y=y, w=w, h=h,
            text=str(rec.get("text") or ""),
            confidence=float(rec.get("confidence") or 0.0),
        )
        active_boxes.append(new_box)
        next_id += 1
    return active_boxes, next_id


# ---------------------------------------------------------------------------
# Text-mask yardımcıları (Fix 2 & 3)
# ---------------------------------------------------------------------------
def _build_text_union_bbox(
    active_boxes: list[ActiveBox],
    frame_h: int,
    frame_w: int,
) -> tuple[int, int, int, int] | None:
    """Aktif box'ların birleşim (union) bounding box'unu döndür.

    Döner: (x1, y1, x2, y2) tamsayı koordinatları — frame sınırları içinde kırpılmış.
    Hiç box yoksa None döner.
    """
    if not active_boxes:
        return None
    x1 = min(int(b.x) for b in active_boxes)
    y1 = min(int(b.y) for b in active_boxes)
    x2 = max(int(b.x + b.w) for b in active_boxes)
    y2 = max(int(b.y + b.h) for b in active_boxes)
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(frame_w, x2)
    y2 = min(frame_h, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _apply_text_mask_to_strip(
    strip: np.ndarray,
    active_boxes: list[ActiveBox],
    strip_y_start: int,
    frame_w: int,
    dilation: int = TEXT_MASK_DILATION,
) -> np.ndarray:
    """Şeridi text-box maskesiyle maskele; kutu dışındaki pikseller sıfırlanır.

    strip          : (strip_h, frame_w, 3) BGR görüntü — ekranın alt şeridi
    active_boxes   : Aktif metin kutuları (frame koordinatlarında)
    strip_y_start  : strip'in kaynak görüntüdeki y başlangıç satırı (frame_h - strip_h)
    frame_w        : Görüntü genişliği
    dilation       : Maske genişletme miktarı (px)

    Döner: Maskelenmiş strip (aynı shape, siyah zemin üstünde yazı pikselleri).
    """
    strip_h = strip.shape[0]
    mask = np.zeros((strip_h, frame_w), dtype=np.uint8)

    for box in active_boxes:
        bx1 = max(0, int(box.x) - dilation)
        bx2 = min(frame_w, int(box.x + box.w) + dilation)
        by1 = int(box.y) - dilation
        by2 = int(box.y + box.h) + dilation
        # strip koordinatına çevir
        sy1 = max(0, by1 - strip_y_start)
        sy2 = min(strip_h, by2 - strip_y_start)
        if sy2 > sy1 and bx2 > bx1:
            mask[sy1:sy2, bx1:bx2] = 255

    if mask.max() == 0:
        # Hiçbir kutu strip'e düşmüyorsa (tüm kutu strip'in üstünde), tüm strip geçerli
        # Bu kaydırma gecikmesinden kaynaklanır; maskeleme atlanır
        return strip

    result = strip.copy()
    result[mask == 0] = 0  # Yazı dışı pikseller siyah
    return result


# ---------------------------------------------------------------------------
# Ana motor
# ---------------------------------------------------------------------------
def run_box_motion_track(
    frames: list[Path],
    *,
    output_dir: Path,
    paddle_engine,
    source_fps: float = 6.0,
    ocr_stride: int = OCR_STRIDE,
) -> BoxTrackResult:
    """
    BoxMotionTrack ana fonksiyonu.

    frames      : Sıralı frame dosya yolları listesi
    output_dir  : panorama.png, lines.json, debug.json yazılacak dizin
    paddle_engine: PaddleOcrEngine örneği (reuse edilir)
    source_fps  : Kaynak FPS (zaman damgası hesabı için)
    ocr_stride  : Her kaçıncı karede OCR çalıştırılır
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    started = perf_counter()

    if not frames:
        _empty_result(output_dir)
        return BoxTrackResult(
            panorama_path=output_dir / "panorama.png",
            text_lines=[],
            sections=[],
            debug={"error": "no_frames"},
        )

    # --- İlk kareyi oku, boyutu al ---
    first_img = _imread_safe(frames[0])
    if first_img is None:
        raise RuntimeError(f"İlk kare okunamadı: {frames[0]}")
    frame_h, frame_w = first_img.shape[:2]

    # --- Canvas hazırla ---
    # Tuval: frame genişliğinde, çok yüksek (dinamik büyür)
    canvas_slices: list[np.ndarray] = []  # Panoramaya eklenecek şeritler
    canvas_height_used: int = 0

    # --- Durum değişkenleri ---
    active_boxes: list[ActiveBox] = []
    next_box_id: int = 0
    cumulative_dy: float = 0.0
    prev_gray: np.ndarray | None = None

    # Statik faz için en iyi kare takibi
    static_phase_active: bool = False
    static_best_sharpness: float = -1.0
    static_best_frame: np.ndarray | None = None
    static_start_frame: int = 0
    static_frame_count: int = 0

    # Debug verileri
    per_frame_debug: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    current_section_start: int = 0
    current_section_type: str = "unknown"
    events: list[dict[str, Any]] = []

    # Panorama şeritleri: [(y_canvas_start, slice_img)]
    panorama_strips: list[tuple[int, np.ndarray]] = []

    def flush_static_block():
        """Statik bloğu tuvale ekle."""
        nonlocal static_phase_active, static_best_sharpness, static_best_frame
        nonlocal static_frame_count, canvas_height_used
        if static_best_frame is not None and static_frame_count >= STATIC_BLOCK_MIN_FRAMES:
            resized = cv2.resize(static_best_frame, (frame_w, frame_h))
            panorama_strips.append((canvas_height_used, resized.copy()))
            canvas_height_used += frame_h
            events.append({
                "type": "static_block_flushed",
                "y_canvas": canvas_height_used - frame_h,
                "frame_count": static_frame_count,
                "sharpness": round(static_best_sharpness, 2),
            })
        static_phase_active = False
        static_best_sharpness = -1.0
        static_best_frame = None
        static_frame_count = 0

    def add_section_break(frame_idx: int, reason: str):
        """Yeni bölüm başlat."""
        nonlocal current_section_start, current_section_type, canvas_height_used
        sections.append({
            "start_frame": current_section_start,
            "end_frame": frame_idx,
            "type": current_section_type,
        })
        # Panoramada boşluk bırak
        gap_height = max(10, frame_h // 8)
        blank = np.zeros((gap_height, frame_w, 3), dtype=np.uint8)
        panorama_strips.append((canvas_height_used, blank))
        canvas_height_used += gap_height
        events.append({
            "type": "section_break",
            "frame": frame_idx,
            "reason": reason,
            "y_canvas": canvas_height_used - gap_height,
        })
        current_section_start = frame_idx
        current_section_type = "unknown"

    # --- Kare-kare işleme ---
    for frame_idx, frame_path in enumerate(frames):
        img = _imread_safe(frame_path)
        if img is None:
            per_frame_debug.append({"frame": frame_idx, "error": "read_failed"})
            continue

        # Frame genişliğine normalize et
        if img.shape[1] != frame_w:
            img = cv2.resize(img, (frame_w, frame_h))

        cur_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # --- Cut / dissolve tespiti ---
        is_cut = False
        global_diff = 0.0
        if prev_gray is not None:
            global_diff = _global_frame_diff(prev_gray, cur_gray)
            if global_diff > CUT_GLOBAL_DIFF:
                is_cut = True
                events.append({
                    "type": "cut_detected",
                    "frame": frame_idx,
                    "global_diff": round(global_diff, 2),
                })

        # --- Seyrek OCR ---
        ocr_records: list[dict[str, Any]] = []
        do_ocr = (frame_idx % ocr_stride == 0) or is_cut or (len(active_boxes) == 0 and frame_idx > 0)
        if do_ocr and paddle_engine is not None:
            ts = frame_idx / source_fps
            try:
                raw_records = paddle_engine.recognize(
                    frame_path,
                    strategy="unified_detection",
                    timestamp_seconds=ts,
                )
                ocr_records = raw_records or []
            except Exception as exc:
                events.append({"type": "ocr_error", "frame": frame_idx, "error": str(exc)})

        # --- Cut/dissolve işle ---
        if is_cut:
            flush_static_block()
            add_section_break(frame_idx, f"cut_global_diff={global_diff:.1f}")
            active_boxes = []
            cumulative_dy = 0.0
            # Yeni seed
            active_boxes, next_box_id = _add_new_boxes_from_records(
                ocr_records, active_boxes, next_box_id, frame_h
            )
            prev_gray = cur_gray
            per_frame_debug.append({
                "frame": frame_idx,
                "event": "cut",
                "global_diff": round(global_diff, 2),
                "new_boxes": len(active_boxes),
            })
            continue

        # --- OCR sonuçlarıyla aktif box'ları güncelle ---
        if do_ocr and ocr_records:
            active_boxes, unmatched = _match_ocr_to_active_boxes(
                ocr_records, active_boxes
            )
            # Drift çapasını sadece drift kontrol döngüsünde yapalım (aşağıda)
            # Yeni box'ları ekle
            active_boxes, next_box_id = _add_new_boxes_from_records(
                unmatched, active_boxes, next_box_id, frame_h
            )

        # --- İlk kare ya da hiç box yok → seed at ---
        if frame_idx == 0 and not active_boxes and ocr_records:
            active_boxes, next_box_id = _add_new_boxes_from_records(
                ocr_records, active_boxes, next_box_id, frame_h
            )

        # --- Lucas-Kanade tracking (prev_gray varsa) ---
        box_dys: list[float] = []
        boxes_to_remove: list[int] = []

        if prev_gray is not None and active_boxes:
            for box in active_boxes:
                dx, dy, new_feats = _track_box_lk(prev_gray, cur_gray, box)
                if dx is None:
                    box.lost_frames += 1
                    if box.lost_frames > 3:
                        boxes_to_remove.append(box.box_id)
                    continue
                # Box pozisyonunu güncelle
                box.x += dx
                box.y += dy
                box.features = new_feats
                box.lost_frames = 0
                box.age += 1
                box_dys.append(dy)

        # Kaybolmuş box'ları temizle
        if boxes_to_remove:
            active_boxes = [b for b in active_boxes if b.box_id not in boxes_to_remove]

        # Handoff: üst %15'e giren box'ları düşür
        handoff_removed = []
        remaining_boxes = []
        for box in active_boxes:
            if box.y < frame_h * HANDOFF_TOP_RATIO:
                handoff_removed.append(box.box_id)
                events.append({
                    "type": "handoff",
                    "frame": frame_idx,
                    "box_id": box.box_id,
                    "box_y": round(box.y, 1),
                })
            else:
                remaining_boxes.append(box)
        active_boxes = remaining_boxes

        # Ani box kaybı tespiti (cut değilse de bölüm kırılması)
        if frame_idx > 0 and prev_gray is not None:
            prev_box_count = len(active_boxes) + len(boxes_to_remove) + len(handoff_removed)
            if prev_box_count > 3 and len(active_boxes) == 0:
                flush_static_block()
                add_section_break(frame_idx, "total_box_loss")
                cumulative_dy = 0.0

        # --- Konsensüs dy ---
        median_dy: float = 0.0
        if box_dys:
            median_dy = float(np.median(box_dys))

        # --- Drift çapası (her ANCHOR_EVERY karede) ---
        if frame_idx > 0 and frame_idx % ANCHOR_EVERY == 0 and do_ocr and ocr_records and active_boxes:
            # En alttaki aktif box'u referans al ve OCR ile senkronla
            bottom_boxes_sorted = sorted(active_boxes, key=lambda b: b.y + b.h, reverse=True)
            if bottom_boxes_sorted:
                ref_box = bottom_boxes_sorted[0]
                # O box'a uyan OCR kaydı var mı?
                for rec in ocr_records:
                    xywh = _bbox_to_xywh(rec.get("bbox"))
                    if xywh is None:
                        continue
                    rx, ry, rw, rh = xywh
                    cx1, cy1 = ref_box.x + ref_box.w / 2, ref_box.y + ref_box.h / 2
                    cx2, cy2 = rx + rw / 2, ry + rh / 2
                    dist = ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5
                    if dist < 40.0:
                        drift_correction = ry - ref_box.y
                        if abs(drift_correction) > 5.0:
                            ref_box.y = ry
                            ref_box.x = rx
                            ref_box.features = None
                            events.append({
                                "type": "drift_anchor",
                                "frame": frame_idx,
                                "correction": round(drift_correction, 2),
                            })
                        break

        # --- Panorama güncelle ---
        is_static = abs(median_dy) < STATIC_EPS

        # FIX 1: Text-gating — saf sahne karesi (hiç aktif box yok) → atla.
        # Statik faz YALNIZCA gerçek takip edilen metin kutusu varsa başlar.
        # box_dys boş → median_dy=0 → is_static=True olur ama bu "gerçek statik metin
        # kartı" değil, "tracking yok" anlamına gelir; her ikisini ayırt et.
        has_active_text = len(active_boxes) > 0

        if is_static:
            if not has_active_text:
                # Hiç metin kutusu izlenmiyor → bu kareyi tamamen atla
                # (sahne karesi ya da henüz seed alınmamış): panoramaya hiçbir şey ekleme
                per_frame_debug.append({
                    "frame": frame_idx,
                    "active_boxes": 0,
                    "box_dys": [],
                    "median_dy": round(median_dy, 3),
                    "cumulative_dy": round(cumulative_dy, 3),
                    "is_static": is_static,
                    "skipped": "no_active_boxes",
                    "global_diff": round(global_diff, 2),
                    "sharpness": None,
                })
                prev_gray = cur_gray
                continue

            # Statik faz — gerçek metin kutusu var
            if not static_phase_active:
                static_phase_active = True
                static_start_frame = frame_idx
                static_frame_count = 0
                static_best_sharpness = -1.0
                static_best_frame = None

            sharpness = _image_sharpness(cur_gray)
            if sharpness > static_best_sharpness:
                static_best_sharpness = sharpness
                # FIX 3: Tam kare yerine text-bölgesi kırpması kaydet.
                union_bbox = _build_text_union_bbox(active_boxes, frame_h, frame_w)
                if union_bbox is not None:
                    ux1, uy1, ux2, uy2 = union_bbox
                    # Tam frame boyutunda siyah tuval; yalnızca text bölgesi kopyalanır.
                    # Genişlik korunur → panorama assembly'de hizalama bozulmaz.
                    text_crop = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
                    text_crop[uy1:uy2, ux1:ux2] = img[uy1:uy2, ux1:ux2]
                    static_best_frame = text_crop
                else:
                    # Birleşim hesaplanamıyorsa tam kareyi kaydet (fallback)
                    static_best_frame = img.copy()
            static_frame_count += 1

        else:
            # Akan faz — statik bloğu varsa önce flush et
            if static_phase_active:
                flush_static_block()

            # FIX 1 (akan faz): metin kutusu yoksa bu kareyi atla.
            if not has_active_text:
                per_frame_debug.append({
                    "frame": frame_idx,
                    "active_boxes": 0,
                    "box_dys": [],
                    "median_dy": round(median_dy, 3),
                    "cumulative_dy": round(cumulative_dy, 3),
                    "is_static": is_static,
                    "skipped": "no_active_boxes_scroll",
                    "global_diff": round(global_diff, 2),
                    "sharpness": None,
                })
                prev_gray = cur_gray
                continue

            # Kümülatif ofseti güncelle
            cumulative_dy += median_dy

            # FIX 2: Şeridi text-maskesiyle filtrele; sahne pikselleri panoramaya girmesin.
            # dy pozitif → içerik yukarı kayıyor → alttan yeni içerik geliyor
            if abs(median_dy) >= MIN_FRAME_DIFF_FOR_STRIP:
                strip_h = max(1, int(abs(median_dy)))
                strip_h = min(strip_h, frame_h)
                strip_y_start = frame_h - strip_h
                # Ham şerit — ekranın alt kısmı
                strip_raw = img[strip_y_start:frame_h, :, :].copy()
                # Text-mask uygula: aktif box bölgesi dışındaki pikselleri sıfırla
                strip_masked = _apply_text_mask_to_strip(
                    strip_raw, active_boxes, strip_y_start, frame_w
                )
                panorama_strips.append((canvas_height_used, strip_masked))
                canvas_height_used += strip_h

            current_section_type = "scroll"

        # İlk karede hiç box yoksa tam kareyi EKLEME — sadece box varsa panoramaya gir.
        # (Eski kod sahne karelerini buradan ekliyordu; Fix 1 gereği kaldırıldı.)
        # Gerektiğinde ilk OCR seed sonrası box gelince zaten işlenecek.

        # --- Per-frame debug ---
        per_frame_debug.append({
            "frame": frame_idx,
            "active_boxes": len(active_boxes),
            "box_dys": [round(d, 3) for d in box_dys],
            "median_dy": round(median_dy, 3),
            "cumulative_dy": round(cumulative_dy, 3),
            "is_static": is_static,
            "global_diff": round(global_diff, 2),
            "sharpness": round(_image_sharpness(cur_gray), 1) if is_static else None,
        })

        prev_gray = cur_gray

    # --- Son statik bloğu flush et ---
    flush_static_block()
    sections.append({
        "start_frame": current_section_start,
        "end_frame": len(frames),
        "type": current_section_type,
    })

    # --- Panoramayı birleştir ---
    total_height = min(canvas_height_used, MAX_CANVAS_HEIGHT)
    if total_height < 10:
        total_height = frame_h  # fallback

    panorama = np.zeros((total_height, frame_w, 3), dtype=np.uint8)

    for (y_start, strip) in panorama_strips:
        if y_start >= total_height:
            break
        sh = strip.shape[0]
        sw = strip.shape[1]
        y_end = min(y_start + sh, total_height)
        actual_h = y_end - y_start
        if actual_h <= 0:
            continue
        # Genişlik uyumu
        if sw != frame_w:
            strip_resized = cv2.resize(strip, (frame_w, actual_h))
        else:
            strip_resized = strip[:actual_h]
        panorama[y_start:y_end, :] = strip_resized

    # --- OCR on panorama for text_lines ---
    panorama_path = output_dir / "panorama.png"
    _imwrite_safe(panorama_path, panorama)

    text_lines: list[dict[str, Any]] = []
    if paddle_engine is not None and total_height > 10:
        try:
            pano_records = paddle_engine.recognize(
                panorama_path,
                strategy="panorama_ocr",
                timestamp_seconds=None,
            )
            for rec in (pano_records or []):
                text = str(rec.get("text") or rec.get("normalized_text") or "")
                if text:
                    text_lines.append({
                        "text": text,
                        "bbox": rec.get("bbox"),
                        "confidence": rec.get("confidence"),
                    })
            # Yukarıdan aşağıya sırala
            text_lines.sort(key=lambda r: (r["bbox"][1] if r.get("bbox") and len(r["bbox"]) >= 2 else 0))
        except Exception as exc:
            events.append({"type": "panorama_ocr_error", "error": str(exc)})

    # --- debug.json ---
    debug_data: dict[str, Any] = {
        "total_frames": len(frames),
        "frame_size": [frame_w, frame_h],
        "canvas_height_used": canvas_height_used,
        "panorama_height": total_height,
        "panorama_width": frame_w,
        "strip_count": len(panorama_strips),
        "section_count": len(sections),
        "event_count": len(events),
        "runtime_sec": round(perf_counter() - started, 3),
        "events": events,
        "per_frame": per_frame_debug,
    }

    with open(output_dir / "debug.json", "w", encoding="utf-8") as fh:
        json.dump(debug_data, fh, ensure_ascii=False, indent=2)

    # --- lines.json ---
    lines_data: dict[str, Any] = {
        "panorama_path": str(panorama_path),
        "line_count": len(text_lines),
        "lines": text_lines,
        "sections": sections,
    }
    with open(output_dir / "lines.json", "w", encoding="utf-8") as fh:
        json.dump(lines_data, fh, ensure_ascii=False, indent=2)

    return BoxTrackResult(
        panorama_path=panorama_path,
        text_lines=text_lines,
        sections=sections,
        debug=debug_data,
    )


def _empty_result(output_dir: Path) -> None:
    blank = np.zeros((100, CANVAS_WIDTH, 3), dtype=np.uint8)
    _imwrite_safe(output_dir / "panorama.png", blank)
    for name in ("lines.json", "debug.json"):
        with open(output_dir / name, "w", encoding="utf-8") as fh:
            json.dump({"error": "no_frames"}, fh)
