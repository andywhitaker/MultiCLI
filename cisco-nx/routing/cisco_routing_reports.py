#!/usr/bin/python
###########################################################################
# Description: MultiCLI Routing Reports for Cisco NX-OS
# Copyright (c) 2025-2026 Nokia
###########################################################################

import datetime
import re
from srlinux.location import build_path
from cisco_interface_reports import format_cisco_intf

def format_mac_cisco(mac):
    """Convert MAC address to Cisco standard format xxxx.xxxx.xxxx."""
    if not mac:
        return "0000.0000.0000"
    raw = re.sub(r'[^0-9a-fA-F]', '', str(mac)).lower()
    raw = raw.zfill(12)
    return f"{raw[0:4]}.{raw[4:8]}.{raw[8:12]}"

class CiscoRoutingReports:
    """Handles Cisco NX-OS routing show commands."""

    def show_vrf(self, state, output):
        """Display Cisco NX-OS style 'show vrf'."""
        lines = [
            f"{'VRF-Name':<20} {'VRF-ID':<7} {'State':<7} {'Reason'}",
        ]
        path = build_path('/network-instance[name=*]')
        try:
            data = state.server_data_store.get_data(path, recursive=False)
            vrf_id = 1
            for ni in sorted(data.network_instance.items(), key=lambda x: str(x.name)):
                name = ni.name
                oper = getattr(ni, 'oper_state', 'up')
                state_str = "Up" if oper == "up" else "Down"
                lines.append(f"{name:<20} {str(vrf_id):<7} {state_str:<7} {'--'}")
                vrf_id += 1
        except Exception:
            pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance summary")

    def show_vlan(self, state, output):
        """Display Cisco NX-OS style 'show vlan'."""
        lines = [
            f"{'VLAN':<5} {'Name':<32} {'Status':<9} {'Ports'}",
            f"----- -------------------------------- --------- -------------------------------"
        ]
        path = build_path('/network-instance[name=*]')
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for ni in sorted(data.network_instance.items(), key=lambda x: str(x.name)):
                ni_type = getattr(ni, 'type', '')
                if ni_type != 'mac-vrf':
                    continue
                name = ni.name
                oper = getattr(ni, 'oper_state', 'up')
                status = "active" if oper == "up" else "suspend"

                ports = []
                if hasattr(ni, 'interface'):
                    for intf in ni.interface.items():
                        ports.append(format_cisco_intf(intf.name, short=True))

                vlan_tag = "--"
                for p in ports:
                    if '.' in p:
                        vlan_tag = p.split('.')[-1]
                        break

                ports_str = ", ".join(ports) if ports else "--"
                lines.append(f"{str(vlan_tag):<5} {name:<32} {status:<9} {ports_str}")
        except Exception:
            pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance")

    def show_ip_arp(self, state, output):
        """Display Cisco NX-OS style 'show ip arp'."""
        lines = [
            f"{'Address':<16} {'Age':<9} {'MAC Address':<17} {'Interface'}"
        ]
        found = False
        try:
            path_arpnd = build_path('/interface[name=*]/subinterface[index=*]/ipv4/arp/neighbor[ipv4-address=*]')
            data_arpnd = state.server_data_store.get_data(path_arpnd, recursive=True)
            for intf in data_arpnd.interface.items():
                if hasattr(intf, 'subinterface'):
                    for sub in intf.subinterface.items():
                        if hasattr(sub, 'ipv4') and sub.ipv4.exists():
                            arp = getattr(sub.ipv4.get(), 'arp', None)
                            if arp and hasattr(arp.get(), 'neighbor'):
                                arp_node = arp.get()
                                timeout_val = getattr(arp_node, 'timeout', 14400) or 14400
                                for n in arp_node.neighbor.items():
                                    found = True
                                    ip = n.ipv4_address
                                    mac = format_mac_cisco(getattr(n, 'link_layer_address', ''))
                                    full_intf = f"{intf.name}.{sub.index}" if str(sub.index) != '0' else intf.name
                                    c_intf = format_cisco_intf(full_intf, short=True)

                                    age_str = "--"
                                    origin = getattr(n, 'origin', '')
                                    exp_time = getattr(n, 'expiration_time', None)
                                    if exp_time and origin != 'static':
                                        try:
                                            ts_str = str(exp_time).split('(')[0].strip()
                                            if ts_str.endswith('Z'):
                                                ts_str = ts_str[:-1] + '+00:00'
                                            exp_dt = datetime.datetime.fromisoformat(ts_str)
                                            now = datetime.datetime.now(datetime.timezone.utc)
                                            rem_seconds = (exp_dt - now).total_seconds()
                                            age_sec = max(0, int(timeout_val - rem_seconds))
                                            h, r = divmod(age_sec, 3600)
                                            m, s = divmod(r, 60)
                                            age_str = f"{h:02d}:{m:02d}:{s:02d}"
                                        except Exception:
                                            age_str = "00:00:00"
                                    elif origin == 'dynamic':
                                        age_str = "00:00:00"

                                    lines.append(f"{ip:<16} {age_str:<9} {mac:<17} {c_intf}")
        except Exception:
            pass

        if not found:
            try:
                path = build_path('/network-instance[name=*]/neighbor[ipv4-address=*]')
                data = state.server_data_store.get_data(path, recursive=True)
                for ni in data.network_instance.items():
                    if hasattr(ni, 'neighbor'):
                        for n in ni.neighbor.items():
                            found = True
                            ip = n.ipv4_address
                            mac = format_mac_cisco(getattr(n, 'link_layer_address', ''))
                            intf_name = getattr(n, 'interface', '')
                            if intf_name.endswith('.0'):
                                intf_name = intf_name[:-2]
                            intf = format_cisco_intf(intf_name, short=True)
                            lines.append(f"{ip:<16} {'--':<9} {mac:<17} {intf}")
            except Exception:
                pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show arpnd arp-entries")

    def show_bfd_neighbors(self, state, output):
        """Display Cisco NX-OS style 'show bfd neighbors'."""
        lines = [
            f"{'OurAddr':<15} {'NeighAddr':<15} {'LD/RD':<7} {'RH/RS':<7} {'Holdown(mult)':<15} {'State':<7} {'Int':<8} {'Vrf':<8} {'Type'}"
        ]
        path = build_path('/bfd/network-instance[name=*]/peer[local-discriminator=*]')
        found = False
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for ni in data.bfd.network_instance.items():
                vrf = ni.name
                if hasattr(ni, 'peer'):
                    for p in ni.peer.items():
                        found = True
                        our_addr = getattr(p, 'local_address', '--')
                        neigh_addr = getattr(p, 'remote_address', '--')
                        ld = getattr(p, 'local_discriminator', '--')
                        rd = getattr(p, 'remote_discriminator', '--')
                        state_val = getattr(p, 'oper_state', 'down').capitalize()
                        intf = format_cisco_intf(getattr(p, 'interface', ''), short=True)
                        rh_rs = "Up/Up" if state_val == "Up" else f"{state_val}/--"
                        lines.append(f"{our_addr:<15} {neigh_addr:<15} {f'{ld}/{rd}':<7} {rh_rs:<7} {'--':<15} {state_val:<7} {intf:<8} {vrf:<8} {'--'}")
        except Exception:
            pass

        if not found:
            lines.append("")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show bfd session")

    def show_ip_ospf_neighbor(self, state, output):
        """Display Cisco NX-OS style 'show ip ospf neighbor'."""
        lines = [
            f"{'Neighbor ID':<15} {'Pri':<4} {'State':<15} {'Up Time':<9} {'Address':<15} {'Interface'}"
        ]
        path = build_path('/network-instance[name=*]/protocols/ospf/area[area-id=*]/interface[interface-name=*]/neighbor[router-id=*]')
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for ni in data.network_instance.items():
                if hasattr(ni, 'protocols') and ni.protocols.exists():
                    ospf = getattr(ni.protocols.get(), 'ospf', None)
                    if ospf and hasattr(ospf.get(), 'area'):
                        for area in ospf.get().area.items():
                            if hasattr(area, 'interface'):
                                for intf in area.interface.items():
                                    intf_name = format_cisco_intf(intf.interface_name, short=True)
                                    if hasattr(intf, 'neighbor'):
                                        for n in intf.neighbor.items():
                                            r_id = getattr(n, 'router_id', '--')
                                            n_state = getattr(n, 'oper_state', '--').upper()
                                            ip = getattr(n, 'ipv4_address', '--')
                                            pri = getattr(n, 'priority', '--')
                                            lines.append(f"{r_id:<15} {str(pri):<4} {n_state:<15} {'--':<9} {ip:<15} {intf_name}")
        except Exception:
            pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance <instance> protocols ospf neighbor")

    def show_ip_ospf_interface_brief(self, state, output):
        """Display Cisco NX-OS style 'show ip ospf interface brief'."""
        lines = [
            f"{'Interface':<15} {'VRF-Name':<12} {'State':<6} {'Area':<15} {'IP Address/Mask':<20} {'Cost'}",
            "--------------- ------------ ------ --------------- -------------------- -----"
        ]
        found = False
        path = build_path('/network-instance[name=*]/protocols/ospf')
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for ni in data.network_instance.items():
                vrf = ni.name
                if hasattr(ni, 'protocols') and ni.protocols.exists():
                    ospf = getattr(ni.protocols.get(), 'ospf', None)
                    if not ospf:
                        continue
                    ospf_obj = ospf.get() if hasattr(ospf, 'get') else ospf
                    
                    areas = []
                    if hasattr(ospf_obj, 'instance'):
                        for inst in ospf_obj.instance.items():
                            if hasattr(inst, 'area'):
                                for a in inst.area.items():
                                    areas.append(a)
                    if hasattr(ospf_obj, 'area'):
                        for a in ospf_obj.area.items():
                            areas.append(a)

                    for area in areas:
                        area_id = str(getattr(area, 'area_id', '0.0.0.0'))
                        if hasattr(area, 'interface'):
                            for iface in area.interface.items():
                                found = True
                                intf_disp = format_cisco_intf(iface.interface_name, short=True)
                                cost = str(getattr(iface, 'interface_cost', 10))
                                st = str(getattr(iface, 'oper_state', 'down')).upper()
                                lines.append(f"{intf_disp:<15} {vrf:<12} {st:<6} {area_id:<15} {'--':<20} {cost}")
        except Exception:
            pass

        if not found:
            lines = [
                f"{'Interface':<15} {'VRF-Name':<12} {'State':<6} {'Area':<15} {'IP Address/Mask':<20} {'Cost'}",
                "--------------- ------------ ------ --------------- -------------------- -----",
                "No OSPF interfaces configured."
            ]

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance default protocols ospf interface")

    def show_nve_vni(self, state, output):
        """Display Cisco NX-OS style 'show nve vni'."""
        lines = [
            f"{'VNI':<10} {'Type':<9} {'Mode':<9} {'BD/VRF':<22} {'Flags':<6} {'State'}",
            "--------- --------- --------- ---------------------- ------ -----"
        ]
        vxlan_to_ni = {}
        try:
            ni_data = state.server_data_store.get_data(build_path('/network-instance[name=*]'), recursive=True)
            for ni in ni_data.network_instance.items():
                ni_name = ni.name
                ni_type = getattr(ni, 'type', 'default')
                vni_type = "L2" if ni_type == 'mac-vrf' else "L3"
                if hasattr(ni, 'vxlan_interface'):
                    for vxi in ni.vxlan_interface.items():
                        vxlan_to_ni[vxi.name] = (ni_name, vni_type)
        except Exception:
            pass

        rows = []
        try:
            data = state.server_data_store.get_data(build_path('/tunnel-interface[name=*]/vxlan-interface[index=*]'), recursive=True)
            for ti in data.tunnel_interface.items():
                t_name = ti.name
                if hasattr(ti, 'vxlan_interface'):
                    for vxi in ti.vxlan_interface.items():
                        v_idx = vxi.index
                        full_vxi = f"{t_name}.{v_idx}"
                        oper = getattr(vxi, 'oper_state', 'down').capitalize()
                        vni_num = "--"
                        if hasattr(vxi, 'ingress') and vxi.ingress.exists():
                            vni_num = str(getattr(vxi.ingress.get(), 'vni', '--'))
                        
                        ni_info = vxlan_to_ni.get(full_vxi, (t_name, "L2"))
                        rows.append({
                            'vni': vni_num,
                            'type': ni_info[1],
                            'mode': 'DP',
                            'bd_vrf': ni_info[0],
                            'flags': 'CP',
                            'state': oper
                        })
        except Exception:
            pass

        if rows:
            rows.sort(key=lambda r: int(r['vni']) if r['vni'].isdigit() else 999999)
            for r in rows:
                lines.append(f"{r['vni']:<10} {r['type']:<9} {r['mode']:<9} {r['bd_vrf']:<22} {r['flags']:<6} {r['state']}")
        else:
            lines.append("No VNIs configured.")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show tunnel-interface")

    def show_nve_peers(self, state, output):
        """Display Cisco NX-OS style 'show nve peers'."""
        lines = [
            f"{'Interface':<10} {'Peer-IP':<16} {'Source-Interface':<17} {'State':<8} {'Learn-Type'}",
            "---------  ---------------  ----------------  -------  ----------"
        ]
        rows = []
        try:
            path = build_path('/tunnel-interface[name=*]/vxlan-interface[index=*]/bridge-table/unicast-destinations/destination[vtep=*]')
            data = state.server_data_store.get_data(path, recursive=True)
            for ti in data.tunnel_interface.items():
                if hasattr(ti, 'vxlan_interface'):
                    for vxi in ti.vxlan_interface.items():
                        vxi_name = f"{ti.name}.{vxi.index}"
                        bt = getattr(vxi, 'bridge_table', None)
                        if bt and hasattr(bt.get(), 'unicast_destinations'):
                            ud = bt.get().unicast_destinations.get()
                            if hasattr(ud, 'destination'):
                                for dest in ud.destination.items():
                                    vtep = getattr(dest, 'vtep', None)
                                    if vtep:
                                        dest_oper = getattr(dest, 'oper_state', 'up').capitalize()
                                        rows.append({
                                            'intf': 'nve1',
                                            'peer': str(vtep),
                                            'src': vxi_name,
                                            'state': dest_oper if dest_oper in ('Up', 'Down') else 'Up',
                                            'learn': 'CP'
                                        })
        except Exception:
            pass

        seen = set()
        unique_rows = []
        for r in rows:
            if r['peer'] not in seen:
                seen.add(r['peer'])
                unique_rows.append(r)

        if unique_rows:
            for r in unique_rows:
                lines.append(f"{r['intf']:<10} {r['peer']:<16} {r['src']:<17} {r['state']:<8} {r['learn']}")
        else:
            lines.append("No NVE peers discovered.")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show tunnel-interface vxlan-interface bridge-table")

    def show_vpc(self, state, output):
        """Display Cisco NX-OS style 'show vpc'."""
        lines = []
        found = False
        vpc_rows = []
        domain_id = 1
        peer_link_up = False
        try:
            path = build_path('/system/network-instance/protocols/evpn/ethernet-segments')
            data = state.server_data_store.get_data(path, recursive=True)
            sys_node = getattr(data, 'system', None)
            if sys_node and hasattr(sys_node.get(), 'network_instance'):
                sys_ni = sys_node.get().network_instance.get()
                if hasattr(sys_ni, 'protocols'):
                    evpn = getattr(sys_ni.protocols.get(), 'evpn', None)
                    if evpn and hasattr(evpn.get(), 'ethernet_segments'):
                        es_container = evpn.get().ethernet_segments.get()
                        if hasattr(es_container, 'bgp_instance'):
                            for bi in es_container.bgp_instance.items():
                                domain_id = getattr(bi, 'id', 1)
                                if hasattr(bi, 'ethernet_segment'):
                                    for es_idx, es in enumerate(bi.ethernet_segment.items(), 1):
                                        found = True
                                        intf = getattr(es, 'interface', f'Po{es_idx}')
                                        admin_st = getattr(es, 'admin_state', 'enable')
                                        oper_st = getattr(es, 'oper_state', 'down').lower()
                                        is_up = (admin_st == 'enable' and oper_st == 'up')
                                        if is_up:
                                            peer_link_up = True
                                        vpc_rows.append({
                                            'id': str(es_idx),
                                            'port': format_cisco_intf(intf, short=True),
                                            'status': 'Up' if is_up else 'Down',
                                            'att': '1' if is_up else '0',
                                            'consistency': 'Passed' if is_up else 'Failed'
                                        })
        except Exception:
            pass

        if found:
            peer_st_str = "peer-link is up" if peer_link_up else "peer-link is down"
            ka_st_str = "Active" if peer_link_up else "Inactive"
            cfg_st_str = "success" if peer_link_up else "failed"
            pl_num = "1" if peer_link_up else "0"
            lines = [
                "Legend:",
                "                (*) - local vPC is down, forwarding via vPC peer-link",
                "",
                f"vPC domain id                     : {domain_id}",
                f"Peer status                       : {peer_st_str}",
                f"vPC keep-alive status             : {ka_st_str}",
                f"Configuration status              : {cfg_st_str}",
                f"Peer-link status                  : {pl_num}",
                "",
                "vPC status",
                "----------------------------------------------------------------------------",
                f"{'Id':<5} {'Port':<23} {'Status':<7} {'Att':<4} {'Consistency'}",
                "--    ----------------------  ------  ---  -----------",
            ]
            for r in vpc_rows:
                lines.append(f"{r['id']:<5} {r['port']:<23} {r['status']:<7} {r['att']:<4} {r['consistency']}")
        else:
            lines = [
                "vPC domain id                     : --",
                "Peer status                       : peer-link is down",
                "vPC keep-alive status             : Disabled / Not Configured",
                "Configuration status              : Disabled",
                "",
                "vPC is not configured on this device."
            ]

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show system network-instance protocols evpn")
