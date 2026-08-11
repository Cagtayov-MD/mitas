"""KOBE (figo) — dil-yönlendirici, script görünürlüğü, OCR hata görünürlüğü,
kurtarma-yolu sınırları.

Bağlam (2026-08-11 dış inceleme turu): üç bağımsız gözden geçirmenin doğrulanan
bulguları. 11 Ağustos'ta düzeltilen 4 sessiz bug'ın AYNI SINIFTAN kalan artıkları:
- `script` yalnız BAŞARILI dönüşte doldurulıyordu → `kredi_yok` filmleri PDF'te
  "hep Latin" görünüyordu (şikâyetin kapatılmamış yarısı).
- Yönlendirici filmin %25/%50/%75'inden örnekliyordu — jenerik SONDA.
- `except Exception: []` deseni program hatalarını (NameError/AttributeError)
  OCR başarısızlığı gibi yutuyordu; 841/106/5 kayıtlı çöküşün görünmezlik sebebi.

Bu testler PaddleOCR/Ollama İSTEMEZ — cc/cb modülleri ve HTTP sahte.
"""
from __future__ import annotations

import io
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

KUNYE = Path(__file__).resolve().parents[1] / "harness" / "kunye_kiyas"
sys.path.insert(0, str(KUNYE))


# ── sahte bağımlılıklar ──────────────────────────────────────────────────
class _SahteCC(types.ModuleType):
    """credit_content yerine geçen asgari sahte — tespit_v5'in dokunduğu yüzey."""

    def __init__(self, satirlar_fn=None):
        super().__init__("credit_content")
        import re
        self._dil = "en"
        self._satirlar_fn = satirlar_fn or (lambda yol: [])
        self._ROL = re.compile(r"\b(director|producer)\b", re.I)
        self._ROL_CEKIRDEK = re.compile(r"\b(director|producer)\b", re.I)
        self._PRODUC_GENIS = re.compile(r"\b(produc\w*)\b", re.I)
        self._SIRKET_KALIBI = re.compile(r"\b(studios?|pictures)\b", re.I)

    # dil durumu
    def set_aktif_dil(self, dil):
        self._dil = dil

    def get_aktif_dil(self):
        return self._dil

    # içerik yüzeyi
    def satirlar(self, yol):
        return self._satirlar_fn(yol)

    def satirlar_ru(self, yol):
        return []

    def satirlar_ar(self, yol):
        return []

    def kredi_karti_mi(self, satirlar):
        return False

    def kredi_skoru_coklu(self, kare_satirlari, yogun_esik=4):
        return 0.0

    def kredi_skoru_kiril(self, k):
        return 0.0, []

    def kredi_skoru_arap(self, k):
        return 0.0, []

    def cekirdek_rol_bul(self, k):
        return []

    def cekirdek_rol_bul_genis(self, k):
        return []

    def cop_desenli_mi(self, k, esik=0.92):
        return False

    def _isim_gibi(self, s, satirlar):
        return False


class _SahteCB(types.ModuleType):
    """credit_box yerine geçen asgari sahte."""

    def __init__(self, jbayrak=None, say=None):
        super().__init__("credit_box")
        self._jb = jbayrak
        self._say = say

    def kutu_serisi(self, frame_yollari, stride=1):
        m = len(frame_yollari)
        if self._jb is None:
            return np.zeros(m, bool), np.zeros(m, np.int16)
        return self._jb[:m], self._say[:m]

    def kutu_analiz(self, yol):
        return {"n": 0, "jenerik_benzeri": False, "yayilim": 0.0}


@pytest.fixture
def kobe(monkeypatch):
    """kobe modülünü sahte cc/cb ile taze yükler."""
    for ad in ("kobe", "figo", "credit_content", "credit_box"):
        sys.modules.pop(ad, None)
    cc, cb = _SahteCC(), _SahteCB()
    monkeypatch.setitem(sys.modules, "credit_content", cc)
    monkeypatch.setitem(sys.modules, "credit_box", cb)
    import kobe as _k
    _k._sahte_cc, _k._sahte_cb = cc, cb
    return _k


def _kare_dizini(tmp_path: Path, adet: int) -> Path:
    d = tmp_path / "kareler"
    d.mkdir()
    for i in range(1, adet + 1):
        Image.fromarray(np.zeros((36, 64), dtype=np.uint8)).save(d / f"c_{i:05d}.png")
    return d


@pytest.fixture
def uc_kare(tmp_path):
    """Yönlendirici testleri için GERÇEK dosya yolları.

    DİKKAT (bu testler yazılırken yakalandı): sahte yollar ("a","b","c")
    kullanıldığında `open(path,'rb')` FileNotFoundError atıyor, fonksiyonun
    kendi `except`ine düşüp "en" dönüyordu — testler DOĞRU SONUCU YANLIŞ
    SEBEPLE yeşil gösteriyordu. Yollar var olmalı."""
    d = tmp_path / "router"
    d.mkdir()
    yollar = []
    for i in (1, 2, 3):
        p = d / f"c_{i:05d}.png"
        Image.fromarray(np.zeros((36, 64), dtype=np.uint8)).save(p)
        yollar.append(str(p))
    return yollar


def _sahte_ollama(monkeypatch, kobe, cevaplar: list[str], kayit: dict | None = None):
    """urlopen'i sahtele; `cevaplar` sırayla döner. `kayit` istekleri toplar."""
    import urllib.request

    sira = list(cevaplar)

    class _Yanit(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.close()
            return False

    def _sahte_urlopen(req, timeout=None):
        gövde = json.loads(req.data.decode("utf-8"))
        if kayit is not None:
            kayit.setdefault("istekler", []).append(gövde)
        if not sira:
            raise OSError("cevap kalmadı")
        return _Yanit(json.dumps({"message": {"content": sira.pop(0)}}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", _sahte_urlopen)


# ── A. Yönlendirici (K2) ─────────────────────────────────────────────────
def test_router_filmin_sonundan_ornekler(kobe, tmp_path, monkeypatch):
    """Jenerik SONDA. %25/%50/%75 noktalarında jenerik metni YOK — VLM oralarda
    sahne/tabela okuyup halüsine ediyordu. Örnekleme son %20'ye taşındı."""
    d = _kare_dizini(tmp_path, 100)
    g = kobe.kareler(str(d))
    kayit: dict = {}
    _sahte_ollama(monkeypatch, kobe, ["Latin"] * 3, kayit)

    kobe.detect_script_qwen(kobe._router_ornek_yollari(g))

    istenen = [kobe._kare_no(i["images"][0]) if "images" in i else None
               for i in kayit["istekler"]]
    # sahte istekte gerçek yol yok; örnekleyicinin kendisini doğrula
    yollar = kobe._router_ornek_yollari(g)
    numaralar = [kobe._kare_no(p) for p in yollar]
    assert all(no >= 80 for no in numaralar), f"son %20 dışından örnek: {numaralar}"
    assert len(set(numaralar)) == 3
    assert len(istenen) == 3


def test_router_oylama_cogunlugu_alir(kobe, uc_kare, monkeypatch):
    """Tek halüsinasyon tüm filmi çevirmemeli — ilk-eşleşmede-return kaldırıldı."""
    _sahte_ollama(monkeypatch, kobe, ["Arabic", "Latin", "Latin"])
    assert kobe.detect_script_qwen(uc_kare) == "en"

    _sahte_ollama(monkeypatch, kobe, ["Arabic", "Latin", "Arabic"])
    assert kobe.detect_script_qwen(uc_kare) == "ar"


def test_router_tek_oy_yetmez(kobe, uc_kare, monkeypatch):
    """oy_esik=2: iki kare hata verip biri 'Arabic' derse filmi Arapça'ya çevirme."""
    _sahte_ollama(monkeypatch, kobe, ["Arabic"])   # kalan 2 istek OSError
    assert kobe.detect_script_qwen(uc_kare) == "en"


def test_router_negasyonu_yutmaz(kobe, uc_kare, monkeypatch):
    """'Not Arabic, it is Latin' → substring eşleşmesi 'ar' döndürüyordu.
    Cevapta BİRDEN FAZLA farklı dil geçiyorsa oy kullanılmaz (belirsiz)."""
    _sahte_ollama(monkeypatch, kobe, ["Not Arabic, it is Latin"] * 3)
    assert kobe.detect_script_qwen(uc_kare) == "en"


def test_router_cumle_icindeki_tek_dili_okur(kobe, uc_kare, monkeypatch):
    """Model tek kelimeyle cevap vermezse de tek dil geçiyorsa oy geçerli."""
    _sahte_ollama(monkeypatch, kobe, ["The script is Cyrillic."] * 3)
    assert kobe.detect_script_qwen(uc_kare) == "ru"


def test_router_deterministik(kobe, uc_kare, monkeypatch):
    """temperature verilmeyince aynı film iki koşuda farklı dil veriyordu →
    110-film ölçümü tekrarlanabilir DEĞİLDİ."""
    kayit: dict = {}
    _sahte_ollama(monkeypatch, kobe, ["Latin"] * 3, kayit)
    kobe.detect_script_qwen(uc_kare)
    for istek in kayit["istekler"]:
        assert istek["options"]["temperature"] == 0


def test_router_cok_alfabe_destegi_korunur(kobe, uc_kare, monkeypatch):
    """483f48a2 ile bilinçli eklenen CJK/Yunan desteği kaldırılmadı
    (dış inceleme 'DESTEKLENEN={en,ru,ar}' önerdi — REDDEDİLDİ, regresyon olurdu)."""
    for cevap, beklenen in [("Chinese", "ch"), ("Japanese", "japan"),
                            ("Korean", "korean"), ("Greek", "gr")]:
        _sahte_ollama(monkeypatch, kobe, [cevap] * 3)
        assert kobe.detect_script_qwen(uc_kare) == beklenen


def test_router_hepsi_hata_ise_en(kobe, uc_kare, monkeypatch):
    _sahte_ollama(monkeypatch, kobe, [])
    assert kobe.detect_script_qwen(uc_kare) == "en"


# ── B. script alanı tüm dönüş yollarında (O1) ────────────────────────────
def test_kredi_yok_donusunde_script_dolu(kobe, tmp_path, monkeypatch):
    """ŞİKÂYETİN KÖKÜ: kredi_yok dönen film manifest/PDF'te script='en' (Latin)
    görünüyordu — yönlendirici 'ar' demiş olsa bile."""
    d = _kare_dizini(tmp_path, 60)
    monkeypatch.setattr(kobe, "detect_script_qwen", lambda yollar: "ar")

    r = kobe.tespit_v5(str(d))

    assert r.yontem == "kredi_yok"
    assert r.script == "ar", "kredi_yok dönüşü script'i düşürüyor → PDF'te 'hep Latin'"


def test_kredi_yok_ikinci_yol_da_script_tasir(kobe, tmp_path, monkeypatch):
    """İçerik-eşiği geçilemeyen dönüş yolu (adaylar VAR ama hiçbiri geçmedi)."""
    d = _kare_dizini(tmp_path, 60)
    n = len(kobe.kareler(str(d))[::2])
    jb = np.zeros(n, bool)
    jb[int(n * 0.85):] = True            # son %15'te sürdürülen kutu koşusu
    kobe._sahte_cb._jb, kobe._sahte_cb._say = jb, np.full(n, 4, np.int16)
    monkeypatch.setattr(kobe, "detect_script_qwen", lambda yollar: "ru")

    r = kobe.tespit_v5(str(d))

    assert r.start_frame == -1
    assert r.script == "ru"


def test_kare_yok_donusu_bozulmadi(kobe, tmp_path):
    """<10 kare: örneklenecek kare yok, varsayılan 'en' dürüst — davranış korunur."""
    d = _kare_dizini(tmp_path, 5)
    r = kobe.tespit_v5(str(d))
    assert r.yontem == "kare_yok"
    assert r.script == "en"


# ── C. OCR hata görünürlüğü (K1) ─────────────────────────────────────────
def test_ocr_calisma_hatasi_sayilir_ve_yutulmaz_degil(kobe, caplog):
    """OSError/RuntimeError gerçek çalışma hatası: [] dönülür AMA sayılır+loglanır."""
    sayac = kobe._OcrSayac()

    def _patlat(yol):
        raise OSError("dosya okunamadı")

    cc = _SahteCC(satirlar_fn=_patlat)
    with caplog.at_level("WARNING"):
        assert kobe._ocr_satirlar(cc, "c_00001.png", sayac) == []

    assert sayac.hata == 1
    assert "c_00001.png" in caplog.text


def test_program_hatasi_yutulmaz(kobe):
    """841 sessiz çöküşün SINIFI: NameError/AttributeError bir BUG'dır,
    'OCR başarısız' değil. Yukarı kaçmalı ki errors.jsonl'e düşsün."""
    sayac = kobe._OcrSayac()

    def _bug(yol):
        raise NameError("name '_kare_okunabilir_mi' is not defined")

    cc = _SahteCC(satirlar_fn=_bug)
    with pytest.raises(NameError):
        kobe._ocr_satirlar(cc, "c_00001.png", sayac)
    assert sayac.hata == 0


def test_ocr_hata_sonuca_yansir(kobe, tmp_path, monkeypatch):
    """Sayaç Sonuc'a çıkmalı — manifest üzerinden izlemeye düşsün."""
    d = _kare_dizini(tmp_path, 60)
    monkeypatch.setattr(kobe, "detect_script_qwen", lambda yollar: "en")
    r = kobe.tespit_v5(str(d))
    assert hasattr(r, "ocr_hata")
    assert r.ocr_hata == 0


# ── D. Kurtarma yolu sınırları (K4) ──────────────────────────────────────
def _kurtarma_cagir(kobe, aktif: np.ndarray, roller_var=True):
    n = len(aktif)
    cc = _SahteCC(satirlar_fn=lambda yol: (["DIRECTOR"] if roller_var else ["xxx"]))
    g = [f"c_{i:05d}.png" for i in range(n)]
    return kobe._scroll_kurtarma(g, list(range(n)), cc, aktif.copy(),
                                 np.ones(n, bool), n, fps=25.0, stride=2)


def test_kurtarma_geri_yurume_alt_sinirla_kisitli(kobe):
    """SINIRSIZ geri-yürüme: aktif koşu filmin %30'undan sona kadar sürerse
    kurtarma yolu filmin %30'unu 'jenerik başlangıcı' ilan ediyordu."""
    n = 600
    aktif = np.zeros(n, bool)
    aktif[180:] = True                    # %30'dan sona kadar kesintisiz
    sonuc = _kurtarma_cagir(kobe, aktif)

    assert sonuc is not None
    ks, ke = sonuc
    assert ks >= int(0.50 * (n - 1)), f"onset %50'nin gerisine kaçtı: {ks}"


def test_kurtarma_normal_kosuyu_bozmaz(kobe):
    """Sınırın SAĞLIKLI tarafı: son %25 içinde başlayan koşu aynen bulunur."""
    n = 600
    aktif = np.zeros(n, bool)
    aktif[460:] = True
    sonuc = _kurtarma_cagir(kobe, aktif)
    assert sonuc == (460, 599)


def test_kurtarma_rolsuz_kosuyu_reddeder(kobe):
    n = 600
    aktif = np.zeros(n, bool)
    aktif[460:] = True
    assert _kurtarma_cagir(kobe, aktif, roller_var=False) is None


def test_kurtarma_kisa_kosuyu_reddeder(kobe):
    """min_kosu = max(16, fps*8/stride) = 100 örnek-kare."""
    n = 600
    aktif = np.zeros(n, bool)
    aktif[520:580] = True                 # 60 < 100
    assert _kurtarma_cagir(kobe, aktif) is None


def test_kurtarma_bitisi_her_zaman_son_ceyrekte(kobe):
    """DIŞ İNCELEME İTİRAZI: 'bitiş çapası (SON_ERISIM analoğu) yok' denildi.
    Tarama %75 sınırından başladığı için bulunan HER koşu ya 449'u içerir ya da
    sonrasında başlar → ke ASLA %75'in altına inemez. Ek bir çapa ÖLÜ KOD olurdu;
    bu test o değişmezi kilitler (bir gün tarama başlangıcı değişirse kırılır)."""
    rng = np.random.default_rng(20260811)
    n = 600
    for _ in range(200):
        aktif = rng.random(n) < 0.7
        sonuc = _kurtarma_cagir(kobe, aktif)
        if sonuc is None:
            continue
        _, ke = sonuc
        assert ke >= int(0.75 * (n - 1)), f"koşu sonu %75'in altında bitti: {ke}"
