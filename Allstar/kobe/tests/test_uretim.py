"""Kobe artefakt üretimi — kare havuzu ve sessiz klip. ffmpeg sahte."""
import json
import sys
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))

import main  # noqa: E402
from sozlesme import Cikti, Girdi  # noqa: E402


class _SahteSonuc:
    def __init__(self, kare):
        self.start_frame, self.yontem, self.guven = kare, "tespit_v5", 0.9
        self.script, self.notlar, self.ocr_hata = "en", "", 0


def _kare_dizini(p: Path, adet: int = 200) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    for i in range(1, adet + 1):
        (p / f"c_{i:05d}.png").write_bytes(b"x")
    return p


# ── varsayılan: artefakt üretilmez ──────────────────────────────────────
def test_varsayilan_artefakt_uretmez(tmp_path, monkeypatch):
    d = _kare_dizini(tmp_path / "kareler")
    monkeypatch.setattr(main, "_tespit", lambda x, c: _SahteSonuc(100))
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out")
    assert c.uretilen is None
    assert not (tmp_path / "out" / "F1" / "cikis" / "kareler").exists()
    assert not (tmp_path / "out" / "F1" / "cikis" / "klip").exists()


# ── kare havuzu ─────────────────────────────────────────────────────────
def test_kare_havuzu_10sn_geriden_baslar(tmp_path, monkeypatch):
    """fps=2 → 10 sn = 20 kare geri. onset 100 ise havuz 80'den başlar."""
    d = _kare_dizini(tmp_path / "kareler")
    monkeypatch.setattr(main, "_tespit", lambda x, c: _SahteSonuc(100))
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", uret="kare")
    havuz = tmp_path / "out" / "F1" / "cikis" / "kareler"
    kareler = sorted(havuz.glob("*.png"))
    assert c.uretilen[0]["tip"] == "kare"
    assert c.uretilen[0]["ilk_kare"] == 80
    assert kareler[0].name == "c_00080.png"
    assert kareler[-1].name == "c_00200.png"
    assert len(kareler) == 121


def test_kare_havuzu_kaynak_dizine_dokunmaz(tmp_path, monkeypatch):
    """Tek-yazar ilkesi: dışarıdan verilen dizin bozulmaz."""
    d = _kare_dizini(tmp_path / "kareler")
    monkeypatch.setattr(main, "_tespit", lambda x, c: _SahteSonuc(100))
    main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", uret="kare")
    assert len(list(d.glob("*.png"))) == 200


def test_kare_havuzu_sifirin_altina_inmez(tmp_path, monkeypatch):
    """onset 5 ise 10 sn geri negatif olurdu — 1'e kırpılır."""
    d = _kare_dizini(tmp_path / "kareler", adet=50)
    monkeypatch.setattr(main, "_tespit", lambda x, c: _SahteSonuc(5))
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", uret="kare")
    assert c.uretilen[0]["ilk_kare"] == 1


# ── sessiz klip ─────────────────────────────────────────────────────────
def test_klip_10sn_geriden_kesilir_ve_sessiz(tmp_path, monkeypatch):
    cagrilar = []

    def _sahte_ffmpeg(video, hedef, bas_sn):
        cagrilar.append((video, bas_sn))
        hedef.parent.mkdir(parents=True, exist_ok=True)
        hedef.write_bytes(b"mp4")
        return hedef

    monkeypatch.setattr(main, "SCRATCH", tmp_path / "scratch")
    monkeypatch.setattr(main, "kare_cikar", lambda v, h, b="cikis": (_kare_dizini(h), 400))
    monkeypatch.setattr(main, "_tespit", lambda x, c: _SahteSonuc(100))
    monkeypatch.setattr(main, "klip_kes", _sahte_ffmpeg)
    c = main.tek(Girdi(film_id="F1", video="/y/F1.mp4"), tmp_path / "out", uret="klip")
    # pencere 400 sn + onset 100/2 = 450 sn; 10 sn geri → 440
    assert cagrilar == [("/y/F1.mp4", 440.0)]
    assert c.uretilen[0]["tip"] == "klip"
    assert (tmp_path / "out" / "F1" / "cikis" / "klip" / "klip.mp4").exists()


def test_klip_ffmpeg_komutu_format_ve_sessizlik_tasir(tmp_path, monkeypatch):
    """Regresyon: geçici dosya '.mp4.tmp' ile bittiği için ffmpeg formatı
    uzantıdan çıkaramıyor ve 'Unable to choose an output format' veriyordu.
    Bu, klip_kes'in tamamı sahtelendiği için birim testlerden kaçmıştı —
    yalnız gerçek koşuda görüldü. Komutun kendisi burada denetlenir."""
    yakalanan = {}

    class _R:
        returncode = 0
        stderr = ""

    def _sahte_run(cmd, **kw):
        yakalanan["cmd"] = cmd
        Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(cmd[-1]).write_bytes(b"mp4")
        return _R()

    monkeypatch.setattr(main.subprocess, "run", _sahte_run)
    main.klip_kes("/y/F1.mp4", tmp_path / "klip" / "klip.mp4", 440.0)
    c = yakalanan["cmd"]
    assert "-f" in c and c[c.index("-f") + 1] == "mp4", "format acikca verilmeli"
    assert "-an" in c, "klip SESSIZ olmali"
    assert c[c.index("-ss") + 1] == "440.000"
    assert not (tmp_path / "klip" / "klip.mp4.tmp").exists(), "gecici dosya kalmamali"


def test_klip_video_olmadan_istenirse_ARIZA(tmp_path, monkeypatch):
    """Kare dizininden klip kesilemez — sessizce atlamak YASAK."""
    d = _kare_dizini(tmp_path / "kareler")
    monkeypatch.setattr(main, "_tespit", lambda x, c: _SahteSonuc(100))
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", uret="klip")
    assert c.durum == "ARIZA" and c.sinif == "GIRDI_HATASI"
    assert c.uretilen is None


# ── kredi yok / arıza: artefakt üretilmez ───────────────────────────────
def test_kredi_yokta_artefakt_uretilmez(tmp_path, monkeypatch):
    d = _kare_dizini(tmp_path / "kareler")
    monkeypatch.setattr(main, "_tespit", lambda x, c: _SahteSonuc(-1))
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", uret="kare")
    assert c.durum == "KREDI_YOK" and c.uretilen is None
    assert not (tmp_path / "out" / "F1" / "cikis" / "kareler").exists()


# ── kuyruk değişmezi: _TAMAM en SON ─────────────────────────────────────
def test_TAMAM_artefakttan_SONRA_yazilir(tmp_path, monkeypatch):
    """Tüketici _TAMAM görünce artefakt hazır olmalı — yarısı değil."""
    d = _kare_dizini(tmp_path / "kareler")
    monkeypatch.setattr(main, "_tespit", lambda x, c: _SahteSonuc(100))
    main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", uret="kare")
    o = tmp_path / "out" / "F1" / "cikis"
    son_kare = max((p.stat().st_mtime for p in (o / "kareler").glob("*.png")))
    assert (o / "_TAMAM").stat().st_mtime >= son_kare


def test_uretilen_kobe_jsona_yazilir(tmp_path, monkeypatch):
    d = _kare_dizini(tmp_path / "kareler")
    monkeypatch.setattr(main, "_tespit", lambda x, c: _SahteSonuc(100))
    main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", uret="kare")
    j = json.loads((tmp_path / "out" / "F1" / "cikis" / "kobe.json").read_text(encoding="utf-8"))
    assert j["uretilen"][0]["tip"] == "kare" and j["uretilen"][0]["yol"] == "kareler"
    assert j["uretilen"][0]["adet"] == 121


# ── sözleşme: uretilen alanı ────────────────────────────────────────────
def test_kredi_yok_uretilen_tasiyamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="KREDI_YOK", uretilen={"tip": "kare"})


def test_ariza_uretilen_tasiyamaz():
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="ARIZA", sinif="X", mesaj="y",
              uretilen={"tip": "klip"})
