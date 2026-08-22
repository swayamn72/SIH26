import json
import logging
from pathlib import Path

import joblib
import numpy as np

from app.config_loader import load_config
from app.scoring.calibration import apply_calibration

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "ml" / "artifacts"


def supervised_model_available(label_count: int) -> bool:
    cfg = load_config("thresholds")
    min_labels = cfg.get("supervised", {}).get("min_labeled_accounts", 200)
    return label_count >= min_labels


class SupervisedScorer:
    """Loads the classifier trained by app/ml/training/train_supervised.py
    and scores the same named feature dict produced by
    app.features.feature_registry.compute_all_features.

    If no trained artifacts exist yet (e.g. fresh checkout, or fewer than
    `min_labeled_accounts` labeled accounts), this degrades cleanly:
    `available` is False and fusion.fuse_scores falls back to
    rule_score + anomaly_score only -- no supervised model in the loop.
    """

    def __init__(self):
        self.model = None
        self.calibrator: dict = {}
        self.feature_names: list[str] = []
        self.is_trained = False
        self._load()

    def _load(self):
        model_path = ARTIFACT_DIR / "model.pkl"
        calib_path = ARTIFACT_DIR / "calibrator.pkl"
        features_path = ARTIFACT_DIR / "feature_names.json"

        if not (model_path.exists() and features_path.exists()):
            logger.info(
                "No trained supervised model found at %s -- supervised scoring disabled.",
                ARTIFACT_DIR,
            )
            return

        try:
            self.model = joblib.load(model_path)
            self.feature_names = json.loads(features_path.read_text())
            self.calibrator = joblib.load(calib_path) if calib_path.exists() else {}
            self.is_trained = True
            logger.info(
                "Loaded supervised model (%d features) from %s",
                len(self.feature_names),
                ARTIFACT_DIR,
            )
        except Exception as exc:
            logger.warning("Failed to load supervised model artifacts: %s", exc)
            self.model = None
            self.is_trained = False

    @property
    def available(self) -> bool:
        return self.is_trained

    def predict_proba(self, feature_values: dict[str, float]) -> float | None:
        """feature_values: the same {name: value} dict routes_review.py
        already builds from compute_all_features (plus any extras --
        unknown keys are ignored, missing ones become NaN)."""
        if not self.is_trained or self.model is None:
            return None

        try:
            row = np.array(
                [[feature_values.get(name, np.nan) for name in self.feature_names]],
                dtype=float,
            )
            raw_score = float(self.model.predict_proba(row)[0, 1])
            calibrated = apply_calibration(
                raw_score,
                self.calibrator.get("isotonic"),
                self.calibrator.get("platt"),
            )
            return calibrated
        except Exception as exc:
            logger.warning(
                "Supervised scoring failed, falling back to rule/anomaly only: %s", exc
            )
            return None
