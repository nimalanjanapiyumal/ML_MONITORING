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
    model_score: float
    robust_score: float
    confidence: float
    baseline_deviation: float
    flag: int
    severity: str
    threshold: float
    latest_value: float
    model: str
    points: int


class TelemetryFeatureEngineer:
    """Creates simple explainable features from a single time-series."""

    @staticmethod
    def build_features(values: List[float]) -> pd.DataFrame:
        series = pd.Series(values, dtype="float64").replace([np.inf, -np.inf], np.nan)
        series = series.interpolate(limit_direction="both").bfill().ffill().fillna(0)

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
        watch_threshold: float = 0.50,
        critical_threshold: float = 0.85,
        model_weight: float = 0.65,
        robust_weight: float = 0.35,
        confidence_reference_points: int = 120,
    ) -> None:
        self.algorithm = algorithm
        self.contamination = contamination
        self.random_state = random_state
        self.anomaly_threshold = anomaly_threshold
        self.watch_threshold = watch_threshold
        self.critical_threshold = critical_threshold
        total_weight = model_weight + robust_weight
        if total_weight <= 0:
            raise ValueError("model_weight and robust_weight must have a positive sum.")
        self.model_weight = model_weight / total_weight
        self.robust_weight = robust_weight / total_weight
        self.confidence_reference_points = max(confidence_reference_points, 1)

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
            return AnomalyResult(
                metric_name=metric_name,
                target=target,
                score=0.0,
                model_score=0.0,
                robust_score=0.0,
                confidence=0.0,
                baseline_deviation=0.0,
                flag=0,
                severity="normal",
                threshold=self.anomaly_threshold,
                latest_value=0.0,
                model=self.algorithm,
                points=0,
            )

        features = TelemetryFeatureEngineer.build_features(values)
        model = self._make_model()

        if self.algorithm == "local_outlier_factor":
            model.fit_predict(features)
            # negative_outlier_factor_: more negative = more abnormal
            raw_scores = -model.negative_outlier_factor_
            model_scores = self._normalize_scores(raw_scores)
        else:
            model.fit(features)
            raw_scores = -model.score_samples(features)
            model_scores = self._normalize_scores(raw_scores)

        latest_model_score = float(model_scores[-1]) if len(model_scores) else 0.0
        latest_value = float(values[-1])
        baseline_deviation, robust_score = self._robust_deviation(values)
        latest_score = float(
            np.clip(
                self.model_weight * latest_model_score + self.robust_weight * robust_score,
                0.0,
                1.0,
            )
        )
        latest_flag = int(latest_score >= self.anomaly_threshold)
        severity = self._severity(latest_score)
        confidence = self._confidence(latest_score, len(values))

        return AnomalyResult(
            metric_name=metric_name,
            target=target,
            score=latest_score,
            model_score=latest_model_score,
            robust_score=robust_score,
            confidence=confidence,
            baseline_deviation=baseline_deviation,
            flag=latest_flag,
            severity=severity,
            threshold=self.anomaly_threshold,
            latest_value=latest_value,
            model=f"hybrid_{self.algorithm}",
            points=len(values),
        )

    def _severity(self, score: float) -> str:
        if score >= self.critical_threshold:
            return "critical"
        if score >= self.anomaly_threshold:
            return "warning"
        if score >= self.watch_threshold:
            return "watch"
        return "normal"

    def _confidence(self, score: float, points: int) -> float:
        data_coverage = min(points / self.confidence_reference_points, 1.0)
        decision_span = max(self.critical_threshold - self.watch_threshold, 0.1)
        decision_separation = min(abs(score - self.anomaly_threshold) / decision_span, 1.0)
        return float(np.clip(0.65 * data_coverage + 0.35 * decision_separation, 0.0, 1.0))

    @staticmethod
    def _robust_deviation(values: List[float]) -> Tuple[float, float]:
        numeric = np.asarray(values, dtype="float64")
        baseline = numeric[:-1] if numeric.size > 1 else numeric
        median = float(np.median(baseline))
        mad = float(np.median(np.abs(baseline - median)))
        standard_deviation = float(np.std(baseline))
        scale = max(1.4826 * mad, standard_deviation * 0.25, abs(median) * 0.01, 1e-6)
        deviation = abs(float(numeric[-1]) - median) / scale
        robust_score = 1.0 - np.exp(-deviation / 3.0)
        return float(deviation), float(np.clip(robust_score, 0.0, 1.0))

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
