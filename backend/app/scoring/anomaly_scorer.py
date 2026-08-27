from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest

from app.config_loader import load_config


def compute_robust_zscore(values: list[float]) -> list[float]:
    arr = np.array(values, dtype=float)
    median = np.median(arr)
    mad = np.median(np.abs(arr - median))
    if mad == 0:
        return [0.0] * len(arr)
    modified_z = 0.6745 * (arr - median) / mad
    return modified_z.tolist()


def _minimum_reference_cohort() -> int:
    return int(
        load_config("thresholds")
        .get("anomaly", {})
        .get("minimum_reference_statements", 3)
    )


def compute_isolation_forest_anomaly(
    reference_feature_matrix: np.ndarray,
    current_feature_row: np.ndarray,
    feature_names: list[str],
) -> tuple[float | None, list[str], dict[str, Any]]:
    """Score the current statement against a stable, separate reference cohort.

    The fitted forest never includes the current row. This prevents a statement's
    earlier evidence from becoming a duplicate training observation on a repeated
    confirmation and ensures the returned score belongs to the current statement,
    not the fraction of anomalous reference rows.
    """
    cfg = load_config("thresholds")
    if_cfg = cfg.get("anomaly", {}).get("isolation_forest", {})
    n_estimators = if_cfg.get("n_estimators", 200)
    random_state = if_cfg.get("random_state", 42)
    contamination = if_cfg.get("contamination", "auto")
    min_references = _minimum_reference_cohort()

    if reference_feature_matrix.ndim != 2 or reference_feature_matrix.shape[1] < 1:
        return None, [], {"availability_reason": "invalid_reference_feature_matrix"}
    if reference_feature_matrix.shape[0] < min_references:
        return None, [], {
            "availability_reason": "insufficient_reference_cohort",
            "reference_cohort_size": int(reference_feature_matrix.shape[0]),
            "minimum_reference_cohort_size": min_references,
        }

    model = IsolationForest(
        n_estimators=n_estimators,
        random_state=random_state,
        contamination=contamination,
    )
    model.fit(reference_feature_matrix)
    current_row = np.asarray(current_feature_row, dtype=float).reshape(1, -1)
    # A deterministic current-statement score: 1 only when the fitted model marks
    # this current row anomalous, otherwise 0. It is intentionally not a statistic
    # over all cohort rows.
    current_score = float(model.predict(current_row)[0] == -1)

    top_features: list[str] = []
    if reference_feature_matrix.shape[1] >= 2:
        feature_contrib = np.abs(current_row[0] - np.median(reference_feature_matrix, axis=0))
        top_indices = np.argsort(feature_contrib)[-5:][::-1]
        top_features = [feature_names[i] for i in top_indices if i < len(feature_names)]

    return current_score, top_features, {
        "seed": random_state,
        "n_estimators": n_estimators,
        "reference_cohort_size": int(reference_feature_matrix.shape[0]),
        "minimum_reference_cohort_size": min_references,
    }


def compute_mad_anomaly(
    reference_feature_matrix: np.ndarray,
    feature_names: list[str],
    current_feature_row: np.ndarray,
) -> dict[str, float]:
    """Return current-row robust-z flags using only the reference cohort."""
    cfg = load_config("thresholds")
    threshold = cfg.get("anomaly", {}).get("robust_zscore_threshold", 3.5)
    min_references = _minimum_reference_cohort()

    if (
        reference_feature_matrix.ndim != 2
        or reference_feature_matrix.shape[0] < min_references
        or reference_feature_matrix.shape[1] == 0
    ):
        return {}

    flagged: dict[str, float] = {}
    current_row = np.asarray(current_feature_row, dtype=float).reshape(-1)
    for col_idx, name in enumerate(feature_names):
        col_data = reference_feature_matrix[:, col_idx]
        median = np.median(col_data)
        mad = np.median(np.abs(col_data - median))
        if mad > 0:
            z = 0.6745 * (current_row[col_idx] - median) / mad
            if abs(z) > threshold:
                flagged[name] = round(float(z), 4)
    return flagged
