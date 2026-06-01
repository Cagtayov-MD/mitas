"""POC β — Band-Bazlı Motion Füzyon Motoru.

Fikir (§29 duvarı çözümü):
  Ekranı K yatay banda böl. Her bandı zaman boyunca ayrı sınıfla:
    - STATİK: |median_dy| < EPS tüm segment boyunca → en keskin kareyi kırp.
    - SCROLL: tutarlı dikey kayma → pushbroom slit-scan ile panorama dik.
  Sonra her şeyi Paddle ile OCR'la → tek lines.json (bant/tip etiketli).

cv2 Turkish-İ tuzağı: imread/imwrite YERİNE fromfile+imdecode / imencode+tofile.
"""

from __future__ import annotations

import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

# Windows console cp1254 gibi dar kodlamalar Unicode karakterlerde patlıyor.
# stdout/stderr'i UTF-8'e sabitle.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
K_BANDS: int = 8               # Yatay band sayısı (gerekirse ayarlanır)
STATIC_EPS: float = 1.5        # |median_dy| < bu px/kare → statik bant
SCROLL_CONSISTENT_FRAC: float = 0.5  # Kaç fraksiyonda consistent scroll olmalı
STATIC_MIN_FRAMES: int = 5     # Statik karar için min kare
SCROLL_MIN_FRAMES: int = 10    # Scroll karar için min kare
SLIT_H: int = 6                # Scroll panorama için şerit yüksekliği (px)
SHARP_WIN: int = 3             # Keskinlik puanlamasında Laplacian kernel
OCR_DILATION: int = 12         # Metin maskesi dilatasyon (px)
PHASE_STRIDE: int = 5          # Faz-korelasyon stride (her N karede bir)
MAX_CANVAS_H: int = 40000      # Scroll tuval güvenlik limiti
MIN_BAND_TEXT_RATIO: float = 0.0005  # Bandin text icerdigini kabul icin min oran (dusuk esik)


# ---------------------------------------------------------------------------
# I/O yardımcıları
# ---------------------------------------------------------------------------
def _read(path: Path) -> np.ndarray | None:
    try:
        buf = np.fromfile(str(path), np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _read_gray(path: Path) -> np.ndarray | None:
    try:
        buf = np.fromfile(str(path), np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
        return img.astype(np.float32) if img is not None else None
    except Exception:
        return None


def _write(path: Path, img: np.ndarray) -> bool:
    try:
        ok, buf = cv2.imencode(".png", img)
        if ok:
            buf.tofile(str(path))
            return True
    except Exception:
        pass
    return False


def _sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray.astype(np.uint8), cv2.CV_64F).var())


def _hann2d(h: int, w: int) -> np.ndarray:
    return (
        np.hanning(h).reshape(-1, 1).astype(np.float32)
        * np.hanning(w).reshape(1, -1).astype(np.float32)
    )


def _phase_corr_dy(g1: np.ndarray, g2: np.ndarray, hann: np.ndarray) -> float | None:
    """İki gri banttan dikey displacement döndürür. Başarısızlıkta None."""
    try:
        # Bant çok küçükse faz-korelasyon güvenilmez
        if g1.shape[0] < 8 or g1.shape[1] < 8:
            return None
        (_, dy), rsp = cv2.phaseCorrelate(g1 * hann, g2 * hann)
        # Düşük response güvenilmez
        if abs(rsp) < 0.03:
            return None
        return float(dy)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Bant dy serisi hesaplama
# ---------------------------------------------------------------------------
def compute_band_dy_series(
    frames: list[Path],
    fh: int,
    fw: int,
    K: int,
    stride: int = PHASE_STRIDE,
) -> list[list[float]]:
    """Her bant için dy zaman serisi döndürür.

    Returns:
        list[list[float]]: band_idx → [dy_0, dy_1, ...] (sadece geçerli ölçümler)
    """
    band_h = fh // K
    hann_list = [_hann2d(band_h, fw) for _ in range(K)]
    band_dy: list[list[float]] = [[] for _ in range(K)]

    prev_bands: list[np.ndarray | None] = [None] * K

    for i, fp in enumerate(frames):
        if i % stride != 0:
            continue

        gray = _read_gray(fp)
        if gray is None:
            prev_bands = [None] * K
            continue

        # Boyut kontrolü
        if gray.shape != (fh, fw):
            gray = cv2.resize(gray, (fw, fh), interpolation=cv2.INTER_AREA).astype(np.float32)

        for b in range(K):
            y0 = b * band_h
            y1 = min(fh, y0 + band_h)
            curr = gray[y0:y1, :]

            if prev_bands[b] is not None:
                dy = _phase_corr_dy(prev_bands[b], curr, hann_list[b])
                if dy is not None:
                    band_dy[b].append(dy)

            prev_bands[b] = curr

    return band_dy


# ---------------------------------------------------------------------------
# Bant sınıflandırma
# ---------------------------------------------------------------------------
def classify_bands(
    band_dy: list[list[float]],
    static_eps: float = STATIC_EPS,
    scroll_consistent_frac: float = SCROLL_CONSISTENT_FRAC,
    static_min: int = STATIC_MIN_FRAMES,
    scroll_min: int = SCROLL_MIN_FRAMES,
) -> list[str]:
    """Her bant için 'static', 'scroll' veya 'unknown' döndürür."""
    K = len(band_dy)
    labels: list[str] = []

    for b in range(K):
        dys = band_dy[b]
        n = len(dys)

        if n < 2:
            labels.append("unknown")
            continue

        arr = np.array(dys, dtype=np.float64)
        median_abs = float(np.median(np.abs(arr)))

        # Statik: medyan mutlak dy küçük
        if median_abs < static_eps:
            if n >= static_min:
                labels.append("static")
            else:
                labels.append("unknown")
            continue

        # Scroll: tutarlı yön?
        # Bir yönde (negatif veya pozitif) yeterince çok ölçüm var mı?
        n_neg = np.sum(arr < -static_eps)
        n_pos = np.sum(arr > static_eps)
        dominant_frac = max(n_neg, n_pos) / max(1, n)

        if dominant_frac >= scroll_consistent_frac and n >= scroll_min:
            labels.append("scroll")
        else:
            labels.append("unknown")

    return labels


# ---------------------------------------------------------------------------
# Statik bant: en keskin kareyi seç, kırp, kaydet
# ---------------------------------------------------------------------------
def process_static_band(
    frames: list[Path],
    fh: int,
    fw: int,
    band_idx: int,
    K: int,
    output_dir: Path,
    prefix: str = "static_",
    stride: int = 5,
    n_segments: int = 5,
) -> dict[str, Any]:
    """Bant icin en keskin kareyi N zaman segmentinden bulup dikey stack uretir.

    n_segments: Video tüm uzunlugu N parcaya bolunur; her parca icindeki
    en keskin metin-içeren kare alinir. Boylece hem ilk hem son kisimdan
    ornek alinir (kadro farkli zamandalarda, sarki farkli zamanlarda).
    """
    band_h = fh // K
    y0 = band_idx * band_h
    y1 = min(fh, y0 + band_h)

    n_frames = len(frames)
    seg_len = max(1, n_frames // n_segments)

    # Her segmentten en keskin metin karesi
    segment_bests: list[tuple[int, float, np.ndarray]] = []  # (idx, sharp, img)

    for seg in range(n_segments):
        seg_start = seg * seg_len
        seg_end = min(n_frames, (seg + 1) * seg_len)

        best_sharp = -1.0
        best_img = None
        best_idx = -1

        for i in range(seg_start, seg_end, stride):
            fp = frames[i]
            img = _read(fp)
            if img is None:
                continue
            if img.shape[:2] != (fh, fw):
                img = cv2.resize(img, (fw, fh), interpolation=cv2.INTER_AREA)
            crop = img[y0:y1, :]
            gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

            # Metin var mi? (parlak piksel yuzdesi)
            bright_frac = np.mean(gray_crop > 180)
            if bright_frac < MIN_BAND_TEXT_RATIO:
                continue

            sharp = _sharpness(gray_crop.astype(np.float32))
            if sharp > best_sharp:
                best_sharp = sharp
                best_img = crop.copy()
                best_idx = i

        if best_img is not None:
            segment_bests.append((best_idx, best_sharp, best_img))

    result = {
        "band_idx": band_idx,
        "type": "static",
        "y0": y0,
        "y1": y1,
        "best_frame_idx": segment_bests[0][0] if segment_bests else -1,
        "best_sharpness": round(segment_bests[0][1] if segment_bests else -1.0, 1),
        "has_text_frame_count": len(segment_bests),
        "n_segments_with_text": len(segment_bests),
    }

    if segment_bests:
        # Her segmentten gelen en iyi kareyi dikey olarak birlestir
        # Bu N*60px yuksekliginde bir grid verir
        stack_imgs = [item[2] for item in segment_bests]
        stacked = np.vstack(stack_imgs)
        out_path = output_dir / f"{prefix}band{band_idx}.png"
        _write(out_path, stacked)
        result["crop_path"] = str(out_path)
        result["stack_height"] = stacked.shape[0]
        result["segment_frame_indices"] = [item[0] for item in segment_bests]
    else:
        result["crop_path"] = None

    return result


# ---------------------------------------------------------------------------
# Scroll bant: pushbroom slit-scan
# ---------------------------------------------------------------------------
def process_scroll_band(
    frames: list[Path],
    fh: int,
    fw: int,
    band_idx: int,
    K: int,
    output_dir: Path,
) -> dict[str, Any]:
    """Scroll bant için slit-scan panorama üretir."""
    band_h = fh // K
    y0 = band_idx * band_h
    y1 = min(fh, y0 + band_h)

    hann = _hann2d(band_h, fw)
    canvas = np.zeros((MAX_CANVAS_H, fw, 3), dtype=np.uint8)
    cy = 0

    slit_half = max(1, SLIT_H // 2)
    band_mid = (y1 - y0) // 2
    slit_top = max(0, band_mid - slit_half)
    slit_bot = min(band_h, band_mid + slit_half)

    prev_gray: np.ndarray | None = None
    frames_used = 0
    first_frame = True

    for fp in frames:
        img = _read(fp)
        if img is None:
            continue
        if img.shape[:2] != (fh, fw):
            img = cv2.resize(img, (fw, fh), interpolation=cv2.INTER_AREA)

        crop = img[y0:y1, :]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)

        # Metin yoksa atla
        bright_frac = np.mean(gray > 180)
        if bright_frac < MIN_BAND_TEXT_RATIO:
            prev_gray = gray
            continue

        if first_frame:
            # İlk metin çerçevesi: tam band yaz
            h_write = min(band_h, MAX_CANVAS_H - cy)
            canvas[cy:cy + h_write, :] = crop[:h_write, :]
            cy += h_write
            first_frame = False
        else:
            # Pushbroom: merkez şerit ekle
            strip = crop[slit_top:slit_bot, :]
            rows = slit_bot - slit_top
            h_write = min(rows, MAX_CANVAS_H - cy)
            if h_write > 0:
                canvas[cy:cy + h_write, :] = strip[:h_write, :]
                cy += h_write

        prev_gray = gray
        frames_used += 1

        if cy >= MAX_CANVAS_H - 10:
            break

    result = {
        "band_idx": band_idx,
        "type": "scroll",
        "y0": y0,
        "y1": y1,
        "frames_used": frames_used,
        "panorama_height": cy,
    }

    if cy > 0:
        panorama = canvas[:cy, :].copy()
        out_path = output_dir / f"scroll_band{band_idx}_panorama.png"
        _write(out_path, panorama)
        result["panorama_path"] = str(out_path)
        print(f"  [BandMotion] Scroll band {band_idx} panorama: {fw}x{cy}px -> {out_path}")
    else:
        result["panorama_path"] = None

    return result


# ---------------------------------------------------------------------------
# Tam bant tarama: N frame araliginda bant kisimlarini dikey birles, OCR yap
# ---------------------------------------------------------------------------
def scan_band_frames(
    frames: list[Path],
    fh: int,
    fw: int,
    y0: int,
    y1: int,
    output_dir: Path,
    tag: str,
    stride: int = 30,
) -> Path | None:
    """Belirli y araliginda ardisik framelerin kesimleri dikey birlestirir.

    Bu yaklaşım hem scroll hem de kareli (kadro ismi gibi) icerik icin calisir:
    stripe-by-stripe degil, tam bant yuksekligi korunur.
    """
    stack = []
    for i, fp in enumerate(frames):
        if i % stride != 0:
            continue
        img = _read(fp)
        if img is None:
            continue
        if img.shape[:2] != (fh, fw):
            img = cv2.resize(img, (fw, fh), interpolation=cv2.INTER_AREA)
        crop = img[y0:y1, :]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        bright_frac = np.mean(gray > 160)
        if bright_frac < MIN_BAND_TEXT_RATIO * 0.5:
            continue
        stack.append(crop)

    if not stack:
        return None

    combined = np.vstack(stack)
    out_path = output_dir / f"scan_{tag}.png"
    _write(out_path, combined)
    print(f"  [BandMotion] Frame scan {tag}: {len(stack)} kare, {combined.shape[1]}x{combined.shape[0]}px")
    return out_path


# ---------------------------------------------------------------------------
# OCR yardımcısı (Paddle tiled)
# ---------------------------------------------------------------------------
def _ocr_image(
    img_path: Path | None,
    paddle_engine: Any,
    strategy: str = "scroll_canvas_ocr",
    y_offset: int = 0,
    source_tag: str = "",
) -> list[dict]:
    """Tek PNG'yi OCR'la. Büyük görüntüler için tile."""
    if img_path is None or not img_path.exists():
        return []

    PADDLE_MAX_H = 3800
    TILE_OVERLAP = 80

    # Boyut
    buf = np.fromfile(str(img_path), np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        return []
    ph, pw = img.shape[:2]

    lines: list[dict] = []

    if ph <= PADDLE_MAX_H:
        try:
            recs = paddle_engine.recognize(img_path, strategy=strategy, timestamp_seconds=None)
        except Exception as e:
            print(f"  [BandMotion] OCR error {img_path.name}: {e}", file=sys.stderr)
            return []
        for r in recs:
            txt = r.get("text", "").strip()
            if not txt:
                continue
            bbox = r.get("bbox")
            if bbox and len(bbox) >= 4:
                adj_bbox = [bbox[0], bbox[1] + y_offset, bbox[2], bbox[3]]
            else:
                adj_bbox = bbox
            lines.append({
                "text": txt,
                "bbox": adj_bbox,
                "confidence": r.get("confidence"),
                "source": source_tag,
            })
    else:
        # Tiled
        tile_dir = img_path.parent / f"_tiles_{img_path.stem}"
        tile_dir.mkdir(exist_ok=True)
        seen: set[str] = set()
        y = 0
        tile_idx = 0
        while y < ph:
            y_end = min(ph, y + PADDLE_MAX_H)
            tile = img[y:y_end, :]
            tile_path = tile_dir / f"tile_{tile_idx:04d}.png"
            ok, tbuf = cv2.imencode(".png", tile)
            if ok:
                tbuf.tofile(str(tile_path))
            try:
                recs = paddle_engine.recognize(tile_path, strategy=strategy, timestamp_seconds=None)
            except Exception as e:
                print(f"  [BandMotion] Tile OCR error {tile_path.name}: {e}", file=sys.stderr)
                recs = []
            for r in recs:
                txt = r.get("text", "").strip()
                if not txt:
                    continue
                bbox = r.get("bbox")
                if bbox and len(bbox) >= 4:
                    adj_bbox = [bbox[0], bbox[1] + y + y_offset, bbox[2], bbox[3]]
                else:
                    adj_bbox = bbox
                key = f"{txt}|{round(r.get('confidence', 0), 2)}"
                if key not in seen:
                    seen.add(key)
                    lines.append({
                        "text": txt,
                        "bbox": adj_bbox,
                        "confidence": r.get("confidence"),
                        "source": source_tag,
                    })
            tile_idx += 1
            y = y_end - TILE_OVERLAP
            if y_end >= ph:
                break

    return lines


# ---------------------------------------------------------------------------
# Ana motor
# ---------------------------------------------------------------------------
@dataclass
class BandMotionResult:
    lines_path: Path
    bands_debug_path: Path
    all_lines: list[dict] = field(default_factory=list)
    band_infos: list[dict] = field(default_factory=list)


def run_band_motion(
    frames: list[Path],
    *,
    output_dir: Path,
    paddle_engine: Any,
    K: int = K_BANDS,
    phase_stride: int = PHASE_STRIDE,
    static_eps: float = STATIC_EPS,
    source_fps: float = 6.0,
) -> BandMotionResult:
    """Bant-bazlı motion füzyon motoru.

    Args:
        frames: Sıralı frame yolları.
        output_dir: Çıktı dizini.
        paddle_engine: PaddleOcrEngine örneği.
        K: Bant sayısı.
        phase_stride: Faz-korelasyon atlama sayısı.
        static_eps: |median_dy| < bu → statik.
        source_fps: Kaynak FPS.

    Returns:
        BandMotionResult
    """
    t0 = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)

    n = len(frames)
    if n == 0:
        raise ValueError("Frame listesi bos.")

    # Frame boyutu
    fh = fw = None
    for fp in frames:
        img0 = _read(fp)
        if img0 is not None:
            fh, fw = img0.shape[:2]
            break
    if fh is None:
        raise RuntimeError("Hicbir frame okunamadi.")
    print(f"  [BandMotion] Frame boyutu: {fw}x{fh}, K={K}, frame sayisi: {n}")

    band_h = fh // K
    print(f"  [BandMotion] Bant yuksekligi: {band_h}px")

    # ── 1. Bant dy serileri ──────────────────────────────────────────────────
    print(f"  [BandMotion] Faz-korelasyon hesaplaniyor (stride={phase_stride})...")
    t1 = perf_counter()
    band_dy = compute_band_dy_series(frames, fh, fw, K, stride=phase_stride)
    print(f"  [BandMotion] Faz-korelasyon tamam ({(perf_counter()-t1):.1f}s)")

    for b in range(K):
        dys = band_dy[b]
        if dys:
            med = float(np.median(np.abs(dys)))
            print(f"    Band {b} (y={b*band_h}-{min(fh,(b+1)*band_h)}): n={len(dys)}, |median_dy|={med:.2f}")
        else:
            print(f"    Band {b}: veri yok")

    # ── 2. Sınıflandırma ────────────────────────────────────────────────────
    labels = classify_bands(
        band_dy,
        static_eps=static_eps,
        scroll_consistent_frac=SCROLL_CONSISTENT_FRAC,
        static_min=STATIC_MIN_FRAMES,
        scroll_min=SCROLL_MIN_FRAMES,
    )
    print(f"  [BandMotion] Bant etiketleri: {list(enumerate(labels))}")  # ASCII safe

    # ── 3. Her bant işle ────────────────────────────────────────────────────
    band_infos: list[dict] = []
    ocr_jobs: list[dict] = []  # {path, y_offset, source_tag}

    for b, label in enumerate(labels):
        y0 = b * band_h
        dy_list = band_dy[b]
        med_abs = float(np.median(np.abs(dy_list))) if dy_list else 0.0

        base_info = {
            "band_idx": b,
            "label": label,
            "y0": y0,
            "y1": min(fh, y0 + band_h),
            "dy_count": len(dy_list),
            "dy_median_abs": round(med_abs, 3),
            "dy_sample": [round(d, 2) for d in dy_list[:10]],
        }

        if label == "static":
            print(f"  [BandMotion] Band {b}: STATIK -> en keskin kare seciliyor...")
            info = process_static_band(frames, fh, fw, b, K, output_dir)
            base_info.update(info)
            if info.get("crop_path"):
                ocr_jobs.append({
                    "path": Path(info["crop_path"]),
                    "y_offset": 0,
                    "source_tag": f"static_band{b}",
                    "strategy": "unified_detection",
                })

        elif label in ("scroll", "unknown"):
            # unknown bantlar da scroll gibi isle: eger global scroll varsa
            # tum aktif bantlar birer miktar hareket eder, bu normal
            effective_label = "scroll"
            base_info["label"] = effective_label
            print(f"  [BandMotion] Band {b}: {label.upper()} -> scroll slit-scan panorama uretiliyor...")
            info = process_scroll_band(frames, fh, fw, b, K, output_dir)
            base_info.update(info)
            if info.get("panorama_path"):
                ocr_jobs.append({
                    "path": Path(info["panorama_path"]),
                    "y_offset": 0,
                    "source_tag": f"scroll_band{b}",
                    "strategy": "scroll_canvas_ocr",
                })
            # AYRICA: frame-by-frame tam bant taramasi da OCR'la
            # Scroll slit-scan dar serit aliyor (6px), kadro isimleri (~30px) kaciyor.
            # Frame taramasi tum frame yuksekligini (band_h) korur, bu yuzden
            # kirmizi arka plandaki beyaz isimler de yakalanir.
            print(f"  [BandMotion] Band {b}: frame taramasi OCR...")
            y0_band = b * (fh // K)
            y1_band = min(fh, y0_band + (fh // K))
            scan_path = scan_band_frames(
                frames, fh, fw, y0_band, y1_band, output_dir, f"b{b}", stride=20
            )
            if scan_path is not None:
                ocr_jobs.append({
                    "path": scan_path,
                    "y_offset": 0,
                    "source_tag": f"framescan_band{b}",
                    "strategy": "scroll_canvas_ocr",
                })

        else:
            print(f"  [BandMotion] Band {b}: diger etiket {label!r}, atlaniyor.")

        band_infos.append(base_info)

    # ── 4. OCR ─────────────────────────────────────────────────────────────
    all_lines: list[dict] = []
    print(f"  [BandMotion] OCR basliyor, {len(ocr_jobs)} is var...")
    for job in ocr_jobs:
        tag = job["source_tag"]
        path = job["path"]
        print(f"    OCR: {tag} ({path.name})...")
        t_o = perf_counter()
        lines = _ocr_image(
            path,
            paddle_engine,
            strategy=job["strategy"],
            y_offset=job.get("y_offset", 0),
            source_tag=tag,
        )
        print(f"    OCR: {tag} -> {len(lines)} satir ({(perf_counter()-t_o):.1f}s)")
        all_lines.extend(lines)

    # ── 5. bands_debug.json ─────────────────────────────────────────────────
    debug = {
        "K": K,
        "frame_count": n,
        "band_h_px": band_h,
        "frame_size": [fw, fh],
        "phase_stride": phase_stride,
        "static_eps": static_eps,
        "bands": band_infos,
        "runtime_sec": round(perf_counter() - t0, 2),
    }
    debug_path = output_dir / "bands_debug.json"
    debug_path.write_text(json.dumps(debug, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 6. lines.json ───────────────────────────────────────────────────────
    lines_path = output_dir / "lines.json"
    lines_path.write_text(
        json.dumps({
            "line_count": len(all_lines),
            "lines": all_lines,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"  [BandMotion] Toplam OCR satiri: {len(all_lines)}")
    print(f"  [BandMotion] lines.json: {lines_path}")
    print(f"  [BandMotion] bands_debug.json: {debug_path}")
    print(f"  [BandMotion] Toplam sure: {(perf_counter()-t0):.1f}s")

    return BandMotionResult(
        lines_path=lines_path,
        bands_debug_path=debug_path,
        all_lines=all_lines,
        band_infos=band_infos,
    )
