"""sadakat.py (Katman-0 metin-recall) için birim testleri.

Gerçek PaddleOCR'a HİÇ dokunmaz -- `dc` bağımlılığı sahte (_SahteDC) bir
nesneyle enjekte edilir (det_rec_tokenlari/sadakat_olc her ikisi de `dc`
parametresi kabul ediyor, bu yüzden gerçek motor testte hiç yüklenmez: hızlı,
determinist, GPU/CPU-OCR maliyeti sıfır). Gerçek motorla doğrulama AYRI
bir adım -- bkz. sadakat_raporu.md'deki 6-film doğrulama seti (kasıtlı
olarak burada TEKRARLANMAZ, testler yalnız orkestrasyon mantığını kanıtlar).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sadakat  # noqa: E402


# --------------------------------------------------------------------------- #
# yardımcılar
# --------------------------------------------------------------------------- #
def _sabit_png(path: Path, deger: int, h: int = 20, w: int = 20) -> None:
    arr = np.full((h, w), deger, dtype=np.uint8)
    Image.fromarray(arr, mode="L").save(path)


class _SahteDC:
    """det/rec arayüzünü simüle eder. Görüntünün ortalama piksel değeri
    ("kimlik") -> önceden tanımlı [(metin, güven), ...] listesine eşlenir.
    `_f1b_det_boxes`, kayıt sayısı kadar YER TUTUCU kutu döner -- gerçek
    `db_compose_master.py`'de `_f1c_rec_boxes` HER kutu için TAM BİR rec-
    sonucu döndürdüğünden (bkz. `_det_rec_kutulari`'nin `zip(rec,
    boxes_sorted)` kullanımı) len(boxes)==len(rec) DEĞİŞMEZ-KURALI burada da
    korunmalı -- tek bir sabit kutu dönseydi (kayıt sayısı>1 iken) zip()
    fazla rec sonucunu SESSİZCE keserdi (bu tam olarak bir test-fake hatası
    olarak yakalandı, bkz. GUNLUK/rapor)."""

    def __init__(self, harita: dict[int, list[tuple[str, float]]]):
        self.harita = harita
        self.det_cagri = 0
        self.rec_cagri = 0

    def _anahtar(self, gray: np.ndarray) -> int:
        return int(round(float(gray.mean())))

    def _f1b_det_boxes(self, gray: np.ndarray):
        self.det_cagri += 1
        kayitlar = self.harita.get(self._anahtar(gray))
        if not kayitlar:
            return []
        return [(0.0, 0.0, 0.0, 0.0, 0, 0, 1, 1)] * len(kayitlar)

    def _f1b_boxes_sorted(self, boxes):
        return list(boxes)

    def _f1c_rec_boxes(self, gray: np.ndarray, boxes_sorted):
        self.rec_cagri += 1
        return list(self.harita.get(self._anahtar(gray), []))


class _PatlayanDC:
    """det/rec çağrılırsa istisna fırlatır -- hata-yutma davranışını kanıtlar."""

    def _f1b_det_boxes(self, gray):
        raise RuntimeError("motor çöktü")

    def _f1b_boxes_sorted(self, boxes):
        return boxes

    def _f1c_rec_boxes(self, gray, boxes_sorted):
        raise RuntimeError("rec çöktü")


# --------------------------------------------------------------------------- #
# orneklenmis_kareler
# --------------------------------------------------------------------------- #
def test_ornek_hedef_asilmiyorsa_tumu_donuyor():
    kareler = [f"k{i}" for i in range(15)]
    assert sadakat.orneklenmis_kareler(kareler, hedef=20) == kareler


def test_ornek_hedef_asilinca_hedef_kadar_benzersiz_secim():
    kareler = [f"k{i}" for i in range(100)]
    secim = sadakat.orneklenmis_kareler(kareler, hedef=20)
    assert len(secim) == 20
    assert len(set(secim)) == 20  # benzersiz
    # ilk ve son kare kaçırılmaz (linspace uç noktaları her zaman 0 ve n-1)
    assert secim[0] == "k0"
    assert secim[-1] == "k99"
    # kaynak sıralaması korunur (artan indeks)
    assert secim == sorted(secim, key=kareler.index)


def test_ornek_bos_liste():
    assert sadakat.orneklenmis_kareler([], hedef=20) == []


# --------------------------------------------------------------------------- #
# hedef_kare_uyarla (uzun/hızlı filmlerde referans-küme zenginleştirme)
# --------------------------------------------------------------------------- #
def test_uyarla_kisa_filmde_degismiyor():
    # n<=taban -> davranış eskisiyle BİREBİR aynı (tüm kareler zaten kullanılıyor)
    assert sadakat.hedef_kare_uyarla(15, taban=20, tavan=40) == 15
    assert sadakat.hedef_kare_uyarla(20, taban=20, tavan=40) == 20


def test_uyarla_uzun_filmde_yukselir_ama_tavani_asmaz():
    # olum-emri'nin gerçek kare sayısı (272) -- taban 20'nin ÜSTÜNE çıkmalı
    # ama tavan (40) asla aşılmamalı
    hedef = sadakat.hedef_kare_uyarla(272, taban=20, tavan=40)
    assert 20 < hedef <= 40


def test_uyarla_asiri_uzun_filmde_tavanda_sabitlenir():
    assert sadakat.hedef_kare_uyarla(100_000, taban=20, tavan=40) == 40


def test_uyarla_monoton_artan():
    # daha çok kare -> asla daha düşük hedef (monotonluk -- şaşırtıcı ters-yön yok)
    onceki = sadakat.hedef_kare_uyarla(20, taban=20, tavan=40)
    for n in (30, 60, 120, 300, 1000):
        simdiki = sadakat.hedef_kare_uyarla(n, taban=20, tavan=40)
        assert simdiki >= onceki
        onceki = simdiki


def test_var_kunye_tokenlari_uzun_listede_uyarlanmis_hedef_kullanir(monkeypatch, tmp_path):
    # 272 SAHTE (var olmayan) kare yolu -- _gri_yukle None döner, det_rec_tokenlari
    # sessizce [] döner (zaten ayrı testte kanıtlandı); burada yalnız ÖRNEKLENEN
    # SAYI (ornek_kare) uyarlamayı yansıtıyor mu kontrol ediliyor.
    slug = "uzun-film"
    monkeypatch.setattr(sadakat, "EX_KARE_ROOT", tmp_path)
    frames_dir = tmp_path / f"{slug}-exit_frames"
    frames_dir.mkdir()
    sahte_kareler = [str(tmp_path / f"yok_{i:04d}.png") for i in range(272)]
    monkeypatch.setattr(sadakat, "ham_kareler", lambda s: sahte_kareler)

    dc = _SahteDC({})
    sonuc = sadakat.var_kunye_tokenlari(slug, dc, hedef_kare=20)

    beklenen = sadakat.hedef_kare_uyarla(272, taban=20, tavan=40)
    assert sonuc["ornek_kare"] == beklenen
    assert beklenen > 20  # asıl nokta: düz-20 DEĞİL, yukarı uyarlanmış


# --------------------------------------------------------------------------- #
# master_bantlari
# --------------------------------------------------------------------------- #
def test_bant_kucuk_master_tek_bant():
    assert sadakat.master_bantlari(500, bant_h=1200, ortusme=200) == [(0, 500)]


def test_bant_sifir_yukseklik():
    assert sadakat.master_bantlari(0) == []


def test_bant_buyuk_master_tam_kaplama_ve_ortusme():
    h = 5000
    bantlar = sadakat.master_bantlari(h, bant_h=1200, ortusme=200)
    assert len(bantlar) > 1
    assert bantlar[0][0] == 0
    assert bantlar[-1][1] == h  # son bant TAM h'de biter -- kaplama eksiksiz
    for (y0, y1) in bantlar:
        assert y1 - y0 <= 1200
        assert y1 > y0
    # ardışık bantlar arasında boşluk yok (örtüşme veya bitişiklik)
    for (_, prev_y1), (y0, _) in zip(bantlar, bantlar[1:]):
        assert y0 <= prev_y1


# --------------------------------------------------------------------------- #
# bant_cekirdekleri (GLM konsey incelemesinde bulunan çifte-sayım fix'i)
# --------------------------------------------------------------------------- #
def test_bant_cekirdekleri_cakismasiz_ve_bosluksuz():
    bantlar = sadakat.master_bantlari(5000, bant_h=1200, ortusme=200)
    cekirdekler = sadakat.bant_cekirdekleri(bantlar, ortusme=200)
    assert len(cekirdekler) == len(bantlar)
    assert cekirdekler[0][0] == 0
    assert cekirdekler[-1][1] == 5000
    # ÇAKIŞMASIZ + BOŞLUKSUZ: ardışık çekirdekler TAM birbirine değmeli (miras
    # kalan boşluk/çakışma "occ" sayımında sessiz hata üretirdi)
    for (_, c1_onceki), (c0_sonraki, _) in zip(cekirdekler, cekirdekler[1:]):
        assert c1_onceki == c0_sonraki
    # her çekirdek kendi bandının İÇİNDE kalmalı (dışına taşmamalı)
    for (y0, y1), (c0, c1) in zip(bantlar, cekirdekler):
        assert y0 <= c0 and c1 <= y1


def test_bant_cekirdekleri_tek_bant_tam_kapsar():
    assert sadakat.bant_cekirdekleri([(0, 500)], ortusme=200) == [(0, 500)]


def test_master_tokenlari_ortusme_bolgesinde_cifte_saymaz(tmp_path, monkeypatch):
    """REGRESYON (GLM konsey bulgusu): örtüşme bölgesine düşen bir kutu HEM
    önceki HEM sonraki bant taramasında algılanabilir -- fix ÖNCESİ bu kod
    `occ`'a AYNI token'ı iki kez ekliyor, okunabilirlik'i çarpıtıyordu.
    `_det_rec_kutulari` sahte biçimde AYNI fiziksel master-satırını iki farklı
    bant çağrısında iki farklı yerel cy_norm ile döndürüyor -- gerçek
    PaddleOCR'ın örtüşen iki banttaki davranışını simüle eder.

    NOT: `MASTER_BANT_YUKSEKLIK`/`MASTER_BANT_ORTUSME` modül sabitleri
    `master_bantlari`/`bant_cekirdekleri`'nin PARAMETRE VARSAYILANI olarak
    kullanılıyor -- Python varsayılan değerleri TANIM anında bağlar, bu yüzden
    modül sabitini monkeypatch'lemek `master_tokenlari`'nin (varsayılanla
    çağırdığı) davranışını DEĞİŞTİRMEZ. Bu yüzden gerçek varsayılanlarla
    (1200/200) çalışan, 2 bant üretecek kadar uzun (h=2000) bir master
    kullanılıyor -- üretim davranışını olduğu gibi test eder."""
    slug = "test-bant-film"
    master_root = tmp_path / "master_root"
    (master_root / slug).mkdir(parents=True)
    monkeypatch.setattr(sadakat, "MASTER_KOK", master_root)
    # h=2000, varsayılan bant_h=1200/ortusme=200 (adim=1000) ->
    # bantlar=[(0,1200),(1000,2000)], çekirdekler=[(0,1000),(1000,2000)]
    _sabit_png(master_root / slug / "reading_master.png", 50, h=2000, w=20)

    cagri_no = {"i": 0}

    def sahte_det_rec_kutulari(gray, dc):
        cagri_no["i"] += 1
        if cagri_no["i"] == 1:
            # bant0 (master-satır 0-1200, yükseklik 1200): master-row 1100 -> yerel cy=1100/1200
            return [("ortaksatir", 0.9, 1100 / 1200)]
        if cagri_no["i"] == 2:
            # bant1 (master-satır 1000-2000, yükseklik 1000): AYNI master-row 1100 -> yerel cy=100/1000
            return [("ortaksatir", 0.9, 100 / 1000)]
        return []

    monkeypatch.setattr(sadakat, "_det_rec_kutulari", sahte_det_rec_kutulari)

    m = sadakat.master_tokenlari(slug, dc=None)

    assert m["yakalanan"] == {"ortaksatir"}
    assert len(m["occ"]) == 1  # 2 DEĞİL -- çekirdek-filtresi çifte sayımı engelledi
    assert cagri_no["i"] == 2  # her iki bant da gerçekten taranmış (atlanmamış)


# --------------------------------------------------------------------------- #
# det_rec_tokenlari
# --------------------------------------------------------------------------- #
def test_det_rec_tokenlari_bolme_ve_uzunluk_filtresi():
    dc = _SahteDC({10: [("yonetmen ali veli vs", 0.85)]})
    gray = np.full((20, 20), 10, dtype=np.uint8)
    out = sadakat.det_rec_tokenlari(gray, dc)
    # "vs" (2 karakter) elenir; kalan 3 token AYNI kutu güvenini taşır
    assert sorted(out) == sorted([("yonetmen", 0.85), ("ali", 0.85), ("veli", 0.85)])


def test_det_rec_tokenlari_kayitsiz_goruntu_bos_liste():
    dc = _SahteDC({10: [("bir sey", 0.9)]})
    gray = np.full((20, 20), 77, dtype=np.uint8)  # 77 haritada yok
    assert sadakat.det_rec_tokenlari(gray, dc) == []


def test_det_rec_tokenlari_none_gray_bos_liste():
    dc = _SahteDC({})
    assert sadakat.det_rec_tokenlari(None, dc) == []


def test_det_rec_tokenlari_motor_hatasi_yutulur():
    gray = np.full((20, 20), 10, dtype=np.uint8)
    assert sadakat.det_rec_tokenlari(gray, _PatlayanDC()) == []


# --------------------------------------------------------------------------- #
# sadakat_olc -- uçtan uca (sahte dc + tmp_path dizin yapısı)
# --------------------------------------------------------------------------- #
def _kur(tmp_path: Path, monkeypatch, slug: str = "test-film") -> Path:
    ex_root = tmp_path / "ex_root"
    master_root = tmp_path / "master_root"
    monkeypatch.setattr(sadakat, "EX_KARE_ROOT", ex_root)
    monkeypatch.setattr(sadakat, "MASTER_KOK", master_root)
    frames_dir = ex_root / f"{slug}-exit_frames"
    frames_dir.mkdir(parents=True)
    return frames_dir


def test_sadakat_olc_uctan_uca_recall_ve_okunabilirlik(tmp_path, monkeypatch):
    slug = "test-film"
    frames_dir = _kur(tmp_path, monkeypatch, slug)

    # 2 ham kare: var = {yonetmen, ali, veli, kamera, mehmet} ("vs" 2-karakter elenir)
    _sabit_png(frames_dir / "exit_000001.png", 10)
    _sabit_png(frames_dir / "exit_000002.png", 20)

    master_dir = sadakat.MASTER_KOK / slug
    master_dir.mkdir(parents=True)
    _sabit_png(master_dir / "reading_master.png", 30, h=20, w=20)

    harita = {
        10: [("yonetmen ali veli vs", 0.9)],
        20: [("kamera mehmet", 0.9)],
        # master: 2 kutu -- biri var'la kesişen (yonetmen ali, conf yüksek),
        # biri var'da OLMAYAN hayalet token (xyz, conf DÜŞÜK -- ezik sinyali)
        30: [("yonetmen ali", 0.9), ("xyz", 0.4)],
    }
    dc = _SahteDC(harita)

    r = sadakat.sadakat_olc(slug, dc=dc)

    assert r["durum"] == "olculdu"
    assert r["var_token"] == 5  # yonetmen, ali, veli, kamera, mehmet
    assert r["yakalanan_token"] == 3  # yonetmen, ali, xyz
    assert r["kesisim_token"] == 2  # yonetmen, ali
    assert r["text_recall"] == pytest.approx(2 / 5)
    # 2/3 occ conf>=0.6 (xyz 0.4 düşüyor) -- sonuç 4 ondalığa yuvarlanıyor, tolerans buna göre
    assert r["okunabilirlik"] == pytest.approx(2 / 3, abs=1e-4)
    assert r["frame_sayisi"] == 2
    assert r["ornek_kare"] == 2
    assert r["master_boy"] == [20, 20]
    assert r["sure_s"] >= 0


def test_sadakat_olc_kare_yok():
    dc = _SahteDC({})
    r = sadakat.sadakat_olc("olmayan-slug-xyz-987", dc=dc)
    assert r["durum"] == "kare_yok"
    assert r["text_recall"] is None
    assert r["okunabilirlik"] is None


def test_sadakat_olc_master_yok(tmp_path, monkeypatch):
    slug = "test-film-mastersiz"
    frames_dir = _kur(tmp_path, monkeypatch, slug)
    _sabit_png(frames_dir / "exit_000001.png", 10)
    dc = _SahteDC({10: [("bir metin burada", 0.9)]})

    r = sadakat.sadakat_olc(slug, dc=dc)

    assert r["durum"] == "master_yok"
    assert r["text_recall"] is None
    assert r["okunabilirlik"] is None
    assert r["var_token"] == 3  # bir, metin, burada


def test_sadakat_olc_kunye_yok_recall_none_sifir_degil(tmp_path, monkeypatch):
    """var kümesi boşsa (ham karelerde anlamlı token yok) recall None olmalı --
    0.0 ile karıştırılmamalı (0.0 'ölçtüm ve tam kayıp' derken None 'ölçecek
    bir şey yoktu' der -- anlamları farklı, testte AYRIM zorunlu)."""
    slug = "test-film-kunyesiz"
    frames_dir = _kur(tmp_path, monkeypatch, slug)
    _sabit_png(frames_dir / "exit_000001.png", 10)
    master_dir = sadakat.MASTER_KOK / slug
    master_dir.mkdir(parents=True)
    _sabit_png(master_dir / "reading_master.png", 30, h=20, w=20)

    # 10 haritada yok -> det_rec_tokenlari boş -> var kümesi boş
    dc = _SahteDC({30: [("yonetmen ali", 0.9)]})

    r = sadakat.sadakat_olc(slug, dc=dc)

    assert r["durum"] == "kunye_yok"
    assert r["text_recall"] is None
    assert r["var_token"] == 0
    assert r["yakalanan_token"] == 2  # teşhis amaçlı yine de raporlanır


# --------------------------------------------------------------------------- #
# evren / rastgele örneklem
# --------------------------------------------------------------------------- #
def test_tum_slugler_yalniz_dogru_soneki_alir(tmp_path, monkeypatch):
    monkeypatch.setattr(sadakat, "EX_KARE_ROOT", tmp_path)
    (tmp_path / "filma-exit_frames").mkdir()
    (tmp_path / "filmb-exit_frames").mkdir()
    (tmp_path / "alakasiz_dosya.txt").write_text("x")
    (tmp_path / "alakasiz_klasor").mkdir()
    assert sadakat.tum_slugler() == ["filma", "filmb"]


def test_rastgele_ornek_determinist_ve_boyut(monkeypatch):
    monkeypatch.setattr(sadakat, "tum_slugler", lambda: [f"film{i}" for i in range(200)])
    a = sadakat.rastgele_ornek(40, tohum=42)
    b = sadakat.rastgele_ornek(40, tohum=42)
    assert a == b  # aynı tohum -> aynı sonuç (tekrar-üretilebilir)
    assert len(a) == 40
    assert a == sorted(a)
    farkli = sadakat.rastgele_ornek(40, tohum=7)
    assert farkli != a  # farklı tohum -> (pratikte) farklı örneklem


def test_rastgele_ornek_evrenden_buyuk_n_tasmiyor(monkeypatch):
    monkeypatch.setattr(sadakat, "tum_slugler", lambda: [f"film{i}" for i in range(5)])
    assert len(sadakat.rastgele_ornek(40, tohum=42)) == 5
