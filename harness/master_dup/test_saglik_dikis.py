"""saglik.py'nin F3c takip denetimi (`dikis_tekrari_supheli_kontrol` + `degerlendir`
kablolaması) için testler -- bkz. saglik.py modül-üstü "F3c takip" yorumu.
Bu, composer'ın (db_compose_master.py) KENDİ seam-dup kararına GÜVENMEDEN, final
manifest+PNG üzerinden BAĞIMSIZ bir ikinci denetimdir (safety-net -- K4-i/imha_imzasi
ile aynı 'sağlığı etkilemez, teşhis bayrağı' felsefesi)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import saglik  # noqa: E402


def _metin_bloku(satirlar: list[str], *, w: int = 400, line_h: int = 40, pad: int = 10) -> np.ndarray:
    h = line_h * len(satirlar) + 2 * pad
    img = np.zeros((h, w, 3), dtype=np.uint8)
    for i, satir in enumerate(satirlar):
        y = pad + (i + 1) * line_h - int(line_h * 0.3)
        cv2.putText(img, satir, (14, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
    return img


SEP_PX = 12


def _stack(blocks: list[np.ndarray]) -> np.ndarray:
    w = max(b.shape[1] for b in blocks)
    norm = [
        cv2.copyMakeBorder(b, 0, 0, 0, w - b.shape[1], cv2.BORDER_CONSTANT, value=(0, 0, 0))
        if b.shape[1] < w else b
        for b in blocks
    ]
    stacked = []
    for b in norm:
        stacked.append(b)
        stacked.append(np.zeros((SEP_PX, w, 3), np.uint8))
    return np.vstack(stacked[:-1])


def _yaz_film(tmp_path: Path, ad: str, blocks_meta: list[tuple[str, np.ndarray]]) -> Path:
    """blocks_meta: [(kind, img), ...] -- manifest.blocks + reading_master.png +
    metrik.json + status=OK üretir (saglik.degerlendir'in beklediği şema)."""
    film_dir = tmp_path / ad
    film_dir.mkdir()
    png = _stack([img for _, img in blocks_meta])
    cv2.imwrite(str(film_dir / "reading_master.png"), png)
    blocks = [{"kind": kind, "h": int(img.shape[0]), "w": int(img.shape[1])} for kind, img in blocks_meta]
    manifest = {
        "status": "OK", "kept_blocks": len(blocks), "size": [int(png.shape[1]), int(png.shape[0])],
        "blocks": blocks,
    }
    (film_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    metrik = {"dup_oran": 0.0, "doku_kapsami": 0.5, "boy": [int(png.shape[1]), int(png.shape[0])]}
    (film_dir / "metrik.json").write_text(json.dumps(metrik, ensure_ascii=False), encoding="utf-8")
    return film_dir


def test_kept_blocks_with_offsets_kumulatif_dogru():
    manifest = {
        "blocks": [
            {"kind": "static_page", "h": 90},
            {"kind": "scroll_slit", "h": 500},
            {"kind": "static_page", "skip": "consecutive-dup"},  # h yok/skip -- ATLANIR
        ]
    }
    offs = saglik._kept_blocks_with_offsets(manifest, sep_px=12)
    assert len(offs) == 2
    assert offs[0][:2] == (0, 90)
    assert offs[1][:2] == (90 + 12, 90 + 12 + 500)


def test_dikis_supheli_gercek_tekrarda_yakalanir(tmp_path):
    """static_page 'JOHN SMITH' hemen ardından scroll_slit'in İLK satırı da AYNI --
    bağımsız denetim bunu YAKALAMALI (composer'ın kendi kararına bakılmaksızın)."""
    static_img = _metin_bloku(["JOHN SMITH"])
    slit_img = _metin_bloku(["JOHN SMITH", "MARY JONES", "PRODUCER CREDIT", "EXTRA ROW HERE"])
    film_dir = _yaz_film(tmp_path, "supheli-film", [("static_page", static_img), ("scroll_slit", slit_img)])
    sonuc = saglik.degerlendir(film_dir)
    assert "dikis_tekrari_supheli" in sonuc["teshis_bayraklari"]
    assert sonuc["saglikli"] is True or "dikis_tekrari_supheli" not in sonuc["ihlaller"]  # SAĞLIĞI ETKİLEMEZ
    olaylar = sonuc["detay"]["dikis_tekrari_olaylari"]
    assert len(olaylar) == 1
    assert olaylar[0]["kanit"]["match_ratio"] >= 0.70


def test_dikis_supheli_gercek_ayri_kartta_yakalanmaz(tmp_path):
    """static_page 'ACME STUDIOS' -- slit TAMAMEN farklı içerik -- bağımsız denetim
    de KORUMALI (yanlış-pozitif üretmemeli)."""
    static_img = _metin_bloku(["ACME STUDIOS PRESENTS"])
    slit_img = _metin_bloku(["MARY JONES", "ROBERT DALE", "PRODUCER CREDIT"])
    film_dir = _yaz_film(tmp_path, "ayri-kart-film", [("static_page", static_img), ("scroll_slit", slit_img)])
    sonuc = saglik.degerlendir(film_dir)
    assert "dikis_tekrari_supheli" not in sonuc["teshis_bayraklari"]
    assert "dikis_tekrari_olaylari" not in sonuc["detay"]


def test_dikis_kontrolu_kapatilabilir(tmp_path):
    """--no-dikis-kontrolu (dikis_kontrolu=False) -- denetim hiç ÇALIŞMAZ (maliyet
    kaçışı), tekrar olsa bile bayrak YOK."""
    static_img = _metin_bloku(["JOHN SMITH"])
    slit_img = _metin_bloku(["JOHN SMITH", "MARY JONES"])
    film_dir = _yaz_film(tmp_path, "kapali-film", [("static_page", static_img), ("scroll_slit", slit_img)])
    sonuc = saglik.degerlendir(film_dir, dikis_kontrolu=False)
    assert "dikis_tekrari_supheli" not in sonuc["teshis_bayraklari"]


def test_dikis_supheli_aday_yoksa_hic_calismaz(tmp_path):
    """static_page->scroll_slit bitişikliği hiç YOKSA (ör. iki ayrı kart) PNG bile
    okunmaz -- fonksiyon erken boş liste döner (maliyet kanıtı: dikis_tekrari_
    supheli_kontrol'ü doğrudan çağırıp PNG yolunu KASITLI bozarak doğrulanır)."""
    manifest = {"status": "OK", "blocks": [
        {"kind": "static_page", "h": 90}, {"kind": "static_page", "h": 80},
    ]}
    olaylar = saglik.dikis_tekrari_supheli_kontrol(manifest, Path("/nonexistent/hicbir_yer.png"), 12)
    assert olaylar == []
