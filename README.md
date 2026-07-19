# Scalable Network Health Monitoring Framework Using Open-Source Tools

This repository contains a complete open-source prototype for a **Scalable Network Health Monitoring Framework Using Open-Source Tools**, enhanced with hybrid ML-based anomaly detection.

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

### 2. Start Everything With One Command

```bash
bash run.sh
```

This command creates `.env` from `.env.example` when needed, removes stale legacy `nhmf-*` containers, trains the UNSW-NB15 model if the model bundle is missing, builds the ML API image, and starts the full Docker Compose stack.

On Windows PowerShell, run:

```powershell
.\run.ps1
```

Useful options:

```bash
bash run.sh --retrain
bash run.sh --skip-train
```

If your Docker build cannot resolve PyPI during `pip install`, Linux setup defaults the ML image build to host networking. You can override it:

```bash
DOCKER_BUILD_NETWORK=default bash run.sh
```

Grafana starts with the Prometheus dashboard by default. The Zabbix Grafana plugin is optional because it requires internet access from inside the Grafana container; enable it by setting `GRAFANA_INSTALL_PLUGINS=alexanderzobnin-zabbix-app` in `.env`.

### 3. Access Services

| Service | URL | Default Login |
|---|---|---|
| NHMF Operations Portal | http://localhost:8088 | No login |
| Grafana | http://localhost:3000 | admin / admin123 |
| Prometheus | http://localhost:9090 | No login |
| Alertmanager | http://localhost:9093 | No login |
| ML Anomaly API | http://localhost:8000 | No login |
| Zabbix Web UI | http://localhost:8080 | Admin / zabbix |

Grafana dashboard paths:

- Dashboards > NHMF > Network Health Monitoring - Hybrid Operations Dashboard
- Dashboards > NHMF > ML Anomaly Detection Dashboard

Direct ML dashboard URL: http://localhost:3000/d/nhmf-ml/ml-anomaly-detection-dashboard

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

The detector combines an Isolation Forest score (65%) with a robust median/MAD deviation score (35%). This keeps the model sensitive to multivariate patterns while retaining an explainable measure of distance from the recent baseline.

Main exported metrics:

```text
nhmf_anomaly_score
nhmf_anomaly_flag
nhmf_anomaly_confidence
nhmf_baseline_deviation
nhmf_anomaly_severity_level
nhmf_anomaly_component_score
nhmf_attack_simulation_active
nhmf_model_trained
nhmf_last_run_timestamp
```

The operations portal displays these metrics on its main board and includes controlled synthetic attack scenarios for CPU, memory, latency and service availability. These scenarios alter only the ML demonstration signals; they do not generate harmful traffic or modify the host.

See `docs/ML_Threshold_Justification.md` for the score bands, colour policy, infrastructure thresholds, validation evidence and tuning limitations.

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
