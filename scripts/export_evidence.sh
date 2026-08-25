#!/usr/bin/env bash
# =============================================================================
# export_evidence.sh — Export comprehensive monitoring and IDS evidence
# =============================================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="evidence/evidence_$STAMP"
mkdir -p "$OUT"

echo "============================================================"
echo " NHMF — Exporting Evidence to $OUT"
echo "============================================================"

# Docker container state and compose specification
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" > "$OUT/docker_ps.txt" 2>&1 || true
docker compose config > "$OUT/docker_compose_rendered.yml" 2>&1 || true

# Prometheus & Alertmanager runtime states
curl -fsS "http://localhost:9090/api/v1/targets" | python3 -m json.tool > "$OUT/prometheus_targets.json" 2>&1 || true
curl -fsS "http://localhost:9090/api/v1/alerts" | python3 -m json.tool > "$OUT/prometheus_alerts.json" 2>&1 || true
curl -fsS "http://localhost:9090/api/v1/rules" | python3 -m json.tool > "$OUT/prometheus_rules.json" 2>&1 || true
curl -fsS "http://localhost:9093/api/v2/alerts" | python3 -m json.tool > "$OUT/alertmanager_alerts.json" 2>&1 || true

# ML Anomaly Detection state
curl -fsS "http://localhost:8000/results" | python3 -m json.tool > "$OUT/ml_results.json" 2>&1 || true
curl -fsS "http://localhost:8000/metrics" > "$OUT/ml_metrics_raw.txt" 2>&1 || true
curl -fsS "http://localhost:8000/zabbix-health?refresh=true" | python3 -m json.tool > "$OUT/zabbix_native_health.json" 2>&1 || true

# Suricata IDS metrics & eve-log sample
curl -fsS "http://localhost:9517/metrics" > "$OUT/suricata_metrics_raw.txt" 2>&1 || true
curl -fsS "http://localhost:9517/status" | python3 -m json.tool > "$OUT/suricata_status.json" 2>&1 || true
docker compose exec -T suricata tail -n 100 /var/log/suricata/eve.json > "$OUT/suricata_eve_sample.json" 2>&1 || true
docker compose exec -T suricata tail -n 50 /var/log/suricata/fast.log > "$OUT/suricata_fast_sample.log" 2>&1 || true

# Container logs for all services
SERVICES=(
  prometheus
  alertmanager
  grafana
  ml-anomaly
  blackbox-exporter
  node-exporter
  suricata
  suricata-exporter
  portal
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

for service in "${SERVICES[@]}"; do
  docker compose logs --no-color --tail 250 "$service" > "$OUT/${service}_logs.txt" 2>&1 || true
done

echo ""
echo "============================================================"
echo " Evidence export complete:"
echo " Directory: $OUT"
echo " Total files: $(find "$OUT" -type f | wc -l)"
echo "============================================================"
