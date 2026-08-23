#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

exec bash "$PROJECT_ROOT/scripts/fault_injection/demo_scenarios.sh" ml-outage "${1:-90}"
