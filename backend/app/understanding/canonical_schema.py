from datetime import date, datetime
from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, Field



class CanonicalTransaction(BaseModel):
    row_id: str
    txn_date: date
    value_date: Optional[date] = None
    narration: str = ""
    reference_no: Optional[str] = None
    debit_amount: Optional[Decimal] = None
    credit_amount: Optional[Decimal] = None
    balance_after: Optional[Decimal] = None
    channel: Optional[str] = None
    counterparty_raw: Optional[str] = None
    source_row_confidence: float = 1.0


