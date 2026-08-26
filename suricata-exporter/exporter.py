#!/usr/bin/env python3
"""
suricata-exporter — Suricata EVE-JSON → Prometheus Metrics Bridge
=================================================================
Tails /var/log/suricata/eve.json, parses each JSON event, and exposes
aggregated counters + gauges on :9517/metrics for Prometheus to scrape.

Metrics exposed:
  suricata_alerts_total          Counter  alert events (by sig/cat/severity/proto)
  suricata_alerts_last_window    Gauge    rolling alert count (configurable window)
  suricata_flow_bytes_total      Counter  bytes per direction (to_server / to_client)
  suricata_flow_packets_total    Counter  packets per direction
  suricata_dns_queries_total     Counter  DNS queries by type (A/AAAA/MX/TXT/…)
  suricata_http_requests_total   Counter  HTTP requests by method + status code
  suricata_tls_sessions_total    Counter  TLS sessions by version + JA3 fingerprint
  suricata_ssh_sessions_total    Counter  SSH sessions by client/server software
  suricata_drop_packets_total    Counter  dropped packets (IPS mode)
  suricata_anomaly_events_total  Counter  protocol anomaly events by type + layer
  suricata_stats_uptime_seconds  Gauge    Suricata process uptime from stats events
  suricata_eve_events_total      Counter  total EVE events processed by event type
  suricata_exporter_errors_total Counter  parsing errors in this exporter

Author: NHMF — auto-generated
"""

from __future__ import annotations

import json
import os
import sys
import time
import threading
import logging
from collections import deque
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional

from prometheus_client import (
    Counter,
    Gauge,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# ─── Configuration ────────────────────────────────────────────────────────────
EVE_JSON_PATH: str = os.getenv("EVE_JSON_PATH", "/var/log/suricata/eve.json")
EXPORTER_PORT: int = int(os.getenv("EXPORTER_PORT", "9517"))
ROLLING_WINDOW_SECONDS: int = int(os.getenv("ROLLING_WINDOW_SECONDS", "3600"))
SENSOR_STALE_AFTER_SECONDS: int = int(os.getenv("SENSOR_STALE_AFTER_SECONDS", "30"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
TAIL_POLL_INTERVAL: float = float(os.getenv("TAIL_POLL_INTERVAL", "0.5"))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("suricata-exporter")

# ─── Prometheus Registry ──────────────────────────────────────────────────────
registry = CollectorRegistry()

# Total alert events
alerts_total = Counter(
    "suricata_alerts_total",
    "Total Suricata IDS alert events",
    ["signature", "category", "severity", "proto", "app_proto"],
    registry=registry,
)

# Rolling alert window gauge (alerts in last N seconds)
alerts_window = Gauge(
    "suricata_alerts_last_window",
    "Number of Suricata alerts in the last rolling window (see ROLLING_WINDOW_SECONDS)",
    registry=registry,
)

# Flow bytes
flow_bytes = Counter(
    "suricata_flow_bytes_total",
    "Total bytes tracked in Suricata flow events",
    ["direction"],
    registry=registry,
)

# Flow packets
flow_packets = Counter(
    "suricata_flow_packets_total",
    "Total packets tracked in Suricata flow events",
    ["direction"],
    registry=registry,
)

# DNS queries
dns_queries = Counter(
    "suricata_dns_queries_total",
    "Total DNS queries observed by Suricata",
    ["rrtype", "rcode"],
    registry=registry,
)

# HTTP requests
http_requests = Counter(
    "suricata_http_requests_total",
    "Total HTTP transactions observed by Suricata",
    ["method", "status"],
    registry=registry,
)

# TLS sessions
tls_sessions = Counter(
    "suricata_tls_sessions_total",
    "Total TLS sessions observed by Suricata",
    ["version", "ja3_hash"],
    registry=registry,
)

# SSH sessions
ssh_sessions = Counter(
    "suricata_ssh_sessions_total",
    "Total SSH sessions observed by Suricata",
    ["client_software", "server_software"],
    registry=registry,
)

# Anomaly events
anomaly_events = Counter(
    "suricata_anomaly_events_total",
    "Total Suricata protocol anomaly events",
    ["type", "layer"],
    registry=registry,
)

# Drop packets (IPS mode)
drop_packets = Counter(
    "suricata_drop_packets_total",
    "Total packets dropped by Suricata (IPS mode only)",
    registry=registry,
)

# Suricata uptime from stats events
suricata_uptime = Gauge(
    "suricata_stats_uptime_seconds",
    "Suricata process uptime in seconds (from stats EVE events)",
    registry=registry,
)

# Raw event type counters
eve_events_total = Counter(
    "suricata_eve_events_total",
    "Total EVE-JSON events processed by this exporter, by event type",
    ["event_type"],
    registry=registry,
)

# Exporter internal errors
exporter_errors = Counter(
    "suricata_exporter_errors_total",
    "Total parsing or processing errors in suricata-exporter",
    ["stage"],
    registry=registry,
)

# Sensor freshness and capture-health metrics. These distinguish a healthy
# exporter process from a healthy Suricata sensor producing current stats.
sensor_health = Gauge(
    "suricata_sensor_health",
    "Whether the Suricata sensor has produced a stats event within the configured freshness window.",
    registry=registry,
)
eve_file_available = Gauge(
    "suricata_eve_file_available",
    "Whether the configured Suricata EVE-JSON file currently exists.",
    registry=registry,
)
eve_last_event_timestamp = Gauge(
    "suricata_eve_last_event_timestamp_seconds",
    "Unix timestamp when the exporter last processed an EVE event.",
    registry=registry,
)
stats_last_event_timestamp = Gauge(
    "suricata_stats_last_event_timestamp_seconds",
    "Unix timestamp when the exporter last processed a Suricata stats event.",
    registry=registry,
)
capture_packets = Gauge(
    "suricata_stats_capture_packets",
    "Latest cumulative kernel packet count reported by Suricata stats.",
    registry=registry,
)
capture_kernel_drops = Gauge(
    "suricata_stats_kernel_drops",
    "Latest cumulative kernel drop count reported by Suricata stats.",
    registry=registry,
)
capture_kernel_drop_ratio = Gauge(
    "suricata_stats_kernel_drop_ratio_percent",
    "Kernel packet drops as a percentage of captured packets from the latest Suricata stats event.",
    registry=registry,
)

# ─── Rolling alert window ────────────────────────────────────────────────────
# Store timestamps of recent alerts for the rolling gauge
_alert_timestamps: deque[float] = deque()
_alert_lock = threading.Lock()
_last_stats_observed_at = 0.0
_last_event_observed_at = 0.0
_events_processed = 0
_latest_alert: dict = {}


def _record_alert_timestamp(details: Optional[dict] = None) -> None:
    global _latest_alert
    now = time.time()
    with _alert_lock:
        _alert_timestamps.append(now)
        if details:
            _latest_alert = {**details, "observed_at": now}


def _update_alert_window_gauge() -> None:
    """Periodically prune old timestamps and update the gauge."""
    while True:
        try:
            cutoff = time.time() - ROLLING_WINDOW_SECONDS
            with _alert_lock:
                while _alert_timestamps and _alert_timestamps[0] < cutoff:
                    _alert_timestamps.popleft()
                alerts_window.set(len(_alert_timestamps))
        except Exception as exc:
            log.warning("Alert window update failed: %s", exc)
        time.sleep(5)


def _sensor_is_healthy(now: Optional[float] = None) -> bool:
    observed_at = now if now is not None else time.time()
    stats_fresh = (
        _last_stats_observed_at > 0
        and observed_at - _last_stats_observed_at <= SENSOR_STALE_AFTER_SECONDS
    )
    return Path(EVE_JSON_PATH).exists() and stats_fresh


def _status_payload() -> dict:
    now = time.time()
    with _alert_lock:
        recent_alerts = len(_alert_timestamps)
        latest_alert = dict(_latest_alert)
    return {
        "exporter": "ok",
        "sensor": "healthy" if _sensor_is_healthy(now) else "stale_or_unavailable",
        "sensor_healthy": _sensor_is_healthy(now),
        "eve_file": EVE_JSON_PATH,
        "eve_file_available": Path(EVE_JSON_PATH).exists(),
        "events_processed": _events_processed,
        "alerts_in_window": recent_alerts,
        "latest_alert": latest_alert or None,
        "last_event_age_seconds": round(now - _last_event_observed_at, 3) if _last_event_observed_at else None,
        "last_stats_age_seconds": round(now - _last_stats_observed_at, 3) if _last_stats_observed_at else None,
        "sensor_stale_after_seconds": SENSOR_STALE_AFTER_SECONDS,
        "rolling_window_seconds": ROLLING_WINDOW_SECONDS,
    }


def _update_sensor_health_gauges() -> None:
    while True:
        try:
            eve_file_available.set(1 if Path(EVE_JSON_PATH).exists() else 0)
            sensor_health.set(1 if _sensor_is_healthy() else 0)
        except Exception as exc:
            log.warning("Sensor health update failed: %s", exc)
            sensor_health.set(0)
        time.sleep(1)


# ─── Event Parsers ────────────────────────────────────────────────────────────

def _safe_str(val: object, max_len: int = 80, fallback: str = "unknown") -> str:
    """Return a sanitised, label-safe string truncated to max_len."""
    if val is None:
        return fallback
    s = str(val).strip()
    return s[:max_len] if s else fallback


def handle_alert(evt: dict) -> None:
    alert = evt.get("alert", {})
    sig = _safe_str(alert.get("signature"), 120)
    cat = _safe_str(alert.get("category"), 80)
    sev = str(alert.get("severity", 3))
    proto = _safe_str(evt.get("proto"), 20)
    app_proto = _safe_str(evt.get("app_proto"), 30)
    alerts_total.labels(signature=sig, category=cat, severity=sev,
                        proto=proto, app_proto=app_proto).inc()
    _record_alert_timestamp(
        {
            "signature": sig,
            "category": cat,
            "severity": sev,
            "proto": proto,
            "app_proto": app_proto,
        }
    )


def handle_flow(evt: dict) -> None:
    flow = evt.get("flow", {})
    bytes_ts = flow.get("bytes_toserver", 0) or 0
    bytes_tc = flow.get("bytes_toclient", 0) or 0
    pkts_ts = flow.get("pkts_toserver", 0) or 0
    pkts_tc = flow.get("pkts_toclient", 0) or 0
    flow_bytes.labels(direction="to_server").inc(bytes_ts)
    flow_bytes.labels(direction="to_client").inc(bytes_tc)
    flow_packets.labels(direction="to_server").inc(pkts_ts)
    flow_packets.labels(direction="to_client").inc(pkts_tc)


def handle_dns(evt: dict) -> None:
    dns = evt.get("dns", {})
    # EVE DNS v2 has type: query / answer
    if dns.get("type") == "query":
        rrtype = _safe_str(dns.get("rrtype"), 10)
        rcode = "N/A"
    else:
        rrtype = _safe_str(dns.get("rrtype"), 10)
        rcode = _safe_str(dns.get("rcode"), 10)
    dns_queries.labels(rrtype=rrtype, rcode=rcode).inc()


def handle_http(evt: dict) -> None:
    http = evt.get("http", {})
    method = _safe_str(http.get("http_method"), 10)
    status = str(http.get("status", 0))
    http_requests.labels(method=method, status=status).inc()


def handle_tls(evt: dict) -> None:
    tls = evt.get("tls", {})
    version = _safe_str(tls.get("version"), 20)
    ja3 = _safe_str(tls.get("ja3", {}).get("hash") if isinstance(tls.get("ja3"), dict) else None, 40, "none")
    tls_sessions.labels(version=version, ja3_hash=ja3).inc()


def handle_ssh(evt: dict) -> None:
    ssh = evt.get("ssh", {})
    client = _safe_str(ssh.get("client", {}).get("software_version") if isinstance(ssh.get("client"), dict) else None, 40)
    server = _safe_str(ssh.get("server", {}).get("software_version") if isinstance(ssh.get("server"), dict) else None, 40)
    ssh_sessions.labels(client_software=client, server_software=server).inc()


def handle_anomaly(evt: dict) -> None:
    anomaly = evt.get("anomaly", {})
    atype = _safe_str(anomaly.get("type"), 30)
    layer = _safe_str(anomaly.get("layer"), 20)
    anomaly_events.labels(type=atype, layer=layer).inc()


def handle_drop(evt: dict) -> None:
    drop_packets.inc()


def handle_stats(evt: dict) -> None:
    global _last_stats_observed_at

    stats = evt.get("stats", {})
    _last_stats_observed_at = time.time()
    stats_last_event_timestamp.set(_last_stats_observed_at)
    sensor_health.set(1)
    uptime = stats.get("uptime")
    if uptime is not None:
        try:
            suricata_uptime.set(float(uptime))
        except (ValueError, TypeError):
            pass

    capture = stats.get("capture", {})
    if isinstance(capture, dict):
        try:
            packets = float(capture.get("kernel_packets", 0) or 0)
            drops = float(capture.get("kernel_drops", 0) or 0)
            capture_packets.set(packets)
            capture_kernel_drops.set(drops)
            capture_kernel_drop_ratio.set((drops / packets * 100.0) if packets > 0 else 0.0)
        except (ValueError, TypeError):
            exporter_errors.labels(stage="stats_capture").inc()


# Dispatch table
_HANDLERS = {
    "alert": handle_alert,
    "flow": handle_flow,
    "dns": handle_dns,
    "http": handle_http,
    "tls": handle_tls,
    "ssh": handle_ssh,
    "anomaly": handle_anomaly,
    "drop": handle_drop,
    "stats": handle_stats,
}


# ─── EVE-JSON Tailer ─────────────────────────────────────────────────────────

def tail_eve_json(path: str) -> None:
    """
    Tail the EVE-JSON file. On rotation or truncation, reopen the file.
    New events are always processed and exposed through /status and /metrics.
    """
    global _events_processed, _last_event_observed_at
    p = Path(path)
    log.info("Waiting for EVE-JSON file: %s", path)

    # Wait for the file to exist
    while not p.exists():
        log.info("EVE file not found yet, retrying in 5s…")
        time.sleep(5)

    log.info("EVE file found. Starting tail…")
    fh = None
    last_inode: Optional[int] = None

    while True:
        try:
            current_inode = p.stat().st_ino if p.exists() else None

            # Open or reopen on rotation
            if fh is None or current_inode != last_inode:
                if fh:
                    fh.close()
                    log.info("EVE file rotated — reopening")
                fh = open(path, "r", encoding="utf-8", errors="replace")
                # New events are consumed from this point. Current sensor stats
                # arrive every eight seconds, so health becomes deterministic.
                fh.seek(0, 2)
                last_inode = current_inode

            # Docker log volume files may be truncated without an inode change.
            if p.exists() and p.stat().st_size < fh.tell():
                fh.close()
                fh = open(path, "r", encoding="utf-8", errors="replace")
                last_inode = current_inode

            line = fh.readline()
            if not line:
                time.sleep(TAIL_POLL_INTERVAL)
                continue

            line = line.strip()
            if not line:
                continue

            try:
                evt = json.loads(line)
            except json.JSONDecodeError as exc:
                exporter_errors.labels(stage="json_parse").inc()
                log.debug("JSON parse error: %s — line: %r", exc, line[:120])
                continue

            event_type = evt.get("event_type", "unknown")
            _last_event_observed_at = time.time()
            _events_processed += 1
            eve_last_event_timestamp.set(_last_event_observed_at)
            eve_events_total.labels(event_type=event_type).inc()

            handler = _HANDLERS.get(event_type)
            if handler:
                try:
                    handler(evt)
                except Exception as exc:
                    exporter_errors.labels(stage=f"handler_{event_type}").inc()
                    log.debug("Handler error [%s]: %s", event_type, exc)

        except Exception as exc:
            exporter_errors.labels(stage="tail_loop").inc()
            log.warning("Tail loop error: %s — retrying in 2s", exc)
            if fh:
                try:
                    fh.close()
                except Exception:
                    pass
                fh = None
            time.sleep(2)


# ─── HTTP Server ─────────────────────────────────────────────────────────────

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/metrics", "/metrics/"):
            data = generate_latest(registry)
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path in ("/health", "/healthz"):
            healthy = _sensor_is_healthy()
            body = b"ok" if healthy else b"suricata sensor stale or unavailable"
            self.send_response(200 if healthy else 503)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/status":
            body = json.dumps(_status_payload(), sort_keys=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/-/healthy":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        # Suppress noisy request logs unless debug
        if log.isEnabledFor(logging.DEBUG):
            log.debug(fmt, *args)


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("Suricata EVE-JSON Prometheus Exporter starting")
    log.info("EVE_JSON_PATH        = %s", EVE_JSON_PATH)
    log.info("EXPORTER_PORT        = %d", EXPORTER_PORT)
    log.info("ROLLING_WINDOW_SECS  = %d", ROLLING_WINDOW_SECONDS)
    log.info("SENSOR_STALE_AFTER   = %d", SENSOR_STALE_AFTER_SECONDS)

    # Background: rolling alert window gauge updater
    threading.Thread(target=_update_alert_window_gauge, daemon=True, name="alert-window").start()
    threading.Thread(target=_update_sensor_health_gauges, daemon=True, name="sensor-health").start()

    # Background: EVE-JSON tailer
    threading.Thread(target=tail_eve_json, args=(EVE_JSON_PATH,), daemon=True, name="eve-tailer").start()

    # Foreground: metrics HTTP server
    server = HTTPServer(("0.0.0.0", EXPORTER_PORT), MetricsHandler)
    log.info("Serving metrics on http://0.0.0.0:%d/metrics", EXPORTER_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
