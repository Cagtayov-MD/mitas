# -*- coding: utf-8 -*-
"""sozlesme.py sözleşme değişmezleri — kobe/mcgrady test_sozlesme kalıbı."""
import json
import sys
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KULE))

import pytest

from sozlesme import Cikti, GirdiHatasi, ariza, paket_oku  # noqa: E402


def _paket(tmp_path, **uzanti):
    paket = {"schema_version": "iverson.girdi/v1", "film_id": "t-1", "ses": "/yol/a.wav"}
    paket.update(uzanti)
    p = tmp_path / "paket.json"
    p.write_text(json.dumps(paket, ensure_ascii=False), encoding="utf-8")
    return p


def test_paket_okunur(tmp_path):
    raw = paket_oku(_paket(tmp_path))
    assert raw["ses"] == "/yol/a.wav"


def test_paket_yanlis_sema(tmp_path):
    with pytest.raises(GirdiHatasi):
        paket_oku(_paket(tmp_path, schema_version="baska/v9"))


def test_paket_json_degil(tmp_path):
    p = tmp_path / "bozuk.json"
    p.write_text("{", encoding="utf-8")
    with pytest.raises(GirdiHatasi):
        paket_oku(p)


# ── Cikti değişmezleri ───────────────────────────────────────────────────────
def test_ariza_sinif_mesaj_zorunlu():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="ARIZA", sinif=None, mesaj=None)


def test_ariza_disi_sinif_tasiyamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="METIN_YOK", sinif="X", mesaj="y")


def test_transkript_segmentsiz_olamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="TRANSKRIPT", segment_sayisi=0, transkript=None)


def test_metin_yok_segment_tasiyamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="METIN_YOK", segment_sayisi=3,
              transkript={"yol": "x"})


def test_dil_desteksiz_dil_zorunlu():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="DIL_DESTEKSIZ", dil=None)


def test_dil_desteksiz_transkript_tasiyamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="DIL_DESTEKSIZ", dil="ku",
              transkript={"yol": "x"})


def test_gecersiz_durum():
    with pytest.raises(ValueError):
        Cikti(film_id="f", durum="BILINMEYEN")


# ── yaz: atomik + _TAMAM + sheriff kimliği ──────────────────────────────────
def test_yaz_tamam_marker(tmp_path):
    c = Cikti(film_id="f1", durum="METIN_YOK", dil=None, ses_sure_sn=12.0)
    yol = c.yaz(tmp_path)
    assert yol == tmp_path / "f1" / "iverson.json"
    assert (tmp_path / "f1" / "_TAMAM").exists()
    assert not (tmp_path / "f1" / "iverson.json.tmp").exists()
    d = json.loads(yol.read_text(encoding="utf-8"))
    assert d["durum"] == "METIN_YOK" and d["segment_sayisi"] == 0


def test_yaz_sheriff_kimligi(tmp_path, monkeypatch):
    for k in ("MITAS_SHERIFF_RUN_ID", "MITAS_SHERIFF_TASK_ID", "MITAS_SHERIFF_ATTEMPT_ID"):
        monkeypatch.setenv(k, "x")
    c = Cikti(film_id="f2", durum="METIN_YOK")
    d = json.loads(c.yaz(tmp_path).read_text(encoding="utf-8"))
    assert d["schema_version"] == "mitas.boundary/v1"
    assert "identity" in d


def test_ariza_fabrikasi_sozluk():
    c = ariza("f", "MODEL_YOK", "yok")
    d = c.sozluk()
    assert d["sinif"] == "MODEL_YOK" and "transkript" not in d
