#!/usr/bin/env bash
set -euo pipefail
chmod +x scripts/*.sh scripts/fault_injection/*.sh
./scripts/start_stack.sh "$@"
