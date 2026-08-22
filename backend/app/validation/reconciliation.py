from datetime import date
from typing import Optional
from decimal import Decimal

from app.understanding.canonical_schema import CanonicalTransaction
from app.config_loader import load_config


def reconcile_transactions(
    transactions: list[CanonicalTransaction],
) -> tuple[float, list[bool], Optional[float]]:
    if not transactions:
        return 1.0, [], None

    cfg = load_config("thresholds")
    tolerance = Decimal(str(cfg.get("reconciliation", {}).get("tolerance", 0.01)))

    def _sort_key(t: CanonicalTransaction):
        parts = str(t.row_id).split("-")
        row_num = int(parts[-1]) if parts[-1].isdigit() else 0
        return (t.txn_date or date.min, row_num)

    sorted_txns = sorted(transactions, key=_sort_key)
    has_balance = any(t.balance_after is not None for t in sorted_txns)

    if not has_balance:
        total_debit = sum((t.debit_amount or Decimal(0)) for t in sorted_txns)
        total_credit = sum((t.credit_amount or Decimal(0)) for t in sorted_txns)
        if total_debit == 0 and total_credit == 0:
            return 1.0, [True] * len(sorted_txns), None
        net_delta = abs(total_credit - total_debit)
        max_flow = max(abs(total_credit), abs(total_debit))
        if max_flow == 0:
            return 1.0, [True] * len(sorted_txns), None
        rate = 1.0 - float(net_delta / max_flow)
        return max(rate, 0.0), [True] * len(sorted_txns), None

    reconciled: list[bool] = []
    prev_balance: Optional[Decimal] = None
    reconciled_count = 0
    balance_row_count = 0

    for txn in sorted_txns:
        if txn.balance_after is not None:
            balance_row_count += 1
            if prev_balance is not None:
                expected = prev_balance - (txn.debit_amount or Decimal(0)) + (txn.credit_amount or Decimal(0))
                diff = abs(expected - txn.balance_after)
                is_rec = diff <= tolerance
                reconciled.append(is_rec)
                if is_rec:
                    reconciled_count += 1
            else:
                reconciled.append(True)
                reconciled_count += 1
            prev_balance = txn.balance_after
        else:
            reconciled.append(True)

    rate = reconciled_count / max(balance_row_count, 1)
    return float(rate), reconciled, None
