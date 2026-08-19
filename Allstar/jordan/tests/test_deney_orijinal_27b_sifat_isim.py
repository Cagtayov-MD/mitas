from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


YOL = Path(__file__).parents[1] / "deneyler" / "orijinal_27b_sifat_isim.py"
SPEC = spec_from_file_location("orijinal_27b_sifat_isim", YOL)
MOD = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MOD)


def test_pencere_sonlari_ozgun_davranisi_acikca_yeniden_uretir(tmp_path):
    kareler = [tmp_path / f"frame_{i:04d}.jpg" for i in range(1, 72)]
    secilen = MOD.pencere_sonlarini_sec(kareler, 24)
    assert [x.name for x in secilen] == [
        "frame_0024.jpg", "frame_0048.jpg", "frame_0071.jpg"]


def test_schema_ham_kredi_ve_altyazi_listelerini_zorlar():
    nesne = {
        "credits": ["CO-STARRING", "EDMUND GILBERT", "AS CHARLES ACTON"],
        "subtitles": [],
    }
    MOD.dogrula(nesne)


def test_prompt_ozgun_etiketli_prompt_ve_schema_talimati_eklenmemis():
    assert "Use ONLY the text visible in these frames" in MOD.PROMPT
    assert "[CREDITS]" in MOD.PROMPT
    assert "[SUBTITLES]" in MOD.PROMPT
    assert "`sifat`" not in MOD.PROMPT
    assert "kayitlar" not in MOD.PROMPT


def test_komut_ozgun_gibi_her_gorsel_icin_image_anahtarini_tekrarlar(tmp_path):
    kareler = [tmp_path / "frame_0001.jpg", tmp_path / "frame_0002.jpg"]
    komut = MOD.komut(kareler)
    assert komut.count("--image") == 2
    image_degerleri = [komut[i + 1] for i, x in enumerate(komut) if x == "--image"]
    assert image_degerleri == [str(kare.resolve()) for kare in kareler]
    assert "--json-schema" in komut
    assert komut[komut.index("--temp") + 1] == "0.01"
    assert komut[komut.index("--repeat-penalty") + 1] == "1.05"


def test_birlestirme_tekrarlari_bile_kayipsiz_korur():
    a = {
        "credits": ["THEME", "STU PHILLIPS"],
        "subtitles": [],
    }
    b = {
        "credits": ["THEME", "STU PHILLIPS", "MUSIC BY", "STU PHILLIPS"],
        "subtitles": [],
    }
    sonuc = MOD.kesin_birlestir([a, b])
    assert sonuc["credits"] == [
        "THEME", "STU PHILLIPS", "THEME", "STU PHILLIPS", "MUSIC BY",
        "STU PHILLIPS"]
