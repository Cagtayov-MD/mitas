# -*- coding: utf-8 -*-
"""MITAS Cikti Sureci akis semasi - asenkron batch ozet + durum makinesi."""
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

DARK = HexColor("#19222E"); GOLD = HexColor("#C2A14D"); CREAM = HexColor("#F1EEE6")
CREAM_M = HexColor("#9DA8B4"); INK = HexColor("#1C2531"); MUTE = HexColor("#6B7785")
HAIR = HexColor("#E4E7EC"); ARROW = HexColor("#9AA6B2")
AMBER = HexColor("#D2922A"); AMBER_BG = HexColor("#FBF3E0"); AMBER_BOX = HexColor("#FCF6E8"); AMBER_TX = HexColor("#9C6A12")
GOLDFILL = HexColor("#C2A14D"); BLUE_BG = HexColor("#EAF0FB"); BLUE_BD = HexColor("#6B8FC0"); BLUE_TX = HexColor("#2B4E80")
NEU_BG = HexColor("#F4F6F8"); NEU_BD = HexColor("#B7C0CA"); NEU_TX = HexColor("#2A3340")

PW, PH = landscape(A4)
ML = 28


def tracked(c, x, y, text, font, size, color, sp, center=False, right=False):
    w = pdfmetrics.stringWidth(text, font, size) + sp * max(len(text) - 1, 0)
    if center: x -= w / 2.0
    elif right: x -= w
    to = c.beginText(x, y); to.setFont(font, size); to.setFillColor(color)
    to.setCharSpace(sp); to.textOut(text); to.setCharSpace(0); c.drawText(to)
    return w


def box(c, x, cy, w, h, lines, fill, border, t1, t2):
    c.setFillColor(fill); c.setStrokeColor(border); c.setLineWidth(1.1)
    c.roundRect(x, cy - h / 2.0, w, h, 6, fill=1, stroke=1)
    yy = cy + (len(lines) - 1) * 5.5 + 2
    for i, ln in enumerate(lines):
        if i == 0:
            c.setFont(SANS_SB, 8.6); c.setFillColor(t1)
        else:
            c.setFont(SANS, 7.4); c.setFillColor(t2)
        c.drawCentredString(x + w / 2.0, yy, ln); yy -= 11


def arrow(c, x1, x2, cy, label=None):
    c.setStrokeColor(ARROW); c.setLineWidth(1.1)
    c.line(x1, cy, x2 - 4, cy)
    p = c.beginPath(); p.moveTo(x2 - 6, cy + 3.4); p.lineTo(x2, cy); p.lineTo(x2 - 6, cy - 3.4)
    c.drawPath(p, stroke=1, fill=0)
    if label:
        tracked(c, (x1 + x2) / 2.0, cy + 8, label, SANS_SB, 6.3, AMBER_TX, 0.3, center=True)


def pill(c, x, cy, label, fill, bd, tx):
    w = pdfmetrics.stringWidth(label, SANS_SB, 8) + 26
    h = 22
    c.setFillColor(fill); c.setStrokeColor(bd); c.setLineWidth(1.0)
    c.roundRect(x, cy - h / 2.0, w, h, h / 2.0, fill=1, stroke=1)
    c.setFont(SANS_SB, 8); c.setFillColor(tx)
    c.drawCentredString(x + w / 2.0, cy - 3, label)
    return w


def build(path):
    c = canvas.Canvas(path, pagesize=landscape(A4))

    bh = 66
    c.setFillColor(DARK); c.rect(0, PH - bh, PW, bh, fill=1, stroke=0)
    c.setFillColor(GOLD); c.rect(0, PH - bh - 3, PW, 3, fill=1, stroke=0)
    c.setFillColor(CREAM); c.setFont(SERIF_B, 14); c.drawString(ML, PH - 28, "MİTAS")
    c.setFillColor(GOLD); c.rect(ML, PH - 35, 24, 2, fill=1, stroke=0)
    c.setFillColor(CREAM); c.setFont(SERIF_B, 19); c.drawString(ML, PH - 55, "Çıktı Süreci")
    tracked(c, ML + 150, PH - 53, "ASENKRON BATCH ÖZET · TOPLU/GECİKMELİ ÇIKTI", SANS_SB, 7.4, CREAM_M, 1.5)
    tracked(c, PW - ML, PH - 40, "ÖZET = SONNET BATCHES API", SANS_SB, 8, GOLD, 1.4, right=True)

    # ---- Ana akis ----
    n = 7; bw, gap = 100.0, 14.0
    xs = [ML + i * (bw + gap) for i in range(n)]
    cy = 415; h = 62
    bx0 = xs[3] - 12; bx1 = xs[5] + bw + 12
    c.setFillColor(AMBER_BG); c.roundRect(bx0, cy - h / 2.0 - 22, bx1 - bx0, h + 44, 8, fill=1, stroke=0)
    tracked(c, (bx0 + bx1) / 2.0, cy + h / 2.0 + 11, "ASENKRON · BATCH · GECİKMELİ", SANS_SB, 7, AMBER_TX, 1.6, center=True)
    tracked(c, (bx0 + bx1) / 2.0, cy - h / 2.0 - 16, "paket, özet dönene kadar bekler · sonuç batch bitince topluca gelir", SANS, 6.6, AMBER_TX, 0.3, center=True)

    nodes = [
        (["GİRDİ", "medya", "dosya adı"], "n"),
        (["YEREL İŞLEME", "ASR · OCR", "ffmpeg · afiş"], "n"),
        (["PAKET", "özet HARİÇ", "hazır → bekler"], "wait"),
        (["ÖZET BATCH", "N = 10 / 20", "custom_id"], "a"),
        (["SONNET", "BATCHES API", "async · %50"], "a"),
        (["ÖZET", "sonuç", "→ eşle"], "a"),
        (["BİRLEŞTİR", "+ özet", "PDF ÇIKTI"], "pdf"),
    ]
    for i, (lines, kind) in enumerate(nodes):
        if kind == "a": box(c, xs[i], cy, bw, h, lines, AMBER_BOX, AMBER, AMBER_TX, AMBER_TX)
        elif kind == "pdf": box(c, xs[i], cy, bw, h, lines, GOLDFILL, HexColor("#A8862F"), HexColor("#241A05"), HexColor("#3a2c08"))
        elif kind == "wait": box(c, xs[i], cy, bw, h, lines, HexColor("#F6F5F1"), GOLD, INK, MUTE)
        else: box(c, xs[i], cy, bw, h, lines, HexColor("#FFFFFF"), GOLD, INK, MUTE)
    for i in range(n - 1):
        arrow(c, xs[i] + bw, xs[i + 1], cy, "tetik: N / süre" if i == 2 else None)

    # ---- Durum makinesi ----
    c.setStrokeColor(HAIR); c.setLineWidth(0.6); c.line(ML, 318, PW - ML, 318)
    tracked(c, ML, 300, "ASSET DURUM MAKİNESİ", SANS_SB, 8, GOLD, 1.8)
    states = [
        ("NEW", NEU_BG, NEU_BD, NEU_TX), ("İŞLENİYOR", NEU_BG, NEU_BD, NEU_TX),
        ("ÖZET BEKLİYOR", AMBER_BOX, AMBER, AMBER_TX), ("BATCH'TE", AMBER_BOX, AMBER, AMBER_TX),
        ("ÖZET GELDİ", BLUE_BG, BLUE_BD, BLUE_TX), ("PDF HAZIR", GOLDFILL, HexColor("#A8862F"), HexColor("#241A05")),
    ]
    widths = [pdfmetrics.stringWidth(s[0], SANS_SB, 8) + 26 for s in states]
    total = sum(widths) + 20 * (len(states) - 1)
    x = (PW - total) / 2.0; cys = 258
    for i, (lbl, fill, bd, tx) in enumerate(states):
        if i > 0:
            arrow(c, x, x + 20, cys); x += 20
        x += pill(c, x, cys, lbl, fill, bd, tx)

    # ---- Alt not ----
    c.setStrokeColor(HAIR); c.setLineWidth(0.6); c.line(ML, 196, PW - ML, 196)
    c.setFillColor(MUTE); c.setFont(SANS, 8)
    c.drawString(ML, 178, "Hızlı/yerel (dakikalar): ASR · OCR · ffmpeg · afiş  →  paket.    Yavaş/bulut (asenkron): transcript → Sonnet batch → özet.")
    c.drawString(ML, 162, "Çıktı en yavaşı bekler → paketler havuzda birikir, batch bitince N'li grup hâlinde PDF'e döner.  Durum diskte tutulur (restart-safe).")

    c.setStrokeColor(HAIR); c.setLineWidth(0.6); c.line(ML, 30, PW - ML, 30)
    c.setFillColor(MUTE); c.setFont(SANS, 7.2)
    c.drawString(ML, 18, "MİTAS · Çıktı süreci · taslak")
    c.drawRightString(PW - ML, 18, "2026-06-01")

    c.showPage(); c.save()
    print("yazildi:", path)


build(OUT + r"\Cikti_Sureci_Semasi.pdf")
import fitz
fitz.open(OUT + r"\Cikti_Sureci_Semasi.pdf")[0].get_pixmap(dpi=160).save(OUT + r"\_pv_cikti.png")
print("bitti")
