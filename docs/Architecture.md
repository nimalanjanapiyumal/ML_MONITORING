# Architecture

## Layered Artefact Design

The framework follows a layered architecture:

1. **Telemetry Sources**: Linux hosts, network devices, services, ICMP/HTTP endpoints
2. **Collection Layer**: Prometheus exporters and Zabbix agents/proxies
3. **Monitoring and Storage Layer**: Prometheus TSDB and Zabbix database
4. **Processing and ML Layer**: Python anomaly detection API
5. **Presentation and Alert Layer**: Grafana dashboards and Alertmanager
6. **Evaluation Layer**: KPI measurement and fault-injection evidence

## Main Data Flow

1. Exporters expose metrics.
2. Prometheus scrapes metrics from exporters and the ML API.
3. Alert rules evaluate baseline thresholds.
4. The ML module queries Prometheus, computes anomaly scores and exposes them as metrics.
5. Grafana displays raw telemetry, rule-based alerts and ML anomaly scores.
6. Fault injection scripts create controlled abnormal behaviour for evaluation.

## Mermaid Diagram

See `diagrams/architecture.mmd`.
