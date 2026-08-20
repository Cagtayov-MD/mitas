"""BİTİŞ ŞELALESİ — giriş jeneriğinin bitiş düzeltmesi (2026-08-17).

Kalibrasyon hikâyesi: 36 filmde sinir 20'sini çok erken kesiyordu; şelale
(ters-motor → sağdan-sola kuralı → sinir) medyan hatayı 122→19 kareye indirdi
(eğitim 18 / sınav 18, değerler teyit — bkz. olcum/giris/bitis_kalibrasyonu.md).
Bu testler kuralın MANTIĞINI kilitler; kalite ölçüm yatağının işi.
"""
import sys
from pathlib import Path

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))

import main  # noqa: E402
from giris import bitis  # noqa: E402


# ── sağdan-sola kuralı: saf fonksiyon ───────────────────────────────────
def test_kural_kalin_blogun_sag_ucusu():
    # 200..250 arası yoğun içerik (blok), 300'de izci TEK kare. Kural bloğun
    # sağ ucundan (w−k)=18 kare sağa taşar — pencere [239..269] hâlâ ≥12 içerik
    # tutar. Bu taşma KALİBRASYONUN parçasıdır (offline testle birebir aynı
    # kod); blok kenarı keskinse sistematik +18, aksi halde daha az.
    ks = list(range(200, 251)) + [300]
    assert bitis.sagdan_sola(ks, w=30, k=12) == 269


def test_kural_izciler_kaldirilamazsa_uzamaz():
    # izciler yoğun OLUrsa (>=k eşiği) kural onları blok sanır — kalibrasyon
    # gerçeği; bu davranış BİLİNÇLİ (eşik W/K ile ayarlanır, koda değil
    # ölçüme dokunulur)
    ks = list(range(200, 251)) + list(range(340, 380))
    assert bitis.sagdan_sola(ks, w=30, k=12) == 379


def test_kural_blok_yoksa_none():
    assert bitis.sagdan_sola([5, 50, 120, 300], w=30, k=12) is None
    assert bitis.sagdan_sola([], w=30, k=12) is None


# ── şelale: duzelt ──────────────────────────────────────────────────────
def _b(bulundu=True, bit=41):
    return {"bulundu": bulundu, "baslangic_kare": 1, "baslangic_sn": 0.0,
            "bitis_kare": bit,
            "bitis_sn": (round(bit / 2, 2) if bit is not None else None),
            "guven": 0.75, "kanit": {"sinir_kaynagi": "tespit"}}


def test_selale_ters_motor_kazanir(monkeypatch):
    monkeypatch.setattr(bitis.havuz, "icerik_kareleri", lambda d: [])
    b = bitis.duzelt(_b(bit=41), "/yok", ters_aday=240)
    assert b["bitis_kare"] == 240 and b["bitis_sn"] == 120.0
    assert b["kanit"]["bitis_kaynagi"] == "ters-motor"
    assert b["kanit"]["bitis_sinir_ham"] == 41


def test_selale_ters_ateslenmezse_kural(monkeypatch):
    monkeypatch.setattr(bitis.havuz, "icerik_kareleri",
                        lambda d: [f"/x/c_{i:05d}.png" for i in range(200, 251)])
    b = bitis.duzelt(_b(bit=41), "/yok", ters_aday=None)
    assert b["bitis_kare"] == 250 and b["kanit"]["bitis_kaynagi"] == "kural"


def test_selale_ikisi_de_yoksa_sinir_dokunulmaz(monkeypatch):
    monkeypatch.setattr(bitis.havuz, "icerik_kareleri", lambda d: [])
    b = bitis.duzelt(_b(bit=41), "/yok", ters_aday=None)
    assert b["bitis_kare"] == 41 and "bitis_kaynagi" not in b["kanit"]


def test_selale_kredi_yokta_dokunulmaz(monkeypatch):
    monkeypatch.setattr(bitis.havuz, "icerik_kareleri", lambda d: [])
    b = bitis.duzelt(_b(bulundu=False, bit=None), "/yok", ters_aday=300)
    assert b["bitis_kare"] is None


def test_selale_kredi_yokta_yogun_icerik_kanitiyla_kurtarir(monkeypatch):
    """Statik açılış blob kalkanına takılsa da yoğun OCR kanıtı kaybolmaz."""
    monkeypatch.setattr(
        bitis.havuz, "icerik_kareleri",
        lambda d: [f"/x/g_{i:05d}.png" for i in range(100, 116)],
    )
    b = _b(bulundu=False, bit=None)
    b["guven"] = 0.0
    b["kanit"] = {"tespit_ham": {"found": False}}

    sonuc = bitis.duzelt(b, "/yok", ters_aday=None)

    assert sonuc["bulundu"] is True
    assert sonuc["baslangic_kare"] == 1 and sonuc["baslangic_sn"] == 0.0
    assert sonuc["bitis_kare"] == 115 and sonuc["bitis_sn"] == 57.5
    assert sonuc["guven"] == 0.0  # uydurma güven üretilmez
    assert sonuc["kanit"]["sinir_kaynagi"] == "bitis-kaniti"
    assert sonuc["kanit"]["bitis_kaynagi"] == "kural"
    assert sonuc["kanit"]["bitis_icerik_kare_sayisi"] == 16


def test_selale_kredi_yokta_ince_izciler_kurtaramaz(monkeypatch):
    """Dağınık diyalog ismi/tabela, kalın kredi bloğu sayılmaz."""
    monkeypatch.setattr(
        bitis.havuz, "icerik_kareleri",
        lambda d: ["/x/g_00010.png", "/x/g_00080.png", "/x/g_00160.png"],
    )
    sonuc = bitis.duzelt(_b(bulundu=False, bit=None), "/yok", ters_aday=None)
    assert sonuc["bulundu"] is False
    assert sonuc["bitis_kare"] is None


def test_selale_kapatilabilir(monkeypatch):
    monkeypatch.setattr(bitis.havuz, "icerik_kareleri", lambda d: ["x"])
    b = bitis.duzelt(_b(bit=41), "/yok",
                     config={"giris": {"bitis_selale": False}}, ters_aday=240)
    assert b["bitis_kare"] == 41


# ── ters-motor yardımcısı (main.py) ────────────────────────────────────
def test_ters_bitis_koordinat_donusumu(tmp_path, monkeypatch):
    """5 kare: ters görünümde motor start=2 derse gerçek bitiş 5−2+1=4."""
    for i in range(1, 6):
        (tmp_path / f"c_{i:05d}.png").write_bytes(b"x")
    monkeypatch.setattr(main, "SCRATCH", tmp_path / "scratch")
    monkeypatch.setattr(main, "_tespit",
                        lambda d, c: _SahteSonuc(2))
    assert main._ters_bitis(tmp_path) == 4
    assert not (tmp_path / "scratch" / "ters").exists() or \
        not list((tmp_path / "scratch" / "ters").glob("*"))   # temizlik


def test_ters_bitis_kredi_yoksa_none(tmp_path, monkeypatch):
    for i in range(1, 6):
        (tmp_path / f"c_{i:05d}.png").write_bytes(b"x")
    monkeypatch.setattr(main, "SCRATCH", tmp_path / "scratch")
    monkeypatch.setattr(main, "_tespit", lambda d, c: _SahteSonuc(-1))
    assert main._ters_bitis(tmp_path) is None


def test_ters_bitis_motor_patlarsa_none(tmp_path, monkeypatch):
    for i in range(1, 6):
        (tmp_path / f"c_{i:05d}.png").write_bytes(b"x")
    monkeypatch.setattr(main, "SCRATCH", tmp_path / "scratch")
    def _patla(d, c):
        raise RuntimeError("OOM")
    monkeypatch.setattr(main, "_tespit", _patla)
    assert main._ters_bitis(tmp_path) is None


class _SahteSonuc:
    def __init__(self, kare):
        self.start_frame, self.yontem, self.guven = kare, "tespit_v5", 0.9
        self.script, self.notlar, self.ocr_hata = "en", "", 0
