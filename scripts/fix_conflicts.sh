#!/usr/bin/env bash
# =============================================================================
# fix_conflicts.sh — Resolve all git merge conflict markers in NHMF repo
# Run this ONCE on Ubuntu before starting the stack:
#   bash scripts/fix_conflicts.sh
# =============================================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
info() { echo -e "${YELLOW}[INFO]${NC}  $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

echo "============================================"
echo " NHMF — Git Merge Conflict Fixer"
echo "============================================"
echo ""

# ---------------------------------------------------------------------------
# 1. .env.example — write clean version directly
# ---------------------------------------------------------------------------
info "Writing clean .env.example..."
cat > .env.example << 'ENVEOF'
COMPOSE_PROJECT_NAME=nhmf
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin123
# Optional. Requires internet from inside the Grafana container.
# GRAFANA_INSTALL_PLUGINS=alexanderzobnin-zabbix-app
ZABBIX_DB_NAME=zabbix
ZABBIX_DB_USER=zabbix
ZABBIX_DB_PASSWORD=zabbix
ZABBIX_DB_ROOT_PASSWORD=zabbix-root
# Suricata — set to your Ubuntu host's primary network interface
# Typical values: eth0, ens3, ens33, ens160, enp0s3
# Auto-detect with: ip route get 8.8.8.8 | awk '{print $5; exit}'
SURICATA_INTERFACE=eth0
ENVEOF
ok ".env.example written"

# ---------------------------------------------------------------------------
# 2. Remove stale .env so it regenerates from clean .env.example
# ---------------------------------------------------------------------------
if [[ -f ".env" ]]; then
  info "Removing stale .env (will be recreated from .env.example on next start)..."
  rm -f .env
  ok ".env removed"
fi

# ---------------------------------------------------------------------------
# Helper: strip conflict markers keeping BOTH sides' content
# (safe because HEAD side is always empty in this repo's conflicts)
# ---------------------------------------------------------------------------
strip_conflicts() {
  local file="$1"
  if grep -q "<<<<<<" "$file" 2>/dev/null; then
    info "Fixing conflict markers in: $file"
    # Remove all three types of conflict marker lines
    sed -i '/^<<<<<<< /d; /^=======$/d; /^>>>>>>> /d' "$file"
    ok "$file fixed"
  else
    ok "$file — no conflict markers"
  fi
}

# ---------------------------------------------------------------------------
# 3. Fix all known conflicted files
# ---------------------------------------------------------------------------
strip_conflicts "scripts/start_stack.sh"
strip_conflicts "docker-compose.yml"
strip_conflicts "configs/prometheus/prometheus.yml"
strip_conflicts "configs/prometheus/alert_rules.yml"
strip_conflicts "configs/grafana/dashboards/network-health-dashboard.json"

# ---------------------------------------------------------------------------
# 4. Check for any remaining conflict markers in the whole repo
# ---------------------------------------------------------------------------
echo ""
info "Scanning for any remaining conflict markers..."
REMAINING=$(grep -rl "<<<<<<" --include="*.sh" --include="*.yml" --include="*.yaml" \
            --include="*.json" --include="*.py" --include="*.txt" --include="*.md" . \
            2>/dev/null || true)

if [[ -n "$REMAINING" ]]; then
  err "Remaining conflict markers found in:"
  echo "$REMAINING"
  info "Applying strip_conflicts to remaining files..."
  while IFS= read -r f; do
    strip_conflicts "$f"
  done <<< "$REMAINING"
else
  ok "No remaining conflict markers found!"
fi

# ---------------------------------------------------------------------------
# 5. Ensure Suricata configs exist (create if missing)
# ---------------------------------------------------------------------------
echo ""
info "Checking Suricata config directories..."
mkdir -p configs/suricata/rules

if [[ ! -f configs/suricata/rules/local.rules ]]; then
  info "Creating missing configs/suricata/rules/local.rules..."
  cat > configs/suricata/rules/local.rules << 'RULESEOF'
# NHMF Local Suricata Rules
alert tcp any any -> $HOME_NET any (msg:"NHMF SCAN TCP SYN port scan detected"; flags:S; threshold: type threshold, track by_src, count 20, seconds 10; sid:9000001; rev:1; classtype:attempted-recon;)
alert udp any any -> $HOME_NET any (msg:"NHMF SCAN UDP port scan detected"; threshold: type threshold, track by_src, count 30, seconds 10; sid:9000002; rev:1; classtype:attempted-recon;)
alert icmp any any -> $HOME_NET any (msg:"NHMF DOS ICMP flood detected"; itype:8; threshold: type threshold, track by_src, count 100, seconds 5; sid:9000003; rev:1; classtype:bad-unknown;)
alert tcp any any -> $HOME_NET 22 (msg:"NHMF BRUTE SSH brute force attempt"; flow:to_server,established; threshold: type threshold, track by_src, count 5, seconds 30; sid:9000005; rev:1; classtype:attempted-admin;)
alert tcp $HOME_NET any -> any 4444 (msg:"NHMF C2 suspicious outbound port 4444"; flow:to_server,established; sid:9000006; rev:1; classtype:trojan-activity;)
RULESEOF
  ok "local.rules created"
fi

if [[ ! -f configs/suricata/suricata.yaml ]]; then
  err "configs/suricata/suricata.yaml is missing! Push from Windows dev machine and re-run."
fi

if [[ ! -d suricata-exporter ]]; then
  err "suricata-exporter/ directory is missing! Push from Windows dev machine and re-run."
fi

# ---------------------------------------------------------------------------
# 6. Fix permissions
# ---------------------------------------------------------------------------
echo ""
info "Fixing script permissions..."
chmod +x scripts/*.sh scripts/fault_injection/*.sh 2>/dev/null || true
ok "Permissions set"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "============================================"
echo -e " ${GREEN}All conflicts resolved.${NC}"
echo " Now run:  bash run.sh --skip-train"
echo " (or)      bash run.sh   (if model not trained yet)"
echo "============================================"
