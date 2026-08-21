"""Kare hazırlığı: reçete birliği (iki yol AYNI sha256), gruplama sınırları,
manifest alanları, sha256 kararlılığı, fps varsayımı, kayma hızı. GPU/model yok."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(KULE / "src"))

from hazirlik import (  # noqa: E402
    VideoHatasi, gruplar, kare_dizininden_hazirla, kayma_hizi, videodan_hazirla,
)


def _ffmpeg_var_mi() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10)
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


ffmpeg_gerekli = pytest.mark.skipif(not _ffmpeg_var_mi(), reason="ffmpeg bulunamadi")


def _kare(sira: int, kaynak_sn: float | None = None) -> dict:
    """gruplar() testleri için gerçek dosya gerektirmeyen sahte kare kaydı."""
    return {
        "sira": sira,
        "dosya": f"k_{sira:05d}.jpg",
        "kaynak_sn": kaynak_sn if kaynak_sn is not None else round((sira - 1) / 2, 3),
        "sha256": f"sahte{sira}",
        "genislik": 720,
        "yukseklik": 404,
    }


def _kucuk_cfg(genislik: int = 64, fps: float = 2) -> dict:
    """Testler için küçük/hızlı config — reçete şablonu gerçek config.yaml ile aynı."""
    return {
        "kare": {
            "fps": fps,
            "genislik": genislik,
            "suzgec": "scale={genislik}:-2:flags=lanczos,unsharp=5:5:1.0",
            "bicim": "jpg",
            "jpeg_kalite": 2,
        }
    }


def _kaynak_png_uret(dizin: Path, adlar: list[str], boyut=(60, 48)) -> None:
    dizin.mkdir(parents=True, exist_ok=True)
    for i, ad in enumerate(adlar):
        # Her karede farklı dolgu — sha256'nin gerçekten İÇERİĞE bağlı
        # olduğunu (hep aynı sabit değeri dönmediğini) sınamak için.
        renk = (i * 17 % 256, i * 41 % 256, i * 73 % 256)
        Image.new("RGB", boyut, color=renk).save(dizin / ad)


# ---------------------------------------------------------------------------
# REÇETE BİRLİĞİ — kulenin iki girdi yolu AYNI görsel reçeteyi uygulamalı.
# Bu, ölçülmüş %91'lik skorun havuz B'deki (yalnız kare-dizini yolundan geçen)
# filmler için de geçerli olmasının TEK garantisi.
# ---------------------------------------------------------------------------

@ffmpeg_gerekli
def test_iki_yol_ayni_gorsel_receteyi_uygular_sha256_birebir_ayni(tmp_path):
    """Aynı görsel içerik iki yoldan da geçince üretilen JPEG'ler BİREBİR aynı.

    Kaynak klip KAYIPSIZ ve rgb24 seçildi (ffv1). Sebep: PNG her zaman RGB'dir,
    yani kare-dizini yolunda ölçeğe giren piksel biçimi rgb24'tür. Kaynak klip
    yuv420p olsaydı video yolu ölçeğe yuv420p verirdi ve PNG'ye çıkarma
    (yuv420p->rgb24) + geri kodlama (rgb24->yuvj420p) kroma alt-örneklemesini
    bir tur döndürürdü — bu, REÇETEDEN değil KAYNAĞIN renk uzayından gelen bir
    farktır (ölçüldü: maks piksel farkı ~128/255, PSNR ~31 dB, testsrc renk
    çubuklarında en kötü hâl). rgb24 kaynak bu değişkeni sabitler ve testin
    gerçekten ÖLÇMEK İSTEDİĞİ şeyi izole eder: filtre zinciri + kodlayıcı
    ayarları iki kod yolunda aynı mı?
    """
    klip = tmp_path / "klip.mkv"
    uret = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=duration=2:size=320x240:rate=10",
         "-c:v", "ffv1", "-pix_fmt", "rgb24", str(klip)],
        capture_output=True, timeout=60)
    assert uret.returncode == 0, uret.stderr

    # Kare dizini girdisi: AYNI klipten fps=2 ile PNG kareler (OLCEKLEME YOK --
    # olcekleme reçetenin isi, girdi hazirliginin degil).
    kaynak = tmp_path / "kaynak"
    kaynak.mkdir()
    cikar = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(klip), "-vf", "fps=2",
         str(kaynak / "c_%04d.png")], capture_output=True, timeout=60)
    assert cikar.returncode == 0, cikar.stderr

    cfg = _kucuk_cfg(genislik=720, fps=2)
    m_video = videodan_hazirla(klip, tmp_path / "A", cfg)
    m_dizin = kare_dizininden_hazirla(kaynak, tmp_path / "B", cfg)

    assert m_video["kare_sayisi"] == m_dizin["kare_sayisi"] > 0
    assert ([k["sha256"] for k in m_video["kareler"]]
            == [k["sha256"] for k in m_dizin["kareler"]])


@ffmpeg_gerekli
def test_iki_yolda_da_ilk_karenin_kaynak_sn_degeri_sifir(tmp_path):
    """`kaynak_sn` formülü iki yolda AYNI (0-tabanlı): ilk kare her zaman 0.0.

    Yarım-fps'lik bir ofset farkı kare aralıklarını kaydırır ve OCR kanıt
    penceresini (PLAN §3: 's'nin kare aralığı ± pay') yanlış yere oturtur.
    """
    klip = tmp_path / "klip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=duration=2:size=320x240:rate=10", str(klip)],
        capture_output=True, timeout=60, check=True)
    kaynak = tmp_path / "kaynak"
    _kaynak_png_uret(kaynak, ["c_0001.png", "c_0002.png", "c_0003.png"])

    cfg = _kucuk_cfg()
    m_video = videodan_hazirla(klip, tmp_path / "A", cfg)
    m_dizin = kare_dizininden_hazirla(kaynak, tmp_path / "B", cfg)

    assert m_video["kareler"][0]["kaynak_sn"] == 0.0
    assert m_dizin["kareler"][0]["kaynak_sn"] == 0.0
    # ikinci kare de ayni adimda (1/fps = 0.5)
    assert m_video["kareler"][1]["kaynak_sn"] == pytest.approx(0.5)
    assert m_dizin["kareler"][1]["kaynak_sn"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# gruplar() — sınırlar (bindirme, faz kaydırma, son kısa grup)
# ---------------------------------------------------------------------------

def test_gruplama_bindirme_ile_komsu_gruplar_ortak_kare_paylasir():
    kareler = [_kare(i) for i in range(1, 11)]          # 10 kare
    g = gruplar(kareler, kare_sayisi=8, bindirme=1)
    assert len(g) == 2
    assert g[0]["kare_indeksleri"] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert g[1]["kare_indeksleri"] == [8, 9, 10]         # 8 ortak (bindirme=1)


def test_gruplama_tam_bolunurse_bindirmesiz_kisa_grup_olusmaz():
    kareler = [_kare(i) for i in range(1, 17)]          # 16 kare, tam 2x8
    g = gruplar(kareler, kare_sayisi=8, bindirme=0)
    assert len(g) == 2
    assert len(g[0]["kare_indeksleri"]) == 8
    assert len(g[1]["kare_indeksleri"]) == 8
    assert g[0]["kare_indeksleri"][-1] != g[1]["kare_indeksleri"][0]   # bindirme yok


def test_gruplama_son_grup_kisa_olabilir():
    kareler = [_kare(i) for i in range(1, 11)]          # 10 kare
    g = gruplar(kareler, kare_sayisi=8, bindirme=0)
    assert len(g) == 2
    assert g[1]["kare_indeksleri"] == [9, 10]            # son grup 2 kareyle kisa


def test_gruplama_faz_kaydirma_baslangici_kaydirir_ve_bindirmeyi_korur():
    kareler = [_kare(i) for i in range(1, 20)]          # 19 kare
    g = gruplar(kareler, kare_sayisi=8, bindirme=1, faz=4)
    assert g[0]["kare_indeksleri"] == [5, 6, 7, 8, 9, 10, 11, 12]   # ilk 4 kare disarda
    assert g[1]["kare_indeksleri"][0] == 12              # bindirme=1 faz'da da gecerli
    assert g[-1]["kare_indeksleri"][-1] == 19             # son kareyi kapsar


def test_gruplama_faz_sifirsa_normal_davranisla_ayni():
    kareler = [_kare(i) for i in range(1, 11)]
    assert gruplar(kareler, 8, 1, faz=0) == gruplar(kareler, 8, 1)


def test_gruplama_no_alani_sirali_ve_sn_alanlari_dogru():
    kareler = [_kare(i) for i in range(1, 11)]
    g = gruplar(kareler, kare_sayisi=8, bindirme=1)
    assert [x["no"] for x in g] == [0, 1]
    assert g[0]["ilk_sn"] == kareler[0]["kaynak_sn"]
    assert g[0]["son_sn"] == kareler[7]["kaynak_sn"]


def test_gruplama_gecersiz_parametreler_reddedilir():
    kareler = [_kare(i) for i in range(1, 5)]
    with pytest.raises(ValueError):
        gruplar(kareler, kare_sayisi=8, bindirme=8)      # bindirme >= kare_sayisi
    with pytest.raises(ValueError):
        gruplar(kareler, kare_sayisi=0, bindirme=0)
    with pytest.raises(ValueError):
        gruplar(kareler, kare_sayisi=8, bindirme=1, faz=-1)


def test_gruplama_manifest_sozlugu_de_kabul_eder():
    kareler = [_kare(i) for i in range(1, 11)]
    manifest = {"kareler": kareler, "kare_dizini": "/yok"}
    assert gruplar(manifest, 8, 1) == gruplar(kareler, 8, 1)


# ---------------------------------------------------------------------------
# manifest alanları + fps varsayımı — kare_dizininden_hazirla
# ---------------------------------------------------------------------------

@ffmpeg_gerekli
def test_kare_dizininden_hazirla_manifest_alanlari(tmp_path):
    kaynak = tmp_path / "kaynak"
    _kaynak_png_uret(kaynak, ["c_0001.png", "c_0002.png", "c_0003.png"])
    manifest = kare_dizininden_hazirla(kaynak, tmp_path / "cikis", _kucuk_cfg())

    assert manifest["fps_varsayimi"] is True
    assert manifest["kaynak"] == "kare_dizini"
    assert manifest["kare_sayisi"] == 3
    zorunlu = {"sira", "dosya", "kaynak_sn", "sha256", "genislik", "yukseklik"}
    for kare in manifest["kareler"]:
        assert zorunlu <= kare.keys()
        assert kare["genislik"] == 64                    # reçete geregi 64'e buyutuldu
    assert [k["sira"] for k in manifest["kareler"]] == [1, 2, 3]
    assert manifest["kareler"][0]["kaynak_sn"] == 0.0
    assert manifest["kareler"][1]["kaynak_sn"] == pytest.approx(0.5)
    # iz surulebilirlik: hangi KAYNAK dosyadan turedi
    assert [k["kaynak_dosya"] for k in manifest["kareler"]] == [
        "c_0001.png", "c_0002.png", "c_0003.png"]

    # diskteki kanit dosyasi donen manifestle birebir ayni mi?
    disk = json.loads((tmp_path / "cikis" / "kare_manifesti.json").read_text())
    assert disk == manifest


@ffmpeg_gerekli
def test_kare_dizininden_hazirla_dogal_siralama_ve_mutlak_kare_no(tmp_path):
    """Sıfır dolgusuz adlar: sözlüksel sıra YANLIŞ, doğal sıra doğru.

    ffmpeg glob'u sözlüksel sıralar; bu yüzden kod sıralı sembolik-bağ dizini
    üzerinden besliyor. Bozulsaydı kod patlamaz, sessizce yanlış zaman damgası
    üretirdi — bu testin varlık sebebi tam olarak o sessiz hata.
    """
    kaynak = tmp_path / "kaynak"
    _kaynak_png_uret(kaynak, ["c_1.png", "c_2.png", "c_10.png"])
    manifest = kare_dizininden_hazirla(kaynak, tmp_path / "cikis", _kucuk_cfg())
    assert [k["sira"] for k in manifest["kareler"]] == [1, 2, 10]
    assert [k["kaynak_dosya"] for k in manifest["kareler"]] == [
        "c_1.png", "c_2.png", "c_10.png"]
    # mutlak kare no'dan turetilen zaman: 10. kare -> (10-1)/2 = 4.5
    assert manifest["kareler"][2]["kaynak_sn"] == pytest.approx(4.5)


@ffmpeg_gerekli
def test_kare_dizininden_hazirla_karisik_uzanti_sirayi_korur(tmp_path):
    """PNG+JPG karışık dizin: tek image2 girdisi codec'i bir kez seçer, bu yüzden
    uzantıya göre gruplanıp ayrı geçişlerde işlenir — global sıra korunmalı."""
    kaynak = tmp_path / "kaynak"
    _kaynak_png_uret(kaynak, ["c_0001.png", "c_0003.png"])
    Image.new("RGB", (60, 48), color=(200, 30, 30)).save(kaynak / "c_0002.jpg")
    Image.new("RGB", (60, 48), color=(30, 200, 30)).save(kaynak / "c_0004.jpg")
    manifest = kare_dizininden_hazirla(kaynak, tmp_path / "cikis", _kucuk_cfg())
    assert [k["sira"] for k in manifest["kareler"]] == [1, 2, 3, 4]
    assert [k["kaynak_dosya"] for k in manifest["kareler"]] == [
        "c_0001.png", "c_0002.jpg", "c_0003.png", "c_0004.jpg"]
    # her kare gercekten uretildi mi (dosyalar diskte)
    for k in manifest["kareler"]:
        assert (tmp_path / "cikis" / k["dosya"]).is_file()


@ffmpeg_gerekli
def test_kare_dizininden_hazirla_kucuk_kareyi_buyutur(tmp_path):
    kaynak = tmp_path / "kaynak"
    _kaynak_png_uret(kaynak, ["c_0001.png"], boyut=(600, 480))    # gercek GT boyutu
    manifest = kare_dizininden_hazirla(kaynak, tmp_path / "cikis", _kucuk_cfg(genislik=720))
    kare = manifest["kareler"][0]
    assert kare["genislik"] == 720
    assert kare["yukseklik"] == 576                      # 720*(480/600)=576, zaten cift


@ffmpeg_gerekli
def test_kare_dizininden_hazirla_cakisan_kare_numarasi_reddedilir(tmp_path):
    """`c_1.png` ve `c_01.jpg` ayni `sira`ya duser -> cikti sessizce ezilirdi."""
    kaynak = tmp_path / "kaynak"
    _kaynak_png_uret(kaynak, ["c_1.png"])
    Image.new("RGB", (60, 48), color=(1, 2, 3)).save(kaynak / "c_01.jpg")
    with pytest.raises(VideoHatasi):
        kare_dizininden_hazirla(kaynak, tmp_path / "cikis", _kucuk_cfg())


def test_kare_dizininden_hazirla_bos_dizin_hata_verir(tmp_path):
    bos = tmp_path / "bos"
    bos.mkdir()
    with pytest.raises(VideoHatasi):
        kare_dizininden_hazirla(bos, tmp_path / "cikis", _kucuk_cfg())


def test_kare_dizininden_hazirla_olmayan_dizin_hata_verir(tmp_path):
    with pytest.raises(VideoHatasi):
        kare_dizininden_hazirla(tmp_path / "yok", tmp_path / "cikis", _kucuk_cfg())


@ffmpeg_gerekli
def test_kare_dizininden_hazirla_gecici_dizin_birakmaz(tmp_path):
    """Sembolik-bag ve ham cikti dizinleri temizlenmeli — arkada dangling
    sembolik bag birakmak MITAS'ta bilinen bir tuzak."""
    kaynak = tmp_path / "kaynak"
    _kaynak_png_uret(kaynak, ["c_0001.png", "c_0002.png"])
    cikis = tmp_path / "cikis"
    kare_dizininden_hazirla(kaynak, cikis, _kucuk_cfg())
    assert [p.name for p in cikis.iterdir() if p.is_dir()] == []


# ---------------------------------------------------------------------------
# sha256 kararlılığı — aynı girdi -> aynı hash
# ---------------------------------------------------------------------------

@ffmpeg_gerekli
def test_sha256_kararliligi_ayni_girdi_ayni_hash(tmp_path):
    kaynak = tmp_path / "kaynak"
    _kaynak_png_uret(kaynak, ["c_0001.png", "c_0002.png"])
    cfg = _kucuk_cfg()
    m1 = kare_dizininden_hazirla(kaynak, tmp_path / "cikis1", cfg)
    m2 = kare_dizininden_hazirla(kaynak, tmp_path / "cikis2", cfg)
    h1 = [k["sha256"] for k in m1["kareler"]]
    h2 = [k["sha256"] for k in m2["kareler"]]
    assert h1 == h2
    assert h1[0] != h1[1]                                 # farkli icerik -> farkli hash


@ffmpeg_gerekli
def test_sha256_farkli_icerik_farkli_hash(tmp_path):
    kaynak = tmp_path / "kaynak"
    _kaynak_png_uret(kaynak, ["c_0001.png"])
    m1 = kare_dizininden_hazirla(kaynak, tmp_path / "cikis1", _kucuk_cfg())
    Image.new("RGB", (60, 48), color=(9, 9, 9)).save(kaynak / "c_0001.png")   # icerigi degistir
    m2 = kare_dizininden_hazirla(kaynak, tmp_path / "cikis2", _kucuk_cfg())
    assert m1["kareler"][0]["sha256"] != m2["kareler"][0]["sha256"]


# ---------------------------------------------------------------------------
# videodan_hazirla — gerçek ffmpeg, küçük sentetik klip (dış dosyaya bağımlı değil)
# ---------------------------------------------------------------------------

@ffmpeg_gerekli
def test_videodan_hazirla_gercek_ffmpeg_ile_manifest_uretir(tmp_path):
    video = tmp_path / "sentetik.mp4"
    uret = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=duration=2:size=320x240:rate=10", str(video)],
        capture_output=True, timeout=30)
    assert uret.returncode == 0, uret.stderr

    manifest = videodan_hazirla(video, tmp_path / "cikis", _kucuk_cfg(genislik=64, fps=2))
    assert manifest["fps_varsayimi"] is False             # video yolunda fps GERCEK, varsayim degil
    assert manifest["kaynak"] == "video"
    assert 3 <= manifest["kare_sayisi"] <= 5               # 2sn @ 2fps ~ 4 kare (sinirda +-1)
    ilk = manifest["kareler"][0]
    assert ilk["sira"] == 1
    assert ilk["kaynak_sn"] == 0.0
    assert ilk["genislik"] == 64


def test_videodan_hazirla_olmayan_video_hata_verir(tmp_path):
    with pytest.raises(VideoHatasi):
        videodan_hazirla(tmp_path / "yok.mp4", tmp_path / "cikis", _kucuk_cfg())


# ---------------------------------------------------------------------------
# kayma_hizi — davranışı değiştirmeyen kaba ölçüm (yalnız kanıta yazılır)
# ---------------------------------------------------------------------------

def _sahte_kare(sira: int, dosya: str) -> dict:
    return {"sira": sira, "dosya": dosya, "kaynak_sn": round((sira - 1) / 2, 3),
            "sha256": "x", "genislik": 50, "yukseklik": 200}


def test_kayma_hizi_ozdes_karelerde_kayma_sifir_ve_mod_sayfa(tmp_path):
    dizin = tmp_path / "kareler"
    dizin.mkdir()
    kareler = []
    for i in range(1, 5):
        ad = f"k_{i:05d}.png"
        Image.new("RGB", (40, 100), color=(120, 120, 120)).save(dizin / ad)
        kareler.append(_sahte_kare(i, ad))
    manifest = {"kare_dizini": str(dizin), "kareler": kareler}
    sonuc = kayma_hizi(manifest)
    assert sonuc["px_sn"] == pytest.approx(0.0, abs=1e-6)
    assert sonuc["mod"] == "sayfa"


def test_kayma_hizi_dikey_kaydirilmis_seritte_kayma_algilar(tmp_path):
    dizin = tmp_path / "kareler"
    dizin.mkdir()
    yukseklik, genislik = 200, 50
    taban = (np.random.default_rng(42).random((yukseklik + 40, genislik)) * 255).astype("uint8")
    kareler = []
    for i in range(1, 6):
        kayma = (i - 1) * 5                              # her karede 5px kayan serit
        dilim = taban[kayma:kayma + yukseklik, :]
        ad = f"k_{i:05d}.png"                             # kayipsiz -- sha SAD taramasi kirlenmesin
        Image.fromarray(dilim, mode="L").convert("RGB").save(dizin / ad)
        kareler.append(_sahte_kare(i, ad))
    manifest = {"kare_dizini": str(dizin), "kareler": kareler}
    sonuc = kayma_hizi(manifest)
    assert sonuc["mod"] == "kayan"
    assert sonuc["px_sn"] > 0


def test_kayma_hizi_tek_kareyle_veya_dizinsiz_cokmez():
    assert kayma_hizi({"kareler": [], "kare_dizini": None}) == {"mod": "sayfa", "px_sn": 0.0}
    assert kayma_hizi({"kareler": [_kare(1)], "kare_dizini": None}) == {"mod": "sayfa", "px_sn": 0.0}
