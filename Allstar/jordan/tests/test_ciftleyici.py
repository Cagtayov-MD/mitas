"""Geçiş 2 — sızdırmazlık kapısı. Model geçiş 1'de olmayan metin uyduramaz."""
import sys
from pathlib import Path

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(KULE / "src"))

from model import CiktiBozuk        # noqa: E402
from ciftleyici import ciftle       # noqa: E402

CFG = {"istem": {"ciftleme": "CIFTLE"}}
BLOKLAR = [
    {"no": 1, "sn": 0.0, "satirlar": ["YONETMEN", "ALI OZGENTURK"]},
    {"no": 2, "sn": 15.0, "satirlar": ["MUZIK", "ZULFU LIVANELI"]},
]


class SahteMotor:
    def __init__(self, cevap):
        self.cevap = cevap
        self.sizinti = 0
        self.gorduğu_video = "DOKUNULMADI"

    def sor(self, istem, video=None):
        self.gorduğu_video = video
        if isinstance(self.cevap, Exception):
            raise self.cevap
        return self.cevap


def test_gecis2_GORUNTU_GORMEZ():
    """Çiftleme yalnız metinle yapılır — yoksa okuma/eşleme hatası ayrılamaz."""
    m = SahteMotor("YONETMEN\tALI OZGENTURK")
    ciftle(m, BLOKLAR, CFG)
    assert m.gorduğu_video is None


def test_sekmeli_cift_ayristirilir():
    m = SahteMotor("YONETMEN\tALI OZGENTURK")
    ciftler, kanit = ciftle(m, BLOKLAR, CFG)
    assert ciftler == [{"rol": "YONETMEN", "isim": "ALI OZGENTURK", "blok": 1}]
    assert kanit["cift_eleme"] == 0


def test_iki_noktali_cift_de_kabul():
    m = SahteMotor("MUZIK: ZULFU LIVANELI")
    ciftler, _ = ciftle(m, BLOKLAR, CFG)
    assert ciftler[0]["isim"] == "ZULFU LIVANELI" and ciftler[0]["blok"] == 2


def test_UYDURMA_isim_elenir():
    """Geçiş 1'de geçmeyen isim çıktıya giremez — sessizce değil, sayaçla."""
    m = SahteMotor("YONETMEN\tALI OZGENTURK\nOYUNCU\tTARIK AKAN")
    ciftler, kanit = ciftle(m, BLOKLAR, CFG)
    assert [c["isim"] for c in ciftler] == ["ALI OZGENTURK"]
    assert kanit["cift_eleme"] == 1


def test_uydurma_ROL_de_elenir():
    m = SahteMotor("KURGU\tALI OZGENTURK")
    ciftler, kanit = ciftle(m, BLOKLAR, CFG)
    assert ciftler == [] and kanit["cift_eleme"] == 1


def test_bicimsiz_satir_atlanir():
    m = SahteMotor("bir aciklama cumlesi\nYONETMEN\tALI OZGENTURK")
    ciftler, kanit = ciftle(m, BLOKLAR, CFG)
    assert len(ciftler) == 1 and kanit["cift_eleme"] == 0


def test_bloksuz_cagri_bos_doner():
    ciftler, kanit = ciftle(SahteMotor("X\tY"), [], CFG)
    assert ciftler == [] and kanit["cift_sayisi"] == 0


def test_gecis2_cokerse_gecis1_metni_KAYBOLMAZ():
    """Bloklar gerçek okumadır, çiftler türevdir — türev çökünce asıl atılmaz."""
    ciftler, kanit = ciftle(SahteMotor(CiktiBozuk("bozuk")), BLOKLAR, CFG)
    assert ciftler == [] and kanit["cift_ariza"] == 1
