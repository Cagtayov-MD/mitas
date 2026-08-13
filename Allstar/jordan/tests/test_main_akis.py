"""main.tek / main.toplu akışı — model yüklenmez, ffmpeg koşmaz."""
import json
import sys
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(KULE / "src"))

import main                                  # noqa: E402
from sozlesme import Girdi                   # noqa: E402
from model import BellekHatasi, CiktiBozuk, ModelHatasi   # noqa: E402
from okuyucu import VideoHatasi              # noqa: E402

BLOKLAR = [{"no": 1, "parca": 0, "sn": 0.0,
            "satirlar": ["YONETMEN", "ALI OZGENTURK"]}]


@pytest.fixture
def klip(tmp_path):
    v = tmp_path / "KLIP.mp4"
    v.write_bytes(b"sahte")
    return v


@pytest.fixture(autouse=True)
def sahte_boru(monkeypatch):
    """Varsayılan: parçalama ve model başarılı. Testler tek tek ezer."""
    monkeypatch.setattr(main, "motor_kur", lambda cfg: object())
    monkeypatch.setattr("okuyucu.parcala",
                        lambda v, h, c: [{"no": 0, "bas_sn": 0.0, "yol": "p.mp4"}])
    monkeypatch.setattr("okuyucu.oku", lambda m, p, c: (BLOKLAR, {"blok_sayisi": 1}))
    monkeypatch.setattr("ciftleyici.ciftle",
                        lambda m, b, c: ([{"rol": "YONETMEN",
                                           "isim": "ALI OZGENTURK", "blok": 1}],
                                         {"cift_sayisi": 1, "cift_eleme": 0}))


def _kos(klip, tmp_path, film_id="F1", bolum="cikis"):
    return main.tek(Girdi(film_id=film_id, video=str(klip), bolum=bolum),
                    kok=tmp_path / "out")


# ── mutlu yol ───────────────────────────────────────────────────────────
def test_okundu_json_txt_ve_tamam_yazar(klip, tmp_path):
    c = _kos(klip, tmp_path)
    d = tmp_path / "out" / "F1" / "cikis"
    assert c.durum == "OKUNDU"
    assert (d / "jordan.json").exists() and (d / "_TAMAM").exists()
    assert (d / "jordan.txt").read_text(encoding="utf-8").splitlines() == [
        "YONETMEN", "ALI OZGENTURK"]
    j = json.loads((d / "jordan.json").read_text(encoding="utf-8"))
    assert j["ciftler"][0]["isim"] == "ALI OZGENTURK"
    assert j["kanit"]["cift_eleme"] == 0 and j["motor_surumu"].startswith("jordan@")


def test_metin_yok_ariza_degildir(klip, tmp_path, monkeypatch):
    monkeypatch.setattr("okuyucu.oku", lambda m, p, c: ([], {"blok_sayisi": 0}))
    c = _kos(klip, tmp_path)
    assert c.durum == "METIN_YOK" and c.sinif is None
    assert (tmp_path / "out" / "F1" / "cikis" / "_TAMAM").exists()


def test_scratch_temizlenir(klip, tmp_path):
    _kos(klip, tmp_path)
    assert not (main.SCRATCH / "F1" / "cikis").exists()


def test_bolum_ayri_yazilir(klip, tmp_path):
    _kos(klip, tmp_path, bolum="cikis")
    _kos(klip, tmp_path, bolum="giris")
    assert (tmp_path / "out" / "F1" / "cikis" / "jordan.json").exists()
    assert (tmp_path / "out" / "F1" / "giris" / "jordan.json").exists()


# ── arıza sınıflandırması ───────────────────────────────────────────────
def test_video_yoksa_girdi_hatasi(tmp_path):
    c = main.tek(Girdi(film_id="F1", video=str(tmp_path / "yok.mp4")),
                 kok=tmp_path / "out")
    assert c.durum == "ARIZA" and c.sinif == "GIRDI_HATASI"


@pytest.mark.parametrize("istisna,beklenen", [
    (VideoHatasi("ffmpeg patladi"), "VIDEO_OKUNAMADI"),
    (BellekHatasi("CUDA out of memory"), "BELLEK"),
    (CiktiBozuk("dusunme kapanmadi"), "CIKTI_BOZUK"),
    (ModelHatasi("agirlik yok"), "MODEL"),
    (RuntimeError("beklenmedik"), "MODEL"),
])
def test_ariza_siniflari(klip, tmp_path, monkeypatch, istisna, beklenen):
    def patla(*a, **k):
        raise istisna
    hedef = "okuyucu.parcala" if beklenen == "VIDEO_OKUNAMADI" else "okuyucu.oku"
    monkeypatch.setattr(hedef, patla)
    c = _kos(klip, tmp_path)
    assert c.durum == "ARIZA" and c.sinif == beklenen
    assert c.mesaj and (tmp_path / "out" / "F1" / "cikis" / "_TAMAM").exists()


def test_ariza_blok_tasimaz(klip, tmp_path, monkeypatch):
    """Arıza anında yarım okuma çıktı sayılmaz — sözleşme zorlar."""
    def patla(*a, **k):
        raise BellekHatasi("OOM")
    monkeypatch.setattr("okuyucu.oku", patla)
    c = _kos(klip, tmp_path)
    assert c.bloklar == [] and c.ciftler == []
    j = json.loads((tmp_path / "out" / "F1" / "cikis" / "jordan.json")
                   .read_text(encoding="utf-8"))
    assert "bloklar" not in j and j["sinif"] == "BELLEK"


# ── toplu kuyruk ────────────────────────────────────────────────────────
def test_toplu_tamam_olani_atlar(tmp_path, capsys):
    giris = tmp_path / "klipler"
    giris.mkdir()
    for ad in ("A.mp4", "B.mp4"):
        (giris / ad).write_bytes(b"x")
    kok = tmp_path / "out"
    (kok / "A" / "cikis").mkdir(parents=True)
    (kok / "A" / "cikis" / "_TAMAM").write_text("")

    sonuc = main.toplu(giris, kok=kok)
    assert [c.film_id for c in sonuc] == ["B"]
    assert "[atla] A" in capsys.readouterr().out


def test_toplu_film_id_dosya_adindan(tmp_path):
    giris = tmp_path / "k"
    giris.mkdir()
    (giris / "2025-1307-1-0000-50-0.mp4").write_bytes(b"x")
    sonuc = main.toplu(giris, kok=tmp_path / "out")
    assert sonuc[0].film_id == "2025-1307-1-0000-50-0"
