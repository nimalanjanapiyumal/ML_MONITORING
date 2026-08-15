#!/usr/bin/env bash
# =============================================================================
# simulate_network_attacks.sh — Safe Attack & IDS Signature Simulation
# Generates controlled traffic matching NHMF local Suricata detection rules
# =============================================================================
set -euo pipefail

TARGET_HOST="${1:-127.0.0.1}"
SCENARIO="${2:-all}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "============================================================"
echo " NHMF — Suricata IDS Signature Simulation"
echo " Target: $TARGET_HOST | Scenario: $SCENARIO"
echo "============================================================"

run_syn_scan() {
  echo -e "\n${BLUE}[1/4] Simulating TCP SYN Port Scan (sid:9000001)...${NC}"
  if command -v nmap >/dev/null 2>&1; then
    echo "Using nmap for quick SYN scan across ports 20-100..."
    sudo nmap -sS -p 20-100 -T4 "$TARGET_HOST" || true
  else
    echo "nmap not found. Simulating with bash socket burst..."
    for port in {20..45}; do
      (timeout 0.1 bash -c "echo > /dev/tcp/$TARGET_HOST/$port" 2>/dev/null || true) &
    done
    wait 2>/dev/null || true
  fi
  echo -e "${GREEN}[OK] Port scan traffic generated.${NC}"
}

run_icmp_burst() {
  echo -e "\n${BLUE}[2/4] Simulating ICMP Echo Burst (sid:9000003)...${NC}"
  echo "Sending 120 fast ICMP ping packets..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    ping -c 120 -i 0.05 "$TARGET_HOST" >/dev/null 2>&1 || true
  else
    ping -c 120 -i 0.04 -W 1 "$TARGET_HOST" >/dev/null 2>&1 || true
  fi
  echo -e "${GREEN}[OK] ICMP burst sent.${NC}"
}

run_http_basic_auth() {
  echo -e "\n${BLUE}[3/4] Simulating Cleartext HTTP Basic Auth (sid:9000008)...${NC}"
  echo "Sending HTTP request with Authorization: Basic header..."
  for i in {1..3}; do
    curl -s -H "Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=" "http://$TARGET_HOST:8088/" >/dev/null 2>&1 || true
    curl -s -H "Authorization: Basic dGVzdHVzZXI6c2VjcmV0" "http://$TARGET_HOST:8000/health" >/dev/null 2>&1 || true
  done
  echo -e "${GREEN}[OK] HTTP Basic Auth requests sent.${NC}"
}

run_c2_probe() {
  echo -e "\n${BLUE}[4/4] Simulating Outbound C2 Port 4444 Connection (sid:9000006)...${NC}"
  echo "Testing connection probe to port 4444..."
  (timeout 1 bash -c "echo 'hello' > /dev/tcp/$TARGET_HOST/4444" 2>/dev/null || true)
  echo -e "${GREEN}[OK] C2 port probe sent.${NC}"
}

case "$SCENARIO" in
  scan)
    run_syn_scan
    ;;
  icmp)
    run_icmp_burst
    ;;
  http)
    run_http_basic_auth
    ;;
  c2)
    run_c2_probe
    ;;
  all)
    run_syn_scan
    run_icmp_burst
    run_http_basic_auth
    run_c2_probe
    ;;
  *)
    echo "Unknown scenario: $SCENARIO"
    echo "Usage: $0 [TARGET_IP] [scan|icmp|http|c2|all]"
    exit 1
    ;;
esac

echo ""
echo "============================================================"
echo -e "${YELLOW}Simulation finished. Check results in:${NC}"
echo "  1. Grafana IDS: http://localhost:3000/d/nhmf-suricata/suricata-ids-dashboard"
echo "  2. Metrics:     http://localhost:9517/metrics"
echo "  3. Fast log:    docker compose exec suricata tail -n 20 /var/log/suricata/fast.log"
echo "============================================================"
