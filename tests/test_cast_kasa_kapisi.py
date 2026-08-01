"""Cast kasa-kapısı (`filter_cast_by_dotleader_casing`) — iki yönlü kilit.

Kapının işi: "Karakter......OYUNCU" iki-sütunlu kartlarda karakter adını (Baş-Harfi-
Büyük) oyuncu sanmayı engellemek. NEGATİF kapı — yalnız düşürür, isim eklemez.

İKİ YÖNLÜ TEHLİKE (kapı bugüne kadar TESTSİZDİ):
  • gevşek → karakter adları cast'e sızar (LAUREL HARDY kökü, 2026-07-09)
  • sıkı   → GERÇEK oyuncu düşer, alan boşalır  (ALİE kökü, 2026-08-01)

ALİE 2010-9253 ölçülen vaka: MITAS İKİ jenerik okur. Bu filmde ÇIKIŞ jeneriği
TÜMÜ-BÜYÜK (NAZLI ÖZDEMİR…), GİRİŞ jeneriği tümü küçük dizilmiş
('konuk oyuncular / selçuk yöntem / meral okay / suzan kardeş / ve / oktay kaynarca'
— g_0024.png, gözle doğrulandı). Çıkıştaki ALL-CAPS kanıtı kapıyı açıyordu, kapı
da girişteki GERÇEK konuk oyuncuları 'karakter adı' sanıp atıyordu.

Kasa ancak AYNI KARTTA ayırt edicidir → yerellik kuralı (±60 satır).
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import credit_text_read as ctr  # noqa: E402


# ───────── DÜŞÜRMESİ ZORUNLU (kapının varlık sebebi) ─────────

def test_karakter_adi_ayni_kartta_dusurulur():
    """LAUREL HARDY kökü: karakter adı ile oyuncu adı AYNI kartta, yan yana."""
    ham = [
        "CAST",
        "Tommy White", "JOHN SHELTON",
        "Doc Lake", "ADDISON RICHARDS",
    ]
    out = ctr.filter_cast_by_dotleader_casing(
        ["Tommy White", "JOHN SHELTON", "Doc Lake", "ADDISON RICHARDS"], ham)
    assert "JOHN SHELTON" in out and "ADDISON RICHARDS" in out
    assert "Tommy White" not in out and "Doc Lake" not in out


def test_nokta_dizili_tek_satir():
    ham = ["Malcolm Kilgore ....... ADDISON RICHARDS"]
    out = ctr.filter_cast_by_dotleader_casing(["Malcolm Kilgore", "ADDISON RICHARDS"], ham)
    assert out == ["ADDISON RICHARDS"]


# ───────── DÜŞÜRMEMESİ ZORUNLU (ALİE regresyon kilidi) ─────────

def _alie_ham() -> list[str]:
    """ÇIKIŞ jeneriği ALL-CAPS (baş), GİRİŞ jeneriği küçük harf (son) — arada uzun ekip listesi."""
    cikis = ["oyuncular", "NAZLI ÖZDEMİR", "EMİNE YAREN", "ERDEM KARACAY", "ATİLLA YURTTAŞ"]
    ara = [f"EKİP ÜYESİ {i}" for i in range(200)]          # ≫ 60 satır: iki jenerik uzakta
    giris = ["konuk oyuncular", "selçuk yöntem", "meral okay", "suzan kardeş",
             "ve", "oktay kaynarca", "yapimci", "oktay kaynarca"]
    return cikis + ara + giris


def test_alie_kucuk_harf_giris_jeneriği_korunur():
    """Uzaktaki ALL-CAPS kanıtı BAŞKA bir jeneriğin geleneği — bu isimler için hüküm veremez."""
    cast = ["NAZLI ÖZDEMİR", "EMİNE YAREN", "ERDEM KARACAY", "ATİLLA YURTTAŞ",
            "Selçuk Yöntem", "Meral Okay", "Suzan Kardeş", "Oktay Kaynarca"]
    out = ctr.filter_cast_by_dotleader_casing(cast, _alie_ham())
    assert len(out) == 8, f"konuk oyuncu düştü: {set(cast) - set(out)}"
    for nm in ("Meral Okay", "Oktay Kaynarca", "Selçuk Yöntem", "Suzan Kardeş"):
        assert nm in out


def test_yerellik_kill_switch_eski_davranisi_geri_getirir(monkeypatch):
    monkeypatch.setenv("MITAS_CAST_CASING_YEREL", "0")
    cast = ["NAZLI ÖZDEMİR", "EMİNE YAREN", "Meral Okay", "Oktay Kaynarca"]
    out = ctr.filter_cast_by_dotleader_casing(cast, _alie_ham())
    assert "Meral Okay" not in out          # eski küresel davranış: düşer


# ───────── FAIL-SAFE davranışlar ─────────

def test_hic_all_caps_yoksa_dokunma():
    """Casing bu filmde ayırt edici değil (OCR hepsini küçük okumuş) → hüküm YOK."""
    cast = ["Selçuk Yöntem", "Meral Okay"]
    ham = ["konuk oyuncular", "selçuk yöntem", "meral okay"]
    assert ctr.filter_cast_by_dotleader_casing(cast, ham) == cast


def test_kill_switch_kapiyi_komple_kapatir(monkeypatch):
    monkeypatch.setenv("MITAS_CAST_CASING_GATE", "0")
    cast = ["Tommy White", "JOHN SHELTON"]
    ham = ["Tommy White", "JOHN SHELTON"]
    assert ctr.filter_cast_by_dotleader_casing(cast, ham) == cast


@pytest.mark.parametrize("cast,ham", [
    ([], ["X"]),
    (["TEK İSİM"], ["TEK İSİM"]),        # len<2 → dokunma
    (["A B", "C D"], []),                 # ham yok → dokunma
])
def test_dejenere_girdi(cast, ham):
    assert ctr.filter_cast_by_dotleader_casing(cast, ham) == (cast or [])
