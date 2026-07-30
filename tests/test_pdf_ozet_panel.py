# -*- coding: utf-8 -*-
"""test_pdf_ozet_panel.py — ASR kapalıyken PDF'te placeholder ÖZET paneli olmamalı.

İki katman:
1. _make_pdf.build: ozet="" → sayfa metninde 'ÖZET' başlığı YOK (panel çizilmez,
   936a12b fix'inin ilk gerçek testi — fitz ile render edilen PDF'in metni okunur).
2. mitas_pipeline: no_asr yolunda ozet placeholder DEĞİL boş string olmalı
   (kaynak sözleşmesi — placeholder "(Özet ayrı bir adımda üretilecektir.)"
   YAĞMACILAR PDF'inde panele basılıyordu).

Çalıştır: /opt/mitas/venvs/asr/bin/python -m pytest tests/test_pdf_ozet_panel.py -q
(fitz + reportlab asr venv'de — requirements/asr.txt 2026-07-30)
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")

_ROOT = Path(__file__).resolve().parent.parent
# _make_pdf import-anında font kaydeder; env'siz kabukta Windows yoluna düşer (mitas.env:15).
os.environ.setdefault("MITAS_MSFONT_DIR", "/usr/share/fonts/truetype/msttcorefonts")
os.environ.setdefault("MITAS_PROJECT_ROOT", str(_ROOT))
_spec = importlib.util.spec_from_file_location(
    "make_pdf_under_test", _ROOT / "OCR-worktree" / "pdf-mitas" / "_make_pdf.py")
mp = importlib.util.module_from_spec(_spec)
sys.modules["make_pdf_under_test"] = mp
_spec.loader.exec_module(mp)


def _veri(ozet: str) -> dict:
    return dict(
        profile="FİLM", date="30.07.2026 · 15:00", title="YAĞMACILAR",
        subtitle="LAND RAIDERS", poster="", bolum="",
        specs=[("ÇÖZÜNÜRLÜK", "512x288"), ("TÜR", "AKSİYON"),
               ("TOPLAM SÜRE", "01:34:36"), ("TRT KİMLİK", "1970-0021-1-0000-90-1")],
        keywords="TELLY SAVALAS", cast=["TELLY SAVALAS"],
        crew=[("Yönetmen", ["NATHAN JURAN"])], ozet=ozet,
    )


def _sayfa_metni(pdf_yolu: Path) -> str:
    """Sayfa metni, boşluk/satır normalize. DİKKAT: başlıklar tracked() ile
    harf-aralıklı çizilir ('Ö Z E T') — ham metinde bitişik 'ÖZET' GEÇMEZ."""
    with fitz.open(str(pdf_yolu)) as doc:
        ham = doc[0].get_text()
    return ham.replace(" ", "").replace("\n", "")


def test_ozet_bos_panel_yok(tmp_path):
    hedef = tmp_path / "bos.pdf"
    mp.build(str(hedef), _veri(""))
    metin = _sayfa_metni(hedef)
    assert "ÖZET" not in metin, "özet boşken ÖZET paneli çizilmemeli"
    assert "YAĞMACILAR" in metin      # PDF gerçekten render oldu


def test_ozet_dolu_panel_var(tmp_path):
    hedef = tmp_path / "dolu.pdf"
    mp.build(str(hedef), _veri("Vahşi batıda bir kasaba çatışması."))
    metin = _sayfa_metni(hedef)
    assert "ÖZET" in metin
    assert "kasaba" in metin           # gövde metni tracked değil; boşluksuz normalize'de bitişik


def test_pipeline_no_asr_yolunda_ozet_bos():
    """mitas_pipeline no_asr iken placeholder'ı DEĞİL boş özeti göndermeli."""
    src = (_ROOT / "scripts" / "mitas_pipeline.py").read_text(encoding="utf-8", errors="replace")
    i = src.find("(Özet ayrı bir adımda üretilecektir.)")
    assert i > 0, "placeholder metni taşındıysa testi güncelle"
    blok = src[max(0, i - 400):i + 200]
    assert "no_asr" in blok, (
        "placeholder no_asr koşuluna bağlanmalı: ASR kapalıyken ozet='' olmalı "
        "(panel yok), ASR açıkken mevcut davranış korunur")
