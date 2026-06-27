#!/usr/bin/env bash
set -euo pipefail

IFACE="${1:-eth0}"
DELAY="${2:-100ms}"
LOSS="${3:-5%}"
DURATION="${4:-60}"

echo "Applying network delay=$DELAY and packet loss=$LOSS on interface=$IFACE for ${DURATION}s"
echo "This requires root privileges and should only be used in a lab VM."

sudo tc qdisc add dev "$IFACE" root netem delay "$DELAY" loss "$LOSS" || {
  echo "Existing qdisc may be present. Replacing..."
  sudo tc qdisc replace dev "$IFACE" root netem delay "$DELAY" loss "$LOSS"
}

sleep "$DURATION"

echo "Removing network impairment..."
sudo tc qdisc del dev "$IFACE" root || true
echo "Completed."
