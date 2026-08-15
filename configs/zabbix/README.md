# Zabbix Infrastructure Monitoring — Architecture & Guide

Zabbix 7.0 LTS is integrated into the NHMF monitoring stack as an enterprise-grade Network Management System (NMS) and infrastructure monitoring layer.

---

## 1. Access Credentials & Endpoints

| Service | Endpoint | Credentials | Role |
|---|---|---|---|
| **Zabbix Web UI** | `http://localhost:8080` | `Admin` / `zabbix` | Web GUI for host management & maps |
| **Zabbix JSON-RPC API** | `http://localhost:8080/api_jsonrpc.php` | `Admin` / `zabbix` | Automated programmatic control |
| **Zabbix Server Daemon** | `localhost:10051` | Native protocol | Active/passive polling and trapper engine |
| **Zabbix Agent** | `localhost:10050` (internal) | Native protocol | OS & Docker metric collector |
| **Zabbix MySQL 8 DB** | `localhost:3306` (internal) | `zabbix` / `zabbix` | Relational storage engine |

---

## 2. Grafana Zabbix Dashboard

A dedicated Grafana dashboard is pre-provisioned at:
**`/d/nhmf-zabbix/zabbix-infrastructure-host-dashboard`**

Features:
- Live service status indicators for Zabbix Web, Server Daemon, and MySQL Database.
- HTTP & ICMP response latency breakdown (connect time, PHP-FPM processing, RTT).
- Host CPU utilization, I/O wait, memory distribution, filesystem space, and network interface throughput.
- Instant cross-links to the native Zabbix Web UI, Operations Dashboard, ML Dashboard, and Suricata IDS.

---

## 3. Automation via Zabbix JSON-RPC API

NHMF includes an automated API management suite in `scripts/`:

```bash
# Check Zabbix API connectivity and list active hosts & problems
./scripts/setup_zabbix.sh status

# Auto-create / register the host in Zabbix with Linux Agent template
./scripts/setup_zabbix.sh setup-host --host-name "NHMF-Docker-Host"

# Inspect current active problems & triggers
./scripts/setup_zabbix.sh problems

# List all available templates
./scripts/setup_zabbix.sh templates
```

---

## 4. Prometheus & Alertmanager Integration

Prometheus continuously probes Zabbix infrastructure via the Blackbox Exporter (`blackbox-http` and `blackbox-icmp`).

Alert rules in `configs/prometheus/alert_rules.yml`:
- `ZabbixWebDown`: Fires if Zabbix Web UI on port 8080 is unreachable for > 2m.
- `ZabbixServerUnreachable`: Fires if Zabbix Server daemon is down for > 2m.
- `ZabbixWebHighLatency`: Fires if Web UI response latency exceeds 500ms for > 2m.
