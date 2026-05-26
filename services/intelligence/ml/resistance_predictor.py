"""XGBoost resistance predictor.

Tabular feature predictor with SHAP explainability. Trains on isolate_events
data (or external ATLAS data, if downloaded) and predicts P(resistant) for an
organism-antibiotic combination given clinical context.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES

log = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parents[3] / "data" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TrainResult:
    model_version: str
    n_train: int
    n_test: int
    auc: float
    accuracy: float
    feature_names: list[str] = field(default_factory=list)


class ResistancePredictor:
    """End-to-end pipeline: preprocessing + XGBoost. Persisted as a single joblib file."""

    def __init__(self) -> None:
        self.pipeline: Optional[Pipeline] = None
        self.model_version: Optional[str] = None
        self._explainer = None

    def train(self, df: pd.DataFrame) -> TrainResult:
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import roc_auc_score, accuracy_score

        if df.empty:
            raise ValueError("Empty training frame")

        X = df[CATEGORICAL_FEATURES + NUMERIC_FEATURES]
        y = df["resistant"].astype(int)

        preprocessor = ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=10), CATEGORICAL_FEATURES),
            ("num", StandardScaler(),                                          NUMERIC_FEATURES),
        ])

        clf = XGBClassifier(
            n_estimators=400,
            max_depth=6,
            learning_rate=0.05,
            objective="binary:logistic",
            eval_metric="auc",
            tree_method="hist",
            random_state=42,
        )

        self.pipeline = Pipeline([("preprocess", preprocessor), ("clf", clf)])

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        self.pipeline.fit(X_train, y_train)
        proba_test = self.pipeline.predict_proba(X_test)[:, 1]
        pred_test = (proba_test >= 0.5).astype(int)

        auc = float(roc_auc_score(y_test, proba_test))
        acc = float(accuracy_score(y_test, pred_test))
        self.model_version = f"xgb-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}"

        log.info("Trained model %s — AUC %.3f, accuracy %.3f", self.model_version, auc, acc)

        return TrainResult(
            model_version=self.model_version,
            n_train=len(X_train),
            n_test=len(X_test),
            auc=auc,
            accuracy=acc,
        )

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        if self.pipeline is None:
            raise RuntimeError("Model not loaded; call train() or load() first")
        df = pd.DataFrame([features])
        proba = float(self.pipeline.predict_proba(df)[0, 1])

        # Wilson score interval as a simple confidence bound
        n = max(features.get("n_observations", 30), 1)
        ci_half = 1.96 * float(np.sqrt(proba * (1 - proba) / n))
        return {
            "predicted_rate": proba,
            "confidence_lower": max(0.0, proba - ci_half),
            "confidence_upper": min(1.0, proba + ci_half),
            "model_version": self.model_version,
        }

    def shap_values(self, features: dict[str, Any]) -> dict[str, float]:
        """Top-N SHAP feature contributions for a single prediction."""
        try:
            import shap
        except ImportError:
            return {}
        if self.pipeline is None:
            return {}

        df = pd.DataFrame([features])
        preprocess = self.pipeline.named_steps["preprocess"]
        clf = self.pipeline.named_steps["clf"]
        X = preprocess.transform(df)
        feature_names = preprocess.get_feature_names_out().tolist()

        if self._explainer is None:
            self._explainer = shap.TreeExplainer(clf)
        values = self._explainer.shap_values(X)[0]

        named = list(zip(feature_names, values))
        named.sort(key=lambda kv: abs(kv[1]), reverse=True)
        return {name: float(value) for name, value in named[:10]}

    def save(self, name: str | None = None) -> Path:
        if self.pipeline is None or self.model_version is None:
            raise RuntimeError("Nothing to save")
        path = MODEL_DIR / f"{name or self.model_version}.joblib"
        joblib.dump({"pipeline": self.pipeline, "version": self.model_version}, path)
        log.info("Saved model to %s", path)
        return path

    def load(self, path: Path) -> None:
        blob = joblib.load(path)
        self.pipeline = blob["pipeline"]
        self.model_version = blob["version"]


_predictor: Optional[ResistancePredictor] = None


def get_predictor() -> ResistancePredictor:
    global _predictor
    if _predictor is None:
        _predictor = ResistancePredictor()
        models = sorted(MODEL_DIR.glob("xgb-*.joblib"))
        if models:
            _predictor.load(models[-1])
    return _predictor
