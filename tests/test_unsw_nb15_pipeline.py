import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "ml-anomaly"))

from unsw_nb15_pipeline import (  # noqa: E402
    DEFAULT_TEST_FILE,
    DEFAULT_TRAIN_FILE,
    UNSWNB15Pipeline,
    train_from_csv,
)


def make_unsw_like_frame():
    return pd.DataFrame(
        [
            [1, 0.12, "tcp", "http", "FIN", 6, 4, 258, 172, 74.1, "Normal", 0],
            [2, 0.23, "tcp", "http", "FIN", 8, 6, 400, 260, 60.2, "Normal", 0],
            [3, 0.05, "udp", "dns", "INT", 2, 0, 900, 0, 90000.0, "DoS", 1],
            [4, 1.20, "tcp", "ftp", "CON", 18, 20, 1500, 6400, 30.0, "Exploits", 1],
            [5, 0.09, "udp", "dns", "INT", 2, 0, 880, 0, 85000.0, "DoS", 1],
            [6, 0.18, "tcp", "smtp", "FIN", 8, 8, 600, 450, 45.0, "Normal", 0],
            [7, 1.80, "tcp", "ftp", "CON", 20, 22, 1800, 7000, 28.0, "Exploits", 1],
            [8, 0.16, "tcp", "http", "FIN", 6, 6, 320, 290, 50.0, "Normal", 0],
        ],
        columns=[
            "id",
            "dur",
            "proto",
            "service",
            "state",
            "spkts",
            "dpkts",
            "sbytes",
            "dbytes",
            "rate",
            "attack_cat",
            "label",
        ],
    )


def test_unsw_pipeline_trains_and_predicts_dashboard_output():
    train_df = make_unsw_like_frame()
    test_df = make_unsw_like_frame()

    pipeline = UNSWNB15Pipeline(feature_k=8, n_estimators=10, random_state=7)
    metrics = pipeline.fit(train_df, test_df)
    predictions = pipeline.predict_records(test_df.drop(columns=["attack_cat", "label"]).head(2))

    assert metrics["binary"]["accuracy"] >= 0.0
    assert metrics["multiclass"]["classes"]
    assert set(predictions[0]) == {
        "normal_attack",
        "attack_type",
        "severity",
        "anomaly_score",
        "action",
        "binary_attack_probability",
    }


def test_train_from_csv_saves_model_and_metrics(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "models"
    data_dir.mkdir()

    frame = make_unsw_like_frame()
    frame.to_csv(data_dir / DEFAULT_TRAIN_FILE, index=False)
    frame.to_csv(data_dir / DEFAULT_TEST_FILE, index=False)

    output = train_from_csv(
        data_dir=data_dir,
        output_dir=output_dir,
        feature_k=8,
        sample_size=None,
        random_state=7,
        n_estimators=10,
    )

    assert output.model_path.exists()
    assert output.metrics_path.exists()
    assert output.sample_predictions_path.exists()

    loaded = UNSWNB15Pipeline.load(output.model_path)
    assert loaded.predict_records(frame.head(1))[0]["normal_attack"] in {"Normal", "Attack"}
