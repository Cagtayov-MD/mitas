"""_generate_ozet_v2 kapalı-döngü karar mantığı — sahte sağlayıcılarla (ağ yok).

Kalite kapısı/onarımın kendisi test_ozet_kalite.py'de sabitli; burada DÖNGÜ davranışı test edilir:
öz-düzeltme (feedback ile tekrar), spoiler-final tercihi, finalsiz-geçerli yedeği, kapı-reddi →
placeholder (None), boş sağlayıcıyı atlama.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))
mp = pytest.importorskip("mitas_pipeline")

# mitas_pipeline import-anında PROJECT_ROOT'u env-aware çözer (MITAS_PROJECT_ROOT yoksa Windows
# fallback E:\MITAS). Bare pytest bu env'i yüklemez → prompt yolları prod-dışı. Giriş testleri
# gerçek prompt dosyalarını okuduğundan, o yolları bu repodaki dosyalara sabitliyoruz (env-bağımsız).
_PROMPTS = _REPO / "core" / "api" / "prompts"


# 39 kelime, spoiler final (finalde + feda eder) — kapıyı geçer.
VALID = (
    "İşgal altındaki Fransa'da idama mahkum Jean Picard bombardımanda kaçar ama müfettiş "
    "Bonet tarafından yakalanır. Almanlar teslim olmazsa yüz rehineyi öldüreceğini duyurunca "
    "Jean kararını değiştirir. Kasabada tanıştığı Marianne'e olan aşkı onu dönüştürür ve "
    "finalde sahte sabotajcı olarak kendini feda eder."
)

# 38 kelime, kapıyı geçer ama SON cümlede outcome-fiil/final-ipucu YOK → spoiler-final değil.
FINALLESS = (
    "Genç öğretmen Deniz, uzak bir dağ köyüne tayin olur ve orada yeni bir sınıf açar. "
    "Köylüler önce ona mesafeli davranır ama zamanla ısınır. Deniz her sabah çocuklarla "
    "birlikte uzun yollar yürüyerek okula ulaşmaya çalışır ve akşamları kitap okur."
)


def _fixed(out):
    return lambda system_content, user_msg: out


def test_v2_returns_spoiler_final_immediately() -> None:
    assert mp._generate_ozet_v2("s", "u", [("a", _fixed(VALID))], 1) == VALID


def test_v2_rejects_all_bad_returns_none() -> None:
    # "Çok kısa." kısa-format kapısını geçemez → tüm denemeler başarısız → placeholder (None).
    assert mp._generate_ozet_v2("s", "u", [("a", _fixed("Çok kısa."))], 1) is None


def test_v2_self_corrects_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MITAS_OZET_V2_ATTEMPTS", "3")
    calls = {"n": 0}

    def flaky(system_content, user_msg):
        calls["n"] += 1
        return "Kısa ve yetersiz özet." if calls["n"] < 3 else VALID

    assert mp._generate_ozet_v2("s", "u", [("a", flaky)], 1) == VALID
    assert calls["n"] == 3  # iki başarısız + bir başarılı deneme


def test_v2_prefers_spoiler_over_finalless() -> None:
    chain = [("a", _fixed(FINALLESS)), ("b", _fixed(VALID))]
    assert mp._generate_ozet_v2("s", "u", chain, 1) == VALID


def test_v2_falls_back_to_finalless_best() -> None:
    assert mp._generate_ozet_v2("s", "u", [("a", _fixed(FINALLESS))], 1) == FINALLESS


def test_v2_skips_empty_provider() -> None:
    chain = [("a", _fixed("")), ("b", _fixed(VALID))]
    assert mp._generate_ozet_v2("s", "u", chain, 1) == VALID


def test_v2_entrypoint_routes_and_reads_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """MITAS_OZET_V2=1 → _generate_ozet gerçek v2 prompt dosyasını okuyup v2 döngüsüne yönlendirmeli."""
    monkeypatch.setenv("MITAS_OZET_V2", "1")
    monkeypatch.setattr(mp, "OZET_PROMPT_V2_PATH", _PROMPTS / "ozet_film_v2.txt")
    monkeypatch.setattr(mp, "_ozet_chain", lambda: [("fake", _fixed(VALID))])
    got = mp._generate_ozet("bir film transkripti metni. " * 20, title="Deneme", duration="01:30:00")
    assert got == VALID


def test_legacy_path_unchanged_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag kapalıyken eski davranış: ilk boş-olmayan çıktı körlemesine kabul (kapı YOK)."""
    monkeypatch.delenv("MITAS_OZET_V2", raising=False)
    monkeypatch.setattr(mp, "OZET_PROMPT_PATH", _PROMPTS / "ozet_film.txt")
    # Kapıyı geçemeyecek kısa çıktı bile legacy'de aynen döner (kapı devrede değil).
    monkeypatch.setattr(mp, "_ozet_chain", lambda: [("fake", _fixed("Çok kısa özet."))])
    got = mp._generate_ozet("transkript. " * 20, title="Deneme", duration="01:00:00")
    assert got == "Çok kısa özet."
