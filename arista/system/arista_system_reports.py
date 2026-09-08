#!/usr/bin/python
###########################################################################
# Description: MultiCLI Arista EOS System Reports
# Commands: show version, show hostname, show clock, show inventory, show environment
# Copyright (c) 2026 Nokia
###########################################################################

import datetime
import platform
from srlinux.location import build_path
from srlinux.schema.data_store import DataStore

def format_mac_cisco_arista(mac_str):
    if not mac_str:
        return ""
    clean = str(mac_str).replace(':', '').replace('-', '').replace('.', '').lower()
    if len(clean) == 12:
        return f"{clean[0:4]}.{clean[4:8]}.{clean[8:12]}"
    return mac_str

def format_uptime_words(uptime_seconds):
    try:
        total_seconds = int(uptime_seconds)
    except (ValueError, TypeError):
        return "Unknown"
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0 or days > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return ", ".join(parts)

class AristaSystemReports:
    """Handles Arista EOS system show commands."""

    def show_version(self, state, output):
        """Display Arista EOS style 'show version'."""
        chassis_type = "Chassis"
        hw_mac = ""
        serial_number = ""
        part_number = ""
        chassis_path = build_path('/platform/chassis')
        try:
            chassis_data = state.server.get_data_store(DataStore.State).get_data(chassis_path, recursive=True)
            ch = chassis_data.platform.get().chassis.get()
            if hasattr(ch, 'type') and ch.type:
                chassis_type = f"Nokia {ch.type}"
            if hasattr(ch, 'hw_mac_address') and ch.hw_mac_address:
                hw_mac = format_mac_cisco_arista(ch.hw_mac_address)
            if hasattr(ch, 'serial_number') and ch.serial_number:
                serial_number = str(ch.serial_number)
            if hasattr(ch, 'part_number') and ch.part_number:
                part_number = str(ch.part_number)
        except Exception:
            pass

        sw_version = "N/A"
        last_booted = ""
        uptime_seconds = 0
        sys_info_path = build_path('/system/information')
        try:
            sys_data = state.server.get_data_store(DataStore.State).get_data(sys_info_path, recursive=True)
            info = sys_data.system.get().information.get()
            if hasattr(info, 'version') and info.version:
                sw_version = str(info.version)
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
                now = datetime.datetime.now(datetime.timezone.utc)
                if boot_time.tzinfo is None:
                    boot_time = boot_time.replace(tzinfo=datetime.timezone.utc)
                uptime_seconds = int((now - boot_time).total_seconds())
            except Exception:
                uptime_seconds = 0

        uptime_str = format_uptime_words(uptime_seconds)

        total_mem_kb = 0
        free_mem_kb = 0
        ctrl_path = build_path('/platform/control[slot=*]')
        try:
            ctrl_data = state.server.get_data_store(DataStore.State).get_data(ctrl_path, recursive=True)
            for c in ctrl_data.platform.get().control.items():
                if hasattr(c, 'memory') and c.memory.exists():
                    mem = c.memory.get()
                    if hasattr(mem, 'physical') and mem.physical:
                        total_mem_kb = int(mem.physical) // 1024
                    if hasattr(mem, 'free') and mem.free:
                        free_mem_kb = int(mem.free) // 1024
                break
        except Exception:
            pass

        lines = [
            f"{chassis_type}",
            f"Hardware version:    {part_number or '--'}",
            f"Serial number:       {serial_number}",
            f"System MAC address:  {hw_mac}",
            f"",
            f"Software image version: {sw_version}",
            f"Architecture:           {platform.machine() or 'x86_64'}",
            f"Internal build version: {sw_version}",
            f"Internal build ID:      {sw_version}",
            f"",
            f"Uptime:                 {uptime_str}",
            f"Total memory:           {total_mem_kb} kB",
            f"Free memory:            {free_mem_kb} kB",
        ]
        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show version")

    def show_hostname(self, state, output):
        """Display Arista EOS style 'show hostname'."""
        hostname = "unknown"
        p_host = build_path('/system/name/host-name')
        try:
            d_host = state.server.get_data_store(DataStore.State).get_data(p_host, recursive=True)
            hostname = d_host.system.get().name.get().host_name or "unknown"
        except Exception:
            pass

        output.print_line(f"Hostname: {hostname}")
        output.print_line(f"FQDN:     {hostname}")
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: info from state system name")

    def show_clock(self, state, output):
        """Display Arista EOS style 'show clock'."""
        current_dt = datetime.datetime.now(datetime.timezone.utc)
        timezone = "UTC"
        sys_info_path = build_path('/system/information')
        try:
            sys_data = state.server.get_data_store(DataStore.State).get_data(sys_info_path, recursive=True)
            info = sys_data.system.get().information.get()
            if hasattr(info, 'current_datetime') and info.current_datetime:
                dt_str = str(info.current_datetime).split('(')[0].strip()
                if 'Z' in dt_str:
                    dt_str = dt_str.replace('Z', '+00:00')
                current_dt = datetime.datetime.fromisoformat(dt_str)
        except Exception:
            pass

        try:
            clock_path = build_path('/system/clock')
            clock_data = state.server.get_data_store(DataStore.State).get_data(clock_path, recursive=True)
            clock = clock_data.system.get().clock.get()
            if hasattr(clock, 'timezone') and clock.timezone:
                timezone = str(clock.timezone)
        except Exception:
            pass

        formatted_time = current_dt.strftime("%a %b %d %H:%M:%S %Y")
        output.print_line(f"{formatted_time}")
        output.print_line(f"Timezone: {timezone}")
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: info from state system clock")

    def show_inventory(self, state, output):
        """Display Arista EOS style 'show inventory'."""
        chassis_type = "Nokia Chassis"
        description = "Nokia SR Linux System"
        serial_number = ""
        hw_version = "-"
        try:
            chassis_path = build_path('/platform/chassis')
            chassis_data = state.server.get_data_store(DataStore.State).get_data(chassis_path, recursive=True)
            chassis = chassis_data.platform.get().chassis.get()
            if hasattr(chassis, 'type') and chassis.type:
                chassis_type = str(chassis.type)
                description = f"Nokia {chassis.type} Chassis"
            if hasattr(chassis, 'serial_number') and chassis.serial_number:
                serial_number = str(chassis.serial_number)
            if hasattr(chassis, 'part_number') and chassis.part_number:
                hw_version = str(chassis.part_number)
        except Exception:
            pass

        lines = [
            "System information",
            f" Model                    Description",
            f" ------------------------ ----------------------------------------------------",
            f" {chassis_type:<24} {description}",
            f"",
            f" HW Version  Serial Number  Mfg Date   Epoch",
            f" ----------- -------------- ---------- -----",
            f" {hw_version:<11} {serial_number:<14} -          -    ",
            f""
        ]

        try:
            psu_path = build_path('/platform/power-supply[id=*]')
            psu_data = state.server.get_data_store(DataStore.State).get_data(psu_path, recursive=True)
            psus = [p for p in psu_data.platform.get().power_supply.items() if getattr(p, 'oper_state', '') != 'empty']
            if psus:
                lines.append(f"System has {len(psus)} power supply slot{'s' if len(psus) != 1 else ''}")
                lines.append(f" Slot Model            Serial Number")
                lines.append(f" ---- ---------------- ----------------")
                for psu in psus:
                    slot = getattr(psu, 'id', '-')
                    model = getattr(psu, 'type', 'PWR') or 'PWR'
                    sn = getattr(psu, 'serial_number', '-') or '-'
                    lines.append(f" {str(slot):<4} {str(model):<16} {str(sn):<16}")
                lines.append("")
        except Exception:
            pass

        try:
            fan_path = build_path('/platform/fan-tray[id=*]')
            fan_data = state.server.get_data_store(DataStore.State).get_data(fan_path, recursive=True)
            fans = [f for f in fan_data.platform.get().fan_tray.items() if getattr(f, 'oper_state', '') != 'empty']
            if fans:
                lines.append(f"System has {len(fans)} fan module{'s' if len(fans) != 1 else ''}")
                lines.append(f" Module Number of Fans Model            Serial Number")
                lines.append(f" ------- --------------- ---------------- ----------------")
                for fan in fans:
                    tray_id = getattr(fan, 'id', getattr(fan, 'tray_id', '-'))
                    model = getattr(fan, 'type', 'FAN') or 'FAN'
                    sn = getattr(fan, 'serial_number', '-') or '-'
                    lines.append(f" {str(tray_id):<7} 1               {str(model):<16} {str(sn):<16}")
                lines.append("")
        except Exception:
            pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show platform")

    def show_environment(self, state, output, component='all'):
        """Display Arista EOS style 'show environment [temperature|cooling|power]'."""
        lines = []
        if component in ('all', 'cooling'):
            lines.append("System cooling status:")
            found_fan = False
            try:
                fan_path = build_path('/platform/fan-tray[id=*]')
                fan_data = state.server.get_data_store(DataStore.State).get_data(fan_path, recursive=True)
                lines.append("Slot  Description                       Status         Speed")
                lines.append("----- --------------------------------- -------------- ------")
                for fan in fan_data.platform.get().fan_tray.items():
                    tray_id = getattr(fan, 'id', getattr(fan, 'tray_id', '-'))
                    oper = getattr(fan, 'oper_state', '-')
                    if oper != 'empty':
                        found_fan = True
                        status = "ok" if oper in ("up", "ok") else oper
                        speed = getattr(fan, 'speed', None)
                        speed_str = f"{speed}%" if speed is not None else "--"
                        lines.append(f"{str(tray_id):<5} Fan-Tray {str(tray_id):<22} {status:<14} {speed_str}")
            except Exception:
                pass
            if not found_fan:
                lines.append("No fan tray modules populated.")
            lines.append("")

        if component in ('all', 'power'):
            lines.append("System power status:")
            found_psu = False
            try:
                psu_path = build_path('/platform/power-supply[id=*]')
                psu_data = state.server.get_data_store(DataStore.State).get_data(psu_path, recursive=True)
                lines.append("Slot  Model            Output Power   Status")
                lines.append("----- ---------------- -------------- -----------------")
                for psu in psu_data.platform.get().power_supply.items():
                    psu_id = getattr(psu, 'id', '-')
                    model = getattr(psu, 'type', '-')
                    oper = getattr(psu, 'oper_state', '-')
                    if oper != 'empty' and model != '-':
                        found_psu = True
                        status = "ok" if oper in ("up", "ok") else oper
                        cap = getattr(psu, 'capacity', None)
                        cap_str = f"{cap}W" if cap is not None else "--"
                        lines.append(f"{str(psu_id):<5} {str(model):<16} {cap_str:<14} {status}")
            except Exception:
                pass
            if not found_psu:
                lines.append("No power supply modules populated.")
            lines.append("")

        if component in ('all', 'temperature'):
            lines.append("System temperature status:")
            lines.append("Sensor                Description                       Status    Temp(C)")
            lines.append("--------------------- --------------------------------- --------- -------")
            found_temp = False
            try:
                ctrl_path = build_path('/platform/control[slot=*]')
                ctrl_data = state.server.get_data_store(DataStore.State).get_data(ctrl_path, recursive=True)
                for c in ctrl_data.platform.get().control.items():
                    slot = getattr(c, 'slot', 'A')
                    temp_c = getattr(c, 'temperature', None)
                    if temp_c:
                        t_val = getattr(temp_c, 'instant', None)
                        if t_val is not None:
                            found_temp = True
                            lines.append(f"Slot-{str(slot):<15} Control Processor Sensor            ok        {str(t_val)}")
            except Exception:
                pass
            if not found_temp:
                lines.append("No temperature sensor data available.")
            lines.append("")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show platform environment")

    def show_module(self, state, output):
        """Display Arista EOS style 'show module'."""
        lines = []
        modules = []
        linecard_path = build_path('/platform/linecard[slot=*]')
        ctrl_path = build_path('/platform/control[slot=*]')

        num_ports = 0
        try:
            intf_data = state.server.get_data_store(DataStore.State).get_data(build_path('/interface[name=*]'), recursive=True)
            num_ports = sum(1 for i in intf_data.interface.items() if i.name.startswith('ethernet-'))
        except Exception:
            num_ports = 0
        ports_str = str(num_ports) if num_ports > 0 else "--"

        uptime_str = "--"
        try:
            with open('/proc/uptime') as f:
                up_secs = float(f.read().split()[0])
                days = int(up_secs // 86400)
                hours = int((up_secs % 86400) // 3600)
                uptime_str = f"{days} days, {hours} hours" if days > 0 else f"{hours} hours"
        except Exception:
            pass

        try:
            lc_data = state.server.get_data_store(DataStore.State).get_data(linecard_path, recursive=True)
            for lc in lc_data.platform.get().linecard.items():
                slot = getattr(lc, 'slot', '1')
                model = getattr(lc, 'type', '') or getattr(lc, 'part_number', 'Linecard')
                serial = getattr(lc, 'serial_number', '--') or '--'
                oper = getattr(lc, 'oper_state', 'up')
                status = "Ok" if oper == 'up' else "Disabled"
                modules.append({
                    'mod': str(slot),
                    'ports': ports_str,
                    'card': 'Linecard',
                    'type': 'Linecard',
                    'model': str(model),
                    'serial': str(serial),
                    'status': status,
                    'uptime': uptime_str
                })
        except Exception:
            pass

        if not modules:
            try:
                ctrl_data = state.server.get_data_store(DataStore.State).get_data(ctrl_path, recursive=True)
                for c in ctrl_data.platform.get().control.items():
                    slot = getattr(c, 'slot', '1')
                    model = getattr(c, 'type', '') or getattr(c, 'part_number', 'Control')
                    serial = getattr(c, 'serial_number', '--') or '--'
                    oper = getattr(c, 'oper_state', 'up')
                    status = "Ok" if oper == 'up' else "Disabled"
                    modules.append({
                        'mod': '1',
                        'ports': ports_str,
                        'card': 'Fabric/Control',
                        'type': 'Fabric/Control',
                        'model': str(model),
                        'serial': str(serial),
                        'status': status,
                        'uptime': uptime_str
                    })
            except Exception:
                pass

        lines.append(f"{'Module':<7} {'Ports':<6} {'Card':<22} {'Type':<10} {'Model':<22} {'Serial No.'}")
        lines.append("------ ----- ---------------------- ---------- ---------------------- ----------")
        for m in modules:
            lines.append(f"{m['mod']:<7} {m['ports']:<6} {m['card']:<22} {m['type']:<10} {m['model']:<22} {m['serial']}")

        lines.append("")
        lines.append(f"{'Module':<7} {'Status':<18} {'Uptime'}")
        lines.append("------ ------------------ -------------------------")
        for m in modules:
            lines.append(f"{m['mod']:<7} {m['status']:<18} {m['uptime']}")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show platform")

    def show_processes_top_once(self, state, output):
        """Display Arista EOS style 'show processes top once'."""
        lines = []
        now_time = datetime.datetime.now().strftime("%H:%M:%S")
        load1, load5, load15 = "0.00", "0.00", "0.00"
        try:
            with open('/proc/loadavg') as f:
                parts = f.read().split()
                load1, load5, load15 = parts[0], parts[1], parts[2]
        except Exception:
            pass

        up_str = "--"
        try:
            with open('/proc/uptime') as f:
                up_secs = float(f.read().split()[0])
                days = int(up_secs // 86400)
                hours = int((up_secs % 86400) // 3600)
                mins = int((up_secs % 3600) // 60)
                if days > 0:
                    up_str = f"{days} days, {hours:2d}:{mins:02d}"
                else:
                    up_str = f"{hours:2d}:{mins:02d}"
        except Exception:
            pass

        mem_total, mem_free, mem_avail, buffers, cached = "0", "0", "0", "0", "0"
        swap_total, swap_free = "0", "0"
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
                    elif line.startswith('SwapTotal:'):
                        swap_total = line.split()[1]
                    elif line.startswith('SwapFree:'):
                        swap_free = line.split()[1]
        except Exception:
            pass

        used_kb = int(mem_total) - int(mem_free) if mem_total.isdigit() and mem_free.isdigit() else 0
        buff_cache = int(buffers) + int(cached) if buffers.isdigit() and cached.isdigit() else 0
        swap_tot_kb = int(swap_total) if swap_total.isdigit() else 0
        swap_free_kb = int(swap_free) if swap_free.isdigit() else 0
        swap_used_kb = max(0, swap_tot_kb - swap_free_kb)

        # Read task info and ps
        ps_rows = []
        try:
            import subprocess
            ps_out = subprocess.run(["ps", "-eo", "pid,user,pri,ni,vsz,rss,stat,%cpu,%mem,time,comm", "--sort=-%cpu"],
                                    stdout=subprocess.PIPE, text=True).stdout
            for p_line in ps_out.strip().split("\n")[1:]:
                fields = p_line.split(None, 10)
                if len(fields) == 11:
                    ps_rows.append(fields)
        except Exception:
            pass

        total_tasks = len(ps_rows)
        running = sum(1 for p in ps_rows if p[6].startswith('R'))
        sleeping = sum(1 for p in ps_rows if p[6].startswith('S') or p[6].startswith('D'))
        stopped = sum(1 for p in ps_rows if p[6].startswith('T'))
        zombie = sum(1 for p in ps_rows if p[6].startswith('Z'))

        # CPU from /proc/stat
        cpu_line = "%Cpu(s):  0.0 us,  0.0 sy,  0.0 ni, 100.0 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st"
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
                        wa = (c_parts[4] / tot) * 100
                        hi = (c_parts[5] / tot) * 100
                        si = (c_parts[6] / tot) * 100
                        st = (c_parts[7] / tot) * 100 if len(c_parts) > 7 else 0.0
                        cpu_line = f"%Cpu(s): {us:4.1f} us, {sy:4.1f} sy, {ni:4.1f} ni, {idl:4.1f} id, {wa:4.1f} wa, {hi:4.1f} hi, {si:4.1f} si, {st:4.1f} st"
        except Exception:
            pass

        # Check logged in users count
        num_users = 1
        try:
            who_res = subprocess.run(["who"], stdout=subprocess.PIPE, text=True)
            u_count = len(who_res.stdout.strip().splitlines())
            if u_count > 0:
                num_users = u_count
        except Exception:
            pass

        lines.append(f"top - {now_time} up {up_str},  {num_users} user{'s' if num_users != 1 else ''},  load average: {load1}, {load5}, {load15}")
        lines.append(f"Tasks: {total_tasks} total,   {running} running, {sleeping} sleeping,   {stopped} stopped,   {zombie} zombie")
        lines.append(cpu_line)
        lines.append(f"KiB Mem : {mem_total} total, {mem_free} free, {used_kb} used,  {buff_cache} buff/cache")
        lines.append(f"KiB Swap: {swap_tot_kb:>9} total, {swap_free_kb:>8} free, {swap_used_kb:>8} used. {mem_avail} avail Mem")
        lines.append("")
        lines.append(f"{'PID':>5} {'USER':<9} {'PR':<4} {'NI':<4} {'VIRT':>8} {'RES':>7} {'SHR':>6} {'S':<2} {'%CPU':>5} {'%MEM':>5} {'TIME+':>8} {'COMMAND'}")

        for fields in ps_rows[:25]:
            pid, usr, pri, ni, vsz, rss, stat, cpu, mem, tm, comm = fields
            s_stat = stat[0]
            shr_kb = "0"
            try:
                with open(f"/proc/{pid}/statm") as f_sm:
                    shr_pages = int(f_sm.read().split()[2])
                    shr_kb = str(shr_pages * 4)
            except Exception:
                shr_kb = "0"
            lines.append(f"{pid:>5} {usr:<9} {pri:<4} {ni:<4} {vsz:>8} {rss:>7} {shr_kb:>6} {s_stat:<2} {cpu:>5} {mem:>5} {tm:>8} {comm}")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: info from state system information")

