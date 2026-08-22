import os
import sys
from datetime import date, timedelta
from pathlib import Path
from decimal import Decimal

import pytest
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))


@pytest.fixture
def sample_transactions_df():
    data = {
        "txn_date": [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 5)],
        "debit_amount": [Decimal("0"), Decimal("500"), Decimal("0"), Decimal("200"), Decimal("0")],
        "credit_amount": [Decimal("1000"), Decimal("0"), Decimal("300"), Decimal("0"), Decimal("100")],
        "balance_after": [Decimal("1000"), Decimal("500"), Decimal("800"), Decimal("600"), Decimal("700")],
        "narration": ["Salary credit", "ATM withdrawal", "UPI payment", "NEFT transfer", "Interest"],
        "counterparty_id": [1, None, 3, 4, None],
        "row_id": ["stmt1-0", "stmt1-1", "stmt1-2", "stmt1-3", "stmt1-4"],
        "channel": ["NEFT", "ATM", "UPI", "NEFT", "INTEREST"],
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_csv_rows():
    return [
        ["Date", "Narration", "Withdrawal", "Deposit", "Balance"],
        ["01/01/2024", "Salary credit", "", "50000", "50000"],
        ["02/01/2024", "ATM withdrawal", "2000", "", "48000"],
        ["03/01/2024", "UPI payment", "1500", "", "46500"],
        ["04/01/2024", "NEFT transfer", "", "10000", "56500"],
    ]


@pytest.fixture
def sample_ood_text():
    return """Statement of Account
    Account Holder: Test User
    IFSC: SBIN0001234
    Date: 01/01/2024
    Narration: Salary
    Debit: 1000
    Credit: 2000
    Balance: 3000"""
