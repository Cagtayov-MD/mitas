#!/usr/bin/env python3
"""YÖNETMEN KURTARMA — künyede etiket VAR ama alan BOŞ kalan filmleri kurtarır.

ÖLÇÜLEN SORUN (2026-08-01, garble_trigger_olcum düzeltildikten sonra):
    292 künyeli filmin 145'inde yönetmen etiketi var; bunların **35'inde (%24)**
    etiket künyede duruyor ama yönetmen alanı BOŞ → QC1 RED → KONTROL.

CANLI KANIT — KUTSAL HAZİNE 1998-0325:
    giriş karesi g_0244.png ekranda "Directed by / JOHN CONNICK" gösteriyor;
    hibrit okuyucu DOĞRU okudu, hakem piksel kanıtı verdi (kutu_n=2),
    kunye.txt:252-253'e YAZILDI. Sonra gemma (rol çıkarımı) 18 oyuncuyu buldu
    ama yönetmeni atladı; VL yedeği de koştu ve o da bulamadı. İKİ LLM YOLU DA
    kaçırdı. Kayıp okuma değil, hatırlama hatası.

BU MODÜLÜN DURUŞU: LLM'i DÜZELTMEZ, yalnız BOŞLUĞU doldurur.
  • Yalnız yonetmen BOŞ iken çağrılır → dolu alanı ASLA ezmez → sıfır regresyon.
  • Deterministik: model yok, ağ yok, aynı girdi aynı çıktı.
  • Kanıt döndürür (etiket, satır no) → karar izlenebilir, sessiz tahmin yok.
  • Bulamazsa None döner; uydurmaz (Çağatay: "halüsinasyon olmasın").
"""
from __future__ import annotations

import re
import unicodedata

# Yönetmen etiketi — çok dilli. Kelime sınırı ŞART: 'DIRECTORS SOUND' eşleşmesin.
#
# ÇIPLAK "DIRECTOR" BİLEREK YOK (kuru koşu bulgusu 2026-08-01): 28 adayın 20'si
# çıplak DIRECTOR'dan geldi ve HEPSİ çöptü — çünkü OCR "DIRECTOR OF PHOTOGRAPHY"yi
# bozunca ('OF PHOROGRAPHY', 'OH PHOBOGRAGN', 'DE FOTOGRAFIA') _DEGIL süzgeci
# tutmuyor, geriye çıplak DIRECTOR kalıyor. Yalnız KENDİ BAŞINA yönetmen anlamına
# gelen kalıplar kabul edilir. Kapsam kaybı bilinçli: yanlış yönetmen yazmak boş
# bırakmaktan BETERDİR (Çağatay: "halüsinasyon olmasın").
_ETIKET = re.compile(
    r"\b("
    r"y[oö]netmen|y[oö]neten|"
    r"directed\s+by|"
    r"r[eé]alisation|r[eé]alis[eé]\s+par|mise\s+en\s+sc[eè]ne|un\s+film\s+de|"
    r"ein\s+film\s+von|a\s+film\s+by|"
    r"regia|regie|"
    r"re[zj]iss[oö]r"
    r")\b"
    # KİRİL AYRI (ANNA KARENINA 1988-0520 bulgusu 2026-08-01): künyede 'РЕЖИССЕРЫ'
    # (çoğul) vardı ama \b sonlandırması Rusça ÇEKİM EKİNİ kesiyordu (-ы/-а/-ом/-ов)
    # → etiket hiç görülmedi. Kiril için ek serbest bırakılır; 'ПОСТАНОВЩИК' (sanat
    # yönetmeni) BİLEREK yok — o _DEGIL sınıfı.
    r"|режисс[ёе]р\w*|постановка\b",
    re.IGNORECASE,
)

# Adayın İLK kelimesi bunlardan biriyse isim değildir (edat/bağlaç/etiket başı).
# 'OF PHOROGRAPHY', 'DE FOTOGRAFIA', 'BY JOHN', 'AND EDITED' vakaları.
_ADAY_BAS_YASAK = {
    "OF", "DE", "DI", "DA", "DU", "DES", "DEL", "BY", "AND", "THE", "A", "AN",
    "VE", "ILE", "ZND", "2ND", "3RD", "1ST", "FIRST", "SECOND", "THIRD",
    "PRODUCED", "WRITTEN", "EDITED", "MUSIC", "SOUND", "CAMERA", "UNIT",
    "EXECUTIVE", "ASSOCIATE", "LINE", "CO",
}

# Aday içinde bu kelimelerden biri geçerse isim değildir (bozuk OCR'a dayanıklı:
# PHO*RAPH*, FOTOGRAF* gibi kökler harf hatalarını da yakalasın diye gevşek).
_ADAY_ICI_YASAK = re.compile(
    r"ph[o0]?[tr8b][o0]?[gq]r?a?[pf]h?|f[o0]t[o0][gq]raf|"      # photography / fotografia bozulmaları
    r"\bunit\b|\bsound\b|\bcamera\b|\bmusic\b|\bproduc|\bedit|"
    r"\bpresent|\bstudio|\bpictures?\b|\bfilms?\b|"
    r"\bdirect|\bwrit|\bdesign|\bsupervis",                      # 'DIRECTOR OF' vakası (CAZCI)
    re.IGNORECASE,
)

# Düzyazı imzası: bu işlev sözcükleri bir İSİMDE bulunmaz — cümle parçasıdır.
# ('EXPLODED THROUGHOUT AN UNSUSPECTING…' / 'YOU CANT …' vakaları)
_PROSA = re.compile(
    r"\b(the|an|and|with|that|this|from|into|through|throughout|when|while|"
    r"his|her|their|its|you|they|was|were|has|have|had|been|being|"
    r"cant|cannot|dont|wont|isnt|about|after|before|during|over|under)\b",
    re.IGNORECASE,
)

# Bu kelimelerden biri geçiyorsa o etiket FİLM yönetmeni DEĞİL.
# (KUTSAL HAZİNE'de '2nd Unit Director' ve 'DIRECTORS SOUND' bu yüzden elenir;
#  CİNAYET'te 'Director of Photography', OKYANUSUN'da 'Seslendirme Yönetmen'.)
_DEGIL = re.compile(
    r"yard[iı]mc|asist|assistant|associate|"
    r"photograph|d\.?o\.?p\.?|g[oö]r[uü]nt[uü]|"
    r"sanat|art\s+direct|"
    r"casting|cast\s+direct|"
    r"dublaj|seslendirme|sound|audio|ses\b|"
    r"m[uü]zik|music|"
    r"2nd\s+unit|second\s+unit|ikinci\s+birim|"
    r"post|teknik|prod[uü]ksiyon|production\s+manager|"
    r"stunt|d[oö]v[uü][sş]",
    re.IGNORECASE,
)

# İsim OLMAYAN satırlar (şirket/rol/teknik). isim_mi() bunları eler.
_SIRKET = {
    "FILM", "FILMS", "FILMI", "PRODUCTION", "PRODUCTIONS", "PICTURES", "PICTURE",
    "STUDIO", "STUDIOS", "ENTERTAINMENT", "MEDIA", "INC", "LLC", "LTD", "LIMITED",
    "COMPANY", "CO", "TV", "INTERNATIONAL", "GROUP", "CORP", "CORPORATION",
    "ASSOCIATES", "YAPIM", "YAPIMCILIK", "SUNAR", "PRESENTS", "PRODUCTIONS",
    "AS", "A.S", "SANAYI", "TICARET", "REKLAM", "AJANS",
}

_MAX_ILERI = 3            # etiketten sonra en fazla kaç satır ileri bakılır
_MAX_ISIM_TOKEN = 5       # 'JOHN RONALD REUEL TOLKIEN JR' sınırı


def _kats(s: str) -> str:
    s = (s or "").replace("ı", "i").replace("İ", "i")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def isim_mi(satir: str) -> bool:
    """Bu satır bir KİŞİ adı olabilir mi? Muhafazakâr: şüphede HAYIR."""
    s = (satir or "").strip(" .:-–—\t")
    if not (3 <= len(s) <= 48):
        return False
    if _ETIKET.search(s) or _DEGIL.search(s):
        return False                       # başka bir rol etiketi
    if any(ch.isdigit() for ch in s):
        return False
    if _ADAY_ICI_YASAK.search(s):
        return False                       # görüntü yön./ekip/şirket kökü (OCR bozulmasına dayanıklı)
    if _PROSA.search(s):
        return False                       # cümle parçası, isim değil
    tok = [t for t in re.split(r"[\s'’.\-]+", s) if t]
    if not (2 <= len(tok) <= _MAX_ISIM_TOKEN):
        return False                       # tek kelime isim sayılmaz (Çağatay kuralı)
    if _kats(tok[0]) in _ADAY_BAS_YASAK:
        return False                       # edat/etiket başı: 'OF ...', 'PRODUCED BY'
    if any(_kats(t) in _SIRKET for t in tok):
        return False
    if not all(re.fullmatch(r"[^\W\d_]+", t, re.UNICODE) for t in tok):
        return False                       # her token SAF harf olmalı
    harf = [c for c in s if c.isalpha()]
    if len(harf) < len(s.replace(" ", "")) * 0.8:
        return False                       # noktalama ağırlıklı → çöp
    return True


def _ayni_kare(iz_yolu, etiket_metin: str, isim_metin: str) -> str | None:
    """ADRES TEYİDİ (Çağatay'ın hakem fikri, rol-eşlemeye uygulanmış).

    Etiket ile isim EKRANDA AYNI KAREDE mi? hibrit_iz.jsonl her satırın kaynak
    PNG'sini tutuyor. Aynı kare = kart gerçekten "Directed by / İSİM" kartı.
    Farklı kare = satırlar künyede yan yana düşmüş ama ekranda ilgisiz
    (HOTEL RWANDA vakası: 'A FILM BY' ile oyuncu adı tesadüfen komşu).
    Döner: ortak kare adı, yoksa None. İz dosyası yoksa None (hüküm verme).
    """
    try:
        import json as _json
        et, isim = etiket_metin.strip().lower(), isim_metin.strip().lower()
        et_kare, isim_kare = set(), set()
        with open(iz_yolu, encoding="utf-8") as h:
            for satir in h:
                try:
                    k = _json.loads(satir)
                except Exception:  # noqa: BLE001
                    continue
                t = str(k.get("text", "")).strip().lower()
                kaynak = k.get("kaynak")
                if not kaynak:
                    continue
                if et and et in t:
                    et_kare.add(kaynak)
                if isim and t == isim:
                    isim_kare.add(kaynak)
        ortak = et_kare & isim_kare
        return sorted(ortak)[0] if ortak else None
    except Exception:  # noqa: BLE001 — teyit yoksa hüküm yok
        return None


def kurtar(satirlar, iz_yolu=None) -> dict | None:
    """Künye satırlarından yönetmeni ETİKET ÜZERİNDEN çıkar.

    Döner: {"yonetmen": str, "etiket": str, "satir": int, "nasil": "ayni_satir|alt_satir"}
    veya bulunamazsa None. ASLA uydurmaz.
    """
    satirlar = [str(s or "") for s in (satirlar or [])]
    for i, ham in enumerate(satirlar):
        m = _ETIKET.search(ham)
        if not m or _DEGIL.search(ham):
            continue
        # (a) etiketin AYNI satırdaki devamı: 'Directed by JOHN CONNICK'
        kalan = ham[m.end():].strip(" :.-–—\t")
        if isim_mi(kalan):
            return {"yonetmen": kalan, "etiket": m.group(0), "satir": i,
                    "nasil": "ayni_satir", "kare_teyidi": "etiketle_ayni_satir"}
        # (b) ALT satır(lar): 'Directed by' \n 'JOHN CONNICK'
        if ham[:m.start()].strip(" :.-–—\t"):
            continue                       # etiketten ÖNCE metin var → serbest cümle, atla
        for j in range(i + 1, min(i + 1 + _MAX_ILERI, len(satirlar))):
            aday = satirlar[j].strip()
            if not aday:
                continue
            if _ETIKET.search(aday) or _DEGIL.search(aday):
                break                      # araya başka rol girdi → bu etiket sahipsiz
            if isim_mi(aday):
                kare = _ayni_kare(iz_yolu, m.group(0), aday) if iz_yolu else None
                return {"yonetmen": aday, "etiket": m.group(0), "satir": j,
                        "nasil": "alt_satir",
                        "kare_teyidi": kare or ("iz_yok" if not iz_yolu else "AYRI_KARE")}
            break                          # ilk dolu satır isim değilse zorlama
    return None


if __name__ == "__main__":                 # elle deneme: python3 scripts/yonetmen_kurtar.py <kunye.txt>
    import json
    import sys
    from pathlib import Path
    if len(sys.argv) < 2:
        raise SystemExit("kullanım: yonetmen_kurtar.py <kunye.txt>")
    print(json.dumps(kurtar(Path(sys.argv[1]).read_text(encoding="utf-8",
                                                        errors="ignore").splitlines()),
                     ensure_ascii=False, indent=1))
