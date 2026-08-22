from datetime import datetime, date
from typing import Optional, Any

from sqlmodel import SQLModel, Field, Column, JSON, Text


class Statement(SQLModel, table=True):
    __tablename__ = "statements"
    id: Optional[int] = Field(default=None, primary_key=True)
    filename_hash: str = Field(max_length=64, index=True)
    original_filename: Optional[str] = Field(default=None, max_length=512)
    upload_ts: datetime = Field(default_factory=datetime.utcnow)
    ood_score: Optional[float] = None
    ood_signals: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    reconciliation_rate: Optional[float] = None
    extraction_confidence: Optional[float] = None
    template_id_used: Optional[str] = Field(default=None, max_length=64)
    manual_mapping_used: bool = False
    status: str = Field(default="uploaded", max_length=32)
    transaction_count: Optional[int] = None
    observed_start: Optional[date] = None
    observed_end: Optional[date] = None
    account_holder: Optional[str] = Field(default=None, max_length=255)
    account_number_hashed: Optional[str] = Field(default=None, max_length=128)
    raw_headers: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    raw_rows: Optional[list[list[str]]] = Field(default=None, sa_column=Column(JSON))


class Counterparty(SQLModel, table=True):
    __tablename__ = "counterparties"
    id: Optional[int] = Field(default=None, primary_key=True)
    canonical_name: str = Field(max_length=255, index=True)
    raw_variants: list[str] = Field(default=[], sa_column=Column(JSON))
    is_self_transfer: bool = False
    first_seen_statement_id: Optional[int] = Field(default=None, foreign_key="statements.id")


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    row_id: str = Field(primary_key=True, max_length=64)
    statement_id: int = Field(foreign_key="statements.id", index=True)
    txn_date: date
    value_date: Optional[date] = None
    narration: str = Field(default="", max_length=2048)
    reference_no: Optional[str] = Field(default=None, max_length=128)
    debit_amount: Optional[float] = None
    credit_amount: Optional[float] = None
    balance_after: Optional[float] = None
    channel: Optional[str] = Field(default=None, max_length=32)
    category: Optional[str] = Field(default=None, max_length=64)
    counterparty_id: Optional[int] = Field(default=None, foreign_key="counterparties.id")
    row_confidence: float = 1.0
    is_reconciled: bool = False
    tagged_rules: list[str] = Field(default=[], sa_column=Column(JSON))
    tagged_cycles: list[str] = Field(default=[], sa_column=Column(JSON))


class EvidenceBundleRecord(SQLModel, table=True):
    __tablename__ = "evidence_bundles"
    id: Optional[int] = Field(default=None, primary_key=True)
    statement_id: int = Field(foreign_key="statements.id", index=True)
    json_blob: dict[str, Any] = Field(sa_column=Column(JSON))
    created_ts: datetime = Field(default_factory=datetime.utcnow)
    score_version: str = Field(default="0.1.0", max_length=32)


class Cycle(SQLModel, table=True):
    __tablename__ = "cycles"
    id: Optional[int] = Field(default=None, primary_key=True)
    statement_id: Optional[int] = Field(default=None, foreign_key="statements.id")
    batch_id: Optional[int] = Field(default=None)
    node_sequence: list[str] = Field(sa_column=Column(JSON))
    hop_count: int = 0
    amount_conservation_ratio: Optional[float] = None
    cycle_risk_score: Optional[float] = None
    cycle_span_days: Optional[float] = None
    contributing_row_ids: list[str] = Field(default=[], sa_column=Column(JSON))


class InvestigatorLabel(SQLModel, table=True):
    __tablename__ = "investigator_labels"
    id: Optional[int] = Field(default=None, primary_key=True)
    statement_id: int = Field(foreign_key="statements.id", index=True)
    confirmed_outcome: str = Field(max_length=32)
    notes: Optional[str] = Field(default=None, max_length=4096)
    labeled_ts: datetime = Field(default_factory=datetime.utcnow)


class ConfigAuditLog(SQLModel, table=True):
    __tablename__ = "config_audit_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    changed_by: str = Field(max_length=128)
    config_key: str = Field(max_length=255)
    old_value: Optional[str] = Field(default=None, sa_column=Column(Text))
    new_value: Optional[str] = Field(default=None, sa_column=Column(Text))
    change_ts: datetime = Field(default_factory=datetime.utcnow)
