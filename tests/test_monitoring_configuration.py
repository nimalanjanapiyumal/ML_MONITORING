import json
import importlib.util
import time
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path: str) -> dict:
    return json.loads((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))


def load_yaml(relative_path: str) -> dict:
    return yaml.safe_load((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))


def load_module(relative_path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def panel_by_title(dashboard: dict, title: str) -> dict:
    return next(panel for panel in dashboard["panels"] if panel.get("title") == title)


def threshold_colors(panel: dict) -> list[str]:
    return [step["color"] for step in panel["fieldConfig"]["defaults"]["thresholds"]["steps"]]


def test_zabbix_demo_servers_are_deployed_and_probed():
    compose = load_yaml("docker-compose.yml")
    services = compose["services"]
    expected_agents = {
        "zabbix-agent",
        "zabbix-agent-application",
        "zabbix-agent-database",
        "zabbix-agent-security",
        "zabbix-agent-web",
        "zabbix-agent-api",
        "zabbix-agent-backup",
    }
    assert expected_agents <= services.keys()
    manager = load_module("scripts/zabbix_api_manager.py", "zabbix_fleet_definition_test")
    assert {host["dns"] for host in manager.DEMO_HOSTS} == expected_agents
    assert "zabbix-provisioner" not in services
    assert "suricata-demo-generator" not in services

    start_source = (PROJECT_ROOT / "scripts" / "start_stack.sh").read_text(encoding="utf-8")
    assert "setup-demo-hosts" in start_source
    assert "http://localhost:9090/-/reload" in start_source
    demo_source = (PROJECT_ROOT / "scripts" / "fault_injection" / "demo_scenarios.sh").read_text(
        encoding="utf-8"
    )
    assert "inject_suricata_demo_events.py" in demo_source
    assert "docker compose cp" in demo_source
    for agent_name in expected_agents:
        environment = services[agent_name]["environment"]
        assert environment["ZBX_PASSIVE_ALLOW"] == "true"
        assert environment["ZBX_PASSIVESERVERS"] == "zabbix-server"
        assert environment["ZBX_ACTIVE_ALLOW"] == "true"
        assert environment["ZBX_ACTIVESERVERS"] == "zabbix-server:10051"

    prometheus = load_yaml("configs/prometheus/prometheus.yml")
    jobs = {job["job_name"]: job for job in prometheus["scrape_configs"]}
    tcp_targets = set(jobs["blackbox-tcp"]["static_configs"][0]["targets"])
    assert {
        "zabbix-server:10051",
        "zabbix-db:3306",
        "zabbix-agent:10050",
        "zabbix-agent-application:10050",
        "zabbix-agent-database:10050",
        "zabbix-agent-security:10050",
        "zabbix-agent-web:10050",
        "zabbix-agent-api:10050",
        "zabbix-agent-backup:10050",
    } <= tcp_targets


def test_health_counts_use_real_probe_results_and_count_failed_targets():
    dashboard = load_json("configs/grafana/dashboards/network-health-dashboard.json")
    healthy_query = panel_by_title(dashboard, "Healthy Targets")["targets"][0]["expr"]
    unavailable_query = panel_by_title(dashboard, "Unavailable Targets")["targets"][0]["expr"]
    assert "count(up" in healthy_query and "probe_success" in healthy_query
    assert "count(up" in unavailable_query and "probe_success" in unavailable_query
    assert "== 0" in unavailable_query
    assert "sum(up" not in unavailable_query

    portal_source = (PROJECT_ROOT / "ml-anomaly" / "app.py").read_text(encoding="utf-8")
    assert 'count(up{job!~"blackbox-(icmp|http|tcp)"} == 0)' in portal_source
    assert 'count(probe_success{job=~"blackbox-(icmp|http|tcp)"} == 0)' in portal_source


def test_dashboard_risk_colors_and_numeric_boundaries_are_consistent():
    main = load_json("configs/grafana/dashboards/network-health-dashboard.json")
    ml = load_json("configs/grafana/dashboards/ml-anomaly-dashboard.json")
    zabbix = load_json("configs/grafana/dashboards/zabbix-infrastructure-dashboard.json")
    suricata = load_json("configs/grafana/dashboards/suricata-ids-dashboard.json")

    four_state = ["green", "yellow", "orange", "red"]
    for dashboard, title in (
        (main, "CPU Usage"),
        (main, "Memory Usage"),
        (main, "Disk Usage"),
        (main, "Peak Anomaly Score"),
        (ml, "Peak Anomaly Score"),
        (zabbix, "Filesystem Space Utilization (%)"),
        (suricata, "Alerts (Last Hour)"),
        (suricata, "Kernel Capture Drop Ratio"),
    ):
        assert threshold_colors(panel_by_title(dashboard, title)) == four_state

    cpu_steps = panel_by_title(main, "CPU Usage")["fieldConfig"]["defaults"]["thresholds"]["steps"]
    assert [step["value"] for step in cpu_steps] == [None, 70, 85, 95]
    score_steps = panel_by_title(main, "Peak Anomaly Score")["fieldConfig"]["defaults"]["thresholds"]["steps"]
    assert [step["value"] for step in score_steps] == [None, 0.5, 0.65, 0.85]


def test_suricata_dashboard_reports_sensor_freshness_and_capture_drop_ratio():
    dashboard = load_json("configs/grafana/dashboards/suricata-ids-dashboard.json")
    sensor_query = panel_by_title(dashboard, "Suricata Sensor Health")["targets"][0]["expr"]
    drop_query = panel_by_title(dashboard, "Kernel Capture Drop Ratio")["targets"][0]["expr"]
    assert "suricata_sensor_health" in sensor_query
    assert "suricata_stats_kernel_drop_ratio_percent" in drop_query

    exporter_source = (PROJECT_ROOT / "suricata-exporter" / "exporter.py").read_text(encoding="utf-8")
    assert '"suricata_sensor_health"' in exporter_source
    assert '"suricata_stats_kernel_drop_ratio_percent"' in exporter_source
    assert "SENSOR_STALE_AFTER_SECONDS" in exporter_source
    assert 'elif path == "/status"' in exporter_source
    compose = load_yaml("docker-compose.yml")
    assert "--af-packet=${SURICATA_INTERFACE:-eth0}" in compose["services"]["suricata"]["command"]
    assert "--init-errors-fatal" not in compose["services"]["suricata"]["command"]


def test_zabbix_dashboard_never_defaults_missing_services_to_online():
    dashboard_path = PROJECT_ROOT / "configs" / "grafana" / "dashboards" / "zabbix-infrastructure-dashboard.json"
    dashboard_text = dashboard_path.read_text(encoding="utf-8")
    dashboard = json.loads(dashboard_text)
    assert "or vector(1)" not in dashboard_text
    assert "zabbix-server:10051" in panel_by_title(dashboard, "Zabbix Server Daemon")["targets"][0]["expr"]
    assert "zabbix-db:3306" in panel_by_title(dashboard, "Zabbix MySQL Database")["targets"][0]["expr"]
    assert panel_by_title(dashboard, "Healthy Zabbix Servers")["targets"][0]["expr"] == (
        "count(zabbix_native_host_health == 2) or vector(0)"
    )
    assert panel_by_title(dashboard, "Unavailable Zabbix Servers")["targets"][0]["expr"] == (
        "count(zabbix_native_host_health == 0) or vector(0)"
    )
    all_targets = panel_by_title(dashboard, "All Zabbix Targets — Health Timeline")
    assert all_targets["type"] == "state-timeline"
    assert len(all_targets["targets"]) == 10
    fleet = panel_by_title(dashboard, "Native Zabbix Server Health Timeline")
    assert {target["legendFormat"] for target in fleet["targets"]} == {
        "Core Monitoring Server",
        "Application Server",
        "Database Server",
        "Security Server",
        "Web Server",
        "API Server",
        "Backup Server",
    }
    assert all(target["expr"].startswith("zabbix_native_host_health") for target in fleet["targets"])
    mappings = fleet["fieldConfig"]["defaults"]["mappings"][0]["options"]
    assert [(mappings[value]["color"], mappings[value]["text"]) for value in ("0", "1", "2")] == [
        ("red", "RISK / DOWN"),
        ("yellow", "WARNING / PENDING"),
        ("green", "HEALTHY"),
    ]
    activation = panel_by_title(dashboard, "Zabbix Host Activation Timeline")
    assert activation["type"] == "state-timeline"
    assert len(activation["targets"]) == 7
    assert all("zabbix_native_host_enabled" in target["expr"] for target in activation["targets"])
    activation_mappings = activation["fieldConfig"]["defaults"]["mappings"][0]["options"]
    assert activation_mappings == {
        "-1": {"color": "orange", "text": "UNKNOWN / API DOWN"},
        "0": {"color": "red", "text": "DEACTIVATED"},
        "1": {"color": "green", "text": "ACTIVE"},
    }
    assert panel_by_title(dashboard, "Healthy Zabbix Servers")["fieldConfig"]["defaults"]["max"] == 7
    assert panel_by_title(dashboard, "Unavailable Zabbix Servers")["fieldConfig"]["defaults"]["max"] == 7
    healthy_steps = panel_by_title(dashboard, "Healthy Zabbix Servers")["fieldConfig"]["defaults"]["thresholds"]["steps"]
    unavailable_steps = panel_by_title(dashboard, "Unavailable Zabbix Servers")["fieldConfig"]["defaults"]["thresholds"]["steps"]
    assert [(step["color"], step["value"]) for step in healthy_steps] == [
        ("red", None),
        ("orange", 5),
        ("yellow", 6),
        ("green", 7),
    ]
    assert [(step["color"], step["value"]) for step in unavailable_steps] == [
        ("green", None),
        ("yellow", 1),
        ("orange", 2),
        ("red", 3),
    ]


def test_outage_alerts_and_demo_scenarios_cover_suricata_and_zabbix():
    alerts = load_yaml("configs/prometheus/alert_rules.yml")
    alert_names = {
        rule["alert"]
        for group in alerts["groups"]
        for rule in group["rules"]
        if "alert" in rule
    }
    assert {
        "SuricataSensorDown",
        "SuricataExporterDown",
        "ZabbixServerUnreachable",
        "ZabbixDatabaseUnreachable",
        "ZabbixAgentUnreachable",
        "ZabbixAgentPending",
        "ZabbixNativeAPIUnavailable",
        "ZabbixFleetDegraded",
        "ZabbixFleetCritical",
    } <= alert_names

    demo_source = (PROJECT_ROOT / "scripts" / "fault_injection" / "demo_scenarios.sh").read_text(encoding="utf-8")
    for scenario in (
        "suricata-sensor-outage",
        "suricata-exporter-outage",
        "suricata-full-outage",
        "zabbix-server-outage",
        "zabbix-web-outage",
        "zabbix-control-plane-outage",
        "zabbix-core-agent-outage",
        "zabbix-application-outage",
        "zabbix-database-outage",
        "zabbix-security-outage",
        "zabbix-web-server-outage",
        "zabbix-api-server-outage",
        "zabbix-backup-server-outage",
        "zabbix-multi-server-outage",
        "zabbix-fleet-outage",
    ):
        assert scenario in demo_source
    assert "DURING OUTAGE — FINAL" in demo_source
    assert "alerts_in_window" in demo_source
    assert "zabbix-health?refresh=true" in demo_source

    portal_html = (PROJECT_ROOT / "ui-preview" / "index.html").read_text(encoding="utf-8")
    portal_js = (PROJECT_ROOT / "ui-preview" / "app.js").read_text(encoding="utf-8")
    assert 'id="zabbixFleetBody"' in portal_html
    assert "zabbix-application-outage 210" in portal_html
    assert "suricata-full-outage 150" in portal_html
    assert "updateZabbixFleet(data.zabbix)" in portal_js
    assert "changeZabbixHostActivation" in portal_js
    assert "/zabbix-hosts/" in portal_js


def test_suricata_stats_values_and_sensor_freshness(tmp_path, monkeypatch):
    exporter = load_module("suricata-exporter/exporter.py", "suricata_exporter_test")
    eve_path = tmp_path / "eve.json"
    eve_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(exporter, "EVE_JSON_PATH", str(eve_path))

    exporter.handle_stats(
        {
            "stats": {
                "uptime": 120,
                "capture": {"kernel_packets": 1000, "kernel_drops": 25},
            }
        }
    )

    assert exporter.suricata_uptime._value.get() == 120
    assert exporter.capture_packets._value.get() == 1000
    assert exporter.capture_kernel_drops._value.get() == 25
    assert exporter.capture_kernel_drop_ratio._value.get() == 2.5
    assert exporter._sensor_is_healthy() is True

    exporter._last_stats_observed_at = time.time() - exporter.SENSOR_STALE_AFTER_SECONDS - 1
    assert exporter._sensor_is_healthy() is False


def test_zabbix_existing_host_reconciliation_uses_host_massadd(monkeypatch):
    manager = load_module("scripts/zabbix_api_manager.py", "zabbix_api_manager_test")
    api = manager.ZabbixAPI()
    calls = []

    def fake_call(method, params=None):
        calls.append((method, params))
        if method == "host.get":
            return [
                {
                    "hostid": "10101",
                    "host": "NHMF Application Server",
                    "name": "NHMF Application Server",
                    "interfaces": [{"interfaceid": "20202", "type": "1", "main": "1"}],
                }
            ]
        return {}

    monkeypatch.setattr(api, "call", fake_call)
    monkeypatch.setattr(api, "get_linux_template_ids", lambda: [{"templateid": "10001"}])
    monkeypatch.setattr(api, "get_demo_group_id", lambda: "30001")
    result = api.ensure_host(
        "NHMF Application Server",
        "zabbix-agent-application",
        ip_address="172.30.0.12",
    )

    assert result["status"] == "updated"
    host_get = next(params for method, params in calls if method == "host.get")
    assert {"type", "main"} <= set(host_get["selectInterfaces"])
    interface_update = next(params for method, params in calls if method == "hostinterface.update")
    assert interface_update["ip"] == "172.30.0.12"
    assert interface_update["useip"] == 1
    assert not any(method == "hostinterface.create" for method, _params in calls)
    massadd = next(params for method, params in calls if method == "host.massadd")
    assert massadd == {
        "hosts": [{"hostid": "10101"}],
        "groups": [{"groupid": "30001"}],
        "templates": [{"templateid": "10001"}],
    }


def test_zabbix_demo_provisioning_continues_after_one_host_error(monkeypatch):
    manager = load_module("scripts/zabbix_api_manager.py", "zabbix_provisioning_retry_test")
    api = manager.ZabbixAPI()
    attempts = {}

    monkeypatch.setattr(manager, "resolve_compose_service_ip", lambda dns: f"172.30.0.{len(dns) % 100 + 10}")
    monkeypatch.setattr(manager.time, "sleep", lambda _seconds: None)

    def fake_ensure(hostname, dns, port="10050", ip_address=None):
        attempts[hostname] = attempts.get(hostname, 0) + 1
        if hostname == "Zabbix server":
            raise RuntimeError("simulated first-host API failure")
        return {
            "status": "created",
            "hostname": hostname,
            "dns": dns,
            "ip": ip_address,
            "useip": 1,
        }

    monkeypatch.setattr(api, "ensure_host", fake_ensure)
    results = api.setup_demo_hosts()
    assert len(results) == 7
    assert results[0]["status"] == "error"
    assert attempts["Zabbix server"] == 3
    assert {result["status"] for result in results[1:]} == {"created"}


def test_zabbix_native_health_requires_available_interface_and_fresh_agent_ping(monkeypatch):
    manager = load_module("scripts/zabbix_api_manager.py", "zabbix_native_health_test")
    api = manager.ZabbixAPI()
    now = int(time.time())
    hosts = []
    ping_items = []
    for index, demo_host in enumerate(manager.DEMO_HOSTS, start=1):
        host_id = str(10000 + index)
        hosts.append(
            {
                "hostid": host_id,
                "host": demo_host["hostname"],
                "name": demo_host["hostname"],
                "status": "0",
                "interfaces": [
                    {
                        "interfaceid": str(20000 + index),
                        "type": "1",
                        "main": "1",
                        "available": "1",
                        "error": "",
                    }
                ],
            }
        )
        ping_items.append(
            {
                "hostid": host_id,
                "key_": "agent.ping",
                "state": "0",
                "lastvalue": "1",
                "lastclock": str(now),
                "error": "",
            }
        )

    monkeypatch.setattr(api, "get_hosts", lambda: hosts)
    monkeypatch.setattr(api, "call", lambda method, _params=None: ping_items if method == "item.get" else {})
    health = api.get_demo_host_health()
    assert {target["health"] for target in health} == {"HEALTHY"}

    hosts[2]["interfaces"][0]["available"] = "2"
    health = api.get_demo_host_health()
    assert health[2]["health"] == "RISK / DOWN"


def test_suricata_demo_generator_populates_every_dashboard_event_type(tmp_path):
    generator = load_module(
        "scripts/fault_injection/inject_suricata_demo_events.py",
        "inject_suricata_demo_events_test",
    )
    eve_path = tmp_path / "eve.json"
    count = generator.inject_events("all", eve_path)
    events = [json.loads(line) for line in eve_path.read_text(encoding="utf-8").splitlines()]

    assert count == len(events)
    assert sum(event["event_type"] == "alert" for event in events) > 50
    assert {event["event_type"] for event in events} >= {
        "alert",
        "flow",
        "dns",
        "http",
        "tls",
        "ssh",
        "anomaly",
    }
    assert any(event.get("alert", {}).get("severity") == 1 for event in events)
