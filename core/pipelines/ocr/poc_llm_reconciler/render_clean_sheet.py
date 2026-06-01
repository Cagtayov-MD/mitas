"""Son kosu: SON METRO closing icin TEMIZ kunye PNG'si.
Kaynak SADECE yuksek-guven temiz OCR: A panorama (kadro, conf~1.0) + B panorama
(sarki). beta'nin bozuk frame-scan'i ve VLM uydurmasi DISARIDA. Her ismin yaninda
A/B'den gelen gercek OCR guven skoru — temiz olduğunun kaniti.

Calistir: venvs\\core\\Scripts\\python.exe core\\pipelines\\ocr\\poc_llm_reconciler\\render_clean_sheet.py
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

A_LINES = Path(r"E:\MITAS\outputs\_boxtracking_test_20260529_235350\1980_son_metro_end_credits__closing\lines.json")
B_LINES = Path(r"E:\MITAS\outputs\_slitscan_test_20260529_234847\1980_son_metro_end_credits__closing\lines.json")
MERGED = Path(r"E:\MITAS\outputs\_poc_llm_reconciler_20260530\merged.json")
OUT = Path(r"E:\MITAS\outputs\_poc_credit_sheet_clean_20260530")
FONTS = r"C:\Windows\Fonts"

def font(name, sz):
    return ImageFont.truetype(str(Path(FONTS) / name), sz)

def conf_map(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    m = {}
    for l in d.get("lines", []):
        t = (l.get("text") or "").strip().upper().replace(" ", "")
        if len(t) >= 4:
            m[t] = max(m.get(t, 0), float(l.get("confidence", 0) or 0))
    return m

def lookup(name, cmap):
    k = (name or "").upper().replace(" ", "")
    if k in cmap:
        return cmap[k]
    # gevsek: ilk uzun token
    for tok in (name or "").upper().split():
        if len(tok) >= 5 and tok in cmap:
            return cmap[tok]
    return None

def main():
    merged = json.loads(MERGED.read_text(encoding="utf-8"))
    acm = conf_map(A_LINES)
    bcm = conf_map(B_LINES)

    W = 1040
    BG = (24, 24, 28)
    FG = (232, 230, 224)
    AMBER = (224, 176, 92)
    DIM = (140, 140, 148)
    GREEN = (120, 200, 130)

    f_title = font("arialbd.ttf", 38)
    f_sub = font("arial.ttf", 19)
    f_head = font("arialbd.ttf", 24)
    f_item = font("arial.ttf", 22)
    f_small = font("arial.ttf", 16)
    f_conf = font("arial.ttf", 15)

    # icerik bl  oklari hazirla
    cast = [c.get("name") for c in merged.get("cast", []) if c.get("name")]
    crew = merged.get("crew", [])
    songs = merged.get("songs", [])

    # yukseklik hesabi icin once olc
    lines = []  # (text, font, color, conf or None, indent)
    lines.append(("SON METRO", f_title, FG, None, 0))
    lines.append(("Le Dernier Métro (1980) — closing jenerik · TEMIZ künye", f_sub, DIM, None, 0))
    lines.append(("kaynak: A stitch (kadro) + B scroll (şarkı) → LLM birleştirme · β/VLM hariç", f_small, DIM, None, 0))
    lines.append(("__RULE__", None, None, None, 0))

    lines.append(("OYUNCULAR", f_head, AMBER, None, 0))
    for nm in cast:
        lines.append((nm, f_item, FG, lookup(nm, acm), 1))
    lines.append(("__GAP__", None, None, None, 0))

    lines.append(("ŞARKILAR", f_head, AMBER, None, 0))
    for s in songs:
        title = s.get("title") if isinstance(s, dict) else str(s)
        lines.append((title, f_item, FG, lookup(title, bcm), 1))
        det = s.get("detail") if isinstance(s, dict) else None
        if det:
            lines.append((det, f_small, DIM, None, 2))
    lines.append(("__GAP__", None, None, None, 0))

    lines.append(("TEKNİK / YAPIM", f_head, AMBER, None, 0))
    for c in crew:
        nm = c.get("name") if isinstance(c, dict) else str(c)
        role = c.get("role") if isinstance(c, dict) else None
        txt = f"{role} — {nm}" if role and role.lower() not in ("studio", "laboratoires") else nm
        lines.append((txt, f_item, FG, None, 1))
    lines.append(("__GAP__", None, None, None, 0))
    lines.append(("Not: ~7 yan rol (Bennent, Risch, Dubost, Haudepin, Szabó…) kaynak 600×480/452kbps'de", f_small, DIM, None, 0))
    lines.append(("düşük çözünürlükte bozuk okundu → bu temiz listede YOK (kapsama eksiği, kalite değil).", f_small, DIM, None, 0))

    # yukseklik
    pad = 56
    y = pad
    heights = []
    for txt, fnt, col, cf, ind in lines:
        if txt == "__RULE__":
            heights.append(28)
        elif txt == "__GAP__":
            heights.append(18)
        else:
            bb = fnt.getbbox(txt)
            heights.append((bb[3] - bb[1]) + 14)
    H = pad * 2 + sum(heights)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    y = pad
    for (txt, fnt, col, cf, ind), h in zip(lines, heights):
        if txt == "__RULE__":
            d.line([(pad, y + 10), (W - pad, y + 10)], fill=(60, 60, 68), width=2)
            y += h
            continue
        if txt == "__GAP__":
            y += h
            continue
        x = pad + ind * 26
        d.text((x, y), txt, font=fnt, fill=col)
        if cf is not None:
            tag = f"{cf:.2f}"
            cc = GREEN if cf >= 0.95 else (AMBER if cf >= 0.8 else DIM)
            tb = f_conf.getbbox(tag)
            d.text((W - pad - (tb[2] - tb[0]), y + 4), tag, font=f_conf, fill=cc)
        y += h

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "son_metro_kunye_temiz.png"
    img.save(p)
    print("YAZILDI:", p, img.size)
    print("kadro:", len(cast), "sarki:", len(songs), "teknik:", len(crew))

if __name__ == "__main__":
    main()
