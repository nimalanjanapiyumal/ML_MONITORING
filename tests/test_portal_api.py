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


def test_native_zabbix_collection_publishes_all_server_health(monkeypatch):
    configure_test_app(monkeypatch)
    now = int(app.time.time())
    hosts = []
    items = []
    for index, definition in enumerate(app.ZABBIX_DEMO_HOSTS, start=1):
        host_id = str(10000 + index)
        hosts.append(
            {
                "hostid": host_id,
                "host": definition["host"],
                "name": definition["host"],
                "status": "0",
                "interfaces": [
                    {
                        "type": "1",
                        "main": "1",
                        "available": "1",
                        "useip": "0",
                        "dns": definition["target"],
                        "error": "",
                    }
                ],
            }
        )
        items.append(
            {
                "hostid": host_id,
                "key_": "agent.ping",
                "state": "0",
                "lastvalue": "1",
                "lastclock": str(now),
                "error": "",
            }
        )

    def fake_zabbix_call(method, _params=None, _auth=None):
        return {
            "apiinfo.version": "7.0.27",
            "user.login": "test-token",
            "host.get": hosts,
            "item.get": items,
        }[method]

    monkeypatch.setattr(app, "_zabbix_api_call", fake_zabbix_call)
    state = app.refresh_zabbix_native_state()
    metrics_text = app.metrics().body.decode("utf-8")

    assert state["api_up"] is True
    assert state["summary"] == {
        "healthy": 7,
        "warning": 0,
        "risk_down": 0,
        "registered": 7,
        "active": 7,
        "deactivated": 0,
        "total": 7,
    }
    assert {host["state"] for host in state["hosts"]} == {"HEALTHY"}
    assert "zabbix_native_api_up 1.0" in metrics_text
    assert metrics_text.count("zabbix_native_host_health{") == 7
    assert metrics_text.count("zabbix_native_host_enabled{") == 7

    hosts[2]["interfaces"][0]["available"] = "2"
    state = app.refresh_zabbix_native_state()
    assert state["summary"]["healthy"] == 6
    assert state["summary"]["risk_down"] == 1
    assert state["hosts"][2]["state"] == "RISK / DOWN"

    hosts[2]["status"] = "1"
    state = app.refresh_zabbix_native_state()
    assert state["summary"]["active"] == 6
    assert state["summary"]["deactivated"] == 1
    assert state["hosts"][2]["state"] == "DEACTIVATED"


def test_zabbix_activation_is_restricted_and_updates_native_host(monkeypatch):
    calls = []

    def fake_zabbix_call(method, params=None, auth=None):
        calls.append((method, params, auth))
        if method == "user.login":
            return "test-token"
        if method == "host.get":
            return [{"hostid": "10101", "host": "NHMF Application Server", "status": "0"}]
        if method == "host.update":
            return {"hostids": ["10101"]}
        raise AssertionError(method)

    refreshed = {
        "summary": {"active": 6, "deactivated": 1, "total": 7},
        "hosts": [
            {
                "target": "zabbix-agent-application",
                "role": "Application Server",
                "enabled": False,
                "state": "DEACTIVATED",
            }
        ],
    }
    monkeypatch.setattr(app, "_zabbix_api_call", fake_zabbix_call)
    monkeypatch.setattr(app, "refresh_zabbix_native_state", lambda: refreshed)

    result = app.set_zabbix_host_activation("zabbix-agent-application", False)
    update = next(params for method, params, _auth in calls if method == "host.update")
    assert update == {"hostid": "10101", "status": 1}
    assert result["host"]["state"] == "DEACTIVATED"

    try:
        app.set_zabbix_host_activation("not-an-allowed-server", True)
    except ValueError as exc:
        assert "Unknown NHMF lab server" in str(exc)
    else:
        raise AssertionError("Unknown targets must not be accepted")
