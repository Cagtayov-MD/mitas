"""
SES_TEYIT PDF onay aracı.
Her PDF için:
  1. VAR MI? → yönetmen, yapımcı, oyuncu, özet, afiş
  2. DOĞRU MU? → garble/slogan değil, gerçek isim/metin
Geçen PDFleri _onaylı adıyla 'onaylı' alt klasörüne taşır.
"""

import re
import os
import sys
import shutil
from pathlib import Path
from pypdf import PdfReader

# Linux geçişi 2026-07-16: kök env'den (yoksa eski Windows davranışı birebir).
import os as _os
SES_DIR = Path(_os.environ.get("MITAS_PROJECT_ROOT") or r"E:/MITAS") / "Mitas Output" / "export" / "KONTROL" / "SES TEYİT"  # 2026-06-15: KONTROL altına taşındı
ONAY_DIR = SES_DIR / "onaylı"

# Garble belirteci — büyük harfle cümle fragmanları (film sloganı/altyazı tuzağı)
SLOGAN_PATTERN = re.compile(
    r"(KURTULU[ŞS]|HAYATTA KAL|KAPANA|KADER|MUCİZE|TESLIM OL|ETRAFINIZI|FOR A |HOPING FOR|WE SARR)",
    re.IGNORECASE,
)

# Ad-soyadı benzeri: 2-4 büyük kelime, çoğu harf (no '!' '.' soru içermiyor)
NAME_WORD = re.compile(r"^[A-ZÇĞİÖŞÜA-Z][A-ZÇĞİÖŞÜa-zçğışöüñ\-'\.]{1,25}$")


def is_name_like(line: str) -> bool:
    """Satır gerçek isim satırı mı (1-4 büyük kelime, noktalama yok)?"""
    words = line.strip().split()
    if not (1 <= len(words) <= 5):
        return False
    # İçinde '!' veya '?' veya sayı varsa slogan/altyazıdır
    if re.search(r"[!?0-9]", line):
        return False
    # Kelimelerin yarısından fazlası name-like olmalı
    good = sum(1 for w in words if NAME_WORD.match(w))
    return good >= max(1, len(words) // 2)


def extract_section(text: str, start_marker: str, end_markers: list) -> str:
    """text'ten start_marker ile end_markers arasındaki kısmı döndür."""
    idx = text.find(start_marker)
    if idx < 0:
        return ""
    content = text[idx + len(start_marker):]
    for em in end_markers:
        ei = content.find(em)
        if ei >= 0:
            content = content[:ei]
    return content.strip()


def has_poster(reader: PdfReader) -> bool:
    """PDF'de embed image var mı?"""
    try:
        for page in reader.pages:
            if page.images:
                return True
    except Exception:
        pass
    return False


def analyze_pdf(path: Path) -> dict:
    result = {
        "file": path.name,
        "yonetmen": ("", False, ""),
        "yapimci": ("", False, ""),
        "oyuncu": ("", False, ""),
        "ozet": ("", False, ""),
        "afis": False,
        "onay": False,
        "sorunlar": [],
    }

    try:
        reader = PdfReader(str(path))
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
    except Exception as e:
        result["sorunlar"].append(f"PDF okunamadı: {e}")
        return result

    # --- AFİŞ ---
    result["afis"] = has_poster(reader)
    if not result["afis"]:
        result["sorunlar"].append("Afiş (poster) yok")

    # --- ÖZET ---
    ozet = extract_section(text, "ÖZET", ["Sayfa", "Otomatik"])
    # Encoding bozuksa "ZET" ile de dene
    if not ozet:
        ozet = extract_section(text, "ZET\n", ["Sayfa", "Otomatik"])
    ozet_clean = ozet.strip()
    ozet_var = len(ozet_clean) >= 60
    ozet_dogru = ozet_var and not re.search(r"[█▓░]{3,}", ozet_clean)
    result["ozet"] = (ozet_clean[:80], ozet_var, "ok" if ozet_dogru else "çok kısa/garble")
    if not ozet_var:
        result["sorunlar"].append("Özet yok/çok kısa")
    elif not ozet_dogru:
        result["sorunlar"].append("Özet garble")

    # --- YÖNETMENİ ---
    yon = extract_section(text, "netmen\n", ["Yapımcı", "ap", "ZET", "ÖZET"])
    if not yon:
        yon = extract_section(text, "netmen", ["\n\n", "Yapımcı"])
    yon_lines = [l.strip() for l in yon.splitlines() if l.strip()]
    yon_names = [l for l in yon_lines if is_name_like(l)]
    yon_var = len(yon_names) > 0
    result["yonetmen"] = (", ".join(yon_names[:3]), yon_var, "ok" if yon_var else "boş")
    if not yon_var:
        result["sorunlar"].append("Yönetmen boş")

    # --- YAPIMCI ---
    yap = extract_section(text, "Yapımcı\n", ["ZET", "ÖZET", "Sayfa"])
    if not yap:
        yap = extract_section(text, "ap", ["\n\n", "ZET"])
    yap_lines = [l.strip() for l in yap.splitlines() if l.strip()]
    yap_names = [l for l in yap_lines if is_name_like(l)]
    yap_var = len(yap_names) > 0
    result["yapimci"] = (", ".join(yap_names[:3]), yap_var, "ok" if yap_var else "boş")
    if not yap_var:
        result["sorunlar"].append("Yapımcı boş")

    # --- OYUNCU ---
    # OYUNCULAR → YAPIM EKİBİ arası
    oyu = extract_section(text, "OYUNCULAR\n", ["YAPIM", "Sayfa"])
    if not oyu:
        oyu = extract_section(text, "NCULAR\n", ["YAPIM", "Sayfa"])
    oyu_lines = [l.strip() for l in oyu.splitlines() if l.strip()]
    oyu_names = [l for l in oyu_lines if is_name_like(l)]
    oyu_var = len(oyu_names) >= 1
    # Slogan/garble kontrolü
    slogan_count = sum(1 for l in oyu_lines if SLOGAN_PATTERN.search(l))
    oyu_dogru = oyu_var and (slogan_count == 0 or len(oyu_names) > slogan_count)
    result["oyuncu"] = (
        ", ".join(oyu_names[:4]),
        oyu_var,
        "ok" if oyu_dogru else ("slogan/garble" if not oyu_dogru else "boş"),
    )
    if not oyu_var:
        result["sorunlar"].append("Oyuncu boş")
    elif not oyu_dogru:
        result["sorunlar"].append(f"Oyuncu slogan/garble ({slogan_count} slogan satır)")

    # --- ONAY ---
    result["onay"] = (
        result["afis"]
        and ozet_dogru
        and yon_var
        and yap_var
        and oyu_var
        and oyu_dogru
    )

    return result


def main(dry_run: bool = False):
    pdfs = sorted(SES_DIR.glob("*.pdf"))
    print(f"Toplam PDF: {len(pdfs)}\n")

    if not dry_run:
        ONAY_DIR.mkdir(exist_ok=True)

    approved = []
    rejected = []

    for path in pdfs:
        r = analyze_pdf(path)
        status = "[OK] ONAYLANDI" if r["onay"] else "[--] REDDEDILDI"
        sorun_str = " | ".join(r["sorunlar"]) if r["sorunlar"] else "—"
        print(f"{status}  {path.name}")
        if r["sorunlar"]:
            print(f"   Sorun: {sorun_str}")
        if r["onay"]:
            approved.append(path)
        else:
            rejected.append(path)

    print(f"\n{'='*60}")
    print(f"ONAYLANAN : {len(approved)}")
    print(f"REDDEDİLEN: {len(rejected)}")
    print(f"{'='*60}\n")

    if not dry_run and approved:
        print("Taşıma başlıyor...")
        for path in approved:
            stem = path.stem  # "2017-1058... DUNKIRK SESTEYIT"
            new_name = stem + "_onaylı.pdf"
            dest = ONAY_DIR / new_name
            shutil.copy2(path, dest)
            path.unlink()
            print(f"  Taşındı → onaylı/{new_name}")
        print(f"\nToplam {len(approved)} PDF taşındı.")
    elif dry_run:
        print("DRY-RUN: Hiçbir dosya taşınmadı.")


if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    if dry:
        print("*** DRY-RUN modu (taşıma yok). Uygulamak için --apply ekle ***\n")
    main(dry_run=dry)
