# -*- coding: utf-8 -*-
"""MITAS Profil AKIS SEMASI - her profil bir modul zinciri (yatay A4)."""
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

OUT = r"E:\MITAS\OCR-worktree\pdf-mitas"
F = r"C:\Windows\Fonts"
pdfmetrics.registerFont(TTFont("AR", F + r"\arial.ttf"))
pdfmetrics.registerFont(TTFont("ARB", F + r"\arialbd.ttf"))


def tf(n, p, fb):
    try:
        pdfmetrics.registerFont(TTFont(n, p)); return n
    except Exception:
        return fb


SERIF_B = tf("Georgia-Bold", F + r"\georgiab.ttf", "ARB")
SANS = tf("Segoe", F + r"\segoeui.ttf", "AR")
SANS_SB = tf("Segoe-SB", F + r"\seguisb.ttf", "ARB")

DARK = HexColor("#19222E")
GOLD = HexColor("#C2A14D")
CREAM = HexColor("#F1EEE6")
CREAM_M = HexColor("#9DA8B4")
INK = HexColor("#1C2531")
MUTE = HexColor("#7B8794")
HAIR = HexColor("#E4E7EC")
ARROW = HexColor("#9AA6B2")

STYLE = {
    "asr":    (HexColor("#EDF0F4"), HexColor("#8A95A2"), HexColor("#2A3340"), False),
    "dia":    (HexColor("#E9F0FB"), HexColor("#3F6FB0"), HexColor("#2B4E80"), False),
    "credit": (HexColor("#F7F0DE"), HexColor("#C2A14D"), HexColor("#7A6326"), False),
    "ozet":   (HexColor("#E8F3EC"), HexColor("#2E8B57"), HexColor("#1F6B41"), False),
    "q":      (HexColor("#FBF2DD"), HexColor("#D2922A"), HexColor("#9C6A12"), True),
    "out":    (HexColor("#EFF2F5"), HexColor("#8A95A2"), HexColor("#2A3340"), False),
    "pdf":    (HexColor("#C2A14D"), HexColor("#A8862F"), HexColor("#241A05"), False),
}

PW, PH = landscape(A4)
ML = 36
XP = 40          # profil kapsulu sol
WP = 100         # profil kapsul genisligi
XM = XP + WP + 20
XOUT = 596       # cikti kapsul sol kenari (sabit kolon)

# profil, [(label, key)...], (cikti_label, cikti_key), tanimli?
LANES = [
    ("STT", [("ASR", "asr")], ("Transcript", "out"), True),
    ("Haber", [("ASR", "asr"), ("Konuşmacı", "dia"), ("KJ OCR ?", "q"), ("Özet ?", "q")], ("Transcript", "out"), False),
    ("Stüdyo", [("ASR", "asr"), ("Konuşmacı", "dia"), ("Özet ?", "q")], ("Transcript", "out"), False),
    ("Müzik / Eğlence", [("ASR", "asr"), ("Konuşmacı", "dia"), ("Şarkı ?", "q"), ("Özet ?", "q")], ("Transcript", "out"), False),
    ("Spor", [("ASR", "asr"), ("KJ OCR ?", "q"), ("Özet", "ozet")], ("Transcript + Özet", "out"), False),
    ("Belgesel", [("ASR", "asr"), ("Özet ?", "q")], ("Transcript", "out"), False),
    ("Film", [("ASR", "asr"), ("Credit OCR", "credit"), ("Özet", "ozet")], ("PDF Künye", "pdf"), True),
    ("Dizi", [("ASR", "asr"), ("Credit OCR", "credit"), ("Özet", "ozet")], ("PDF Künye", "pdf"), True),
]


def ctext(c, cx, cy, text, font, size, color):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawCentredString(cx, cy - size / 2.0 + 1, text)


def pill(c, x, cy, label, key, h=21, fixedw=None):
    bg, bd, tx, dashed = STYLE[key]
    w = fixedw or (pdfmetrics.stringWidth(label, SANS_SB, 8.3) + 22)
    c.setFillColor(bg)
    c.setStrokeColor(bd)
    c.setLineWidth(1.1)
    c.setDash([2.4, 1.9], 0) if dashed else c.setDash([], 0)
    c.roundRect(x, cy - h / 2.0, w, h, h / 2.0, fill=1, stroke=1)
    c.setDash([], 0)
    ctext(c, x + w / 2.0, cy, label, SANS_SB, 8.3, tx)
    return x + w


def arrow(c, x1, x2, cy):
    c.setStrokeColor(ARROW)
    c.setLineWidth(1.0)
    c.setDash([], 0)
    c.line(x1, cy, x2 - 3.5, cy)
    p = c.beginPath()
    p.moveTo(x2 - 5.5, cy + 3.2)
    p.lineTo(x2, cy)
    p.lineTo(x2 - 5.5, cy - 3.2)
    c.drawPath(p, stroke=1, fill=0)


def prof_pill(c, x, cy, label, tanimli):
    h = 26
    c.setFillColor(DARK)
    c.setStrokeColor(GOLD if tanimli else DARK)
    c.setLineWidth(1.4 if tanimli else 0)
    c.setDash([], 0)
    c.roundRect(x, cy - h / 2.0, WP, h, 5, fill=1, stroke=1)
    size = 9.5 if pdfmetrics.stringWidth(label, SANS_SB, 9.5) < WP - 12 else 8
    ctext(c, x + WP / 2.0, cy, label, SANS_SB, size, CREAM)


def build(path):
    c = canvas.Canvas(path, pagesize=landscape(A4))

    bh = 72
    c.setFillColor(DARK); c.rect(0, PH - bh, PW, bh, fill=1, stroke=0)
    c.setFillColor(GOLD); c.rect(0, PH - bh - 3, PW, 3, fill=1, stroke=0)
    c.setFillColor(CREAM); c.setFont(SERIF_B, 14)
    c.drawString(ML, PH - 28, "MİTAS")
    c.setFillColor(GOLD); c.rect(ML, PH - 35, 24, 2, fill=1, stroke=0)
    c.setFillColor(CREAM); c.setFont(SERIF_B, 20)
    c.drawString(ML, PH - 57, "Profil Akış Şeması")
    to = c.beginText(ML + 210, PH - 55); to.setFont(SANS_SB, 7.5); to.setFillColor(CREAM_M)
    to.setCharSpace(1.6); to.textOut("GİRDİ → PROFİL → MODÜL ZİNCİRİ → ÇIKTI"); c.drawText(to)
    to = c.beginText(PW - ML - 168, PH - 34); to.setFont(SANS_SB, 8); to.setFillColor(GOLD)
    to.setCharSpace(1.4); to.textOut("FİLM & DİZİ TANIMLI"); c.drawText(to)

    # kolon basliklari
    gy = PH - bh - 16
    for lbl, gx in [("PROFİL", XP), ("MODÜL AKIŞI", XM), ("ÇIKTI", XOUT)]:
        to = c.beginText(gx, gy); to.setFont(SANS_SB, 7); to.setFillColor(MUTE)
        to.setCharSpace(1.5); to.textOut(lbl); c.drawText(to)

    y0 = PH - bh - 30
    lh = 52
    for i, (name, chain, (olbl, okey), tanimli) in enumerate(LANES):
        cy = y0 - i * lh - lh / 2.0
        if tanimli:
            c.setFillColor(HexColor("#FAF6EA"))
            c.rect(XP - 8, cy - lh / 2.0 + 4, PW + 8 + 8, lh - 8, fill=1, stroke=0)
        prof_pill(c, XP, cy, name, tanimli)
        x = XM
        prev = XP + WP
        arrow(c, prev, x, cy)
        for j, (lbl, key) in enumerate(chain):
            if j > 0:
                nx = x + 16
                arrow(c, x, nx, cy)
                x = nx
            x = pill(c, x, cy, lbl, key)
        arrow(c, x, XOUT, cy)
        pill(c, XOUT, cy, olbl, okey)
        if i < len(LANES) - 1:
            c.setStrokeColor(HAIR); c.setLineWidth(0.4); c.setDash([], 0)
            c.line(XP - 8, cy - lh / 2.0, PW - ML, cy - lh / 2.0)

    # Lejant
    ly = y0 - len(LANES) * lh - 16
    x = pill(c, XP, ly, "dolu = tanımlı modül", "asr")
    x = pill(c, x + 18, ly, "kesik ? = belirlenecek", "q")
    pill(c, x + 18, ly, "PDF Künye", "pdf")
    to = c.beginText(PW - ML, ly - 3); to.setFont(SANS, 7.6); to.setFillColor(MUTE)
    txt = "Film & Dizi tanımlı. '?' kapsüller bu şemada birlikte belirlenecek."
    w = pdfmetrics.stringWidth(txt, SANS, 7.6)
    to2 = c.beginText(PW - ML - w, ly - 3); to2.setFont(SANS, 7.6); to2.setFillColor(MUTE)
    to2.textOut(txt); c.drawText(to2)

    c.setStrokeColor(HAIR); c.setLineWidth(0.6); c.line(ML, 28, PW - ML, 28)
    c.setFillColor(MUTE); c.setFont(SANS, 7.2)
    c.drawString(ML, 17, "MİTAS · Profil akış şeması · taslak")
    c.drawRightString(PW - ML, 17, "2026-05-31")

    c.showPage(); c.save()
    print("yazildi:", path)


build(OUT + r"\Profil_Akis_Semasi.pdf")
import fitz
fitz.open(OUT + r"\Profil_Akis_Semasi.pdf")[0].get_pixmap(dpi=160).save(OUT + r"\_pv_diag.png")
print("bitti")
