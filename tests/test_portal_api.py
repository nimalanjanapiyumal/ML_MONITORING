import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "ml-anomaly"))

import app  # noqa: E402


def configure_test_app(monkeypatch):
    monkeypatch.setattr(app, "CONFIG_PATH", str(PROJECT_ROOT / "ml-anomaly" / "config.yaml"))
    monkeypatch.setattr(
        app,
        "UNSW_MODEL_PATH",
        str(PROJECT_ROOT / "ml-anomaly" / "models" / "unsw_nb15_model.joblib"),
    )
    app.cancel_attack_simulation()
    app.STATE["results"] = []
    app.STATE["last_error"] = ""


def test_threshold_policy_documents_hybrid_decision(monkeypatch):
    configure_test_app(monkeypatch)
    policy = app.threshold_policy()

    assert [band["name"] for band in policy["score_bands"]] == [
        "Normal",
        "Watch",
        "Warning",
        "Critical",
    ]
    assert policy["model"]["model_weight"] == 0.65
    assert policy["model"]["robust_weight"] == 0.35


def test_controlled_simulation_updates_portal_and_metrics(monkeypatch):
    configure_test_app(monkeypatch)
    monkeypatch.setattr(app, "safe_prometheus_value", lambda *_args, **_kwargs: 1.0)

    status = app.start_attack_simulation("latency_burst", 30)
    overview = app.portal_overview_payload()
    metrics_text = app.metrics().body.decode("utf-8")

    assert status["active"] is True
    assert overview["simulation"]["scenario"] == "latency_burst"
    assert overview["ml"]["peak_severity"] == "warning"
    assert overview["ml"]["training_evaluation"]["binary_f1"] > 0.89
    assert 'nhmf_attack_simulation_active{scenario="latency_burst"} 1.0' in metrics_text

    stopped = app.cancel_attack_simulation()
    assert stopped["active"] is False
    assert app.STATE["results"] == []
