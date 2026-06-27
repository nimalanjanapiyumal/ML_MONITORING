#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] Updating package index..."
sudo apt-get update

echo "[2/5] Installing prerequisites..."
sudo apt-get install -y ca-certificates curl gnupg lsb-release

echo "[3/5] Installing Docker..."
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
else
  echo "Docker already installed."
fi

echo "[4/5] Installing Docker Compose plugin..."
sudo apt-get install -y docker-compose-plugin || true

echo "[5/5] Adding current user to docker group..."
sudo usermod -aG docker "$USER" || true

echo "Docker installation completed. Log out and log back in if docker requires sudo."
docker --version || true
docker compose version || true
