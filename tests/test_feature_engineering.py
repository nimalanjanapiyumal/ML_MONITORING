import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "ml-anomaly"))

from anomaly_detector import TelemetryFeatureEngineer, AnomalyDetector


def test_feature_engineering_outputs_columns():
    features = TelemetryFeatureEngineer.build_features([1, 2, 3, 4, 5])
    assert "rolling_mean_3" in features.columns
    assert "rate_change" in features.columns
    assert len(features) == 5


def test_detector_returns_result():
    values = [1.0] * 50 + [10.0]
    detector = AnomalyDetector()
    result = detector.score_series("demo_metric", "demo_target", values)
    assert result.points == 51
    assert 0.0 <= result.score <= 1.0
    assert 0.0 <= result.model_score <= 1.0
    assert 0.0 <= result.robust_score <= 1.0
    assert 0.0 <= result.confidence <= 1.0
    assert result.baseline_deviation > 1.0
    assert result.flag == 1
    assert result.severity == "critical"
    assert result.threshold == 0.65


def test_detector_keeps_stable_series_normal():
    values = [50.0 + ((index % 3) - 1) * 0.2 for index in range(120)]
    detector = AnomalyDetector()
    result = detector.score_series("stable_metric", "demo_target", values)
    assert result.score < result.threshold
    assert result.flag == 0
    assert result.severity in {"normal", "watch"}
