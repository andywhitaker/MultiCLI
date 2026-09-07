#!/usr/bin/python
###########################################################################
# Description: MultiCLI Arista EOS Routing Reports
# Commands: show ip route, show vrf, show vlan, show mac address-table,
#           show ip ospf neighbor, show isis neighbors
# Copyright (c) 2026 Nokia
###########################################################################

import ipaddress
import re
from srlinux.location import build_path

def format_mac_cisco_arista(mac_str):
    if not mac_str:
        return ""
    clean = str(mac_str).replace(':', '').replace('-', '').replace('.', '').lower()
    if len(clean) == 12:
        return f"{clean[0:4]}.{clean[4:8]}.{clean[8:12]}"
    return mac_str

def format_arista_intf(name, short=False):
    if not name:
        return ""
    name = str(name)
    if name.endswith('.0'):
        name = name[:-2]
    if name.startswith('ethernet-'):
        num = name.replace('ethernet-', '')
        return f"Et{num}" if short else f"Ethernet{num}"
    if name.startswith('mgmt'):
        num = name.replace('mgmt', '') or '1'
        return f"Ma{num}" if short else f"Management{num}"
    if name.startswith('lag'):
        num = name.replace('lag', '')
        return f"Po{num}" if short else f"Port-Channel{num}"
    if name.startswith(('lo', 'system')):
        num = name.replace('system', '').replace('lo', '') or '0'
        return f"Lo{num}" if short else f"Loopback{num}"
    if name.startswith('irb'):
        num = name.replace('irb', '')
        if '.' in num:
            num = num.split('.', 1)[1]
        return f"Vlan{num}"
    return name

class AristaRoutingReports:
    """Handles Arista EOS routing show commands."""

    ROUTE_CODE_MAP = {
        'connected': ' C   ',
        'local': ' L   ',
        'static': ' S   ',
        'bgp': ' B I ',
        'bgp-evpn': ' B I ',
        'bgp-vpn': ' B I ',
        'ospf': ' O   ',
        'ospfv2': ' O   ',
        'ospfv3': ' O3  ',
        'isis': ' I L2',
        'aggregate': ' A B ',
        'host': ' K   ',
    }

    def show_ip_route(self, state, output, vrf='default'):
        """Display Arista EOS style 'show ip route [vrf <vrf>]'."""
        lines = [
            f"VRF name: {vrf}",
            "Codes: C - connected, S - static, K - kernel,",
            "       O - OSPF, IA - OSPF inter area, E1 - OSPF external type 1,",
            "       E2 - OSPF external type 2, N1 - OSPF NSSA external type 1,",
            "       N2 - OSPF NSSA external type2, B I - iBGP, B E - eBGP,",
            "       R - RIP, I L1 - ISIS level 1, I L2 - ISIS level 2,",
            "       O3 - OSPFv3, A B - BGP Aggregate, A O - OSPF Summary,",
            "       NG - Nexthop Group Static Route, V - VXLAN Control Service",
            ""
        ]

        routes = []
        nh_map = {}
        nhg_map = {}

        try:
            rt_path = build_path('/network-instance[name={name}]/route-table', name=vrf)
            rt_data = state.server_data_store.get_data(rt_path, recursive=True)

            # Build next-hop index to IP/interface mapping
            for nh in rt_data.get_descendants('/network-instance/route-table/next-hop'):
                nh_idx = getattr(nh, 'index', None)
                if nh_idx is not None:
                    ip = getattr(nh, 'ip_address', None)
                    subif = getattr(nh, 'subinterface', None)
                    nh_map[str(nh_idx)] = {
                        'ip': str(ip) if ip else None,
                        'interface': str(subif) if subif else None
                    }

            # Build next-hop group mapping
            for nhg in rt_data.get_descendants('/network-instance/route-table/next-hop-group'):
                nhg_idx = getattr(nhg, 'index', None)
                if nhg_idx is not None and hasattr(nhg, 'next_hop'):
                    hops = []
                    for nh_item in nhg.next_hop.items():
                        target_nh = getattr(nh_item, 'next_hop', None)
                        if target_nh is not None and str(target_nh) in nh_map:
                            hops.append(nh_map[str(target_nh)])
                    nhg_map[str(nhg_idx)] = hops

            for r in rt_data.get_descendants('/network-instance/route-table/ipv4-unicast/route'):
                pfx = getattr(r, 'ipv4_prefix', None)
                if not pfx:
                    continue
                rtype = str(getattr(r, 'route_type', '')).lower()
                rowner = str(getattr(r, 'route_owner', '')).lower()

                if 'connected' in rowner or 'direct' in rowner or rtype in ('local', 'connected'):
                    code = ' C   '
                elif 'host' in rtype or 'local' in rowner:
                    code = ' L   '
                elif 'bgp' in rowner or 'bgp' in rtype:
                    code = ' B I '
                elif 'ospf' in rowner or 'ospf' in rtype:
                    code = ' O   '
                elif 'isis' in rowner or 'isis' in rtype:
                    code = ' I L2'
                else:
                    code = ' S   '

                metric = getattr(r, 'metric', 0)
                pref = getattr(r, 'preference', 0)
                nhg_id = getattr(r, 'next_hop_group', None)
                route_hops = nhg_map.get(str(nhg_id), [])

                routes.append({
                    'prefix': pfx,
                    'code': code,
                    'pref': pref,
                    'metric': metric,
                    'owner': rowner,
                    'type': rtype,
                    'hops': route_hops
                })
        except Exception:
            pass

        default_route = next((r for r in routes if r['prefix'] == '0.0.0.0/0'), None)
        if default_route:
            lines.append("Gateway of last resort is set\n")
        else:
            lines.append("Gateway of last resort is not set\n")

        # Sort routes by IP network
        try:
            sorted_routes = sorted(routes, key=lambda x: ipaddress.ip_network(x['prefix']).network_address)
        except Exception:
            sorted_routes = routes

        for r in sorted_routes:
            hops = r.get('hops', [])
            is_conn = ('C' in r['code'] or 'L' in r['code'])
            if is_conn:
                if hops and hops[0].get('interface'):
                    disp_intf = format_arista_intf(hops[0]['interface'], short=False)
                    lines.append(f"{r['code']:<5} {r['prefix']} is directly connected, {disp_intf}")
                else:
                    lines.append(f"{r['code']:<5} {r['prefix']} is directly connected")
            else:
                if hops and hops[0].get('ip'):
                    nh_ip = hops[0]['ip']
                    nh_intf = f", {format_arista_intf(hops[0]['interface'], short=False)}" if hops[0].get('interface') else ""
                    lines.append(f"{r['code']:<5} {r['prefix']} [{r['pref']}/{r['metric']}] via {nh_ip}{nh_intf}")
                else:
                    lines.append(f"{r['code']:<5} {r['prefix']} [{r['pref']}/{r['metric']}]")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line(f"Try SR Linux command: show network-instance {vrf} route-table")

    def show_vrf(self, state, output):
        """Display Arista EOS style 'show vrf'."""
        lines = [
            "Maximum number of vrfs allowed: 4095",
            f"  {'Vrf':<9} {'RD':<14} {'Protocols':<14} {'State':<19} {'Interfaces'}",
            f"--------- -------------- -------------- ------------------- ---------------------"
        ]
        path = build_path('/network-instance[name=*]')
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for ni in sorted(data.network_instance.items(), key=lambda x: str(x.name)):
                try:
                    name = ni.name
                    ni_type = getattr(ni, 'type', 'default')
                    rd = "-"

                    if hasattr(ni, 'protocols') and ni.protocols.exists():
                        p_obj = ni.protocols.get()
                        bgp_vpn = getattr(p_obj, 'bgp_vpn', None)
                        if bgp_vpn and hasattr(bgp_vpn, 'exists') and bgp_vpn.exists():
                            bv_obj = bgp_vpn.get()
                            if hasattr(bv_obj, 'bgp_instance'):
                                for bi in bv_obj.bgp_instance.items():
                                    rd_val = getattr(bi, 'route_distinguisher', None)
                                    if rd_val:
                                        m = re.search(r'rd\s+([0-9\.:]+)', str(rd_val))
                                        if m:
                                            rd = m.group(1)
                                        else:
                                            rd = str(getattr(rd_val, 'rd', rd_val)).strip()
                                        break

                    # Interfaces
                    intfs = []
                    has_v4 = False
                    has_v6 = False
                    if hasattr(ni, 'interface'):
                        for intf in ni.interface.items():
                            intfs.append(format_arista_intf(intf.name, short=False))

                    if ni_type == 'mac-vrf':
                        proto_str = "-"
                        v4_state = "v4:no routing,"
                        v6_state = "v6:no routing"
                    else:
                        # Determine protocols dynamically from route table or interfaces
                        try:
                            v4_path = build_path('/network-instance[name={name}]/route-table/ipv4-unicast/route[ipv4-prefix=*]', name=name)
                            v4_data = state.server_data_store.get_data(v4_path, recursive=False)
                            has_v4 = len(list(v4_data.get_descendants('/network-instance/route-table/ipv4-unicast/route'))) > 0
                        except Exception:
                            has_v4 = True

                        try:
                            v6_path = build_path('/network-instance[name={name}]/route-table/ipv6-unicast/route[ipv6-prefix=*]', name=name)
                            v6_data = state.server_data_store.get_data(v6_path, recursive=False)
                            has_v6 = len(list(v6_data.get_descendants('/network-instance/route-table/ipv6-unicast/route'))) > 0
                        except Exception:
                            has_v6 = False

                        protos = []
                        if has_v4:
                            protos.append('ipv4')
                        if has_v6:
                            protos.append('ipv6')
                        proto_str = ",".join(protos) if protos else "ipv4"
                        v4_state = "v4:routing," if has_v4 else "v4:no routing,"
                        v6_state = "v6:routing" if has_v6 else "v6:no routing"

                    intf_str = ", ".join(intfs[:3]) if intfs else "-"
                    lines.append(f"  {name:<9} {rd:<14} {proto_str:<14} {v4_state:<19} {intf_str}")
                    lines.append(f"  {'':<9} {'':<14} {'':<14} {v6_state:<19}")
                except Exception:
                    pass
        except Exception:
            pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance summary")

    def show_vlan(self, state, output):
        """Display Arista EOS style 'show vlan'."""
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
                status = "active" if oper == "up" else "suspended"

                ports = []
                if hasattr(ni, 'interface'):
                    for intf in ni.interface.items():
                        ports.append(format_arista_intf(intf.name, short=True))

                vlan_tag = "--"
                for p in ports:
                    if '.' in p:
                        vlan_tag = p.split('.')[-1]
                        break

                ports_str = ", ".join(ports) if ports else "-"
                lines.append(f"{str(vlan_tag):<5} {name:<32} {status:<9} {ports_str}")
        except Exception:
            pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance")

    def show_mac_address_table(self, state, output):
        """Display Arista EOS style 'show mac address-table'."""
        lines = [
            f"{'':>10}Mac Address Table",
            f"------------------------------------------------------------------\n",
            f"{'Vlan':<7} {'Mac Address':<17} {'Type':<11} {'Ports':<10} {'Moves':<7} {'Last Move'}",
            f"{'----':<7} {'-----------':<17} {'----':<11} {'-----':<10} {'-----':<7} {'---------'}"
        ]
        path = build_path('/network-instance[name=*]/bridge-table/mac-table/mac[address=*]')
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for entry in data.get_descendants('/network-instance/bridge-table/mac-table/mac'):
                mac_addr = format_mac_cisco_arista(getattr(entry, 'address', ''))
                mac_type = "DYNAMIC" if getattr(entry, 'type', 'learnt') in ('learnt', 'evpn') else "STATIC"
                dest = getattr(entry, 'destination', '')
                vlan_str = "--"
                if 'vxlan' in dest.lower():
                    m_vni = re.search(r'vni:(\d+)', dest)
                    if m_vni:
                        port = 'Vx' + m_vni.group(1)
                        vlan_str = m_vni.group(1)
                    else:
                        port = 'VxLAN'
                elif 'irb' in dest.lower():
                    m = re.search(r'irb\d*\.(\d+)', dest)
                    if m:
                        vlan_str = m.group(1)
                        port = f"Vlan{vlan_str}"
                    else:
                        port = "Vlan--"
                else:
                    port = format_arista_intf(dest.split()[0] if dest else "-", short=True)
                    if '.' in port:
                        vlan_str = port.split('.')[-1]
                lines.append(f"{vlan_str:<7} {mac_addr:<17} {mac_type:<11} {port:<10} {'--':<7} {'-'}")
        except Exception:
            pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance <instance> bridge-table mac-table all")

    def show_ip_ospf_neighbor(self, state, output):
        """Display Arista EOS style 'show ip ospf neighbor'."""
        lines = [
            f"{'Neighbor ID':<15} {'VRF':<6} {'Pri':<5} {'State':<16} {'Dead Time':<11} {'Address':<15} {'Interface'}"
        ]
        path = build_path('/network-instance[name=*]/protocols/ospf/area[area-id=*]/interface[interface-name=*]/neighbor[router-id=*]')
        found = False
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for ni in data.network_instance.items():
                vrf = ni.name
                if hasattr(ni, 'protocols') and ni.protocols.exists():
                    ospf = getattr(ni.protocols.get(), 'ospf', None)
                    if ospf and hasattr(ospf.get(), 'area'):
                        for area in ospf.get().area.items():
                            if hasattr(area, 'interface'):
                                for intf in area.interface.items():
                                    intf_name = format_arista_intf(intf.interface_name, short=False)
                                    if hasattr(intf, 'neighbor'):
                                        for n in intf.neighbor.items():
                                            found = True
                                            r_id = getattr(n, 'router_id', '--')
                                            n_state = getattr(n, 'oper_state', '--').upper()
                                            ip = getattr(n, 'ipv4_address', '--')
                                            pri = getattr(n, 'priority', '--')
                                            lines.append(f"{r_id:<15} {vrf:<6} {str(pri):<5} {n_state:<16} {'--':<11} {ip:<15} {intf_name}")
        except Exception:
            pass

        if not found:
            lines.append("No OSPF neighbors configured or active.")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance default protocols ospf neighbor")

    def show_isis_neighbors(self, state, output):
        """Display Arista EOS style 'show isis neighbors'."""
        lines = [
            f"{'Instance':<13} {'VRF':<12} {'System Id':<15} {'Type':<4} {'Interface':<18} {'Sni':<8} {'Holdtime':<8} {'State'}"
        ]
        path = build_path('/network-instance[name=*]/protocols/isis/instance[name=*]/adjacency[system-id=*]')
        found = False
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for ni in data.network_instance.items():
                vrf = ni.name
                if hasattr(ni, 'protocols') and ni.protocols.exists():
                    isis = getattr(ni.protocols.get(), 'isis', None)
                    if isis and hasattr(isis.get(), 'instance'):
                        for inst in isis.get().instance.items():
                            inst_name = inst.name
                            if hasattr(inst, 'adjacency'):
                                for adj in inst.adjacency.items():
                                    found = True
                                    sys_id = getattr(adj, 'system_id', '--')
                                    intf = format_arista_intf(getattr(adj, 'interface_name', ''), short=False)
                                    level = getattr(adj, 'level', 'L2')
                                    oper = getattr(adj, 'oper_state', '--').upper()
                                    hold = getattr(adj, 'remaining_hold_time', '--')
                                    lines.append(f"{inst_name:<13} {vrf:<12} {sys_id:<15} {level:<4} {intf:<18} {'-':<8} {str(hold):<8} {oper}")
        except Exception:
            pass

        if not found:
            lines.append("No IS-IS neighbors configured or active.")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance default protocols isis adjacency")

    def show_ip_ospf_interface_brief(self, state, output):
        """Display Arista EOS style 'show ip ospf interface brief'."""
        lines = [
            f"{'Interface':<16} {'Instance':<9} {'VRF':<9} {'Area':<16} {'IP Address/Mask':<19} {'Cost':<6} {'State':<7} {'Nbrs'}",
            "---------------- -------- -------- --------------- ------------------ ----- ------ ----"
        ]
        path = build_path('/network-instance[name=*]/protocols/ospf/instance[name=*]/area[area-id=*]/interface[interface-name=*]')
        found = False
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for ni in data.network_instance.items():
                vrf = ni.name
                if hasattr(ni, 'protocols') and ni.protocols.exists():
                    ospf = getattr(ni.protocols.get(), 'ospf', None)
                    if ospf and hasattr(ospf.get(), 'instance'):
                        for inst in ospf.get().instance.items():
                            inst_name = inst.name
                            if hasattr(inst, 'area'):
                                for area in inst.area.items():
                                    area_id = area.area_id
                                    if hasattr(area, 'interface'):
                                        for iface in area.interface.items():
                                            found = True
                                            intf_disp = format_arista_intf(iface.interface_name, short=False)
                                            cost = getattr(iface, 'interface_cost', 10)
                                            st = getattr(iface, 'oper_state', 'down').upper()
                                            nbrs = getattr(iface, 'neighbor_count', 0)
                                            ip_mask = "--"
                                            try:
                                                sub_name = str(iface.interface_name)
                                                if '.' in sub_name:
                                                    p_name, s_idx = sub_name.split('.', 1)
                                                    p_intf = build_path('/interface[name={name}]/subinterface[index={idx}]/ipv4/address', name=p_name, idx=s_idx)
                                                    d_intf = state.server_data_store.get_data(p_intf, recursive=False)
                                                    for a in d_intf.get_descendants('/interface/subinterface/ipv4/address'):
                                                        if hasattr(a, 'ip_prefix') and a.ip_prefix:
                                                            ip_mask = str(a.ip_prefix)
                                                            break
                                            except Exception:
                                                pass
                                            lines.append(f"{intf_disp:<16} {inst_name:<9} {vrf:<9} {str(area_id):<16} {ip_mask:<19} {str(cost):<6} {st:<7} {str(nbrs)}")
        except Exception:
            pass

        if not found:
            lines = [
                f"{'Interface':<16} {'Instance':<9} {'VRF':<9} {'Area':<16} {'IP Address/Mask':<19} {'Cost':<6} {'State':<7} {'Nbrs'}",
                "---------------- -------- -------- --------------- ------------------ ----- ------ ----",
                "No OSPF interfaces configured."
            ]

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance default protocols ospf interface")

    def show_mlag(self, state, output):
        """Display Arista EOS style 'show mlag'."""
        lines = []
        path = build_path('/system/network-instance/protocols/evpn/ethernet-segments')
        found = False
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            # Check for EVPN MH / ESI
            es_container = getattr(data.system.get().network_instance.get().protocols.get().evpn.get(), 'ethernet_segments', None)
            if es_container and hasattr(es_container.get(), 'bgp_instance'):
                for bi in es_container.get().bgp_instance.items():
                    if hasattr(bi, 'ethernet_segment'):
                        for es in bi.ethernet_segment.items():
                            found = True
                            esi = getattr(es, 'esi', '--')
                            intf = getattr(es, 'interface', '') or 'Po1'
                            domain_id = getattr(bi, 'id', 1)
                            admin_st = getattr(es, 'admin_state', 'enable')
                            oper_st = getattr(es, 'oper_state', 'down')
                            mlag_state = "Active" if (admin_st == "enable" and oper_st == "up") else "Inactive"

                            peer_addr = "--"
                            lines = [
                                "MLAG Configuration:",
                                f"domain-id           : {domain_id}",
                                f"local-interface     : {format_arista_intf(intf, short=True)}",
                                f"peer-address        : {peer_addr}",
                                f"peer-link           : {format_arista_intf(intf, short=True)}",
                                f"state               : {mlag_state}"
                            ]
                            break
        except Exception:
            pass

        if not found:
            lines = [
                "MLAG Configuration:",
                "domain-id           : --",
                "local-interface     : --",
                "peer-address        : --",
                "peer-link           : --",
                "state               : Disabled / Not Configured"
            ]

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show system network-instance protocols evpn")

