# Submission Notes

This project ZIP is prepared as a reproducible prototype artefact.

## Included Deliverables

- Docker Compose monitoring stack
- Prometheus configuration
- Alertmanager rules
- Grafana datasource and dashboard provisioning
- Blackbox exporter configuration
- Automated seven-server Zabbix monitoring lab
- Python ML anomaly detection API
- Fault injection scripts
- Evidence export script
- Implementation and testing documentation
- Mermaid architecture diagram
- Sample telemetry datasets

## Recommended Screenshots for Final Report

1. Docker containers running
2. Prometheus targets page
3. Grafana dashboard overview
4. Alertmanager active alert
5. ML API results endpoint
6. Fault injection terminal output
7. Evidence export folder
8. Zabbix seven-server dashboard with an individual and multi-server outage
9. Suricata sensor-only and complete-IDS outage recovery

## Limitations

- The seven Zabbix lab hosts are synthetic containerized server roles; production deployment would replace them with real hosts and credentials.
- SNMP monitoring requires real SNMP-enabled devices or simulated devices.
- ML anomaly scores depend on the quality and length of collected telemetry.
- The provided test environment is a lab prototype and should be clearly presented as such in academic evaluation.
