#!/usr/bin/env python3
"""
zabbix_api_manager.py — Zabbix 7.0 JSON-RPC API Automation & Management Tool
Provides automated host registration, health checking, and problem inspection for NHMF.
"""

import os
import sys
import json
import argparse
import time
import urllib.request
import urllib.error


DEFAULT_ZABBIX_URL = os.getenv("ZABBIX_URL", "http://localhost:8080/api_jsonrpc.php")
DEFAULT_USER = os.getenv("ZABBIX_ADMIN_USER", "Admin")
DEFAULT_PASSWORD = os.getenv("ZABBIX_ADMIN_PASSWORD", "zabbix")

DEMO_HOSTS = (
    {"hostname": "Zabbix server", "dns": "zabbix-agent", "role": "Core monitoring server"},
    {"hostname": "NHMF Application Server", "dns": "zabbix-agent-application", "role": "Application tier"},
    {"hostname": "NHMF Database Server", "dns": "zabbix-agent-database", "role": "Database tier"},
    {"hostname": "NHMF Security Server", "dns": "zabbix-agent-security", "role": "Suricata/security tier"},
)


class ZabbixAPI:
    def __init__(self, url=DEFAULT_ZABBIX_URL, user=DEFAULT_USER, password=DEFAULT_PASSWORD):
        self.url = url
        self.user = user
        self.password = password
        self.auth_token = None
        self.request_id = 1

    def call(self, method: str, params: dict = None) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self.request_id,
        }
        if self.auth_token:
            payload["auth"] = self.auth_token

        self.request_id += 1
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=data,
            headers={"Content-Type": "application/json-rpc"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res = json.loads(response.read().decode("utf-8"))
                if "error" in res:
                    raise RuntimeError(f"Zabbix API Error: {res['error']}")
                return res.get("result", {})
        except urllib.error.URLError as e:
            raise ConnectionError(f"Cannot connect to Zabbix API at {self.url}: {e}")

    def get_version(self) -> str:
        return self.call("apiinfo.version")

    def login(self) -> str:
        res = self.call("user.login", {"username": self.user, "password": self.password})
        self.auth_token = res
        return self.auth_token

    def get_hosts(self) -> list:
        return self.call(
            "host.get",
            {
                "output": ["hostid", "host", "name", "status"],
                "selectInterfaces": ["interfaceid", "ip", "dns", "useip", "port", "type", "main"],
            },
        )

    def get_templates(self, pattern: str = "Linux") -> list:
        return self.call(
            "template.get",
            {
                "output": ["templateid", "name", "host"],
                "search": {"name": pattern},
            },
        )

    def get_host_groups(self) -> list:
        return self.call("hostgroup.get", {"output": ["groupid", "name"]})

    def get_linux_group_id(self) -> str:
        groups = self.call(
            "hostgroup.get",
            {"output": ["groupid", "name"], "filter": {"name": ["Linux servers"]}},
        )
        if groups:
            return groups[0]["groupid"]
        all_groups = self.get_host_groups()
        return all_groups[0]["groupid"] if all_groups else "2"

    def get_linux_template_ids(self) -> list:
        templates = self.get_templates("Linux")
        preferred_names = ("Linux by Zabbix agent", "Linux by Zabbix agent active")
        for preferred_name in preferred_names:
            match = next((item for item in templates if item.get("name") == preferred_name), None)
            if match:
                return [{"templateid": match["templateid"]}]
        return [{"templateid": templates[0]["templateid"]}] if templates else []

    def get_problems(self) -> list:
        return self.call(
            "problem.get",
            {
                "output": ["eventid", "name", "severity", "clock", "r_clock"],
                "recent": True,
                "sortfield": ["eventid"],
                "sortorder": "DESC",
                "limit": 25,
            },
        )

    def fix_agent_interface(self, target_dns: str = "zabbix-agent", hostname: str = "Zabbix server") -> dict:
        """Fixes the default Zabbix server host interface so it connects to the zabbix-agent container via Docker DNS."""
        hosts = self.call(
            "host.get",
            {
                "filter": {"host": [hostname]},
                "selectInterfaces": ["interfaceid", "ip", "dns", "useip", "port"],
            },
        )
        if not hosts:
            return {"status": "error", "message": f"Host '{hostname}' was not found in Zabbix"}

        host = hosts[0]
        interfaces = host.get("interfaces", [])
        if not interfaces:
            return {"status": "error", "message": "No interfaces found on host"}

        iface_id = interfaces[0]["interfaceid"]
        res = self.call(
            "hostinterface.update",
            {
                "interfaceid": iface_id,
                "dns": target_dns,
                "useip": 0,
                "port": "10050",
            },
        )
        return {
            "status": "ok",
            "host": host.get("name", "Zabbix server"),
            "interfaceid": iface_id,
            "dns": target_dns,
            "useip": 0,
        }

    def create_host(self, hostname: str, dns: str = "zabbix-agent", port: str = "10050") -> dict:
        return self.call(
            "host.create",
            {
                "host": hostname,
                "interfaces": [
                    {
                        "type": 1,
                        "main": 1,
                        "useip": 0,
                        "ip": "127.0.0.1",
                        "dns": dns,
                        "port": port,
                    }
                ],
                "groups": [{"groupid": self.get_linux_group_id()}],
                "templates": self.get_linux_template_ids(),
            },
        )

    def ensure_host(self, hostname: str, dns: str, port: str = "10050") -> dict:
        existing = self.call(
            "host.get",
            {
                "output": ["hostid", "host", "name"],
                "filter": {"host": [hostname]},
                "selectInterfaces": ["interfaceid", "ip", "dns", "useip", "port"],
            },
        )
        if existing:
            host = existing[0]
            interfaces = host.get("interfaces", [])
            if interfaces:
                self.call(
                    "hostinterface.update",
                    {
                        "interfaceid": interfaces[0]["interfaceid"],
                        "dns": dns,
                        "useip": 0,
                        "port": port,
                    },
                )
            template_ids = self.get_linux_template_ids()
            if template_ids:
                self.call(
                    "host.massadd",
                    {"hosts": [{"hostid": host["hostid"]}], "templates": template_ids},
                )
            return {"status": "updated", "hostid": host["hostid"], "hostname": hostname, "dns": dns}

        result = self.create_host(hostname, dns, port)
        host_ids = result.get("hostids", [])
        return {
            "status": "created",
            "hostid": host_ids[0] if host_ids else None,
            "hostname": hostname,
            "dns": dns,
        }

    def setup_demo_hosts(self) -> list:
        results = []
        for host in DEMO_HOSTS:
            if host["hostname"] == "Zabbix server":
                result = self.fix_agent_interface(host["dns"], host["hostname"])
                result.update({"hostname": host["hostname"], "role": host["role"]})
            else:
                result = self.ensure_host(host["hostname"], host["dns"])
                result["role"] = host["role"]
            results.append(result)
        return results


def wait_for_api(api: ZabbixAPI, wait_seconds: int) -> str:
    deadline = time.monotonic() + max(wait_seconds, 0)
    last_error = None
    while True:
        try:
            return api.get_version()
        except Exception as exc:
            last_error = exc
            if time.monotonic() >= deadline:
                raise ConnectionError(f"Zabbix API was not ready within {wait_seconds}s: {last_error}")
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="Zabbix 7.0 API Manager for NHMF")
    parser.add_argument("--url", default=DEFAULT_ZABBIX_URL, help="Zabbix JSON-RPC API endpoint")
    parser.add_argument("--user", default=DEFAULT_USER, help="Zabbix username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Zabbix password")
    parser.add_argument(
        "action",
        choices=["status", "hosts", "problems", "templates", "setup-host", "setup-demo-hosts", "fix-agent"],
        help="Action to execute",
    )
    parser.add_argument("--host-name", default="NHMF-Docker-Host", help="Host name for setup-host action")
    parser.add_argument("--dns", default="zabbix-agent", help="DNS name for host interface")
    parser.add_argument("--wait-seconds", type=int, default=0, help="Wait for the Zabbix API before running the action")

    args = parser.parse_args()
    api = ZabbixAPI(args.url, args.user, args.password)

    try:
        version = wait_for_api(api, args.wait_seconds)
        print(f"[OK] Connected to Zabbix API v{version} at {args.url}")

        api.login()
        print(f"[OK] Authenticated successfully as '{args.user}'")

        if args.action == "status":
            hosts = api.get_hosts()
            problems = api.get_problems()
            print(f"\n--- Zabbix System Overview ---")
            print(f"  Zabbix Version:      {version}")
            print(f"  Monitored Hosts:     {len(hosts)}")
            print(f"  Active Problems:     {len(problems)}")
            for h in hosts:
                status_str = "ENABLED" if h.get("status") == "0" else "DISABLED"
                ifaces = h.get("interfaces", [])
                iface_info = f"DNS={ifaces[0].get('dns')} IP={ifaces[0].get('ip')} Port={ifaces[0].get('port')}" if ifaces else "No iface"
                print(f"    - Host: {h.get('name')} [{status_str}] ({iface_info})")

        elif args.action == "fix-agent":
            result = api.fix_agent_interface(args.dns)
            if result.get("status") == "ok":
                print(f"[OK] Successfully updated host interface for '{result.get('host')}' to connect via DNS '{result.get('dns')}:10050'.")
            else:
                print(f"[ERROR] {result.get('message')}")

        elif args.action == "hosts":
            hosts = api.get_hosts()
            print(json.dumps(hosts, indent=2))

        elif args.action == "problems":
            problems = api.get_problems()
            print(f"\n--- Active Problems ({len(problems)}) ---")
            for p in problems:
                sev_map = {"0": "NOT_CLASSIFIED", "1": "INFO", "2": "WARNING", "3": "AVERAGE", "4": "HIGH", "5": "DISASTER"}
                sev = sev_map.get(str(p.get("severity")), "UNKNOWN")
                print(f"  [{sev}] {p.get('name')} (Event ID: {p.get('eventid')})")

        elif args.action == "templates":
            templates = api.get_templates()
            print(json.dumps(templates, indent=2))

        elif args.action == "setup-host":
            result = api.ensure_host(args.host_name, args.dns)
            print(f"[OK] {result['status'].title()} host '{args.host_name}' (ID: {result.get('hostid')}, DNS: {args.dns}:10050).")

        elif args.action == "setup-demo-hosts":
            results = api.setup_demo_hosts()
            print(f"\n--- Demo Host Provisioning ({len(results)} hosts) ---")
            for result in results:
                state = result.get("status", "unknown").upper()
                print(
                    f"  [{state}] {result.get('hostname')} — {result.get('role')} "
                    f"(DNS: {result.get('dns')}:10050)"
                )

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
