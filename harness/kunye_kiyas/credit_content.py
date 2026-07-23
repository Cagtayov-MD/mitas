"""OCR-içerik ayırıcı — kredi vs ara-yazı/tabela/sahne-metni.

Konsey (GLM, 2026-07-21): kutu var/yok YETMEZ, metni OKU. Kredi = isim-listesi
(Title Case + BÜYÜK-HARF isimler, rol-keyword), ara-yazı = tek cümle, tabela =
0-birkaç kelime. Test doğruladı: BILLY kredi 11-satır cast, ara-yazı 1-cümle.

PaddleOCR rec sadece ADAY karelerde (birkaç), maliyet düşük.
"""
from __future__ import annotations

import re

_OCR = None

# rol/görev keyword'leri (EN + TR)
_ROL = re.compile(
    r"\b(director|directed|produc|screenplay|written|writer|story|music|"
    r"photograph|cinematograph|edit|editor|cast|starring|art|costume|sound|"
    r"camera|design|makeup|make-up|producer|executive|associate|assistant|"
    r"yönet|yapım|senaryo|görüntü|müzik|kurgu|oyuncu|kostüm|montaj|ses)\b",
    re.I)


def _ocr():
    global _OCR
    if _OCR is None:
        from paddleocr import PaddleOCR
        _OCR = PaddleOCR(use_textline_orientation=False, lang="en")
    return _OCR


def satirlar(frame_path: str) -> list[str]:
    r = _ocr().predict(frame_path)
    if not r or not r[0]:
        return []
    rr = r[0]
    txt = rr.get("rec_texts", []) if isinstance(rr, dict) else []
    return [t.strip() for t in txt if t and t.strip()]


def _isim_gibi(satir: str) -> bool:
    """Bir satır kredi-satırı mı (isim/rol) yoksa cümle/gürültü mü."""
    s = satir.strip().strip('"“”\'')
    if len(s) < 2:
        return False
    # rol keyword → kredi
    if _ROL.search(s):
        return True
    kelimeler = s.split()
    if not kelimeler:
        return False
    # cümle işareti (ara-yazı: "...cuff." gibi) → kredi DEĞİL
    if s.endswith((".", "?", "!")) and len(kelimeler) >= 4:
        kucuk = sum(1 for w in kelimeler if w and w[0].islower())
        if kucuk >= 2:            # birden fazla küçük-harf başlangıç = cümle
            return False
    # BÜYÜK-HARF isim (PAUL FIX) veya Title Case (Doc Cushman)
    buyuk = sum(1 for w in kelimeler if len(w) >= 2 and w.isupper())
    title = sum(1 for w in kelimeler if len(w) >= 2 and w[0].isupper() and not w.isupper())
    return buyuk >= 1 or title >= 2


def kredi_benzeri(satir_listesi: list[str]) -> float:
    """Tek-kare skoru (geriye-uyum). Çoklu-kare için kredi_skoru_coklu kullan."""
    if not satir_listesi:
        return 0.0
    n = len(satir_listesi)
    isim = sum(1 for s in satir_listesi if _isim_gibi(s))
    return round((isim / n) * min(1.0, n / 3.0), 3)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def isim_sayisi(satir_listesi: list[str]) -> int:
    """Bir karede isim-benzeri satır sayısı."""
    return sum(1 for s in satir_listesi if _isim_gibi(s))


def _tek_isim_sutunu(satir: str) -> bool:
    """Tek-kelimelik Title-case satır (isim-sütunu üyesi): 'Christine' / 'McTeer'.

    Kart-başına-tek-oyuncu düzeninde her satır TEK kelime olur; _isim_gibi bunu
    kaçırır (≥2 title-kelime ister). BÜYÜK-HARF tek kelime zaten _isim_gibi'de
    sayılır — burada yalnız Title-case tekiller (çifte sayım yok)."""
    p = satir.strip().strip('"“”\'').split()
    if len(p) != 1:
        return False
    w = p[0]
    return len(w) >= 3 and w[0].isupper() and w.isalpha() and not w.isupper()


def kredi_karti_mi(satir_listesi: list[str]) -> bool:
    """Tek karenin KREDİ KARTI olup olmadığı (epilog/ara-yazı/ithaf DEĞİL).

    Konsey (GLM tur-2): gerçek ayırıcı yapısal düzen — kredi satırları noktalama
    ile BİTMEZ, rol-keyword veya isim-sütunu taşır; epilog düzyazıdır.

    isim-sütunu ayarı (T5 ölçümü, BAYAN_JULIE regresyonu): tek-kelime Title-case
    satırlar (kart-başına-tek-oyuncu düzeni) isim sayımına eklenir — film-adı
    değil YAPISAL düzen; _isim_gibi'nin ≥2-kelime şartı bu düzeni kaçırıyordu."""
    if not satir_listesi:
        return False
    isim = sum(1 for s in satir_listesi if _isim_gibi(s))
    isim += sum(1 for s in satir_listesi
                if not _isim_gibi(s) and _tek_isim_sutunu(s))
    rol = any(_ROL.search(s) for s in satir_listesi)
    noktali = sum(1 for s in satir_listesi
                  if s.strip().endswith((".", "!", "?", "...")) and len(s.split()) >= 4)
    if noktali >= 2 and not rol:
        return False              # düzyazı kartı (epilog/mektup/ithaf)
    return rol or isim >= 3


def kredi_skoru_coklu(kare_satirlari: list[list[str]], yogun_esik: int = 4) -> float:
    """SÜRDÜRÜLEN yoğunluk skoru — kaç kare ≥yogun_esik isim gösteriyor.

    Kritik ayrım (2026-07-21, doğrulandı): gerçek kredi yoğunluğu SÜRDÜRÜR
    (cast listesi onlarca kare boyunca çok-isimli). Gazete/afiş/arananıyor
    (MODERN "WANTED FOR Vagrancy") TEK-kare yoğun sonra kaybolur; tabela hep
    seyrek. Tek-kare tepe gazeteyi geçiriyordu; sürdürülen-yoğun-kare sayısı
    ayırır. ≥3 yoğun kare → kesin kredi, 1 → gazete insertı."""
    if not kare_satirlari:
        return 0.0
    yogun = sum(1 for s in kare_satirlari if isim_sayisi(s) >= yogun_esik)
    return round(min(1.0, yogun / 3.0), 3)
