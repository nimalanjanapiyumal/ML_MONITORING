#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-nhmf}"

RETRAIN="${NHMF_RETRAIN:-0}"
SKIP_TRAIN="${NHMF_SKIP_TRAIN:-0}"
CLEANUP_LEGACY="${NHMF_CLEANUP_LEGACY:-1}"

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
  if [[ -f ".env" ]]; then
    return
  fi

  cp ".env.example" ".env"
  echo "Created default .env file."
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
  )

  for name in "${names[@]}"; do
    local container_id
    container_id="$(docker ps -aq --filter "name=^/${name}$")"
    if [[ -n "$container_id" ]]; then
      echo "Removing stale legacy container: $name"
      docker rm -f "$container_id" >/dev/null
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

require_command docker
docker compose version >/dev/null
docker info >/dev/null

ensure_env_file
configure_build_network
cleanup_legacy_containers
ensure_unsw_model

echo "Starting Network Health Monitoring Framework..."
docker compose up -d --build

echo ""
echo "Services:"
echo "Grafana:       http://localhost:3000  admin/admin123"
echo "Prometheus:    http://localhost:9090"
echo "Alertmanager:  http://localhost:9093"
echo "ML API:        http://localhost:8000/health"
echo "Zabbix:        http://localhost:8080  Admin/zabbix"
