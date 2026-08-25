#!/usr/bin/env bash
# =============================================================================
# update_suricata_rules.sh — Update Suricata Emerging Threats Open rules
# Run this periodically (or on-demand) without restarting the stack.
# Usage: ./scripts/update_suricata_rules.sh
# =============================================================================
set -euo pipefail

CONTAINER_NAME="${COMPOSE_PROJECT_NAME:-nhmf}-suricata-1"

echo "════════════════════════════════════════════"
echo " NHMF — Suricata Rule Update"
echo "════════════════════════════════════════════"

# Check if container is running
if ! docker inspect --format='{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null | grep -q true; then
  echo "[WARN] Suricata container '$CONTAINER_NAME' is not running."
  echo "       Start the stack first with: ./scripts/start_stack.sh"
  exit 1
fi

echo "[INFO] Updating Emerging Threats Open ruleset inside container…"
docker exec "$CONTAINER_NAME" suricata-update \
  --suricata-conf /etc/suricata/suricata.yaml \
  --output /var/lib/suricata/rules

echo "[INFO] Sending SIGUSR2 to reload rules without restart…"
docker exec "$CONTAINER_NAME" kill -USR2 1

echo "[OK] Rules updated and reloaded."
echo "     Check alert activity in Grafana → Suricata IDS Dashboard"
