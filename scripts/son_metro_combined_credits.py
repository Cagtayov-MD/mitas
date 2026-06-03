"""
SON METRO Combined Credits PNG Producer
========================================
Hedef: HEM statik oyuncu kadrosu (56 kart) HEM de hareket eden şarkı/teknik
       jenerik (kırmızı arka planlı scroll: CHANSONS, BEI MIR BIST DU SCHÖN,
       PRIERE A ZUMBA, L.T.C. SAINT CLOUD, EURO-TITRES…) içeren TEK bir PNG.

Strateji:
  1. Statik kadro  → wide run card_*.json'larından best_frame crop (full width, y_range).
  2. Hareketli scroll → SlitScan pushbroom motorunu YALNIZCA frames 4150-4320
     (scroll bölgesi, t≈691-720s) üzerinde çalıştır. Text-masked phase-corr
     sahne kesimlerini filtreler; sadece smooth scroll karelerini birleştirir.
  3. Assemble → statik kartlar (first_timestamp sırasına göre) + slit-scan
     panoraması tek bir PNG'de.

Kullanım:
    E:/MITAS/venvs/ocr/Scripts/python.exe scripts/son_metro_combined_credits.py

Çıktı:
    outputs/_sonmetro_combined_<ts>/son_metro_closing_combined.png
    outputs/_sonmetro_combined_<ts>/report.json
"""

from __future__ import annotations

import json
import sys
import os
import time
from datetime import datetime
from pathlib import Path

# ── Proje kökünü sys.path'e ekle ─────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# ── Sabitler ──────────────────────────────────────────────────────────────────
WIDE_ITEM = PROJECT_ROOT / "outputs" / "_sonmetro_best_20260530" / "items" / "1980_son_metro_wide"
CARDS_DIR  = WIDE_ITEM / "unified" / "closing" / "cards"
FRAMES_DIR = WIDE_ITEM / "frames" / "closing"

# Scroll bölgesi: frame indeksleri (1-tabanlı isimlendirme, 0-tabanlı liste indeksi)
# Bilgi: scroll t≈699-717s @ ~6fps → frame ~4193-4302
# Biraz geniş tutalım: 4100-4320 → tüm scroll bölgesini kapsar
SCROLL_START_FRAME = 4100  # 1-tabanlı frame numarası
SCROLL_END_FRAME   = 4320  # dahil

GAP     = 20
SEP_H   = 40
SEP_GRAY = (20, 20, 20)

SECTION_LABEL_H = 32


def _read_img(path: Path):
    import cv2, numpy as np
    buf = np.fromfile(str(path), np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def _write_img(path: Path, img) -> bool:
    import cv2
    ok, buf = cv2.imencode(".png", img)
    if ok:
        buf.tofile(str(path))
        return True
    return False


def load_cards(cards_dir: Path) -> list[dict]:
    """card_*.json dosyalarını first_timestamp sırasına göre döndür."""
    cards = []
    for fp in sorted(cards_dir.glob("card_*.json")):
        d = json.loads(fp.read_text(encoding="utf-8"))
        cards.append(d)
    # first_timestamp'e göre sırala
    cards.sort(key=lambda c: c.get("first_timestamp", 0.0))
    return cards


def crop_card(card_data: dict) -> object | None:
    """best_frame'den tam genişlik, y_range bölgesi crop'u döndür (PIL Image)."""
    from PIL import Image
    best = card_data.get("best_frame_path", "")
    p = Path(best) if os.path.isabs(best) else PROJECT_ROOT / best
    if not p.exists():
        # fallback: frames dizininde ara
        p = FRAMES_DIR / Path(best).name
    if not p.exists():
        print(f"  [WARN] Frame bulunamadı: {best}", file=sys.stderr)
        return None
    frame = Image.open(p).convert("RGB")
    W, H = frame.size
    yr = card_data.get("y_range", [0, H])
    y0 = max(0, int(yr[0]) - 5)
    y1 = min(H, int(yr[1]) + 5)
    if y1 <= y0:
        y0, y1 = 0, H
    return frame.crop((0, y0, W, y1))


def run_slit_scan(frames: list[Path], output_dir: Path, paddle_engine) -> Path | None:
    """SlitScan motorunu çalıştır; panorama.png yolunu döndür."""
    from core.pipelines.ocr.slitscan.slitscan_panorama import run_slitscan_panorama
    result = run_slitscan_panorama(
        frames,
        output_dir=output_dir,
        paddle_engine=paddle_engine,
        source_fps=6.0,
        ocr_stride=6,   # Her 6 karede bir OCR (daha sık = daha iyi text-gate)
    )
    print(f"  [SlitScan] Panorama: {result.panorama_path}")
    print(f"  [SlitScan] Lines ({len(result.text_lines)}):")
    for ln in result.text_lines[:20]:
        print(f"    {ln.get('text','')!r}")
    return result.panorama_path, result.text_lines, result.sections


def assemble(
    card_crops: list,          # PIL Images, sıralı
    card_metas: list[dict],    # eşleşen kart meta verisi
    scroll_panorama_path: Path | None,
    output_path: Path,
    master_width: int,
) -> dict:
    """Statik kartlar + scroll panoraması → tek PNG."""
    from PIL import Image, ImageDraw, ImageFont

    pieces = []
    for img, meta in zip(card_crops, card_metas):
        pieces.append({"type": "card", "img": img, "meta": meta})

    scroll_img = None
    if scroll_panorama_path and scroll_panorama_path.exists():
        scroll_img = Image.open(scroll_panorama_path).convert("RGB")
        pieces.append({"type": "scroll", "img": scroll_img, "meta": {}})

    # Canvas yüksekliği
    total_h = SECTION_LABEL_H  # "STATIC CAST" etiketi
    for p in pieces:
        img = p["img"]
        draw_w = min(img.width, master_width)
        draw_h = img.height
        if img.width > master_width:
            draw_h = int(img.height * master_width / img.width)
        total_h += draw_h + GAP
        if p["type"] == "scroll":
            total_h += SEP_H  # scroll'dan önce ayırıcı

    canvas = Image.new("RGB", (master_width, total_h), (0, 0, 0))
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)

    cy = 0

    # Bölüm etiketi
    draw.rectangle([(0, cy), (master_width, cy + SECTION_LABEL_H)], fill=(60, 30, 30))
    draw.text((10, cy + 7), "--- SON METRO CLOSING CREDITS (CAST + SONG/TECHNICAL SCROLL) ---",
              fill=(255, 200, 200), font=font)
    cy += SECTION_LABEL_H

    report_pieces = []
    for p in pieces:
        img = p["img"]
        if p["type"] == "scroll":
            # Scroll'dan önce ayırıcı çizgi
            draw.rectangle([(0, cy), (master_width, cy + SEP_H)], fill=(40, 10, 10))
            draw.text((10, cy + 10), "--- SONG & TECHNICAL CREDITS (SLIT-SCAN PANORAMA) ---",
                      fill=(255, 180, 80), font=font)
            cy += SEP_H

        if img.width > master_width:
            new_h = int(img.height * master_width / img.width)
            img = img.resize((master_width, new_h), Image.LANCZOS)

        canvas.paste(img, (0, cy))
        report_pieces.append({
            "type": p["type"],
            "place_y": cy,
            "height": img.height,
            "width": img.width,
            "meta": p.get("meta", {}),
        })
        cy += img.height + GAP

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(output_path))
    file_size_kb = output_path.stat().st_size / 1024
    print(f"  [Assemble] Kaydedildi: {output_path} ({canvas.size[0]}x{canvas.size[1]}, {file_size_kb:.0f} KB)")
    return {
        "output_path": str(output_path),
        "canvas_size": [canvas.size[0], canvas.size[1]],
        "file_size_kb": round(file_size_kb, 1),
        "pieces": report_pieces,
    }


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_base = PROJECT_ROOT / "outputs" / f"_sonmetro_combined_{ts}"
    out_base.mkdir(parents=True, exist_ok=True)
    print(f"[Combined] Çıktı dizini: {out_base}")
    t0 = time.perf_counter()

    # ── 1. Kart verilerini yükle ──────────────────────────────────────────────
    print("\n[Step 1] Statik kadro kartları yükleniyor...")
    cards = load_cards(CARDS_DIR)
    print(f"  {len(cards)} kart bulundu.")

    card_crops = []
    card_metas = []
    for card in cards:
        img = crop_card(card)
        if img is not None:
            card_crops.append(img)
            card_metas.append(card)
            texts = " | ".join(ln.get("text","") for ln in card.get("text_lines", [])[:3])
            print(f"  {card['card_id']} t={card['first_timestamp']:.1f}s: {texts}")
    print(f"  {len(card_crops)}/{len(cards)} kart crop başarılı.")

    # ── 2. PaddleOCR engine başlat ────────────────────────────────────────────
    print("\n[Step 2] PaddleOCR engine başlatılıyor...")
    t_ocr = time.perf_counter()
    try:
        from core.pipelines.ocr.credit_experiment import PaddleOcrEngine
        paddle_engine = PaddleOcrEngine()
        print(f"  PaddleOCR hazır ({time.perf_counter()-t_ocr:.1f}s). Device: {paddle_engine.device}")
    except Exception as e:
        import traceback
        print(f"  [HATA] PaddleOCR başlatılamadı: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    # ── 3. Scroll frame'lerini seç ────────────────────────────────────────────
    print(f"\n[Step 3] Scroll frame'leri ({SCROLL_START_FRAME}-{SCROLL_END_FRAME}) seçiliyor...")
    all_frames = sorted(FRAMES_DIR.glob("frame_*.png"), key=lambda p: int(p.stem.split("_")[-1]))
    # 1-tabanlı frame numaralarına göre filtrele
    scroll_frames = [
        f for f in all_frames
        if SCROLL_START_FRAME <= int(f.stem.split("_")[-1]) <= SCROLL_END_FRAME
    ]
    print(f"  {len(scroll_frames)} scroll frame seçildi ({scroll_frames[0].name} - {scroll_frames[-1].name})")

    # ── 4. SlitScan çalıştır ──────────────────────────────────────────────────
    print("\n[Step 4] SlitScan slit-scan panorama motoru çalıştırılıyor...")
    slitscan_out = out_base / "slitscan"
    t_ss = time.perf_counter()
    scroll_panorama_path, scroll_lines, scroll_sections = run_slit_scan(
        scroll_frames, slitscan_out, paddle_engine
    )
    print(f"  SlitScan tamamlandı ({time.perf_counter()-t_ss:.1f}s).")

    # ── 5. master_width'i belirle ─────────────────────────────────────────────
    master_width = 600
    if all_frames:
        from PIL import Image
        try:
            master_width = Image.open(all_frames[0]).size[0]
        except Exception:
            pass
    print(f"\n[Step 5] master_width = {master_width}")

    # ── 6. Assemble ───────────────────────────────────────────────────────────
    print("\n[Step 6] PNG derleniyor...")
    out_png = out_base / "son_metro_closing_combined.png"
    assemble_report = assemble(
        card_crops, card_metas,
        scroll_panorama_path,
        out_png,
        master_width,
    )

    # ── 7. Report JSON ────────────────────────────────────────────────────────
    report = {
        "timestamp": ts,
        "wide_item_dir": str(WIDE_ITEM),
        "card_count": len(cards),
        "card_crop_success": len(card_crops),
        "scroll_frame_range": [SCROLL_START_FRAME, SCROLL_END_FRAME],
        "scroll_frame_count": len(scroll_frames),
        "scroll_panorama_path": str(scroll_panorama_path) if scroll_panorama_path else None,
        "scroll_text_lines": scroll_lines,
        "scroll_sections": scroll_sections,
        "assemble": assemble_report,
        "runtime_total_sec": round(time.perf_counter() - t0, 2),
    }
    report_path = out_base / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[Combined] Rapor: {report_path}")

    # ── 8. Özet ───────────────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("ÖZET")
    print("="*70)
    print(f"  Statik kadro kartları : {len(card_crops)} adet")
    print(f"  Scroll panoraması     : {scroll_panorama_path}")
    print(f"  Çıktı PNG             : {out_png}")
    print(f"  Boyut                 : {assemble_report['canvas_size'][0]}x{assemble_report['canvas_size'][1]}")
    print(f"  Dosya boyutu          : {assemble_report['file_size_kb']:.0f} KB")
    print(f"  Toplam runtime        : {report['runtime_total_sec']:.0f}s")
    print()
    print(f"Scroll OCR satırları ({len(scroll_lines)} adet):")
    for ln in scroll_lines[:30]:
        print(f"  {ln.get('text','')!r}")

    print()
    print("Yeniden çalıştırma komutu:")
    print("  E:/MITAS/venvs/ocr/Scripts/python.exe E:/MITAS/scripts/son_metro_combined_credits.py")


if __name__ == "__main__":
    main()
