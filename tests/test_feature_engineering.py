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
