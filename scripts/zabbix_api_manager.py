#!/usr/bin/env python3
"""
zabbix_api_manager.py — Zabbix 7.0 JSON-RPC API Automation & Management Tool
Provides automated host registration, health checking, and problem inspection for NHMF.
"""

import os
import sys
import json
import argparse
import subprocess
import time
import urllib.request
import urllib.error


DEFAULT_ZABBIX_URL = os.getenv("ZABBIX_URL", "http://localhost:8080/api_jsonrpc.php")
DEFAULT_USER = os.getenv("ZABBIX_ADMIN_USER", "Admin")
DEFAULT_PASSWORD = os.getenv("ZABBIX_ADMIN_PASSWORD", "zabbix")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEMO_HOSTS = (
    {"hostname": "Zabbix server", "dns": "zabbix-agent", "role": "Core monitoring server"},
    {"hostname": "NHMF Application Server", "dns": "zabbix-agent-application", "role": "Application tier"},
    {"hostname": "NHMF Database Server", "dns": "zabbix-agent-database", "role": "Database tier"},
    {"hostname": "NHMF Security Server", "dns": "zabbix-agent-security", "role": "Suricata/security tier"},
    {"hostname": "NHMF Web Server", "dns": "zabbix-agent-web", "role": "Web/frontend tier"},
    {"hostname": "NHMF API Server", "dns": "zabbix-agent-api", "role": "API/service tier"},
    {"hostname": "NHMF Backup Server", "dns": "zabbix-agent-backup", "role": "Backup/recovery tier"},
)
DEMO_GROUP_NAME = "NHMF Monitored Servers"


def resolve_compose_service_ip(service_name: str) -> str | None:
    """Resolve a running Compose service IP without depending on Docker's embedded DNS."""
    try:
        compose_result = subprocess.run(
            ["docker", "compose", "ps", "-q", service_name],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        container_ids = compose_result.stdout.strip().splitlines()
        if not container_ids:
            return None
        inspect_result = subprocess.run(
            ["docker", "inspect", container_ids[0]],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=PROJECT_ROOT,
        )
        containers = json.loads(inspect_result.stdout)
        networks = containers[0].get("NetworkSettings", {}).get("Networks", {}) if containers else {}
        for network in networks.values():
            ip_address = network.get("IPAddress", "")
            if ip_address:
                return ip_address
    except (FileNotFoundError, IndexError, KeyError, json.JSONDecodeError, subprocess.SubprocessError):
        return None
    return None


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
                "selectInterfaces": [
                    "interfaceid",
                    "ip",
                    "dns",
                    "useip",
                    "port",
                    "type",
                    "main",
                    "available",
                    "error",
                ],
            },
        )

    def get_demo_host_health(self) -> list:
        """Return native Zabbix agent availability and agent.ping state for the demo fleet."""
        hosts_by_name = {host.get("host"): host for host in self.get_hosts()}
        host_ids = [
            hosts_by_name[demo_host["hostname"]]["hostid"]
            for demo_host in DEMO_HOSTS
            if demo_host["hostname"] in hosts_by_name
        ]
        items = []
        if host_ids:
            items = self.call(
                "item.get",
                {
                    "output": ["itemid", "hostid", "name", "key_", "status", "state", "lastvalue", "lastclock", "error"],
                    "hostids": host_ids,
                    "filter": {"key_": ["agent.ping"]},
                },
            )
        ping_by_host = {item.get("hostid"): item for item in items}
        current_time = int(time.time())
        health_rows = []

        for demo_host in DEMO_HOSTS:
            hostname = demo_host["hostname"]
            host = hosts_by_name.get(hostname)
            if not host:
                health_rows.append(
                    {
                        **demo_host,
                        "health": "NOT REGISTERED",
                        "availability": "UNKNOWN",
                        "agent_ping": "NO DATA",
                        "endpoint": demo_host["dns"],
                        "error": "Host is missing from Zabbix",
                    }
                )
                continue

            interfaces = host.get("interfaces", [])
            agent_interface = next(
                (interface for interface in interfaces if str(interface.get("type")) == "1" and str(interface.get("main")) == "1"),
                next((interface for interface in interfaces if str(interface.get("type")) == "1"), interfaces[0] if interfaces else {}),
            )
            availability_value = str(agent_interface.get("available", "0"))
            use_ip = str(agent_interface.get("useip", "0")) == "1"
            endpoint = agent_interface.get("ip") if use_ip else agent_interface.get("dns")
            availability = {"0": "PENDING", "1": "AVAILABLE", "2": "UNAVAILABLE"}.get(
                availability_value, "UNKNOWN"
            )
            ping_item = ping_by_host.get(host["hostid"], {})
            last_value = str(ping_item.get("lastvalue", ""))
            item_state = str(ping_item.get("state", "0"))
            try:
                last_clock = int(ping_item.get("lastclock", 0) or 0)
            except (TypeError, ValueError):
                last_clock = 0
            ping_fresh = last_clock > 0 and current_time - last_clock <= 300

            if str(host.get("status")) != "0":
                health = "DISABLED"
            elif availability_value == "1" and last_value == "1" and item_state == "0" and ping_fresh:
                health = "HEALTHY"
            elif availability_value == "2" or item_state == "1":
                health = "RISK / DOWN"
            else:
                health = "PENDING"

            health_rows.append(
                {
                    **demo_host,
                    "health": health,
                    "availability": availability,
                    "agent_ping": "1" if last_value == "1" else "NO DATA",
                    "endpoint": endpoint or demo_host["dns"],
                    "lastclock": last_clock,
                    "error": agent_interface.get("error") or ping_item.get("error") or "",
                }
            )
        return health_rows

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

    def get_demo_group_id(self) -> str:
        groups = self.call(
            "hostgroup.get",
            {"output": ["groupid", "name"], "filter": {"name": [DEMO_GROUP_NAME]}},
        )
        if groups:
            return groups[0]["groupid"]
        result = self.call("hostgroup.create", {"name": DEMO_GROUP_NAME})
        group_ids = result.get("groupids", [])
        if not group_ids:
            raise RuntimeError(f"Zabbix did not return an ID for host group '{DEMO_GROUP_NAME}'")
        return group_ids[0]

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
        """Fix the default host interface using a container IP when available."""
        hosts = self.call(
            "host.get",
            {
                "filter": {"host": [hostname]},
                "selectInterfaces": ["interfaceid", "ip", "dns", "useip", "port", "type", "main"],
            },
        )
        if not hosts:
            return {"status": "error", "message": f"Host '{hostname}' was not found in Zabbix"}

        host = hosts[0]
        interfaces = host.get("interfaces", [])
        if not interfaces:
            return {"status": "error", "message": "No interfaces found on host"}

        agent_interface = next(
            (interface for interface in interfaces if str(interface.get("type")) == "1" and str(interface.get("main")) == "1"),
            next((interface for interface in interfaces if str(interface.get("type")) == "1"), interfaces[0]),
        )
        iface_id = agent_interface["interfaceid"]
        target_ip = resolve_compose_service_ip(target_dns)
        self.call(
            "hostinterface.update",
            {
                "interfaceid": iface_id,
                "dns": target_dns,
                "ip": target_ip or agent_interface.get("ip") or "127.0.0.1",
                "useip": 1 if target_ip else 0,
                "port": "10050",
            },
        )
        self.call("host.update", {"hostid": host["hostid"], "status": 0})
        return {
            "status": "ok",
            "host": host.get("name", "Zabbix server"),
            "interfaceid": iface_id,
            "dns": target_dns,
            "ip": target_ip,
            "useip": 1 if target_ip else 0,
        }

    def create_host(
        self,
        hostname: str,
        dns: str = "zabbix-agent",
        port: str = "10050",
        ip_address: str | None = None,
    ) -> dict:
        group_ids = {self.get_linux_group_id(), self.get_demo_group_id()}
        return self.call(
            "host.create",
            {
                "host": hostname,
                "interfaces": [
                    {
                        "type": 1,
                        "main": 1,
                        "useip": 1 if ip_address else 0,
                        "ip": ip_address or "127.0.0.1",
                        "dns": dns,
                        "port": port,
                    }
                ],
                "groups": [{"groupid": group_id} for group_id in sorted(group_ids)],
                "templates": self.get_linux_template_ids(),
            },
        )

    def ensure_host(
        self,
        hostname: str,
        dns: str,
        port: str = "10050",
        ip_address: str | None = None,
    ) -> dict:
        existing = self.call(
            "host.get",
            {
                "output": ["hostid", "host", "name"],
                "filter": {"host": [hostname]},
                "selectInterfaces": ["interfaceid", "ip", "dns", "useip", "port", "type", "main"],
                "selectParentTemplates": ["templateid"],
                "selectHostGroups": ["groupid"],
            },
        )
        if existing:
            host = existing[0]
            interfaces = host.get("interfaces", [])
            agent_interface = next(
                (interface for interface in interfaces if str(interface.get("type")) == "1" and str(interface.get("main")) == "1"),
                next((interface for interface in interfaces if str(interface.get("type")) == "1"), None),
            )
            if agent_interface:
                self.call(
                    "hostinterface.update",
                    {
                        "interfaceid": agent_interface["interfaceid"],
                        "dns": dns,
                        "ip": ip_address or agent_interface.get("ip") or "127.0.0.1",
                        "useip": 1 if ip_address else 0,
                        "port": port,
                    },
                )
            else:
                self.call(
                    "hostinterface.create",
                    {
                        "hostid": host["hostid"],
                        "type": 1,
                        "main": 1,
                        "useip": 1 if ip_address else 0,
                        "ip": ip_address or "127.0.0.1",
                        "dns": dns,
                        "port": port,
                    },
                )
            self.call("host.update", {"hostid": host["hostid"], "status": 0})
            template_ids = self.get_linux_template_ids()
            linked_template_ids = {item.get("templateid") for item in host.get("parentTemplates", [])}
            linked_group_ids = {item.get("groupid") for item in host.get("hostgroups", [])}
            demo_group_id = self.get_demo_group_id()
            missing_templates = [
                template for template in template_ids if template.get("templateid") not in linked_template_ids
            ]
            mass_add = {"hosts": [{"hostid": host["hostid"]}]}
            if demo_group_id not in linked_group_ids:
                mass_add["groups"] = [{"groupid": demo_group_id}]
            if missing_templates:
                mass_add["templates"] = missing_templates
            if len(mass_add) > 1:
                self.call("host.massadd", mass_add)
            return {
                "status": "updated",
                "hostid": host["hostid"],
                "hostname": hostname,
                "dns": dns,
                "ip": ip_address,
                "useip": 1 if ip_address else 0,
            }

        result = self.create_host(hostname, dns, port, ip_address)
        host_ids = result.get("hostids", [])
        return {
            "status": "created",
            "hostid": host_ids[0] if host_ids else None,
            "hostname": hostname,
            "dns": dns,
            "ip": ip_address,
            "useip": 1 if ip_address else 0,
        }

    def setup_demo_hosts(self) -> list:
        results = []
        for host in DEMO_HOSTS:
            ip_address = resolve_compose_service_ip(host["dns"])
            result = None
            last_error = None
            for attempt in range(3):
                try:
                    result = self.ensure_host(host["hostname"], host["dns"], ip_address=ip_address)
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < 2:
                        time.sleep(2)
            if result is None:
                result = {
                    "status": "error",
                    "hostname": host["hostname"],
                    "dns": host["dns"],
                    "ip": ip_address,
                    "message": str(last_error),
                }
            elif not ip_address:
                result["warning"] = (
                    f"Compose service '{host['dns']}' has no running container IP; "
                    "the interface is using Docker DNS fallback"
                )
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

            print("\n--- Native Zabbix Agent Health ---")
            for target in api.get_demo_host_health():
                detail = f"availability={target['availability']} agent.ping={target['agent_ping']}"
                if target.get("error"):
                    detail += f" error={target['error']}"
                print(f"  [{target['health']}] {target['hostname']} ({target['endpoint']}:10050; {detail})")

        elif args.action == "fix-agent":
            result = api.fix_agent_interface(args.dns)
            if result.get("status") == "ok":
                endpoint_label = "IP" if result.get("useip") else "DNS"
                endpoint = result.get("ip") or result.get("dns")
                print(
                    f"[OK] Successfully updated host interface for '{result.get('host')}' "
                    f"to connect via {endpoint_label} '{endpoint}:10050'."
                )
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
                endpoint_label = "IP" if result.get("useip") else "DNS"
                endpoint = result.get("ip") or result.get("dns")
                message = f" error={result.get('message')}" if result.get("message") else ""
                warning = f" warning={result.get('warning')}" if result.get("warning") else ""
                print(
                    f"  [{state}] {result.get('hostname')} — {result.get('role')} "
                    f"({endpoint_label}: {endpoint}:10050){message}{warning}"
                )
            if any(result.get("status") == "error" for result in results):
                sys.exit(1)

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
