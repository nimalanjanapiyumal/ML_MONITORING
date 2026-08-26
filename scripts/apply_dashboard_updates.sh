#!/usr/bin/env bash
# Apply the latest NHMF portal, Grafana dashboards, and control API after a pull/import.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-nhmf}"
PORTAL_BUILD_ID="2026.08.26-zabbix-attack-demo-v2"

for command_name in docker curl; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "[ERROR] Required command is not installed: ${command_name}" >&2
    exit 1
  fi
done

docker compose version >/dev/null

echo "Recreating the portal and Grafana with the imported dashboard files..."
docker compose up -d --force-recreate --no-deps portal grafana

echo -n "Waiting for dashboard build ${PORTAL_BUILD_ID} "
elapsed=0
while (( elapsed < 90 )); do
  payload="$(curl -fsS "http://localhost:8088/version" 2>/dev/null || true)"
  if grep -Fq "\"build\":\"${PORTAL_BUILD_ID}\"" <<<"$payload"; then
    echo "[OK]"
    break
  fi
  echo -n "."
  sleep 3
  elapsed=$((elapsed + 3))
done

if ! grep -Fq "\"build\":\"${PORTAL_BUILD_ID}\"" <<<"${payload:-}"; then
  echo "[FAILED]" >&2
  echo "Expected portal build: ${PORTAL_BUILD_ID}" >&2
  echo "Received: ${payload:-no response}" >&2
  echo "Check: docker compose logs --tail 120 portal" >&2
  exit 1
fi

echo "Applying the latest portal control API..."
if ! docker compose up -d --build ml-anomaly; then
  echo "[WARN] The new dashboard is deployed, but the control API could not be rebuilt." >&2
  echo "       This is commonly caused by Docker Hub DNS access. Fix Docker DNS, then rerun this command." >&2
fi

if command -v python3 >/dev/null 2>&1; then
  echo "Reconciling current container addresses and activating all seven Zabbix hosts..."
  docker compose restart \
    zabbix-agent \
    zabbix-agent-application \
    zabbix-agent-database \
    zabbix-agent-security \
    zabbix-agent-web \
    zabbix-agent-api \
    zabbix-agent-backup >/dev/null 2>&1 || true
  sleep 5
  if python3 "$PROJECT_ROOT/scripts/zabbix_api_manager.py" --wait-seconds 120 setup-demo-hosts && \
     python3 "$PROJECT_ROOT/scripts/zabbix_api_manager.py" --wait-seconds 60 activate-demo-hosts; then
    curl -fsS "http://localhost:8000/zabbix-health?refresh=true" >/dev/null 2>&1 || true
    echo "[OK] Seven-server Zabbix fleet reconciled and activated."
  else
    echo "[WARN] Automatic Zabbix reconciliation did not complete." >&2
    echo "       Run: bash scripts/repair_zabbix_fleet.sh" >&2
  fi
else
  echo "[WARN] python3 is unavailable; run scripts/repair_zabbix_fleet.sh after installing Python 3." >&2
fi

echo "Main dashboard: http://localhost:8088"
echo "Zabbix dashboard: http://localhost:3000/d/nhmf-zabbix/zabbix-infrastructure-host-dashboard"
echo "If a browser tab was already open, refresh it once (Ctrl+Shift+R)."
