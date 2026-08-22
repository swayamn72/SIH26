import logging
from decimal import Decimal
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.categorization.counterparty_extractor import extract_counterparty
from app.categorization.rule_engine import assign_category, infer_channel
from app.db.models import (
    Counterparty,
    Cycle,
    EvidenceBundleRecord,
    Statement,
    Transaction,
)
from app.db.session import get_session
from app.evidence.evidence_bundle import (
    assemble_evidence_bundle,
    evidence_bundle_to_json,
)
from app.features.feature_registry import compute_all_features
from app.graph.cycle_detector import detect_cycles
from app.graph.graph_builder import build_transaction_graph, graph_to_json
from app.scoring.anomaly_scorer import (
    compute_isolation_forest_anomaly,
    compute_mad_anomaly,
)
from app.scoring.decision_policy import decide_tier
from app.scoring.fusion import fuse_scores
from app.scoring.rule_scorer import evaluate_rules
from app.scoring.supervised_scorer import SupervisedScorer
from app.understanding.canonical_schema import CanonicalTransaction
from app.understanding.column_mapper import map_row_to_transaction
from app.validation.manual_mapping_api import save_user_template
from app.validation.quality_score import (
    classify_extraction_confidence,
    compute_row_confidence,
)
from app.validation.reconciliation import reconcile_transactions

logger = logging.getLogger(__name__)

router = APIRouter()

# Loaded once at import time (reads app/ml/artifacts/*). If no model has
# been trained yet, `supervised_scorer.available` is False and scoring
# below transparently falls back to rule_score + anomaly_score only.
supervised_scorer = SupervisedScorer()


class MappingOverrideIn(BaseModel):
    # Keys are column header names (as shown in the UI) mapped to canonical
    # field names. The backend converts these to integer column indices
    # internally using the stored raw_headers.
    column_mapping: dict[str, str]
    save_as_template: bool = False
    headers: list[str] | None = None
    raw_rows: list[list[str]] | None = None


class MappingOut(BaseModel):
    statement_id: int
    column_mapping: dict[str, str]
    transaction_count: int
    message: str


class PreviewOut(BaseModel):
    statement_id: int
    original_filename: str | None
    status: str
    ood_score: float | None
    ood_signals: dict | None
    reconciliation_rate: float | None
    extraction_confidence: float | None
    transaction_count: int | None
    observed_start: str | None
    observed_end: str | None
    detected_column_mapping: dict[str, Any]
    transactions: list[dict[str, Any]]


class ConfirmOut(BaseModel):
    statement_id: int
    status: str
    tier: str
    fused_score: float
    score_formula: str
    reconciliation_rate: float
    extraction_confidence: str
    triggered_rules: list[dict[str, Any]]
    feature_count: int
    cycle_count: int


def _load_statement_or_404(db: Session, statement_id: int) -> Statement:
    stmt = db.get(Statement, statement_id)
    if stmt is None:
        raise HTTPException(
            status_code=404, detail=f"Statement {statement_id} not found"
        )
    return stmt


def _transactions_to_canonical(txns: list[Transaction]) -> list[CanonicalTransaction]:
    result: list[CanonicalTransaction] = []
    for t in txns:
        result.append(
            CanonicalTransaction(
                row_id=t.row_id,
                txn_date=t.txn_date,
                value_date=t.value_date,
                narration=t.narration or "",
                reference_no=t.reference_no,
                debit_amount=Decimal(str(t.debit_amount))
                if t.debit_amount is not None
                else None,
                credit_amount=Decimal(str(t.credit_amount))
                if t.credit_amount is not None
                else None,
                balance_after=Decimal(str(t.balance_after))
                if t.balance_after is not None
                else None,
                channel=t.channel,
                source_row_confidence=t.row_confidence,
            )
        )
    return result


def _transactions_to_df(txns: list[Transaction]) -> pd.DataFrame:
    records = []
    for t in txns:
        records.append(
            {
                "row_id": t.row_id,
                "txn_date": t.txn_date,
                "value_date": t.value_date,
                "narration": t.narration or "",
                "reference_no": t.reference_no,
                "debit_amount": float(t.debit_amount) if t.debit_amount else 0.0,
                "credit_amount": float(t.credit_amount) if t.credit_amount else 0.0,
                "balance_after": float(t.balance_after) if t.balance_after else None,
                "channel": t.channel or "",
                "counterparty_id": t.counterparty_id or "UNKNOWN",
            }
        )
    return pd.DataFrame(records)


@router.get("/{statement_id}/preview", response_model=PreviewOut)
async def get_preview(statement_id: int, db: Session = Depends(get_session)):
    stmt = _load_statement_or_404(db, statement_id)
    txns = db.exec(
        select(Transaction).where(Transaction.statement_id == statement_id)
    ).all()
    col_map = {}
    if stmt.raw_headers:
        from app.understanding.header_classifier import classify_columns
        sample_rows = stmt.raw_rows[:50] if stmt.raw_rows else []
        classified = classify_columns(stmt.raw_headers, sample_rows)
        for idx, h in enumerate(stmt.raw_headers):
            if idx in classified:
                col_map[h] = classified[idx][0]
            else:
                col_map[h] = ""
    return PreviewOut(
        statement_id=stmt.id,
        original_filename=stmt.original_filename,
        status=stmt.status,
        ood_score=stmt.ood_score,
        ood_signals=stmt.ood_signals,
        reconciliation_rate=stmt.reconciliation_rate,
        extraction_confidence=stmt.extraction_confidence,
        transaction_count=stmt.transaction_count,
        observed_start=str(stmt.observed_start) if stmt.observed_start else None,
        observed_end=str(stmt.observed_end) if stmt.observed_end else None,
        detected_column_mapping=col_map,
        transactions=[
            {
                "row_id": t.row_id,
                "txn_date": str(t.txn_date),
                "value_date": str(t.value_date) if t.value_date else None,
                "narration": t.narration,
                "reference_no": t.reference_no,
                "debit_amount": t.debit_amount,
                "credit_amount": t.credit_amount,
                "balance_after": t.balance_after,
                "channel": t.channel,
                "category": t.category,
                "is_reconciled": t.is_reconciled,
                "row_confidence": t.row_confidence,
            }
            for t in txns
        ],
    )


@router.post("/{statement_id}/mapping", response_model=MappingOut)
async def update_mapping(
    statement_id: int,
    body: MappingOverrideIn,
    db: Session = Depends(get_session),
):
    stmt = _load_statement_or_404(db, statement_id)

    # Convert header-name keys → integer column-index keys required by
    # map_row_to_transaction. The stored raw_headers gives us the index of
    # each header name in the original CSV/XLSX rows.
    resolved_headers: list[str] = body.headers or (stmt.raw_headers or [])
    header_to_idx: dict[str, int] = {h: i for i, h in enumerate(resolved_headers)}

    int_col_mapping: dict[int, str] = {}
    for header_key, field_name in body.column_mapping.items():
        if not field_name:  # ignore blanks / "— ignore —" selections
            continue
        # Accept both header-name keys (from UI) and already-integer-string keys
        if header_key in header_to_idx:
            int_col_mapping[header_to_idx[header_key]] = field_name
        else:
            try:
                int_col_mapping[int(header_key)] = field_name
            except (ValueError, TypeError):
                logger.warning("update_mapping: unknown header key %r — skipped", header_key)

    if body.save_as_template and resolved_headers:
        save_user_template(resolved_headers, int_col_mapping)

    stmt.manual_mapping_used = True
    db.add(stmt)

    new_txn_count = stmt.transaction_count or 0
    message = "Mapping override saved"

    raw_rows = body.raw_rows or (stmt.raw_rows if stmt.raw_rows else [])
    if raw_rows:
        existing = db.exec(
            select(Transaction).where(Transaction.statement_id == statement_id)
        ).all()
        for t in existing:
            db.delete(t)
        db.flush()

        new_txn_count = 0
        for row_idx, row in enumerate(raw_rows):
            canonical = map_row_to_transaction(
                row, int_col_mapping, statement_id, row_idx
            )
            if canonical is None:
                continue
            txn = Transaction(
                row_id=canonical.row_id,
                statement_id=statement_id,
                txn_date=canonical.txn_date,
                value_date=canonical.value_date,
                narration=canonical.narration,
                reference_no=canonical.reference_no,
                debit_amount=float(canonical.debit_amount)
                if canonical.debit_amount
                else None,
                credit_amount=float(canonical.credit_amount)
                if canonical.credit_amount
                else None,
                balance_after=float(canonical.balance_after)
                if canonical.balance_after
                else None,
                row_confidence=canonical.source_row_confidence,
            )
            db.add(txn)
            new_txn_count += 1

        stmt.transaction_count = new_txn_count
        message = f"Mapping override applied, {new_txn_count} transactions re-parsed"

    db.commit()

    return MappingOut(
        statement_id=statement_id,
        column_mapping=body.column_mapping,
        transaction_count=new_txn_count,
        message=message,
    )


@router.post("/{statement_id}/confirm", response_model=ConfirmOut)
async def confirm_extraction(statement_id: int, db: Session = Depends(get_session)):
    stmt = _load_statement_or_404(db, statement_id)
    txns = db.exec(
        select(Transaction)
        .where(Transaction.statement_id == statement_id)
        .order_by(Transaction.txn_date)
    ).all()
    if not txns:
        raise HTTPException(status_code=400, detail="No transactions to confirm")

    canonical_list = _transactions_to_canonical(txns)

    rec_rate, reconciled_flags, rec_error = reconcile_transactions(canonical_list)
    stmt.reconciliation_rate = rec_rate

    for i, txn in enumerate(txns):
        txn.is_reconciled = reconciled_flags[i] if i < len(reconciled_flags) else True
        txn.row_confidence = compute_row_confidence(
            canonical_list[i], txn.is_reconciled
        )

    extraction_conf_str = classify_extraction_confidence(rec_rate)
    stmt.extraction_confidence = rec_rate

    # Pass 1: Identify narrations that need AI categorization
    unique_narrations_for_ai = set()
    for txn, ct in zip(txns, canonical_list):
        narration = txn.narration or ""
        direction = "debit" if txn.debit_amount else ("credit" if txn.credit_amount else "unknown")
        cat = assign_category(narration, direction)
        cp = extract_counterparty(narration)
        if (cat == "uncategorized" or cp is None) and narration.strip():
            unique_narrations_for_ai.add(narration.strip())

    ai_results = {}
    if unique_narrations_for_ai:
        # Limit to 100 to prevent massive latency
        narrations_to_process = list(unique_narrations_for_ai)[:100]
        try:
            from app.categorization.llm_categorizer import batch_categorize
            # Process in chunks of 20
            for i in range(0, len(narrations_to_process), 20):
                chunk = narrations_to_process[i:i+20]
                chunk_results = batch_categorize(chunk)
                ai_results.update(chunk_results)
        except ImportError:
            pass

    counterparty_cache: dict[str, int] = {}
    for txn, ct in zip(txns, canonical_list):
        narration = txn.narration or ""
        txn.channel = infer_channel(narration)
        direction = (
            "debit"
            if txn.debit_amount
            else ("credit" if txn.credit_amount else "unknown")
        )
        
        txn.category = assign_category(narration, direction)
        cp_raw = extract_counterparty(narration)
        
        # Override with AI results
        if narration.strip() in ai_results:
            ai_data = ai_results[narration.strip()]
            if ai_data.get("category") and ai_data["category"] != "uncategorized":
                txn.category = ai_data["category"]
            if ai_data.get("merchant_name") and ai_data["merchant_name"] != "UNKNOWN":
                cp_raw = ai_data["merchant_name"]

        # 1. Check for self-transfers
        from app.categorization.counterparty_extractor import is_self_transfer
        is_self = is_self_transfer(narration, stmt.account_holder)
        if is_self:
            cp_raw = "Self Transfer"
            
        if cp_raw:
            # 2. Normalize the counterparty name to prevent duplicates (e.g. AMZN vs AMAZON)
            from app.categorization.merchant_normalizer import normalize_counterparty_name
            cp_norm = normalize_counterparty_name(cp_raw)
            
            existing = db.exec(
                select(Counterparty).where(Counterparty.canonical_name == cp_norm)
            ).first()
            if existing:
                txn.counterparty_id = existing.id
                if is_self and not existing.is_self_transfer:
                    existing.is_self_transfer = True
            else:
                cp = Counterparty(
                    canonical_name=cp_norm,
                    raw_variants=[cp_raw],
                    first_seen_statement_id=statement_id,
                    is_self_transfer=is_self
                )
                db.add(cp)
                db.commit()
                db.refresh(cp)
                txn.counterparty_id = cp.id
                counterparty_cache[cp_norm] = cp.id

    db.commit()

    df = _transactions_to_df(txns)
    feature_results = compute_all_features(df)
    feature_values: dict[str, float] = {}
    features_list: list[dict[str, Any]] = []
    for name, info in feature_results.items():
        val = info.get("value")
        if val is not None and isinstance(val, (int, float)):
            feature_values[name] = float(val)
        features_list.append(
            {
                "name": name,
                "value": val,
                "formula": info.get("formula", ""),
                "explanation": info.get("explanation", ""),
                "family": info.get("family", ""),
            }
        )

    G = build_transaction_graph(df, subject_account_id=f"ACCT_{statement_id}")
    graph_json = graph_to_json(G)
    cycles = detect_cycles(G)
    for txn in txns:
        txn.tagged_cycles = []
        for c in cycles:
            contributing = c.get("contributing_row_ids", [])
            if txn.row_id in contributing:
                cid = c.get("cycle_id", "")
                txn.tagged_cycles.append(cid)

    max_cycle_risk_score = 0.0
    if cycles:
        max_cycle_risk_score = max(c.get("cycle_risk_score", 0.0) for c in cycles)
    feature_values["max_cycle_risk_score"] = float(max_cycle_risk_score)

    rule_score, triggered_rules = evaluate_rules(feature_values)
    anomaly_score: float = 0.0
    anomaly_detail: dict[str, Any] | None = None
    try:
        # Construct feature matrix using past statements + current statement
        past_evidences = db.exec(select(EvidenceBundleRecord)).all()
        past_features_list = []
        feature_names = list(feature_values.keys())
        for ev in past_evidences:
            if ev.json_blob and isinstance(ev.json_blob, dict):
                feats = ev.json_blob.get("features", [])
                if feats:
                    pf = {f["name"]: f.get("value", 0.0) for f in feats if f.get("value") is not None}
                    row_vec = [pf.get(name, 0.0) for name in feature_names]
                    past_features_list.append(row_vec)
        
        current_row_vec = [feature_values.get(name, 0.0) for name in feature_names]
        matrix_data = past_features_list + [current_row_vec]
        feature_matrix = pd.DataFrame(matrix_data).fillna(0).to_numpy()

        mad_flagged = compute_mad_anomaly(feature_matrix, feature_names)

        iso_frac, top_iso, _ = compute_isolation_forest_anomaly(
            feature_matrix, feature_names
        )

        anomaly_score = (len(mad_flagged) / max(len(feature_values), 1) + iso_frac) / 2.0
        anomaly_detail = {
            "isolation_forest_score": iso_frac,
            "top_contributing_features": top_iso,
            "mad_flagged_features": mad_flagged,
        }
    except Exception as exc:
        logger.warning("MAD anomaly scoring skipped: %s", exc)

    supervised_probability: float | None = None
    if supervised_scorer.available:
        supervised_probability = supervised_scorer.predict_proba(feature_values)

    fused_score, score_formula = fuse_scores(
        rule_score, anomaly_score, supervised_probability
    )
    rules_triggered_bool = len(triggered_rules) > 0
    tier, thresholds_applied, decision_reason = decide_tier(
        fused_score=fused_score,
        rule_score=rule_score,
        anomaly_score=anomaly_score,
        extraction_confidence=extraction_conf_str,
        rules_triggered=rules_triggered_bool,
    )

    ood_check_passed = stmt.ood_score is not None and stmt.ood_score >= 0.5
    bundle = assemble_evidence_bundle(
        statement_id=str(statement_id),
        observed_start=str(stmt.observed_start) if stmt.observed_start else None,
        observed_end=str(stmt.observed_end) if stmt.observed_end else None,
        extraction_confidence=rec_rate,
        ood_score=stmt.ood_score or 0.0,
        transaction_count=len(txns),
        tier=tier,
        fused_score=fused_score,
        score_formula=score_formula,
        thresholds_applied=thresholds_applied,
        triggered_rules=triggered_rules,
        features=features_list,
        cycles=cycles,
        anomaly_detail=anomaly_detail,
        ood_check_passed=ood_check_passed,
        reconciliation_rate=rec_rate,
        extraction_conf_str=extraction_conf_str,
        manual_mapping_used=stmt.manual_mapping_used,
        rule_score=rule_score,
        anomaly_score=anomaly_score,
        decision_reason=decision_reason,
    )
    bundle_json = evidence_bundle_to_json(bundle)

    ev_rec = EvidenceBundleRecord(
        statement_id=statement_id,
        json_blob=bundle_json,
    )
    db.add(ev_rec)

    for cycle_data in cycles:
        cycle_rec = Cycle(
            statement_id=statement_id,
            node_sequence=cycle_data.get("nodes", []),
            hop_count=cycle_data.get("hop_count", 0),
            amount_conservation_ratio=cycle_data.get("amount_conservation_ratio"),
            cycle_span_days=cycle_data.get("cycle_span_days"),
            cycle_risk_score=cycle_data.get("cycle_risk_score"),
            contributing_row_ids=cycle_data.get("contributing_row_ids", []),
        )
        db.add(cycle_rec)

    stmt.status = "analyzed"
    db.commit()

    return ConfirmOut(
        statement_id=statement_id,
        status="analyzed",
        tier=tier,
        fused_score=fused_score,
        score_formula=score_formula,
        reconciliation_rate=rec_rate,
        extraction_confidence=extraction_conf_str,
        triggered_rules=triggered_rules,
        feature_count=len(features_list),
        cycle_count=len(cycles),
    )
