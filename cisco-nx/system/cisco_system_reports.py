#!/usr/bin/python
###########################################################################
# Description: MultiCLI System Reports for Cisco NX-OS
# Copyright (c) 2025-2026 Nokia
###########################################################################

import datetime
from srlinux.location import build_path

class CiscoSystemReports:
    """Handles Cisco NX-OS system-level show commands."""

    def show_version(self, state, output):
        """Display Cisco NX-OS style 'show version'."""
        hostname = "-"
        chassis_type = "-"
        serial = ""
        sw_version = ""
        last_booted = ""
        uptime_seconds = 0
        total_mem = 0
        free_mem = 0

        # Query platform / chassis info
        path_chassis = build_path('/platform/chassis')
        try:
            data = state.server_data_store.get_data(path_chassis, recursive=True)
            ch = data.platform.get().chassis.get()
            if hasattr(ch, 'serial_number') and ch.serial_number:
                serial = str(ch.serial_number)
            if hasattr(ch, 'type') and ch.type:
                chassis_type = str(ch.type)
            if hasattr(ch, 'last_booted') and ch.last_booted:
                last_booted = str(ch.last_booted)
        except Exception:
            pass

        # Query system information (version, uptime)
        sys_info_path = build_path('/system/information')
        try:
            sys_data = state.server_data_store.get_data(sys_info_path, recursive=True)
            info = sys_data.system.get().information.get()
            if hasattr(info, 'version') and info.version:
                sw_version = str(info.version)
            if hasattr(info, 'last_booted') and info.last_booted:
                last_booted = str(info.last_booted)
            if hasattr(info, 'up_time_counter') and info.up_time_counter:
                uptime_seconds = int(info.up_time_counter) // 1_000_000_000
        except Exception:
            pass

        # Query control / memory info
        path_control = build_path('/platform/control[slot=*]')
        try:
            data = state.server_data_store.get_data(path_control, recursive=True)
            for ctrl in data.platform.get().control.items():
                if hasattr(ctrl, 'memory') and ctrl.memory.exists():
                    mem = ctrl.memory.get()
                    if hasattr(mem, 'physical') and mem.physical:
                        total_mem = mem.physical
                    if hasattr(mem, 'free') and mem.free:
                        free_mem = mem.free
        except Exception:
            pass

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

        # Calculate uptime
        if uptime_seconds == 0 and last_booted:
            try:
                boot_str = last_booted.split('(')[0].strip()
                if 'Z' in boot_str:
                    boot_str = boot_str.replace('Z', '+00:00')
                boot_time = datetime.datetime.fromisoformat(boot_str)
                now = datetime.datetime.now(datetime.timezone.utc)
                if boot_time.tzinfo is None:
                    boot_time = boot_time.replace(tzinfo=datetime.timezone.utc)
                uptime_seconds = max(0, int((now - boot_time).total_seconds()))
            except Exception:
                uptime_seconds = 0

        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{days} day(s), {hours} hour(s), {minutes} minute(s), {seconds} second(s)"

        lines = [
            "Nokia SR Linux Software",
            "",
            "Software",
            f"  SRLinux: version {sw_version if sw_version else 'N/A'}",
            "",
            "Hardware",
            f"  Nokia {chassis_type} Chassis" if chassis_type != "-" else "  Chassis",
            f"  System memory: {total_mem} kB",
            f"  Processor Board ID {serial}" if serial else "  Processor Board ID -",
            f"  Device name: {hostname}",
            "",
            f"Kernel uptime is {uptime_str}",
            "",
            "Last reset at " + (last_booted.replace('T', ' ').replace('Z', '') if last_booted else "Unknown"),
            f"  System version: {sw_version if sw_version else 'N/A'}"
        ]

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show version")

    def show_hostname(self, state, output):
        """Display Cisco NX-OS style 'show hostname'."""
        hostname = "-"
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

        output.print_line(hostname)
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show system name")

    def show_clock(self, state, output):
        """Display Cisco NX-OS style 'show clock': HH:MM:SS.mmm UTC Day Mon DD YYYY."""
        now = datetime.datetime.now(datetime.timezone.utc)
        clock_str = now.strftime("%H:%M:%S.%f")[:-3] + " UTC " + now.strftime("%a %b %d %Y")
        output.print_line(clock_str)
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show system clock")

    def show_inventory(self, state, output):
        """Display Cisco NX-OS style 'show inventory'."""
        lines = []

        # Chassis
        path_chassis = build_path('/platform/chassis')
        try:
            data = state.server_data_store.get_data(path_chassis, recursive=True)
            ch = data.platform.get().chassis.get()
            ch_type = getattr(ch, 'type', None)
            serial = getattr(ch, 'serial_number', None)
            if ch_type:
                lines.append(f'NAME: "Chassis",  DESCR: "Nokia {ch_type} Chassis"')
                lines.append(f'PID: {ch_type:<19},  VID: -   ,  SN: {serial if serial else "-"}\n')
        except Exception:
            pass

        # Power supplies
        path_psu = build_path('/platform/power-supply[id=*]')
        try:
            data = state.server_data_store.get_data(path_psu, recursive=True)
            for psu in data.platform.get().power_supply.items():
                p_id = psu.id
                p_type = getattr(psu, 'type', None)
                p_sn = getattr(psu, 'serial_number', None)
                if p_type:
                    lines.append(f'NAME: "Power Supply {p_id}",  DESCR: "Nokia Power Supply"')
                    lines.append(f'PID: {p_type:<19},  VID: -   ,  SN: {p_sn if p_sn else "-"}\n')
        except Exception:
            pass

        # Fan modules
        path_fan = build_path('/platform/fan-tray[id=*]')
        try:
            data = state.server_data_store.get_data(path_fan, recursive=True)
            for fan in data.platform.get().fan_tray.items():
                f_id = fan.id
                f_sn = getattr(fan, 'serial_number', None)
                f_type = getattr(fan, 'type', 'FAN-MODULE')
                if f_sn:
                    lines.append(f'NAME: "Fan {f_id}",  DESCR: "Chassis Fan Module"')
                    lines.append(f'PID: {f_type:<19},  VID: -   ,  SN: {f_sn}\n')
        except Exception:
            pass

        if not lines:
            lines.append("No inventory components detected.")

        output.print_line("\n".join(lines).rstrip())
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show platform chassis")

    def show_environment(self, state, output, sub_type='all'):
        """Display Cisco NX-OS style 'show environment'."""
        lines = []

        if sub_type in ('all', 'temperature'):
            lines.append("Temperature:")
            lines.append("--------------------------------------------------------------------")
            lines.append(f"{'Module':<10} {'Sensor':<22} {'MajorThresh':<12} {'MinorThresh':<12} {'CurTemp':<8} {'Status'}")
            lines.append(f"{'':<10} {'':<22} {'(Celsius)':<12} {'(Celsius)':<12} {'(Celsius)':<8} {''}")
            lines.append("--------------------------------------------------------------------")
            path_temp = build_path('/platform/control[slot=*]/temperature[sensor-name=*]')
            found_temp = False
            try:
                data = state.server_data_store.get_data(path_temp, recursive=True)
                for ctrl in data.platform.control.items():
                    slot = ctrl.slot
                    if hasattr(ctrl, 'temperature'):
                        for s in ctrl.temperature.items():
                            cur = getattr(s, 'instant', None)
                            if cur is not None:
                                found_temp = True
                                status = "Ok" if getattr(s, 'alarm_status', False) is False else "Alarm"
                                s_name = s.sensor_name
                                lines.append(f"Slot-{slot:<5} {s_name:<22} {'--':<12} {'--':<12} {cur:<8} {status}")
            except Exception:
                pass
            if not found_temp:
                lines.append("No temperature sensor data available.")
            lines.append("")

        if sub_type in ('all', 'power'):
            lines.append("Power Supply:")
            lines.append("---------------------------------------------------------------------------")
            lines.append(f"{'PS':<6} {'Model':<18} {'Power(W)':<12} {'Status'}")
            lines.append("---------------------------------------------------------------------------")
            path_psu = build_path('/platform/power-supply[id=*]')
            found_psu = False
            try:
                data = state.server_data_store.get_data(path_psu, recursive=True)
                for psu in data.platform.power_supply.items():
                    p_id = psu.id
                    p_type = getattr(psu, 'type', '-')
                    oper = getattr(psu, 'oper_state', '-')
                    p_cap = getattr(psu, 'capacity', None)
                    p_cap_str = f"{p_cap}W" if p_cap is not None else "--"
                    if oper != 'empty' or p_type != '-':
                        found_psu = True
                        lines.append(f"{p_id:<6} {p_type:<18} {p_cap_str:<12} {oper}")
            except Exception:
                pass
            if not found_psu:
                lines.append("No power supply modules populated.")
            lines.append("")

        if sub_type in ('all', 'cooling'):
            lines.append("Fan:")
            lines.append("------------------------------------------------------")
            lines.append(f"{'Fan':<10} {'Model':<20} {'Status'}")
            lines.append("------------------------------------------------------")
            path_fan = build_path('/platform/fan-tray[id=*]')
            found_fan = False
            try:
                data = state.server_data_store.get_data(path_fan, recursive=True)
                for fan in data.platform.fan_tray.items():
                    f_id = fan.id
                    oper = getattr(fan, 'oper_state', '-')
                    if oper != 'empty':
                        found_fan = True
                        lines.append(f"Fan{f_id:<7} Chassis Fan          {oper}")
            except Exception:
                pass
            if not found_fan:
                lines.append("No fan tray modules populated.")
            lines.append("")

        output.print_line("\n".join(lines).rstrip())
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show platform environment")

    def show_module(self, state, output):
        """Display Cisco NX-OS style 'show module'."""
        lines = []
        modules = []
        linecard_path = build_path('/platform/linecard[slot=*]')
        ctrl_path = build_path('/platform/control[slot=*]')

        num_ports = 0
        try:
            intf_data = state.server_data_store.get_data(build_path('/interface[name=*]'), recursive=True)
            num_ports = sum(1 for i in intf_data.interface.items() if i.name.startswith('ethernet-'))
        except Exception:
            num_ports = 0
        ports_str = str(num_ports) if num_ports > 0 else "--"

        sw_version = "--"
        try:
            sys_info = state.server_data_store.get_data(build_path('/system/information'), recursive=True)
            info = sys_info.system.get().information.get()
            if hasattr(info, 'version') and info.version:
                sw_version = str(info.version)
        except Exception:
            pass

        serial = "--"
        mac = "--"
        try:
            ch_data = state.server_data_store.get_data(build_path('/platform/chassis'), recursive=True)
            ch = ch_data.platform.get().chassis.get()
            if hasattr(ch, 'serial_number') and ch.serial_number:
                serial = str(ch.serial_number)
            if hasattr(ch, 'hw_mac_address') and ch.hw_mac_address:
                mac = str(ch.hw_mac_address)
        except Exception:
            pass

        try:
            lc_data = state.server_data_store.get_data(linecard_path, recursive=True)
            for lc in lc_data.platform.get().linecard.items():
                slot = getattr(lc, 'slot', '1')
                model = getattr(lc, 'type', '') or getattr(lc, 'part_number', 'Linecard')
                oper = getattr(lc, 'oper_state', 'up')
                status = "ok" if oper == 'up' else "down"
                modules.append({
                    'mod': str(slot),
                    'ports': ports_str,
                    'type': 'Linecard',
                    'model': str(model),
                    'status': status,
                    'sw': sw_version,
                    'hw': '--',
                    'mac': mac,
                    'serial': serial
                })
        except Exception:
            pass

        if not modules:
            try:
                ctrl_data = state.server_data_store.get_data(ctrl_path, recursive=True)
                for c in ctrl_data.platform.get().control.items():
                    slot = getattr(c, 'slot', '1')
                    model = getattr(c, 'type', '') or getattr(c, 'part_number', 'Control')
                    oper = getattr(c, 'oper_state', 'up')
                    status = "ok" if oper == 'up' else "down"
                    modules.append({
                        'mod': '1',
                        'ports': ports_str,
                        'type': 'Fabric/Control',
                        'model': str(model),
                        'status': status,
                        'sw': sw_version,
                        'hw': '--',
                        'mac': mac,
                        'serial': serial
                    })
            except Exception:
                pass

        lines.append(f"{'Mod':<5} {'Ports':<6} {'Module-Type':<35} {'Model':<18} {'Status'}")
        lines.append(f"---  -----  ----------------------------------- ------------------ ----------")
        for m in modules:
            lines.append(f"{m['mod']:<5} {m['ports']:<6} {m['type']:<35} {m['model']:<18} {m['status']}")

        lines.append("")
        lines.append(f"{'Mod':<5} {'Sw':<16} {'Hw'}")
        lines.append(f"---  --------------  ------")
        for m in modules:
            lines.append(f"{m['mod']:<5} {m['sw']:<16} {m['hw']}")

        lines.append("")
        lines.append(f"{'Mod':<5} {'MAC-Address(es)':<39} {'Serial-Num'}")
        lines.append(f"---  --------------------------------------  ----------")
        for m in modules:
            lines.append(f"{m['mod']:<5} {m['mac']:<39} {m['serial']}")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show platform")

    def show_processes_cpu(self, state, output):
        """Display Cisco NX-OS style 'show processes cpu'."""
        lines = []
        load1, load5, load15 = "0.00", "0.00", "0.00"
        try:
            with open('/proc/loadavg') as f:
                parts = f.read().split()
                load1, load5, load15 = parts[0], parts[1], parts[2]
        except Exception:
            pass

        lines.append(f"{'PID':<6} {'Runtime(ms)':<13} {'Invoked':<12} {'uSecs':<6} {'1Sec':<6} {'Process'}")
        lines.append(f"-----  ------------  -----------  -----  -----  -----------------")

        ps_rows = []
        try:
            import subprocess
            ps_out = subprocess.run(["ps", "-eo", "pid,time,%cpu,comm", "--sort=-%cpu"],
                                    stdout=subprocess.PIPE, text=True).stdout
            for p_line in ps_out.strip().split("\n")[1:30]:
                fields = p_line.split(None, 3)
                if len(fields) == 4:
                    pid, tm, cpu, comm = fields
                    # Convert time MM:SS or HH:MM:SS to ms approx
                    t_parts = tm.split(':')
                    ms = 0
                    if len(t_parts) == 2:
                        ms = int(t_parts[0]) * 60000 + int(float(t_parts[1]) * 1000)
                    elif len(t_parts) == 3:
                        ms = int(t_parts[0]) * 3600000 + int(t_parts[1]) * 60000 + int(float(t_parts[2]) * 1000)
                    lines.append(f"{pid:<6} {str(ms):<13} {'1':<12} {'0':<6} {f'{cpu}%':<6} {comm}")
        except Exception:
            pass

        lines.append("")
        lines.append(f"CPU utilization for five seconds: {load1}%; one minute: {load1}%; five minutes: {load5}%")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show system information")
