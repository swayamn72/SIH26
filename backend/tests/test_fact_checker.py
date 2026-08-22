import pytest
from app.llm.fact_checker import fact_check_output, _check_banned_terms


class TestFactChecker:
    def test_valid_numbers_pass(self):
        text = "The account has a score of 74.5 and 3 cycles detected."
        evidence = '{"fused_score": 74.5, "cycle_count": 3}'
        assert fact_check_output(text, evidence) is True

    def test_invented_number_fails(self):
        text = "The account has a score of 99.9."
        evidence = '{"fused_score": 50.0}'
        assert fact_check_output(text, evidence) is False

    def test_banned_terms_caught(self):
        assert _check_banned_terms("this account is guilty of fraud") == "guilty"
        assert _check_banned_terms("money laundering confirmed in this case") == "money laundering confirmed"
        assert _check_banned_terms("legitimate pattern observed") is None
