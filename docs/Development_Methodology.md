# Development Methodology

## Selected Methodology

The project uses an **iterative design-science prototyping methodology**. This is suitable because the project develops a working artefact rather than only producing a theoretical analysis. The artefact integrates monitoring tools, dashboards, alert workflows and a machine-learning anomaly detection module.

## Iteration Logic

Each stage produces a testable output:

1. Environment preparation
2. Baseline monitoring
3. Dashboard development
4. Rule-based alerting
5. ML anomaly detection
6. ML integration with dashboards and Prometheus
7. Fault injection and validation
8. KPI-based evaluation and refinement

## Why This Methodology Is Suitable

The framework contains several independent but connected layers. Building all layers at once would make troubleshooting difficult. Iterative prototyping reduces risk by validating each component before full integration.

For example, Prometheus target scraping is validated before Grafana dashboard development. Rule-based alerts are validated before ML alerts are compared. The ML anomaly detector is first tested using collected metrics and then exposed to Prometheus as custom metrics.

## Software Used

| Development Area | Software |
|---|---|
| Operating system | Ubuntu Server |
| Virtualization | VMware Workstation / VirtualBox |
| Container deployment | Docker, Docker Compose |
| Monitoring | Prometheus, Zabbix |
| Visualization | Grafana |
| Alerting | Alertmanager |
| Exporters | Node Exporter, Blackbox Exporter, Pushgateway |
| ML development | Python, scikit-learn, Pandas, NumPy |
| API layer | FastAPI |
| Testing | ping, iPerf3, stress-ng, tc/netem |
| Version control | Git, GitHub |

## Final Output

The final output is a reproducible monitoring framework that can collect telemetry, visualize network and host health, generate rule-based alerts and display ML-based anomaly scores.
