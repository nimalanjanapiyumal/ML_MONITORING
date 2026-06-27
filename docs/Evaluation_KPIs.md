# Evaluation KPIs

The project should be evaluated using technical and operational KPIs.

## Technical KPIs

| KPI | Measurement Method |
|---|---|
| Telemetry collection reliability | Percentage of targets showing UP |
| Scrape success | Prometheus target status and scrape duration |
| Query latency | Prometheus graph/query response time |
| Dashboard responsiveness | Grafana panel loading time |
| Resource usage | CPU and memory usage of containers |
| ML processing cycle | Time between anomaly refresh cycles |

## Operational KPIs

| KPI | Measurement Method |
|---|---|
| Time to detect | Time between fault injection and alert/anomaly visibility |
| Alert correctness | Whether expected alert fires for known fault |
| Alert noise | Number of repeated/non-actionable alerts |
| ML usefulness | Whether anomaly score changes during abnormal behaviour |
| Explainability | Whether raw metric and anomaly score can be viewed together |

## Baseline vs Hybrid Comparison

The evaluation should compare:

1. **Baseline mode**: Prometheus rules and Alertmanager only
2. **Hybrid mode**: Rule-based alerts plus ML anomaly scores

The hybrid mode is considered successful if it provides earlier warning, clearer prioritization or useful additional evidence in at least selected test scenarios.
