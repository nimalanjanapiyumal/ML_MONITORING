#!/usr/bin/env bash
# =============================================================================
# install_docker_ubuntu.sh — Install & Start Docker Engine & Compose on Ubuntu
# =============================================================================
set -euo pipefail

echo "============================================================"
echo " NHMF — Docker & Docker Compose Installer for Ubuntu"
echo "============================================================"

# Resolve any interrupted / half-installed dpkg states first
sudo dpkg --configure -a || true
sudo apt-get --fix-broken install -y || true

# Function to enable and start services
start_docker_service() {
  echo "[*] Enabling and starting Docker daemon..."
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl enable --now containerd || true
    sudo systemctl enable --now docker || true
  elif command -v service >/dev/null 2>&1; then
    sudo service containerd start || true
    sudo service docker start || true
  fi
}

# If docker compose is already functional, ensure service is active and exit early
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  start_docker_service
  echo "[INFO] Docker and Docker Compose plugin are already installed and functional:"
  echo "       Docker:         $(docker --version 2>/dev/null || echo 'Installed')"
  echo "       Docker Compose: $(docker compose version 2>/dev/null || echo 'Installed')"
  sudo usermod -aG docker "$USER" 2>/dev/null || true
  echo "============================================================"
  exit 0
fi

echo "[1/5] Updating package index and installing prerequisites..."
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Remove conflicting Ubuntu universe docker packages if present
echo "[2/5] Cleaning up conflicting packages (if any)..."
sudo apt-get remove -y docker-compose-v2 docker-compose docker.io containerd runc 2>/dev/null || true

echo "[3/5] Setting up Docker official GPG keyring..."
sudo install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
fi

echo "[4/5] Configuring Docker APT repository..."
ARCH="$(dpkg --print-architecture)"
CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"
echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${CODENAME} stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "[5/5] Installing Docker Engine, CLI, and Compose Plugin..."
sudo apt-get update -y
sudo apt-get install -y -o Dpkg::Options::="--force-overwrite" \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker "$USER" 2>/dev/null || true

start_docker_service

echo ""
echo "============================================================"
echo " Docker installation completed successfully!"
echo " Docker Version:         $(docker --version 2>/dev/null || echo 'Installed')"
echo " Docker Compose Version: $(docker compose version 2>/dev/null || echo 'Installed')"
echo "============================================================"
echo "NOTE: Log out and back in (or run 'newgrp docker') to apply group changes."
