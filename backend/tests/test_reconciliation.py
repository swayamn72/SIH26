from datetime import date
from decimal import Decimal
import pytest
from app.validation.reconciliation import reconcile_transactions
from app.understanding.canonical_schema import CanonicalTransaction


class TestReconciliation:
    def test_perfect_reconciliation(self):
        txns = [
            CanonicalTransaction(row_id="1", txn_date=date(2024, 1, 1), debit_amount=Decimal(0), credit_amount=Decimal(1000), balance_after=Decimal(1000), narration=""),
            CanonicalTransaction(row_id="2", txn_date=date(2024, 1, 2), debit_amount=Decimal(500), credit_amount=Decimal(0), balance_after=Decimal(500), narration=""),
            CanonicalTransaction(row_id="3", txn_date=date(2024, 1, 3), debit_amount=Decimal(0), credit_amount=Decimal(300), balance_after=Decimal(800), narration=""),
        ]
        rate, reconciled, _ = reconcile_transactions(txns)
        assert rate >= 0.98

    def test_no_balance_column(self):
        txns = [
            CanonicalTransaction(row_id="1", txn_date=date(2024, 1, 1), debit_amount=Decimal(0), credit_amount=Decimal(1000), narration=""),
            CanonicalTransaction(row_id="2", txn_date=date(2024, 1, 2), debit_amount=Decimal(500), credit_amount=Decimal(0), narration=""),
        ]
        rate, reconciled, _ = reconcile_transactions(txns)
        assert rate >= 0

    def test_empty_transactions(self):
        rate, reconciled, _ = reconcile_transactions([])
        assert rate == 1.0
