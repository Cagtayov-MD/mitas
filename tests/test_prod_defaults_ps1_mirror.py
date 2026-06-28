# -*- coding: utf-8 -*-
"""test_prod_defaults_ps1_mirror.py — AYNA-INVARIANT testi.

Her start_mitas.ps1 $env:MITAS_xxx = "deger" satiri icin _PROD_DEFAULTS'ta
AYNI anahtar + AYNI degerin bulundugunu dogrular.

Kaynak okuma:
  - _PROD_DEFAULTS: mitas_pipeline.py'den AST ile (agir import YOK).
  - ps1: regex ile ($env:MITAS_xxx = 'deger' / "deger" satirlari).

MITAS_OCR_FORM_KEEP ps1'de YOKTUR → mirror-test'e dahil edilmez (expected).
"""
import ast
import os
import re
import textwrap

# ── Dosya yollari ─────────────────────────────────────────────────────────────
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PIPELINE  = os.path.join(_REPO_ROOT, "scripts", "mitas_pipeline.py")
_PS1       = os.path.join(_REPO_ROOT, "scripts", "start_mitas.ps1")


# ── Yardimci: _PROD_DEFAULTS literal'ini dosyadan ast ile cek ─────────────────
def _load_prod_defaults() -> dict:
    """mitas_pipeline.py'deki _PROD_DEFAULTS = {...} literalini ast ile okur.
    Import yapmaz; agir bagimliliklara dokunmaz."""
    with open(_PIPELINE, encoding="utf-8") as fh:
        src = fh.read()

    # AST parse; _PROD_DEFAULTS assign dugumunu bul
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_PROD_DEFAULTS":
                    # ast.literal_eval ile guvende deger al
                    return ast.literal_eval(node.value)
    raise RuntimeError("_PROD_DEFAULTS bulunamadi: " + _PIPELINE)


# ── Yardimci: ps1'deki $env:MITAS_xxx = 'deger' satirlarini parse et ─────────
_PS1_ENV_RE = re.compile(
    r'\$env:(MITAS_\w+)\s*=\s*["\']([^"\']*)["\']',
    re.IGNORECASE,
)


def _load_ps1_env() -> dict:
    """start_mitas.ps1'deki $env:MITAS_xxx atamalarini {anahtar: deger} dict'i olarak döner.
    Coklu atama varsa sonuncusu kazanir (ps1 davranisiyla tutarli)."""
    with open(_PS1, encoding="utf-8") as fh:
        content = fh.read()
    result: dict = {}
    for m in _PS1_ENV_RE.finditer(content):
        key   = m.group(1).upper()   # normalize: buyuk harf
        value = m.group(2)
        result[key] = value
    return result


# ── Test ──────────────────────────────────────────────────────────────────────
def test_prod_defaults_mirrors_ps1():
    """ps1'deki her MITAS_ atamasi _PROD_DEFAULTS'ta ayni degerle bulunmali."""
    prod  = _load_prod_defaults()
    ps1   = _load_ps1_env()

    # if() guard icindeki atamalar: ps1'de $env:X = 'v' seklinde yaziliyor;
    # regex onlari yakalar. if (-not $env:X) blogu disindaki raw atamalar da yakalanir.

    missing_keys   = []   # ps1'de var, prod'da yok
    value_mismatch = []   # ikisinde de var ama deger farkli

    for key, ps1_val in sorted(ps1.items()):
        if key not in prod:
            missing_keys.append((key, ps1_val))
        elif prod[key] != ps1_val:
            value_mismatch.append((key, ps1_val, prod[key]))

    # Hata mesaji olustur
    errors = []
    if missing_keys:
        lines = "\n".join(f"  {k} = '{v}' (ps1 degeri)" for k, v in missing_keys)
        errors.append(
            "ps1'de SET EDILEN ama _PROD_DEFAULTS'ta EKSIK anahtarlar:\n" + lines
        )
    if value_mismatch:
        lines = "\n".join(
            f"  {k}: ps1='{pv}' ama _PROD_DEFAULTS='{dv}'"
            for k, pv, dv in value_mismatch
        )
        errors.append(
            "_PROD_DEFAULTS degeri ps1 ile UYUSMUYOR:\n" + lines
        )

    assert not errors, "\n\n" + "\n\n".join(errors)


def test_ps1_has_expected_mirror_keys():
    """ps1'de varligini bekledigimiz 4 yeni anahtarin gercekten mevcut oldugunu kontrol et."""
    ps1 = _load_ps1_env()
    expected = {
        "MITAS_CAST_OCR_KEEP":    "1",
        "MITAS_CAST_CAP":         "10",
        "MITAS_QC_NONCAST_FILTER":"1",
        "MITAS_FRAME_DEDUP":      "0",
    }
    for key, val in expected.items():
        assert key in ps1, f"ps1'de beklenen anahtar YOK: {key}"
        assert ps1[key] == val, f"ps1[{key}] beklenen='{val}', bulunan='{ps1[key]}'"


def test_ocr_form_keep_not_in_ps1():
    """MITAS_OCR_FORM_KEEP ps1'de SET EDILMEMELI (A/B bekleniyor); durumu belgelemek icin."""
    ps1 = _load_ps1_env()
    assert "MITAS_OCR_FORM_KEEP" not in ps1, (
        "MITAS_OCR_FORM_KEEP ps1'e eklenmis — _PROD_DEFAULTS'a da ekle ve bu testi guncelle"
    )
