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
    monkeypatch.setattr("okuyucu.kare_havuzu",
                        lambda d, h, c, bolum=None: [
                            {"no": 0, "bas_sn": 0.0, "yol": "frame.jpg"}])
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
    assert j["ciftler"] == []
    assert j["kanit"]["cift_atlandi"] == 1
    assert j["motor_surumu"].startswith("jordan@")


def test_ciftleme_acikca_istenirse_calisir(klip, tmp_path):
    c = main.tek(Girdi(film_id="F2", video=str(klip),
                       config={"ciftleme_atla": False}), kok=tmp_path / "out")
    assert c.ciftler[0]["isim"] == "ALI OZGENTURK"


def test_kare_havuzu_girdisi_frame_pool_olarak_kaydedilir(tmp_path):
    havuz = tmp_path / "frames"
    havuz.mkdir()
    c = main.tek(Girdi(film_id="F3", kareler=str(havuz)), kok=tmp_path / "out")
    assert c.durum == "OKUNDU"
    assert c.kanit["girdi_modu"] == "frame_pool"


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


def test_kare_havuzu_yoksa_girdi_hatasi(tmp_path):
    c = main.tek(Girdi(film_id="F1", kareler=str(tmp_path / "yok")),
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


def test_27b_backend_olculmus_24_kare_grubunu_alir():
    cfg = main._config({"model": {"backend": "llama_mtmd"}})
    assert cfg["grup"]["kare_sayisi"] == cfg["llama_mtmd"]["grup_kare"] == 24


def test_varsayilan_8b_ve_8_kare_1_bindirmedir():
    """Varsayılan (Çağatay kararı 2026-08-19): Qwen3-VL-8B, kare=8, bindirme=1 — 13-klip dizi GT yarışının ölçülmüş kazananı (470/519)."""
    cfg = main._config()
    assert cfg["model"]["backend"] == "transformers"
    assert cfg["model"]["yol"] == "model/qwen3-vl-8b"
    assert cfg["grup"]["kare_sayisi"] == 8
    assert cfg["grup"]["bindirme_kare"] == 1
    assert cfg["uretim"]["max_new_tokens"] == 512
    # Ölçülmüş kaldıraç: bu iki cümle sessizce düşerse okuma kalitesi sessizce düşer.
    istem = cfg["istem"]["okuma"].strip()
    assert istem.endswith("Never split a name or title across multiple lines.")
    assert "dotless ı" in istem


def test_27b_acik_grup_ezmesini_korur():
    cfg = main._config({"model": {"backend": "llama_mtmd"},
                        "grup": {"kare_sayisi": 4}})
    assert cfg["grup"]["kare_sayisi"] == 4
