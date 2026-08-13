"""Geçiş 1 — blok ayırma, tekrar düşürme, düşünme sızıntısı. Model koşmaz."""
import sys
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(KULE / "src"))

from model import CiktiBozuk, _dusunme_ayikla       # noqa: E402
from okuyucu import _bloklara_ayir, oku, parcala    # noqa: E402


class SahteMotor:
    """Sırayla hazır cevap döner; GPU yok, transformers yok."""

    def __init__(self, cevaplar):
        self.cevaplar = list(cevaplar)
        self.sizinti = 0
        self.sorulan = []

    def sor(self, istem, video=None):
        self.sorulan.append((istem, video))
        c = self.cevaplar.pop(0)
        if isinstance(c, Exception):
            raise c
        return c


CFG = {"istem": {"okuma": "OKU"}}


# ── düşünme sızıntısı ───────────────────────────────────────────────────
def test_dusunme_temiz_metni_gecirir():
    metin, sizdi = _dusunme_ayikla("YONETMEN\nALI OZGENTURK")
    assert metin == "YONETMEN\nALI OZGENTURK" and sizdi is False


def test_dusunme_kapanmis_bloktan_sonrasini_alir():
    metin, sizdi = _dusunme_ayikla("dusunuyorum...</think>\nYONETMEN")
    assert metin == "YONETMEN" and sizdi is True


def test_dusunme_cift_kapanista_SON_bloktan_sonrasini_alir():
    """Sandbox'ta gözlenen bozukluk: cevap iki kez, kaçak </think> ile."""
    ham = "akil...</think>\nYONETMEN\n</think>\nYONETMEN"
    metin, sizdi = _dusunme_ayikla(ham)
    assert metin == "YONETMEN" and sizdi is True


def test_dusunme_kapanmamissa_bozuk_sayilir():
    with pytest.raises(CiktiBozuk):
        _dusunme_ayikla("<think> daha bitirmedim")


# ── blok ayırma ─────────────────────────────────────────────────────────
def test_bos_satir_blok_sinirdir():
    b = _bloklara_ayir("YONETMEN\nALI OZGENTURK\n\nMUZIK\nZULFU LIVANELI")
    assert b == [["YONETMEN", "ALI OZGENTURK"], ["MUZIK", "ZULFU LIVANELI"]]


def test_bos_isaret_satiri_isim_sayilmaz():
    """'NO TEXT' dürüst bir boş-işaretidir, künye satırı değil."""
    assert _bloklara_ayir("NO TEXT") == []
    assert _bloklara_ayir("YAZI YOK\n\nYONETMEN") == [["YONETMEN"]]


@pytest.mark.parametrize("cumle", [
    # KUKLA ADAM koşusunda (2026-08-13) transkripte SIZAN gerçek cümleler
    "There is no text in the provided video frames.",
    "There is no text in the picture.",
    "There's no text in this picture.",
    "There is no text in the provided images.",
    "There is no text visible in the provided video frames. The images show "
    "people walking down steps from a house, but there are no signs, logos, "
    "or subtitles present in the shots.",
    "No text is visible in these frames.",
    "Bu karelerde metin yok.",
])
def test_yazi_yok_CUMLESI_de_elenir(cumle):
    """Model 'yazı yok'u cümleyle söyleyince o bir künye satırı DEĞİLDİR.

    Kısa işaret süzgeci bunları kaçırıyordu; yorum transkripte sızıyordu.
    """
    assert _bloklara_ayir(cumle) == []


def test_yazi_yok_cumlesi_gercek_satiri_goturmez():
    b = _bloklara_ayir("There is no text in the picture.\n\nYONETMEN\nALI")
    assert b == [["YONETMEN", "ALI"]]


# ── oku(): tekrar düşürme + kanıt ───────────────────────────────────────
def test_bindirmedeki_ayni_blok_tekrarlanmaz():
    m = SahteMotor(["YONETMEN\nALI OZGENTURK", "YONETMEN\nALI OZGENTURK\n\nMUZIK"])
    bloklar, kanit = oku(m, [{"no": 0, "bas_sn": 0.0, "yol": "a.mp4"},
                             {"no": 1, "bas_sn": 13.0, "yol": "b.mp4"}], CFG)
    assert [b["satirlar"] for b in bloklar] == [["YONETMEN", "ALI OZGENTURK"],
                                                ["MUZIK"]]
    assert kanit["blok_sayisi"] == 2 and kanit["parca_sayisi"] == 2


def test_uzak_tekrar_korunur():
    """Ardışık OLMAYAN tekrar gerçek olabilir — silmek veri kaybıdır."""
    m = SahteMotor(["SON", "ARADA", "SON"])
    p = [{"no": i, "bas_sn": 0.0, "yol": "x.mp4"} for i in range(3)]
    bloklar, _ = oku(m, p, CFG)
    assert [b["satirlar"] for b in bloklar] == [["SON"], ["ARADA"], ["SON"]]


def test_blok_parca_ve_saniye_tasir():
    m = SahteMotor(["YONETMEN"])
    bloklar, _ = oku(m, [{"no": 4, "bas_sn": 52.0, "yol": "a.mp4"}], CFG)
    assert bloklar[0]["parca"] == 4 and bloklar[0]["sn"] == 52.0


def test_tek_bozuk_parca_kosuyu_bitirmez_ama_sayilir():
    m = SahteMotor([CiktiBozuk("bozuk"), "YONETMEN"])
    p = [{"no": 0, "bas_sn": 0.0, "yol": "a"}, {"no": 1, "bas_sn": 1.0, "yol": "b"}]
    bloklar, kanit = oku(m, p, CFG)
    assert len(bloklar) == 1 and kanit["bozuk_parca"] == 1


def test_hepsi_bozuksa_ariza():
    m = SahteMotor([CiktiBozuk("x"), CiktiBozuk("y")])
    p = [{"no": 0, "bas_sn": 0.0, "yol": "a"}, {"no": 1, "bas_sn": 1.0, "yol": "b"}]
    with pytest.raises(CiktiBozuk):
        oku(m, p, CFG)


def test_metin_yoksa_blok_bos_doner_ariza_degil():
    """Klipte yazı yoksa bu içerik gerçeğidir — arıza değil."""
    m = SahteMotor(["NO TEXT"])
    bloklar, kanit = oku(m, [{"no": 0, "bas_sn": 0.0, "yol": "a"}], CFG)
    assert bloklar == [] and kanit["satir_sayisi"] == 0


def test_okuma_modele_VIDEO_verir():
    """Jordan'ın geçiş 1'i native video ile sorar — kare listesiyle değil."""
    m = SahteMotor(["X"])
    oku(m, [{"no": 0, "bas_sn": 0.0, "yol": "/yol/parca_000.mp4"}], CFG)
    assert m.sorulan[0][1] == "/yol/parca_000.mp4"


# ── parcala(): kare tavanı ──────────────────────────────────────────────
def test_kare_tavani_parca_suresini_kisar(tmp_path, monkeypatch):
    """30 kare çalışıyor, 36 OOM — tavan aşılamaz (ölçülmüş sınır)."""
    import okuyucu
    monkeypatch.setattr(okuyucu, "sure_sn", lambda v: 40.0)
    cagri = {}

    def sahte_run(cmd, **kw):
        if "-t" in cmd:
            cagri.setdefault("t", []).append(float(cmd[cmd.index("-t") + 1]))
        Path(cmd[-1]).write_bytes(b"x")
        class R: returncode = 0; stderr = ""
        return R()

    monkeypatch.setattr(okuyucu.subprocess, "run", sahte_run)
    cfg = {"parca": {"sure_sn": 60, "bindirme_sn": 2, "kare_tavani": 30},
           "video": {"fps": 2, "genislik": 720, "suzgec": "scale={genislik}:-2"}}
    parcala("f.mp4", tmp_path, cfg)
    assert max(cagri["t"]) == pytest.approx(15.0)   # 30 kare / 2 fps
