# -*- coding: utf-8 -*-
"""MİTAS künye belgesi — A4 genişliğinde, içeriğe göre uzayan ortak şablon.

Hem film hem dizi üretir; eski ``crew`` sözleşmesini ve yeni ``guest_cast`` /
``full_credits`` alanlarını kabul eder.
"""
import math
import os
import re
import unicodedata
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit, ImageReader
from reportlab.lib.colors import HexColor

# Linux geçişi 2026-07-16: kök+font env'den (Windows'ta env yoksa eski davranış birebir).
OUT = os.path.join(os.environ.get("MITAS_PROJECT_ROOT") or r"E:\MITAS", "OCR-worktree", "pdf-mitas") \
    if os.environ.get("MITAS_PROJECT_ROOT") else r"E:\MITAS\OCR-worktree\pdf-mitas"
F = os.environ.get("MITAS_MSFONT_DIR") or ("/usr/share/fonts/truetype/msttcorefonts" if os.name != "nt" else r"C:\Windows\Fonts")

if os.path.exists(os.path.join(F, "Arial.ttf")):
    pdfmetrics.registerFont(TTFont("AR", os.path.join(F, "Arial.ttf")))
elif os.path.exists(os.path.join(F, "arial.ttf")):
    pdfmetrics.registerFont(TTFont("AR", os.path.join(F, "arial.ttf")))
else:
    pdfmetrics.registerFont(TTFont("AR", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"))

if os.path.exists(os.path.join(F, "arialbd.ttf")):
    pdfmetrics.registerFont(TTFont("ARB", os.path.join(F, "arialbd.ttf")))
elif os.path.exists(os.path.join(F, "Arial_Bold.ttf")):
    pdfmetrics.registerFont(TTFont("ARB", os.path.join(F, "Arial_Bold.ttf")))
else:
    pdfmetrics.registerFont(TTFont("ARB", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"))


def tryfont(name, path, fb):
    try:
        pdfmetrics.registerFont(TTFont(name, path))
        return name
    except Exception:
        return fb


SERIF_B = tryfont("Georgia-Bold", F + r"\georgiab.ttf", "ARB")
SERIF_I = tryfont("Georgia-Italic", F + r"\georgiai.ttf", "AR")
SANS = tryfont("Segoe", F + r"\segoeui.ttf", "AR")
SANS_SB = tryfont("Segoe-SB", F + r"\seguisb.ttf", "ARB")

RAIL = HexColor("#19222E")
PANEL = HexColor("#222E3C")
HOLE = HexColor("#3C4858")
ACCENT = HexColor("#C2A14D")       # altin
CREAM = HexColor("#F1EEE6")
CREAM_M = HexColor("#9DA8B4")
RAIL_HAIR = HexColor("#33404F")
INK = HexColor("#1A2230")
BODY = HexColor("#333D49")
MUTE = HexColor("#6B7785")
HAIR = HexColor("#E2E6EB")
TINT = HexColor("#F6F5F1")

PAGE_W, PAGE_H = A4
RW = 192
RM = 22
X0 = RW + 34
XR = PAGE_W - 44
CW = XR - X0
FOOT_H = 32

# PDF sayfa kenarı üst sınırı (points). PDF spec/Acrobat 200 inch = 14400pt üstünü
# güvenilir işlemez; aşan sayfa görüntüleyicide kırpılır. Künye sayfası artık içerik
# kadar uzayabildiği için sınır hem künye hem master-kanıt sayfasında uygulanır.
_PDF_MAX_PT = 14400.0

_TRT_ID_RE = re.compile(r"(\d{4})-(\d{3,4})-(\d)-(\d{3,4})-(\d{2})-(\d)")
_DIRECTOR_ROLES = {"yonetmen", "director", "directed by"}
_PRODUCER_ROLES = {"yapimci", "producer", "produced by"}
_GUEST_ROLES = {
    "konuk oyuncu", "konuk oyuncular", "konuklar",
    "guest cast", "guest starring", "guest stars", "special guest",
}


def hair(c, y, x0, x1, color=HAIR, w=0.6):
    c.setStrokeColor(color)
    c.setLineWidth(w)
    c.line(x0, y, x1, y)


def tracked(c, x, y, text, font, size, color, sp, right=False, center=False):
    w = pdfmetrics.stringWidth(text, font, size) + sp * max(len(text) - 1, 0)
    if right:
        x -= w
    elif center:
        x -= w / 2.0
    to = c.beginText(x, y)
    to.setFont(font, size)
    to.setFillColor(color)
    to.setCharSpace(sp)
    to.textOut(text)
    to.setCharSpace(0)
    c.drawText(to)
    return w


def fit(text, font, size, maxw, lo=20):
    while size > lo and pdfmetrics.stringWidth(text, font, size) > maxw:
        size -= 1
    return size


def _role_key(value):
    """Rol karşılaştırması için Türkçe/aksan-duyarsız, tam-eşleşme anahtarı."""
    s = str(value or "").translate(str.maketrans({"ı": "i", "İ": "I"}))
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.casefold()).split())


def _names(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _credit_pairs(value):
    """Serbest liste/tuple girdisini [(rol, [değer...])] sözleşmesine indirger."""
    out = []
    for item in value or []:
        if isinstance(item, dict):
            role = item.get("role", item.get("rol", ""))
            names = item.get("names", item.get("isimler", item.get("name", item.get("isim", []))))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            role, names = item
        else:
            continue
        role, names = str(role or "").strip(), _names(names)
        if role and names:
            out.append((role, names))
    return out


def _partition_credits(d):
    """Eski crew sözleşmesini yeni ana/konuk/tam-jenerik yüzeylerine ayırır.

    guest_cast/full_credits anahtarının VARLIĞI otoriterdir: boş liste de bilinçli
    boşluk sayılır. Anahtar yoksa eski crew içinden geriye uyumlu türetme yapılır.
    """
    directors, producers, legacy_guests, legacy_full = [], [], [], []
    for role, names in _credit_pairs(d.get("crew") or []):
        key = _role_key(role)
        if key in _DIRECTOR_ROLES:
            directors.extend(names)
        elif key in _PRODUCER_ROLES:
            producers.extend(names)
        elif key in _GUEST_ROLES:
            legacy_guests.extend(names)
        else:
            legacy_full.append((role, names))

    main = []
    if directors:
        main.append(("Yönetmen", directors))
    if producers:
        main.append(("Yapımcı", producers))
    guests = _names(d.get("guest_cast")) if "guest_cast" in d else legacy_guests
    full = _credit_pairs(d.get("full_credits")) if "full_credits" in d else legacy_full
    return main, guests, full


def _title_context(d):
    """TRT kimliğinden profil/bölüm çıkar; kimlik yoksa eski d alanlarına düş."""
    trt = next((str(value) for label, value in (d.get("specs") or [])
                if "KİMLİK" in str(label).upper() or "KIMLIK" in str(label).upper()), "")
    match = _TRT_ID_RE.search(trt)
    profile = str(d.get("profile") or "FİLM")
    is_series = _role_key(profile) == "dizi"
    episode = None
    if match and match.group(3) in ("0", "1"):
        is_series = match.group(3) == "0"
        profile = "DİZİ" if is_series else "FİLM"
        number = int(match.group(4))
        episode = f"{number}. Bölüm" if is_series and number > 0 else None
    elif is_series:
        raw = str(d.get("bolum") or "").strip()
        number = re.search(r"\d+", raw)
        if number and int(number.group()) > 0:
            episode = f"{int(number.group())}. Bölüm"
        elif raw:
            episode = raw
    return {
        "profile": profile,
        "subtitle": None if is_series else d.get("subtitle"),
        "bolum": episode if is_series else None,
    }


def _wrap_lines(text, font, size, maxw):
    """Boşluksuz çok uzun sözcüklerde de yatay taşma bırakmadan satır sar."""
    wrapped = simpleSplit(str(text), font, size, maxw) or [str(text)]
    lines = []
    for line in wrapped:
        if pdfmetrics.stringWidth(line, font, size) <= maxw:
            lines.append(line)
            continue
        part = ""
        for char in line:
            candidate = part + char
            if part and pdfmetrics.stringWidth(candidate, font, size) > maxw:
                lines.append(part)
                part = char
            else:
                part = candidate
        if part:
            lines.append(part)
    return lines


def _name_columns(names, font=SANS, size=10, leading=15.0, gap=3.0):
    """İsimleri iki kolona böler; her adı kendi kolon genişliğinde sarar."""
    names = [str(name) for name in names or []]
    half = math.ceil(len(names) / 2)
    col_w = (CW - 14) / 2.0
    columns = []
    for group in (names[:half], names[half:]):
        items = []
        for name in group:
            lines = _wrap_lines(name, font, size, col_w)
            items.append(lines)
        columns.append(items)

    def column_height(items):
        if not items:
            return 0.0
        return sum(len(lines) * leading + gap for lines in items) - gap

    return {"columns": columns, "height": max(column_height(c) for c in columns),
            "font": font, "size": size, "leading": leading, "gap": gap,
            "col_w": col_w}


def _credit_rows(pairs, *, colon=False):
    """Rol/değer çiftlerini sarılmış, yüksekliği ölçülmüş satır gruplarına çevirir."""
    role_w, name_w = 112.0, CW - 130.0
    rows, total = [], 0.0
    for role, names in pairs:
        role_text = role + (" :" if colon else "")
        role_lines = _wrap_lines(role_text, SANS, 9, role_w)
        name_lines = []
        for name in names:
            name_lines.extend(_wrap_lines(name, SANS_SB, 9.5, name_w))
        line_count = max(len(role_lines), len(name_lines), 1)
        height = line_count * 14.0 + 4.0
        rows.append({"role": role_lines, "names": name_lines, "height": height})
        total += height
    return {"rows": rows, "height": total}


def _prepare_layout(d):
    context = _title_context(d)
    title = str(d.get("title") or "—")
    title_size = 35
    while title_size > 22 and pdfmetrics.stringWidth(title, SERIF_B, title_size) > CW:
        title_size -= 1
    title_lines = ([title] if pdfmetrics.stringWidth(title, SERIF_B, title_size) <= CW
                   else (simpleSplit(title, SERIF_B, title_size, CW) or [title]))
    title_drop = ((title_size - 10) if len(title_lines) == 1
                  else len(title_lines) * (title_size - 3) + 7)

    main_crew, guests, full_credits = _partition_credits(d)
    keywords = simpleSplit(str(d.get("keywords") or "—"), SANS, 9.5, CW) or ["—"]
    cast = _name_columns(_names(d.get("cast")) or ["—"])
    guest_cols = _name_columns(guests)
    main_rows = _credit_rows(main_crew)
    full_rows = _credit_rows(full_credits, colon=True)

    notes = [str(x).strip() for x in (d.get("film_notu") or []) if str(x).strip()]
    note_lines = []
    for note in notes[:4]:
        note_lines += simpleSplit("•  " + note, SANS, 8.8, CW - 36)
    note_h = (34 + len(note_lines) * 13.0) if note_lines else 0.0

    summary_text = str(d.get("ozet") or "").strip()
    summary_lines = simpleSplit(summary_text, SANS, 10.5, CW - 34) if summary_text else []
    summary_h = (42 + len(summary_lines) * 16.0) if summary_lines else 0.0

    # PAGE_H-92'de başlayan sağ akışın sayfa tepesinden toplam inişi.
    used = 92 + 34 + title_drop
    used += 18 if context["subtitle"] else 0
    used += 18 if context["bolum"] else 0
    used += 40
    used += 34 + len(keywords) * 15
    used += 34 + cast["height"]
    if main_rows["rows"]:
        used += 34 + main_rows["height"]
    if guest_cols["height"]:
        used += 34 + guest_cols["height"]
    if note_h:
        used += 14 + note_h
    if summary_h:
        used += 16 + summary_h
    if full_rows["rows"]:
        used += 34 + full_rows["height"]
    page_h = max(PAGE_H, used + FOOT_H + 10)
    if page_h > _PDF_MAX_PT:
        raise ValueError(
            f"künye sayfası PDF güvenli yükseklik sınırını aşıyor: "
            f"{page_h:.1f}pt > {_PDF_MAX_PT:.0f}pt; veri kırpılmadı")
    return {
        "context": context, "title": title, "title_size": title_size,
        "title_lines": title_lines, "keywords": keywords, "cast": cast,
        "main_rows": main_rows, "guests": guest_cols, "full_rows": full_rows,
        "note_lines": note_lines, "note_h": note_h,
        "summary_lines": summary_lines, "summary_h": summary_h,
        "page_h": page_h,
    }


def _draw_name_columns(c, x, y, layout):
    xs = (x, x + layout["col_w"] + 14)
    bottoms = []
    for col, items in enumerate(layout["columns"]):
        yy = y
        for lines in items:
            for line in lines:
                c.setFont(layout["font"], layout["size"])
                c.setFillColor(INK)
                c.drawString(xs[col], yy, line)
                yy -= layout["leading"]
            yy -= layout["gap"]
        bottoms.append(yy + (layout["gap"] if items else 0))
    return min(bottoms) if bottoms else y


def _draw_credit_rows(c, y, layout):
    for row in layout["rows"]:
        role_y = name_y = y
        for line in row["role"]:
            c.setFont(SANS, 9)
            c.setFillColor(MUTE)
            c.drawString(X0, role_y, line)
            role_y -= 14
        for line in row["names"]:
            c.setFont(SANS_SB, 9.5)
            c.setFillColor(INK)
            c.drawString(X0 + 130, name_y, line)
            name_y -= 14
        y -= row["height"]
    return y


def build(path, d):
    layout = _prepare_layout(d)
    page_h = layout["page_h"]
    context = layout["context"]
    c = canvas.Canvas(path, pagesize=(PAGE_W, page_h))

    c.setFillColor(RAIL)
    c.rect(0, 0, RW, page_h, fill=1, stroke=0)
    c.rect(0, 0, PAGE_W, FOOT_H, fill=1, stroke=0)

    # Amblem (yazi)
    c.setFillColor(CREAM)
    c.setFont(SERIF_B, 18)
    c.drawString(RM, page_h - 48, "MİTAS")
    c.setFillColor(ACCENT)
    c.rect(RM, page_h - 60, 34, 2.4, fill=1, stroke=0)
    tracked(c, RM, page_h - 76, "İÇERİK KÜNYE BELGESİ", SANS_SB, 6.6, CREAM_M, 1.5)

    # Sol panel: afiş varsa afiş (çerçeve afişin oranına göre), yoksa anahtar-kare placeholder
    pw = RW - 2 * RM
    ptop = page_h - 96
    poster = d.get("poster")
    if poster and os.path.exists(poster):
        img = ImageReader(poster)
        iw, ih = img.getSize()
        dw = pw
        dh = dw * ih / float(iw)
        maxh = 300.0
        if dh > maxh:
            dh = maxh
            dw = dh * iw / float(ih)
        px = RM + (pw - dw) / 2.0
        panel_bottom = ptop - dh
        c.drawImage(img, px, panel_bottom, dw, dh, mask='auto')
        c.setStrokeColor(ACCENT)
        c.setLineWidth(0.9)
        c.roundRect(px, panel_bottom, dw, dh, 2, stroke=1, fill=0)
    else:
        panel_bottom = ptop          # frame (anahtar-kare placeholder) KALDIRILDI → yerine ses/altyazı

    # SES & ALTYAZI (sol ray — frame'in yerine; kanal-dil + altyazı + jenerik dili tespiti)
    if d.get("ses_kanallari") or d.get("altyazi") or d.get("jenerik_dili"):
        sb = panel_bottom - 22
        tracked(c, RM, sb, "SES & ALTYAZI", SANS_SB, 6.8, ACCENT, 1.4)
        sb -= 19
        if d.get("jenerik_dili"):
            tracked(c, RM, sb, "JENERİK DİLİ", SANS_SB, 6.2, CREAM_M, 1.1)
            c.setFillColor(CREAM)
            c.setFont(SANS_SB, 9.5)
            c.drawString(RM + 60, sb - 1, str(d.get("jenerik_dili", "—")))
            sb -= 16
        tracked(c, RM, sb, "ANA DİL", SANS_SB, 6.2, CREAM_M, 1.1)
        c.setFillColor(CREAM)
        c.setFont(SANS_SB, 9.5)
        c.drawString(RM + 60, sb - 1, str(d.get("ana_dil", "—")))
        sb -= 16
        tracked(c, RM, sb, "ALTYAZI", SANS_SB, 6.2, CREAM_M, 1.1)
        c.setFillColor(ACCENT if str(d.get("altyazi", "")).upper() == "EVET" else CREAM)
        c.setFont(SANS_SB, 9.5)
        c.drawString(RM + 60, sb - 1, str(d.get("altyazi", "—")))
        sb -= 18
        if d.get("sesler_ic_ice"):     # seslendirme + orijinal karışık
            tracked(c, RM, sb, "SESLER İÇ İÇE", SANS_SB, 6.2, ACCENT, 1.0)
            sb -= 16
        sb -= 4
        hair(c, sb, RM, RW - RM, RAIL_HAIR, 0.5)
        panel_bottom = sb

    # Teknik kunye (cozunurluk haric — o sag uste, Uretim altina silik tasindi)
    sy = panel_bottom - 30
    for label, value in d["specs"]:
        if "ÖZÜNÜR" in label.upper() or "OZUNUR" in label.upper():
            continue
        tracked(c, RM, sy, label, SANS_SB, 6.8, ACCENT, 1.4)
        c.setFillColor(CREAM)
        c.setFont(SANS_SB, 10)
        c.drawString(RM, sy - 13, value)
        hair(c, sy - 24, RM, RW - RM, RAIL_HAIR, 0.5)
        sy -= 42

    _stamp = d.get("stamp", "")  # gercek belge: damga yok (istenirse d["stamp"] verilir)
    if _stamp:
        c.setFillColor(ACCENT)
        c.setFont(SANS_SB, 12)
        c.drawString(RM, 46, _stamp)

    c.setFillColor(CREAM_M)
    c.setFont(SANS, 7.6)
    c.drawString(X0, FOOT_H / 2.0 - 3, "OTOMATİK ÜRETİLMİŞ KÜNYE BELGESİ")
    c.drawRightString(XR, FOOT_H / 2.0 - 3, "SAYFA  1 / 1")

    # ---- Sag icerik ----
    c.setFillColor(MUTE)
    c.setFont(SANS, 8.5)
    c.drawRightString(XR, page_h - 46, "ÜRETİM:  " + d["date"])
    # cozunurluk: Uretim'in hemen altinda, SILIK
    _res = next((v for l, v in d["specs"] if ("ÖZÜNÜR" in l.upper() or "OZUNUR" in l.upper()) and v and v != "—"), None)
    if _res:
        c.setFillColor(CREAM_M)
        c.setFont(SANS, 7.3)
        c.drawRightString(XR, page_h - 57, _res)

    ty = page_h - 92
    profile = context["profile"]
    chip_w = pdfmetrics.stringWidth(profile, SANS_SB, 8) + 1.5 * (len(profile) - 1) + 20
    c.setStrokeColor(ACCENT)
    c.setLineWidth(0.9)
    c.roundRect(X0, ty, chip_w, 17, 8.5, stroke=1, fill=0)
    tracked(c, X0 + 10, ty + 5, profile, SANS_SB, 8, ACCENT, 1.5)
    ty -= 34

    title = layout["title"]
    ts = layout["title_size"]
    c.setFillColor(INK)
    c.setFont(SERIF_B, ts)
    if len(layout["title_lines"]) == 1:
        c.drawString(X0, ty, layout["title_lines"][0])
        ty -= (ts - 10)
    else:
        for _ln in layout["title_lines"]:
            c.drawString(X0, ty, _ln)
            ty -= (ts - 3)
        ty -= 7
    if context["subtitle"]:
        c.setFillColor(MUTE)
        c.setFont(SERIF_I, 13.5)
        c.drawString(X0, ty, str(context["subtitle"]))
        ty -= 18
    if context["bolum"]:
        tracked(c, X0, ty, context["bolum"], SANS_SB, 10.5, MUTE, 1.6)
        ty -= 18
    ty -= 8
    c.setFillColor(ACCENT)
    c.rect(X0, ty, 40, 2.4, fill=1, stroke=0)
    ty -= 32

    def section(label):
        nonlocal ty
        ty -= 12
        lw = tracked(c, X0, ty, label, SANS_SB, 8, ACCENT, 2)
        hair(c, ty + 3, X0 + lw + 12, XR)
        ty -= 22

    section("ANAHTAR SÖZCÜKLER")
    for ln in layout["keywords"]:
        c.setFont(SANS, 9.5)
        c.setFillColor(BODY)
        c.drawString(X0, ty, ln)
        ty -= 15

    section("OYUNCULAR")
    ty = _draw_name_columns(c, X0, ty, layout["cast"])

    if layout["main_rows"]["rows"]:
        section("YAPIM EKİBİ")
        ty = _draw_credit_rows(c, ty, layout["main_rows"])

    if layout["guests"]["height"]:
        section("KONUK OYUNCULAR")
        ty = _draw_name_columns(c, X0, ty, layout["guests"])

    # FİLM NOTU kutusu (2026-07-04, Çağatay): sağ içeriğin altında, ÖZET'ten hemen önce.
    # Deterministik standart notlar (animasyon-seslendirme / sessiz-özet-yok / jenerik-yok / XML-uyarı).
    # d["film_notu"] boşsa HİÇ çizilmez (mevcut düzen birebir korunur). Kutu ve özet
    # önceden ölçülen uzun sayfa içinde kendi doğal punto/leading değerleriyle çizilir.
    if layout["note_lines"]:
        ty -= 14
        nt_size, nt_lh = 8.8, 13.0
        nt_lines = layout["note_lines"]
        nt_h = layout["note_h"]
        c.setFillColor(TINT)
        c.roundRect(X0, ty - nt_h, CW, nt_h, 7, fill=1, stroke=0)
        c.setStrokeColor(ACCENT)
        c.setLineWidth(0.9)
        c.roundRect(X0, ty - nt_h, CW, nt_h, 7, stroke=1, fill=0)
        tracked(c, X0 + 18, ty - 20, "FİLM NOTU", SANS_SB, 8, ACCENT, 2)
        _nyy = ty - 36
        for _ln in nt_lines:
            c.setFont(SANS, nt_size)
            c.setFillColor(BODY)
            c.drawString(X0 + 18, _nyy, _ln)
            _nyy -= nt_lh
        ty -= nt_h

    if layout["summary_lines"]:
        ty -= 16
        oz_size, oz_lh = 10.5, 16.0
        lines = layout["summary_lines"]
        panel_h = layout["summary_h"]
        ptopz = ty
        pbz = ptopz - panel_h
        c.setFillColor(TINT)
        c.roundRect(X0, pbz, CW, panel_h, 7, fill=1, stroke=0)
        tracked(c, X0 + 18, ptopz - 22, "ÖZET", SANS_SB, 8, ACCENT, 2)
        c.setFillColor(ACCENT)
        c.rect(X0 + 18, pbz + 16, 2.4, len(lines) * oz_lh - 4, fill=1, stroke=0)
        yy = ptopz - 40
        for ln in lines:
            c.setFont(SANS, oz_size)
            c.setFillColor(BODY)
            c.drawString(X0 + 30, yy, ln)
            yy -= oz_lh
        ty = pbz

    if layout["full_rows"]["rows"]:
        section("TAM JENERİK")
        ty = _draw_credit_rows(c, ty, layout["full_rows"])

    if ty < FOOT_H + 9:
        raise RuntimeError(f"künye yerleşimi alt sınıra taştı: y={ty:.1f}")

    # Jenerik Master Okuma Kanıtı Sayfaları (Giriş & Çıkış)
    clip_dir = d.get("clip_dir") or d.get("clip") or (os.path.dirname(d.get("poster")) if d.get("poster") else None)
    if clip_dir:
        try:
            _ekle_kanit_sayfalari(c, clip_dir)
        except Exception as _exc:
            print(f"[pdf-kanit] HATA: {_exc}")

    c.showPage()
    c.save()
    print("yazildi:", path)


# NOT (2026-08-11): _slice_im_parts + _combine_side_by_side BURADAN SİLİNDİ.
# Master PNG'yi 4 parçaya bölüp sabit target_h=2000'e SIKIŞTIRAN eski yaklaşımdı;
# uzun jeneriği A4'e zorladığı için PDF'te KESİK görüntüye yol açıyordu (kanıt:
# 05-06 Ağustos'ta üretilen kunye.pdf'lerde kanıt sayfaları A4 + gömülü görseller
# tam 2000px). 08 Ağustos'ta yerini aşağıdaki dinamik-yükseklik yaklaşımı aldı;
# iki fonksiyon da o tarihten beri HİÇBİR yerden çağrılmıyordu (repo geneli
# doğrulandı). Ölü bırakmak yerine siliniyor ki kesen yol yanlışlıkla dirilmesin.


def _ekle_kanit_sayfalari(c, clip_dir):
    """
    Giriş ve Çıkış master PNG'lerini yan yana (sol/sağ) tek sayfada koyar.
    Sayfa yüksekliği görüntülerin uzunluğuna göre dinamik ayarlanır.
    Çözünürlük düşürülmez - PDF'de zoom yapıp okuyabilirler.
    """
    import glob
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    
    cd = str(clip_dir)
    giris_candidates = [os.path.join(cd, "giris_reading_master_runaware.png")] + glob.glob(os.path.join(cd, "*giris-lebron.png"))
    giris_png = next((p for p in giris_candidates if os.path.isfile(p)), None)

    cikis_candidates = [os.path.join(cd, "reading_master_runaware.png")] + glob.glob(os.path.join(cd, "*cikis-lebron.png"))
    cikis_png = next((p for p in cikis_candidates if os.path.isfile(p)), None)
    
    if not giris_png and not cikis_png:
        return
    
    margin = 36.0
    page_w, page_h = A4
    usable_w = page_w - (2 * margin)
    gap = 20  # iki görüntü arası boşluk
    
    # Her iki görüntü de varsa yan yana, tek varsa tam genişlik
    has_giris = giris_png and os.path.isfile(giris_png)
    has_cikis = cikis_png and os.path.isfile(cikis_png)
    
    if has_giris and has_cikis:
        img_w_each = (usable_w - gap) / 2.0
    else:
        img_w_each = usable_w
    
    # Görüntü boyutlarını oku ve ölçek hesapla (sadece genişliğe göre, yüksekliğe GÖRE DEĞİL)
    target_h = 0
    img_infos = []
    
    for label, png_path in [("GİRİŞ", giris_png), ("ÇIKIŞ", cikis_png)]:
        if png_path and os.path.isfile(png_path):
            img = ImageReader(png_path)
            iw, ih = img.getSize()
            scale = img_w_each / iw
            draw_h = ih * scale
            img_infos.append((label, png_path, iw, ih, draw_h, scale))
            target_h = max(target_h, draw_h)
    
    # Başlık alanı + kenar boşlukları
    title_h = 60
    krom_h = title_h + 2 * margin + 40          # görüntü dışı sabit yükseklik
    total_h = target_h + krom_h

    # EMNİYET KEMERİ: sayfa PDF üst sınırını aşarsa görüntüleyici KIRPAR (istenen
    # davranış "kesme yok"). Kırpmak yerine her iki görüntüyü de AYNI oranda
    # küçült — en/boy oranı ve sol=giriş/sağ=çıkış düzeni korunur, içerik tam kalır.
    if total_h > _PDF_MAX_PT:
        kucult = (_PDF_MAX_PT - krom_h) / target_h
        img_infos = [(lb, p, iw, ih, dh * kucult, sc * kucult)
                     for (lb, p, iw, ih, dh, sc) in img_infos]
        img_w_each *= kucult
        gap *= kucult
        target_h *= kucult
        total_h = _PDF_MAX_PT
        print(f"[pdf-kanit] sayfa {_PDF_MAX_PT:.0f}pt sinirini asiyordu — "
              f"tum gorseller x{kucult:.3f} kucultuldu (kirpma YOK)")
    
    # Yeni sayfa oluştur - çok uzun sayfa (ReportLab destekliyor)
    c.showPage()
    c.setPageSize((page_w, total_h))
    
    # Başlık çiz
    c.setFont(SANS_SB, 11)
    c.setFillColor(RAIL)
    
    if has_giris and has_cikis:
        # İki başlık yan yana
        left_x = margin
        right_x = margin + img_w_each + gap
        c.drawString(left_x, total_h - margin - 10, "GİRİŞ JENERİĞİ OKUMA KANITI (MASTER SLIT)")
        c.drawString(right_x, total_h - margin - 10, "ÇIKIŞ JENERİĞİ OKUMA KANITI (MASTER SLIT)")
        hair(c, total_h - margin - 16, left_x, left_x + img_w_each, color=ACCENT, w=1.5)
        hair(c, total_h - margin - 16, right_x, right_x + img_w_each, color=ACCENT, w=1.5)
    elif has_giris:
        c.drawString(margin, total_h - margin - 10, "GİRİŞ JENERİĞİ OKUMA KANITI (MASTER SLIT)")
        hair(c, total_h - margin - 16, margin, margin + img_w_each, color=ACCENT, w=1.5)
    else:
        c.drawString(margin, total_h - margin - 10, "ÇIKIŞ JENERİĞİ OKUMA KANITI (MASTER SLIT)")
        hair(c, total_h - margin - 16, margin, margin + img_w_each, color=ACCENT, w=1.5)
    
    # Görüntüleri çiz - orijinal çözünürlükte, sadece genişlik ölçekli
    y_base = total_h - margin - title_h
    for i, (label, png_path, iw, ih, draw_h, scale) in enumerate(img_infos):
        if has_giris and has_cikis:
            x = margin if i == 0 else margin + img_w_each + gap
        else:
            x = margin
        
        # Doğrudan PNG dosyasını çiz (geçici dosya yok, resize yok)
        c.drawImage(png_path, x, y_base - draw_h, width=img_w_each, height=draw_h)



FILM = dict(
    profile="FİLM",
    date="31.05.2026  ·  14:32",
    title="BAŞLANGIÇ",
    subtitle="INCEPTION",
    poster=OUT + r"\afis_inception.jpg",
    specs=[("ÇÖZÜNÜRLÜK", "1920×1080"), ("TÜR", "BİLİM KURGU"),
           ("TOPLAM SÜRE", "02:28:00"), ("TRT KİMLİK", "2010-0147-1-0000-00-1")],
    keywords="LEONARDO DICAPRIO ; JOSEPH GORDON-LEVITT ; ELLIOT PAGE ; TOM HARDY ; "
             "KEN WATANABE ; MARION COTILLARD ; CILLIAN MURPHY ; MICHAEL CAINE",
    cast=["LEONARDO DICAPRIO", "JOSEPH GORDON-LEVITT", "ELLIOT PAGE", "TOM HARDY",
          "KEN WATANABE", "MARION COTILLARD", "CILLIAN MURPHY", "MICHAEL CAINE"],
    crew=[("Yapımcı", ["EMMA THOMAS", "CHRISTOPHER NOLAN"]),
          ("Yönetmen", "CHRISTOPHER NOLAN")],
    ozet="Rüyalara girerek insanların zihnindeki fikirleri çalan usta bir hırsıza, bu kez "
         "çok daha zor bir görev verilir: bir hedefin bilinçaltına sıfırdan bir fikir "
         "yerleştirmek. Ekibiyle birlikte rüyanın içindeki rüyalara inen kahraman, her "
         "katmanda zamanın ve gerçekliğin kurallarının değiştiği bu yolculukta düş ile "
         "gerçek arasındaki sınırı yitirme tehlikesiyle yüzleşir.",
)

DIZI = dict(
    profile="DİZİ",
    date="31.05.2026  ·  14:35",
    title="BİZİM EVİN HALLERİ",
    bolum="13. BÖLÜM",
    poster=OUT + r"\afis_bizimevinhalleri.jpg",
    specs=[("ÇÖZÜNÜRLÜK", "720×576"), ("TÜR", "AİLE"),
           ("TOPLAM SÜRE", "00:45:20"), ("TRT KİMLİK", "1998-0042-0-0013-00-1")],
    keywords="AYŞE YILDIZ ; KEMAL DEMİR ; FATMA ŞEN ; HASAN KAYA ; ZEYNEP AK",
    cast=["AYŞE YILDIZ", "KEMAL DEMİR", "FATMA ŞEN", "HASAN KAYA", "ZEYNEP AK"],
    crew=[("Yapımcı", "MEHMET ÖZ"), ("Yönetmen", "SELİM AK"),
          ("Yönetmen Yardımcısı", "DENİZ ER"), ("Görüntü Yönetmeni", "CAN YILMAZ"),
          ("Kameraman", ["BURAK ŞAHİN", "ONUR KOÇ"]), ("Kameraman Yardımcısı", "EGE TAŞ"),
          ("Kurgu", "NUR ARSLAN")],
    ozet="Kalabalık bir ailenin aynı çatı altında yaşadığı gündelik telaş, bu bölümde "
         "beklenmedik bir komşu ziyaretiyle tatlı bir kargaşaya dönüşür. Yanlış "
         "anlaşılmalar büyürken herkes kendi planının peşine düşer; akşam yemeğinde ise "
         "biriken tüm sırlar tek tek masaya yatar.",
)

def safe_build(name, data):
    try:
        build(OUT + "\\" + name + ".pdf", data)
        return name
    except PermissionError:
        alt = name + "_yeni"
        build(OUT + "\\" + alt + ".pdf", data)
        print("KİLİTLİ (dosya açık olabilir) ->", alt + ".pdf")
        return alt


if __name__ == "__main__":
    import fitz
    for nm, data in [("Ornek_FILM", FILM), ("Ornek_DIZI", DIZI)]:
        out = safe_build(nm, data)
        fitz.open(OUT + rf"\{out}.pdf")[0].get_pixmap(dpi=150).save(OUT + rf"\_pv_{out}.png")
    print("bitti")
