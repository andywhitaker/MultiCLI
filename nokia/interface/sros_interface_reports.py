#!/usr/bin/python
###########################################################################
# Description: MultiCLI Nokia SR OS Interface and Port Reports
# Commands: show port, show port description, show lag, show system lldp neighbor
# Copyright (c) 2026 Nokia
###########################################################################

import re
from srlinux.location import build_path
from srlinux.schema.data_store import DataStore

def format_sros_port(name):
    if not name:
        return ""
    name_str = str(name)
    m = re.match(r'ethernet-(\d+)/(\d+)', name_str)
    if m:
        return f"1/{m.group(1)}/{m.group(2)}"
    m = re.match(r'mgmt(\d*)', name_str)
    if m:
        return "A/1"
    m = re.match(r'system(\d*)', name_str)
    if m:
        return "system"
    return name_str

class SrosInterfaceReports:
    """Handles classic Nokia SR OS port, lag, and lldp show reports."""

    def show_port(self, state, output, port_id=None):
        """Display Nokia SR OS formatted 'show port'."""
        path = build_path('/interface[name=*]')
        try:
            intf_data = state.server.get_data_store(DataStore.State).get_data(path, recursive=True)
            interfaces = list(intf_data.interface.items())
        except Exception:
            interfaces = []

        output.print_line("=" * 79)
        output.print_line("Ports on Slot 1")
        output.print_line("=" * 79)
        output.print_line(f"{'Port':<12}{'Admin':<7}{'Link':<6}{'Port':<8}{'Cfg':<7}{'Oper':<7}{'LAG/':<7}{'Port':<6}{'Port':<6}{'Port':<6}{'C/QS/S/XFP/'}")
        output.print_line(f"{'Id':<12}{'State':<7}{'':<6}{'State':<8}{'MTU':<7}{'MTU':<7}{'Bndl':<7}{'Mode':<6}{'Encp':<6}{'Type':<6}{'MDIMDX'}")
        output.print_line("-" * 79)

        count = 0
        for intf in interfaces:
            raw_name = str(intf.name)
            if not raw_name.startswith('ethernet-'):
                continue
            sros_name = format_sros_port(raw_name)
            if port_id and port_id != '*' and port_id not in (raw_name, sros_name):
                continue

            admin_state = "Up" if getattr(intf, 'admin_state', '') == 'enable' else "Down"
            oper_state = "Up" if getattr(intf, 'oper_state', '') == 'up' else "Down"
            link = "Yes" if oper_state == "Up" else "No"
            mtu = str(getattr(intf, 'mtu', 9232) or 9232)

            output.print_line(
                f"{sros_name:<12}{admin_state:<7}{link:<6}{oper_state:<8}{mtu:<7}{mtu:<7}{'-':<7}{'netw':<6}{'null':<6}{'xcvr':<6}{''}"
            )
            count += 1

        output.print_line("=" * 79)
        output.print_line("\nTry SR Linux command: show interface brief")

    def show_port_description(self, state, output):
        """Display Nokia SR OS formatted 'show port description'."""
        path = build_path('/interface[name=*]')
        try:
            intf_data = state.server.get_data_store(DataStore.State).get_data(path, recursive=True)
            interfaces = list(intf_data.interface.items())
        except Exception:
            interfaces = []

        output.print_line("=" * 79)
        output.print_line("Port Descriptions on Slot 1")
        output.print_line("=" * 79)
        output.print_line(f"{'Port Id':<20}{'Description'}")
        output.print_line("-" * 79)

        for intf in interfaces:
            raw_name = str(intf.name)
            if not raw_name.startswith('ethernet-'):
                continue
            sros_name = format_sros_port(raw_name)
            desc = getattr(intf, 'description', '') or ''
            output.print_line(f"{sros_name:<20}{desc}")

        output.print_line("=" * 79)
        output.print_line("\nTry SR Linux command: show interface")

    def show_lag(self, state, output, lag_id=None):
        """Display Nokia SR OS formatted 'show lag'."""
        path = build_path('/interface[name=*]')
        lags = []
        try:
            intf_data = state.server.get_data_store(DataStore.State).get_data(path, recursive=True)
            for intf in intf_data.interface.items():
                if str(intf.name).startswith('lag'):
                    lags.append(intf)
        except Exception:
            pass

        output.print_line("=" * 79)
        output.print_line("Lag Data")
        output.print_line("=" * 79)
        output.print_line(f"{'Lag-id':<10}{'Adm':<8}{'Opr':<8}{'Weighted':<10}{'Threshold':<11}{'Up-Count':<9}{'MC Act/Stdby'}")
        output.print_line("-" * 79)

        if not lags:
            output.print_line("No Matching Entries")
        else:
            for l in lags:
                lid = str(l.name).replace('lag', '') or '1'
                adm = "up" if getattr(l, 'admin_state', '') == 'enable' else "down"
                opr = "up" if getattr(l, 'oper_state', '') == 'up' else "down"
                output.print_line(f"{lid:<10}{adm:<8}{opr:<8}{'No':<10}{'0':<11}{'0':<9}{'N/A'}")

        output.print_line("=" * 79)
        output.print_line("\nTry SR Linux command: show lag")

    def show_lldp_neighbor(self, state, output):
        """Display Nokia SR OS formatted 'show system lldp neighbor'."""
        output.print_line("=" * 79)
        output.print_line("LLDP Remote System Information")
        output.print_line("=" * 79)

        path = build_path('/system/lldp')
        neighbors = []
        try:
            lldp_data = state.server.get_data_store(DataStore.State).get_data(path, recursive=True)
            lldp = lldp_data.system.get().lldp.get()
            if hasattr(lldp, 'interface'):
                for intf in lldp.interface.items():
                    local_intf = str(intf.name)
                    if hasattr(intf, 'neighbor'):
                        for n in intf.neighbor.items():
                            neighbors.append((local_intf, n))
        except Exception:
            pass

        if not neighbors:
            output.print_line("No Matching Entries Found.")
        else:
            for local_intf, n in neighbors:
                sros_port = format_sros_port(local_intf)
                chassis_id = getattr(n, 'chassis_id', 'N/A')
                port_id = getattr(n, 'port_id', 'N/A')
                sys_name = getattr(n, 'system_name', 'N/A')
                sys_desc = getattr(n, 'system_description', 'N/A')
                output.print_line(f"Port Id         : {sros_port} ({local_intf})")
                output.print_line(f"Chassis Id      : {chassis_id}")
                output.print_line(f"Port Id         : {port_id}")
                output.print_line(f"System Name     : {sys_name}")
                output.print_line(f"System Descr    : {sys_desc}")
                output.print_line("-" * 79)

        output.print_line("=" * 79)
        output.print_line("\nTry SR Linux command: show system lldp neighbor")
