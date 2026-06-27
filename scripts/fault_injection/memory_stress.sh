#!/usr/bin/env bash
set -euo pipefail

DURATION="${1:-60}"

if ! command -v stress-ng >/dev/null 2>&1; then
  echo "stress-ng not found. Install with: sudo apt-get install -y stress-ng"
  exit 1
fi

echo "Starting memory stress test for ${DURATION}s"
stress-ng --vm 1 --vm-bytes 512M --timeout "${DURATION}s" --metrics-brief
echo "Completed."
