#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-nhmf}"

PORTAL_BUILD_ID="2026.08.26-zabbix-attack-demo-v2"

RETRAIN="${NHMF_RETRAIN:-0}"
SKIP_TRAIN="${NHMF_SKIP_TRAIN:-0}"
CLEANUP_LEGACY="${NHMF_CLEANUP_LEGACY:-1}"

# Auto-detect network interface if not set
if [[ -z "${SURICATA_INTERFACE:-}" ]]; then
  DETECTED_IFACE="$(ip route get 8.8.8.8 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i=="dev") print $(i+1); exit}' || echo 'eth0')"
  export SURICATA_INTERFACE="${DETECTED_IFACE:-eth0}"
  echo "[INFO] Auto-detected SURICATA_INTERFACE=${SURICATA_INTERFACE}"
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --retrain)
      RETRAIN=1
      ;;
    --skip-train)
      SKIP_TRAIN=1
      ;;
    --no-cleanup)
      CLEANUP_LEGACY=0
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--retrain] [--skip-train] [--no-cleanup]" >&2
      exit 1
      ;;
  esac
  shift
done

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

ensure_docker_daemon() {
  if ! docker info >/dev/null 2>&1; then
    echo "[INFO] Docker daemon is not running. Attempting to start service..."
    if command -v systemctl >/dev/null 2>&1; then
      sudo systemctl enable --now containerd 2>/dev/null || true
      sudo systemctl enable --now docker 2>/dev/null || true
    elif command -v service >/dev/null 2>&1; then
      sudo service containerd start 2>/dev/null || true
      sudo service docker start 2>/dev/null || true
    fi
    sleep 3
    if ! docker info >/dev/null 2>&1; then
      echo "[ERROR] Docker daemon is not running and could not be started automatically." >&2
      echo "        Please run: sudo systemctl enable --now docker" >&2
      exit 1
    fi
    echo "[OK] Docker daemon started."
  fi
}

configure_build_network() {
  if [[ -z "${DOCKER_BUILD_NETWORK:-}" ]]; then
    case "$(uname -s 2>/dev/null || echo unknown)" in
      Linux*)
        export DOCKER_BUILD_NETWORK=host
        ;;
      *)
        export DOCKER_BUILD_NETWORK=default
        ;;
    esac
  fi

  export PIP_RETRIES="${PIP_RETRIES:-10}"
  export PIP_TIMEOUT="${PIP_TIMEOUT:-120}"

  echo "Docker build network: $DOCKER_BUILD_NETWORK"
  echo "Pip retries/timeout: $PIP_RETRIES retries, ${PIP_TIMEOUT}s timeout"
}

ensure_env_file() {
  # Auto-sanitize .env if corrupted or containing conflict markers
  if [[ -f ".env" ]] && grep -q "<<<<<<" ".env" 2>/dev/null; then
    echo "[WARN] Corrupted conflict markers detected in .env. Recreating cleanly..."
    rm -f ".env"
  fi

  # Auto-sanitize .env.example if conflict markers exist
  if grep -q "<<<<<<" ".env.example" 2>/dev/null; then
    sed -i -e '/^<<<<<<</d' -e '/^=======$/d' -e '/^>>>>>>>/d' ".env.example"
  fi

  if [[ ! -f ".env" ]]; then
    cp ".env.example" ".env"
    echo "Created clean .env file."
  fi

  # Ensure SURICATA_INTERFACE is correctly populated in .env
  if [[ -n "${SURICATA_INTERFACE:-}" && -f ".env" ]]; then
    if grep -q "^SURICATA_INTERFACE=" ".env"; then
      sed -i "s|^SURICATA_INTERFACE=.*|SURICATA_INTERFACE=${SURICATA_INTERFACE}|" ".env"
    else
      echo "SURICATA_INTERFACE=${SURICATA_INTERFACE}" >> ".env"
    fi
  fi
}

cleanup_legacy_containers() {
  if [[ "$CLEANUP_LEGACY" != "1" ]]; then
    return
  fi

  local names=(
    nhmf-prometheus
    nhmf-alertmanager
    nhmf-grafana
    nhmf-node-exporter
    nhmf-blackbox-exporter
    nhmf-pushgateway
    nhmf-ml-anomaly
    nhmf-zabbix-db
    nhmf-zabbix-server
    nhmf-zabbix-web
    nhmf-zabbix-agent
    nhmf-suricata
    nhmf-suricata-exporter
  )

  for name in "${names[@]}"; do
    local container_id
    container_id="$(docker ps -aq --filter "name=^/${name}$" 2>/dev/null || true)"
    if [[ -n "$container_id" ]]; then
      echo "Removing stale legacy container: $name"
      docker rm -f "$container_id" >/dev/null 2>&1 || true
    fi
  done
}

ensure_unsw_model() {
  local model_path="$PROJECT_ROOT/ml-anomaly/models/unsw_nb15_model.joblib"
  local data_dir="$PROJECT_ROOT/Data/UNSW-NB15 dataset/CSV Files/Training and Testing Sets"

  if [[ ! -f "$data_dir/UNSW_NB15_training-set.csv" || ! -f "$data_dir/UNSW_NB15_testing-set.csv" ]]; then
    echo "UNSW-NB15 train/test CSV files were not found in: $data_dir" >&2
    exit 1
  fi

  mkdir -p "$PROJECT_ROOT/ml-anomaly/models"

  if [[ "$SKIP_TRAIN" == "1" ]]; then
    echo "Skipping ML model training."
    return
  fi

  if [[ "$RETRAIN" == "1" || ! -f "$model_path" ]]; then
    echo "Training UNSW-NB15 model inside Docker. This can take several minutes..."
    docker compose build ml-anomaly
    docker compose run --rm --no-deps ml-anomaly python train_unsw_nb15.py
  else
    echo "Using existing UNSW-NB15 model: $model_path"
  fi
}

check_url() {
  local name="$1"
  local url="$2"
  local timeout_seconds="${3:-90}"
  local service_name="${4:-$1}"

  if ! command -v curl >/dev/null 2>&1; then
    echo "$name: skipped health check because curl is not installed."
    return
  fi

  echo -n "Waiting for $name at $url "
  local elapsed=0
  until curl -fsS "$url" >/dev/null 2>&1; do
    if (( elapsed >= timeout_seconds )); then
      echo "FAILED"
      echo "  Check logs: docker compose logs --tail 120 $service_name"
      return
    fi
    echo -n "."
    sleep 3
    elapsed=$((elapsed + 3))
  done
  echo " OK"
}

verify_portal_build() {
  if ! command -v curl >/dev/null 2>&1; then
    echo "Operations Portal build: skipped because curl is not installed."
    return
  fi

  local payload
  payload="$(curl -fsS "http://localhost:8088/version" 2>/dev/null || true)"
  if grep -Fq "\"build\":\"${PORTAL_BUILD_ID}\"" <<<"$payload"; then
    echo "Operations Portal build: ${PORTAL_BUILD_ID} [OK]"
    return
  fi

  echo "[ERROR] Operations Portal is serving an old or incomplete dashboard build." >&2
  echo "        Expected: ${PORTAL_BUILD_ID}" >&2
  echo "        Received: ${payload:-no response}" >&2
  echo "        Re-apply with: bash scripts/apply_dashboard_updates.sh" >&2
  return 1
}

require_command docker
docker compose version >/dev/null
ensure_docker_daemon

ensure_env_file
configure_build_network
cleanup_legacy_containers
ensure_unsw_model

echo "Starting Network Health Monitoring Framework..."
docker compose up -d --build

# Bind-mounted portal files can change without Docker detecting a new image.
# Recreating these services guarantees that Nginx reloads its cache policy and
# Grafana reprovisions the current dashboard definitions after an import/pull.
docker compose up -d --force-recreate --no-deps portal grafana

docker compose restart \
  zabbix-agent \
  zabbix-agent-application \
  zabbix-agent-database \
  zabbix-agent-security \
  zabbix-agent-web \
  zabbix-agent-api \
  zabbix-agent-backup >/dev/null
sleep 5

echo ""
docker compose ps

echo ""
check_url "Prometheus" "http://localhost:9090/-/healthy" 60 "prometheus"
check_url "Grafana" "http://localhost:3000/api/health" 120 "grafana"
check_url "ML anomaly API" "http://localhost:8000/health" 90 "ml-anomaly"
check_url "Operations Portal" "http://localhost:8088/health" 90 "portal"
verify_portal_build
check_url "Zabbix Web" "http://localhost:8080" 180 "zabbix-web"
check_url "Suricata Exporter" "http://localhost:9517/-/healthy" 60 "suricata-exporter"
check_url "Suricata Sensor Data" "http://localhost:9517/health" 60 "suricata"

if command -v curl >/dev/null 2>&1; then
  echo ""
  echo "Reloading Prometheus targets and alert rules..."
  if ! curl -fsS -X POST "http://localhost:9090/-/reload" >/dev/null; then
    echo "[WARN] Prometheus configuration reload failed. Re-run: curl -X POST http://localhost:9090/-/reload" >&2
  fi
fi

if command -v python3 >/dev/null 2>&1; then
  echo ""
  echo "Reconciling the seven Zabbix monitored servers..."
  if ! python3 "$PROJECT_ROOT/scripts/zabbix_api_manager.py" --wait-seconds 120 setup-demo-hosts; then
    echo "[WARN] Zabbix host reconciliation did not complete. Re-run: ./scripts/setup_zabbix.sh setup-demo-hosts" >&2
  fi
else
  echo "[WARN] python3 is unavailable; Zabbix host reconciliation was skipped." >&2
fi

if command -v curl >/dev/null 2>&1; then
  echo ""
  echo "Native Zabbix server data supplied to Grafana:"
  curl -fsS "http://localhost:8000/zabbix-health?refresh=true" 2>/dev/null | python3 -m json.tool 2>/dev/null || \
    echo "[WARN] Native Zabbix data is not ready. Check: docker compose logs --tail 100 ml-anomaly zabbix-web" >&2
  echo ""
  echo "Suricata IDS response:"
  curl -fsS "http://localhost:9517/status" 2>/dev/null | python3 -m json.tool 2>/dev/null || \
    echo "[WARN] Suricata status is not ready. Check: docker compose logs --tail 100 suricata suricata-exporter" >&2
fi

echo ""
echo "Services:"
echo "Main Portal:          http://localhost:8088"
echo "Grafana:              http://localhost:3000  (admin/${GRAFANA_ADMIN_PASSWORD:-admin123})"
echo "ML Dashboard:         http://localhost:3000/d/nhmf-ml/ml-anomaly-detection-dashboard"
echo "Suricata IDS:         http://localhost:3000/d/nhmf-suricata/suricata-ids-dashboard"
echo "Zabbix Dashboard:     http://localhost:3000/d/nhmf-zabbix/zabbix-infrastructure-host-dashboard"
echo "Prometheus:           http://localhost:9090"
echo "Alertmanager:         http://localhost:9093"
echo "ML API:               http://localhost:8000/health"
echo "Suricata Metrics:     http://localhost:9517/metrics"
echo "Suricata Status:      http://localhost:9517/status"
echo "Zabbix:               http://localhost:8080  Admin/zabbix"
echo "Zabbix Native Data:   http://localhost:8000/zabbix-health"
echo ""
echo "Network interface monitored by Suricata: ${SURICATA_INTERFACE}"
echo "To update Suricata rules:  ./scripts/update_suricata_rules.sh"
echo "To list demo scenarios:    ./scripts/fault_injection/demo_scenarios.sh list"
