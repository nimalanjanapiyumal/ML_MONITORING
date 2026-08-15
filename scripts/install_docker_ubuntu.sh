#!/usr/bin/env bash
# =============================================================================
# install_docker_ubuntu.sh — Install Docker Engine & Compose plugin on Ubuntu
# =============================================================================
set -euo pipefail

echo "============================================================"
echo " NHMF — Docker & Docker Compose Installer for Ubuntu"
echo "============================================================"

echo "[1/5] Updating package index and installing prerequisites..."
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg lsb-release

echo "[2/5] Setting up Docker official GPG keyring..."
sudo install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
fi

echo "[3/5] Configuring Docker APT repository..."
ARCH="$(dpkg --print-architecture)"
CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"
echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${CODENAME} stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "[4/5] Installing Docker Engine, CLI, and Compose Plugin..."
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "[5/5] Adding current user ($USER) to docker group..."
sudo usermod -aG docker "$USER" || true

echo ""
echo "============================================================"
echo " Docker installation completed successfully!"
echo " Docker Version:         $(docker --version 2>/dev/null || echo 'Installed')"
echo " Docker Compose Version: $(docker compose version 2>/dev/null || echo 'Installed')"
echo "============================================================"
echo "NOTE: Log out and back in (or run 'newgrp docker') to apply group changes."
