# -*- coding: utf-8 -*-
"""MITAS kunye belgesi - SABIT tasarim (altin 'Dosya', logosuz).
Hem Film hem Dizi uretir. Temsili veri."""
import math
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit, ImageReader
from reportlab.lib.colors import HexColor

OUT = r"E:\MITAS\OCR-worktree\pdf-mitas"
F = r"C:\Windows\Fonts"

pdfmetrics.registerFont(TTFont("AR", F + r"\arial.ttf"))
pdfmetrics.registerFont(TTFont("ARB", F + r"\arialbd.ttf"))


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


def build(path, d):
    c = canvas.Canvas(path, pagesize=A4)

    c.setFillColor(RAIL)
    c.rect(0, 0, RW, PAGE_H, fill=1, stroke=0)
    c.rect(0, 0, PAGE_W, FOOT_H, fill=1, stroke=0)

    # Amblem (yazi)
    c.setFillColor(CREAM)
    c.setFont(SERIF_B, 18)
    c.drawString(RM, PAGE_H - 48, "MİTAS")
    c.setFillColor(ACCENT)
    c.rect(RM, PAGE_H - 60, 34, 2.4, fill=1, stroke=0)
    tracked(c, RM, PAGE_H - 76, "İÇERİK KÜNYE BELGESİ", SANS_SB, 6.6, CREAM_M, 1.5)

    # Sol panel: afiş varsa afiş (çerçeve afişin oranına göre), yoksa anahtar-kare placeholder
    pw = RW - 2 * RM
    ptop = PAGE_H - 96
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

    # SES & ALTYAZI (sol ray — frame'in yerine; kanal-dil + altyazı tespiti)
    if d.get("ses_kanallari") or d.get("altyazi"):
        sb = panel_bottom - 22
        tracked(c, RM, sb, "SES & ALTYAZI", SANS_SB, 6.8, ACCENT, 1.4)
        sb -= 19
        for i, l in enumerate(d.get("ses_kanallari", []), 1):
            tracked(c, RM, sb, f"{i}. KANAL", SANS_SB, 6.2, CREAM_M, 1.1)
            c.setFillColor(CREAM)
            c.setFont(SANS_SB, 9.5)
            c.drawString(RM + 60, sb - 1, str(l))
            sb -= 16
        sb -= 6
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
        tracked(c, RM, 46, _stamp, SANS_SB, 6.6, ACCENT, 1.3)

    c.setFillColor(CREAM_M)
    c.setFont(SANS, 7.6)
    c.drawString(X0, FOOT_H / 2.0 - 3, "Otomatik üretilmiş künye belgesi")
    c.drawRightString(XR, FOOT_H / 2.0 - 3, "Sayfa  1 / 1")

    # ---- Sag icerik ----
    c.setFillColor(MUTE)
    c.setFont(SANS, 8.5)
    c.drawRightString(XR, PAGE_H - 46, "Üretim:  " + d["date"])
    # cozunurluk: Uretim'in hemen altinda, SILIK
    _res = next((v for l, v in d["specs"] if ("ÖZÜNÜR" in l.upper() or "OZUNUR" in l.upper()) and v and v != "—"), None)
    if _res:
        c.setFillColor(CREAM_M)
        c.setFont(SANS, 7.3)
        c.drawRightString(XR, PAGE_H - 57, _res)

    ty = PAGE_H - 92
    chip_w = pdfmetrics.stringWidth(d["profile"], SANS_SB, 8) + 1.5 * (len(d["profile"]) - 1) + 20
    c.setStrokeColor(ACCENT)
    c.setLineWidth(0.9)
    c.roundRect(X0, ty, chip_w, 17, 8.5, stroke=1, fill=0)
    tracked(c, X0 + 10, ty + 5, d["profile"], SANS_SB, 8, ACCENT, 1.5)
    ty -= 34

    title = d["title"]
    ts = 35
    while ts > 22 and pdfmetrics.stringWidth(title, SERIF_B, ts) > CW:
        ts -= 1
    c.setFillColor(INK)
    c.setFont(SERIF_B, ts)
    if pdfmetrics.stringWidth(title, SERIF_B, ts) <= CW:
        c.drawString(X0, ty, title)
        ty -= (ts - 10)
    else:  # hâlâ sığmıyorsa 2+ satıra sar (sağ kenardan taşmayı önler)
        for _ln in simpleSplit(title, SERIF_B, ts, CW):
            c.drawString(X0, ty, _ln)
            ty -= (ts - 3)
        ty -= 7
    if d.get("subtitle"):
        c.setFillColor(MUTE)
        c.setFont(SERIF_I, 13.5)
        c.drawString(X0, ty, d["subtitle"])
        ty -= 18
    elif d.get("bolum"):
        tracked(c, X0, ty, d["bolum"], SANS_SB, 10.5, MUTE, 1.6)
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
    for ln in simpleSplit(d["keywords"], SANS, 9.5, CW):
        c.setFont(SANS, 9.5)
        c.setFillColor(BODY)
        c.drawString(X0, ty, ln)
        ty -= 15

    section("OYUNCULAR")
    cast = d["cast"]
    half = math.ceil(len(cast) / 2)
    y0 = ty
    for i, name in enumerate(cast):
        col, row = (0, i) if i < half else (1, i - half)
        c.setFont(SANS, 10)
        c.setFillColor(INK)
        c.drawString(X0 + (0 if col == 0 else 168), y0 - row * 18, name)
    ty = y0 - half * 18

    section("YAPIM EKİBİ")
    for role, name in d["crew"]:
        names = name if isinstance(name, (list, tuple)) else [name]
        c.setFont(SANS, 9)
        c.setFillColor(MUTE)
        c.drawString(X0, ty, role)  # rol etiketi yalnız ilk satırda
        for nm in names:
            c.setFont(SANS_SB, 10)
            c.setFillColor(INK)
            c.drawString(X0 + 130, ty, nm)
            ty -= 17

    ty -= 16
    oz_size, oz_lh = 10.5, 16.0
    while True:  # özeti sayfaya sığdır (alta taşmayı önler)
        lines = simpleSplit(d["ozet"], SANS, oz_size, CW - 34)
        panel_h = 42 + len(lines) * oz_lh
        if ty - panel_h >= FOOT_H + 10 or oz_size <= 7.5:
            break
        oz_size -= 0.5
        oz_lh -= 0.5
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

    c.showPage()
    c.save()
    print("yazildi:", path)


FILM = dict(
    profile="FİLM",
    date="31.05.2026  ·  14:32",
    title="BAŞLANGIÇ",
    subtitle="INCEPTION",
    poster=OUT + r"\afis_inception.jpg",
    specs=[("ÇÖZÜNÜRLÜK", "1920×1080"), ("KARE HIZI", "24 fps"),
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
    specs=[("ÇÖZÜNÜRLÜK", "720×576"), ("KARE HIZI", "25 fps"),
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
