#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="evidence/evidence_$STAMP"
mkdir -p "$OUT"

echo "Exporting evidence to $OUT"

docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" > "$OUT/docker_ps.txt"
docker compose config > "$OUT/docker_compose_rendered.yml"

curl -fsS "http://localhost:9090/api/v1/targets" | python3 -m json.tool > "$OUT/prometheus_targets.json" || true
curl -fsS "http://localhost:9090/api/v1/alerts" | python3 -m json.tool > "$OUT/prometheus_alerts.json" || true
curl -fsS "http://localhost:9093/api/v2/alerts" | python3 -m json.tool > "$OUT/alertmanager_alerts.json" || true
curl -fsS "http://localhost:8000/results" | python3 -m json.tool > "$OUT/ml_results.json" || true

for c in nhmf-prometheus nhmf-alertmanager nhmf-grafana nhmf-ml-anomaly nhmf-blackbox-exporter nhmf-node-exporter; do
  docker logs "$c" --tail 200 > "$OUT/${c}_logs.txt" 2>&1 || true
done

echo "Evidence export completed: $OUT"
