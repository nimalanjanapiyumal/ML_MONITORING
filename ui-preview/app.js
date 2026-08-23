const host = window.location.hostname || "localhost";
const apiBase = `http://${host}:8000`;

const serviceUrls = {
  "grafana-main": `http://${host}:3000/d/nhmf-main/network-health-monitoring-hybrid-operations-dashboard`,
  "grafana-ml": `http://${host}:3000/d/nhmf-ml/ml-anomaly-detection-dashboard`,
  "grafana-zabbix": `http://${host}:3000/d/nhmf-zabbix/zabbix-infrastructure-host-dashboard`,
  "suricata-ids": `http://${host}:3000/d/nhmf-suricata/suricata-ids-dashboard`,
  prometheus: `http://${host}:9090`,
  alertmanager: `http://${host}:9093`,
  zabbix: `http://${host}:8080`,
  "ml-api": `${apiBase}/docs`,
  "suricata-metrics": `http://${host}:9517/metrics`,
  pushgateway: `http://${host}:9091`,
  blackbox: `http://${host}:9115`
};

const palette = {
  green: "#35c884",
  yellow: "#d7c14b",
  amber: "#e59a3d",
  red: "#ee6262",
  cyan: "#41bad2",
  grid: "rgba(156, 169, 175, 0.17)",
  text: "#9ca9af"
};

const history = {
  scores: [],
  confidence: []
};

let latestOverview = null;
let toastTimer = null;

function element(id) {
  return document.getElementById(id);
}

function finiteNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatNumber(value, decimals = 0, suffix = "") {
  const number = finiteNumber(value);
  return number === null ? "--" : `${number.toFixed(decimals)}${suffix}`;
}

function scoreState(score) {
  const value = finiteNumber(score) ?? 0;
  if (value >= 0.85) return "critical";
  if (value >= 0.65) return "warning";
  if (value >= 0.5) return "watch";
  return "normal";
}

function resourceState(value) {
  const number = finiteNumber(value);
  if (number === null) return "neutral";
  if (number >= 95) return "critical";
  if (number >= 85) return "warning";
  if (number >= 70) return "watch";
  return "normal";
}

function latencyState(seconds) {
  const value = finiteNumber(seconds);
  if (value === null) return "neutral";
  if (value >= 0.5) return "critical";
  if (value >= 0.2) return "warning";
  if (value >= 0.15) return "watch";
  return "normal";
}

function setCardState(id, state) {
  const card = element(id);
  if (card) card.dataset.state = state;
}

function setServiceLinks() {
  document.querySelectorAll("[data-service-link]").forEach((link) => {
    const url = serviceUrls[link.dataset.serviceLink];
    if (!url) return;
    link.href = url;
    link.target = "_blank";
    link.rel = "noreferrer";
  });
}

function setConnection(state, label) {
  const connection = element("connectionState");
  connection.dataset.state = state;
  connection.querySelector("span").textContent = label;
}

function showToast(message, isError = false) {
  const toast = element("toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("visible"), 4200);
}

function updateServiceIndicators(services = {}) {
  document.querySelectorAll("[data-service-status]").forEach((indicator) => {
    const value = finiteNumber(services[indicator.dataset.serviceStatus]);
    indicator.classList.remove("online", "offline");
    if (value === null) return;
    indicator.classList.add(value >= 1 ? "online" : "offline");
  });
}

function updateOperationCards(data) {
  const operations = data.operations || {};
  const ml = data.ml || {};
  const healthy = finiteNumber(operations.healthy_targets);
  const unavailable = finiteNumber(operations.unavailable_targets);
  const alerts = finiteNumber(operations.active_alerts);
  const peakScore = finiteNumber(ml.peak_score) ?? 0;

  element("healthyTargets").textContent = formatNumber(healthy);
  element("healthyReason").textContent = healthy === null ? "Prometheus is not responding" : `${healthy} direct scrapes and endpoint probes succeeded`;
  setCardState("healthyCard", healthy === null ? "neutral" : healthy > 0 ? "normal" : "critical");

  element("unavailableTargets").textContent = formatNumber(unavailable);
  element("unavailableReason").textContent = unavailable === null ? "No availability decision yet" : unavailable > 0 ? "One or more scrapes or endpoint probes failed" : "All monitored checks are available";
  setCardState("unavailableCard", unavailable === null ? "neutral" : unavailable > 0 ? "critical" : "normal");

  element("activeAlerts").textContent = formatNumber(alerts);
  element("alertReason").textContent = alerts === null ? "Alert state is unavailable" : alerts > 0 ? "Review firing rules in Alertmanager" : "No Prometheus alerts are firing";
  setCardState("alertCard", alerts === null ? "neutral" : alerts >= 5 ? "critical" : alerts >= 3 ? "warning" : alerts > 0 ? "watch" : "normal");

  element("modelState").textContent = ml.model_trained ? "Ready" : "Waiting";
  element("modelReason").textContent = ml.model_trained ? `${ml.result_count || 0} metric series scored` : "At least 30 points are required";
  setCardState("modelCard", ml.model_trained ? "info" : "watch");

  element("peakScore").textContent = peakScore.toFixed(2);
  element("scoreReason").textContent = ml.peak_metric ? `${ml.peak_metric}: ${ml.peak_severity}` : "Decision boundary: 0.65";
  setCardState("scoreCard", scoreState(peakScore));
}

function updateSimulation(simulation = {}) {
  const active = Boolean(simulation.active);
  const label = simulation.label || "Idle";
  element("simulationState").textContent = active ? "Active" : "Idle";
  element("simulationReason").textContent = active ? `${label}, ${simulation.remaining_seconds}s remaining` : "No synthetic fault is active";
  setCardState("simulationCard", active ? "warning" : "normal");

  element("activeScenario").textContent = active ? label : "None";
  element("simulationCountdown").textContent = active ? `${simulation.remaining_seconds} seconds remaining` : "Ready for a controlled test";
  element("cancelSimulation").disabled = !active;
  document.querySelectorAll("[data-scenario]").forEach((button) => {
    button.classList.toggle("active", active && button.dataset.scenario === simulation.scenario);
  });
}

function updateMlCards(data) {
  const ml = data.ml || {};
  const operations = data.operations || {};
  const evaluation = ml.training_evaluation || {};
  const confidence = finiteNumber(ml.average_confidence);
  const deviation = finiteNumber(ml.maximum_baseline_deviation);
  const cpu = finiteNumber(operations.cpu_usage_percent);
  const memory = finiteNumber(operations.memory_usage_percent);
  const latency = finiteNumber(operations.icmp_latency_seconds);
  const binaryF1 = finiteNumber(evaluation.binary_f1);

  element("decisionConfidence").textContent = formatNumber(confidence === null ? null : confidence * 100, 0, "%");
  setCardState("confidenceCard", confidence === null ? "neutral" : confidence >= 0.75 ? "normal" : confidence >= 0.5 ? "watch" : "warning");

  element("baselineDeviation").textContent = formatNumber(deviation, 1, "x");
  setCardState("deviationCard", deviation === null ? "neutral" : deviation >= 5 ? "critical" : deviation >= 3 ? "warning" : deviation >= 2 ? "watch" : "normal");

  element("cpuUsage").textContent = formatNumber(cpu, 1, "%");
  setCardState("cpuCard", resourceState(cpu));
  element("memoryUsage").textContent = formatNumber(memory, 1, "%");
  setCardState("memoryCard", resourceState(memory));
  element("icmpLatency").textContent = formatNumber(latency === null ? null : latency * 1000, 0, " ms");
  setCardState("latencyCard", latencyState(latency));

  element("binaryF1").textContent = formatNumber(binaryF1 === null ? null : binaryF1 * 100, 1, "%");
  setCardState("binaryF1Card", "info");
}

function updateMlTable(results = []) {
  const body = element("mlResultsBody");
  body.replaceChildren();
  element("resultCount").textContent = `${results.length} ${results.length === 1 ? "series" : "series"}`;
  if (!results.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.className = "empty-cell";
    cell.textContent = "No ML results have been published yet";
    row.appendChild(cell);
    body.appendChild(row);
    return;
  }

  results.slice(0, 8).forEach((result) => {
    const row = document.createElement("tr");
    const metric = document.createElement("td");
    metric.textContent = result.metric_name || "unknown";
    const score = document.createElement("td");
    score.textContent = formatNumber(result.score, 2);
    const confidence = document.createElement("td");
    confidence.textContent = formatNumber((finiteNumber(result.confidence) ?? 0) * 100, 0, "%");
    const severity = document.createElement("td");
    const tag = document.createElement("span");
    const severityName = result.severity || scoreState(result.score);
    tag.className = `severity-tag ${severityName}`;
    tag.textContent = severityName;
    severity.appendChild(tag);
    row.append(metric, score, confidence, severity);
    body.appendChild(row);
  });
}

function pushHistory(data) {
  const score = finiteNumber(data.ml?.peak_score) ?? 0;
  const confidence = finiteNumber(data.ml?.average_confidence) ?? 0;
  history.scores.push(score);
  history.confidence.push(confidence);
  if (history.scores.length > 60) history.scores.shift();
  if (history.confidence.length > 60) history.confidence.shift();
  drawTrendChart();
}

function drawTrendChart() {
  const canvas = element("mlTrendChart");
  if (!canvas) return;
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(canvas.clientWidth, 280);
  const height = Number(canvas.getAttribute("height")) || 260;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const context = canvas.getContext("2d");
  context.scale(ratio, ratio);

  const padding = { top: 18, right: 16, bottom: 28, left: 42 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  context.clearRect(0, 0, width, height);
  context.font = "11px Inter, system-ui, sans-serif";
  context.fillStyle = palette.text;
  context.strokeStyle = palette.grid;
  context.lineWidth = 1;

  for (let index = 0; index <= 4; index += 1) {
    const value = 1 - index * 0.25;
    const y = padding.top + index * (plotHeight / 4);
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(width - padding.right, y);
    context.stroke();
    context.fillText(value.toFixed(2), 7, y + 4);
  }

  const thresholdY = padding.top + plotHeight * (1 - 0.65);
  context.strokeStyle = palette.amber;
  context.setLineDash([6, 5]);
  context.beginPath();
  context.moveTo(padding.left, thresholdY);
  context.lineTo(width - padding.right, thresholdY);
  context.stroke();
  context.setLineDash([]);

  const drawSeries = (values, color) => {
    if (!values.length) return;
    context.strokeStyle = color;
    context.lineWidth = 2.2;
    context.beginPath();
    values.forEach((value, index) => {
      const divisor = Math.max(values.length - 1, 1);
      const x = padding.left + (plotWidth / divisor) * index;
      const y = padding.top + plotHeight * (1 - Math.max(0, Math.min(value, 1)));
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    });
    context.stroke();
  };

  drawSeries(history.scores, palette.red);
  drawSeries(history.confidence, palette.cyan);

  const legend = [
    ["Anomaly score", palette.red],
    ["Confidence", palette.cyan]
  ];
  let legendX = padding.left;
  legend.forEach(([label, color]) => {
    context.fillStyle = color;
    context.fillRect(legendX, height - 15, 10, 10);
    context.fillStyle = palette.text;
    context.fillText(label, legendX + 15, height - 6);
    legendX += context.measureText(label).width + 52;
  });
}

function updatePortal(data) {
  latestOverview = data;
  const updated = new Date((data.last_updated || Date.now() / 1000) * 1000);
  element("lastUpdated").textContent = `Updated ${updated.toLocaleTimeString()}`;
  setConnection(data.status === "ok" ? "healthy" : "degraded", data.status === "ok" ? "Live" : "Degraded");
  updateOperationCards(data);
  updateSimulation(data.simulation);
  updateMlCards(data);
  updateMlTable(data.ml?.results || []);
  updateServiceIndicators(data.services);
  pushHistory(data);
}

async function refreshOverview(showErrors = false) {
  element("refreshButton").disabled = true;
  try {
    const response = await fetch(`${apiBase}/portal/overview`, { cache: "no-store" });
    if (!response.ok) throw new Error(`ML API returned HTTP ${response.status}`);
    updatePortal(await response.json());
  } catch (error) {
    setConnection("degraded", "API unavailable");
    element("lastUpdated").textContent = "Check the ml-anomaly container";
    if (showErrors) showToast(error.message, true);
  } finally {
    element("refreshButton").disabled = false;
  }
}

async function triggerSimulation(scenario) {
  const duration = Number(element("simulationDuration").value);
  document.querySelectorAll("[data-scenario]").forEach((button) => {
    button.disabled = true;
  });
  try {
    const response = await fetch(`${apiBase}/attack-simulations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario, duration_seconds: duration })
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `Simulation failed with HTTP ${response.status}`);
    showToast(`${payload.simulation.label} simulation started for ${duration} seconds`);
    await refreshOverview(true);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    document.querySelectorAll("[data-scenario]").forEach((button) => {
      button.disabled = false;
    });
  }
}

async function cancelSimulation() {
  try {
    const response = await fetch(`${apiBase}/attack-simulations/current`, { method: "DELETE" });
    if (!response.ok) throw new Error(`Unable to stop simulation: HTTP ${response.status}`);
    showToast("Controlled simulation stopped");
    await refreshOverview(true);
  } catch (error) {
    showToast(error.message, true);
  }
}

setServiceLinks();
element("refreshButton").addEventListener("click", () => refreshOverview(true));
element("cancelSimulation").addEventListener("click", cancelSimulation);
document.querySelectorAll("[data-scenario]").forEach((button) => {
  button.addEventListener("click", () => triggerSimulation(button.dataset.scenario));
});
window.addEventListener("resize", drawTrendChart);

refreshOverview(true);
window.setInterval(() => refreshOverview(false), 10000);
