"""
SON METRO Credits PNG Composer
Yeni pipeline run'ından (opening + closing) tek PNG üretir.
Kullanım: venvs/ocr/Scripts/python.exe scripts/compose_son_metro_credits.py
"""

import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ── Ayarlar ───────────────────────────────────────────────────────────────────
BASE        = Path("E:/MITAS")
RUN_DIR     = BASE / "outputs/_sonmetro_best_20260530/items/1980_son_metro_wide"
OUT_PATH    = BASE / "outputs/_sonmetro_best_20260530_credits/son_metro_credits.png"

GAP              = 20
SECTION_GAP      = 60
SECTION_LABEL_H  = 30

# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def load_events(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8")).get("events", [])


def sort_key(ev: dict) -> float:
    return float("inf") if ev["type"] == "scroll_credit" else ev.get("start_sec", 0.0)


def load_cards(cards_dir: Path) -> dict:
    cards = {}
    for fp in sorted(cards_dir.glob("card_*.json")):
        d = json.loads(fp.read_text(encoding="utf-8"))
        cards[d["card_id"]] = d
    return cards


def crop_card(card_data: dict, frames_dir: Path) -> Image.Image | None:
    best = card_data.get("best_frame_path", "")
    p = Path(best) if os.path.isabs(best) else BASE / best
    if not p.exists():
        p = frames_dir / Path(best).name
    if not p.exists():
        print(f"  [WARN] frame bulunamadı: {best}")
        return None
    frame = Image.open(p).convert("RGB")
    W, H = frame.size
    yr = card_data.get("y_range", [0, H])
    y0 = max(0, int(yr[0]) - 5)
    y1 = min(H, int(yr[1]) + 5)
    return frame.crop((0, y0, W, y1))


def _composite_quality(seg_dir: Path) -> float:
    """row_reconstruct_summary.json'dan quality score oku. Yoksa 1.0 döner."""
    p = seg_dir / "scroll" / "row_reconstruct_summary.json"
    if not p.exists():
        return 1.0
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return float((d.get("quality") or {}).get("score", 1.0))
    except Exception:
        return 1.0


def _render_text_lines(lines: list, width: int) -> Image.Image:
    """Metin satırlarını siyah zemin üzerine beyaz yazıyla render eder."""
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

    line_h = 28
    pad = 12
    img_h = pad + len(lines) * line_h + pad
    img = Image.new("RGB", (width, img_h), (10, 10, 10))
    draw = ImageDraw.Draw(img)
    y = pad
    for ln in lines:
        text = ln.get("text", "").strip()
        conf = ln.get("confidence", 0.0)
        color = (255, 255, 255) if conf >= 0.75 else (180, 180, 180)
        draw.text((20, y), text, fill=color, font=font)
        y += line_h
    return img


def load_scroll(seg_dir: Path, master_width: int = 600) -> Image.Image | None:
    composite_p = seg_dir / "scroll" / "row_composite.png"
    lines_p     = seg_dir / "scroll" / "scroll_text_lines.json"

    quality = _composite_quality(seg_dir)
    composite_ok = composite_p.exists() and quality >= 0.35

    if composite_ok:
        return Image.open(composite_p).convert("RGB")

    # Composite bozuk — metin satırlarını render et
    if lines_p.exists():
        try:
            lines = json.loads(lines_p.read_text(encoding="utf-8")).get("lines", [])
        except Exception:
            lines = []
        if lines:
            print(f"  [INFO] scroll composite bozuk (quality={quality:.2f}), {len(lines)} satır metin render ediliyor")
            return _render_text_lines(lines, master_width)

    print(f"  [WARN] scroll verisi yok: {seg_dir}")
    return None


# ── Ana akış ──────────────────────────────────────────────────────────────────

def main():
    # Master genişliği ilk frame'den al
    master_width = 600
    for seg in ("opening", "closing"):
        frames = sorted((RUN_DIR / "frames" / seg).glob("frame_*.png"))
        if frames:
            master_width = Image.open(frames[0]).size[0]
            break

    pieces = []   # {"seg", "type", "img"}

    for seg in ("opening", "closing"):
        seg_dir   = RUN_DIR / "unified" / seg
        frames_dir = RUN_DIR / "frames" / seg
        events = sorted(load_events(seg_dir / "events.json"), key=sort_key)
        cards  = load_cards(seg_dir / "cards")

        for ev in events:
            num      = int(ev["event_id"].split("_")[1])
            card_key = f"card_{num:03d}"

            if ev["type"] == "card":
                card_data = cards.get(card_key)
                if card_data is None:
                    continue
                img = crop_card(card_data, frames_dir)
                if img:
                    pieces.append({"seg": seg, "type": "card", "img": img})

            elif ev["type"] == "scroll_credit":
                img = load_scroll(seg_dir, master_width)
                if img:
                    pieces.append({"seg": seg, "type": "scroll", "img": img})

    op = [p for p in pieces if p["seg"] == "opening"]
    cl = [p for p in pieces if p["seg"] == "closing"]
    print(f"Pieces: opening={len(op)}  closing={len(cl)}")

    # Canvas yüksekliği
    total_h = (
        SECTION_LABEL_H + sum(p["img"].height + GAP for p in op)
        + SECTION_GAP
        + SECTION_LABEL_H + sum(p["img"].height + GAP for p in cl)
        + GAP
    )

    canvas = Image.new("RGB", (master_width, total_h), (0, 0, 0))
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)

    def paste_pieces(piece_list, label, label_color_bg, label_color_fg, start_y):
        draw.rectangle([(0, start_y), (master_width, start_y + SECTION_LABEL_H)], fill=label_color_bg)
        draw.text((10, start_y + 5), label, fill=label_color_fg, font=font)
        cy = start_y + SECTION_LABEL_H
        for p in piece_list:
            img = p["img"]
            if img.width > master_width:
                img = img.resize(
                    (master_width, int(img.height * master_width / img.width)),
                    Image.LANCZOS,
                )
            canvas.paste(img, (0, cy))
            cy += img.height + GAP
        return cy

    cy = paste_pieces(op, "--- OPENING CREDITS ---", (30, 30, 80), (200, 200, 255), 0)
    cy += SECTION_GAP
    paste_pieces(cl, "--- CLOSING CREDITS ---", (80, 30, 30), (255, 200, 200), cy)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(OUT_PATH))
    print(f"Kaydedildi: {OUT_PATH}  ({canvas.size[0]}x{canvas.size[1]})")


if __name__ == "__main__":
    main()
