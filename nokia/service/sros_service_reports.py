#!/usr/bin/python
###########################################################################
# Description: MultiCLI Nokia SR OS Service Reports
# Commands: show service service-using, show service fdb mac,
#           show service id <id> fdb mac
# Copyright (c) 2026 Nokia
###########################################################################

import datetime
from srlinux.location import build_path
from srlinux.schema.data_store import DataStore

def format_sros_age(dt_or_str):
    if not dt_or_str:
        return "00d00h00m"
    try:
        s = str(dt_or_str).strip()
        if '(' in s:
            return s.split('(')[-1].rstrip(')').replace(' ago', '')
        if 'Z' in s:
            s = s.replace('Z', '+00:00')
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        delta = datetime.datetime.now(datetime.timezone.utc) - dt
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        return f"{days:02d}d{hours:02d}h{minutes:02d}m"
    except Exception:
        return "00d00h00m"

class SrosServiceReports:
    """Handles classic Nokia SR OS service and FDB show reports."""

    def show_service_using(self, state, output):
        """Display Nokia SR OS formatted 'show service service-using'."""
        output.print_line("=" * 79)
        output.print_line("Services [Customer: All]")
        output.print_line("=" * 79)
        output.print_line(f"{'ServiceId':<13}{'Type':<10}{'Adm':<5}{'Opr':<5}{'CustomerID':<12}{'Service Name'}")
        output.print_line("-" * 79)

        path = build_path('/network-instance[name=*]')
        services = []
        try:
            data = state.server.get_data_store(DataStore.State).get_data(path, recursive=False)
            svc_id = 1
            for ni in sorted(data.network_instance.items(), key=lambda x: str(x.name)):
                name = str(ni.name)
                ntype = getattr(ni, 'type', 'default')
                if ntype == 'default':
                    continue

                sros_type = "VPLS" if ntype == 'mac-vrf' else "VPRN"
                adm = "Up" if getattr(ni, 'admin_state', 'enable') == 'enable' else "Down"
                opr = "Up" if getattr(ni, 'oper_state', 'up') == 'up' else "Down"
                services.append((str(svc_id), sros_type, adm, opr, "1", name))
                svc_id += 1
        except Exception:
            pass

        for sid, stype, adm, opr, cid, sname in services:
            output.print_line(f"{sid:<13}{stype:<10}{adm:<5}{opr:<5}{cid:<12}{sname}")

        output.print_line("-" * 79)
        output.print_line(f"Matching Services : {len(services)}")
        output.print_line("=" * 79)
        output.print_line("\nTry SR Linux command: show network-instance summary")

    def show_service_fdb_mac(self, state, output, service_name=None):
        """Display Nokia SR OS formatted 'show service fdb mac' or for specific service."""
        header_name = f"Service {service_name}" if service_name else "All Services"
        output.print_line("=" * 79)
        output.print_line(f"Forwarding Database, {header_name}")
        output.print_line("=" * 79)
        output.print_line(f"{'ServId':<10}{'MAC':<20}{'Source-Identifier':<25}{'Type':<9}{'Last Change'}")
        output.print_line(f"{'':<64}{'Age'}")
        output.print_line("-" * 79)

        # Map mac-vrf names to service IDs
        ni_map = {}
        try:
            ni_data = state.server.get_data_store(DataStore.State).get_data(build_path('/network-instance[name=*]'), recursive=False)
            idx = 1
            for ni in sorted(ni_data.network_instance.items(), key=lambda x: str(x.name)):
                if getattr(ni, 'type', '') == 'mac-vrf':
                    ni_map[str(ni.name)] = str(idx)
                    idx += 1
        except Exception:
            pass

        target_ni = '*' if not service_name or service_name == '*' else service_name
        path = build_path(f'/network-instance[name={target_ni}]/bridge-table/mac-table/mac[address=*]')
        entries = []
        try:
            data = state.server.get_data_store(DataStore.State).get_data(path, recursive=True)
            for ni in data.network_instance.items():
                cur_name = str(ni.name)
                sid = ni_map.get(cur_name, "1")
                bt = getattr(ni, 'bridge_table', None)
                if bt and hasattr(bt.get(), 'mac_table'):
                    mt = bt.get().mac_table.get()
                    if hasattr(mt, 'mac'):
                        for m in mt.mac.items():
                            addr = str(getattr(m, 'address', ''))
                            if not addr:
                                continue
                            dest = str(getattr(m, 'dest', '') or getattr(m, 'subinterface', '') or '--')
                            mtype = "Learned" if getattr(m, 'type', 'learned') == 'learned' else "Static"
                            lup = getattr(m, 'last_update', None)
                            age = format_sros_age(lup)
                            entries.append((sid, addr, dest, mtype, age))
        except Exception:
            pass

        for sid, addr, dest, mtype, age in entries:
            output.print_line(f"{sid:<10}{addr:<20}{dest:<25}{mtype:<9}{age}")

        output.print_line("-" * 79)
        output.print_line(f"No. of Entries in FDB: {len(entries)}")
        output.print_line("=" * 79)
        output.print_line("\nTry SR Linux command: show network-instance bridge-table mac-table all")
