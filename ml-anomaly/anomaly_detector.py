from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM


@dataclass
class AnomalyResult:
    metric_name: str
    target: str
    score: float
    flag: int
    latest_value: float
    model: str
    points: int


class TelemetryFeatureEngineer:
    """Creates simple explainable features from a single time-series."""

    @staticmethod
    def build_features(values: List[float]) -> pd.DataFrame:
        series = pd.Series(values, dtype="float64").replace([np.inf, -np.inf], np.nan)
        series = series.interpolate(limit_direction="both").fillna(method="bfill").fillna(method="ffill").fillna(0)

        df = pd.DataFrame({"value": series})
        df["rolling_mean_3"] = df["value"].rolling(window=3, min_periods=1).mean()
        df["rolling_std_3"] = df["value"].rolling(window=3, min_periods=1).std().fillna(0)
        df["rolling_mean_5"] = df["value"].rolling(window=5, min_periods=1).mean()
        df["rolling_std_5"] = df["value"].rolling(window=5, min_periods=1).std().fillna(0)
        df["rate_change"] = df["value"].diff().fillna(0)
        df["abs_rate_change"] = df["rate_change"].abs()
        df["z_like"] = (df["value"] - df["rolling_mean_5"]) / (df["rolling_std_5"] + 1e-6)

        return df.replace([np.inf, -np.inf], 0).fillna(0)


class AnomalyDetector:
    """Lightweight unsupervised anomaly detector for monitoring telemetry."""

    def __init__(
        self,
        algorithm: str = "isolation_forest",
        contamination: float = 0.08,
        random_state: int = 42,
        anomaly_threshold: float = 0.65,
    ) -> None:
        self.algorithm = algorithm
        self.contamination = contamination
        self.random_state = random_state
        self.anomaly_threshold = anomaly_threshold

    def _make_model(self):
        if self.algorithm == "local_outlier_factor":
            return LocalOutlierFactor(n_neighbors=10, contamination=self.contamination, novelty=False)
        if self.algorithm == "one_class_svm":
            return OneClassSVM(nu=max(min(self.contamination, 0.49), 0.01), kernel="rbf", gamma="scale")
        return IsolationForest(
            n_estimators=100,
            contamination=self.contamination,
            random_state=self.random_state,
        )

    def score_series(self, metric_name: str, target: str, values: List[float]) -> AnomalyResult:
        if not values:
            return AnomalyResult(metric_name, target, 0.0, 0, 0.0, self.algorithm, 0)

        features = TelemetryFeatureEngineer.build_features(values)
        model = self._make_model()

        if self.algorithm == "local_outlier_factor":
            predictions = model.fit_predict(features)
            # negative_outlier_factor_: more negative = more abnormal
            raw_scores = -model.negative_outlier_factor_
            normalized = self._normalize_scores(raw_scores)
        else:
            model.fit(features)
            raw_scores = -model.score_samples(features)
            normalized = self._normalize_scores(raw_scores)
            predictions = np.where(normalized >= self.anomaly_threshold, -1, 1)

        latest_score = float(normalized[-1]) if len(normalized) else 0.0
        latest_value = float(values[-1])
        latest_flag = int(predictions[-1] == -1 or latest_score >= self.anomaly_threshold)

        return AnomalyResult(
            metric_name=metric_name,
            target=target,
            score=latest_score,
            flag=latest_flag,
            latest_value=latest_value,
            model=self.algorithm,
            points=len(values),
        )

    @staticmethod
    def _normalize_scores(scores: np.ndarray) -> np.ndarray:
        scores = np.asarray(scores, dtype="float64")
        if scores.size == 0:
            return np.array([0.0])
        minimum = float(np.min(scores))
        maximum = float(np.max(scores))
        if maximum - minimum < 1e-9:
            return np.zeros_like(scores)
        return (scores - minimum) / (maximum - minimum)
