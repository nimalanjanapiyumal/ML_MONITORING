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
  zabbix-fleet-online          Repair/register/activate all seven servers and verify green baseline
  zabbix-monitoring-toggle     Deactivate all seven in Zabbix, then restore them automatically
  zabbix-core-agent-outage     Stop the Core Monitoring Server agent
  zabbix-application-outage    Stop the Application Server agent
  zabbix-database-outage       Stop the Database Server agent
  zabbix-security-outage       Stop the Security Server agent
  zabbix-web-server-outage     Stop the dummy Web Server agent
  zabbix-api-server-outage     Stop the dummy API Server agent
  zabbix-backup-server-outage  Stop the dummy Backup Server agent
  zabbix-multi-server-outage   Stop Web, API, and Backup agents together (7 healthy -> 4)
  zabbix-fleet-outage          Stop all seven monitored server agents

Combined security and availability scenario:
  attack-and-server-outage     Inject all Suricata threats, then stop the Application Server agent

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
  ./scripts/fault_injection/demo_scenarios.sh zabbix-monitoring-toggle 60
  ./scripts/fault_injection/demo_scenarios.sh attack-and-server-outage 90
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

show_zabbix_native_snapshot() {
  echo "Native Zabbix host state (the same values used by Grafana):"
  curl -fsS "http://localhost:8000/zabbix-health?refresh=true" 2>/dev/null | python3 -c '
import json, sys
payload = json.load(sys.stdin)
summary = payload.get("summary", {})
api_state = "UP" if payload.get("api_up") else "DOWN"
print("  API={}; registered={}/7; healthy={}; warning={}; risk/down={}; unreachable={}; unknown={}".format(api_state, summary.get("registered", 0), summary.get("healthy", 0), summary.get("warning", 0), summary.get("risk_down", 0), summary.get("unreachable", 0), summary.get("unknown", 0)))
for host in payload.get("hosts", []):
    print("  - [{}] {} ({})".format(host.get("state", "UNKNOWN"), host.get("role"), host.get("host")))
' || echo "  [NO DATA] Native Zabbix collector did not respond. Check: docker compose logs --tail 100 ml-anomaly zabbix-web"
}

show_suricata_snapshot() {
  echo "Suricata IDS state (the same values used by Grafana):"
  curl -fsS "http://localhost:9517/status" 2>/dev/null | python3 -c '
import json, sys
payload = json.load(sys.stdin)
eve_state = "available" if payload.get("eve_file_available") else "missing"
print("  Exporter={}; sensor={}; EVE file={}".format(payload.get("exporter", "unknown"), payload.get("sensor", "unknown"), eve_state))
print("  Processed events={}; alerts in window={}; last stats age={}".format(payload.get("events_processed", 0), payload.get("alerts_in_window", 0), payload.get("last_stats_age_seconds")))
' || echo "  [NO DATA] Suricata exporter did not respond. Check: docker compose logs --tail 100 suricata suricata-exporter"
}

show_outage_snapshot() {
  local phase="$1"
  shift
  local services=("$@")
  echo ""
  echo -e "${BLUE}[${phase}] Container evidence:${NC}"
  docker compose ps --all --format "table {{.Service}}\t{{.Status}}" "${services[@]}" 2>/dev/null || true
  case " ${services[*]} " in
    *" zabbix"*) show_zabbix_native_snapshot ;;
  esac
  case " ${services[*]} " in
    *" suricata"*) show_suricata_snapshot ;;
  esac
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
  show_outage_snapshot "BEFORE" "$service"
  docker compose stop "$service"
  echo -e "${RED}[OUTAGE ACTIVE] Open Grafana and wait for the configured alert persistence period.${NC}"
  local evidence_delay=30
  (( DURATION < evidence_delay )) && evidence_delay="$DURATION"
  sleep "$evidence_delay"
  show_outage_snapshot "DURING OUTAGE" "$service"
  if (( DURATION > evidence_delay )); then
    sleep "$((DURATION - evidence_delay))"
    show_outage_snapshot "DURING OUTAGE — FINAL" "$service"
  fi
  restore_service
  trap - EXIT INT TERM
  sleep 8
  show_outage_snapshot "AFTER RECOVERY" "$service"
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
  show_outage_snapshot "BEFORE" "${services[@]}"
  docker compose stop "${services[@]}"
  echo -e "${RED}[OUTAGE ACTIVE] Open the relevant dashboard and observe each named target.${NC}"
  local evidence_delay=30
  (( DURATION < evidence_delay )) && evidence_delay="$DURATION"
  sleep "$evidence_delay"
  show_outage_snapshot "DURING OUTAGE" "${services[@]}"
  if (( DURATION > evidence_delay )); then
    sleep "$((DURATION - evidence_delay))"
    show_outage_snapshot "DURING OUTAGE — FINAL" "${services[@]}"
  fi
  restore_services
  trap - EXIT INT TERM
  sleep 8
  show_outage_snapshot "AFTER RECOVERY" "${services[@]}"
  echo -e "${GREEN}[RECOVERED] All scenario services were restarted. Confirm every target returns to green.${NC}"
}

run_suricata_demo() {
  local demo_case="$1"
  local event_file
  local before_events
  local before_alerts
  event_file="$(mktemp)"

  if ! curl -fsS "http://localhost:9517/-/healthy" >/dev/null 2>&1; then
    echo "[FAILED] Suricata exporter is not responding. Start it before running a detection scenario." >&2
    echo "Check: docker compose logs --tail 100 suricata suricata-exporter" >&2
    rm -f "$event_file"
    return 1
  fi
  before_events="$(curl -fsS "http://localhost:9517/status" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("events_processed", 0))')"
  before_alerts="$(curl -fsS "http://localhost:9517/status" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("alerts_in_window", 0))')"
  show_suricata_snapshot

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

  local observed_events="$before_events"
  local observed_alerts="$before_alerts"
  local waited=0
  while (( waited < 20 )); do
    sleep 2
    waited=$((waited + 2))
    observed_events="$(curl -fsS "http://localhost:9517/status" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("events_processed", 0))' 2>/dev/null || echo 0)"
    observed_alerts="$(curl -fsS "http://localhost:9517/status" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("alerts_in_window", 0))' 2>/dev/null || echo 0)"
    if (( observed_events > before_events && observed_alerts > before_alerts )); then
      show_suricata_snapshot
      echo -e "${GREEN}[VERIFIED] Suricata exporter processed $((observed_events - before_events)) new EVE records and $((observed_alerts - before_alerts)) new IDS alerts. Grafana will refresh within 15 seconds.${NC}"
      return 0
    fi
  done

  show_suricata_snapshot
  echo -e "${RED}[FAILED] Events were written but the exporter did not process them within 20 seconds.${NC}" >&2
  echo "Check: docker compose logs --tail 100 suricata suricata-exporter" >&2
  return 1
}

run_zabbix_monitoring_toggle() {
  validate_duration

  restore_monitoring() {
    echo -e "\n${YELLOW}[RECOVERY] Activating all seven Zabbix hosts...${NC}"
    python3 "$PROJECT_ROOT/scripts/zabbix_api_manager.py" --wait-seconds 60 activate-demo-hosts >/dev/null 2>&1 || true
    curl -fsS "http://localhost:8000/zabbix-health?refresh=true" >/dev/null 2>&1 || true
  }
  trap restore_monitoring EXIT INT TERM

  echo -e "${BLUE}[SCENARIO] Deactivating native monitoring for all seven hosts for ${DURATION} seconds.${NC}"
  show_zabbix_native_snapshot
  python3 "$PROJECT_ROOT/scripts/zabbix_api_manager.py" --wait-seconds 60 deactivate-demo-hosts
  curl -fsS "http://localhost:8000/zabbix-health?refresh=true" >/dev/null 2>&1 || true
  sleep 5
  echo -e "${RED}[MONITORING OFF] Main portal rows and the Grafana activation timeline should now be red.${NC}"
  show_zabbix_native_snapshot
  sleep "$DURATION"
  restore_monitoring
  trap - EXIT INT TERM
  sleep 10
  show_zabbix_native_snapshot
  echo -e "${GREEN}[RECOVERED] All seven Zabbix hosts are active again.${NC}"
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
  zabbix-fleet-online)
    bash "$PROJECT_ROOT/scripts/repair_zabbix_fleet.sh"
    ;;
  zabbix-monitoring-toggle)
    run_zabbix_monitoring_toggle
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
  attack-and-server-outage)
    run_suricata_demo "all"
    run_outage "zabbix-agent-application" "Suricata alerts remain visible while Application Server becomes red; the correlation panel reports ATTACK + SERVER OUTAGE."
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
