# -*- coding: utf-8 -*-
"""test_nonlatin_source_propagation_20260623.py — FIX-C: nonlatin_source propagasyonu.

PANEL #3 bug: _pipe_credit_text.py 'out' sözlüğü read_credits_auto'nun döndürdüğü
nonlatin_source + translit_method alanlarını DROP ediyordu → qc_block:791 HEP
nonlatin_source=False görüyordu → erken-romanize Latin-dışı künye KONTROL'e gitmeden
ONAYLI'ya çıkabiliyordu.

Kapsam (DB/LLM/ağ'sız, deterministik — read_credits_auto monkeypatch'lenir):
  • PROPAGATION: _pipe_credit_text.main() ürettiği JSON nonlatin_source/translit_method TAŞIR.
  • GATE: qc_credit_block(nonlatin_source=True) → KONTROL (RENDER gerekçesi). False → gate sessiz.
  • ADDITIVE: nonlatin_source=False/None (Latin film) → out dict eski davranış, sinyal yutulmaz.

Çalıştır:  python -m pytest tests/test_nonlatin_source_propagation_20260623.py -v
"""
import io
import json
import os
import sys

os.environ.pop("MITAS_TMDB", None)
os.environ.pop("TMDB_API_KEY", None)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))


# ─────────────────────── PROPAGATION: _pipe_credit_text 'out' dict ───────────────────────
def _run_pipe_with_fake_read(tmp_path, fake_res):
    """_pipe_credit_text.main()'i sahte read_credits_auto ile koştur → stdout JSON döndür."""
    import _pipe_credit_text as p
    import credit_text_read as ctr

    # OCR dosyası VAR gibi göster (içerik önemsiz; read_credits_auto monkeypatch'li).
    ocr_dir = os.path.join(str(tmp_path), "ocr", "run1")
    os.makedirs(ocr_dir, exist_ok=True)
    ocr_txt = os.path.join(ocr_dir, "kunye.txt")
    with open(ocr_txt, "w", encoding="utf-8") as f:
        f.write("dummy\n")

    _orig_read = ctr.read_credits_auto
    _orig_lines = ctr.load_llm_lines_for_ocr
    _orig_ctx = ctr.load_raw_context_for_ocr
    ctr.read_credits_auto = lambda *a, **k: dict(fake_res)
    ctr.load_llm_lines_for_ocr = lambda ocr: (["dummy"], "ham")
    ctr.load_raw_context_for_ocr = lambda ocr: []

    class _Buf(io.StringIO):
        def reconfigure(self, *a, **k):  # _pipe_credit_text.main() stdout.reconfigure çağırır
            return None

    _argv = sys.argv
    _stdout = sys.stdout
    sys.argv = ["_pipe_credit_text.py", "--ocr", ocr_txt, "--title", "X"]
    buf = _Buf()
    sys.stdout = buf
    try:
        p.main()
    finally:
        sys.stdout = _stdout
        sys.argv = _argv
        ctr.read_credits_auto = _orig_read
        ctr.load_llm_lines_for_ocr = _orig_lines
        ctr.load_raw_context_for_ocr = _orig_ctx
    # son satır = tek-satır JSON
    line = [l for l in buf.getvalue().splitlines() if l.strip()][-1]
    return json.loads(line)


def test_propagation_nonlatin_true_tasinir(tmp_path):
    res = {"yonetmen": ["Zeki Alasya"], "yapimci": [], "cast": ["Metin Akpinar"],
           "guven": "OKUNDU", "nonlatin_source": True, "translit_method": "unidecode"}
    out = _run_pipe_with_fake_read(tmp_path, res)
    assert out.get("nonlatin_source") is True
    assert out.get("translit_method") == "unidecode"


def test_propagation_latin_false_additive(tmp_path):
    # Latin film: read_credits_auto nonlatin_source=False/None → out yutmaz, eski davranış.
    res = {"yonetmen": ["John Doe"], "yapimci": [], "cast": ["Jane Roe"],
           "guven": "OKUNDU", "nonlatin_source": False, "translit_method": None}
    out = _run_pipe_with_fake_read(tmp_path, res)
    assert out.get("nonlatin_source") is False
    assert out.get("translit_method") is None
    # mevcut alanlar bozulmadı (additive kanıtı)
    assert out.get("yonetmen") == ["John Doe"]
    assert out.get("guven") == "OKUNDU"


def test_propagation_eksik_alan_false_default(tmp_path):
    # read_credits_auto eski şema (alan yok) → out nonlatin_source False (KeyError yok, fail-safe).
    res = {"yonetmen": ["A B"], "yapimci": [], "cast": ["C D"], "guven": "OKUNDU"}
    out = _run_pipe_with_fake_read(tmp_path, res)
    assert out.get("nonlatin_source") is False
    assert out.get("translit_method") is None


# ─────────────────────── GATE: qc_block nonlatin_source → KONTROL ───────────────────────
def test_qc_gate_nonlatin_true_kontrol():
    import credit_qc_block as q
    q._upper_names = lambda names: [str(n).upper() for n in (names or [])]
    q._tr_upper_prose = lambda text, names: (text or "").upper()

    r_true = q.qc_credit_block(
        ["Zeki Alasya"], ["Metin Akpinar", "Kemal Sunal", "Sener Sen"], [],
        title="Test", nonlatin_source=True,
    )
    # qc_credit_block dönüşünde gerekceler = düz string listesi (neden metinleri).
    assert r_true["karar"] == "KONTROL"
    assert any("Latin-dışı kaynak" in str(g) for g in r_true["gerekceler"])


def test_qc_gate_nonlatin_false_sessiz():
    import credit_qc_block as q
    q._upper_names = lambda names: [str(n).upper() for n in (names or [])]
    q._tr_upper_prose = lambda text, names: (text or "").upper()

    r_false = q.qc_credit_block(
        ["Zeki Alasya"], ["Metin Akpinar", "Kemal Sunal", "Sener Sen"], [],
        title="Test", nonlatin_source=False,
    )
    # nonlatin gate FİRE ETMEZ (başka gerekçe olabilir ama Latin-dışı gerekçesi YOK)
    assert not any("Latin-dışı kaynak" in str(g) for g in r_false["gerekceler"])


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
