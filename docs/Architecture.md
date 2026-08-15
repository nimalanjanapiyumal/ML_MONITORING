# Network Health Monitoring Framework — Architecture

## Layered Architecture Design

The framework follows a modular, layered architecture for observability, security detection, and anomaly intelligence:

1. **Telemetry & Traffic Sources**:
   - Host system metrics (CPU, memory, disk, network throughput)
   - Live packet traffic captured via Linux `AF-PACKET`
   - ICMP ping and HTTP health probe endpoints
   - Optional SNMP network devices

2. **Collection & Ingestion Layer**:
   - **Node Exporter** (`:9100`): Linux kernel, hardware, and OS performance metrics
   - **Blackbox Exporter** (`:9115`): External reachability and latency probing
   - **Suricata IDS** (`host` network mode): Passive deep packet inspection, protocol parsing (HTTP, DNS, TLS/JA3, SSH), and ET Open + custom threat signature matching
   - **Suricata Exporter** (`:9517`): Lightweight Python bridge tailing `eve.json` and exposing Prometheus metrics
   - **Pushgateway** (`:9091`): Ingestion for ephemeral jobs and synthetic metrics
   - **Zabbix Agent** (`:10050`): Agent-based infrastructure monitoring

3. **Time-Series Storage & Rule Engine**:
   - **Prometheus TSDB** (`:9090`): Metric scraping, 15-day retention, PromQL querying
   - **Prometheus Alert Rules**: Evaluates resource saturation, service down, ML anomalies, and Suricata threat triggers

4. **Machine Learning Anomaly Detection Layer**:
   - **ML Anomaly API** (`:8000`): FastAPI engine combining:
     - 65% Isolation Forest trained on UNSW-NB15 dataset
     - 35% Robust Median / Median Absolute Deviation (MAD) baseline
   - Real-time scoring of telemetry streams with confidence intervals

5. **Alerting & Notification Layer**:
   - **Alertmanager** (`:9093`): Deduplication, grouping, severity routing, and webhook dispatch to the ML engine

6. **Visualization & Operations Layer**:
   - **Grafana** (`:3000`): Pre-provisioned dashboards:
     - *Network Health Monitoring - Hybrid Operations Dashboard*
     - *ML Anomaly Detection Dashboard*
     - *Suricata IDS Dashboard*
   - **Operations Portal** (`:8088`): Single-pane web portal with interactive attack simulations and system status

## Architecture Diagram

See [`diagrams/architecture.mmd`](file:///c:/Users/piyum/PycharmProjects/PythonProject/diagrams/architecture.mmd) for the complete Mermaid flowchart.
