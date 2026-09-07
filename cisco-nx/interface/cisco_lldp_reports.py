#!/usr/bin/python
###########################################################################
# Description: MultiCLI LLDP Reports for Cisco NX-OS
# Copyright (c) 2025-2026 Nokia
###########################################################################

import re
from srlinux.location import build_path
from cisco_interface_reports import format_cisco_intf

class CiscoLldpReports:
    """Handles Cisco NX-OS LLDP show commands."""

    def _get_capability_code(self, neighbor):
        if not hasattr(neighbor, 'capability') or not neighbor.capability:
            return "--"
        caps = []
        c = neighbor.capability
        if hasattr(c, 'router') and c.router:
            caps.append("R")
        if hasattr(c, 'bridge') and c.bridge:
            caps.append("B")
        if hasattr(c, 'mac_bridge') and c.mac_bridge:
            caps.append("B")
        if hasattr(c, 'wlan_access_point') and c.wlan_access_point:
            caps.append("W")
        if hasattr(c, 'station') and c.station:
            caps.append("S")
        return "".join(caps) if caps else "--"

    def show_lldp_neighbors(self, state, output, detail=False):
        """Display Cisco NX-OS style 'show lldp neighbors' or 'detail'."""
        path = build_path('/system/lldp/interface[name=*]/neighbor[id=*]')
        entries = []
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for intf in data.get_descendants('/system/lldp/interface'):
                local_intf = format_cisco_intf(getattr(intf, 'name', ''), short=True)
                if hasattr(intf, 'neighbor'):
                    for n in intf.neighbor.items():
                        sys_name = getattr(n, 'system_name', '')
                        port_id = format_cisco_intf(getattr(n, 'port_id', ''), short=True)
                        chassis_id = getattr(n, 'chassis_id', '')
                        desc = getattr(n, 'system_description', '')
                        mgmt_ip = ""
                        if hasattr(n, 'management_address'):
                            for m in n.management_address.items():
                                mgmt_ip = getattr(m, 'address', '')
                                break
                        ttl = getattr(n, 'time_to_live', getattr(n, 'ttl', '--'))
                        ttl_str = str(ttl) if ttl is not None else '--'
                        cap = self._get_capability_code(n)
                        entries.append({
                            'local_intf': local_intf,
                            'device_id': sys_name,
                            'port_id': port_id,
                            'chassis_id': chassis_id,
                            'desc': desc,
                            'mgmt_ip': mgmt_ip,
                            'cap': cap,
                            'hold_time': ttl_str
                        })
        except Exception:
            pass

        if not detail:
            lines = [
                "Capability codes:",
                "  (R) Router, (B) Bridge, (T) Telephone, (C) DOCSIS Cable Device",
                "  (W) WLAN Access Point, (P) Repeater, (S) Station, (O) Other",
                "",
                f"{'Device ID':<20} {'Local Intf':<15} {'Hold-time':<10} {'Capability':<11} {'Port ID'}",
                ""
            ]
            for e in entries:
                lines.append(f"{e['device_id']:<20} {e['local_intf']:<15} {e['hold_time']:<10} {e['cap']:<11} {e['port_id']}")

            output.print_line("\n".join(lines))
        else:
            lines = []
            for e in entries:
                lines.append(f"Chassis id: {e['chassis_id']}")
                lines.append(f"Port id: {e['port_id']}")
                lines.append(f"Local Port id: {e['local_intf']}")
                lines.append(f"System Name: {e['device_id']}")
                lines.append(f"System Description: {e['desc']}")
                lines.append(f"Enabled Capabilities: {', '.join(list(e['cap'])) if e['cap'] != '--' else 'none'}")
                lines.append(f"Management Address: {e['mgmt_ip'] if e['mgmt_ip'] else 'not advertised'}")
                lines.append("")
            output.print_line("\n".join(lines).rstrip())

        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show system lldp neighbor")
