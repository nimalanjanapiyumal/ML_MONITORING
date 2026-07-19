# ML Threshold and Colour Justification

## Decision approach

The framework uses a hybrid unsupervised anomaly score so that each decision has both a learned and an explainable component:

`final score = (0.65 x Isolation Forest score) + (0.35 x robust baseline-deviation score)`

- The Isolation Forest component detects unusual combinations and shapes in the rolling feature window.
- The robust component measures the latest value against the median using median absolute deviation (MAD). MAD is less affected by a previous spike than a mean and standard deviation baseline.
- A 65/35 weighting keeps the trained model as the primary decision source while giving enough weight to the interpretable baseline deviation to expose sudden operational changes.
- A minimum of 30 samples is required before scoring. Confidence increases toward its full data-coverage value at 120 samples and also increases when the score is clearly separated from the warning boundary.
- The configured contamination value of 0.08 represents an initial assumption that roughly 8% of the training window may contain unusual behaviour. It is a starting point for a controlled lab evaluation, not a universal production value.

## ML score bands and colours

| Score | State | Colour | Reasoning and expected action |
|---:|---|---|---|
| 0.00-0.49 | Normal | Green | The combined evidence remains close to the learned and robust baselines. No intervention is required. |
| 0.50-0.64 | Watch | Yellow | Early deviation is visible, but the evidence is not strong enough to declare an anomaly. The operator should observe the trend and confidence. |
| 0.65-0.84 | Warning | Amber | This is the anomaly decision boundary. The model and/or baseline deviation provide material evidence that current behaviour is abnormal. Correlate with host, availability and alert data. |
| 0.85-1.00 | Critical | Red | The score is far beyond the decision boundary and indicates a high-confidence or high-magnitude event requiring immediate investigation. |

The change from green to yellow intentionally occurs before the anomaly flag. This avoids a binary jump from healthy directly to incident and gives the operator time to inspect a developing trend. Amber means the anomaly threshold has been crossed. Red is reserved for a large separation from normal behaviour, helping the board remain scannable during normal operation.

Colour is never the only indicator. The portal and Grafana panels also show the state name, score, confidence, deviation and metric target so the result remains accessible and auditable.

## Infrastructure thresholds

| Metric | Watch | Warning / alert | Critical visual state | Justification |
|---|---:|---:|---:|---|
| CPU utilisation | 70% | 85% for 3 minutes | 95% | The watch state identifies reduced burst capacity. The sustained 85% rule limits transient alerts, while 95% is reserved for near-saturation. |
| Memory utilisation | 70% | 85% for 3 minutes | 95% | This preserves capacity for application bursts and caches. The critical state indicates a material risk of swapping or out-of-memory termination. |
| Filesystem utilisation | 80% | 85% for 5 minutes | 95% | The longer rule window filters short-lived file activity while preserving time to remove or expand storage before writes fail. |
| HTTP/ICMP availability | Not applicable | Not applicable | Failure for 2 minutes | A two-minute `for` period filters brief network jitter while detecting a sustained outage quickly enough for an operator response. |
| Probe latency | 150 ms | 200 ms for 2 minutes | 400 ms | 200 ms marks sustained user-visible network delay for interactive services; 400 ms indicates severe impairment. These values must be adapted for expected WAN distance. |

Rule-based thresholds describe known operational limits. ML scores describe unusual behaviour relative to learned data. An alert is more persuasive when both agree, while disagreement is useful diagnostic evidence rather than an automatic failure of either method.

An ML warning must persist for 30 seconds, while a critical ML score must persist for 15 seconds. The shorter critical delay is justified by the score already being at least 0.85; both delays still reject a single scrape spike and fit inside the default 60-second controlled simulation.

## Validation evidence

The included UNSW-NB15 evaluation artefact records the following held-out results:

| Task | Metric | Result |
|---|---|---:|
| Binary attack classification | Accuracy | 0.8661 |
| Binary attack classification | Precision | 0.8104 |
| Binary attack classification | Recall | 0.9878 |
| Binary attack classification | F1 | 0.8904 |
| Binary attack classification | ROC AUC | 0.9768 |
| Multiclass attack classification | Accuracy | 0.7419 |
| Multiclass attack classification | Weighted F1 | 0.7749 |
| Multiclass attack classification | ROC AUC | 0.9593 |
| Unsupervised anomaly detection | ROC AUC | 0.7810 |

The high binary recall supports using the classifier as an early-warning signal. However, the multiclass macro F1 (0.4765) indicates weaker performance on less frequent attack classes. The unsupervised AUC of 0.7810 is useful but not sufficient to justify autonomous remediation. For this reason, the framework presents confidence and supporting metrics, requires operator correlation, and treats the current thresholds as testable hypotheses.

## Controlled attack simulations

The portal offers four bounded simulations: CPU spike, memory pressure, latency burst and service outage. They are synthetic ML demonstrations. They do not send attack traffic, consume host resources or disable a real service. Each simulation has a fixed duration, is visibly marked on the main board and returns to the live detector automatically.

These scenarios support repeatable testing of detection visibility, colour transitions, alert interpretation and dashboard usability. Real stress or network fault scripts remain separate and should be used only inside an isolated lab VM.

## Calibration and thesis evaluation

Thresholds should be calibrated against a representative baseline and labelled fault-injection runs. The evaluation should report false-positive rate, precision, recall, F1, detection latency, resource overhead and behaviour as monitored target count increases. A threshold should be changed only when this evidence shows a better operating point, and the change should be recorded with the dataset window and resulting metrics.
