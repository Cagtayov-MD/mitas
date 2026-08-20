"""Multi-image okuma, kayıpsız derleme ve kare gruplama. GPU kullanmaz."""
import sys
import inspect
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(KULE / "src"))

from model import CiktiBozuk, _dusunme_ayikla       # noqa: E402
from okuyucu import _bloklara_ayir, kare_havuzu, oku, parcala    # noqa: E402


class SahteMotor:
    def __init__(self, cevaplar):
        self.cevaplar = list(cevaplar)
        self.sizinti = 0
        self.sorulan = []

    def sor(self, istem, kareler=None):
        self.sorulan.append((istem, kareler))
        cevap = self.cevaplar.pop(0)
        if isinstance(cevap, Exception):
            raise cevap
        return cevap


def kare(sira: int) -> dict:
    return {"sira": sira, "kaynak_sn": (sira - 1) / 2,
            "yol": f"/gecici/frame_{sira:06d}.jpg",
            "dosya": f"frame_{sira:06d}.jpg", "sha256": f"h{sira}",
            "genislik": 720, "yukseklik": 576}


def grup(no: int, ilk: int = 1, adet: int = 2) -> dict:
    ks = [kare(i) for i in range(ilk, ilk + adet)]
    return {"no": no, "bas_sn": ks[0]["kaynak_sn"],
            "bit_sn": ks[-1]["kaynak_sn"], "ilk_kare": ks[0]["sira"],
            "son_kare": ks[-1]["sira"], "kareler": ks}


CFG = {"istem": {"okuma": "OKU"},
       "derleyici": {"kesin_tekrar_penceresi": 12}}


def test_dusunme_temiz_metni_gecirir():
    metin, sizdi = _dusunme_ayikla("YONETMEN\nALI OZGENTURK")
    assert metin == "YONETMEN\nALI OZGENTURK" and sizdi is False


def test_dusunme_kapanmis_bloktan_sonrasini_alir():
    metin, sizdi = _dusunme_ayikla("dusunuyorum...</think>\nYONETMEN")
    assert metin == "YONETMEN" and sizdi is True


def test_dusunme_cift_kapanista_son_bloktan_sonrasini_alir():
    ham = "akil...</think>\nYONETMEN\n</think>\nYONETMEN"
    metin, sizdi = _dusunme_ayikla(ham)
    assert metin == "YONETMEN" and sizdi is True


def test_dusunme_kapanmamissa_bozuk_sayilir():
    with pytest.raises(CiktiBozuk):
        _dusunme_ayikla("<think> daha bitirmedim")


def test_bos_satir_blok_sinirdir():
    b = _bloklara_ayir("YONETMEN\nALI OZGENTURK\n\nMUZIK\nZULFU LIVANELI")
    assert b == [["YONETMEN", "ALI OZGENTURK"], ["MUZIK", "ZULFU LIVANELI"]]


def test_bos_bildirimi_kunye_sayilmaz():
    assert _bloklara_ayir("NO TEXT") == []
    assert _bloklara_ayir("YAZI YOK\n\nYONETMEN") == [["YONETMEN"]]


@pytest.mark.parametrize("cumle", [
    "There is no text in the provided video frames.",
    "There's no text in this picture.",
    "No text is visible in these frames.",
    "Bu karelerde metin yok.",
])
def test_yazi_yok_cumlesi_elenir(cumle):
    assert _bloklara_ayir(cumle) == []


def test_protokol_basligi_ve_altyazi_krediye_karismaz():
    ham = "[CREDITS]\nDIRECTOR\nALI\n[SUBTLES]\nBuraya gel!"
    assert _bloklara_ayir(ham) == [["DIRECTOR", "ALI"]]


def test_kesin_tekrar_elenir_ama_ham_cevap_kaybolmaz():
    m = SahteMotor(["[CREDITS]\nYONETMEN\nALI", "[CREDITS]\nYONETMEN\nAHMET"])
    bloklar, kanit = oku(m, [grup(0), grup(1, 3)], CFG)
    assert [s for b in bloklar for s in b["satirlar"]] == ["YONETMEN", "ALI", "AHMET"]
    assert kanit["kesin_tekrar_elenen"] == 1
    assert kanit["kesin_tekrarlar"][0]["metin"] == "YONETMEN"
    assert "YONETMEN" in kanit["gruplar"][1]["ham_metin"]


def test_yakin_fuzzy_varyantlar_iki_ayri_okuma_olarak_korunur():
    m = SahteMotor(["Ahmat Güldiken", "Ahmet Güldiken"])
    bloklar, kanit = oku(m, [grup(0), grup(1, 3)], CFG)
    assert [s for b in bloklar for s in b["satirlar"]] == [
        "Ahmat Güldiken", "Ahmet Güldiken"]
    assert kanit["kesin_tekrar_elenen"] == 0


def test_pencere_disindaki_gercek_tekrar_korunur():
    cfg = {**CFG, "derleyici": {"kesin_tekrar_penceresi": 2}}
    m = SahteMotor(["SON", "A\nB\nC", "SON"])
    bloklar, _ = oku(m, [grup(0), grup(1, 3), grup(2, 5)], cfg)
    assert [s for b in bloklar for s in b["satirlar"]].count("SON") == 2


def test_blok_grup_kare_ve_zaman_araligini_tasir():
    m = SahteMotor(["YONETMEN"])
    bloklar, _ = oku(m, [grup(4, 9, 3)], CFG)
    assert bloklar[0] | {} == {
        "no": 1, "grup": 4, "parca": 4, "sn": 4.0, "bit_sn": 5.0,
        "ilk_kare": 9, "son_kare": 11, "satirlar": ["YONETMEN"]}


def test_tek_bozuk_grup_kosuyu_bitirmez_ama_sayilir():
    m = SahteMotor([CiktiBozuk("bozuk"), "YONETMEN"])
    bloklar, kanit = oku(m, [grup(0), grup(1, 3)], CFG)
    assert len(bloklar) == 1 and kanit["bozuk_grup"] == 1
    assert kanit["gruplar"][0]["durum"] == "CIKTI_BOZUK"


def test_hepsi_bozuksa_ariza():
    m = SahteMotor([CiktiBozuk("x"), CiktiBozuk("y")])
    with pytest.raises(CiktiBozuk):
        oku(m, [grup(0), grup(1, 3)], CFG)


def test_metin_yoksa_blok_bos_doner_ariza_degil():
    bloklar, kanit = oku(SahteMotor(["NO TEXT"]), [grup(0)], CFG)
    assert bloklar == [] and kanit["satir_sayisi"] == 0


def test_okuma_modele_yalniz_ayri_gorsel_listesi_verir():
    m = SahteMotor(["X"])
    oku(m, [grup(0, 1, 3)], CFG)
    assert m.sorulan == [("OKU", [
        "/gecici/frame_000001.jpg", "/gecici/frame_000002.jpg",
        "/gecici/frame_000003.jpg"])]


def test_motor_ozel_istemi_ve_cagri_kaniti_kaybolmaz():
    class SchemaMotor(SahteMotor):
        istem_anahtari = "okuma"

        def son_cagri_kaniti(self):
            return {"image_transport": "repeated_image_flags",
                    "raw_json": '{"credits":["X"],"subtitles":[]}'}

    m = SchemaMotor(["[CREDITS]\nX\n[SUBTITLES]"])
    cfg = {"istem": {"okuma": "DOGRU"},
           "derleyici": {"kesin_tekrar_penceresi": 12}}
    _, kanit = oku(m, [grup(0)], cfg)
    assert m.sorulan[0][0] == "DOGRU"
    assert kanit["istem_anahtari"] == "okuma"
    assert kanit["gruplar"][0]["model_cagri"]["raw_json"].startswith("{")


def test_27b_ayni_grupta_komsu_tekrari_siler_semantik_tekrari_korur():
    class SchemaMotor(SahteMotor):
        istem_anahtari = "okuma"
        tekrar_modu = "ayni_grupta_yalniz_komsu"

    m = SchemaMotor([
        "[CREDITS]\nSTU PHILLIPS\nSTU PHILLIPS\nMUSIC BY\n"
        "MUSIC BY\nSTU PHILLIPS\nSTU PHILLIPS\n[SUBTITLES]"
    ])
    cfg = {"istem": {"okuma": "OCR"},
           "derleyici": {"kesin_tekrar_penceresi": 12}}
    bloklar, kanit = oku(m, [grup(0)], cfg)
    assert [satir for blok in bloklar for satir in blok["satirlar"]] == [
        "STU PHILLIPS", "MUSIC BY", "STU PHILLIPS"]
    assert kanit["kesin_tekrar_elenen"] == 3
    assert all(item["sebep"] == "kesin_komsu_tekrar"
               for item in kanit["kesin_tekrarlar"])


def test_motor_native_video_parametresi_kabul_etmez():
    """Native-video yolu yanlislikla geri acilamasin."""
    from model import Motor
    assert "video" not in inspect.signature(Motor.sor).parameters


def test_parcala_17_kareyi_8_8_1_gruplar(tmp_path, monkeypatch):
    import okuyucu
    from PIL import Image

    def sahte_run(cmd, **kwargs):
        desen = Path(cmd[-1])
        for i in range(1, 18):
            yol = Path(str(desen).replace("%06d", f"{i:06d}"))
            Image.new("RGB", (720, 576), color=(i, 0, 0)).save(yol)
        class R:
            returncode = 0
            stderr = ""
        return R()

    monkeypatch.setattr(okuyucu.subprocess, "run", sahte_run)
    cfg = {"grup": {"kare_sayisi": 8, "bindirme_kare": 0},
           "video": {"fps": 2, "genislik": 720,
                     "suzgec": "scale={genislik}:-2:flags=lanczos",
                     "bicim": "jpg", "jpeg_kalite": 2}}
    gruplar = parcala("f.mp4", tmp_path, cfg)
    assert [len(g["kareler"]) for g in gruplar] == [8, 8, 1]
    assert [(g["bas_sn"], g["bit_sn"]) for g in gruplar] == [
        (0.0, 3.5), (4.0, 7.5), (8.0, 8.0)]
    assert len(gruplar[0]["kareler"][0]["sha256"]) == 64


def test_sheriff_kare_havuzu_jordan_recetesiyle_multi_image_gruplanir(
        tmp_path, monkeypatch):
    import hashlib
    import json
    import okuyucu
    from PIL import Image

    kaynak = tmp_path / "pool"
    kaynak.mkdir()
    rows = []
    for sira in (11, 12, 14):
        yol = kaynak / f"frame_{sira:06d}.png"
        Image.new("RGB", (1280, 720), color=(sira, 0, 0)).save(yol)
        rows.append({
            "schema_version": "mitas.frame/v1", "section": "cikis",
            "sequence": sira, "filename": yol.name,
            "source_time_s": sira / 2, "section_time_s": (sira - 11) / 2,
            "sha256": hashlib.sha256(yol.read_bytes()).hexdigest(),
        })
    (kaynak / "frames.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    captured = {}
    def sahte_run(cmd, **kwargs):
        captured["cmd"] = cmd
        desen = Path(cmd[-1])
        for i in range(1, 4):
            yol = Path(str(desen).replace("%06d", f"{i:06d}"))
            Image.new("RGB", (720, 405), color=(i, 0, 0)).save(yol)
        class R:
            returncode = 0
            stderr = ""
        return R()

    monkeypatch.setattr(okuyucu.subprocess, "run", sahte_run)
    cfg = {"grup": {"kare_sayisi": 2, "bindirme_kare": 1},
           "video": {"fps": 2, "genislik": 720,
                     "suzgec": "scale={genislik}:-2:flags=lanczos,unsharp=5:5:1.0",
                     "bicim": "jpg", "jpeg_kalite": 2}}
    gruplar = kare_havuzu(str(kaynak), tmp_path / "scratch", cfg, bolum="cikis")

    assert [len(grup["kareler"]) for grup in gruplar] == [2, 2]
    assert [grup["ilk_kare"] for grup in gruplar] == [11, 12]
    assert gruplar[0]["kareler"][0]["kaynak_dosya"] == "frame_000011.png"
    assert "scale=720:-2:flags=lanczos,unsharp=5:5:1.0" in captured["cmd"]


def test_gecersiz_bindirme_reddedilir(tmp_path):
    with pytest.raises(Exception, match="bindirme"):
        parcala("f.mp4", tmp_path, {
            "grup": {"kare_sayisi": 8, "bindirme_kare": 8},
            "video": {"fps": 2}})


def test_top_p_generate_e_gecer():
    from model import Motor
    kw = Motor("/yok", uretim={"do_sample": True, "temperature": 0.01,
                                "top_p": 0.10}).uretim_kwargs()
    assert kw["top_p"] == 0.10 and kw["temperature"] == 0.01


def test_greedy_de_ornekleme_ayarlari_dusurulur():
    from model import Motor
    kw = Motor("/yok", uretim={"do_sample": False, "top_p": 0.1}).uretim_kwargs()
    assert "top_p" not in kw and kw["do_sample"] is False


def test_config_te_ne_varsa_generate_e_gider():
    from model import Motor
    kw = Motor("/yok", uretim={"do_sample": True, "min_p": 0.05}).uretim_kwargs()
    assert kw["min_p"] == 0.05
