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
        return name
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
                if nh_idx is None:
                    continue

                nh_type = getattr(nh, 'type', None)
                ip = getattr(nh, 'ip_address', None)
                subif = getattr(nh, 'subinterface', None)
                resolving_nhg = None

                if nh_type == 'tunnel' and hasattr(nh, 'tunnel'):
                    try:
                        t = nh.tunnel.get()
                        pfx = getattr(t, 'ip_prefix', None)
                        if pfx and not ip:
                            ip = str(pfx).split('/')[0]
                    except Exception:
                        pass

                if nh_type == 'indirect' and hasattr(nh, 'indirect'):
                    try:
                        ind = nh.indirect.get()
                        rr = getattr(ind, 'resolving_route', None)
                        if rr:
                            resolving_nhg = getattr(rr.get(), 'next_hop_group', None)
                    except Exception:
                        pass

                nh_map[str(nh_idx)] = {
                    'ip': str(ip) if ip else None,
                    'interface': str(subif) if subif else None,
                    'resolving_nhg': str(resolving_nhg) if resolving_nhg is not None else None,
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

            # Resolve indirect next-hop interfaces via resolving route's next-hop group
            for nh_info in nh_map.values():
                if not nh_info['interface'] and nh_info.get('resolving_nhg'):
                    target_hops = nhg_map.get(nh_info['resolving_nhg'], [])
                    for th in target_hops:
                        if th.get('interface'):
                            nh_info['interface'] = th['interface']
                            break

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
        rd_by_ni = {}
        try:
            bv_p = build_path('/network-instance[name=*]/protocols/bgp-vpn')
            bv_data = state.server_data_store.get_data(bv_p, recursive=True)
            for ni in bv_data.network_instance.items():
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
                                        rd_by_ni[ni.name] = m.group(1)
                                    else:
                                        rd_by_ni[ni.name] = str(getattr(rd_val, 'rd', rd_val)).strip()
                                    break
        except Exception:
            pass

        intfs_by_ni = {}
        try:
            intf_p = build_path('/network-instance[name=*]/interface[name=*]')
            intf_data = state.server_data_store.get_data(intf_p, recursive=False)
            for ni in intf_data.network_instance.items():
                if hasattr(ni, 'interface'):
                    intfs_by_ni[ni.name] = [format_arista_intf(intf.name, short=False) for intf in ni.interface.items()]
        except Exception:
            pass

        path = build_path('/network-instance[name=*]')
        try:
            data = state.server_data_store.get_data(path, recursive=False)
            for ni in sorted(data.network_instance.items(), key=lambda x: str(x.name)):
                try:
                    name = ni.name
                    ni_type = getattr(ni, 'type', 'default')
                    rd = rd_by_ni.get(name, "-")

                    intfs = intfs_by_ni.get(name, [])

                    if ni_type == 'mac-vrf':
                        proto_str = "-"
                        v4_state = "v4:no routing,"
                        v6_state = "v6:no routing"
                    else:
                        has_v4 = bool(intfs)
                        has_v6 = False
                        protos = ['ipv4']
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

    def _get_vlan_for_ni(self, state, raw_intfs):
        """Extract VLAN ID for a mac-vrf network instance:
        1. Check member subinterfaces' single-tagged VLAN encapsulation.
        2. Fall back to IRB subinterface index (e.g. irb0.1 -> 1).
        3. Fall back to subinterface index if > 0.
        4. Fall back to '--'.
        """
        # 1. Single-tagged encapsulation from member subinterfaces
        for intf_name in raw_intfs:
            if '.' in intf_name and not intf_name.startswith('irb'):
                p_name, sub_idx = intf_name.split('.', 1)
                try:
                    p = build_path(f'/interface[name={p_name}]/subinterface[index={sub_idx}]/vlan/encap/single-tagged/vlan-id')
                    d = state.server_data_store.get_data(p, recursive=False)
                    vlan_val = getattr(d.interface.get().subinterface.get().vlan.get().encap.get().single_tagged.get(), 'vlan_id', None)
                    if vlan_val is not None:
                        return str(vlan_val)
                except Exception:
                    pass

        # 2. Fall back to IRB subinterface index
        for intf_name in raw_intfs:
            if 'irb' in intf_name:
                m = re.search(r'irb\d*\.(\d+)', intf_name)
                if m:
                    return m.group(1)

        # 3. Fall back to subinterface index if > 0
        for intf_name in raw_intfs:
            if '.' in intf_name:
                sub_idx = intf_name.split('.', 1)[1]
                if sub_idx != '0':
                    return sub_idx

        return "--"

    def show_vlan(self, state, output):
        """Display Arista EOS style 'show vlan'."""
        lines = [
            f"{'VLAN':<5} {'Name':<32} {'Status':<9} {'Ports'}",
            f"----- -------------------------------- --------- -------------------------------"
        ]
        intfs_by_ni = {}
        raw_intfs_by_ni = {}
        try:
            intf_p = build_path('/network-instance[name=*]/interface[name=*]')
            intf_data = state.server_data_store.get_data(intf_p, recursive=False)
            for ni in intf_data.network_instance.items():
                if hasattr(ni, 'interface'):
                    raw_intfs_by_ni[ni.name] = [intf.name for intf in ni.interface.items()]
                    intfs_by_ni[ni.name] = [format_arista_intf(intf.name, short=True) for intf in ni.interface.items()]
        except Exception:
            pass

        path = build_path('/network-instance[name=*]')
        try:
            data = state.server_data_store.get_data(path, recursive=False)
            for ni in sorted(data.network_instance.items(), key=lambda x: str(x.name)):
                ni_type = getattr(ni, 'type', '')
                if ni_type != 'mac-vrf':
                    continue
                name = ni.name
                oper = getattr(ni, 'oper_state', 'up')
                status = "active" if oper == "up" else "suspended"

                ports = intfs_by_ni.get(name, [])
                raw_ports = raw_intfs_by_ni.get(name, [])
                vlan_tag = self._get_vlan_for_ni(state, raw_ports)

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
        vlan_by_ni = {}
        ports_by_ni = {}
        try:
            intf_p = build_path('/network-instance[name=*]/interface[name=*]')
            intf_data = state.server_data_store.get_data(intf_p, recursive=False)
            for ni in intf_data.network_instance.items():
                if hasattr(ni, 'interface'):
                    raw_ports = [intf.name for intf in ni.interface.items()]
                    ports_by_ni[ni.name] = raw_ports
                    vlan_by_ni[ni.name] = self._get_vlan_for_ni(state, raw_ports)
        except Exception:
            pass

        path = build_path('/network-instance[name=*]/bridge-table/mac-table/mac[address=*]')
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for ni in getattr(data, 'network_instance', []).items() if hasattr(data, 'network_instance') else []:
                ni_name = ni.name
                ni_vlan = vlan_by_ni.get(ni_name, "--")
                bridge_table = getattr(ni, 'bridge_table', None)
                if not bridge_table:
                    continue
                mac_table = getattr(bridge_table.get(), 'mac_table', None)
                if not mac_table:
                    continue
                for entry in mac_table.get().mac.items():
                    mac_addr = format_mac_cisco_arista(getattr(entry, 'address', ''))
                    raw_type = getattr(entry, 'type', 'learnt')
                    mac_type = "STATIC" if ('irb' in raw_type or raw_type == 'static') else "DYNAMIC"
                    dest = getattr(entry, 'destination', '')
                    vlan_str = ni_vlan
                    if 'vxlan' in dest.lower():
                        m_vni = re.search(r'vni:(\d+)', dest)
                        if m_vni:
                            port = 'Vx' + m_vni.group(1)
                        else:
                            port = 'VxLAN'
                    elif 'irb' in dest.lower():
                        ni_ports = ports_by_ni.get(ni_name, [])
                        irb_ports = [p for p in ni_ports if 'irb' in p]
                        port = irb_ports[0] if irb_ports else "irb"
                    else:
                        port = format_arista_intf(dest.split()[0] if dest else "-", short=True)
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
        path = build_path('/network-instance[name=*]/protocols/ospf/instance[name=*]/area[area-id=*]/interface[interface-name=*]/neighbor[router-id=*]')
        found = False
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for ni in data.network_instance.items():
                vrf = ni.name
                if hasattr(ni, 'protocols') and ni.protocols.exists():
                    ospf = getattr(ni.protocols.get(), 'ospf', None)
                    if ospf and hasattr(ospf.get(), 'instance'):
                        for inst in ospf.get().instance.items():
                            if hasattr(inst, 'area'):
                                for area in inst.area.items():
                                    if hasattr(area, 'interface'):
                                        for intf in area.interface.items():
                                            intf_name = format_arista_intf(intf.interface_name, short=False)
                                            if hasattr(intf, 'neighbor'):
                                                for n in intf.neighbor.items():
                                                    found = True
                                                    r_id = getattr(n, 'router_id', '--')
                                                    adj_st = getattr(n, 'adjacency_state', None)
                                                    n_state = str(adj_st).split(':')[-1].upper() if adj_st else '--'
                                                    ip = getattr(n, 'address', '--')
                                                    pri = getattr(n, 'priority', '--')
                                                    dead = getattr(n, 'dead_time', None)
                                                    if dead is not None:
                                                        try:
                                                            d_sec = int(dead)
                                                            m, s = divmod(d_sec, 60)
                                                            h, m = divmod(m, 60)
                                                            dead_str = f"{h:02d}:{m:02d}:{s:02d}"
                                                        except Exception:
                                                            dead_str = str(dead)
                                                    else:
                                                        dead_str = '--'
                                                    lines.append(f"{r_id:<15} {vrf:<6} {str(pri):<5} {n_state:<16} {dead_str:<11} {str(ip):<15} {intf_name}")
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
        path = build_path('/network-instance[name=*]/protocols/isis/instance[name=*]/interface[interface-name=*]/adjacency[neighbor-system-id=*][adjacency-level=*]')
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
                            if hasattr(inst, 'interface'):
                                for iface in inst.interface.items():
                                    intf_name = format_arista_intf(iface.interface_name, short=False)
                                    if hasattr(iface, 'adjacency'):
                                        for adj in iface.adjacency.items():
                                            found = True
                                            sys_id = getattr(adj, 'neighbor_system_id', '--')
                                            level = getattr(adj, 'adjacency_level', '2')
                                            type_str = f"L{level}" if not str(level).startswith('L') else str(level)
                                            raw_st = getattr(adj, 'state', '--')
                                            oper = str(raw_st).split(':')[-1].upper() if raw_st else '--'
                                            hold = getattr(adj, 'remaining_holdtime', '--')
                                            lines.append(f"{inst_name:<13} {vrf:<12} {sys_id:<15} {type_str:<4} {intf_name:<18} {'-':<8} {str(hold):<8} {oper}")
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
        intf_ip_map = {}
        try:
            intf_path = build_path('/interface[name=*]/subinterface[index=*]/ipv4/address')
            intf_data = state.server_data_store.get_data(intf_path, recursive=False)
            for intf in intf_data.interface.items():
                if hasattr(intf, 'subinterface'):
                    for sub in intf.subinterface.items():
                        full_name = f"{intf.name}.{sub.index}"
                        if hasattr(sub, 'ipv4') and sub.ipv4.exists():
                            ipv4_node = sub.ipv4.get()
                            if hasattr(ipv4_node, 'address'):
                                for a in ipv4_node.address.items():
                                    if hasattr(a, 'ip_prefix') and a.ip_prefix:
                                        intf_ip_map[full_name] = str(a.ip_prefix)
                                        break
        except Exception:
            pass

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
                                            raw_name = str(iface.interface_name)
                                            intf_disp = format_arista_intf(raw_name, short=False)
                                            cost = getattr(iface, 'interface_cost', 10)
                                            st = str(getattr(iface, 'oper_state', 'down')).upper()
                                            nbrs = getattr(iface, 'neighbor_count', 0)
                                            ip_mask = intf_ip_map.get(raw_name, "--")
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
                            intf = getattr(es, 'interface', '') or '--'
                            domain_id = getattr(bi, 'id', 1)
                            admin_st = getattr(es, 'admin_state', 'enable')
                            oper_st = getattr(es, 'oper_state', 'down')
                            mlag_state = "Active" if (admin_st == "enable" and oper_st == "up") else "Inactive"

                            intf_fmt = format_arista_intf(intf, short=True) if intf != '--' else '--'
                            peer_addr = "--"
                            lines = [
                                "MLAG Configuration:",
                                f"domain-id           : {domain_id}",
                                f"local-interface     : {intf_fmt}",
                                f"peer-address        : {peer_addr}",
                                f"peer-link           : {intf_fmt}",
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
        output.print_line("Try SR Linux command: show system network-instance ethernet-segments")

