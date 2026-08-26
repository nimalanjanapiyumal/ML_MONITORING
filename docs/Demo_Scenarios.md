# NHMF Demonstration Scenarios

The demonstration suite provides repeatable evidence for healthy, watch, warning, and risk states. Availability scenarios stop only the named lab container or explicit group of lab containers, keep a recovery trap active, and restart everything after the selected duration. IDS signature scenarios generate deterministic synthetic EVE records with the host Python runtime and copy them into the running Suricata container, avoiding dependence on an extra Docker image, loopback routing, or an external scan target.

## Visual state policy

| State | Color | Meaning |
|---|---|---|
| Healthy | Green | Metric is within the expected operating range or the service is reachable. |
| Watch | Yellow | Early degradation is visible and should be observed. |
| Warning | Orange | The validated warning boundary has been crossed. |
| Risk / Critical | Red | The service is unavailable or the critical boundary has been crossed. |
| Unknown | Grey | The monitoring API cannot currently make a server-health decision; this is not presented as a confirmed outage. |

The shared numeric boundaries are:

- CPU, memory, and disk: green below 70%, yellow from 70%, orange from 85%, red from 95%.
- ICMP/HTTP latency: green below 150 ms, yellow from 150 ms, orange from 200 ms, red from 500 ms.
- ML anomaly score: green below 0.50, yellow from 0.50, orange from 0.65, red from 0.85.
- General availability: `1` is healthy/green and `0` is risk/red.
- Native Zabbix host health: `2` is healthy/green, `1` is reachable but warning/pending/yellow, `0` is confirmed risk/down or deactivated/red, and `-1` is unknown/API-offline/grey.

## Scenario matrix

Run `./scripts/fault_injection/demo_scenarios.sh list` to print the same list at the command line.

For an interactive demonstration, open the main portal at `http://localhost:8088` and use the Activate/Deactivate control beside any of the seven Zabbix server roles. The native host status changes immediately and is recorded in Grafana's **Zabbix Host Activation Timeline**. Use the command-line outage scenarios when the demonstration specifically needs the agent container itself to stop.

Use at least 150 seconds for Prometheus alerts with a two-minute persistence period. Use 210 seconds for agent scenarios when demonstrating Zabbix's native **agent unavailable for 3 minutes** trigger.

| Scenario | Command | Expected evidence |
|---|---|---|
| Restore seven-green baseline | `./scripts/fault_injection/demo_scenarios.sh zabbix-fleet-online` | Starts all Zabbix components and agents, reconciles their current container addresses, activates all seven hosts, and waits for native health to reach 7/7 green. |
| Toggle all monitoring off/on | `./scripts/fault_injection/demo_scenarios.sh zabbix-monitoring-toggle 60` | All activation rows change to red/deactivated, then the recovery trap reactivates all seven and the timeline returns to green. |
| Suricata sensor outage | `./scripts/fault_injection/demo_scenarios.sh suricata-sensor-outage 90` | Sensor freshness becomes `0`, Sensor Health turns red, and `SuricataSensorDown` fires. The exporter remains scrapeable, proving sensor and exporter health are evaluated separately. |
| Suricata exporter outage | `./scripts/fault_injection/demo_scenarios.sh suricata-exporter-outage 150` | Prometheus scrape status becomes `0`, Sensor Health turns red, and `SuricataExporterDown` fires. |
| Complete Suricata outage | `./scripts/fault_injection/demo_scenarios.sh suricata-full-outage 150` | Both sensor and exporter dashboard health turn red, demonstrating complete IDS visibility loss. Both containers are restored automatically. |
| Zabbix daemon outage | `./scripts/fault_injection/demo_scenarios.sh zabbix-server-outage 150` | TCP/10051 probe becomes `0`; Zabbix Server Daemon and component timeline turn red. |
| Zabbix Web/API outage | `./scripts/fault_injection/demo_scenarios.sh zabbix-web-outage 150` | Web UI/API turns red while Server, MySQL, and all seven agent targets retain their independent state. |
| Zabbix control-plane outage | `./scripts/fault_injection/demo_scenarios.sh zabbix-control-plane-outage 150` | Web/API and Server daemon turn red together while MySQL and agent endpoints remain visible. |
| Zabbix Core Server agent outage | `./scripts/fault_injection/demo_scenarios.sh zabbix-core-agent-outage 210` | Core agent becomes red; healthy server count changes from 7 to 6. |
| Zabbix Application Server outage | `./scripts/fault_injection/demo_scenarios.sh zabbix-application-outage 210` | Application agent becomes red; healthy server count changes from 7 to 6. |
| Zabbix Database Server outage | `./scripts/fault_injection/demo_scenarios.sh zabbix-database-outage 210` | Database agent becomes red; healthy server count changes from 7 to 6. |
| Zabbix Security Server outage | `./scripts/fault_injection/demo_scenarios.sh zabbix-security-outage 210` | Security agent becomes red; healthy server count changes from 7 to 6. |
| Dummy Web Server outage | `./scripts/fault_injection/demo_scenarios.sh zabbix-web-server-outage 210` | Web Server row becomes red and native Zabbix agent availability changes to unavailable. |
| Dummy API Server outage | `./scripts/fault_injection/demo_scenarios.sh zabbix-api-server-outage 210` | API Server row becomes red and native Zabbix agent availability changes to unavailable. |
| Dummy Backup Server outage | `./scripts/fault_injection/demo_scenarios.sh zabbix-backup-server-outage 210` | Backup Server row becomes red and native Zabbix agent availability changes to unavailable. |
| Three-server degradation | `./scripts/fault_injection/demo_scenarios.sh zabbix-multi-server-outage 210` | Web, API, and Backup rows turn red; healthy changes from 7 to 4, unavailable reaches 3/red, and fleet-degradation alerts fire. |
| Complete Zabbix server-fleet outage | `./scripts/fault_injection/demo_scenarios.sh zabbix-fleet-outage 210` | All seven monitored-server rows turn red, healthy reaches 0, unavailable reaches 7, and `ZabbixFleetCritical` fires. |
| Zabbix MySQL outage | `./scripts/fault_injection/demo_scenarios.sh zabbix-db-outage 150` | TCP/3306 probe and MySQL status turn red; dependent Zabbix components may degrade. |
| ML service outage | `./scripts/fault_injection/demo_scenarios.sh ml-outage 150` | ML scrape target becomes unavailable and `TargetDown` fires. |
| TCP scan | `./scripts/fault_injection/demo_scenarios.sh suricata-scan` | Demo SID 9000001 appears in the top-signatures table and alert counters rise. |
| ICMP burst | `./scripts/fault_injection/demo_scenarios.sh suricata-icmp` | Demo SID 9000003 appears and alert/anomaly views are populated. |
| Cleartext Basic Auth | `./scripts/fault_injection/demo_scenarios.sh suricata-http` | Demo SID 9000008 appears in alert and HTTP views. |
| C2 port probe | `./scripts/fault_injection/demo_scenarios.sh suricata-c2` | Critical demo SID 9000006 appears and the critical-alert indicator turns red. |
| All IDS views | `./scripts/fault_injection/demo_scenarios.sh suricata-threats-all` | More than 50 alerts cross the red risk boundary and DNS, TLS, SSH, flow, HTTP, and anomaly panels receive data. |
| Combined attack and server outage | `./scripts/fault_injection/demo_scenarios.sh attack-and-server-outage 90` | Suricata signatures remain visible while the Application Server agent is stopped; both the main portal and Zabbix dashboard report `ATTACK + SERVER OUTAGE`. |
| CPU saturation | `./scripts/fault_injection/demo_scenarios.sh cpu 90` | CPU crosses yellow/orange/red boundaries according to observed utilization. |
| Memory pressure | `./scripts/fault_injection/demo_scenarios.sh memory 90` | Memory crosses yellow/orange/red boundaries according to observed utilization. |
| Latency and loss | `sudo ./scripts/fault_injection/demo_scenarios.sh latency 90 eth0` | ICMP latency crosses the 200 ms warning boundary or probe availability degrades. |

## Demonstration procedure

1. Start the stack, run `./scripts/repair_zabbix_fleet.sh` to establish the seven-green baseline, and then run `./scripts/validate_stack.sh`.
2. Open the relevant Grafana dashboard and select a 15-minute time range.
3. Run one scenario from the matrix. Keep outage scenarios active long enough to satisfy the alert `for` duration.
4. Use the runner's before/during/after output as direct evidence; it reports the same native Zabbix or Suricata state consumed by Grafana.
5. Capture the color transition, firing alert, and target timeline.
6. Wait for automatic recovery and confirm general availability returns to `1`/green and native Zabbix health returns to `2`/green.

These scripts are intended only for the isolated NHMF lab stack. They should not be pointed at systems you do not own or have permission to test.
