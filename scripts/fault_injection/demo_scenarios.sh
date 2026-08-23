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

Suricata availability scenarios (real, automatically restored):
  suricata-sensor-outage       Stop packet inspection only; exporter remains available
  suricata-exporter-outage     Stop the metrics exporter only; sensor continues inspecting
  suricata-full-outage         Stop both the IDS sensor and metrics exporter

Zabbix control-plane scenarios (real, automatically restored):
  zabbix-server-outage         Stop the Zabbix server daemon only
  zabbix-web-outage            Stop the Zabbix Web UI/API only
  zabbix-db-outage             Stop the Zabbix MySQL database
  zabbix-control-plane-outage  Stop the Zabbix server daemon and Web UI/API together

Zabbix monitored-server scenarios (seven independently monitored lab servers):
  zabbix-core-agent-outage     Stop the Core Monitoring Server agent
  zabbix-application-outage    Stop the Application Server agent
  zabbix-database-outage       Stop the Database Server agent
  zabbix-security-outage       Stop the Security Server agent
  zabbix-web-server-outage     Stop the dummy Web Server agent
  zabbix-api-server-outage     Stop the dummy API Server agent
  zabbix-backup-server-outage  Stop the dummy Backup Server agent
  zabbix-multi-server-outage   Stop Web, API, and Backup agents together (7 healthy -> 4)
  zabbix-fleet-outage          Stop all seven monitored server agents

Other availability scenarios:
  ml-outage                    Stop the ML anomaly API

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
  ./scripts/fault_injection/demo_scenarios.sh suricata-sensor-outage 150
  ./scripts/fault_injection/demo_scenarios.sh suricata-full-outage 150
  ./scripts/fault_injection/demo_scenarios.sh zabbix-server-outage 210
  ./scripts/fault_injection/demo_scenarios.sh zabbix-web-server-outage 210
  ./scripts/fault_injection/demo_scenarios.sh zabbix-multi-server-outage 210
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

run_multi_outage() {
  local observation="$1"
  shift
  local services=("$@")
  validate_duration

  restore_services() {
    echo -e "\n${YELLOW}[RECOVERY] Starting ${services[*]}...${NC}"
    docker compose start "${services[@]}" >/dev/null 2>&1 || true
  }
  trap restore_services EXIT INT TERM

  echo -e "${BLUE}[SCENARIO] Stopping ${services[*]} for ${DURATION} seconds.${NC}"
  echo "Expected observation: ${observation}"
  docker compose stop "${services[@]}"
  echo -e "${RED}[OUTAGE ACTIVE] Open the relevant dashboard and observe each named target.${NC}"
  sleep "$DURATION"
  restore_services
  trap - EXIT INT TERM
  echo -e "${GREEN}[RECOVERED] All scenario services were restarted. Confirm every target returns to green.${NC}"
}

run_suricata_demo() {
  local demo_case="$1"
  local event_file
  event_file="$(mktemp)"

  if ! python3 "$PROJECT_ROOT/scripts/fault_injection/inject_suricata_demo_events.py" \
    "$demo_case" --output "$event_file"; then
    rm -f "$event_file"
    return 1
  fi

  if ! docker compose cp "$event_file" suricata:/tmp/nhmf-demo-events.json; then
    rm -f "$event_file"
    return 1
  fi
  rm -f "$event_file"

  docker compose exec -T suricata sh -c \
    'cat /tmp/nhmf-demo-events.json >> /var/log/suricata/eve.json && rm -f /tmp/nhmf-demo-events.json'
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
  suricata-full-outage)
    run_multi_outage "Both Suricata sensor and exporter dashboard health become red; SuricataExporterDown confirms complete IDS visibility loss." \
      "suricata" "suricata-exporter"
    ;;
  zabbix-server-outage)
    run_outage "zabbix-server" "Zabbix Server Daemon becomes red and the TCP/10051 availability series drops to 0."
    ;;
  zabbix-web-outage)
    run_outage "zabbix-web" "Zabbix Web UI/API becomes red while the server daemon, database, and agent TCP endpoints remain independently visible."
    ;;
  zabbix-control-plane-outage)
    run_multi_outage "Zabbix Web UI/API and Server Daemon become red together while MySQL and agent endpoints show their independent state." \
      "zabbix-server" "zabbix-web"
    ;;
  zabbix-core-agent-outage)
    run_outage "zabbix-agent" "Core Monitoring Server becomes red; Healthy Zabbix Servers changes from 7 to 6."
    ;;
  zabbix-application-outage)
    run_outage "zabbix-agent-application" "Application Server becomes red; Healthy Zabbix Servers changes from 7 to 6."
    ;;
  zabbix-database-outage)
    run_outage "zabbix-agent-database" "Database Server becomes red; Healthy Zabbix Servers changes from 7 to 6."
    ;;
  zabbix-security-outage)
    run_outage "zabbix-agent-security" "Security Server becomes red; Healthy Zabbix Servers changes from 7 to 6."
    ;;
  zabbix-web-server-outage)
    run_outage "zabbix-agent-web" "Web Server becomes red; Healthy Zabbix Servers changes from 7 to 6."
    ;;
  zabbix-api-server-outage)
    run_outage "zabbix-agent-api" "API Server becomes red; Healthy Zabbix Servers changes from 7 to 6."
    ;;
  zabbix-backup-server-outage)
    run_outage "zabbix-agent-backup" "Backup Server becomes red; Healthy Zabbix Servers changes from 7 to 6."
    ;;
  zabbix-multi-server-outage)
    run_multi_outage "Web, API, and Backup servers become red; healthy count drops from 7 to 4 and unavailable count crosses the red boundary." \
      "zabbix-agent-web" "zabbix-agent-api" "zabbix-agent-backup"
    ;;
  zabbix-fleet-outage)
    run_multi_outage "All seven server rows become red and the healthy count reaches 0, demonstrating complete monitored-fleet loss." \
      "zabbix-agent" "zabbix-agent-application" "zabbix-agent-database" "zabbix-agent-security" \
      "zabbix-agent-web" "zabbix-agent-api" "zabbix-agent-backup"
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
