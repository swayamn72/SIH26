import json
import logging
from pathlib import Path

import joblib
import numpy as np

from app.config_loader import load_config
from app.scoring.calibration import apply_calibration

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "ml" / "artifacts"
_REQUIRED_MANIFEST_FIELDS = {
    "model_version",
    "feature_semantics_version",
    "feature_schema_hash",
    "training_provenance",
    "metrics",
    "library_versions",
    "artifact_hashes",
}


class SupervisedScorer:
    """Load a supervised scorer only when it has explicit governance metadata.

    Checked-in artifacts are intentionally inactive by default. Enabling a model
    requires both `supervised.enabled: true` and a complete versioned manifest
    that binds the artifact to the finalized feature semantics.
    """

    def __init__(self):
        self.model = None
        self.calibrator: dict = {}
        self.feature_names: list[str] = []
        self.is_trained = False
        self.unavailable_reason = "not_loaded"
        self.model_version: str | None = None
        self._load()

    def _load(self) -> None:
        cfg = load_config("thresholds").get("supervised", {})
        if not cfg.get("enabled", False):
            self.unavailable_reason = "disabled_by_configuration"
            logger.info("Supervised scoring disabled by configuration.")
            return

        model_path = ARTIFACT_DIR / "model.pkl"
        calib_path = ARTIFACT_DIR / "calibrator.pkl"
        features_path = ARTIFACT_DIR / "feature_names.json"
        manifest_path = ARTIFACT_DIR / "manifest.json"
        if not (model_path.exists() and features_path.exists()):
            self.unavailable_reason = "artifacts_missing"
            logger.info("No trained supervised model found at %s.", ARTIFACT_DIR)
            return
        if not manifest_path.exists():
            self.unavailable_reason = "provenance_manifest_missing"
            logger.warning("Supervised artifacts ignored: manifest missing at %s", manifest_path)
            return

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            missing = sorted(_REQUIRED_MANIFEST_FIELDS - set(manifest))
            if missing:
                self.unavailable_reason = f"provenance_manifest_incomplete: {', '.join(missing)}"
                logger.warning("Supervised artifacts ignored: incomplete manifest (%s)", ", ".join(missing))
                return
            self.model = joblib.load(model_path)
            self.feature_names = json.loads(features_path.read_text(encoding="utf-8"))
            self.calibrator = joblib.load(calib_path) if calib_path.exists() else {}
            self.model_version = str(manifest["model_version"])
            self.is_trained = True
            self.unavailable_reason = None
            logger.info("Loaded governed supervised model %s (%d features).", self.model_version, len(self.feature_names))
        except Exception as exc:
            self.model = None
            self.is_trained = False
            self.unavailable_reason = f"artifact_load_failed: {exc.__class__.__name__}"
            logger.warning("Failed to load supervised model artifacts: %s", exc)

    @property
    def available(self) -> bool:
        return self.is_trained

    def predict_proba(self, feature_values: dict[str, float]) -> float | None:
        if not self.is_trained or self.model is None:
            return None
        try:
            row = np.array([[feature_values.get(name, np.nan) for name in self.feature_names]], dtype=float)
            raw_score = float(self.model.predict_proba(row)[0, 1])
            return apply_calibration(raw_score, self.calibrator.get("isotonic"), self.calibrator.get("platt"))
        except Exception as exc:
            self.unavailable_reason = f"prediction_failed: {exc.__class__.__name__}"
            logger.warning("Supervised scoring failed, falling back to rule/anomaly only: %s", exc)
            return None
