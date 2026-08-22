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


def compute_isolation_forest_anomaly(
    feature_matrix: np.ndarray,
    feature_names: list[str],
) -> tuple[float, list[str], dict[str, Any]]:
    cfg = load_config("thresholds")
    if_cfg = cfg.get("anomaly", {}).get("isolation_forest", {})
    n_estimators = if_cfg.get("n_estimators", 200)
    random_state = if_cfg.get("random_state", 42)
    contamination = if_cfg.get("contamination", "auto")

    if feature_matrix.shape[0] < 4 or feature_matrix.shape[1] < 1:
        return 0.0, [], {"error": "insufficient data for isolation forest"}

    model = IsolationForest(
        n_estimators=n_estimators,
        random_state=random_state,
        contamination=contamination,
    )

    scores = model.fit_predict(feature_matrix)
    anomaly_scores = model.score_samples(feature_matrix)
    neg_anomaly_count = int((scores == -1).sum())
    anomaly_frac = neg_anomaly_count / len(scores)

    top_features: list[str] = []
    if feature_matrix.shape[1] >= 2:
        feature_contrib = np.abs(feature_matrix - np.median(feature_matrix, axis=0)).mean(axis=0)
        top_indices = np.argsort(feature_contrib)[-5:][::-1]
        top_features = [feature_names[i] for i in top_indices if i < len(feature_names)]

    return float(anomaly_frac), top_features, {"seed": random_state, "n_estimators": n_estimators}


def compute_mad_anomaly(feature_matrix: np.ndarray, feature_names: list[str]) -> dict[str, float]:
    cfg = load_config("thresholds")
    threshold = cfg.get("anomaly", {}).get("robust_zscore_threshold", 3.5)

    if feature_matrix.shape[0] < 3 or feature_matrix.shape[1] == 0:
        return {}

    flagged: dict[str, float] = {}
    
    # We want to check if the *current* statement (last row) is an anomaly
    # compared to the distribution of all statements (all rows).
    current_row = feature_matrix[-1, :]
    
    for col_idx, name in enumerate(feature_names):
        col_data = feature_matrix[:, col_idx]
        median = np.median(col_data)
        mad = np.median(np.abs(col_data - median))
        
        if mad > 0:
            z = 0.6745 * (current_row[col_idx] - median) / mad
            if abs(z) > threshold:
                flagged[name] = round(z, 4)
                
    return flagged
