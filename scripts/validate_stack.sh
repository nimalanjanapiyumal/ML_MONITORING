#!/usr/bin/env bash
# =============================================================================
# validate_stack.sh — Validate all NHMF monitoring and security components
# =============================================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ".env"
  set +a
fi

GRAFANA_ADMIN_USER="${GRAFANA_ADMIN_USER:-admin}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-admin123}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_url() {
  local name="$1"
  local url="$2"
  printf "  %-30s " "$name"
  if curl -fsS "$url" >/dev/null 2>&1; then
    echo -e "${GREEN}[OK]${NC} ($url)"
  else
    echo -e "${RED}[FAILED]${NC} ($url)"
  fi
}

echo "============================================================"
echo " NHMF — Stack Validation & Health Check"
echo "============================================================"
echo ""
echo "[1] Container Status:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "[2] Endpoint Health Checks:"
check_url "Prometheus"            "http://localhost:9090/-/healthy"
check_url "Alertmanager"          "http://localhost:9093/-/healthy"
check_url "Grafana"               "http://localhost:3000/api/health"
check_url "ML Anomaly API"        "http://localhost:8000/health"
check_url "Operations Portal"     "http://localhost:8088"
check_url "Suricata Exporter"     "http://localhost:9517/-/healthy"
check_url "Suricata Sensor"       "http://localhost:9517/health"
check_url "Suricata Status Data"  "http://localhost:9517/status"
check_url "Zabbix Web"            "http://localhost:8080"
check_url "Native Zabbix Data"    "http://localhost:8000/zabbix-health"

echo ""
echo "[3] Grafana Dashboards Provisioned:"
curl -fsS -u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" "http://localhost:3000/api/search?folderIds=0" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "Could not query Grafana API"

echo ""
echo "[4] Prometheus Scrape Targets:"
curl -fsS "http://localhost:9090/api/v1/targets" 2>/dev/null | python3 -c '
import sys, json
try:
    data = json.load(sys.stdin)
    targets = data.get("data", {}).get("activeTargets", [])
    print(f"Total active scrape targets: {len(targets)}")
    for t in targets:
        job = t.get("labels", {}).get("job", "unknown")
        url = t.get("scrapeUrl", "")
        health = t.get("health", "")
        print(f"  - [{health.upper()}] job={job} ({url})")
except Exception as e:
    print(f"Error parsing targets: {e}")
' 2>/dev/null || echo "Could not query Prometheus targets"

echo ""
echo "[5] Monitored Endpoint Health (real probe result):"
curl -fsSG --data-urlencode "query=probe_success" "http://localhost:9090/api/v1/query" 2>/dev/null | python3 -c '
import sys, json
try:
    payload = json.load(sys.stdin)
    results = payload.get("data", {}).get("result", [])
    healthy = 0
    down = 0
    for result in sorted(results, key=lambda item: item.get("metric", {}).get("target", "")):
        target = result.get("metric", {}).get("target", "unknown")
        job = result.get("metric", {}).get("job", "unknown")
        value = float(result.get("value", [0, "0"])[1])
        state = "HEALTHY" if value == 1 else "RISK / DOWN"
        healthy += value == 1
        down += value != 1
        print(f"  - [{state}] {target} ({job})")
    print(f"Probe totals: {healthy} healthy, {down} unavailable, {len(results)} total")
except Exception as exc:
    print(f"Could not parse endpoint health: {exc}")
' || echo "Could not query probe health"

echo ""
echo "[6] Suricata IDS Metrics Sample:"
curl -fsS "http://localhost:9517/metrics" 2>/dev/null | grep -E '^suricata_(sensor_health|alerts_total|alerts_last_window|stats_uptime_seconds|stats_kernel_drop_ratio_percent|flow_bytes_total)' | head -n 12 || echo "Suricata metrics not yet reporting"
echo "Suricata readable status:"
curl -fsS "http://localhost:9517/status" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "Suricata status did not respond"

echo ""
echo "[7] ML Anomaly Detection State:"
curl -fsS "http://localhost:8000/results" 2>/dev/null | python3 -c '
import sys, json
try:
    payload = json.load(sys.stdin)
    results = payload.get("results", [])
    print(f"Total evaluated telemetry metrics: {len(results)}")
    for r in results[:5]:
        m = r.get("metric_name", "")
        t = r.get("target", "")
        s = r.get("score", 0)
        sev = r.get("severity", "")
        print(f"  - {m} [{t}]: score={s:.4f} severity={sev}")
except Exception as e:
    print("No ML results currently cached.")
' 2>/dev/null || echo "Could not query ML results"

echo ""
echo "[8] Zabbix Registered Server Fleet and Native Agent Health:"
curl -fsS "http://localhost:8000/zabbix-health?refresh=true" 2>/dev/null | python3 -c '
import json, sys
payload = json.load(sys.stdin)
summary = payload.get("summary", {})
print("Grafana native collector: API={} registered={}/{} healthy={} warning={} risk/down={}".format(
    "UP" if payload.get("api_up") else "DOWN",
    summary.get("registered", 0), summary.get("total", 7), summary.get("healthy", 0),
    summary.get("warning", 0), summary.get("risk_down", 0)))
for host in payload.get("hosts", []):
    print("  - [{}] {} ({})".format(host.get("state"), host.get("role"), host.get("host")))
' || echo "Could not query the native Zabbix data used by Grafana"
python3 "$PROJECT_ROOT/scripts/zabbix_api_manager.py" status || echo "Could not query the Zabbix API"

echo ""
echo "[9] Demo Scenario Coverage:"
bash "$PROJECT_ROOT/scripts/fault_injection/demo_scenarios.sh" list | grep -E 'outage|suricata-(scan|icmp|http|c2|threats-all)' || echo "Could not list demo scenarios"

echo ""
echo "============================================================"
echo " Validation complete."
echo "============================================================"
