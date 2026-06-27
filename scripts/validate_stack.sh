#!/usr/bin/env bash
set -euo pipefail

check_url() {
  local name="$1"
  local url="$2"
  echo -n "Checking $name ... "
  if curl -fsS "$url" >/dev/null; then
    echo "OK"
  else
    echo "FAILED"
  fi
}

echo "Container status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
check_url "Prometheus" "http://localhost:9090/-/healthy"
check_url "Alertmanager" "http://localhost:9093/-/healthy"
check_url "Grafana" "http://localhost:3000/api/health"
check_url "ML anomaly API" "http://localhost:8000/health"

echo ""
echo "Prometheus targets summary:"
curl -fsS "http://localhost:9090/api/v1/targets" | python3 -m json.tool | head -80 || true

echo ""
echo "ML anomaly results:"
curl -fsS "http://localhost:8000/results" | python3 -m json.tool || true
