# -*- coding: utf-8 -*-
"""Ortak künye PDF'inin uzun-sayfa ve yeni jenerik sözleşmesi testleri."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")
Image = pytest.importorskip("PIL.Image")

_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("MITAS_MSFONT_DIR", "/usr/share/fonts/truetype/msttcorefonts")
os.environ.setdefault("MITAS_PROJECT_ROOT", str(_ROOT))
_SPEC = importlib.util.spec_from_file_location(
    "make_pdf_long_page_under_test",
    _ROOT / "OCR-worktree" / "pdf-mitas" / "_make_pdf.py",
)
mp = importlib.util.module_from_spec(_SPEC)
sys.modules["make_pdf_long_page_under_test"] = mp
_SPEC.loader.exec_module(mp)


def _data(trt_id: str = "2023-1239-1-0000-70-1", **overrides) -> dict:
    data = dict(
        profile="FİLM",
        date="18.08.2026 · 12:00",
        title="LEYLA İLE MECNUN",
        subtitle="ORİJİNAL İSİM",
        poster="",
        bolum="",
        specs=[
            ("ÇÖZÜNÜRLÜK", "1920×1080"),
            ("TÜR", "DRAM"),
            ("TOPLAM SÜRE", "01:30:00"),
            ("TRT KİMLİK", trt_id),
        ],
        keywords="LEYLA ; MECNUN",
        cast=["OYUNCU BİR", "OYUNCU İKİ"],
        crew=[("Yönetmen", ["YÖNETMEN ADI"]), ("Yapımcı", ["YAPIMCI ADI"])],
        ozet="Kısa bir özet.",
    )
    data.update(overrides)
    return data


def _normalized(text: str) -> str:
    return "".join(text.split())


def _page_text(path: Path, page: int = 0) -> str:
    with fitz.open(path) as doc:
        return _normalized(doc[page].get_text())


def test_uzun_sayfa_tum_cast_konuk_ve_jenerigi_eksiksiz_basar(tmp_path):
    cast = [f"OYUNCU {i:03d}" for i in range(60)]
    guests = [f"KONUK {i:03d}" for i in range(8)]
    full_credits = [(f"ROL {i:03d}", [f"EKİP {i:03d} A", f"EKİP {i:03d} B"])
                    for i in range(45)]
    target = tmp_path / "uzun.pdf"
    mp.build(str(target), _data(
        cast=cast,
        guest_cast=guests,
        full_credits=full_credits,
        ozet=" ".join(["Uzun özet metni bütün kayıtların altında kalır."] * 35),
    ))

    with fitz.open(target) as doc:
        assert len(doc) == 1
        assert doc[0].rect.width == pytest.approx(mp.PAGE_W, abs=0.1)
        assert doc[0].rect.height > mp.PAGE_H
        text = _normalized(doc[0].get_text())

    for expected in (cast + guests
                     + [name for _, names in full_credits for name in names]
                     + ["YÖNETMEN ADI", "YAPIMCI ADI"]):
        assert _normalized(expected) in text

    headings = ["ANAHTARSÖZCÜKLER", "OYUNCULAR", "YAPIMEKİBİ",
                "KONUKOYUNCULAR", "ÖZET", "TAMJENERİK"]
    assert [text.index(heading) for heading in headings] == sorted(
        text.index(heading) for heading in headings)
    assert text.index("ROL000") < text.index("ROL044")
    assert text.count("YÖNETMENADI") == 1
    assert text.count("YAPIMCIADI") == 1


def test_eski_crew_ana_konuk_ve_tam_jenerige_ayrilir(tmp_path):
    target = tmp_path / "legacy.pdf"
    mp.build(str(target), _data(crew=[
        ("Yönetmen", ["ESKİ YÖNETMEN"]),
        ("Yapımcı", ["ESKİ YAPIMCI"]),
        ("Konuk Oyuncular", ["ESKİ KONUK"]),
        ("Kamera", ["KÜRŞAT UZUN"]),
        ("Işık Şefi", ["MEHMET SEZGİN"]),
    ]))
    text = _page_text(target)

    assert "KONUKOYUNCULAR" in text and "ESKİKONUK" in text
    assert "TAMJENERİK" in text
    assert text.index("Kamera:") < text.index("IşıkŞefi:")
    assert text.count("ESKİYÖNETMEN") == 1
    assert text.count("ESKİYAPIMCI") == 1
    assert text.count("ESKİKONUK") == 1


def test_acik_yeni_alanlar_bosken_legacy_konuk_ve_ek_roller_basılmaz(tmp_path):
    target = tmp_path / "explicit-empty.pdf"
    mp.build(str(target), _data(
        crew=[
            ("Yönetmen", ["YÖNETMEN ADI"]),
            ("Konuk Oyuncular", ["LEGACY KONUK"]),
            ("Kamera", ["LEGACY KAMERA"]),
        ],
        guest_cast=[],
        full_credits=[],
    ))
    text = _page_text(target)
    assert "KONUKOYUNCULAR" not in text
    assert "TAMJENERİK" not in text
    assert "LEGACYKONUK" not in text
    assert "LEGACYKAMERA" not in text


@pytest.mark.parametrize(
    ("trt_id", "episode_present", "subtitle_present"),
    [
        ("2023-1239-0-0012-70-1", True, False),
        ("2023-1239-0-0000-70-1", False, False),
        ("2023-1239-1-0012-70-1", False, True),
    ],
)
def test_trt_parselleri_dizi_bolum_ve_film_alt_basligini_belirler(
        tmp_path, trt_id, episode_present, subtitle_present):
    target = tmp_path / f"{trt_id}.pdf"
    mp.build(str(target), _data(trt_id))
    text = _page_text(target)
    if episode_present:
        assert "12.Bölüm" in text
    else:
        assert "Bölüm" not in text
    assert ("ORİJİNALİSİM" in text) is subtitle_present


def test_master_pngler_ikinci_uzun_sayfada_solda_giris_sagda_cikis(tmp_path):
    clip = tmp_path / "clip"
    clip.mkdir()
    Image.new("RGB", (240, 1600), "red").save(
        clip / "giris_reading_master_runaware.png")
    Image.new("RGB", (240, 1400), "blue").save(
        clip / "reading_master_runaware.png")

    target = tmp_path / "kanit.pdf"
    mp.build(str(target), _data(clip_dir=str(clip)))

    with fitz.open(target) as doc:
        assert len(doc) == 2
        page = doc[1]
        assert page.rect.width == pytest.approx(mp.PAGE_W, abs=0.1)
        assert page.rect.height > mp.PAGE_H
        images = page.get_image_info(xrefs=True)
        assert len(images) == 2
        boxes = sorted((fitz.Rect(info["bbox"]) for info in images), key=lambda box: box.x0)
        assert boxes[0].x0 < page.rect.width / 2 < boxes[1].x0
        assert all(box.y0 >= 0 and box.y1 <= page.rect.height for box in boxes)
        text = _normalized(page.get_text())
        assert text.index("GİRİŞJENERİĞİ") < text.index("ÇIKIŞJENERİĞİ")


def test_sol_panel_afis_bilgiler_ve_arka_plan_uzun_sayfada_korunur(tmp_path):
    poster = tmp_path / "poster.png"
    Image.new("RGB", (200, 300), "green").save(poster)
    target = tmp_path / "sol-panel.pdf"
    mp.build(str(target), _data(
        poster=str(poster),
        cast=[f"OYUNCU {i:03d}" for i in range(70)],
        ses_kanallari=["TÜRKÇE STEREO"],
        jenerik_dili="TR",
        ana_dil="TR",
        altyazi="EVET",
    ))

    with fitz.open(target) as doc:
        page = doc[0]
        assert page.rect.height > mp.PAGE_H
        images = page.get_image_info(xrefs=True)
        assert len(images) == 1
        assert fitz.Rect(images[0]["bbox"]).x1 <= mp.RW
        text = _normalized(page.get_text())
        assert all(label in text for label in
                   ("SES&ALTYAZI", "JENERİKDİLİ", "ANADİL", "ALTYAZI", "TRTKİMLİK"))
        pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        rail_pixel = pix.pixel(50, pix.height - 50)
        expected = tuple(round(channel * 255) for channel in mp.RAIL.rgb())
        assert rail_pixel == pytest.approx(expected, abs=2)


def test_kunye_14400_pt_sinirini_asarsa_veri_kirpilmadan_hata(tmp_path):
    target = tmp_path / "fazla-uzun.pdf"
    credits = [(f"ROL {i:04d}", [f"İSİM {i:04d}"]) for i in range(900)]
    with pytest.raises(ValueError, match="14400pt.*veri kırpılmadı"):
        mp.build(str(target), _data(full_credits=credits))


def test_bosluksuz_uzun_isimler_kolon_genisliginde_sarilir():
    long_name = "ÇOKUZUNBİRİSİM" * 20
    cast_layout = mp._name_columns([long_name])
    assert len(cast_layout["columns"][0][0]) > 1
    assert all(
        mp.pdfmetrics.stringWidth(line, cast_layout["font"], cast_layout["size"])
        <= cast_layout["col_w"]
        for line in cast_layout["columns"][0][0]
    )


def test_acik_full_credits_sira_yazim_ve_tekrarlari_aynen_korur():
    explicit = [
        ("kamera operatörü", ["AYNI İSİM", "AYNI İSİM"]),
        ("IŞIK ŞEFİ", ["BAŞKA İSİM"]),
    ]
    _, _, full = mp._partition_credits(_data(full_credits=explicit))
    assert full == explicit
