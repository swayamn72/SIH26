import pytest
from app.guardrails.ood_detector import (
    compute_statement_likelihood,
    classify_ood_tier,
)


class TestOODDetector:
    def test_high_confidence_statement(self, sample_csv_rows, sample_ood_text):
        rows = sample_csv_rows[1:]
        score, signals = compute_statement_likelihood(rows, sample_ood_text, len(rows))
        tier = classify_ood_tier(score, signals)
        assert score >= 0.7
        assert tier == "auto_proceed"

    def test_low_row_count_rejected(self):
        rows = [["a", "b"]]
        score, signals = compute_statement_likelihood(rows, "", 2)
        tier = classify_ood_tier(score, signals)
        assert score < 0.4 or tier == "hard_reject"

    def test_ood_signals_all_present(self, sample_csv_rows, sample_ood_text):
        rows = sample_csv_rows[1:]
        _, signals = compute_statement_likelihood(rows, sample_ood_text, len(rows))
        date_signal = signals.get("has_date_column", 0)
        bank_signal = signals.get("has_bank_identity_markers", 0)
        assert date_signal > 0
        assert bank_signal > 0
