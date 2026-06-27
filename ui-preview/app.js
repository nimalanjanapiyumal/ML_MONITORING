const colors = {
  green: "#31c37b",
  red: "#ef5b5b",
  orange: "#f0a33e",
  cyan: "#35b7d7",
  blue: "#688cf5",
  grid: "rgba(255,255,255,0.08)",
  text: "#9ba6ad"
};

function series(length, base, swing, spikeAt = -1, spike = 0) {
  return Array.from({ length }, (_, index) => {
    const wave = Math.sin(index / 2.4) * swing + Math.cos(index / 5.5) * swing * 0.55;
    const raised = spikeAt >= 0 && index >= spikeAt ? spike : 0;
    return Math.max(0, Number((base + wave + raised).toFixed(2)));
  });
}

function drawChart(canvasId, datasets, options = {}) {
  const canvas = document.getElementById(canvasId);
  const context = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = Number(canvas.getAttribute("height"));
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  context.scale(ratio, ratio);

  const padding = { top: 16, right: 18, bottom: 28, left: 42 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const allValues = datasets.flatMap((dataset) => dataset.values);
  const maxValue = options.max ?? Math.max(...allValues) * 1.18;
  const minValue = options.min ?? 0;

  context.clearRect(0, 0, width, height);
  context.strokeStyle = colors.grid;
  context.lineWidth = 1;
  context.fillStyle = colors.text;
  context.font = "11px Inter, system-ui, sans-serif";

  for (let i = 0; i <= 4; i += 1) {
    const y = padding.top + (plotHeight / 4) * i;
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(width - padding.right, y);
    context.stroke();
    const label = maxValue - ((maxValue - minValue) / 4) * i;
    context.fillText(label.toFixed(options.decimals ?? 0), 6, y + 4);
  }

  if (options.threshold) {
    const thresholdY =
      padding.top + plotHeight - ((options.threshold - minValue) / (maxValue - minValue)) * plotHeight;
    context.strokeStyle = options.thresholdColor || colors.orange;
    context.setLineDash([5, 5]);
    context.beginPath();
    context.moveTo(padding.left, thresholdY);
    context.lineTo(width - padding.right, thresholdY);
    context.stroke();
    context.setLineDash([]);
  }

  datasets.forEach((dataset) => {
    context.strokeStyle = dataset.color;
    context.lineWidth = 2.2;
    context.beginPath();
    dataset.values.forEach((value, index) => {
      const x = padding.left + (plotWidth / (dataset.values.length - 1)) * index;
      const y = padding.top + plotHeight - ((value - minValue) / (maxValue - minValue)) * plotHeight;
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    });
    context.stroke();

    const gradient = context.createLinearGradient(0, padding.top, 0, height - padding.bottom);
    gradient.addColorStop(0, `${dataset.color}33`);
    gradient.addColorStop(1, `${dataset.color}00`);
    context.lineTo(width - padding.right, height - padding.bottom);
    context.lineTo(padding.left, height - padding.bottom);
    context.closePath();
    context.fillStyle = gradient;
    context.fill();
  });

  let legendX = padding.left;
  datasets.forEach((dataset) => {
    context.fillStyle = dataset.color;
    context.fillRect(legendX, height - 14, 9, 9);
    context.fillStyle = colors.text;
    context.fillText(dataset.name, legendX + 14, height - 6);
    legendX += context.measureText(dataset.name).width + 42;
  });
}

const chartDefinitions = [
  [
    "latencyChart",
    [
      { name: "8.8.8.8", color: colors.cyan, values: series(36, 0.08, 0.02, 29, 0.13) },
      { name: "1.1.1.1", color: colors.green, values: series(36, 0.06, 0.015) }
    ],
    { max: 0.32, threshold: 0.2, decimals: 2 }
  ],
  [
    "cpuChart",
    [{ name: "node-exporter", color: colors.blue, values: series(36, 28, 7, 30, 18) }],
    { max: 100, threshold: 85 }
  ],
  [
    "memoryChart",
    [{ name: "node-exporter", color: colors.orange, values: series(36, 47, 4, 28, 24) }],
    { max: 100, threshold: 85 }
  ],
  [
    "diskChart",
    [{ name: "root", color: colors.green, values: series(36, 42, 1.6) }],
    { max: 100, threshold: 85 }
  ],
  [
    "networkChart",
    [
      { name: "eth0 receive", color: colors.cyan, values: series(36, 1200, 380, 24, 900) },
      { name: "eth0 transmit", color: colors.blue, values: series(36, 850, 220, 24, 520) }
    ],
    { max: 3100, threshold: 2400 }
  ],
  [
    "anomalyChart",
    [
      { name: "memory_usage_percent", color: colors.red, values: series(36, 0.28, 0.07, 27, 0.35) },
      { name: "cpu_usage_percent", color: colors.orange, values: series(36, 0.2, 0.05, 30, 0.18) },
      { name: "icmp_probe_duration", color: colors.cyan, values: series(36, 0.16, 0.04) }
    ],
    { max: 1, threshold: 0.65, decimals: 2, thresholdColor: colors.red }
  ]
];

function renderCharts() {
  chartDefinitions.forEach(([id, datasets, options]) => drawChart(id, datasets, options));
}

renderCharts();
window.addEventListener("resize", renderCharts);
