#!/usr/bin/env bash
# Restore, register, activate, and verify the complete seven-server Zabbix demo fleet.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-nhmf}"

ZABBIX_SERVICES=(
  zabbix-db
  zabbix-server
  zabbix-web
  zabbix-agent
  zabbix-agent-application
  zabbix-agent-database
  zabbix-agent-security
  zabbix-agent-web
  zabbix-agent-api
  zabbix-agent-backup
)

for command_name in docker python3 curl; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "[ERROR] Required command is not installed: ${command_name}" >&2
    exit 1
  fi
done

echo "[1/4] Starting the Zabbix control plane and all seven monitored servers..."
docker compose up -d "${ZABBIX_SERVICES[@]}"

# Refresh the passive/active server allow-list resolution inside every agent
# after a possible Zabbix server container-address change.
docker compose restart \
  zabbix-agent \
  zabbix-agent-application \
  zabbix-agent-database \
  zabbix-agent-security \
  zabbix-agent-web \
  zabbix-agent-api \
  zabbix-agent-backup >/dev/null
sleep 5

echo "[2/4] Reconciling every Zabbix host interface with its current container address..."
python3 "$PROJECT_ROOT/scripts/zabbix_api_manager.py" --wait-seconds 180 setup-demo-hosts

echo "[3/4] Activating native monitoring for all seven hosts..."
python3 "$PROJECT_ROOT/scripts/zabbix_api_manager.py" --wait-seconds 60 activate-demo-hosts
curl -fsS -X POST "http://localhost:9090/-/reload" >/dev/null 2>&1 || true

echo -n "[4/4] Waiting for seven healthy native agents "
elapsed=0
while (( elapsed < 180 )); do
  snapshot="$(curl -fsS "http://localhost:8000/zabbix-health?refresh=true" 2>/dev/null || true)"
  healthy="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("summary", {}).get("healthy", 0))' <<<"$snapshot" 2>/dev/null || echo 0)"
  if [[ "$healthy" == "7" ]]; then
    echo "[OK]"
    python3 -m json.tool <<<"$snapshot"
    echo "Main dashboard:   http://localhost:8088"
    echo "Zabbix dashboard: http://localhost:3000/d/nhmf-zabbix/zabbix-infrastructure-host-dashboard"
    exit 0
  fi
  echo -n "."
  sleep 5
  elapsed=$((elapsed + 5))
done

echo "[NOT READY]" >&2
echo "The services are running and registered, but not all seven reached native HEALTHY within 180 seconds." >&2
python3 "$PROJECT_ROOT/scripts/zabbix_api_manager.py" status || true
echo "Check: docker compose logs --tail 120 zabbix-server zabbix-agent zabbix-agent-application" >&2
exit 1
