import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
)
from sklearn.model_selection import train_test_split

try:
    import lightgbm as lgb

    HAS_LGB = True
except ImportError:
    HAS_LGB = False

from app.features.feature_registry import REGISTRY, compute_all_features
from app.scoring.calibration import calibrate_scores

ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_NAMES = list(REGISTRY.keys())


def load_ibm_aml(csv_path: str, nrows: int | None = None) -> pd.DataFrame:
    df = pd.read_csv(csv_path, nrows=nrows)
    df.columns = [c.strip() for c in df.columns]

    # The raw CSV has two columns both literally named "Account" (sender
    # and receiver); pandas disambiguates the second as "Account.1".
    acct_cols = [c for c in df.columns if c == "Account" or c.startswith("Account.")]
    if len(acct_cols) != 2:
        raise ValueError(
            f"Expected exactly 2 'Account' columns in the IBM AML CSV, found {acct_cols}. "
            f"Got columns: {list(df.columns)}"
        )
    from_acct_col, to_acct_col = acct_cols

    df = df.rename(
        columns={
            "Timestamp": "timestamp",
            "From Bank": "from_bank",
            from_acct_col: "from_account",
            "To Bank": "to_bank",
            to_acct_col: "to_account",
            "Amount Paid": "amount_paid",
            "Amount Received": "amount_received",
            "Is Laundering": "is_laundering",
        }
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    # Account numbers repeat across banks in this dataset, so make IDs
    # globally unique by prefixing with the bank id.
    df["from_id"] = df["from_bank"].astype(str) + "_" + df["from_account"].astype(str)
    df["to_id"] = df["to_bank"].astype(str) + "_" + df["to_account"].astype(str)
    return df


def build_account_ledger(tx: pd.DataFrame) -> pd.DataFrame:
    """Edge list -> long-format per-account ledger matching the column
    names app/features/*.py already expects."""
    outgoing = pd.DataFrame(
        {
            "account_id": tx["from_id"],
            "txn_date": tx["timestamp"],
            "debit_amount": tx["amount_paid"],
            "credit_amount": np.nan,
            "counterparty_id": tx["to_id"],
            "is_laundering": tx["is_laundering"],
        }
    )
    incoming = pd.DataFrame(
        {
            "account_id": tx["to_id"],
            "txn_date": tx["timestamp"],
            "debit_amount": np.nan,
            "credit_amount": tx["amount_received"],
            "counterparty_id": tx["from_id"],
            "is_laundering": tx["is_laundering"],
        }
    )
    ledger = pd.concat([outgoing, incoming], ignore_index=True)
    ledger["balance_after"] = np.nan  # not present in this dataset
    return ledger


def build_account_dataset(
    ledger: pd.DataFrame,
    max_accounts: int | None,
    max_txns_per_account: int | None = 2000,
) -> pd.DataFrame:
    import time

    account_ids = ledger["account_id"].unique()
    if max_accounts and len(account_ids) > max_accounts:
        rng = np.random.default_rng(42)
        flagged = ledger.loc[ledger["is_laundering"] == 1, "account_id"].unique()
        rest = np.setdiff1d(account_ids, flagged)
        keep_rest = rng.choice(
            rest,
            size=max(min(max_accounts - len(flagged), len(rest)), 0),
            replace=False,
        )
        account_ids = np.concatenate([flagged, keep_rest])

    total = len(account_ids)
    print(f"  Computing features for {total:,} accounts...")

    rows = []
    subset = ledger[ledger["account_id"].isin(account_ids)]
    start = time.time()
    log_every = max(total // 100, 100)  # ~100 progress lines total
    for i, (account_id, group) in enumerate(subset.groupby("account_id"), start=1):
        n_txns = len(group)
        if max_txns_per_account and n_txns > max_txns_per_account:
            elapsed_warn = time.time() - start
            print(
                f"    [{i:,}/{total:,}] account with {n_txns:,} transactions "
                f"-- capping to most recent {max_txns_per_account:,} for feature computation "
                f"({elapsed_warn:.0f}s elapsed so far)",
                flush=True,
            )
            feature_group = group.sort_values("txn_date").tail(max_txns_per_account)
        else:
            feature_group = group

        feats = compute_all_features(feature_group)
        row = {name: feats[name]["value"] for name in FEATURE_NAMES}
        row["account_id"] = account_id
        row["label"] = int(
            group["is_laundering"].max()
        )  # label from FULL history, not the capped sample
        row["n_transactions"] = n_txns
        rows.append(row)

        if i % log_every == 0 or i == total:
            elapsed = time.time() - start
            rate = i / elapsed if elapsed > 0 else 0
            remaining = (total - i) / rate if rate > 0 else 0
            print(
                f"    {i:,}/{total:,} accounts "
                f"({i / total * 100:.1f}%) | "
                f"{elapsed:.0f}s elapsed | "
                f"~{remaining:.0f}s remaining",
                flush=True,
            )

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to IBM AML transactions CSV")
    parser.add_argument(
        "--nrows", type=int, default=None, help="Limit rows read (for fast iteration)"
    )
    parser.add_argument(
        "--max-accounts",
        type=int,
        default=50000,
        help="Cap total accounts sampled (all laundering-linked accounts are always kept)",
    )
    parser.add_argument(
        "--max-txns-per-account",
        type=int,
        default=2000,
        help="Cap transactions fed into feature computation per account. Hub accounts with "
        "tens of thousands of transactions otherwise dominate runtime; the label is "
        "still based on the FULL transaction history, only the features are computed "
        "on a capped, chronologically-recent sample.",
    )
    args = parser.parse_args()

    print("Loading IBM AML transactions...")
    load_start = __import__("time").time()
    tx = load_ibm_aml(args.csv, nrows=args.nrows)
    print(f"  loaded in {__import__('time').time() - load_start:.0f}s")
    print(
        f"  {len(tx):,} transactions, {tx['is_laundering'].mean() * 100:.3f}% flagged laundering"
    )

    print("Building per-account ledger...")
    ledger = build_account_ledger(tx)

    print("Computing account-level features (same functions as production)...")
    accounts = build_account_dataset(
        ledger,
        max_accounts=args.max_accounts,
        max_txns_per_account=args.max_txns_per_account,
    )
    print(
        f"  {len(accounts):,} accounts, {int(accounts['label'].sum())} laundering-linked "
        f"({accounts['label'].mean() * 100:.2f}%)"
    )

    if accounts["label"].nunique() < 2:
        raise SystemExit(
            "Only one class present after sampling -- raise --max-accounts or --nrows."
        )

    X = accounts[FEATURE_NAMES].astype(float)
    y = accounts["label"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    print(f"Training on {len(X_train):,} accounts, evaluating on {len(X_test):,}...")

    if HAS_LGB:
        model = lgb.LGBMClassifier(
            n_estimators=400,
            learning_rate=0.05,
            num_leaves=31,
            class_weight="balanced",
            random_state=42,
        )
    else:
        print(
            "  lightgbm not installed -- using sklearn HistGradientBoostingClassifier "
            "(`pip install lightgbm` for a stronger model)."
        )
        model = HistGradientBoostingClassifier(
            max_iter=400,
            learning_rate=0.05,
            class_weight="balanced",
            random_state=42,
        )
    model.fit(X_train, y_train)

    raw_test = model.predict_proba(X_test)[:, 1]
    raw_train = model.predict_proba(X_train)[:, 1]

    pr_auc = average_precision_score(y_test, raw_test)
    brier = brier_score_loss(y_test, raw_test)
    precisions, recalls, pr_thresholds = precision_recall_curve(y_test, raw_test)

    print(f"\nPR-AUC: {pr_auc:.4f}   Brier: {brier:.4f}")

    # Calibrate on TRAIN scores only -- never fit calibration on test data.
    isotonic, platt = calibrate_scores(raw_train.tolist(), y_train.tolist())

    # Report Brier on the CALIBRATED test scores too -- this is what
    # SupervisedScorer actually serves at inference time, and it's the
    # honest number to quote (raw LightGBM probabilities are frequently
    # over/under-confident and can look worse than a trivial baseline).
    from app.scoring.calibration import apply_calibration

    calibrated_test = np.array(
        [apply_calibration(s, isotonic, platt) for s in raw_test]
    )
    brier_calibrated = brier_score_loss(y_test, calibrated_test)
    baseline_brier = float(
        y_train.mean() * (1 - y_train.mean())
    )  # trivial "always predict base rate"

    print(
        f"Brier (raw): {brier:.4f}   Brier (calibrated): {brier_calibrated:.4f}   "
        f"Baseline (predict base rate): {baseline_brier:.4f}"
    )

    threshold_report = {}
    for target_precision in (0.5, 0.7, 0.9):
        idx = np.where(precisions[:-1] >= target_precision)[0]
        if len(idx):
            i = idx[0]
            threshold_report[f"recall_at_precision_{target_precision}"] = float(
                recalls[i]
            )
            threshold_report[f"score_threshold_at_precision_{target_precision}"] = (
                float(pr_thresholds[i])
            )

    metrics = {
        "n_accounts_total": len(accounts),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "positive_rate": float(y.mean()),
        "pr_auc": float(pr_auc),
        "brier_score_raw": float(brier),
        "brier_score_calibrated": float(brier_calibrated),
        "brier_baseline_predict_base_rate": baseline_brier,
        **threshold_report,
        "used_lightgbm": HAS_LGB,
    }
    print(json.dumps(metrics, indent=2))

    joblib.dump(model, ARTIFACT_DIR / "model.pkl")
    joblib.dump({"isotonic": isotonic, "platt": platt}, ARTIFACT_DIR / "calibrator.pkl")
    (ARTIFACT_DIR / "feature_names.json").write_text(
        json.dumps(FEATURE_NAMES, indent=2)
    )
    (ARTIFACT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"\nSaved model + calibrator + metrics to {ARTIFACT_DIR}")


if __name__ == "__main__":
    main()
