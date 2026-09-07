#!/usr/bin/python
###########################################################################
# Description: MultiCLI Routing & Protocols Reports for Juniper JUNOS
# Copyright (c) 2025-2026 Nokia
###########################################################################

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
        path = build_path('/network-instance[name=*]')
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for ni in sorted(data.network_instance.items(), key=lambda x: str(x.name)):
                ni_type = getattr(ni, 'type', '')
                if ni_type != 'mac-vrf':
                    continue
                name = ni.name
                intfs = []
                if hasattr(ni, 'interface'):
                    for intf in ni.interface.items():
                        intfs.append(format_junos_intf(intf.name, with_unit=True))

                vlan_tag = "--"
                for intf in intfs:
                    if '.' in intf:
                        vlan_tag = intf.split('.')[-1]
                        break

                first_intf = intfs[0] if intfs else ""
                lines.append(f"{'default':<23} {name:<21} {str(vlan_tag):<8} {first_intf}")
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
                    if hasattr(lag_node, 'member_interface'):
                        for mem in lag_node.member_interface.items():
                            m_name = format_junos_intf(mem.name, with_unit=False)
                            members.append(m_name)
                            oper = getattr(mem, 'oper_state', '-')
                            active_str = "Active" if oper == "up" else "Down"
                            lines.append(f"      {m_name:<14} Actor    --    --   --   --   --    --      --      {active_str}")

                lines.append("    LACP protocol:        Receive State  Transmit State          Mux State")
                for m in members:
                    lines.append(f"      {m:<24} Current   --                      --")
                lines.append("")
        except Exception:
            pass

        if not lines:
            lines.append("No aggregated interfaces configured.")

        output.print_line("\n".join(lines).rstrip())
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show lag")

    def show_route_summary(self, state, output):
        """Display Juniper JUNOS style 'show route summary'."""
        asn = "--"
        router_id = "--"

        # Query BGP AS and router ID
        path_ni = build_path('/network-instance[name=default]')
        try:
            data_ni = state.server_data_store.get_data(path_ni, recursive=True)
            for ni in data_ni.network_instance.items():
                if hasattr(ni, 'router_id') and ni.router_id:
                    router_id = str(ni.router_id)
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
        total_routes = 0

        path_routes = build_path('/network-instance[name=default]/route-table/ipv4-unicast/route[ipv4-prefix=*]')
        try:
            data_routes = state.server_data_store.get_data(path_routes, recursive=True)
            for r in data_routes.get_descendants('/network-instance/route-table/ipv4-unicast/route'):
                owner = getattr(r, 'route_owner', getattr(r, 'route_type', 'connected')).lower()
                total_routes += 1
                if 'connected' in owner or 'direct' in owner:
                    direct_count += 1
                elif 'local' in owner:
                    local_count += 1
                elif 'bgp' in owner:
                    bgp_count += 1
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
            f"{'BGP:':>20} {bgp_count:>10} routes, {bgp_count:>10} active"
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

        # Query route count for inet.0
        pfx_count = 0
        try:
            rt_path = build_path('/network-instance[name=default]/route-table/ipv4-unicast/route[ipv4-prefix=*]')
            rt_data = state.server_data_store.get_data(rt_path, recursive=False)
            pfx_count = len(list(rt_data.get_descendants('/network-instance/route-table/ipv4-unicast/route')))
        except Exception:
            pass

        down_peers = sum(1 for p in peers if p['state'].lower() != 'established')
        lines.append(f"Groups: {num_groups} Peers: {len(peers)} Down peers: {down_peers}")
        lines.append("Table          Tot Paths  Act Paths Suppressed    History Damp State    Pending")
        lines.append(f"inet.0                 {pfx_count:<10} {pfx_count:<10} 0          0          0          0")
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
                                    intf_name = format_junos_intf(intf.interface_name, with_unit=True)
                                    if hasattr(intf, 'neighbor'):
                                        for n in intf.neighbor.items():
                                            r_id = getattr(n, 'router_id', '--')
                                            n_state = getattr(n, 'oper_state', '--').capitalize()
                                            ip = getattr(n, 'ipv4_address', '--')
                                            pri = getattr(n, 'priority', '--')
                                            lines.append(f"{ip:<16} {intf_name:<23} {n_state:<9} {r_id:<16} {str(pri):<4} --")
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
        path = build_path('/network-instance[name=*]/protocols/isis/instance[name=*]/adjacency[interface=*]')
        try:
            data = state.server_data_store.get_data(path, recursive=True)
            for adj in data.get_descendants('/network-instance/protocols/isis/instance/adjacency'):
                intf = format_junos_intf(getattr(adj, 'interface', ''), with_unit=True)
                sys_id = getattr(adj, 'system_id', '-') or '-'
                level = getattr(adj, 'level', '2')
                oper = getattr(adj, 'oper_state', '--').capitalize()
                hold = getattr(adj, 'remaining_hold_time', '--') or '--'
                lines.append(f"{intf:<21} {sys_id:<14} {str(level):<2} {oper:<13} {str(hold):<12}")
        except Exception:
            pass

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show network-instance <instance> protocols isis adjacency")
