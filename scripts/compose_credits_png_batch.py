"""
Batch master PNG composer — 50 film
Kaynak: outputs/ocr_50films_aaaa_v21_paddle_20260525/items/<item_id>/
Cikti:  outputs/_credits_png_50films/<item_id>/credits.png

Kural: pipeline'a dokunmaz, sadece okur. PIL/Pillow yeterli.
"""

import json
import os
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE       = Path("E:/MITAS")
ITEMS_DIR  = BASE / "outputs/ocr_50films_aaaa_v21_paddle_20260525/items"
OUT_BASE   = BASE / "outputs/_credits_png_50films"

GAP             = 20
SECTION_GAP     = 60
SECTION_LABEL_H = 30


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def load_font():
    try:
        return ImageFont.truetype("arial.ttf", 18)
    except Exception:
        return ImageFont.load_default()


def load_events(path: Path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("events", [])


def load_cards(cards_dir: Path):
    cards = {}
    if not cards_dir.exists():
        return cards
    for fp in sorted(cards_dir.glob("card_*.json")):
        with open(fp, "r", encoding="utf-8") as f:
            d = json.load(f)
        cards[d["card_id"]] = d
    return cards


def sort_key(ev):
    return float("inf") if ev["type"] == "scroll_credit" else ev.get("start_sec", 0.0)


def detect_master_width(frames_opening: Path, frames_closing: Path) -> int:
    for d in [frames_opening, frames_closing]:
        frames = sorted(d.glob("frame_*.png")) if d.exists() else []
        if frames:
            try:
                return Image.open(frames[0]).size[0]
            except Exception:
                pass
    return 600


def extract_card_piece(event, card_data, frames_dir: Path, base: Path):
    try:
        best = card_data.get("best_frame_path", "")
        frame_abs = Path(best) if os.path.isabs(best) else base / best
        if not frame_abs.exists():
            frame_abs = frames_dir / Path(best).name
        if not frame_abs.exists():
            raise FileNotFoundError(frame_abs)

        frame = Image.open(frame_abs).convert("RGB")
        W, H = frame.size
        yr = card_data.get("y_range", [0, H])
        y0 = max(0, int(yr[0]) - 5)
        y1 = min(H, int(yr[1]) + 5)
        if y1 <= y0:
            y0, y1 = 0, H
        return frame.crop((0, y0, W, y1))
    except Exception as e:
        print(f"  [WARN] card extract hata ({event['event_id']}): {e}")
        return None


def extract_scroll_piece(seg_unified: Path):
    p = seg_unified / "scroll" / "row_composite.png"
    if not p.exists():
        return None
    try:
        return Image.open(p).convert("RGB")
    except Exception as e:
        print(f"  [WARN] scroll extract hata: {e}")
        return None


# ── Tek film compose ───────────────────────────────────────────────────────────

def compose_item(item_dir: Path, out_dir: Path) -> dict:
    label = item_dir.name
    t0 = time.time()

    opening_unified = item_dir / "unified" / "opening"
    closing_unified = item_dir / "unified" / "closing"
    frames_op = item_dir / "frames" / "opening"
    frames_cl = item_dir / "frames" / "closing"

    opening_events = sorted(load_events(opening_unified / "events.json"), key=sort_key)
    closing_events = sorted(load_events(closing_unified / "events.json"), key=sort_key)
    opening_cards  = load_cards(opening_unified / "cards")
    closing_cards  = load_cards(closing_unified / "cards")

    def get_card(ev_id, seg):
        num = int(ev_id.split("_")[1])
        key = f"card_{num:03d}"
        return (opening_cards if seg == "opening" else closing_cards).get(key)

    master_w = detect_master_width(frames_op, frames_cl)
    font = load_font()

    pieces = []
    for seg, evs, frms, seg_uni in [
        ("opening", opening_events, frames_op, opening_unified),
        ("closing", closing_events, frames_cl, closing_unified),
    ]:
        for ev in evs:
            ev_id = ev["event_id"]
            if ev["type"] == "card":
                cd = get_card(ev_id, seg)
                if cd is None:
                    continue
                img = extract_card_piece(ev, cd, frms, BASE)
                if img is None:
                    continue
                pieces.append({"seg": seg, "type": "card", "img": img,
                               "text": ev.get("text", "")[:60]})
            elif ev["type"] == "scroll_credit":
                img = extract_scroll_piece(seg_uni)
                if img is None:
                    continue
                pieces.append({"seg": seg, "type": "scroll_credit", "img": img,
                               "text": ev.get("text", "")[:60]})

    op_pieces = [p for p in pieces if p["seg"] == "opening"]
    cl_pieces = [p for p in pieces if p["seg"] == "closing"]

    if not pieces:
        return {"item": label, "error": "no pieces"}

    # Canvas yüksekliği
    def total_h(ps):
        return sum(p["img"].height + GAP for p in ps)

    canvas_h = (SECTION_LABEL_H + total_h(op_pieces)
                + SECTION_GAP
                + SECTION_LABEL_H + total_h(cl_pieces) + GAP)

    canvas = Image.new("RGB", (master_w, canvas_h), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    y = 0

    draw.rectangle([(0, y), (master_w, y + SECTION_LABEL_H)], fill=(30, 30, 80))
    draw.text((10, y + 5), "--- OPENING CREDITS ---", fill=(200, 200, 255), font=font)
    y += SECTION_LABEL_H

    for p in op_pieces:
        img = p["img"]
        if img.width > master_w:
            img = img.resize((master_w, int(img.height * master_w / img.width)), Image.LANCZOS)
        canvas.paste(img, (0, y))
        y += img.height + GAP

    y += SECTION_GAP
    draw.rectangle([(0, y), (master_w, y + SECTION_LABEL_H)], fill=(80, 30, 30))
    draw.text((10, y + 5), "--- CLOSING CREDITS ---", fill=(255, 200, 200), font=font)
    y += SECTION_LABEL_H

    for p in cl_pieces:
        img = p["img"]
        if img.width > master_w:
            img = img.resize((master_w, int(img.height * master_w / img.width)), Image.LANCZOS)
        canvas.paste(img, (0, y))
        y += img.height + GAP

    out_dir.mkdir(parents=True, exist_ok=True)
    master_path = out_dir / "credits.png"
    canvas.save(str(master_path))

    report = {
        "item": label,
        "master_size": f"{master_w}x{canvas_h}",
        "opening_pieces": len(op_pieces),
        "closing_pieces": len(cl_pieces),
        "total_pieces": len(pieces),
        "size_kb": round(os.path.getsize(master_path) / 1024, 1),
        "runtime_sec": round(time.time() - t0, 2),
    }
    with open(out_dir / "compose_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


# ── Ana döngü ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--items-dir" in args:
        idx = args.index("--items-dir")
        ITEMS_DIR = Path(args[idx + 1])
        args = args[:idx] + args[idx + 2:]
    if "--out-base" in args:
        idx = args.index("--out-base")
        OUT_BASE = Path(args[idx + 1])
        args = args[:idx] + args[idx + 2:]
    filter_ids = set(args)

    items = sorted(ITEMS_DIR.iterdir(), key=lambda p: p.name)
    if filter_ids:
        items = [i for i in items if i.name in filter_ids]

    print(f"İşlenecek film sayısı: {len(items)}")
    t_total = time.time()
    results = []

    for item_dir in items:
        if not item_dir.is_dir():
            continue
        out_dir = OUT_BASE / item_dir.name
        print(f"\n[{item_dir.name}]", end=" ", flush=True)
        try:
            r = compose_item(item_dir, out_dir)
        except Exception as e:
            r = {"item": item_dir.name, "error": str(e)}
            print(f"FATAL: {e}")
        results.append(r)
        if "error" not in r:
            print(f"OK — {r['master_size']} | {r['total_pieces']} parça | {r['size_kb']}KB | {r['runtime_sec']}s")
        else:
            print(f"HATA — {r['error']}")

    # Batch raporu
    ok  = [r for r in results if "error" not in r]
    err = [r for r in results if "error" in r]
    total_rt = time.time() - t_total

    print(f"\n{'='*60}")
    print(f"TAMAMLANDI: {len(ok)}/{len(results)} film")
    print(f"Toplam runtime: {total_rt:.1f}s ({total_rt/60:.1f}dk)")
    if ok:
        avg_pieces = sum(r["total_pieces"] for r in ok) / len(ok)
        print(f"Ortalama parça/film: {avg_pieces:.1f}")
    if err:
        print(f"\nHatalı filmler:")
        for r in err:
            print(f"  {r['item']}: {r['error']}")

    batch_report = OUT_BASE / "_batch_report.json"
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    with open(batch_report, "w", encoding="utf-8") as f:
        json.dump({"ok": len(ok), "error": len(err), "results": results}, f,
                  ensure_ascii=False, indent=2)
    print(f"\nBatch raporu: {batch_report}")
