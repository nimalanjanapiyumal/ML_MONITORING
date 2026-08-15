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
check_url "Suricata Exporter"     "http://localhost:9517/health"
check_url "Zabbix Web"            "http://localhost:8080"

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
echo "[5] Suricata IDS Metrics Sample:"
curl -fsS "http://localhost:9517/metrics" 2>/dev/null | grep -E '^suricata_(alerts_total|alerts_last_window|stats_uptime_seconds|flow_bytes_total)' | head -n 10 || echo "Suricata metrics not yet reporting"

echo ""
echo "[6] ML Anomaly Detection State:"
curl -fsS "http://localhost:8000/results" 2>/dev/null | python3 -c '
import sys, json
try:
    results = json.load(sys.stdin)
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
echo "============================================================"
echo " Validation complete."
echo "============================================================"
