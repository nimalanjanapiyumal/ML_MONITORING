#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "Starting Network Health Monitoring Framework..."
docker compose up -d --build

echo ""
echo "Services:"
echo "Grafana:       http://localhost:3000  admin/admin123"
echo "Prometheus:    http://localhost:9090"
echo "Alertmanager:  http://localhost:9093"
echo "ML API:        http://localhost:8000/health"
echo "Zabbix:        http://localhost:8080  Admin/zabbix"
