"""scripts/credit_text_read._drop_dubbing_directors — GERÇEK-YÖNETMEN bağışıklığı
betik-farkında rol tablosuna delege edildi (adım 4/5).

Kök (spec §2.3/§4.4): satır 582-585'teki `_TRUE_DIR_RE` kendi ayrı, dar, tamamen
Latin listesini taşıyordu. Bu liste `core/lexicon/rol_tablosu.TABLO["LATIN"]["YONETMEN"]`
(credit_role_lexicon.DIRECTOR birebir kopyası) kelimelerinin ALT-KÜMESİ — delege
kayıpsız, dahası kapsamı genişletiyor (ör. bare 'DIRECTOR', 'DIRETTO DA',
'GEREGISSEERD DOOR' — eski regex'te YOKTU).

`folded` satırları `_fold()` (Latin-ASCII'ye indirger) üzerinden geldiği için bu
çağrı yeri zaten Latin-only bağlamda çalışıyordu — rol_tablosu'nun betik tespiti
her satırda LATIN dönecek, davranış değişmez (yalnız kelime dağarcığı genişler).

PaddleOCR/Ollama istemez — saf fonksiyon çağrıları.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import credit_text_read as ctr  # noqa: E402


def test_true_dir_re_kaldirildi():
    """Satır 582-585'teki eski regex silindi (spec §4.4) — rol_tablosu'na delege edildi."""
    assert not hasattr(ctr, "_TRUE_DIR_RE")


# ── Mevcut davranış (eski _TRUE_DIR_RE kelimeleri) bozulmadı ─────────────
def test_dubbing_director_drop_bozulmadi():
    """test_credit_qc_block.py::test_dubbing_director_drop ile AYNI senaryo — burada
    da bağımsız doğrulanır (bare 'YÖNETMEN' eski regex'te de vardı)."""
    raw = ["KURGU", "AHMET K", "SESLENDİRME YÖNETMEN YARDIMCISI", "ESRA TANAR",
           "SESLENDİRME YÖNETMENİ", "ENGİN AYBAKAN", "YÖNETMEN", "Sam Raimi"]
    kept, dropped = ctr._drop_dubbing_directors(["ESRA TANAR", "ENGİN AYBAKAN", "Sam Raimi"], raw)
    assert "ESRA TANAR" in dropped and "ENGİN AYBAKAN" in dropped
    assert "Sam Raimi" in kept


def test_directed_by_bagisikligi_bozulmadi():
    """'Directed by' eski regex'te vardı — NONFILM marker'a rağmen düşmemeli."""
    raw = ["Associate Producer", "John Doe", "Directed by", "Jane Smith"]
    kept, dropped = ctr._drop_dubbing_directors(["Jane Smith"], raw)
    assert "Jane Smith" in kept


# ── Kapsam genişlemesi: eski regex'te OLMAYAN LATIN.YONETMEN kelimeleri ──
def test_bare_director_artik_bagisiklik_tetikler():
    """Bare 'Director' eski _TRUE_DIR_RE listesinde YOKTU (yalnız 'directed by' vardı).
    LATIN.YONETMEN'de VAR — delege sonrası bu da bağışıklık tetiklemeli (kayıp yok,
    kazanım var — spec §4.4)."""
    raw = ["Assistant Director", "Someone Else", "Director", "Maria Rossi"]
    kept, dropped = ctr._drop_dubbing_directors(["Maria Rossi"], raw)
    assert "Maria Rossi" in kept


def test_diretto_da_artik_bagisiklik_tetikler():
    """'Diretto da' eski regex'te YOKTU (yalnız 'regia di' vardı) — LATIN.YONETMEN'de VAR."""
    raw = ["Assistant Director", "Someone Else", "Diretto da", "Sergio Leone"]
    kept, dropped = ctr._drop_dubbing_directors(["Sergio Leone"], raw)
    assert "Sergio Leone" in kept


# ── Alt-roller HÂLÂ bağışıklık TETİKLEMEZ (HARIC uygulanıyor, §3.4 isim-hattı disiplini) ──
def test_art_director_bagisiklik_tetiklemez():
    """'Art Director' LATIN.HARIC'te — genişleyen kelime dağarcığı yanlışlıkla alt-rolü
    'gerçek yönetmen' saymamalı (haric_uygula=True şart)."""
    raw = ["Art Director", "Someone Else", "Assistant Director", "Maria Rossi"]
    kept, dropped = ctr._drop_dubbing_directors(["Maria Rossi"], raw)
    assert "Maria Rossi" in dropped, "Art Director bağışıklık tetiklememeli, düşmeliydi"


def test_goruntu_yonetmeni_bagisiklik_tetiklemez():
    """'Görüntü Yönetmeni' hem eski hem yeni yolda alt-rol — bağışıklık YOK."""
    raw = ["Görüntü Yönetmeni", "Someone Else", "Yardimci Yonetmen", "Maria Rossi"]
    kept, dropped = ctr._drop_dubbing_directors(["Maria Rossi"], raw)
    assert "Maria Rossi" in dropped
