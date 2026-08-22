import pytest
from app.features.lifecycle_features import account_age_days_observed, dormancy_breaks


class TestLifecycleFeatures:
    def test_account_age(self, sample_transactions_df):
        value, formula, explanation = account_age_days_observed(sample_transactions_df)
        assert value is not None
        assert value == 4  # Jan 1 to Jan 5 = 4 days

    def test_dormancy_no_breaks(self, sample_transactions_df):
        value, formula, explanation = dormancy_breaks(sample_transactions_df)
        assert value == 0

    def test_empty_df(self):
        import pandas as pd
        value, _, _ = account_age_days_observed(pd.DataFrame())
        assert value is None
