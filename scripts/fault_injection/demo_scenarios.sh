#!/usr/bin/env bash
# =============================================================================
# demo_scenarios.sh — Repeatable NHMF dashboard and outage demonstrations
# =============================================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

SCENARIO="${1:-list}"
DURATION="${2:-90}"
TARGET_OR_INTERFACE="${3:-}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
  cat <<'EOF'
Usage: ./scripts/fault_injection/demo_scenarios.sh <scenario> [duration_seconds] [interface]

Availability scenarios (real, automatically restored):
  suricata-sensor-outage     Stop packet inspection; exporter stays up and reports stale sensor health
  suricata-exporter-outage   Stop the Suricata metrics exporter
  zabbix-server-outage       Stop the Zabbix server daemon
  zabbix-application-outage  Stop the Application Server agent
  zabbix-database-outage     Stop the Database Server agent
  zabbix-security-outage     Stop the Security Server agent
  zabbix-db-outage           Stop the Zabbix MySQL service
  ml-outage                  Stop the ML anomaly API

Suricata detection scenarios (deterministic synthetic EVE records):
  suricata-scan              TCP SYN port-scan signature
  suricata-icmp              ICMP flood signature
  suricata-http              Cleartext HTTP Basic Auth signature
  suricata-c2                Suspicious TCP/4444 signature
  suricata-threats-all       Run all four cases and populate DNS/TLS/SSH views

Resource scenarios:
  cpu                        CPU saturation
  memory                     Memory pressure
  latency                    100 ms delay and 5% packet loss (third argument is interface)

Examples:
  ./scripts/fault_injection/demo_scenarios.sh suricata-sensor-outage 90
  ./scripts/fault_injection/demo_scenarios.sh zabbix-application-outage 120
  ./scripts/fault_injection/demo_scenarios.sh suricata-scan
  sudo ./scripts/fault_injection/demo_scenarios.sh latency 90 eth0
EOF
}

validate_duration() {
  if ! [[ "$DURATION" =~ ^[0-9]+$ ]] || (( DURATION < 30 || DURATION > 300 )); then
    echo "Duration must be an integer from 30 to 300 seconds." >&2
    exit 2
  fi
}

run_outage() {
  local service="$1"
  local observation="$2"
  validate_duration

  restore_service() {
    echo -e "\n${YELLOW}[RECOVERY] Starting ${service}...${NC}"
    docker compose start "$service" >/dev/null 2>&1 || true
  }
  trap restore_service EXIT INT TERM

  echo -e "${BLUE}[SCENARIO] Stopping ${service} for ${DURATION} seconds.${NC}"
  echo "Expected observation: ${observation}"
  docker compose stop "$service"
  echo -e "${RED}[OUTAGE ACTIVE] Open Grafana and wait for the configured alert persistence period.${NC}"
  sleep "$DURATION"
  restore_service
  trap - EXIT INT TERM
  echo -e "${GREEN}[RECOVERED] ${service} was restarted. Confirm the dashboard returns to green.${NC}"
}

run_suricata_demo() {
  local demo_case="$1"
  docker compose --profile demo run --rm --no-deps suricata-demo-generator "$demo_case"
  echo -e "${GREEN}[OK] Synthetic EVE records submitted. Allow up to 15 seconds for Prometheus and Grafana refresh.${NC}"
}

case "$SCENARIO" in
  list|-h|--help)
    usage
    ;;
  suricata-sensor-outage)
    run_outage "suricata" "Suricata Sensor Health becomes red after 30 seconds while exporter liveness remains available; SuricataSensorDown fires."
    ;;
  suricata-exporter-outage)
    run_outage "suricata-exporter" "Suricata Sensor Health becomes red immediately after the failed scrape; SuricataExporterDown fires after 2 minutes."
    ;;
  zabbix-server-outage)
    run_outage "zabbix-server" "Zabbix Server Daemon becomes red and the TCP/10051 availability series drops to 0."
    ;;
  zabbix-application-outage)
    run_outage "zabbix-agent-application" "Application Server becomes red; Healthy Zabbix Servers changes from 4 to 3."
    ;;
  zabbix-database-outage)
    run_outage "zabbix-agent-database" "Database Server becomes red; Healthy Zabbix Servers changes from 4 to 3."
    ;;
  zabbix-security-outage)
    run_outage "zabbix-agent-security" "Security Server becomes red; Healthy Zabbix Servers changes from 4 to 3."
    ;;
  zabbix-db-outage)
    run_outage "zabbix-db" "Zabbix MySQL Database becomes red; Zabbix Web and Server may also degrade until MySQL recovers."
    ;;
  ml-outage)
    run_outage "ml-anomaly" "ML API status and its direct scrape target become red; TargetDown fires after 2 minutes."
    ;;
  suricata-scan)
    run_suricata_demo "scan"
    ;;
  suricata-icmp)
    run_suricata_demo "icmp"
    ;;
  suricata-http)
    run_suricata_demo "http"
    ;;
  suricata-c2)
    run_suricata_demo "c2"
    ;;
  suricata-threats-all)
    run_suricata_demo "all"
    ;;
  cpu)
    validate_duration
    bash "$PROJECT_ROOT/scripts/fault_injection/cpu_stress.sh" "$DURATION"
    ;;
  memory)
    validate_duration
    bash "$PROJECT_ROOT/scripts/fault_injection/memory_stress.sh" "$DURATION"
    ;;
  latency)
    validate_duration
    if [[ -z "$TARGET_OR_INTERFACE" ]]; then
      echo "The latency scenario requires a network interface as the third argument (for example, eth0)." >&2
      exit 2
    fi
    bash "$PROJECT_ROOT/scripts/fault_injection/latency_packetloss.sh" "$TARGET_OR_INTERFACE" "100ms" "5%" "$DURATION"
    ;;
  *)
    echo "Unknown scenario: $SCENARIO" >&2
    usage >&2
    exit 2
    ;;
esac
