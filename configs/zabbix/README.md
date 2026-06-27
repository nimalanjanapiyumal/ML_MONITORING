# Zabbix Configuration Notes

Zabbix is included as an optional infrastructure monitoring layer.

Default web URL:

```text
http://localhost:8080
```

Default login:

```text
Admin / zabbix
```

Recommended initial actions:

1. Add host `docker-monitoring-host`.
2. Link Linux by Zabbix agent template.
3. Add monitored network devices using SNMP templates if available.
4. Use Zabbix proxy for distributed site simulation if extra VMs are available.
