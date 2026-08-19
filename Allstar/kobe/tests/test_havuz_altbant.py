"""ALT BANT — giriş havuzunda altyazı elemesi (2026-08-20).

Kanıtlanmış kayıp: Çiçek Taksi bölüm 2 girişinde `g_0030..g_0034` karelerinde
EROL GÜNAYDIN yazıyordu; `alt_only` kuralı beşini de OCR'a hiç sokmadan
"footage" diye eledi ve isim havuzdan tamamen düştü.

Kural filmlerde DOĞRU (alt bantta tek satır = gömülü altyazı), dizi
açılışında YANLIŞ (oyuncu ismi tam orada yazıyor). Aynı kusur Nash'te
2026-08-19'da bulunup düzeltilmişti (`197b1f33e`, aynı oyuncu, aynı dizi);
Kobe'ye uygulanmamıştı.

Düzeltme: alt bant karesi artık reddedilmiyor, OCR'a sokulup İÇERİĞİNE
bakılıyor. Kredi gibi görünüyorsa havuza alınıyor ama `"icerik"` SAYILMIYOR —
`icerik_kareleri()` yalnız `"icerik"` döndürdüğü için 36 filmde kalibre edilen
bitiş kuralı (bkz. test_bitis.py) bu değişiklikten etkilenmez.
"""
import sys
from pathlib import Path

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE / "src"))
sys.path.insert(0, str(KULE / "src" / "ortak"))

from giris import havuz  # noqa: E402


class _SahteKutu:
    def __init__(self, n, alt_only):
        self._a = {"n": n, "alt_only": alt_only}

    def kutu_analiz(self, yol):
        return dict(self._a)


class _SahteIcerik:
    def __init__(self, satirlar, kredi_skoru, cop=False):
        self._s, self._k, self._c = satirlar, kredi_skoru, cop

    def satirlar(self, yol):
        return list(self._s)

    def kredi_benzeri(self, satirlar):
        return self._k

    def cop_desenli_mi(self, bloklar):
        return self._c


def _kur(monkeypatch, *, n, alt_only, satirlar, kredi):
    monkeypatch.setattr(havuz, "kutu", _SahteKutu(n, alt_only))
    monkeypatch.setattr(havuz, "icerik", _SahteIcerik(satirlar, kredi))


def test_alt_bantta_kredi_havuza_ALINIR(monkeypatch):
    """EROL GÜNAYDIN vakası: alt bantta tek kutu ama metin kredi gibi."""
    _kur(monkeypatch, n=1, alt_only=True, satirlar=["EROL GÜNAYDIN"], kredi=1)
    al, satirlar, neden = havuz._kare_karari("x.png")
    assert al is True
    assert satirlar == ["EROL GÜNAYDIN"]
    assert neden == "recall_altbant"


def test_alt_bant_karesi_ICERIK_SAYILMAZ(monkeypatch):
    """Bitis kurali yalniz 'icerik' ile calisir; kalibrasyon bozulmamali."""
    _kur(monkeypatch, n=1, alt_only=True, satirlar=["EROL GÜNAYDIN"], kredi=1)
    assert havuz._kare_karari("x.png")[2] != "icerik"


def test_alt_bantta_gercek_ALTYAZI_yine_elenir(monkeypatch):
    """Kredi gibi gorunmeyen alt bant metni (gomulu altyazi) reddedilir."""
    _kur(monkeypatch, n=1, alt_only=True,
         satirlar=["nereye gidiyorsun"], kredi=0)
    al, _, neden = havuz._kare_karari("x.png")
    assert al is False
    assert neden == "icerik_yok"


def test_alt_bant_DISI_kredi_hala_icerik(monkeypatch):
    """Regresyon: normal jenerik karesi eskisi gibi 'icerik' kalmali."""
    _kur(monkeypatch, n=3, alt_only=False, satirlar=["GÜL GÖLGE"], kredi=1)
    al, _, neden = havuz._kare_karari("x.png")
    assert al is True
    assert neden == "icerik"


def test_kutusuz_kare_hala_footage(monkeypatch):
    """Regresyon: n==0 yolu degismemeli — OCR'a hic girmemeli."""
    _kur(monkeypatch, n=0, alt_only=False, satirlar=["X"], kredi=1)
    al, _, neden = havuz._kare_karari("x.png")
    assert al is False
    assert neden == "footage"
