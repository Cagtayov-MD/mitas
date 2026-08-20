"""Zincirin Nash'i Kobe havuzundan bağımsız çağırdığına dair dar regresyon."""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path


ZINCIR = Path(__file__).resolve().parents[2] / "zincir_kos.py"
spec = importlib.util.spec_from_file_location("zincir_kos_test", ZINCIR)
zincir_kos = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(zincir_kos)


def _hazirla(monkeypatch, tmp_path, havuz_var: bool):
    ana = tmp_path / "sheriff" / "output" / "F1" / "cikis"
    ana.mkdir(parents=True)
    (ana / "ana.png").write_bytes(b"x")
    monkeypatch.setattr(zincir_kos, "KOK", tmp_path)
    monkeypatch.setattr(zincir_kos, "KARE_KOK", tmp_path / "sheriff" / "output")
    monkeypatch.setattr(zincir_kos, "video_bul", lambda _film: None)
    if havuz_var:
        havuz = tmp_path / "kobe" / "out" / "F1" / "cikis" / "kareler"
        havuz.mkdir(parents=True)
        (havuz / "dar.png").write_bytes(b"x")
    calls = []

    def kos(kule, argv, *_args):
        calls.append((kule, argv))
        return {"ok": True, "durum": "METIN_YOK"}

    monkeypatch.setattr(zincir_kos, "kos", kos)
    return ana, calls


def test_kobe_havuzu_yokken_nash_ana_karelerde_bir_kez_calisir(monkeypatch, tmp_path):
    ana, calls = _hazirla(monkeypatch, tmp_path, havuz_var=False)
    sonuc = zincir_kos.bolum_isle("F1", "cikis", io.StringIO(), False)
    nash = [argv for kule, argv in calls if kule == "nash"]
    assert len(nash) == 1
    assert nash[0][nash[0].index("--kareler") + 1] == str(ana)
    assert not any(kule == "lebron_james" for kule, _ in calls)
    assert "nash" in sonuc


def test_kobe_havuzu_yokken_atlanmis_nash_logda_calisti_denmez(monkeypatch, tmp_path):
    _ana, calls = _hazirla(monkeypatch, tmp_path, havuz_var=False)
    monkeypatch.setattr(zincir_kos, "tamam_mi",
                        lambda kule, *_args: kule == "nash")
    logf = io.StringIO()
    sonuc = zincir_kos.bolum_isle("F1", "cikis", logf, True)
    assert sonuc["nash"]["durum"] == "ATLANDI"
    assert not any(kule == "nash" for kule, _ in calls)
    assert "nash bagimsiz ele alindi (ATLANDI)" in logf.getvalue()


def test_kobe_havuzu_varken_nash_ikinci_kez_cagrilmaz(monkeypatch, tmp_path):
    ana, calls = _hazirla(monkeypatch, tmp_path, havuz_var=True)
    zincir_kos.bolum_isle("F1", "cikis", io.StringIO(), False)
    nash = [argv for kule, argv in calls if kule == "nash"]
    assert len(nash) == 1
    assert nash[0][nash[0].index("--kareler") + 1] == str(ana)
