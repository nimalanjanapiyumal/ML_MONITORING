#!/usr/bin/env bash
set -euo pipefail

echo "This script stops the ml-anomaly container for 90 seconds to simulate service unavailability."
docker stop nhmf-ml-anomaly
sleep 90
docker start nhmf-ml-anomaly
echo "Service restored."
