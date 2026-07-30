# -*- coding: utf-8 -*-
"""test_surface_pdf_yolu.py — pdf_path=None iken Path('') tuzağı (Errno 21) kilidi.

Kök sorun (2026-07-30, EK_TAKS + YAĞMACILAR koşularında kanıtlı):
`Path((pdf_info).get("pdf_path") or "")` → pdf_path None iken `Path('')` = `Path('.')`.
O da VAR OLAN BİR DİZİN olduğundan `.exists()` True döner → yedek arama atlanır →
`shutil.copy2('.', hedef)` → IsADirectoryError (Errno 21). İki kurban:
  1) surface_deliverables (mitas_pipeline.py:283) → `surface_failed` olayı
  2) export kopyası (mitas_pipeline.py:3739) → md teslimi de İPTAL, sahte .pdf yolu raporlanır

Fix: `.exists()` → `.is_file()` (dizin dosya değildir).

Çalıştır: /opt/mitas/venvs/ocr/bin/python -m pytest tests/test_surface_pdf_yolu.py -q
"""
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))          # mitas_pipeline `import debug_trace` çözümü
_spec = importlib.util.spec_from_file_location(
    "pipeline_surface_under_test", _ROOT / "scripts" / "mitas_pipeline.py")
mp = importlib.util.module_from_spec(_spec)
sys.modules["pipeline_surface_under_test"] = mp
_spec.loader.exec_module(mp)


def _hub(tmp_path: Path) -> Path:
    clip = tmp_path / "HUB"
    (clip / "pdf").mkdir(parents=True)
    return clip


def test_pdf_path_none_patlamaz_ve_sahte_pdf_uretmez(tmp_path, monkeypatch):
    """pdf render başarısız (pdf_path=None) → yüzeyleme patlamamalı, köke .pdf koymamalı."""
    monkeypatch.chdir(tmp_path)          # cwd'de '.' her zaman var — tuzağın ta kendisi
    clip = _hub(tmp_path)

    mp.surface_deliverables(clip, "1970-0021-1-0000-90-1", "YAĞMACILAR",
                            {"pdf_path": None, "md_path": None})

    kokte_pdf = list(clip.glob("*.pdf"))
    assert kokte_pdf == [], f"sahte PDF yüzeylendi: {kokte_pdf}"


def test_pdf_path_none_md_yuzeyi_calisir(tmp_path, monkeypatch):
    """PDF yokken md varsa .txt yüzeyi yine üretilmeli (mevcut davranış korunur)."""
    monkeypatch.chdir(tmp_path)
    clip = _hub(tmp_path)
    (clip / "pdf" / "kunye_teslim.md").write_text("# KÜNYE\nYönetmen: X\n", encoding="utf-8")

    mp.surface_deliverables(clip, "1970-0021-1-0000-90-1", "YAĞMACILAR",
                            {"pdf_path": None, "md_path": None})

    assert (clip / "1970-0021-1-0000-90-1 YAĞMACILAR.txt").exists()
    assert list(clip.glob("*.pdf")) == []


def test_gercek_pdf_varsa_yuzeylenir(tmp_path, monkeypatch):
    """Gerçek kunye.pdf diskte → köke kopyalanır (regresyon yok)."""
    monkeypatch.chdir(tmp_path)
    clip = _hub(tmp_path)
    (clip / "pdf" / "kunye.pdf").write_bytes(b"%PDF-1.4 sahte")

    mp.surface_deliverables(clip, "1970-0021-1-0000-90-1", "YAĞMACILAR", {"pdf_path": None})

    hedef = clip / "1970-0021-1-0000-90-1 YAĞMACILAR.pdf"
    assert hedef.exists() and hedef.read_bytes().startswith(b"%PDF")


def test_export_bloku_is_file_kullanir():
    """Export kopyası (main içi, satır ~3739) aynı tuzağı taşımamalı — is_file şart."""
    src = (_ROOT / "scripts" / "mitas_pipeline.py").read_text(encoding="utf-8", errors="replace")
    i = src.find('pdf_src = Path(pdf_info.get("pdf_path") or "")')
    assert i > 0, "export pdf_src satırı bulunamadı (kod taşındıysa testi güncelle)"
    blok = src[i:i + 400]
    assert ".exists()" not in blok, "export bloğu hâlâ .exists() kullanıyor — Path('') tuzağı açık"
    assert ".is_file()" in blok
