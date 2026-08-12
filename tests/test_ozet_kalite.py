"""Golden testler: _ozet_kalite (testas özet kalite kapısı + onarım portu).

Amaç testas'ın summary_errors/repair davranışını MITAS'ta BİREBİR sabitlemek — port
sırasında bir regresyon olursa burada patlasın. Modül scripts/ altında ve bir paket
değil; doğrudan dosya-yolu ile yüklenir (mitas_pipeline._load_sibling ile aynı desen).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_MOD = Path(__file__).resolve().parents[1] / "scripts" / "_ozet_kalite.py"
_spec = importlib.util.spec_from_file_location("_ozet_kalite", _MOD)
oq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oq)


# 39 kelime, tek paragraf, noktalı-virgül yok, '.' ile biter, spoiler final (finalde + feda eder).
VALID = (
    "İşgal altındaki Fransa'da idama mahkum Jean Picard bombardımanda kaçar ama müfettiş "
    "Bonet tarafından yakalanır. Almanlar teslim olmazsa yüz rehineyi öldüreceğini duyurunca "
    "Jean kararını değiştirir. Kasabada tanıştığı Marianne'e olan aşkı onu dönüştürür ve "
    "finalde sahte sabotajcı olarak kendini feda eder."
)

# 29 kelime, 3 tam cümle, spoiler final → kısa-format (24-31) kapısını geçmeli.
CONCISE = (
    "Genç doktor Ali, memleketindeki ölümcül salgınla mücadele etmek için büyük şehirden "
    "köyüne geri döner. Batıl inançlı halkı ikna edemeyince tek başına savaşır. Finalde "
    "aşıyı yetiştirir ve köyü salgından kurtarır."
)


# ── Kelime sayımı ─────────────────────────────────────────────────────────────
def test_word_count_apostrophe_is_one_word() -> None:
    assert oq.summary_word_count("Ali'nin üç kitabı var.") == 4


def test_valid_word_count_in_range() -> None:
    assert oq.SUMMARY_WORD_MIN <= oq.summary_word_count(VALID) <= oq.SUMMARY_WORD_LIMIT


# ── Kalite kapısı: geçerli ────────────────────────────────────────────────────
def test_valid_summary_passes_gate() -> None:
    assert oq.summary_errors(VALID) == []


def test_concise_complete_passes_gate() -> None:
    assert 24 <= oq.summary_word_count(CONCISE) < 32
    assert oq.summary_errors(CONCISE) == []


# ── Kalite kapısı: red ────────────────────────────────────────────────────────
def test_gate_rejects_semicolon() -> None:
    errs = oq.summary_errors("Ali köye döner; salgınla savaşır ve finalde herkesi kurtarır.")
    assert any("noktalı virgül" in e for e in errs)


def test_gate_rejects_over_limit() -> None:
    long = VALID + " " + VALID
    errs = oq.summary_errors(long)
    assert any(str(oq.SUMMARY_WORD_LIMIT) in e and "sınırını aşıyor" in e for e in errs)


def test_gate_rejects_no_terminal_punctuation() -> None:
    errs = oq.summary_errors("Ali köye döner ve halkı iyileştirmeye çalışır ama başaramaz gibi görünür")
    assert any("noktalama ile bitmiyor" in e for e in errs)


def test_gate_rejects_bad_filler_pattern() -> None:
    text = (
        "Ali'nin hikayesi derin bir yolculuk sunar ve izleyiciyi içine çeker, karakterler "
        "büyür ve sonunda her şey bambaşka bir hâl alır ve seyirci etkilenir."
    )
    errs = oq.summary_errors(text)
    assert any("DERIN BIR YOLCULUK" in e for e in errs)


def test_gate_rejects_too_short_non_concise() -> None:
    errs = oq.summary_errors("Ali köye döner.")
    assert any("kısa-format" in e for e in errs)


def test_gate_rejects_empty() -> None:
    assert any("boş" in e for e in oq.summary_errors("   "))


# ── has_spoiler_final ─────────────────────────────────────────────────────────
def test_has_spoiler_final_true() -> None:
    assert oq.has_spoiler_final(VALID) is True


def test_has_spoiler_final_false_for_plain_sentence() -> None:
    assert oq.has_spoiler_final("Bahçede kuşlar sabahları neşeyle şakır.") is False


# ── Onarım ────────────────────────────────────────────────────────────────────
def test_repair_converts_semicolon_to_period() -> None:
    fixed = oq.repair_generated_summary("Ali köye döner; sonra kasabaya gider ve yerleşir.")
    assert ";" not in fixed


def test_repair_drops_truncated_last_sentence() -> None:
    truncated = VALID + " Ayrıca köye dönüp uzun bir süre orada kalmayı"
    fixed = oq.repair_generated_summary(truncated)
    assert fixed.endswith(".")
    assert "kalmayı" not in fixed


def test_repair_enforces_word_limit() -> None:
    long = VALID + " " + VALID
    assert oq.summary_word_count(oq.repair_generated_summary(long)) <= oq.SUMMARY_WORD_LIMIT


def test_repair_prepends_finalde_for_outcome_final() -> None:
    # Son cümlede outcome-fiil (kazanır) var ama 'finalde/sonunda' ipucu yok → onarım öneki ekler.
    fixed = oq.repair_generated_summary("Ekip uzun uğraşın ardından hedefe ulaşır. Kahraman düşmanı yener.")
    assert oq.canonical(fixed).__contains__("FINALDE")


def test_strip_summary_output_removes_think_and_label() -> None:
    assert oq.strip_summary_output("<think>planlıyorum</think> Özet: Merhaba dünya.") == "Merhaba dünya."
