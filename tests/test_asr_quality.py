from __future__ import annotations

from core.pipelines.asr.quality import (
    QualityConfig,
    detect_repetition_collapse,
    detect_word_density_anomaly,
    evaluate_result_safety,
    evaluate_segment,
    is_stock_artifact,
)


class TestStockArtifact:
    def test_detects_youtube_outro(self) -> None:
        assert is_stock_artifact("İzlediğiniz için teşekkür ederim")[0]

    def test_detects_altyazi_mk(self) -> None:
        assert is_stock_artifact("Altyazı M.K.")[0]

    def test_case_insensitive(self) -> None:
        assert is_stock_artifact("ALTYAZI M.K.")[0]

    def test_real_content_passes(self) -> None:
        assert not is_stock_artifact("Tüm hazırlıklar tamamlandı")[0]

    def test_artifact_within_real_content(self) -> None:
        assert is_stock_artifact("İzlediğiniz için teşekkür ederim Angardan çıkan F-16")[0]


class TestRepetitionCollapse:
    def test_detects_ben_loop(self) -> None:
        text = "ben " * 50
        is_collapsed, max_run, token = detect_repetition_collapse(text, min_run=20)

        assert is_collapsed
        assert max_run >= 50
        assert token == "ben"

    def test_normal_text_passes(self) -> None:
        text = "Tüm hazırlıklar tamamlandı. F-16'lar havalandı."
        is_collapsed, _, _ = detect_repetition_collapse(text)

        assert not is_collapsed

    def test_short_repetition_passes(self) -> None:
        text = "Vallahi çok çok güzel söyledin"
        is_collapsed, _, _ = detect_repetition_collapse(text, min_run=20)

        assert not is_collapsed

    def test_detects_punctuation_tolerant_loop(self) -> None:
        text = "Ben, ben. BEN! " * 10
        is_collapsed, max_run, token = detect_repetition_collapse(text, min_run=20)

        assert is_collapsed
        assert max_run >= 30
        assert token == "Ben,"


class TestWordDensity:
    def test_detects_anomaly(self) -> None:
        is_anomalous, _ = detect_word_density_anomaly(685, 120.0)

        assert is_anomalous

    def test_normal_speech_passes(self) -> None:
        is_anomalous, _ = detect_word_density_anomaly(300, 120.0)

        assert not is_anomalous


class TestSegmentEvaluation:
    def test_drops_stock_artifact(self) -> None:
        decision = evaluate_segment(
            text="İzlediğiniz için teşekkür ederim",
            no_speech_prob=0.1,
            avg_logprob=-0.3,
            language="tr",
        )

        assert not decision.keep
        assert "stock_artifact" in str(decision.drop_reason)

    def test_keeps_low_no_speech_alone(self) -> None:
        decision = evaluate_segment(
            text="Evet ben söyledim",
            no_speech_prob=0.7,
            avg_logprob=-0.4,
            language="tr",
        )

        assert decision.keep
        assert "high_no_speech_prob" in decision.flags
        assert "low_confidence" in decision.flags

    def test_hard_drop_with_multiple_signals(self) -> None:
        decision = evaluate_segment(
            text="É",
            no_speech_prob=0.8,
            avg_logprob=-1.5,
            language="tr",
        )

        assert not decision.keep

    def test_drops_segment_repetition_collapse(self) -> None:
        decision = evaluate_segment(
            text="çıplak " * 54,
            no_speech_prob=0.1,
            avg_logprob=-0.2,
            language="tr",
        )

        assert not decision.keep
        assert "repetition_collapse" in str(decision.drop_reason)

    def test_drops_segment_long_token_artifact(self) -> None:
        long_token = "Hıhı" * 60
        decision = evaluate_segment(
            text=f"Normal cümle {long_token} devam",
            no_speech_prob=0.1,
            avg_logprob=-0.2,
            language="tr",
        )

        assert not decision.keep
        assert "long_token_artifact" in str(decision.drop_reason)

    def test_drops_very_low_logprob_short_text(self) -> None:
        decision = evaluate_segment(
            text="Ayy, de finiske öğret.",
            no_speech_prob=0.0,
            avg_logprob=-1.29,
            language="tr",
        )

        assert not decision.keep
        assert decision.drop_reason == "very_low_logprob_short_text"

    def test_keeps_low_logprob_longer_text_as_flagged(self) -> None:
        decision = evaluate_segment(
            text="Bu cümle biraz düşük güvenli ama uzun olduğu için kalsın",
            no_speech_prob=0.0,
            avg_logprob=-1.16,
            language="tr",
        )

        assert decision.keep
        assert "low_confidence" in decision.flags

    def test_keeps_good_quality(self) -> None:
        decision = evaluate_segment(
            text="Tüm hazırlıklar tamamlandı",
            no_speech_prob=0.05,
            avg_logprob=-0.2,
            language="tr",
        )

        assert decision.keep
        assert "low_confidence" not in decision.flags

    def test_can_flag_stock_artifact_without_dropping_when_configured(self) -> None:
        decision = evaluate_segment(
            text="Altyazı M.K.",
            no_speech_prob=0.1,
            avg_logprob=-0.2,
            language="tr",
            config=QualityConfig(drop_stock_artifacts=False),
        )

        assert decision.keep
        assert "stock_artifact" in decision.flags


class TestResultSafety:
    def test_detects_beyaz1_v11_disaster(self) -> None:
        text = "Normal başlangıç. " + "ben " * 444 + " Normal devam."
        decision = evaluate_result_safety(
            transcript_text=text,
            word_count=len(text.split()),
            speech_seconds=120.0,
        )

        assert not decision.safe
        assert "repetition_collapse" in str(decision.failure_reason)

    def test_detects_hihihi_token(self) -> None:
        long_token = "Hıhı" * 60
        text = f"Normal cümle {long_token} devam."
        decision = evaluate_result_safety(
            transcript_text=text,
            word_count=10,
            speech_seconds=30.0,
        )

        assert not decision.safe
        assert "long_token" in str(decision.failure_reason)

    def test_clean_result_passes(self) -> None:
        text = "Tüm hazırlıklar tamamlandı. F-16'lar Eskişehir'den havalandı."
        decision = evaluate_result_safety(
            transcript_text=text,
            word_count=8,
            speech_seconds=4.0,
        )

        assert decision.safe
