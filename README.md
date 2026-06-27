# Scalable Intelligent Network Health Monitoring Framework

This ZIP contains a complete open-source prototype project for a **Scalable Intelligent Network Health Monitoring Framework with ML-Based Anomaly Detection**.

The project implements a layered monitoring architecture using:

- **Prometheus** for metric scraping and time-series monitoring
- **Alertmanager** for alert grouping, routing and silencing
- **Grafana** for dashboards and operational visibility
- **Blackbox Exporter** for ICMP/HTTP reachability checks
- **Node Exporter** for Linux host metrics
- **Pushgateway** for custom or batch metrics
- **Zabbix** as an optional infrastructure monitoring layer
- **Python + FastAPI + scikit-learn** for ML-based anomaly score generation

## Project Structure

```text
network-health-monitoring-framework/
├── docker-compose.yml
├── .env
├── README.md
├── configs/
│   ├── prometheus/
│   ├── alertmanager/
│   ├── blackbox/
│   ├── grafana/
│   ├── snmp/
│   └── zabbix/
├── ml-anomaly/
│   ├── app.py
│   ├── anomaly_detector.py
│   ├── config.yaml
│   ├── Dockerfile
│   └── requirements.txt
├── scripts/
│   ├── install_docker_ubuntu.sh
│   ├── start_stack.sh
│   ├── stop_stack.sh
│   ├── validate_stack.sh
│   ├── export_evidence.sh
│   └── fault_injection/
├── docs/
├── diagrams/
├── sample-data/
└── tests/
```

## Quick Start

### 1. Install Docker on Ubuntu

```bash
chmod +x scripts/install_docker_ubuntu.sh
./scripts/install_docker_ubuntu.sh
```

Log out and log back in after installation if Docker group membership is updated.

### 2. Start the Monitoring Stack

```bash
chmod +x scripts/start_stack.sh
./scripts/start_stack.sh
```

### 3. Access Services

| Service | URL | Default Login |
|---|---|---|
| Grafana | http://localhost:3000 | admin / admin123 |
| Prometheus | http://localhost:9090 | No login |
| Alertmanager | http://localhost:9093 | No login |
| ML Anomaly API | http://localhost:8000 | No login |
| Zabbix Web UI | http://localhost:8080 | Admin / zabbix |

Grafana dashboard path: Dashboards > NHMF > Network Health Monitoring - Hybrid Operations Dashboard.

### 4. Validate the Stack

```bash
chmod +x scripts/validate_stack.sh
./scripts/validate_stack.sh
```

### 5. Stop the Stack

```bash
chmod +x scripts/stop_stack.sh
./scripts/stop_stack.sh
```

## Optional Zabbix Stack

Zabbix is included in the same Docker Compose file. It is started by default. If your computer has limited RAM, comment out the Zabbix services in `docker-compose.yml`.

## ML Anomaly Detection

The ML component pulls selected metrics from Prometheus, applies feature engineering and trains a lightweight unsupervised anomaly detector. It exposes anomaly metrics at:

```text
http://localhost:8000/metrics
```

Prometheus scrapes this endpoint as job `ml-anomaly`.

Main exported metrics:

```text
nhmf_anomaly_score
nhmf_anomaly_flag
nhmf_model_trained
nhmf_last_run_timestamp
```

## Fault Injection

Fault injection scripts are provided for controlled lab testing.

```bash
sudo scripts/fault_injection/latency_packetloss.sh eth0 100ms 5% 60
scripts/fault_injection/cpu_stress.sh 60
```

Use these only in a controlled lab VM.

## Evidence Collection

```bash
chmod +x scripts/export_evidence.sh
./scripts/export_evidence.sh
```

This exports Prometheus targets, active alerts, container status and logs into an evidence folder.

## Academic Usage

This project supports the development methodology:

1. Environment preparation
2. Baseline monitoring
3. Dashboard development
4. Rule-based alerting
5. ML anomaly detection
6. ML-dashboard integration
7. Fault injection testing
8. KPI-based evaluation and refinement

See the `docs/` folder for methodology, architecture, implementation and testing documents.
