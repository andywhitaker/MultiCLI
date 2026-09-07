#!/usr/bin/python
###########################################################################
# Description: MultiCLI System Reports for Juniper JUNOS
# Copyright (c) 2025-2026 Nokia
###########################################################################

import datetime
from srlinux.location import build_path

class JunosSystemReports:
    """Handles Juniper JUNOS system show commands."""

    def show_version(self, state, output):
        """Display Juniper JUNOS style 'show version'."""
        hostname = "-"
        model = "-"
        sw_version = "-"

        # Query system hostname
        path_system = build_path('/system/name/host-name')
        try:
            data = state.server_data_store.get_data(path_system, recursive=False)
            sys_node = data.system.get()
            if hasattr(sys_node, 'name') and sys_node.name.exists():
                name_node = sys_node.name.get()
                if hasattr(name_node, 'host_name') and name_node.host_name:
                    hostname = str(name_node.host_name)
        except Exception:
            pass

        # Query chassis model
        path_chassis = build_path('/platform/chassis')
        try:
            data = state.server_data_store.get_data(path_chassis, recursive=True)
            ch = data.platform.get().chassis.get()
            if hasattr(ch, 'type') and ch.type:
                model = str(ch.type)
        except Exception:
            pass

        # Query system version
        sys_info_path = build_path('/system/information')
        try:
            sys_data = state.server_data_store.get_data(sys_info_path, recursive=True)
            info = sys_data.system.get().information.get()
            if hasattr(info, 'version') and info.version:
                sw_version = str(info.version).lstrip('v').split('-')[0]
        except Exception:
            pass

        lines = [
            f"Hostname: {hostname}",
            f"Model: {model}",
            f"SRLinux: {sw_version}",
            f"Nokia SR Linux Base OS Software Suite [{sw_version}]",
            f"Nokia SR Linux Kernel Software Suite [{sw_version}]",
            f"Nokia SR Linux Routing Software Suite [{sw_version}]"
        ]

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show version")

    def show_system_uptime(self, state, output):
        """Display Juniper JUNOS style 'show system uptime'."""
        now = datetime.datetime.now(datetime.timezone.utc)
        curr_time_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")

        last_booted = ""
        uptime_seconds = 0
        sys_info_path = build_path('/system/information')
        try:
            sys_data = state.server_data_store.get_data(sys_info_path, recursive=True)
            info = sys_data.system.get().information.get()
            if hasattr(info, 'last_booted') and info.last_booted:
                last_booted = str(info.last_booted)
            if hasattr(info, 'up_time_counter') and info.up_time_counter:
                uptime_seconds = int(info.up_time_counter) // 1_000_000_000
        except Exception:
            pass

        if uptime_seconds == 0 and last_booted:
            try:
                boot_str = last_booted.split('(')[0].strip()
                if 'Z' in boot_str:
                    boot_str = boot_str.replace('Z', '+00:00')
                boot_time = datetime.datetime.fromisoformat(boot_str)
                if boot_time.tzinfo is None:
                    boot_time = boot_time.replace(tzinfo=datetime.timezone.utc)
                uptime_seconds = max(0, int((now - boot_time).total_seconds()))
            except Exception:
                uptime_seconds = 0

        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        ago_str = f"({days}d {hours:02}:{minutes:02} ago)"

        boot_dt = now - datetime.timedelta(seconds=uptime_seconds)
        boot_str = boot_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

        lines = [
            f"Current time: {curr_time_str}",
            "Time Source: NTP CLOCK",
            f"System booted: {boot_str} {ago_str}",
            f"Protocols started: {boot_str} {ago_str}",
            f"Last configured: {boot_str} {ago_str} by admin",
            f" {now.strftime('%I:%M%p')}  up {days} days,  {hours:02}:{minutes:02}"
        ]

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show system information")

    def show_chassis_hardware(self, state, output):
        """Display Juniper JUNOS style 'show chassis hardware'."""
        lines = [
            "Hardware inventory:",
            f"{'Item':<16} {'Version':<8} {'Part number':<12} {'Serial number':<17} {'Description'}"
        ]

        # Chassis
        ch_type = "-"
        serial = "-"
        path_chassis = build_path('/platform/chassis')
        try:
            data = state.server_data_store.get_data(path_chassis, recursive=True)
            ch = data.platform.get().chassis.get()
            ch_type = getattr(ch, 'type', '-') or '-'
            serial = getattr(ch, 'serial_number', '-') or '-'
        except Exception:
            pass

        lines.append(f"{'Chassis':<16} {'':<8} {'':<12} {serial:<17} {ch_type}")

        # Control module
        path_ctrl = build_path('/platform/control[slot=*]')
        try:
            data_ctrl = state.server_data_store.get_data(path_ctrl, recursive=True)
            for c in data_ctrl.platform.get().control.items():
                slot = getattr(c, 'slot', 'A')
                c_type = getattr(c, 'type', 'CPM') or 'CPM'
                c_sn = getattr(c, 'serial_number', '-') or '-'
                c_part = getattr(c, 'part_number', '-') or '-'
                lines.append(f"{f'Control Card {slot}':<16} {'':<8} {c_part:<12} {c_sn:<17} {c_type}")
        except Exception:
            pass

        # Power supplies
        path_psu = build_path('/platform/power-supply[id=*]')
        try:
            data = state.server_data_store.get_data(path_psu, recursive=True)
            for psu in data.platform.get().power_supply.items():
                p_id = psu.id
                oper = getattr(psu, 'oper_state', '-')
                p_sn = getattr(psu, 'serial_number', None)
                if oper != 'empty' and p_sn:
                    lines.append(f"{f'Power Supply {p_id}':<16} {'':<8} {'-':<12} {p_sn:<17} {'Power Supply'}")
        except Exception:
            pass

        # Fan modules
        path_fan = build_path('/platform/fan-tray[id=*]')
        try:
            data = state.server_data_store.get_data(path_fan, recursive=True)
            for fan in data.platform.get().fan_tray.items():
                f_id = fan.id
                oper = getattr(fan, 'oper_state', '-')
                f_sn = getattr(fan, 'serial_number', None)
                if oper != 'empty' and f_sn:
                    lines.append(f"{f'Fan Tray {f_id}':<16} {'':<8} {'-':<12} {f_sn:<17} {'Fan Tray'}")
        except Exception:
            pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show platform chassis")

    def show_system_processes(self, state, output, summary=False):
        """Display Juniper JUNOS style 'show system processes [summary|extensive]'."""
        lines = []
        now_time = datetime.datetime.now().strftime("%H:%M:%S")

        # Last pid
        last_pid = "0"
        try:
            with open('/proc/sys/kernel/ns_last_pid') as f:
                last_pid = f.read().strip()
        except Exception:
            pass

        # Load averages
        load1, load5, load15 = "0.00", "0.00", "0.00"
        try:
            with open('/proc/loadavg') as f:
                parts = f.read().split()
                load1, load5, load15 = parts[0], parts[1], parts[2]
        except Exception:
            pass

        # Uptime
        up_str = "--"
        try:
            with open('/proc/uptime') as f:
                up_secs = float(f.read().split()[0])
                days = int(up_secs // 86400)
                hours = int((up_secs % 86400) // 3600)
                mins = int((up_secs % 3600) // 60)
                secs = int(up_secs % 60)
                up_str = f"{days}+{hours:02d}:{mins:02d}:{secs:02d}"
        except Exception:
            pass

        # Memory
        mem_total, mem_free, mem_avail, buffers, cached = "0", "0", "0", "0", "0"
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        mem_total = line.split()[1]
                    elif line.startswith('MemFree:'):
                        mem_free = line.split()[1]
                    elif line.startswith('MemAvailable:'):
                        mem_avail = line.split()[1]
                    elif line.startswith('Buffers:'):
                        buffers = line.split()[1]
                    elif line.startswith('Cached:'):
                        cached = line.split()[1]
        except Exception:
            pass

        mem_tot_m = int(mem_total) // 1024 if mem_total.isdigit() else 0
        mem_free_m = int(mem_free) // 1024 if mem_free.isdigit() else 0
        active_m = int(mem_total) // 2048 if mem_total.isdigit() else 0
        wired_m = (int(buffers) + int(cached)) // 1024 if buffers.isdigit() and cached.isdigit() else 0

        # Processes
        ps_rows = []
        try:
            import subprocess
            ps_out = subprocess.run(["ps", "-eo", "pid,user,pri,ni,vsz,rss,stat,time,%cpu,comm", "--sort=-%cpu"],
                                    stdout=subprocess.PIPE, text=True).stdout
            for p_line in ps_out.strip().split("\n")[1:]:
                fields = p_line.split(None, 9)
                if len(fields) == 10:
                    ps_rows.append(fields)
        except Exception:
            pass

        if last_pid == "0" and ps_rows:
            try:
                last_pid = str(max(int(p[0]) for p in ps_rows if p[0].isdigit()))
            except Exception:
                pass

        total_procs = len(ps_rows)
        running = sum(1 for p in ps_rows if p[6].startswith('R'))
        sleeping = sum(1 for p in ps_rows if p[6].startswith('S') or p[6].startswith('D'))

        # CPU from /proc/stat
        cpu_line = "CPU:  0.0% user,  0.0% nice,  0.0% system,  0.0% interrupt, 100.0% idle"
        try:
            with open('/proc/stat') as f:
                first = f.readline()
                if first.startswith('cpu '):
                    c_parts = [float(x) for x in first.split()[1:]]
                    tot = sum(c_parts)
                    if tot > 0:
                        us = (c_parts[0] / tot) * 100
                        ni = (c_parts[1] / tot) * 100
                        sy = (c_parts[2] / tot) * 100
                        idl = (c_parts[3] / tot) * 100
                        intr = (c_parts[5] / tot) * 100 if len(c_parts) > 5 else 0.0
                        cpu_line = f"CPU:  {us:4.1f}% user,  {ni:4.1f}% nice,  {sy:4.1f}% system,  {intr:4.1f}% interrupt, {idl:4.1f}% idle"
        except Exception:
            pass

        lines.append(f"last pid: {last_pid:>6};  load averages:  {load1},  {load5},  {load15}  up {up_str}    {now_time}")
        lines.append(f"{total_procs} processes: {running} running, {sleeping} sleeping")
        lines.append(cpu_line)
        lines.append(f"Mem: {active_m}M Active, {mem_free_m}M Inact, {wired_m}M Wired, {mem_free_m}M Free")
        lines.append(f"Swap: 0M Total, 0M Free")

        if not summary:
            lines.append("")
            lines.append(f"{'PID':>6} {'USERNAME':<10} {'THR':<4} {'PRI':<4} {'NICE':<5} {'SIZE':>8} {'RES':>7} {'STATE':<8} {'TIME':>8} {'WCPU':>6} {'COMMAND'}")
            for p in ps_rows[:25]:
                pid, usr, pri, ni, vsz, rss, stat, tm, cpu, comm = p
                size_k = f"{vsz}K"
                res_k = f"{rss}K"
                wcpu = f"{cpu}%"
                s_name = "select" if stat.startswith('S') else ("run" if stat.startswith('R') else "stop")
                lines.append(f"{pid:>6} {usr:<10} {'1':<4} {pri:<4} {ni:<5} {size_k:>8} {res_k:>7} {s_name:<8} {tm:>8} {wcpu:>6} {comm}")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show system information")
