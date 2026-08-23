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

## Step 7: Zabbix Seven-Server Fleet

Open:

```text
http://localhost:8080
```

Login:

```text
Admin / zabbix
```

The startup script automatically registers core, application, database, security, web, API, and backup server roles. To reconcile them again and display native agent health:

```bash
./scripts/setup_zabbix.sh setup-demo-hosts
./scripts/setup_zabbix.sh status
```

In Zabbix, open **Data collection → Hosts** and filter by **NHMF Monitored Servers**.
