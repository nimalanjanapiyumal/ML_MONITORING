# Scalable Network Health Monitoring Framework Using Open-Source Tools (NHMF)

[![Ubuntu Tested](https://img.shields.io/badge/Platform-Ubuntu%2022.04%20%2F%2024.04-orange.svg)](https://ubuntu.com/)
[![Docker](https://img.shields.io/badge/Docker-Engine%2020%2B%20%7C%20Compose%20v2-blue.svg)](https://www.docker.com/)
[![Prometheus](https://img.shields.io/badge/Prometheus-v2.54.1-e6522c.svg)](https://prometheus.io/)
[![Grafana](https://img.shields.io/badge/Grafana-v11.2.0-F46800.svg)](https://grafana.com/)
[![Suricata](https://img.shields.io/badge/Suricata-IDS%20%2F%20IPS-red.svg)](https://suricata.io/)
[![FastAPI ML](https://img.shields.io/badge/ML%20Engine-FastAPI%20%2B%20scikit--learn-009688.svg)](https://fastapi.tiangolo.com/)

An enterprise-grade, open-source **Network Health Monitoring & Intrusion Detection Framework (NHMF)**. This solution merges multi-tier infrastructure telemetry, passive deep packet inspection (Suricata IDS), and supervised/unsupervised Machine Learning anomaly scoring (UNSW-NB15 trained Isolation Forest + Robust MAD).

---

## Architecture Overview

The framework operates across 6 integrated functional layers:

```
                           +-------------------------------------------------------------+
                           |               Interactive Operations Portal                 |
                           |                   http://localhost:8088                     |
                           +------------------------------+------------------------------+
                                                          |
                                                          v
                               +---------------------------------------------------+
                               |                 Grafana (v11.2.0)                 |
                               |  - Network Health Operations Dashboard            |
                               |  - ML Anomaly Intelligence Dashboard              |
                               |  - Suricata IDS Threat Intelligence Dashboard     |
                               +--------------------------+------------------------+
                                                          |
                      +-----------------------------------+-----------------------------------+
                      |                                                                       |
                      v                                                                       v
+-------------------------------------------+                       +-----------------------------------+
|             Prometheus TSDB               |                       |           Zabbix Stack            |
|  - Time-Series Telemetry (15-day storage) |                       |  - Server, Web, MySQL, 4 Agents  |
|  - Baseline & Threat Alerting Rules       |                       |  - Enterprise Agent Monitoring    |
+---+-------------------+---------------+---+                       +-----------------------------------+
    |                   |               |
    |                   |               +-----------------------------------+
    |                   v                                                   |
    |   +-------------------------------+                                   |
    |   |         Alertmanager          |                                   |
    |   |  - Deduplication & Routing    |                                   |
    |   |  - Webhook to ML Feedback     |                                   |
    |   +---------------+---------------+                                   |
    |                   |                                                   |
    v                   v                                                   v
+-------------------------------+                       +---------------------------------------+
|        ML Anomaly API         |                       |      Host & Network Exporters         |
|  - UNSW-NB15 Isolation Forest |                       |  - Node Exporter (:9100)              |
|  - Robust Median/MAD Baseline |                       |  - Blackbox ICMP/HTTP Probe (:9115)   |
|  - Real-time Threat Scoring   |                       |  - Pushgateway Batch Scraper (:9091)  |
+-------------------------------+                       +---------------------------------------+
                                                                            ^
                                                                            |
                                                        +-------------------+-------------------+
                                                        |                                       |
                                            +-----------+-----------+               +-----------+-----------+
                                            |   Suricata Exporter   |               |     Suricata IDS      |
                                            |  - EVE-JSON Parser    |<--------------|  - AF-PACKET Capture  |
                                            |  - Metrics on :9517   |  (eve.json)   |  - ET Open + Custom   |
                                            +-----------------------+               +-----------------------+
```

---

## Component & Port Matrix

| Service | Port | Endpoint / Health URL | Authentication | Description |
|---|---|---|---|---|
| **NHMF Portal** | `8088` | `http://localhost:8088` | None | Single-pane-of-glass operations interface & simulation triggers |
| **Grafana** | `3000` | `http://localhost:3000` | `admin` / `admin123` | Provisioned dashboards (Main, ML, Suricata IDS) |
| **Prometheus** | `9090` | `http://localhost:9090/-/healthy` | None | TSDB metric aggregation and rule evaluation |
| **Alertmanager** | `9093` | `http://localhost:9093/-/healthy` | None | Alert routing, grouping, and webhook notifications |
| **ML Anomaly API** | `8000` | `http://localhost:8000/health` | None | FastAPI anomaly scoring engine & metrics (`/metrics`) |
| **Suricata Exporter** | `9517` | `http://localhost:9517/health` | None | EVE-JSON tailer exporting IDS metrics (`/metrics`) |
| **Node Exporter** | `9100` | `http://localhost:9100/metrics` | None | Host CPU, RAM, Disk, and Network telemetry |
| **Blackbox Exporter** | `9115` | `http://localhost:9115/probe` | None | ICMP ping and HTTP health probes |
| **Pushgateway** | `9091` | `http://localhost:9091/metrics` | None | Batch job and synthetic telemetry ingress |
| **Zabbix Web** | `8080` | `http://localhost:8080` | `Admin` / `zabbix` | Optional enterprise NMS web interface |
| **Zabbix Server** | `10051` | `localhost:10051` | Native | Zabbix trapper and poller daemon |
| **Zabbix Agents** | `10050` | Docker-internal TCP endpoints | Native | Core, application, database, and security demo servers |

---

## Directory Structure

```text
.
├── docker-compose.yml              # Complete multi-container deployment definition
├── .env.example                    # Template for environment variables and interface binding
├── run.sh                          # Primary Linux entry point with automated permissions
├── run.ps1                         # Primary Windows PowerShell entry point
├── PROJECT_MANIFEST.txt            # Complete manifest of tracked project files
├── README.md                       # Comprehensive framework documentation
│
├── configs/                        # Component configuration files
│   ├── alertmanager/               # Alertmanager routing and webhook rules
│   │   └── alertmanager.yml
│   ├── blackbox/                   # ICMP and HTTP probe definitions
│   │   └── blackbox.yml
│   ├── grafana/                    # Automated Grafana provisioning
│   │   ├── dashboards/             # Pre-built JSON dashboard layouts
│   │   │   ├── network-health-dashboard.json
│   │   │   ├── ml-anomaly-dashboard.json
│   │   │   └── suricata-ids-dashboard.json
│   │   └── provisioning/           # Datasource & dashboard providers
│   ├── prometheus/                 # Prometheus scrape targets & alert rules
│   │   ├── prometheus.yml
│   │   └── alert_rules.yml
│   ├── snmp/                       # SNMP exporter target templates
│   │   └── snmp-targets-example.yml
│   ├── suricata/                   # Suricata IDS engine configuration & rules
│   │   ├── suricata.yaml           # AF-PACKET, EVE-JSON, and protocol settings
│   │   └── rules/
│   │       └── local.rules         # Custom port scan, ICMP flood, C2 rules
│   └── zabbix/                     # Zabbix stack setup documentation
│       └── README.md
│
├── diagrams/                       # Architecture diagrams (Mermaid format)
│   └── architecture.mmd
│
├── docs/                           # In-depth technical specifications
│   ├── Architecture.md             # Layered architecture design document
│   ├── Development_Methodology.md  # 8-step developmental methodology
│   ├── Evaluation_KPIs.md          # KPI evaluation benchmarks (TTD, noise, load)
│   ├── Implementation_Guide.md     # Step-by-step deployment guide
│   ├── ML_Threshold_Justification.md# ML decision boundary justification
│   ├── README_FOR_SUBMISSION.md    # Academic submission overview
│   ├── Test_Plan.md                # Comprehensive test strategy
│   └── Demo_Scenarios.md           # Outage, IDS, resource, and recovery demonstrations
│
├── ml-anomaly/                     # Machine Learning engine
│   ├── Dockerfile                  # Python container build specification
│   ├── requirements.txt            # FastAPI, scikit-learn, pandas, numpy
│   ├── config.yaml                 # ML polling interval & scoring weights
│   ├── app.py                      # FastAPI application with REST & Prom endpoints
│   ├── anomaly_detector.py         # Isolation Forest & robust MAD detector
│   ├── train_unsw_nb15.py          # Model training CLI script
│   └── unsw_nb15_pipeline.py       # UNSW-NB15 feature engineering pipeline
│
├── scripts/                        # Automation, operational & test scripts
│   ├── install_docker_ubuntu.sh    # Automated Docker & Compose installer
│   ├── start_stack.sh              # Stack launcher with interface auto-detect
│   ├── start_stack.ps1             # PowerShell launcher for Windows
│   ├── stop_stack.sh               # Graceful container shutdown
│   ├── validate_stack.sh           # End-to-end component health verifier
│   ├── export_evidence.sh          # Automated evidence & log collector
│   ├── update_suricata_rules.sh    # Online Emerging Threats rule updater
│   ├── fix_conflicts.sh            # One-shot repo conflict cleaner
│   └── fault_injection/            # Controlled chaos & threat simulation
│       ├── cpu_stress.sh           # CPU saturation generator
│       ├── memory_stress.sh        # Memory allocation generator
│       ├── latency_packetloss.sh   # Linux netem network degradation
│       ├── simulate_network_attacks.sh # Safe TCP/ICMP/HTTP threat generator
│       ├── inject_suricata_demo_events.py # Deterministic synthetic EVE event generator
│       ├── target_down_simulation.sh   # Backward-compatible ML outage simulator
│       └── demo_scenarios.sh           # Complete repeatable demonstration runner
│
├── suricata-exporter/              # Suricata EVE-JSON to Prometheus bridge
│   ├── Dockerfile                  # Exporter container definition
│   ├── exporter.py                 # Multi-threaded EVE-JSON log tailer
│   └── requirements.txt            # prometheus-client, watchdog
│
├── tests/                          # Unit and integration test suite
│   ├── test_feature_engineering.py
│   ├── test_portal_api.py
│   └── test_unsw_nb15_pipeline.py
│
└── ui-preview/                     # Operations Portal static assets (Nginx served)
    ├── index.html
    ├── styles.css
    └── app.js
```

---

## Quick Start Guide (Ubuntu 22.04 / 24.04)

### 1. Install Docker & Docker Compose Plugin

If Docker is not already installed on your Ubuntu host, run the automated setup script:

```bash
chmod +x scripts/install_docker_ubuntu.sh
./scripts/install_docker_ubuntu.sh
```

> **Note:** If prompted, log out and back in (or run `newgrp docker`) to activate non-root Docker execution permissions.

### 2. Launch the Entire Framework

Launch all monitoring services with a single command:

```bash
bash run.sh
```

This automated runner performs:
1. Auto-detects the active network interface for Suricata (`SURICATA_INTERFACE`, e.g., `eth0`, `enp0s3`).
2. Creates `.env` from `.env.example` if not already present.
3. Cleans up any stale legacy containers.
4. Verifies the UNSW-NB15 dataset and trains the initial model if needed.
5. Builds and deploys the entire Docker Compose stack.
6. Runs automated health probes against all endpoints.

#### Optional Run Flags

```bash
# Skip ML retraining to start immediately (fast start)
bash run.sh --skip-train

# Force retraining of the UNSW-NB15 model bundle
bash run.sh --retrain
```

---

## Windows Quick Start (PowerShell)

On Windows running Docker Desktop:

```powershell
.\run.ps1 -SkipTrain
```

---

## Security & Intrusion Detection (Suricata IDS)

Suricata runs in `host` network mode with kernel AF-PACKET capture enabled. It inspects all ingress/egress network packets in real-time without inline latency penalty.

### EVE-JSON Metric Pipeline

Suricata streams security events into `/var/log/suricata/eve.json`. The **`suricata-exporter`** service tails this log and exposes aggregated time-series metrics to Prometheus:

- `suricata_alerts_total{signature, category, severity, proto}`: Alert counters
- `suricata_alerts_last_window`: Rolling 1-hour active alert count
- `suricata_flow_bytes_total{direction}`: Ingress / egress byte throughput
- `suricata_flow_packets_total{direction}`: Ingress / egress packet throughput
- `suricata_dns_queries_total{rrtype, rcode}`: DNS queries and response codes
- `suricata_http_requests_total{method, status}`: HTTP method and response distribution
- `suricata_tls_sessions_total{version, ja3_hash}`: TLS versions and JA3 fingerprints
- `suricata_ssh_sessions_total`: SSH client and server banners
- `suricata_drop_packets_total`: Packet drop events (IPS mode)

### Updating Threat Rules

Suricata automatically loads the **Emerging Threats (ET) Open** ruleset alongside custom rules in `configs/suricata/rules/local.rules`. To update rules live without restarting containers:

```bash
./scripts/update_suricata_rules.sh
```

---

## Machine Learning Anomaly Detection

The ML subsystem operates a hybrid decision algorithm:
- **65% Weight**: Unsupervised Isolation Forest / One-Class classifier trained on the **UNSW-NB15** network security dataset.
- **35% Weight**: Robust statistical baseline using rolling Median and Median Absolute Deviation (MAD).

### Exported ML Prometheus Metrics

- `nhmf_anomaly_score`: Continuous anomaly score in $[0.0, 1.0]$
- `nhmf_anomaly_flag`: Binary indicator ($1 = \text{Anomaly}, 0 = \text{Normal}$)
- `nhmf_anomaly_confidence`: Metric coverage and decision certainty
- `nhmf_baseline_deviation`: Robust deviation from historical baseline (MAD units)
- `nhmf_anomaly_severity_level`: Categorical severity ($0=\text{Normal}, 1=\text{Watch}, 2=\text{Warning}, 3=\text{Critical}$)

---

## Grafana Dashboards

Grafana is pre-provisioned with 4 dashboards located in the **NHMF** folder:

1. **Network Health Monitoring - Hybrid Operations Dashboard** (`/d/nhmf-main/`):
   - Executive overview: Target uptime, active alerts, host CPU/RAM/Disk baselines, and ICMP probe duration.
2. **ML Anomaly Detection Dashboard** (`/d/nhmf-ml/`):
   - Real-time ML anomaly score curves, confidence bands, baseline deviation, and model training state.
3. **Suricata IDS Dashboard** (`/d/nhmf-suricata/`):
   - 20-panel threat monitoring view: Stacked alert rate timeline, top 15 signatures, protocol distribution, flow throughput, DNS record anomalies, TLS JA3 hashes, and HTTP status codes.
4. **Zabbix Infrastructure & Host Dashboard** (`/d/nhmf-zabbix/`):
   - Zabbix Web latency, Server and MySQL TCP health, CPU/Memory/Disk/Network metrics, active alerts, and a four-server availability timeline.

---

## Zabbix Enterprise NMS & API Automation

Zabbix 7.0 LTS is fully integrated with automated JSON-RPC API tooling:

After Zabbix Web becomes ready, the startup script uses the host Python runtime to idempotently register the core `Zabbix server` plus `NHMF Application Server`, `NHMF Database Server`, and `NHMF Security Server` with the Linux agent template. This avoids pulling an extra utility image during startup.

### Managing Zabbix via CLI

```bash
# Check Zabbix API status and list monitored hosts & problems
./scripts/setup_zabbix.sh status

# Auto-register / link host with Linux Agent template
./scripts/setup_zabbix.sh setup-host --host-name "NHMF-Docker-Host"

# Reconcile all four bundled demonstration hosts and Docker DNS interfaces
./scripts/setup_zabbix.sh setup-demo-hosts

# Display native agent availability and agent.ping state for all four servers
./scripts/setup_zabbix.sh status

# Inspect current active problem triggers
./scripts/setup_zabbix.sh problems

# List all available monitoring templates
./scripts/setup_zabbix.sh templates
```

- **Web GUI:** [http://localhost:8080](http://localhost:8080) (`Admin` / `zabbix`)
- **JSON-RPC API:** `http://localhost:8080/api_jsonrpc.php`

---

## Fault Injection & Threat Simulation Suite

Test alert triggers, ML reaction, and dashboard response using the built-in simulation suite:

### 1. Demonstrate Suricata Security Events
The primary demo path generates deterministic synthetic EVE records with host Python and copies them into the running Suricata container, so every dashboard view works without scanning a live target or pulling an extra utility image:

```bash
# Populate all alert, flow, DNS, TLS, SSH, and anomaly views
./scripts/fault_injection/demo_scenarios.sh suricata-threats-all

# Populate one signature case: scan | icmp | http | c2
./scripts/fault_injection/demo_scenarios.sh suricata-scan
```

For a real packet-capture test, `simulate_network_attacks.sh` remains available but must be given an explicitly authorized lab target reachable through the interface Suricata monitors.

### 2. Simulate Host Stress & Latency
```bash
# CPU Saturation (stress 2 cores for 60s)
./scripts/fault_injection/cpu_stress.sh 60

# Memory Saturation (allocate 512MB for 60s)
./scripts/fault_injection/memory_stress.sh 60

# Network Latency & Packet Loss (100ms delay, 5% loss on eth0 for 60s)
sudo ./scripts/fault_injection/latency_packetloss.sh eth0 100ms 5% 60

# List all repeatable dashboard, IDS, resource, and outage scenarios
./scripts/fault_injection/demo_scenarios.sh list

# Stop the Suricata sensor for 90 seconds and restore it automatically
./scripts/fault_injection/demo_scenarios.sh suricata-sensor-outage 90

# Stop one Zabbix-monitored server for 150 seconds
./scripts/fault_injection/demo_scenarios.sh zabbix-application-outage 150
```

The complete expected-value and color-transition matrix is in [docs/Demo_Scenarios.md](docs/Demo_Scenarios.md).

---

## Validation & Evidence Export

### Validate System Health
Verify that all containers, scrape targets, rules, and exporters are operational:

```bash
./scripts/validate_stack.sh
```

### Export Complete Evaluation Evidence
Generates an audit bundle containing container status, rendered compose spec, Prometheus targets/alerts/rules, ML metrics, Suricata EVE logs, and all service logs:

```bash
./scripts/export_evidence.sh
```

Evidence is saved to `evidence/evidence_YYYYMMDD_HHMMSS/` for evaluation and academic review.

---

## Stopping the Stack

To shut down all containers gracefully:

```bash
./scripts/stop_stack.sh
```

To stop containers and wipe persistent TSDB data volumes:

```bash
docker compose down -v
```

---

## Troubleshooting & FAQ

### 1. `unexpected character '<' in variable name` in `.env`
If you encounter git merge conflict markers in `.env`, run the repository conflict fixer:
```bash
bash scripts/fix_conflicts.sh
```

### 2. Suricata Not Seeing Host Traffic
Ensure `SURICATA_INTERFACE` in `.env` matches your active network interface. Check your default interface with:
```bash
ip route get 8.8.8.8 | awk '{for(i=1;i<=NF;i++) if ($i=="dev") print $(i+1); exit}'
```

### 3. Port Conflicts (e.g., Port 80, 8080, 3000 in use)
Change the host port mapping in `docker-compose.yml` (e.g., change `"3000:3000"` to `"3001:3000"` for Grafana).

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
