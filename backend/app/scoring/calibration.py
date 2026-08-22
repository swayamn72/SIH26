from typing import Optional

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


def _brier_score(y_true: list[int], y_prob: list[float]) -> float:
    return np.mean((np.array(y_true) - np.array(y_prob)) ** 2)


def calibrate_scores(
    scores: list[float],
    labels: list[int],
) -> tuple[Optional[IsotonicRegression], Optional[LogisticRegression]]:
    if len(scores) < 10 or len(set(labels)) < 2:
        return None, None

    scores_arr = np.array(scores).reshape(-1, 1)
    labels_arr = np.array(labels)

    try:
        isotonic = IsotonicRegression(out_of_bounds="clip")
        isotonic.fit(scores, labels_arr)
    except Exception:
        isotonic = None

    try:
        platt = LogisticRegression(solver="lbfgs")
        platt.fit(scores_arr, labels_arr)
    except Exception:
        platt = None

    if isotonic is not None and platt is not None:
        iso_prob = isotonic.predict(scores)
        platt_prob = platt.predict_proba(scores_arr)[:, 1]
        iso_brier = _brier_score(labels_arr, iso_prob)
        platt_brier = _brier_score(labels_arr, platt_prob)
        if platt_brier < iso_brier:
            return None, platt
        else:
            return isotonic, None

    return isotonic, platt


def apply_calibration(
    score: float,
    isotonic: Optional[IsotonicRegression],
    platt: Optional[LogisticRegression],
) -> float:
    if platt is not None:
        prob = platt.predict_proba(np.array([[score]]))[0, 1]
        return float(prob)
    if isotonic is not None:
        prob = isotonic.predict([score])[0]
        return float(max(0, min(1, prob)))
    return float(score)
