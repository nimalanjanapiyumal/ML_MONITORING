# Test Plan

Repeatable live demonstrations, expected dashboard values, colors, alerts, and recovery steps are defined in [Demo_Scenarios.md](Demo_Scenarios.md).

## Test Objective

The objective is to validate that the framework can collect telemetry, show dashboards, generate rule-based alerts and detect abnormal patterns using ML anomaly scoring.

## Test Cases

| Test ID | Test Area | Procedure | Expected Result |
|---|---|---|---|
| T01 | Prometheus availability | Open Prometheus health endpoint | Prometheus returns healthy |
| T02 | Target scraping | Open Prometheus targets page | All configured targets show UP |
| T03 | Grafana dashboard | Open dashboard | Panels display metrics |
| T04 | Alertmanager | Trigger target down condition | Alert appears in Alertmanager |
| T05 | ML scoring | Open `/results` endpoint | Anomaly scores are generated |
| T06 | CPU anomaly | Run CPU stress script | CPU graph rises and anomaly score may increase |
| T07 | Network anomaly | Run latency/packet loss script | Probe duration/loss changes and alert may trigger |
| T08 | Evidence export | Run evidence script | JSON/log evidence files are saved |

## Fault Injection Scenarios

### CPU Stress

```bash
sudo apt-get install -y stress-ng
scripts/fault_injection/cpu_stress.sh 60
```

### Memory Stress

```bash
sudo apt-get install -y stress-ng
scripts/fault_injection/memory_stress.sh 60
```

### Latency and Packet Loss

```bash
sudo scripts/fault_injection/latency_packetloss.sh eth0 100ms 5% 60
```

### Target Down

```bash
scripts/fault_injection/target_down_simulation.sh
```

## Evidence Required

- Prometheus targets screenshot
- Grafana dashboard screenshot
- Alertmanager alert screenshot
- ML API `/results` output
- Docker container status
- Exported evidence folder
