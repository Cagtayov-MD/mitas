"""OCR-teyitli yapımcı KB-fill (2026-07-07, PARDAYYAN / Georges Campana).

Bağlam: DEFERANS kapısı yapımcıyı yalnız extraction çıktısına bakarak "OCR boş → boş kalır"
sayıyordu. Extraction (LLM model:null düştü + VL Fransızca "Producteur délégué" etiketini
kaçırdı) yapımcıyı düşürdüğünde, ham OCR'da "GEORGES CAMPANA" AÇIKÇA dururken KB-fill yanlışlıkla
fabrikasyon sanılıp atlanıyordu → final PDF'de "Yapımcı: —".

_yapimci_ocr_corroborated(): KB-yapımcı adının ham OCR'da FİZİKSEL varlığını doğrular.
Var ise fill (OCR-otorite + kanonik yazım), yoksa deferans korunur (fabrikasyon imkânsız kalır).
"""
import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(r"E:\MITAS\scripts")


def _load_mod():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    path = SCRIPTS / "tek_film_kunye.py"
    spec = importlib.util.spec_from_file_location("tek_film_kunye_ocrcorrob_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    mod._YAPIMCI_OCR_CORROB = True  # test için açık olsun (production'da da default-ON)
    return mod


def _make_clip(tmp_path, ocr_ham_text):
    """Sahte film klasörü: <clip>/ocr/ocr-xxx/ocr_ham.txt"""
    ocr_dir = tmp_path / "ocr" / "ocr-deadbeef"
    ocr_dir.mkdir(parents=True)
    (ocr_dir / "ocr_ham.txt").write_text(ocr_ham_text, encoding="utf-8")
    return str(tmp_path)


PARDAYYAN_HAM = """Un Film De
EDOUARD NIERMANS
Producteur délégué
GEORGES CAMPANA
Producteur Executif Jan BILEK
JEAN-LUC BIDEAU
"""


def test_kb_producer_present_in_ocr_is_corroborated(tmp_path):
    """PARDAYYAN vakası: KB 'Georges Campana' bulur, ham OCR'da 'GEORGES CAMPANA' var → teyitli."""
    mod = _load_mod()
    clip = _make_clip(tmp_path, PARDAYYAN_HAM)
    out = mod._yapimci_ocr_corroborated(["Georges Campana"], clip)
    assert out == ["Georges Campana"]


def test_accent_and_case_insensitive_match(tmp_path):
    """Aksan/harf farkı (é, büyük/küçük) eşleşmeyi engellemez (ascii-fold)."""
    mod = _load_mod()
    clip = _make_clip(tmp_path, "producteur délégué\ngeorges campaña\n")
    out = mod._yapimci_ocr_corroborated(["Georges Campana"], clip)
    assert out == ["Georges Campana"]


def test_producer_absent_from_ocr_is_rejected(tmp_path):
    """Fabrikasyon önlemi: KB-yapımcı adı OCR'da YOKSA teyit YOK (deferans korunur)."""
    mod = _load_mod()
    clip = _make_clip(tmp_path, PARDAYYAN_HAM)
    assert mod._yapimci_ocr_corroborated(["Steven Spielberg"], clip) == []
    assert mod._yapimci_ocr_corroborated(["Christopher Nolan"], clip) == []


def test_partial_name_not_enough(tmp_path):
    """İsmin TÜM parçaları gerekir: yalnız soyadı OCR'da olsa da (adı yoksa) teyit YOK."""
    mod = _load_mod()
    clip = _make_clip(tmp_path, "Producteur\nCAMPANA seuls\n")  # yalnız 'CAMPANA', 'GEORGES' yok
    assert mod._yapimci_ocr_corroborated(["Georges Campana"], clip) == []


def test_mixed_list_keeps_only_corroborated(tmp_path):
    """Karışık liste: yalnız OCR-teyitli ad(lar) döner."""
    mod = _load_mod()
    clip = _make_clip(tmp_path, PARDAYYAN_HAM)
    out = mod._yapimci_ocr_corroborated(["Georges Campana", "Steven Spielberg"], clip)
    assert out == ["Georges Campana"]


def test_flag_off_is_pure_deference(tmp_path):
    """Fail-safe: MITAS_YAPIMCI_OCR_CORROB kapalıysa hiç teyit yapılmaz (eski saf-deferans)."""
    mod = _load_mod()
    mod._YAPIMCI_OCR_CORROB = False
    clip = _make_clip(tmp_path, PARDAYYAN_HAM)
    assert mod._yapimci_ocr_corroborated(["Georges Campana"], clip) == []


def test_empty_inputs_safe(tmp_path):
    """Boş/eksik girdi güvenli: boş liste, boş clip, olmayan OCR → [] (crash yok)."""
    mod = _load_mod()
    assert mod._yapimci_ocr_corroborated([], str(tmp_path)) == []
    assert mod._yapimci_ocr_corroborated(["Georges Campana"], "") == []
    # OCR klasörü yok → sessizce [] (akış bozulmaz)
    assert mod._yapimci_ocr_corroborated(["Georges Campana"], str(tmp_path)) == []
