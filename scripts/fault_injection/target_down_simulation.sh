#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "This script stops the ml-anomaly container for 90 seconds to simulate service unavailability."
docker compose stop ml-anomaly
sleep 90
docker compose start ml-anomaly
echo "Service restored."
