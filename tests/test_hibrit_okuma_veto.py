"""Hibrit okuyucunun SAF mantığı — model/GPU/OCR gerektirmez, CI'da koşar.

Kapsam: `yapisal_veto` (KB'siz halüsinasyon emniyeti) ve `satirlari_ayikla`.
Her vaka gerçek bir üretim gözleminden geliyor; yorumlarda filmi yazılı.

NEDEN BU TESTLER VAR: `_pipe_hibrit_okuma.py` üretim okuma yolu (Paddle'ın
yerine geçti). Veto fonksiyonu iki yönde de tehlikeli:
  - fazla gevşek → uydurma satır künyeye girer (Çağatay: "halüsinasyon olmasın")
  - fazla sıkı   → gerçek isim silinir      (Çağatay: "isim atlamayalım")
İkinci risk teorik değil: `ronaldo.halusinasyon_mu` tam bu yüzden
KULLANILMADI (boş kb_tok'ta >8 kelimelik her satırı yutuyor).
Bu dosya o dengeyi kilitler.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "_pipe_hibrit_okuma",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "scripts", "_pipe_hibrit_okuma.py"))
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)


# ÜRETİMİN KENDİ fonksiyonları enjekte edilir — taklit değil. ronaldo.py
# stdlib-only (unicodedata + dataclasses), CI'da import edilebilir. Sahte fold
# kullanmak testi yalancı yapardı: üretim fold_tr ile davranış ayrışabilir.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "harness", "track_kunye"))
import ronaldo  # noqa: E402


def veto(s: str, garble=ronaldo.garble_mi) -> bool:
    return h.yapisal_veto(s, ronaldo.fold_tr, garble)


# ───────────────────── GEÇMESİ ZORUNLU: gerçek künye satırları ─────────────────────
# Bu blok "isim atlamayalım" şartının testi. Kırılırsa üretimde İSİM KAYBI olur.

def test_gercek_isimler_gecer():
    for satir in (
        "NAZLI ÖZDEMİR",              # ALİE başrolü — KB'de YOK, ekranda VAR
        "SELÇUK YÖNTEM",              # ALİE konuk oyuncu
        "yönetmen yardımcısı",         # rol başlığı (küçük harf)
        "ANNE BAXTER",                 # BOZGUNCULAR 18px kart
        "distribution: linda grinbaum",  # CİNAYET — yalnız master kolunda
        "david rhineer camera loader",   # DEFİNE ADASI — yalnız master kolunda
        "steadicam operatörü",
        "ONUR KAYNARCA",
    ):
        assert not veto(satir), f"gerçek künye satırı vetolandı: {satir!r}"


def test_uzun_cok_isimli_satir_gecer():
    """ronaldo.halusinasyon_mu bu satırı YUTUYORDU (>8 kelime + boş KB).

    Bir kartta yan yana dizilmiş isimler tek satır olarak okunabiliyor;
    kelime sayısına bakan kural bunu halüsinasyon sanıyor. Regresyon kilidi.
    """
    satir = "AYSEL GUROL MELEK BALKAY AHMET DURSUN SELIM NAKI CEM DAVRAN ONUR AKAY"
    assert len(satir.split()) > 8
    assert not veto(satir)


# ───────────────────── DÜŞMESİ ZORUNLU: gözlenmiş uydurmalar ─────────────────────

def test_madde_imi_betimleme_duser():
    """ALİE (2010-9253), 2026-07-31 gece: deepseek boş sahne karesinde
    jenerik yerine sahneyi ANLATTI ve satırlar künyeye girdi."""
    for satir in (
        "- A river flowing from the foreground towards the background.",
        "- A bridge spanning the river in the middle of the image.",
        "* The background features a hill on the right side.",
        "• kapalı bir kapı görünüyor",
    ):
        assert veto(satir), f"betimleme satırı geçti: {satir!r}"


def test_dizyazi_fiili_duser():
    for satir in ("The image shows a man walking",
                  "There appears to be text at the bottom",
                  "ekranda bir tabela gorunuyor"):
        assert veto(satir), f"düzyazı geçti: {satir!r}"


def test_parantez_ve_markdown_duser():
    assert veto("[Image of a dark street]")
    assert veto("(no text visible)")
    assert veto("**YÖNETMEN**")        # markdown artefaktı — hakeme sorulsa ONAYLANIRDI
    assert veto("|---|---|")           # FRANSIZ KIZARMASI duman testi: tablo çöpü


def test_harfsiz_satir_duser():
    """'- 1' liste-numarası çöpü — ölçümde ham satırların %32'si."""
    for satir in ("- 1", "2.", "   ", "###", "1998"):
        assert veto(satir), f"harfsiz satır geçti: {satir!r}"


def test_cjk_betimleme_duser():
    assert veto("这是一个黑暗的场景")


def test_garble_enjeksiyonu_saygi_gorur():
    """garble kararı dışarıdan gelir; veto onu son söz olarak kullanır."""
    assert veto("AHMET DURSUN", garble=lambda s: True)
    assert not veto("AHMET DURSUN", garble=lambda s: False)


# ───────────────────── satirlari_ayikla ─────────────────────

def test_satirlari_ayikla_bos_ve_bosluk():
    assert h.satirlari_ayikla("") == []
    assert h.satirlari_ayikla("   \n\n  ") == []


def test_satirlari_ayikla_kirpar_ve_sirayi_korur():
    ham = "  ANNE BAXTER  \n\nJEFF CHANDLER\n   \nyönetmen\n"
    assert h.satirlari_ayikla(ham) == ["ANNE BAXTER", "JEFF CHANDLER", "yönetmen"]
