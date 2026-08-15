#!/usr/bin/env bash
# =============================================================================
# run.sh — Main entry point to launch the NHMF stack
# Usage:
#   bash run.sh              # Start everything (trains model if missing)
#   bash run.sh --skip-train # Start without ML retraining
#   bash run.sh --retrain    # Force fresh ML retraining
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure all scripts have execute permissions
find scripts -type f -name "*.sh" -exec chmod +x {} + 2>/dev/null || true

exec ./scripts/start_stack.sh "$@"
