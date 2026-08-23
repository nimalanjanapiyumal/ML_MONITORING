#!/usr/bin/env bash
# =============================================================================
# setup_zabbix.sh — Zabbix Automated Provisioning & Verification Wrapper
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ".env"
  set +a
fi

ZABBIX_URL="${ZABBIX_URL:-http://localhost:8080/api_jsonrpc.php}"
ZABBIX_USER="${ZABBIX_ADMIN_USER:-Admin}"
ZABBIX_PASSWORD="${ZABBIX_ADMIN_PASSWORD:-zabbix}"

ACTION="${1:-status}"

echo "============================================================"
echo " NHMF — Zabbix Infrastructure Manager"
echo " Endpoint: $ZABBIX_URL | Action: $ACTION"
echo "============================================================"

echo "Checking Zabbix API availability (up to 60 seconds)..."

python3 "$SCRIPT_DIR/zabbix_api_manager.py" \
  --url "$ZABBIX_URL" \
  --user "$ZABBIX_USER" \
  --password "$ZABBIX_PASSWORD" \
  --wait-seconds 60 \
  "$ACTION" "${@:2}"

echo "============================================================"
