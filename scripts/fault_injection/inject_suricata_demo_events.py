#!/usr/bin/env python3
"""Inject deterministic, synthetic EVE records for repeatable dashboard demonstrations."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


EVE_JSON_PATH = Path(os.getenv("EVE_JSON_PATH", "/var/log/suricata/eve.json"))

ALERT_SCENARIOS = {
    "scan": {
        "count": 5,
        "signature_id": 9000001,
        "signature": "NHMF DEMO TCP SYN port scan detected",
        "category": "Attempted Information Leak",
        "severity": 2,
        "proto": "TCP",
        "app_proto": "unknown",
    },
    "icmp": {
        "count": 12,
        "signature_id": 9000003,
        "signature": "NHMF DEMO ICMP flood detected",
        "category": "Potentially Bad Traffic",
        "severity": 2,
        "proto": "ICMP",
        "app_proto": "unknown",
    },
    "http": {
        "count": 3,
        "signature_id": 9000008,
        "signature": "NHMF DEMO HTTP Basic Auth credentials in cleartext",
        "category": "Policy Violation",
        "severity": 3,
        "proto": "TCP",
        "app_proto": "http",
    },
    "c2": {
        "count": 1,
        "signature_id": 9000006,
        "signature": "NHMF DEMO suspicious outbound C2 port 4444",
        "category": "A Network Trojan was detected",
        "severity": 1,
        "proto": "TCP",
        "app_proto": "unknown",
    },
}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def common_event(event_type: str, proto: str = "TCP", app_proto: str = "unknown") -> dict:
    return {
        "timestamp": timestamp(),
        "event_type": event_type,
        "src_ip": "192.0.2.10",
        "src_port": 41000,
        "dest_ip": "192.0.2.20",
        "dest_port": 443,
        "proto": proto,
        "app_proto": app_proto,
    }


def scenario_events(scenario: str) -> list[dict]:
    definition = ALERT_SCENARIOS[scenario]
    events = []
    for _index in range(definition["count"]):
        event = common_event("alert", definition["proto"], definition["app_proto"])
        event["alert"] = {
            "action": "allowed",
            "signature_id": definition["signature_id"],
            "signature": definition["signature"],
            "category": definition["category"],
            "severity": definition["severity"],
        }
        events.append(event)

    flow = common_event("flow", definition["proto"], definition["app_proto"])
    flow["flow"] = {
        "pkts_toserver": 64,
        "pkts_toclient": 48,
        "bytes_toserver": 65536,
        "bytes_toclient": 49152,
    }
    events.append(flow)

    if scenario == "icmp":
        anomaly = common_event("anomaly", "ICMP")
        anomaly["anomaly"] = {"type": "decoder", "layer": "proto_detect"}
        events.append(anomaly)
    elif scenario == "http":
        http = common_event("http", "TCP", "http")
        http["http"] = {"http_method": "GET", "status": 401, "hostname": "nhmf-demo.local"}
        events.append(http)

    return events


def protocol_view_events() -> list[dict]:
    dns_query = common_event("dns", "UDP", "dns")
    dns_query["dns"] = {"type": "query", "rrtype": "TXT", "rrname": "demo.nhmf.test"}
    dns_answer = common_event("dns", "UDP", "dns")
    dns_answer["dns"] = {"type": "answer", "rrtype": "TXT", "rcode": "NOERROR"}

    tls = common_event("tls", "TCP", "tls")
    tls["tls"] = {"version": "TLS 1.3", "ja3": {"hash": "nhmf-demo-ja3"}}

    ssh = common_event("ssh", "TCP", "ssh")
    ssh["ssh"] = {
        "client": {"software_version": "NHMF-Demo-Client"},
        "server": {"software_version": "NHMF-Demo-Server"},
    }
    return [dns_query, dns_answer, tls, ssh]


def build_events(scenario: str) -> list[dict]:
    if scenario == "all":
        events = []
        # Repeat enough known alerts to cross the dashboard's red 50-alert boundary.
        for name in ALERT_SCENARIOS:
            events.extend(scenario_events(name))
        scan_definition = ALERT_SCENARIOS["scan"]
        for _index in range(35):
            event = common_event("alert", scan_definition["proto"], scan_definition["app_proto"])
            event["alert"] = {
                "action": "allowed",
                "signature_id": scan_definition["signature_id"],
                "signature": scan_definition["signature"],
                "category": scan_definition["category"],
                "severity": scan_definition["severity"],
            }
            events.append(event)
        events.extend(protocol_view_events())
        return events
    return scenario_events(scenario)


def inject_events(scenario: str, eve_path: Path = EVE_JSON_PATH) -> int:
    events = build_events(scenario)
    eve_path.parent.mkdir(parents=True, exist_ok=True)
    with eve_path.open("a", encoding="utf-8") as eve_file:
        for event in events:
            eve_file.write(json.dumps(event, separators=(",", ":")) + "\n")
    return len(events)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=[*ALERT_SCENARIOS, "all"])
    args = parser.parse_args()
    count = inject_events(args.scenario)
    print(f"[OK] Injected {count} synthetic Suricata EVE events for scenario '{args.scenario}'.")


if __name__ == "__main__":
    main()
