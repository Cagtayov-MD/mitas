#!/usr/bin/env python3
"""JASON KIDD — MITAS harf kapısı. Çıktıya giden HER metnin kasa/aksan sorumlusu.

Çağatay (2026-08-01): "Harf işi Jason Kidd kontrolünde dediğimde güvenebilmeliyim."
Kidd sahayı görüp ince detayı doğru yere bırakan pasördür; bu modül de her çıktı
yüzeyinde son pası verir.

KURAL (tek cümle):
    Türkçe ad/sözcük  → ç ğ ı İ ö ş ü SERBEST
    Yabancı ad        → SAF ASCII: ne aksan, ne Türkçe harf

BU MODÜL KURAL YAZMAZ — mevcut motoru ÇAĞIRIR.
Motor: OCR-worktree/pdf-mitas/name_normalize.py (upper_names / tr_upper_prose /
tr_upper / ascii_fold). Orada yıllardır biriken Türkçe/yabancı ayrımı, DB
sorgusu ve dil kuralları var; yeniden yazmak o birikimi çöpe atmak olurdu.
Kidd'in işi TEK GİRİŞ NOKTASI olmak: kural bir yerde dursun, her yüzey buradan
geçsin, biri unutulduğunda `--durum` bağırsın.

YÜZEYLER (durum: python3 scripts/jason_kidd.py --durum):
    isim_listesi()  cast/crew          → nn.upper_names          [KAPSANDI]
    proza()         özet metni         → nn.tr_upper_prose       [KAPSANDI]
    baslik()        PDF başlığı        → nn.tr_upper             [KAPSANDI]
    alt_baslik()    XML orijinal ad    → burada (aşağıda)        [KAPSANDI]

KAPSAM DIŞI (bilerek): dosya adları ve _DURUM.json alanları. Dosya adı TRT
kimliğini taşıyor ve dış sistemlerle eşleşiyor; JSON ise makine yüzeyi, insan
okumuyor. İkisi de "kullanıcıya giden metin" değil.
"""
from __future__ import annotations

import importlib.util
import os
import unicodedata
from pathlib import Path

_KOK = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
_PDFMITAS = Path(os.environ.get("MITAS_PDFMITAS_DIR") or (_KOK / "OCR-worktree" / "pdf-mitas"))

_nn = None
_nn_hata = None


def motor():
    """name_normalize'i tembel yükle. Yüklenemezse SESSİZ kalmaz — durum raporlar."""
    global _nn, _nn_hata
    if _nn is None and _nn_hata is None:
        try:
            sp = importlib.util.spec_from_file_location(
                "jk_name_normalize", str(_PDFMITAS / "name_normalize.py"))
            m = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(m)
            _nn = m
        except Exception as e:  # noqa: BLE001
            _nn_hata = f"{type(e).__name__}: {e}"
    return _nn


# Türkçe harf kümeleri — kuralın çekirdeği.
TR_TUM = set("çğıİöşüÇĞIÖŞÜ")
# ı ş ğ tr_upper tarafından ÜRETİLEMEZ → varlıkları GERÇEK Türkçe kanıtıdır.
# (İ/ü/ö/ç kanıt değildir: tr_upper 'i'yi 'İ' yapabilir, yabancı ada da bulaşır.)
TR_KESIN = set("ışğŞĞ")


def yabanci_aksan(s: str) -> bool:
    """Türkçede BULUNMAYAN Latin aksanı var mı? (é ê å ø ñ Ê…) → kesin yabancı."""
    return any((not c.isascii()) and unicodedata.category(c).startswith("L")
               and c not in TR_TUM for c in (s or ""))


# ── YÜZEY 1: isim listeleri (cast / crew) ────────────────────────────────────
def isim_listesi(adlar):
    nn = motor()
    if nn is None or not adlar:
        return adlar
    try:
        return nn.upper_names(list(adlar))
    except Exception:  # noqa: BLE001 — kapı ASLA teslimi düşürmez
        return adlar


# ── YÜZEY 2: prose (özet) ────────────────────────────────────────────────────
def proza(metin, isimler=(), tr_set=None):
    nn = motor()
    if nn is None or not metin:
        return metin
    try:
        return nn.tr_upper_prose(metin, names=list(isimler or ()), tr_set=tr_set)
    except Exception:  # noqa: BLE001
        return metin


# ── YÜZEY 3: başlık ──────────────────────────────────────────────────────────
def baslik(s):
    nn = motor()
    if nn is None or not s:
        return s
    try:
        return nn.tr_upper(s)
    except Exception:  # noqa: BLE001
        return s


# ── YÜZEY 4: alt başlık (XML orijinal ad) ────────────────────────────────────
def alt_baslik(orig: str, tr_baslik: str = "") -> str:
    """XML <TITLE>. Teslim edilmiş PDF'lerde 'MADE İN ITALY' bulundu (2026-08-01).

    KÖRLEMESİNE fold YAPILAMAZ: orijinal ad çoğu kez TÜRKÇE BAŞLIĞIN KENDİSİ
    ('AĞAÇ', 'MİRAS', 'BORÇ') — fold 'AGAC' yapıp sağlam çıktıyı bozar.
    Ayırıcı tüm DB taranarak çıkarıldı: 3 film düzelir, 15 film korunur.
    """
    if not orig or os.environ.get("MITAS_ALTBASLIK_KAPISI", "1").strip().lower() in ("0", "false", "off"):
        return orig
    if not any(c.isalpha() and not c.isascii() for c in orig):
        return orig                                    # zaten saf ASCII
    if not yabanci_aksan(orig):
        if tr_baslik and orig.upper() == tr_baslik.upper():
            return orig                                # TRT "orijinali de bu" diyor
        if any(c in TR_KESIN for c in orig):
            return orig                                # ı/ş/ğ → kesin Türkçe
    nn = motor()
    if nn is None:
        return orig
    try:
        return nn.ascii_fold(orig)
    except Exception:  # noqa: BLE001
        return orig


# ── durum raporu: "Kidd sahada mı?" ──────────────────────────────────────────
def durum() -> dict:
    nn = motor()
    d = {"motor": "name_normalize", "yuklu": nn is not None, "hata": _nn_hata,
         "pdfmitas": str(_PDFMITAS), "yuzeyler": {}}
    if nn is not None:
        for ad, f in (("upper_names", "upper_names"), ("tr_upper_prose", "tr_upper_prose"),
                      ("tr_upper", "tr_upper"), ("ascii_fold", "ascii_fold")):
            d["yuzeyler"][ad] = hasattr(nn, f)
        try:
            d["turk_isim_db"] = bool(nn._TR_GIVEN or nn._TR_SUR)
        except Exception:  # noqa: BLE001
            d["turk_isim_db"] = None
    return d


if __name__ == "__main__":
    import json
    import sys
    if "--durum" in sys.argv:
        print(json.dumps(durum(), ensure_ascii=False, indent=1))
        raise SystemExit(0)
    print(__doc__)
    print("\nKendi kendine sınav:")
    for o, t, ne in (("LAND RAİDERS", "YAĞMACILAR", "yabancı → ASCII"),
                     ("AĞAÇ", "AĞAÇ", "Türkçe → korunur"),
                     ("MADE İN ITALY", "İTALYAN YAZI", "yabancı → ASCII")):
        print(f"   {o:<26}→ {alt_baslik(o, t):<26}({ne})")
    print(f"   {['frédéric', 'william', 'gökhan']} → {isim_listesi(['frédéric', 'william', 'gökhan'])}")
