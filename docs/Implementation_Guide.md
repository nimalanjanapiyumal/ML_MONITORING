# Implementation Guide

## Prerequisites

Recommended VM specification:

- Ubuntu Server 22.04 or later
- 4 vCPU
- 8 GB RAM minimum
- 40 GB disk
- Internet access for pulling Docker images

## Step 1: Install Docker

```bash
chmod +x scripts/install_docker_ubuntu.sh
./scripts/install_docker_ubuntu.sh
```

## Step 2: Start Stack

```bash
chmod +x scripts/start_stack.sh
./scripts/start_stack.sh
```

## Step 3: Confirm Prometheus Targets

Open:

```text
http://localhost:9090/targets
```

Expected jobs:

- prometheus
- node-exporter
- blackbox-icmp
- blackbox-http
- ml-anomaly
- pushgateway

## Step 4: Open Grafana

Open:

```text
http://localhost:3000
```

Login:

```text
admin / admin123
```

Go to Dashboards > NHMF > Network Health Monitoring - Hybrid Operations Dashboard.

## Step 5: Open Alertmanager

```text
http://localhost:9093
```

## Step 6: Open ML API

```text
http://localhost:8000/health
http://localhost:8000/results
http://localhost:8000/metrics
```

## Step 7: Optional Zabbix

Open:

```text
http://localhost:8080
```

Login:

```text
Admin / zabbix
```

Add monitored hosts and templates manually through the Zabbix web interface.
