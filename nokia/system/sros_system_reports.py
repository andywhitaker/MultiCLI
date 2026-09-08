#!/usr/bin/python
###########################################################################
# Description: MultiCLI Nokia SR OS System Reports
# Commands: show version, show system information, show chassis
# Copyright (c) 2026 Nokia
###########################################################################

import datetime
import platform
from srlinux.location import build_path
from srlinux.schema.data_store import DataStore

class SrosSystemReports:
    """Handles classic Nokia SR OS system show reports."""

    def show_version(self, state, output):
        """Display Nokia SR OS formatted 'show version'."""
        chassis_type = "7220 IXR-D2L"
        chassis_path = build_path('/platform/chassis')
        try:
            ch_data = state.server.get_data_store(DataStore.State).get_data(chassis_path, recursive=True)
            ch = ch_data.platform.get().chassis.get()
            if hasattr(ch, 'type') and ch.type:
                chassis_type = str(ch.type)
        except Exception:
            pass

        sw_version = "26.3.1"
        last_booted = "2026-09-02T20:32:38.586Z"
        sys_info_path = build_path('/system/information')
        try:
            sys_data = state.server.get_data_store(DataStore.State).get_data(sys_info_path, recursive=True)
            info = sys_data.system.get().information.get()
            if hasattr(info, 'version') and info.version:
                sw_version = str(info.version).lstrip('v')
            if hasattr(info, 'last_booted') and info.last_booted:
                last_booted = str(info.last_booted)
        except Exception:
            pass

        arch = platform.machine() or "x86_64"
        output.print_line("=" * 79)
        output.print_line(f"SRLinux-{sw_version} both/{arch} Nokia {chassis_type} Copyright (c) 2000-2026 Nokia.")
        output.print_line("All rights reserved. All use subject to applicable license agreements.")
        output.print_line(f"Built on {last_booted}")
        output.print_line("=" * 79)
        output.print_line("\nTry SR Linux command: show version")

    def show_system_information(self, state, output):
        """Display Nokia SR OS formatted 'show system information'."""
        hostname = "leaf"
        name_path = build_path('/system/name')
        try:
            name_data = state.server.get_data_store(DataStore.State).get_data(name_path, recursive=True)
            n_node = name_data.system.get().name.get()
            if hasattr(n_node, 'host_name') and n_node.host_name:
                hostname = str(n_node.host_name)
        except Exception:
            pass

        uptime_seconds = 0
        contact = ""
        location = ""
        coordinates = ""
        sys_info_path = build_path('/system/information')
        try:
            sys_data = state.server.get_data_store(DataStore.State).get_data(sys_info_path, recursive=True)
            info = sys_data.system.get().information.get()
            if hasattr(info, 'contact') and info.contact:
                contact = str(info.contact)
            if hasattr(info, 'location') and info.location:
                location = str(info.location)
            if hasattr(info, 'coordinates') and info.coordinates:
                coordinates = str(info.coordinates)
            if hasattr(info, 'up_time_counter') and info.up_time_counter:
                uptime_seconds = int(info.up_time_counter) // 1_000_000_000
            elif hasattr(info, 'last_booted') and info.last_booted:
                boot_str = str(info.last_booted).split('(')[0].strip()
                if 'Z' in boot_str:
                    boot_str = boot_str.replace('Z', '+00:00')
                boot_time = datetime.datetime.fromisoformat(boot_str)
                now = datetime.datetime.now(datetime.timezone.utc)
                if boot_time.tzinfo is None:
                    boot_time = boot_time.replace(tzinfo=datetime.timezone.utc)
                uptime_seconds = int((now - boot_time).total_seconds())
        except Exception:
            pass

        active_slot = "A"
        try:
            ctrl_path = build_path('/platform/control[slot=*]')
            ctrl_data = state.server.get_data_store(DataStore.State).get_data(ctrl_path, recursive=True)
            for c in ctrl_data.platform.get().control.items():
                if hasattr(c, 'slot') and c.slot:
                    active_slot = str(c.slot)
                    break
        except Exception:
            pass

        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{days} days, {hours:02d}:{minutes:02d}:{seconds:02d}.00 (hr:min:sec)"

        current_time_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y/%m/%d %H:%M:%S UTC")
        clock_path = build_path('/system/clock')
        try:
            clk_data = state.server.get_data_store(DataStore.State).get_data(clock_path, recursive=True)
            clk = clk_data.system.get().clock.get()
            if hasattr(clk, 'current_time') and clk.current_time:
                current_time_str = str(clk.current_time)
        except Exception:
            pass

        output.print_line("=" * 79)
        output.print_line("System Information")
        output.print_line("=" * 79)
        output.print_line(f"System Name            : {hostname}")
        output.print_line(f"System Contact         : {contact}")
        output.print_line(f"System Location        : {location}")
        output.print_line(f"System Coordinates     : {coordinates}")
        output.print_line(f"System Active Slot     : {active_slot}")
        output.print_line(f"System Up Time         : {uptime_str}")
        output.print_line("SNMP Port              : 161")
        output.print_line("SNMP Engine ID         : ")
        output.print_line("SNMP Max Message Size  : 1500")
        output.print_line("Telnet Server          : Disabled")
        output.print_line("SSH Server             : Enabled")
        output.print_line(f"System Current Time    : {current_time_str}")
        output.print_line("=" * 79)
        output.print_line("\nTry SR Linux command: info from state system information")

    def show_chassis(self, state, output):
        """Display Nokia SR OS formatted 'show chassis'."""
        hostname = "leaf"
        name_path = build_path('/system/name')
        try:
            name_data = state.server.get_data_store(DataStore.State).get_data(name_path, recursive=True)
            n_node = name_data.system.get().name.get()
            if hasattr(n_node, 'host_name') and n_node.host_name:
                hostname = str(n_node.host_name)
        except Exception:
            pass

        chassis_type = "7220 IXR-D2L"
        serial = ""
        clei = ""
        oper_state = "up"
        chassis_path = build_path('/platform/chassis')
        try:
            ch_data = state.server.get_data_store(DataStore.State).get_data(chassis_path, recursive=True)
            ch = ch_data.platform.get().chassis.get()
            if hasattr(ch, 'type') and ch.type:
                chassis_type = str(ch.type)
            if hasattr(ch, 'serial_number') and ch.serial_number:
                serial = str(ch.serial_number)
            if hasattr(ch, 'clei_code') and ch.clei_code:
                clei = str(ch.clei_code)
            if hasattr(ch, 'oper_state') and ch.oper_state:
                oper_state = str(ch.oper_state)
        except Exception:
            pass

        location = ""
        coordinates = ""
        try:
            sys_info_path = build_path('/system/information')
            sys_data = state.server.get_data_store(DataStore.State).get_data(sys_info_path, recursive=True)
            info = sys_data.system.get().information.get()
            if hasattr(info, 'location') and info.location:
                location = str(info.location)
            if hasattr(info, 'coordinates') and info.coordinates:
                coordinates = str(info.coordinates)
        except Exception:
            pass

        fan_count = 1
        fan_path = build_path('/platform/fan-tray[id=*]')
        try:
            f_data = state.server.get_data_store(DataStore.State).get_data(fan_path, recursive=True)
            fan_count = len(list(f_data.platform.get().fan_tray.items())) or 1
        except Exception:
            pass

        psu_count = 2
        psu_path = build_path('/platform/power-supply[id=*]')
        try:
            p_data = state.server.get_data_store(DataStore.State).get_data(psu_path, recursive=True)
            psu_count = len(list(p_data.platform.get().power_supply.items())) or 2
        except Exception:
            pass

        output.print_line("=" * 79)
        output.print_line("Chassis Information")
        output.print_line("=" * 79)
        output.print_line(f"Name                   : {hostname}")
        output.print_line(f"Type                   : {chassis_type}")
        output.print_line(f"Location               : {location}")
        output.print_line(f"Coordinates            : {coordinates}")
        output.print_line(f"CLLI code              : {clei}")
        output.print_line(f"Serial Number          : {serial}")
        output.print_line(f"Number of fan trays    : {fan_count}")
        output.print_line(f"Number of power supplies: {psu_count}")
        output.print_line(f"Operational state      : {oper_state}")
        output.print_line("=" * 79)
        output.print_line("\nTry SR Linux command: show platform chassis")
