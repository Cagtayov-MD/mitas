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
    c.drawRightString(XR, PAGE_H - 46, "ÜRETİM:  " + d["date"])
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
    if d.get("bolum"):                              # elif->if: dizi bolumu subtitle olsa da bassin
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

    # FİLM NOTU kutusu (2026-07-04, Çağatay): sağ içeriğin altında, ÖZET'ten hemen önce.
    # Deterministik standart notlar (animasyon-seslendirme / sessiz-özet-yok / jenerik-yok / XML-uyarı).
    # d["film_notu"] boşsa HİÇ çizilmez (mevcut düzen birebir korunur). ÖZET'in kendi sığdırma
    # döngüsü kalan alana göre küçüldüğünden taşma güvenliği otomatik.
    _notlar = [str(x).strip() for x in (d.get("film_notu") or []) if str(x).strip()]
    if _notlar:
        ty -= 14
        nt_size, nt_lh = 8.8, 13.0
        nt_lines = []
        for _n in _notlar[:4]:                        # en fazla 4 not (taşma güvenliği)
            nt_lines += simpleSplit("•  " + _n, SANS, nt_size, CW - 36)
        nt_h = 34 + len(nt_lines) * nt_lh
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

    if not (d.get("ozet") or "").strip():   # özet boşsa panel hiç çizilmez (2026-07-24)
        c.showPage()
        c.save()
        print("yazildi:", path)
        return
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


# PDF sayfa kenarı üst sınırı (points). PDF spec/Acrobat 200 inch = 14400pt üstünü
# güvenilir işlemez; aşan sayfa görüntüleyicide kırpılır. Normal jeneriklerde
# ulaşılmaz (en uzun ölçülen master ~12000pt) — bu yalnızca emniyet kemeri.
_PDF_MAX_PT = 14400.0


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
