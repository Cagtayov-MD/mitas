"""KULE DIŞARI UZANMAZ — Çağatay kuralı: "bu kule kendi yaşayacak,
dış bağımlılığı olmayacak."

Kule yalnız kendi kodunu, kendi çalışma zamanını ve kendisine GÖSTERİLEN
klasörü bilir. Yasak olanlar:

  * başka bir kulenin / pipeline'ın dosyasını import etmek
    (master_png_monitor, db_compose_master, giris_master_cropstack…)
  * Database'e veya sabit bir üretim yoluna uzanmak
  * Makinenin ORTAK Ollama servisine bağlanmak. LeBron yalnız kendi yerel
    runtime/store sürecini rastgele loopback portunda açabilir.

Bu test kuralı KODDA kilitler. Bağlanmak isteyen önce burayı silmek zorunda
kalsın — yanlışlıkla değil, bilerek yapsın.
"""
import ast
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]

YASAK_MODUL = {
    "master_png_monitor", "db_compose_master", "dcmaster",
    "giris_master_cropstack", "giris_cropstack",
    "lebron_james",          # kaynak dosya TAŞINDI, çağrılmaz
    "ollama", "httpx", "urllib",
}

# Kulenin içinde geçmemesi gereken metinler (import olmasa bile).
YASAK_METIN = (
    "/opt/mitas/Database", "OCR-worktree", "harness/master_dup",
    "localhost:11434", "127.0.0.1:11434",
)


# Kule kuralı ÇALIŞMA ZAMANI için geçerlidir: `lebron` çağrıldığında koşan kod.
# Aşağıdaki dizinler kasıtlı olarak dışarıda:
#   olcum/  — ölçüm yatağı. Görevi GEREĞİ üretimi çağırır (kapi_sadakat.py
#             üretim yoluyla kıyaslıyor; saglik/uret db_compose_master okuyor).
#             Kıyaslanacak şey zaten dışarıdadır.
#   arsiv/  — eski denemeler. Kör taşındı, koşulmuyor; içinde sözdizimi bozuk
#             dosya bile var (benchmark_iyilestirmeler.py:82, ORİJİNALİNDE bozuk).
#   arac/   — master'ı dilimleyen/okuyan yan scriptler; pipeline'a ait, kuleye
#             referans olarak toplandı.
#   aday/   — henüz devrede OLMAYAN motor(lar). src/ YALNIZ koşan kodu tutar;
#             aday oraya ancak ölçüm kazandığında girer.
# Bu dizinlerin çalışma zamanına SIZMADIĞI ayrıca test ediliyor (aşağıda).
KOSMAYAN = {"olcum", "arsiv", "arac", "raporlar", "aday"}


def _kule_dosyalari() -> list[Path]:
    """Kulenin ÇALIŞMA ZAMANI kaynak dosyaları."""
    haric = {"venv", "model", "out", "scratch", "logs",
             "__pycache__", ".pytest_cache", "tests"} | KOSMAYAN
    return sorted(p for p in KULE.rglob("*.py")
                  if not (set(p.relative_to(KULE).parts) & haric))


def _import_adlari(yol: Path) -> set[str]:
    agac = ast.parse(yol.read_text(encoding="utf-8"), filename=str(yol))
    adlar: set[str] = set()
    for d in ast.walk(agac):
        if isinstance(d, ast.Import):
            for a in d.names:
                adlar.add(a.name.split(".")[0])
        elif isinstance(d, ast.ImportFrom) and d.module:
            adlar.add(d.module.split(".")[0])
    return adlar


def test_kule_dosyalari_var():
    """Bekçi: kule silinip test sessizce boş geçmesin."""
    d = _kule_dosyalari()
    adlar = {p.stem for p in d}
    assert {"main", "sozlesme", "derleyici", "yukleyici", "kural"} <= adlar, adlar


@pytest.mark.parametrize("yol", _kule_dosyalari(), ids=lambda p: p.name)
def test_yasak_modul_import_edilmez(yol):
    bulunan = _import_adlari(yol) & YASAK_MODUL
    assert not bulunan, (
        f"{yol.name} {bulunan} import ediyor — kule dışarı uzanıyor. "
        "Gereken şey varsa kuleye TAŞI, çağırma."
    )


def _kod_metinleri(yol: Path) -> list[str]:
    """Dosyadaki GERÇEK string sabitleri — docstring'ler hariç.

    Yorumda ve docstring'de kaynak göstermek serbest ve GEREKLİDİR (taşınan
    kodun nereden geldiği yazılı kalmalı). Yasak olan, o yolun çalışan koda
    girmesi. Ayrım satır-metniyle yapılamaz; AST ile yapılır.
    """
    agac = ast.parse(yol.read_text(encoding="utf-8"), filename=str(yol))
    docstringler = set()
    for d in ast.walk(agac):
        if isinstance(d, (ast.Module, ast.ClassDef, ast.FunctionDef,
                          ast.AsyncFunctionDef)):
            g = d.body[0] if d.body else None
            if (isinstance(g, ast.Expr) and isinstance(g.value, ast.Constant)
                    and isinstance(g.value.value, str)):
                docstringler.add(id(g.value))
    return [d.value for d in ast.walk(agac)
            if isinstance(d, ast.Constant) and isinstance(d.value, str)
            and id(d) not in docstringler]


@pytest.mark.parametrize("yol", _kule_dosyalari(), ids=lambda p: p.name)
def test_yasak_yol_gecmez(yol):
    for s in _kod_metinleri(yol):
        for y in YASAK_METIN:
            assert y not in s, (
                f"{yol.name} kodunda '{y}' geciyor — sabit dis yol/servis."
            )


def test_cikti_kule_icinde():
    """out/ kulenin İÇİNDE — çağıran çıktı yolunu seçmez, kule kendi evine yazar."""
    import main
    assert main.OUT == KULE / "out"
    assert KULE in main.OUT.parents or main.OUT.parent == KULE


def test_calisma_zamani_kendi_venv():
    """`lebron` betiği kendi venv'ini çağırır — çağıran python bilmez."""
    betik = (KULE / "lebron").read_text(encoding="utf-8")
    assert "venv/bin/python" in betik
    assert "main.py" in betik


@pytest.mark.parametrize("yol", _kule_dosyalari(), ids=lambda p: p.name)
def test_kosmayan_dizinler_calisma_zamanina_sizmaz(yol):
    """olcum/arsiv/arac ÇALIŞMA ZAMANINA giremez.

    Bu dizinler üretime bakabildiği için (ölçüm yatağının işi budur) kule
    kuralından muaflar. Muafiyet tek yönlü olmalı: ölçüm kuleyi çağırabilir,
    kule ölçümü ÇAĞIRAMAZ. Aksi halde muafiyet arka kapıya döner.
    """
    adlar = _import_adlari(yol)
    sizan = adlar & {"saglik", "sadakat", "dup_metrik", "uret", "uret_ex", "atlas",
                     "kapi_sadakat", "master_dilim_oku", "master_png_dilimle"}
    assert not sizan, f"{yol.name} olcum/arac modullerini import ediyor: {sizan}"
    for s in _kod_metinleri(yol):
        for d in KOSMAYAN:
            assert f"{d}/" not in s, f"{yol.name} kodunda '{d}/' yolu geciyor"


def test_aday_motor_kulede_ama_BAGLI_DEGIL():
    """İbrahimovic kör taşındı: kulede durur, ama hiçbir yerden çağrılmaz.

    Çağatay 2026-08-15: "ilerde onu lebron ile destekleyeceğim." Magic o
    birleşmenin adıydı; 2026-08-18'de ÖLÇÜMLE terfi etti (aşağıdaki test).
    İbrahimovic 437 filmlik koşuda üçüncü kaldı (340/356/370 sağlıklı) —
    bekleme odasında korumalı durur: silinmez, sessizce bağlanmaz.
    """
    aday = KULE / "aday" / "ibrahimovic.py"
    assert aday.is_file(), "aday motor kaybolmus"
    for yol in _kule_dosyalari():
        assert "ibrahimovic" not in _import_adlari(yol), (
            f"{yol.name} aday motoru import ediyor — olculmeden devreye alinamaz"
        )


def test_secilen_motor_kalici_lebron_kulemasteri():
    """Seçilen birleşik motor artık doğrudan ``derleyici`` adını taşır."""
    assert (KULE / "src" / "derleyici.py").is_file()
    assert not (KULE / "src" / "magic.py").exists()
    kaynak = (KULE / "main.py").read_text(encoding="utf-8")
    assert "import derleyici" in kaynak
    assert "import magic" not in kaynak


def test_ollama_yalniz_kule_owned_private_surec():
    kaynak = (KULE / "src" / "model.py").read_text(encoding="utf-8")
    assert '"OLLAMA_NO_CLOUD": "1"' in kaynak
    assert '"OLLAMA_MODELS": str(self.store)' in kaynak
    assert "11434" not in kaynak
    assert "start_new_session=False" in kaynak


def test_aday_motorun_bilinen_borclari():
    """Kör taşımanın bedeli GÖRÜNÜR olsun — gizlenmesin.

    İbrahimovic olduğu gibi taşındı, kule kuralına uydurulmadı. Bağlanmadan
    önce kapatılması gereken borçlar bunlar; test onları yazılı tutar.
    """
    metin = (KULE / "aday" / "ibrahimovic.py").read_text(encoding="utf-8")
    borclar = {
        "gomulu_mutlak_yol": "/home/cagatay/Ex_Frame" in metin,
        "olcum_modulune_baglaniyor": "import saglik" in metin,
    }
    assert any(borclar.values()), (
        "Borclar kapanmis gorunuyor — oyleyse bu testi guncelle ve aday motoru "
        "src/'in tam vatandasi yap."
    )
