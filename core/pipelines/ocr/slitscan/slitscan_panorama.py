"""SlitScan Panorama Engine — Çağatay'ın faz-korelasyon + pushbroom mozaik motoru.

Algoritma (PRENSIPLER.md §4 — saf pushbroom):
  1. TEXT-GATED seyrek OCR (stride=ocr_stride) → metin maskesi, has_text flag.
  2. Ardışık metin karesi çifti arasında faz-korelasyon (metin maskeli) → dy.
  3. Kümülatif dikey ofset biriktirilir (scroll yönü).
  4. Her metin içeren kare için:
     - |dy_smoothed| >= SLIT_MIN_DY → şerit (pushbroom): kareden orta bant alıp
       tuvaldeki yazma konumuna yapıştır; yazma konumu += strip_px ilerler.
     - |dy_smoothed| < SLIT_MIN_DY (statik) → blok: bu karenin belirtilen
       statik blok bölümünde görünürlüğü güncellenir, tuval ilerlemez.
  5. Metin içermeyen kareler atlanır (sahne karesi gizleme).
  6. Cut algılama (düşük faz-korelasyon gücü + yüksek global diff):
     tuvale boşluk bırak; kümülatif ofset sıfırla.
  7. Scroll modu: tuvale ardışık strip ekler. Şerit yüksekliği = sabit SLIT_H
     (her kare). Bu sayede scroll hızına bakılmaksızın her kare eşit katkı sağlar
     ve toplam panorama yüksekliği = metin kare sayısı × SLIT_H + boşluklar
     olur (öngörülebilir, ghost-free).
  8. Statik mod: ardışık statik kare bloğu → en keskin kareyi panoramaya tek
     tam blok olarak yaz (STATIC_BLOCK_MIN_FRAMES var olduğunda).
  9. Final OCR: panorama.png üzerinde tek paddle OCR.

cv2 Turkish-İ tuzağı: imread/imwrite YERİNE fromfile+imdecode / imencode+tofile.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
STATIC_EPS: float = 0.8          # |dy_smoothed| < bu px → statik
CUT_RESPONSE_MIN: float = 0.04   # Faz-korelasyon gücü bu altında → şüpheli cut
CUT_GLOBAL_DIFF: float = 40.0    # Ortalama piksel farkı bu px üstünde → cut
GAP_HEIGHT: int = 20             # Cut/bölüm arası boşluk yüksekliği (piksel)
GAP_GRAY: int = 40               # Boşluk rengi
SLIT_H: int = 8                  # Scroll modunda her kareden alınan şerit yüksekliği (piksel)
STATIC_BLOCK_MIN: int = 6        # Statik blok için asgari kare sayısı
DRIFT_N: int = 9                 # Drift yumuşatma medyan penceresi
OCR_DILATION: int = 15           # Metin maskesi dilatasyon (piksel)
MIN_TEXT_RATIO: float = 0.004    # Minimum metin alan oranı (kare geçerli sayılmak için)
MAX_CANVAS_H: int = 40000        # Güvenlik limiti


# ---------------------------------------------------------------------------
# Veri yapıları
# ---------------------------------------------------------------------------
@dataclass
class SlitScanResult:
    panorama_path: Path
    text_lines: list[dict[str, Any]]
    sections: list[dict[str, Any]]
    debug: dict[str, Any]


# ---------------------------------------------------------------------------
# I/O yardımcıları
# ---------------------------------------------------------------------------
def _read(path: Path) -> np.ndarray | None:
    try:
        buf = np.fromfile(str(path), np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
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


# ---------------------------------------------------------------------------
# Görüntü işleme
# ---------------------------------------------------------------------------
def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def _sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _hann2d(h: int, w: int) -> np.ndarray:
    return (
        np.hanning(h).reshape(-1, 1).astype(np.float32)
        * np.hanning(w).reshape(1, -1).astype(np.float32)
    )


def _phase_corr(g1: np.ndarray, g2: np.ndarray, hann: np.ndarray) -> tuple[float, float, float]:
    try:
        (dx, dy), rsp = cv2.phaseCorrelate(
            g1.astype(np.float32) * hann,
            g2.astype(np.float32) * hann,
        )
        return float(dx), float(dy), float(rsp)
    except Exception:
        return 0.0, 0.0, 0.0


def _gdiff(g1: np.ndarray, g2: np.ndarray) -> float:
    return float(np.mean(np.abs(g1.astype(np.float32) - g2.astype(np.float32))))


def _build_mask(shape: tuple[int, int], recs: list[dict], dilation: int) -> np.ndarray | None:
    h, w = shape
    mask = np.zeros((h, w), dtype=np.uint8)
    for r in recs:
        b = r.get("bbox")
        if b is None or len(b) < 4:
            continue
        x, y, bw, bh = (int(round(v)) for v in b[:4])
        x1, y1 = max(0, x - dilation), max(0, y - dilation)
        x2, y2 = min(w, x + bw + dilation), min(h, y + bh + dilation)
        mask[y1:y2, x1:x2] = 255
    return mask if mask.max() > 0 else None


def _masked(gray: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    if mask is None:
        return gray
    out = np.zeros_like(gray)
    out[mask > 0] = gray[mask > 0]
    return out


def _text_ratio(mask: np.ndarray | None, total: int) -> float:
    if mask is None:
        return 0.0
    return float(np.count_nonzero(mask)) / max(1, total)


def _med(buf: list[float]) -> float:
    return float(np.median(buf)) if buf else 0.0


# ---------------------------------------------------------------------------
# Sparse OCR
# ---------------------------------------------------------------------------
def _sparse_ocr(
    frames: list[Path],
    engine: Any,
    stride: int,
    fps: float,
) -> dict[int, list[dict]]:
    cache: dict[int, list[dict]] = {}
    for i in range(0, len(frames), stride):
        try:
            cache[i] = engine.recognize(
                frames[i],
                strategy="unified_detection",
                timestamp_seconds=i / max(fps, 1.0),
            )
        except Exception as e:
            print(f"  [OCR-warn] frame {i}: {e}", file=sys.stderr)
            cache[i] = []
    return cache


def _get_recs(idx: int, cache: dict[int, list[dict]], stride: int) -> list[dict]:
    return cache.get((idx // stride) * stride, [])


# ---------------------------------------------------------------------------
# Ana motor
# ---------------------------------------------------------------------------
def run_slitscan_panorama(
    frames: list[Path],
    *,
    output_dir: Path,
    paddle_engine: Any,
    source_fps: float = 6.0,
    ocr_stride: int = 8,
) -> SlitScanResult:
    """Slit-scan (pushbroom) + faz-korelasyon panorama motoru.

    Args:
        frames: Sıralı frame yolları.
        output_dir: panorama.png + JSON çıktıları için dizin.
        paddle_engine: PaddleOcrEngine örneği (final OCR + sparse OCR).
        source_fps: Kaynak FPS.
        ocr_stride: Seyrek OCR adım sayısı.

    Returns:
        SlitScanResult(panorama_path, text_lines, sections, debug)
    """
    t0 = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)

    n = len(frames)
    if n == 0:
        raise ValueError("Kare listesi bos.")

    # ── 1. Seyrek OCR ─────────────────────────────────────────────────────
    print(f"  [SlitScan] Sparse OCR (stride={ocr_stride}) on {n} frames...")
    t_ocr = perf_counter()
    cache = _sparse_ocr(frames, paddle_engine, ocr_stride, source_fps)
    n_ocr = sum(1 for v in cache.values() if v)
    print(f"  [SlitScan] OCR done ({perf_counter()-t_ocr:.1f}s). Frames with text: {n_ocr}/{len(cache)}")

    all_recs: list[list[dict]] = [_get_recs(i, cache, ocr_stride) for i in range(n)]
    has_any = any(r for r in all_recs)

    # ── 2. Kare boyutu ────────────────────────────────────────────────────
    fh = fw = None
    for fp in frames:
        img0 = _read(fp)
        if img0 is not None:
            fh, fw = img0.shape[:2]
            break
    if fh is None:
        raise RuntimeError("No frame could be read.")
    print(f"  [SlitScan] Frame size: {fw}x{fh}")

    hann = _hann2d(fh, fw)
    total_px = fh * fw

    # ── 3. Canvas ─────────────────────────────────────────────────────────
    # Pre-allocate tall canvas; crop at end.
    canvas = np.zeros((MAX_CANVAS_H, fw, 3), dtype=np.uint8)
    cy = 0  # next write row

    ref_y0 = fh // 2 - SLIT_H // 2  # strip source top in frame
    ref_y1 = ref_y0 + SLIT_H        # strip source bottom

    def _write_strip(img: np.ndarray, rows: int) -> None:
        nonlocal cy
        if rows <= 0:
            return
        # Source: always center-band of frame
        strip = img[ref_y0:ref_y1, :]
        # Repeat/resize to `rows` height
        dst_rows = min(rows, MAX_CANVAS_H - cy)
        if dst_rows <= 0:
            return
        if strip.shape[0] != dst_rows:
            strip = cv2.resize(strip, (fw, dst_rows), interpolation=cv2.INTER_LINEAR)
        canvas[cy:cy + dst_rows, :] = strip
        cy += dst_rows

    def _write_block(img: np.ndarray) -> tuple[int, int]:
        nonlocal cy
        h = min(fh, MAX_CANVAS_H - cy)
        if h <= 0:
            return cy, cy
        y0 = cy
        block = img[:h, :]
        canvas[cy:cy + h, :] = block
        cy += h
        return y0, cy

    def _write_gap() -> None:
        nonlocal cy
        h = min(GAP_HEIGHT, MAX_CANVAS_H - cy)
        if h <= 0:
            return
        canvas[cy:cy + h, :] = GAP_GRAY
        cy += h

    # ── 4. Kare-kare döngüsü ───────────────────────────────────────────────
    debug_frames: list[dict] = []
    sections: list[dict] = []
    sec_id = 0

    prev_gray_m: np.ndarray | None = None  # metin maskeli gri
    prev_gray_r: np.ndarray | None = None  # ham gri

    dy_buf: list[float] = []   # drift yumuşatma için son N dy

    # Statik birikim
    st_run: list[tuple[int, float, np.ndarray]] = []  # (idx, sharpness, img)
    st_start: int | None = None

    # Scroll birikim
    sc_start: int | None = None
    sc_y0: int = 0

    def flush_static(end_idx: int) -> None:
        nonlocal sec_id, cy
        if len(st_run) < STATIC_BLOCK_MIN:
            # Çok kısa — boş bırak (scroll içine gömülür)
            return
        best_idx, _, best_img = max(st_run, key=lambda t: t[1])
        y0, y1 = _write_block(best_img)
        sections.append({
            "section_id": sec_id, "kind": "static",
            "start_frame_idx": st_run[0][0], "end_frame_idx": end_idx,
            "start_y": y0, "end_y": y1, "frame_count": len(st_run),
            "best_frame_idx": best_idx,
        })
        sec_id += 1

    def close_scroll(end_idx: int) -> None:
        nonlocal sec_id
        if sc_start is None:
            return
        sections.append({
            "section_id": sec_id, "kind": "scroll",
            "start_frame_idx": sc_start, "end_frame_idx": end_idx,
            "start_y": sc_y0, "end_y": cy, "frame_count": end_idx - sc_start + 1,
            "best_frame_idx": None,
        })
        sec_id += 1

    for i, fp in enumerate(frames):
        recs = all_recs[i]
        # Text-gate: metin yoksa → no_text (sahne karesi, atla)
        # Eğer hiç OCR kaydı yoksa (--no-ocr veya hiç metin bulunamadı): tüm kareler geçerli
        has_text = bool(recs) if has_any else True

        img = _read(fp)
        if img is None:
            debug_frames.append({
                "frame_idx": i, "event": "read_error",
                "has_text": False, "text_area_ratio": 0.0,
                "dx": 0.0, "dy": 0.0, "dy_smoothed": 0.0,
                "response": 0.0, "global_diff": 0.0, "sharpness": 0.0,
                "canvas_y": cy,
            })
            continue

        if img.shape[:2] != (fh, fw):
            img = cv2.resize(img, (fw, fh), interpolation=cv2.INTER_AREA)

        gray_r = _gray(img)
        sharp = _sharpness(gray_r)

        # Metin maskesi
        mask = None
        tar = 0.0
        if has_text and recs:
            mask = _build_mask((fh, fw), recs, OCR_DILATION)
            tar = _text_ratio(mask, total_px)
            if tar < MIN_TEXT_RATIO:
                mask = None
                tar = 0.0

        gray_m = _masked(gray_r, mask)

        # Faz-korelasyon
        dx = dy = 0.0
        rsp = 1.0
        gdiff = 0.0

        if prev_gray_r is not None:
            if mask is not None and prev_gray_m is not None:
                dx, dy, rsp = _phase_corr(prev_gray_m, gray_m, hann)
            else:
                dx, dy, rsp = _phase_corr(prev_gray_r, gray_r, hann)
            gdiff = _gdiff(prev_gray_r, gray_r)

        # Drift yumuşatma (yalnız metin kareleri katkıda bulunur)
        if has_text:
            dy_buf.append(dy)
            if len(dy_buf) > DRIFT_N * 4:
                dy_buf.pop(0)
        dy_sm = _med(dy_buf[-DRIFT_N:]) if dy_buf else dy

        # Cut algılama
        is_cut = i > 0 and rsp < CUT_RESPONSE_MIN and gdiff > CUT_GLOBAL_DIFF

        # Hareket kararı
        is_static = abs(dy_sm) < STATIC_EPS

        # Event
        if not has_text:
            event = "no_text"
        elif is_cut:
            event = "cut"
        elif is_static:
            event = "static"
        else:
            event = "scroll"

        debug_frames.append({
            "frame_idx": i,
            "path": str(fp),
            "has_text": has_text,
            "text_area_ratio": round(tar, 4),
            "dx": round(dx, 3),
            "dy": round(dy, 3),
            "dy_smoothed": round(dy_sm, 3),
            "response": round(rsp, 4),
            "global_diff": round(gdiff, 2),
            "sharpness": round(sharp, 1),
            "event": event,
            "canvas_y": cy,
        })

        # ── Tuval yazma ──────────────────────────────────────────────────
        if event == "no_text":
            pass

        elif event == "cut":
            if st_start is not None:
                flush_static(i - 1)
                st_run.clear(); st_start = None
            if sc_start is not None:
                close_scroll(i - 1)
                sc_start = None
            if cy > 0:
                _write_gap()
            dy_buf.clear()

        elif event == "static":
            # Scroll açıksa kapat
            if sc_start is not None:
                close_scroll(i - 1)
                sc_start = None
            if st_start is None:
                st_start = i
            st_run.append((i, sharp, img.copy()))

        else:  # scroll
            # Statik açıksa yaz
            if st_start is not None:
                flush_static(i - 1)
                st_run.clear(); st_start = None

            if sc_start is None:
                sc_start = i
                sc_y0 = cy
                # İlk karede: tam frame yaz (referans)
                _write_block(img)
            else:
                # Pushbroom: her kareden SLIT_H şerit yaz.
                # Bu ghost-free ve sabit hızlı scrollda kusursuz rekonstrüksiyon sağlar.
                _write_strip(img, SLIT_H)

        prev_gray_r = gray_r
        prev_gray_m = gray_m if mask is not None else None

    # ── Son bölümleri kapat ───────────────────────────────────────────────
    if st_start is not None:
        flush_static(n - 1)
    if sc_start is not None:
        close_scroll(n - 1)

    # ── Panorama kaydet ───────────────────────────────────────────────────
    panorama = canvas[:max(1, cy), :].copy()
    ph, pw = panorama.shape[:2]
    pano_path = output_dir / "panorama.png"
    _write(pano_path, panorama)
    print(f"  [SlitScan] Panorama saved: {pw}x{ph}px -> {pano_path}")

    # ── Final OCR ─────────────────────────────────────────────────────────
    # PaddleOCR has a ~4000px max side limit. For tall panoramas, tile vertically.
    PADDLE_MAX_HEIGHT = 3800  # conservative limit with 200px overlap
    TILE_OVERLAP = 100        # pixels of overlap between tiles for bbox continuity

    print(f"  [SlitScan] Final OCR on panorama ({pw}x{ph}px)...")
    t_o = perf_counter()
    text_lines: list[dict] = []
    try:
        if ph <= PADDLE_MAX_HEIGHT:
            # Single-shot OCR
            final_recs = paddle_engine.recognize(
                pano_path, strategy="scroll_canvas_ocr", timestamp_seconds=None,
            )
            text_lines = [
                {"text": r.get("text", ""), "bbox": r.get("bbox"), "confidence": r.get("confidence")}
                for r in final_recs if r.get("text", "").strip()
            ]
        else:
            # Tiled OCR: split panorama into vertical tiles
            tile_dir = output_dir / "_tiles"
            tile_dir.mkdir(exist_ok=True)
            n_tiles = 0
            tile_offsets: list[int] = []
            tile_paths: list[Path] = []

            y = 0
            while y < ph:
                y_end = min(ph, y + PADDLE_MAX_HEIGHT)
                tile = panorama[y:y_end, :]
                tile_path = tile_dir / f"tile_{n_tiles:04d}.png"
                _write(tile_path, tile)
                tile_paths.append(tile_path)
                tile_offsets.append(y)
                n_tiles += 1
                y = y_end - TILE_OVERLAP  # overlap for context
                if y_end >= ph:
                    break

            print(f"  [SlitScan] Tiled OCR: {n_tiles} tiles...")
            seen_texts: set[str] = set()
            for tile_path, y_off in zip(tile_paths, tile_offsets):
                tile_recs = paddle_engine.recognize(
                    tile_path, strategy="scroll_canvas_ocr", timestamp_seconds=None,
                )
                for r in tile_recs:
                    txt = r.get("text", "").strip()
                    if not txt:
                        continue
                    # Adjust bbox y offset
                    bbox = r.get("bbox")
                    if bbox and len(bbox) >= 4:
                        adj_bbox = [bbox[0], bbox[1] + y_off, bbox[2], bbox[3]]
                    else:
                        adj_bbox = bbox
                    # Deduplicate overlap region
                    key = f"{txt}|{round(r.get('confidence',0), 2)}"
                    if key not in seen_texts:
                        seen_texts.add(key)
                        text_lines.append({
                            "text": txt,
                            "bbox": adj_bbox,
                            "confidence": r.get("confidence"),
                        })

        print(f"  [SlitScan] Final OCR done ({perf_counter()-t_o:.1f}s). Lines: {len(text_lines)}")
    except Exception as e:
        print(f"  [SlitScan] Final OCR error: {e}", file=sys.stderr)

    # ── lines.json ────────────────────────────────────────────────────────
    (output_dir / "lines.json").write_text(
        json.dumps({
            "canvas_path": str(pano_path),
            "line_count": len(text_lines),
            "lines": text_lines,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ── debug.json ────────────────────────────────────────────────────────
    dbg = {
        "frame_count": n,
        "text_frame_count": sum(1 for r in all_recs if r),
        "panorama_size": [pw, ph],
        "section_count": len(sections),
        "sections": sections,
        "runtime_sec": round(perf_counter() - t0, 2),
        "frames": debug_frames,
    }
    (output_dir / "debug.json").write_text(
        json.dumps(dbg, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    return SlitScanResult(
        panorama_path=pano_path,
        text_lines=text_lines,
        sections=sections,
        debug=dbg,
    )
