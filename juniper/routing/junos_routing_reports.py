#!/usr/bin/python
###########################################################################
# Description: MultiCLI Routing & Protocols Reports for Juniper JUNOS
# Copyright (c) 2025-2026 Nokia
###########################################################################

import datetime
import ipaddress
import re
from srlinux.location import build_path

def format_junos_intf(name, with_unit=True):
    """Format SR Linux interface name to Juniper JUNOS format."""
    if not name:
        return "-"
    name = str(name).strip()
    sub_idx = 0
    if '.' in name:
        base, sub = name.rsplit('.', 1)
        try:
            sub_idx = int(sub)
        except ValueError:
            sub_idx = 0
    else:
        base = name

    if base.startswith('ethernet-'):
        try:
            port_num = int(base.split('-')[1].split('/')[1]) - 1
            j_base = f"et-0/0/{port_num}"
        except Exception:
            j_base = base.replace('ethernet-', 'et-0/0/')
    elif base.startswith('mgmt'):
        j_base = "em0"
    elif base.startswith('system0'):
        j_base = "lo0"
    elif base.startswith('irb'):
        j_base = "irb"
    elif base.startswith('lag'):
        num = base.split('lag')[-1]
        j_base = f"ae{num}"
    else:
        j_base = base

    if with_unit:
        return f"{j_base}.{sub_idx}"
    return j_base

def format_mac_junos(mac):
    """Format MAC to Juniper colon-separated lowercase xx:xx:xx:xx:xx:xx."""
    if not mac:
        return "00:00:00:00:00:00"
    raw = re.sub(r'[^0-9a-fA-F]', '', str(mac)).lower().zfill(12)
    return ":".join(raw[i:i+2] for i in range(0, 12, 2))

class JunosRoutingReports:
    """Handles Juniper JUNOS routing and protocol show commands."""

    def show_arp_no_resolve(self, state, output):
        """Display Juniper JUNOS style 'show arp no-resolve'."""
        lines = [
            f"{'MAC Address':<18} {'Address':<16} {'Interface':<14} {'Flags'}"
        ]
        entries = []
        try:
            path_arpnd = build_path('/interface[name=*]/subinterface[index=*]/ipv4/arp/neighbor[ipv4-address=*]')
            data_arpnd = state.server_data_store.get_data(path_arpnd, recursive=True)
            for intf in data_arpnd.interface.items():
                if hasattr(intf, 'subinterface'):
                    for sub in intf.subinterface.items():
                        if hasattr(sub, 'ipv4') and sub.ipv4.exists():
                            arp = getattr(sub.ipv4.get(), 'arp', None)
                            if arp and hasattr(arp.get(), 'neighbor'):
                                for n in arp.get().neighbor.items():
                                    ip = n.ipv4_address
                                    mac = format_mac_junos(getattr(n, 'link_layer_address', ''))
                                    full_intf = f"{intf.name}.{sub.index}"
                                    j_intf = format_junos_intf(full_intf, with_unit=True)
                                    entries.append((mac, ip, j_intf))
        except Exception:
            pass

        if not entries:
            try:
                path = build_path('/network-instance[name=*]/neighbor[ipv4-address=*]')
                data = state.server_data_store.get_data(path, recursive=True)
                for ni in data.network_instance.items():
                    if hasattr(ni, 'neighbor'):
                        for n in ni.neighbor.items():
                            ip = n.ipv4_address
                            mac = format_mac_junos(getattr(n, 'link_layer_address', ''))
                            intf = format_junos_intf(getattr(n, 'interface', ''), with_unit=True)
                            entries.append((mac, ip, intf))
            except Exception:
                pass

        for mac, ip, intf in entries:
            lines.append(f"{mac:<18} {ip:<16} {intf:<14} none")

        lines.append(f"Total entries: {len(entries)}")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show arpnd arp-entries")

    def show_lldp_neighbors(self, state, output):
        """Display Juniper JUNOS style 'show lldp neighbors'."""
        lines = [
            f"{'Local Interface':<18} {'Parent Interface':<17} {'Chassis Id':<20} {'Port info':<18} {'System Name'}"
        ]
        path = build_path('/system/lldp/interface[name=*]/neighbor[id=*]')
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for iface in data.get_descendants('/system/lldp/interface'):
                local_name = format_junos_intf(getattr(iface, 'name', ''), with_unit=False)
                if hasattr(iface, 'neighbor'):
                    for neigh in iface.neighbor.items():
                        sys_name = getattr(neigh, 'system_name', '') or '-'
                        port_id = format_junos_intf(getattr(neigh, 'port_id', ''), with_unit=False)
                        chassis_id = getattr(neigh, 'chassis_id', '') or '-'
                        lines.append(f"{local_name:<18} {'-':<17} {chassis_id:<20} {port_id:<18} {sys_name}")
        except Exception:
            pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show system lldp neighbor")

    def show_vlans(self, state, output):
        """Display Juniper JUNOS style 'show vlans'."""
        lines = [
            f"{'Routing instance':<23} {'VLAN name':<21} {'Tag':<8} {'Interfaces'}"
        ]
        intfs_by_ni = {}
        try:
            intf_p = build_path('/network-instance[name=*]/interface[name=*]')
            intf_data = state.server_data_store.get_data(intf_p, recursive=False)
            for ni in intf_data.network_instance.items():
                if hasattr(ni, 'interface'):
                    intfs_by_ni[ni.name] = [format_junos_intf(intf.name, with_unit=True) for intf in ni.interface.items()]
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
                intfs = intfs_by_ni.get(name, [])

                vlan_tag = "--"
                for intf in intfs:
                    if '.' in intf:
                        vlan_tag = intf.split('.')[-1]
                        break

                first_intf = intfs[0] if intfs else ""
                lines.append(f"{name:<23} {name:<21} {str(vlan_tag):<8} {first_intf}")
                for extra in intfs[1:]:
                    lines.append(f"{'':<23} {'':<21} {'':<8} {extra}")
        except Exception:
            pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance")

    def show_lacp_interfaces(self, state, output):
        """Display Juniper JUNOS style 'show lacp interfaces'."""
        lines = []
        path = build_path('/interface[name=lag*]')
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for intf in data.interface.items():
                name = intf.name
                ae_name = format_junos_intf(name, with_unit=False)
                lines.append(f"Aggregated interface: {ae_name}")
                lines.append("    LACP state:       Role   Exp   Def  Dist  Col  Syn  Aggr  Timeout  Activity")

                members = []
                if hasattr(intf, 'lag') and intf.lag.exists():
                    lag_node = intf.lag.get()
                    mem_items = []
                    if hasattr(lag_node, 'member'):
                        mem_items = lag_node.member.items()
                    elif hasattr(lag_node, 'member_interface'):
                        mem_items = lag_node.member_interface.items()

                    for mem in mem_items:
                        m_name = format_junos_intf(mem.name, with_unit=False)
                        oper = getattr(mem, 'oper_state', '-')
                        role = "Actor"
                        exp = "No"
                        df = "No"
                        dist = "No"
                        col = "No"
                        syn = "No"
                        aggr = "Yes"
                        timeout = "Fast"
                        activity = "Active" if oper == "up" else "Down"
                        rx_state = "Current" if oper == "up" else "Port disabled"
                        tx_state = "Fast periodic" if oper == "up" else "No periodic"
                        mux_state = "Collecting distributing" if oper == "up" else "Detached"

                        lacp_obj = getattr(mem, 'lacp', None)
                        if lacp_obj:
                            l_node = lacp_obj.get() if hasattr(lacp_obj, 'get') else lacp_obj
                            if hasattr(l_node, 'distributing'):
                                dist = "Yes" if getattr(l_node, 'distributing') else "No"
                            if hasattr(l_node, 'collecting'):
                                col = "Yes" if getattr(l_node, 'collecting') else "No"
                            if hasattr(l_node, 'synchronization'):
                                syn_val = str(getattr(l_node, 'synchronization', '')).lower()
                                syn = "Yes" if "in-sync" in syn_val or "true" in syn_val else "No"
                            if hasattr(l_node, 'aggregatable'):
                                aggr = "Yes" if getattr(l_node, 'aggregatable') else "No"
                            if hasattr(l_node, 'timeout'):
                                t_val = str(getattr(l_node, 'timeout', '')).lower()
                                timeout = "Fast" if "short" in t_val or "fast" in t_val else "Slow"
                            if hasattr(l_node, 'activity'):
                                act_val = str(getattr(l_node, 'activity', '')).capitalize()
                                if act_val:
                                    activity = act_val

                        lines.append(f"      {m_name:<14} {role:<7} {exp:<5} {df:<4} {dist:<5} {col:<4} {syn:<4} {aggr:<5} {timeout:<8} {activity}")
                        members.append((m_name, rx_state, tx_state, mux_state))

                if members:
                    lines.append("    LACP protocol:        Receive State  Transmit State          Mux State")
                    for m_name, rx, tx, mux in members:
                        lines.append(f"      {m_name:<24} {rx:<14} {tx:<23} {mux}")
                lines.append("")
        except Exception:
            pass

        if not lines:
            lines.append("No aggregated interfaces configured.")

        output.print_line("\n".join(lines).rstrip())
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show lag")

    def show_route(self, state, output, network_instance='default'):
        """Display Juniper JUNOS style 'show route' table."""
        path_routes = build_path(f'/network-instance[name={network_instance}]/route-table')
        routes_data = None
        try:
            routes_data = state.server_data_store.get_data(path_routes, recursive=True)
        except Exception:
            pass

        if not routes_data:
            output.print_line(f"error: table {network_instance} not found")
            return

        nh_map = {}
        try:
            for nh in routes_data.get_descendants('/network-instance/route-table/next-hop'):
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
        except Exception:
            pass

        nhg_map = {}
        try:
            for nhg in routes_data.get_descendants('/network-instance/route-table/next-hop-group'):
                nhg_idx = getattr(nhg, 'index', None)
                if nhg_idx is not None and hasattr(nhg, 'next_hop'):
                    hops = []
                    for nh_item in nhg.next_hop.items():
                        target_nh = getattr(nh_item, 'next_hop', None)
                        if target_nh is not None and str(target_nh) in nh_map:
                            hops.append(nh_map[str(target_nh)])
                    nhg_map[str(nhg_idx)] = hops
        except Exception:
            pass

        for nh_info in nh_map.values():
            if not nh_info['interface'] and nh_info.get('resolving_nhg'):
                target_hops = nhg_map.get(nh_info['resolving_nhg'], [])
                for th in target_hops:
                    if th.get('interface'):
                        nh_info['interface'] = th['interface']
                        break

        all_routes = []
        try:
            for r in routes_data.get_descendants('/network-instance/route-table/ipv4-unicast/route'):
                pfx = getattr(r, 'ipv4_prefix', None)
                if not pfx:
                    continue
                rtype = str(getattr(r, 'route_type', '')).lower()
                rowner = str(getattr(r, 'route_owner', '')).lower()
                pref = getattr(r, 'preference', None)
                nhg_id = getattr(r, 'next_hop_group', None)
                hops = nhg_map.get(str(nhg_id), []) if nhg_id is not None else []

                # Format protocol and preference
                if 'connected' in rowner or (rtype == 'local' and 'host' not in rtype):
                    proto_name = 'Direct'
                    default_pref = 0
                elif 'host' in rtype or 'local' in rowner:
                    proto_name = 'Local'
                    default_pref = 0
                elif 'bgp' in rtype or 'bgp' in rowner:
                    proto_name = 'BGP'
                    default_pref = 170
                elif 'static' in rtype or 'static' in rowner:
                    proto_name = 'Static'
                    default_pref = 5
                elif 'ospf' in rtype or 'ospf' in rowner:
                    proto_name = 'OSPF'
                    default_pref = 10
                elif 'isis' in rtype or 'isis' in rowner:
                    proto_name = 'IS-IS'
                    default_pref = 15
                else:
                    proto_name = rowner.capitalize() if rowner else 'Direct'
                    default_pref = 0

                pref_val = pref if (pref is not None and pref > 0) else default_pref

                # Calculate uptime
                uptime_str = ""
                if hasattr(r, 'last_app_update') and r.last_app_update:
                    try:
                        ts_str = str(r.last_app_update).split(' (')[0].strip()
                        if 'Z' in ts_str:
                            ts_str = ts_str.replace('Z', '+00:00')
                        dt = datetime.datetime.fromisoformat(ts_str)
                        now = datetime.datetime.now(datetime.timezone.utc)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=datetime.timezone.utc)
                        sec = max(0, int((now - dt).total_seconds()))
                        d, rem = divmod(sec, 86400)
                        h, rem = divmod(rem, 3600)
                        m, s = divmod(rem, 60)
                        if d > 0:
                            uptime_str = f"{d}d {h:02d}:{m:02d}:{s:02d}"
                        else:
                            uptime_str = f"{h:02d}:{m:02d}:{s:02d}"
                    except Exception:
                        uptime_str = ""

                intf_val = hops[0].get('interface') if (hops and hops[0].get('interface')) else None

                all_routes.append({
                    'prefix': str(pfx),
                    'proto': proto_name,
                    'pref': pref_val,
                    'uptime': uptime_str,
                    'hops': hops,
                    'interface': intf_val,
                })
        except Exception:
            pass

        try:
            all_routes = sorted(all_routes, key=lambda x: int(ipaddress.ip_network(x['prefix']).network_address))
        except Exception:
            pass

        tbl_name = f"{network_instance}.0" if network_instance != 'default' else "inet.0"
        total = len(all_routes)
        lines = [
            f"{tbl_name}: {total} destinations, {total} routes ({total} active, 0 holddown, 0 hidden)",
            "+ = Active Route, - = Last Active, * = Both",
            ""
        ]

        for rt in all_routes:
            prefix = rt['prefix']
            tag = f"*[{rt['proto']}/{rt['pref']}]"
            up = f" {rt['uptime']}" if rt['uptime'] else ""
            lines.append(f"{prefix:<20}{tag}{up}")

            if rt['proto'] == 'Local':
                intf_str = format_junos_intf(rt['interface']) if rt['interface'] else "lo0.0"
                lines.append(f"                      Local via {intf_str}")
            elif rt['proto'] == 'Direct':
                intf_str = format_junos_intf(rt['interface']) if rt['interface'] else "-"
                lines.append(f"                    > via {intf_str}")
            elif rt['hops']:
                for h in rt['hops']:
                    h_ip = h.get('ip')
                    h_intf = format_junos_intf(h.get('interface')) if h.get('interface') else None
                    if h_ip and h_intf and h_intf != "-":
                        lines.append(f"                    > to {h_ip} via {h_intf}")
                    elif h_ip:
                        lines.append(f"                    > to {h_ip}")
                    elif h_intf and h_intf != "-":
                        lines.append(f"                    > via {h_intf}")
            else:
                lines.append("                    Receive")

        output.print_line("\n".join(lines).rstrip())
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line(f"Try SR Linux command: show network-instance {network_instance} route-table")

    def show_route_summary(self, state, output):
        """Display Juniper JUNOS style 'show route summary'."""
        asn = "--"
        router_id = "--"

        # Query BGP AS and router ID
        try:
            path_ni = build_path('/network-instance[name=default]')
            data_ni = state.server_data_store.get_data(path_ni, recursive=False)
            for ni in data_ni.network_instance.items():
                if hasattr(ni, 'router_id') and ni.router_id:
                    router_id = str(ni.router_id)
        except Exception:
            pass

        try:
            path_bgp = build_path('/network-instance[name=default]/protocols/bgp')
            data_bgp = state.server_data_store.get_data(path_bgp, recursive=False)
            for ni in data_bgp.network_instance.items():
                if hasattr(ni, 'protocols') and ni.protocols.exists():
                    bgp = getattr(ni.protocols.get(), 'bgp', None)
                    if bgp:
                        b_node = bgp.get() if hasattr(bgp, 'get') else bgp
                        if hasattr(b_node, 'autonomous_system') and b_node.autonomous_system:
                            asn = str(b_node.autonomous_system)
        except Exception:
            pass

        # Query route table
        direct_count = 0
        local_count = 0
        bgp_count = 0
        static_count = 0
        ospf_count = 0
        isis_count = 0
        total_routes = 0

        path_routes = build_path('/network-instance[name=default]/route-table/ipv4-unicast/route[ipv4-prefix=*]')
        try:
            data_routes = state.server_data_store.get_data(path_routes, recursive=False)
            for r in data_routes.get_descendants('/network-instance/route-table/ipv4-unicast/route'):
                total_routes += 1
                rtype = str(getattr(r, 'route_type', '')).lower()
                rowner = str(getattr(r, 'route_owner', '')).lower()
                if 'connected' in rowner or 'direct' in rowner or rtype == 'local':
                    direct_count += 1
                elif 'host' in rtype or 'local' in rowner:
                    local_count += 1
                elif 'bgp' in rtype or 'bgp' in rowner:
                    bgp_count += 1
                elif 'static' in rtype or 'static' in rowner:
                    static_count += 1
                elif 'ospf' in rtype or 'ospf' in rowner:
                    ospf_count += 1
                elif 'isis' in rtype or 'isis' in rowner:
                    isis_count += 1
                else:
                    direct_count += 1
        except Exception:
            pass

        lines = [
            f"Autonomous system number: {asn}",
            f"Router ID: {router_id}\n",
            f"inet.0: {total_routes} destinations, {total_routes} routes ({total_routes} active, 0 holddown, 0 hidden)",
            f"{'Direct:':>20} {direct_count:>10} routes, {direct_count:>10} active",
            f"{'Local:':>20} {local_count:>10} routes, {local_count:>10} active",
            f"{'BGP:':>20} {bgp_count:>10} routes, {bgp_count:>10} active",
            f"{'Static:':>20} {static_count:>10} routes, {static_count:>10} active",
            f"{'OSPF:':>20} {ospf_count:>10} routes, {ospf_count:>10} active",
            f"{'IS-IS:':>20} {isis_count:>10} routes, {isis_count:>10} active"
        ]

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance default route-table")

    def show_bgp_summary(self, state, output):
        """Display Juniper JUNOS style 'show bgp summary'."""
        lines = []
        path = build_path('/network-instance[name=*]/protocols/bgp/neighbor[peer-address=*]')
        peers = []
        peer_groups = set()
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for n in data.get_descendants('/network-instance/protocols/bgp/neighbor'):
                peer_ip = getattr(n, 'peer_address', '-')
                peer_as = getattr(n, 'peer_as', '--')
                oper = getattr(n, 'session_state', '--')
                state_str = str(oper).capitalize() if oper else '--'
                pg = getattr(n, 'peer_group', None)
                if pg:
                    peer_groups.add(str(pg))

                in_pkts = "--"
                recv = getattr(n, 'received_messages', None)
                if recv:
                    node = recv.get() if hasattr(recv, 'get') else recv
                    val = getattr(node, 'total_messages', None)
                    if val is not None:
                        in_pkts = str(val)

                out_pkts = "--"
                out_q = "0"
                sent = getattr(n, 'sent_messages', None)
                if sent:
                    node = sent.get() if hasattr(sent, 'get') else sent
                    val = getattr(node, 'total_messages', None)
                    if val is not None:
                        out_pkts = str(val)
                    qd = getattr(node, 'queue_depth', None)
                    if qd is not None:
                        out_q = str(qd)

                uptime = getattr(n, 'last_established', '--')
                if '(' in str(uptime):
                    uptime = str(uptime).split('(')[-1].rstrip(')')
                flaps = getattr(n, 'established_transitions', '0')
                peers.append({
                    'peer_ip': peer_ip,
                    'peer_as': peer_as,
                    'in_pkts': in_pkts,
                    'out_pkts': out_pkts,
                    'out_q': out_q,
                    'flaps': flaps,
                    'uptime': uptime,
                    'state': state_str
                })
        except Exception:
            pass

        # Query configured peer-groups if available
        try:
            pg_path = build_path('/network-instance[name=*]/protocols/bgp/peer-group[peer-group-name=*]')
            pg_data = state.server_data_store.get_data(pg_path, recursive=False)
            for g in pg_data.get_descendants('/network-instance/protocols/bgp/peer-group'):
                gname = getattr(g, 'peer_group_name', None)
                if gname:
                    peer_groups.add(str(gname))
        except Exception:
            pass

        num_groups = len(peer_groups) if peer_groups else (1 if peers else 0)

        # Query route counts for active tables
        tables = []
        pfx_count = 0
        try:
            rt_path = build_path('/network-instance[name=default]/route-table/ipv4-unicast/route[ipv4-prefix=*]')
            rt_data = state.server_data_store.get_data(rt_path, recursive=False)
            pfx_count = len(list(rt_data.get_descendants('/network-instance/route-table/ipv4-unicast/route')))
        except Exception:
            pass
        tables.append(("inet.0", pfx_count))

        try:
            rt6_path = build_path('/network-instance[name=default]/route-table/ipv6-unicast/route[ipv6-prefix=*]')
            rt6_data = state.server_data_store.get_data(rt6_path, recursive=False)
            pfx6_count = len(list(rt6_data.get_descendants('/network-instance/route-table/ipv6-unicast/route')))
            if pfx6_count > 0:
                tables.append(("inet6.0", pfx6_count))
        except Exception:
            pass

        down_peers = sum(1 for p in peers if p['state'].lower() != 'established')
        lines.append(f"Groups: {num_groups} Peers: {len(peers)} Down peers: {down_peers}")
        lines.append("Table          Tot Paths  Act Paths Suppressed    History Damp State    Pending")
        for t_name, t_cnt in tables:
            lines.append(f"{t_name:<14} {t_cnt:<10} {t_cnt:<10} 0          0          0          0")
        lines.append(f"{'Peer':<24} {'AS':<7} {'InPkt':<9} {'OutPkt':<10} {'OutQ':<6} {'Flaps':<5} {'Last Up/Down':<12} {'State'}")

        for p in peers:
            lines.append(f"{p['peer_ip']:<24} {str(p['peer_as']):<7} {str(p['in_pkts']):<9} {str(p['out_pkts']):<10} {str(p.get('out_q', '0')):<6} {str(p['flaps']):<5} {str(p['uptime']):<12} {p['state']}")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance default protocols bgp neighbor")

    def show_ospf_neighbor(self, state, output):
        """Display Juniper JUNOS style 'show ospf neighbor'."""
        lines = [
            f"{'Address':<16} {'Interface':<23} {'State':<9} {'ID':<16} {'Pri':<4} {'Dead'}"
        ]
        path = build_path('/network-instance[name=*]/protocols/ospf/instance[name=*]/area[area-id=*]/interface[interface-name=*]/neighbor[router-id=*]')
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for ni in data.network_instance.items():
                if hasattr(ni, 'protocols') and ni.protocols.exists():
                    ospf = getattr(ni.protocols.get(), 'ospf', None)
                    if ospf and hasattr(ospf.get(), 'instance'):
                        for inst in ospf.get().instance.items():
                            if hasattr(inst, 'area'):
                                for area in inst.area.items():
                                    if hasattr(area, 'interface'):
                                        for intf in area.interface.items():
                                            intf_name = format_junos_intf(intf.interface_name, with_unit=True)
                                            if hasattr(intf, 'neighbor'):
                                                for n in intf.neighbor.items():
                                                    r_id = getattr(n, 'router_id', '--')
                                                    adj_st = getattr(n, 'adjacency_state', None)
                                                    n_state = str(adj_st).split(':')[-1].capitalize() if adj_st else '--'
                                                    ip = getattr(n, 'address', '--')
                                                    pri = getattr(n, 'priority', '--')
                                                    dead = getattr(n, 'dead_time', '--')
                                                    lines.append(f"{str(ip):<16} {intf_name:<23} {n_state:<9} {str(r_id):<16} {str(pri):<4} {str(dead)}")
        except Exception:
            pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance <instance> protocols ospf neighbor")

    def show_isis_adjacency(self, state, output):
        """Display Juniper JUNOS style 'show isis adjacency'."""
        lines = [
            f"{'Interface':<21} {'System':<14} {'L':<2} {'State':<13} {'Hold (secs)':<12} {'SNPA'}"
        ]
        path = build_path('/network-instance[name=*]/protocols/isis/instance[name=*]/interface[interface-name=*]/adjacency[neighbor-system-id=*][adjacency-level=*]')
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for ni in data.network_instance.items():
                if hasattr(ni, 'protocols') and ni.protocols.exists():
                    isis = getattr(ni.protocols.get(), 'isis', None)
                    if isis and hasattr(isis.get(), 'instance'):
                        for inst in isis.get().instance.items():
                            if hasattr(inst, 'interface'):
                                for iface in inst.interface.items():
                                    intf = format_junos_intf(iface.interface_name, with_unit=True)
                                    if hasattr(iface, 'adjacency'):
                                        for adj in iface.adjacency.items():
                                            sys_id = getattr(adj, 'neighbor_hostname', None) or getattr(adj, 'neighbor_system_id', '-')
                                            level = str(getattr(adj, 'adjacency_level', '2'))
                                            raw_st = getattr(adj, 'state', '--')
                                            oper = str(raw_st).split(':')[-1].capitalize() if raw_st else '--'
                                            hold = str(getattr(adj, 'remaining_holdtime', '--'))
                                            snpa_raw = getattr(adj, 'neighbor_snpa', None)
                                            snpa = format_mac_junos(snpa_raw) if snpa_raw else '--'
                                            lines.append(f"{intf:<21} {str(sys_id):<14} {level:<2} {oper:<13} {hold:<12} {snpa}")
        except Exception:
            pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance <instance> protocols isis adjacency")
