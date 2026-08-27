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
    # The lines above the transaction header — bank name, holder, the account's own
    # IFSC. The extractor discards them, so they are captured separately at upload.
    raw_preamble: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    bank_code: Optional[str] = Field(default=None, max_length=16, index=True)
    bank_name: Optional[str] = Field(default=None, max_length=255)
    bank_code_source: Optional[str] = Field(default=None, max_length=32)


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


class Case(SQLModel, table=True):
    """A persisted investigation containing a selected set of confirmed statements."""

    __tablename__ = "cases"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, max_length=2048)
    created_ts: datetime = Field(default_factory=datetime.utcnow)
    analyzed_ts: Optional[datetime] = None
    analysis_version: int = 0


class CaseStatement(SQLModel, table=True):
    __tablename__ = "case_statements"
    case_id: int = Field(foreign_key="cases.id", primary_key=True)
    statement_id: int = Field(foreign_key="statements.id", primary_key=True)
    added_ts: datetime = Field(default_factory=datetime.utcnow)


class CaseAccountNode(SQLModel, table=True):
    __tablename__ = "case_account_nodes"
    id: str = Field(primary_key=True, max_length=64)
    case_id: int = Field(foreign_key="cases.id", index=True)
    kind: str = Field(max_length=48)
    label: str = Field(max_length=255)
    institution: Optional[str] = Field(default=None, max_length=255)
    subject_statement_id: Optional[int] = Field(default=None, foreign_key="statements.id")
    evidence: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))


class CaseTransferEdge(SQLModel, table=True):
    __tablename__ = "case_transfer_edges"
    id: str = Field(primary_key=True, max_length=64)
    case_id: int = Field(foreign_key="cases.id", index=True)
    source_node_id: str = Field(max_length=64, index=True)
    target_node_id: str = Field(max_length=64, index=True)
    amount: float
    txn_date: date = Field(index=True)
    reference_fingerprint: Optional[str] = Field(default=None, max_length=64)
    source_statement_ids: list[int] = Field(default=[], sa_column=Column(JSON))
    source_row_ids: list[str] = Field(default=[], sa_column=Column(JSON))
    direction: str = Field(default="outgoing_transfer", max_length=32)
    resolution_method: str = Field(default="unresolved_name_not_merged", max_length=64)
    evidence: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))


class CaseFinding(SQLModel, table=True):
    __tablename__ = "case_findings"
    id: str = Field(primary_key=True, max_length=64)
    case_id: int = Field(foreign_key="cases.id", index=True)
    kind: str = Field(max_length=64)
    risk_score: float = 0.0
    hop_count: int = 0
    node_sequence: list[str] = Field(default=[], sa_column=Column(JSON))
    edge_ids: list[str] = Field(default=[], sa_column=Column(JSON))
    source_row_ids: list[str] = Field(default=[], sa_column=Column(JSON))
    source_statement_ids: list[int] = Field(default=[], sa_column=Column(JSON))
    detail: dict[str, Any] = Field(sa_column=Column(JSON))
    created_ts: datetime = Field(default_factory=datetime.utcnow)


class TransferDataset(SQLModel, table=True):
    """An ingested interbank transfer ledger (e.g. an AML transaction network export).

    Distinct from Statement: a statement is one account's history, a dataset is a
    multi-party ledger where every row names both institutions.
    """

    __tablename__ = "transfer_datasets"
    id: Optional[int] = Field(default=None, primary_key=True)
    original_filename: Optional[str] = Field(default=None, max_length=512)
    upload_ts: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="ingested", max_length=32)
    row_count: int = 0
    rows_skipped: int = 0
    truncated: bool = False
    bank_count: int = 0
    account_count: int = 0
    total_value: float = 0.0
    observed_start: Optional[datetime] = None
    observed_end: Optional[datetime] = None
    has_labels: bool = False
    detected_column_mapping: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    currencies: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    payment_formats: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    # Circular fund flows found between accounts in this ledger. Kept here rather
    # than in `cycles` because those rows are shaped for single-statement analysis.
    flow_cycles: Optional[list[dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))


class Bank(SQLModel, table=True):
    """An institution seen in a transfer dataset — a stable node in the bank graph."""

    __tablename__ = "banks"
    id: Optional[int] = Field(default=None, primary_key=True)
    dataset_id: int = Field(foreign_key="transfer_datasets.id", index=True)
    bank_code: str = Field(max_length=64, index=True)
    display_name: str = Field(max_length=255)


class InterbankTransfer(SQLModel, table=True):
    __tablename__ = "interbank_transfers"
    id: Optional[int] = Field(default=None, primary_key=True)
    dataset_id: int = Field(foreign_key="transfer_datasets.id", index=True)
    txn_ts: Optional[datetime] = Field(default=None, index=True)
    from_bank: str = Field(max_length=64, index=True)
    from_account: Optional[str] = Field(default=None, max_length=64)
    to_bank: str = Field(max_length=64, index=True)
    to_account: Optional[str] = Field(default=None, max_length=64)
    amount_paid: float = 0.0
    payment_currency: Optional[str] = Field(default=None, max_length=16)
    amount_received: float = 0.0
    receiving_currency: Optional[str] = Field(default=None, max_length=16)
    payment_format: Optional[str] = Field(default=None, max_length=32)
    is_labelled_laundering: bool = False


class BankEdge(SQLModel, table=True):
    """Aggregated bank -> bank flow, so the network view never re-scans the ledger."""

    __tablename__ = "bank_edges"
    id: Optional[int] = Field(default=None, primary_key=True)
    dataset_id: int = Field(foreign_key="transfer_datasets.id", index=True)
    from_bank: str = Field(max_length=64, index=True)
    to_bank: str = Field(max_length=64, index=True)
    transfer_count: int = 0
    total_amount: float = 0.0
    labelled_laundering_count: int = 0


class BankProfileRecord(SQLModel, table=True):
    """Pre-computed behavioural profile for one bank in one dataset."""

    __tablename__ = "bank_profiles"
    id: Optional[int] = Field(default=None, primary_key=True)
    dataset_id: int = Field(foreign_key="transfer_datasets.id", index=True)
    bank_code: str = Field(max_length=64, index=True)
    risk_score: float = 0.0
    risk_tier: str = Field(default="LOW", max_length=16)
    transfer_count: int = 0
    total_received: float = 0.0
    total_sent: float = 0.0
    connected_banks: int = 0
    avg_transfer: float = 0.0
    json_blob: dict[str, Any] = Field(sa_column=Column(JSON))


class ConfigAuditLog(SQLModel, table=True):
    __tablename__ = "config_audit_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    changed_by: str = Field(max_length=128)
    config_key: str = Field(max_length=255)
    old_value: Optional[str] = Field(default=None, sa_column=Column(Text))
    new_value: Optional[str] = Field(default=None, sa_column=Column(Text))
    change_ts: datetime = Field(default_factory=datetime.utcnow)
