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


# ── temsil sayısı (2026-08-20, Çağatay'ın bulgusu) ──────────────────────
# Dedup aynı metni okuyan kareleri TEK temsilciye indiriyor. Aşağı akıştaki
# LeBron ise tek kareli segmentten EK KANIT istiyor ("anlık yazı olmasın").
# İki kural ters çalışıyor: kart ne kadar TEMİZ okunursa dedup onu o kadar
# kesin tek kareye indiriyor, kapı da ona o kadar sert davranıyor.
# EROL GÜNAYDIN beş karede de aynı okundu → tek temsilci → LeBron eledi.
# Çözüm: dedup'ın YOK ETTİĞİ bilgiyi taşı — temsilci kaç kareyi temsil ediyor.

def test_temsil_kare_sayilir(monkeypatch, tmp_path):
    """Aynı metni okuyan 3 kare → 1 temsilci, ama temsil_kare=3."""
    for n in (1, 2, 3):
        (tmp_path / f"g_{n:04d}.png").write_bytes(b"x")
    _kur(monkeypatch, n=2, alt_only=False, satirlar=["EROL GÜNAYDIN"], kredi=1)
    r = havuz.sec(tmp_path, None)
    assert len(r["kareler"]) == 1                     # dedup calisti
    kayit = r["siniflar"]["g_0001.png"]
    assert kayit["sinif"] == "icerik"
    assert kayit["temsil_kare"] == 3                  # ama kac kare oldugu KAYITLI
    # KARDES ADRESLERI: tuketici gerekirse kaynaktan cekebilsin
    assert kayit["temsil"] == ["g_0001.png", "g_0002.png", "g_0003.png"]
    assert kayit["metin"] == "EROL GÜNAYDIN"
    assert r["kaynak"].endswith(str(tmp_path).split("/")[-1])


def test_tek_karelik_yazi_temsil_1(monkeypatch, tmp_path):
    """Gercekten anlik yazi: tek kare → temsil_kare=1, kapi sinavina girer."""
    (tmp_path / "g_0001.png").write_bytes(b"x")
    _kur(monkeypatch, n=2, alt_only=False, satirlar=["ANLIK"], kredi=1)
    r = havuz.sec(tmp_path, None)
    assert r["siniflar"]["g_0001.png"]["temsil_kare"] == 1


def test_imzasiz_kare_temsil_1(monkeypatch, tmp_path):
    """Satiri olmayan (recall) kare dedup'a girmez; temsil_kare 1 kalir."""
    (tmp_path / "g_0001.png").write_bytes(b"x")
    _kur(monkeypatch, n=1, alt_only=False, satirlar=[], kredi=0)
    r = havuz.sec(tmp_path, None)
    assert r["siniflar"]["g_0001.png"]["temsil_kare"] == 1
