#!/usr/bin/python
###########################################################################
# Description: MultiCLI Plugin for Arista EOS Commands
# Copyright (c) 2025-2026 Nokia
###########################################################################

import srlinux.schema.schema_syntax_builder
from srlinux.mgmt.cli import CliPlugin, KeyCompleter, RequiredPlugin
from srlinux.syntax import Syntax
from srlinux.location import build_path
import sys
import os

potential_paths = [
    '/etc/opt/srlinux/cli',
    os.path.expanduser('~/cli'),
    '/home/auser/cli',
    '/home/admin/cli',
    '/home/srlinux/cli',
]
if globals().get('__file__'):
    cand = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    potential_paths.insert(0, cand)

import_base = None
for path in potential_paths:
    if os.path.exists(path) and (
        os.path.exists(os.path.join(path, 'system')) or
        os.path.exists(os.path.join(path, 'interface')) or
        os.path.exists(os.path.join(path, 'ip'))
    ):
        import_base = path
        break

if import_base is None:
    raise ImportError("Could not find a valid CLI plugin base directory")

for subdir in ["ip", "bgp", "interface", "system", "routing"]:
    sub_path = os.path.join(import_base, subdir)
    if os.path.exists(sub_path) and sub_path not in sys.path:
        sys.path.insert(0, sub_path)

try:
    from ip_bgp_report import IpBgpReport as BaseBgpReport
    from bgp_evpn_report import IpBgpReport as EvpnBgpReport
    from arista_interface_detail import InterfaceDetails
    from arista_interface_status import InterfaceStatus
    from arista_arp_details import ArpDetails

    from arista_system_reports import AristaSystemReports
    from arista_interface_reports import AristaInterfaceReports
    from arista_routing_reports import AristaRoutingReports
except Exception:
    raise

class Plugin(CliPlugin):

    def get_required_plugins(self):
        return [
            RequiredPlugin('version', module='srlinux'),
        ]

    def load(self, cli, **_kwargs):
        # 1. System Commands: version, hostname, clock, inventory, environment
        ver_node = cli.show_mode.root.get_command_or_none('version')
        if ver_node:
            ver_node.set_callback(self._print_version)
        else:
            cli.show_mode.add_command(
                Syntax('version', help='Show system version in Arista EOS format'),
                callback=self._print_version
            )

        cli.show_mode.add_command(
            Syntax('hostname', help='Show system hostname'),
            callback=self._print_hostname
        )

        cli.show_mode.add_command(
            Syntax('clock', help='Show system clock in Arista EOS format'),
            callback=self._print_clock
        )

        cli.show_mode.add_command(
            Syntax('inventory', help='Show system hardware inventory'),
            callback=self._print_inventory
        )

        env_cmd = cli.show_mode.add_command(
            Syntax('environment', help='Show environment status'),
            callback=self._print_environment_all
        )
        env_cmd.add_command(
            Syntax('cooling', help='Show cooling status'),
            callback=self._print_environment_cooling
        )
        env_cmd.add_command(
            Syntax('power', help='Show power supply status'),
            callback=self._print_environment_power
        )
        env_cmd.add_command(
            Syntax('temperature', help='Show temperature status'),
            callback=self._print_environment_temp
        )

        cli.show_mode.add_command(
            Syntax('module', help='Show module information in Arista EOS format'),
            callback=self._print_module
        )

        proc_cmd = cli.show_mode.add_command(
            Syntax('processes', help='Show process information in Arista EOS format')
        )
        proc_top = proc_cmd.add_command(
            Syntax('top', help='Show top processes')
        )
        proc_top.add_command(
            Syntax('once', help='Show top processes once'),
            callback=self._print_processes_top_once
        )

        cli.show_mode.add_command(
            Syntax('mlag', help='Show MLAG information in Arista EOS format'),
            callback=self._print_mlag
        )

        # 2. IP Commands: show ip bgp, show ip route, show ip interface brief, show ip arp, show ip ospf
        ip = cli.show_mode.root.get_command_or_none('ip')
        if not ip:
            ip = cli.show_mode.add_command(Syntax('ip', help='display ip protocol information'), update_location=True)

        bgp = ip.add_command(
            Syntax('bgp', help='show bgp information'),
            update_location=True
        )
        bgp.add_command(
            Syntax('summary')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]')),
            callback=self._print_summary
        )

        # IP Route
        ip_route = ip.add_command(
            Syntax('route', help='IP routing table'),
            callback=self._print_ip_route
        )
        ip_route.add_command(
            Syntax('vrf').add_unnamed_argument('vrf_name', suggestions=KeyCompleter('/network-instance[name=*]')),
            callback=self._print_vrf_route,
            update_location=False
        )

        # IP Interface Brief
        ip_intf = ip.get_command_or_none('interface')
        if not ip_intf:
            ip_intf = ip.add_command(Syntax('interface', help='IP interface information'))
        ip_intf.add_command(
            Syntax('brief', help='IP interface brief'),
            callback=self._print_ip_interface_brief,
            update_location=False
        )

        # IP ARP
        ip.add_command(
            Syntax('arp', help='IP ARP table'),
            callback=self._print_ip_arp
        )

        # IP OSPF
        ip_ospf = ip.add_command(Syntax('ospf', help='IP OSPF information'))
        ip_ospf.add_command(
            Syntax('neighbor', help='OSPF neighbors'),
            callback=self._print_ospf_neighbor
        )
        ospf_intf = ip_ospf.add_command(Syntax('interface', help='OSPF interface information'))
        ospf_intf.add_command(
            Syntax('brief', help='OSPF interface brief'),
            callback=self._print_ospf_interface_brief
        )

        # 3. EVPN Commands
        bgp_root = cli.show_mode.root.get_command_or_none('bgp')
        if not bgp_root:
            bgp_root = cli.show_mode.add_command(Syntax('bgp', help='display bgp information'), update_location=True)

        evpn = bgp_root.add_command(
            Syntax('evpn', help='show EVPN information'),
            update_location=True
        )
        evpn.add_command(
            Syntax('summary')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]')),
            callback=self._print_evpn_summary
        )
        route_type = evpn.add_command(Syntax('route-type', help='specify the EVPN route type'))
        route_type.add_command(
            Syntax('auto-discovery')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]'))
            .add_named_argument('esi', default='*', help='ESI value'),
            callback=self._print_1
        )
        route_type.add_command(
            Syntax('mac-ip')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]'))
            .add_named_argument('mac-address', default='*', help='MAC address'),
            callback=self._print_2
        )
        route_type.add_command(
            Syntax('imet')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]'))
            .add_named_argument('origin-router', default='*', help='Originating router IPv4 or IPv6 address'),
            callback=self._print_3
        )
        route_type.add_command(
            Syntax('ethernet-segment')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]'))
            .add_named_argument('esi', default='*', help='ESI value'),
            callback=self._print_4
        )
        route_type.add_command(
            Syntax('ip-prefix')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]'))
            .add_named_argument('ip-address', default='*', help='IPv4 or IPv6 address prefix'),
            callback=self._print_5
        )

        # 4. Interfaces Commands: show interfaces status, description, detail
        intfs = cli.show_mode.root.get_command_or_none('interfaces')
        if not intfs:
            intfs = cli.show_mode.add_command(Syntax('interfaces', help='Interface status and information'), update_location=True)
        intfs.add_command(
            InterfaceStatus().get_syntax_status(),
            update_location=True,
            callback=self._interface_status,
            schema=InterfaceStatus().get_data_schema()
        )
        intfs.add_command(
            Syntax('description', help='Interface descriptions'),
            callback=self._print_interfaces_description
        )
        intfs_xcvr = intfs.add_command(
            Syntax('transceiver', help='Transceiver and DDM status in Arista EOS format'),
            callback=self._print_interfaces_transceiver
        )
        intfs_xcvr.add_command(
            Syntax('detail', help='Transceiver detail'),
            callback=self._print_interfaces_transceiver_detail
        )

        # Also support on 'interface' singular
        intf_singular = cli.show_mode.root.get_command_or_none('interface')
        if intf_singular:
            intf_status_existing = intf_singular.get_command_or_none('status')
            if not intf_status_existing:
                intf_singular.add_command(
                    InterfaceStatus().get_syntax_status(),
                    update_location=True,
                    callback=self._interface_status,
                    schema=InterfaceStatus().get_data_schema()
                )
            intf_desc_existing = intf_singular.get_command_or_none('description')
            if not intf_desc_existing:
                intf_singular.add_command(
                    Syntax('description', help='Interface descriptions'),
                    callback=self._print_interfaces_description
                )
            intf_xcvr_existing = intf_singular.get_command_or_none('transceiver')
            if not intf_xcvr_existing:
                s_xcvr = intf_singular.add_command(
                    Syntax('transceiver', help='Transceiver and DDM status in Arista EOS format'),
                    callback=self._print_interfaces_transceiver
                )
                s_xcvr.add_command(
                    Syntax('detail', help='Transceiver detail'),
                    callback=self._print_interfaces_transceiver_detail
                )

        # 5. LLDP Commands
        lldp_node = cli.show_mode.root.get_command_or_none('lldp')
        if not lldp_node:
            lldp_node = cli.show_mode.add_command(Syntax('lldp', help='LLDP information'))
        lldp_neigh = lldp_node.add_command(
            Syntax('neighbors', help='LLDP neighbors in Arista format'),
            callback=self._print_lldp_neighbors
        )
        lldp_neigh.add_command(
            Syntax('detail', help='LLDP neighbors detail'),
            callback=self._print_lldp_neighbors_detail
        )

        # 6. MAC Table Commands
        mac_node = cli.show_mode.root.get_command_or_none('mac')
        if not mac_node:
            mac_node = cli.show_mode.add_command(Syntax('mac', help='MAC information'))
        mac_node.add_command(
            Syntax('address-table', help='MAC address table'),
            callback=self._print_mac_address_table
        )

        # 7. VRF & VLAN Commands
        cli.show_mode.add_command(
            Syntax('vrf', help='VRF information in Arista format'),
            callback=self._print_vrf
        )
        cli.show_mode.add_command(
            Syntax('vlan', help='VLAN information in Arista format'),
            callback=self._print_vlan
        )

        # 8. Port-Channel Commands
        pc_node = cli.show_mode.root.get_command_or_none('port-channel')
        if not pc_node:
            pc_node = cli.show_mode.add_command(Syntax('port-channel', help='Port-Channel information'))
        pc_node.add_command(
            Syntax('summary', help='Port-Channel summary in Arista format'),
            callback=self._print_port_channel_summary
        )

        # 9. IS-IS Commands
        isis_node = cli.show_mode.root.get_command_or_none('isis')
        if not isis_node:
            isis_node = cli.show_mode.add_command(Syntax('isis', help='IS-IS information'))
        isis_node.add_command(
            Syntax('neighbors', help='IS-IS neighbors in Arista format'),
            callback=self._print_isis_neighbors
        )

        # 10. Legacy 'show eos ...' container preserved for compatibility
        eos_node = cli.show_mode.root.get_command_or_none('eos')
        if not eos_node:
            eos_node = cli.show_mode.add_command(Syntax('eos', help='Show Arista EOS reports'))
        eos_interfaces = eos_node.add_command(
            InterfaceDetails().get_syntax_details(),
            update_location=True,
            callback=self._interface_details
        )
        eos_interfaces.add_command(
            InterfaceStatus().get_syntax_status(),
            update_location=True,
            callback=self._interface_status,
            schema=InterfaceStatus().get_data_schema()
        )
        eos_node.add_command(
            ArpDetails()._get_syntax_arp(),
            update_location=True,
            callback=self._arp_entries,
            schema=ArpDetails()._get_arp_schema(True)
        )

    # Callbacks
    def _print_version(self, state, output, **_kwargs):
        AristaSystemReports().show_version(state, output)

    def _print_hostname(self, state, output, **_kwargs):
        AristaSystemReports().show_hostname(state, output)

    def _print_clock(self, state, output, **_kwargs):
        AristaSystemReports().show_clock(state, output)

    def _print_inventory(self, state, output, **_kwargs):
        AristaSystemReports().show_inventory(state, output)

    def _print_environment_all(self, state, output, **_kwargs):
        if state.is_intermediate_command:
            return
        AristaSystemReports().show_environment(state, output, 'all')

    def _print_environment_cooling(self, state, output, **_kwargs):
        AristaSystemReports().show_environment(state, output, 'cooling')

    def _print_environment_power(self, state, output, **_kwargs):
        AristaSystemReports().show_environment(state, output, 'power')

    def _print_environment_temp(self, state, output, **_kwargs):
        AristaSystemReports().show_environment(state, output, 'temperature')

    def _print_ip_route(self, state, output, **_kwargs):
        if state.is_intermediate_command:
            return
        AristaRoutingReports().show_ip_route(state, output, vrf='default')

    def _print_vrf_route(self, state, arguments, output, **_kwargs):
        vrf_name = arguments.get('vrf_name') or 'default'
        AristaRoutingReports().show_ip_route(state, output, vrf=vrf_name)

    def _print_ip_interface_brief(self, state, output, **_kwargs):
        AristaInterfaceReports().show_ip_interface_brief(state, output)

    def _print_interfaces_description(self, state, output, **_kwargs):
        AristaInterfaceReports().show_interfaces_description(state, output)

    def _print_ip_arp(self, state, output, **_kwargs):
        AristaInterfaceReports().show_ip_arp(state, output)

    def _print_ospf_neighbor(self, state, output, **_kwargs):
        AristaRoutingReports().show_ip_ospf_neighbor(state, output)

    def _print_isis_neighbors(self, state, output, **_kwargs):
        AristaRoutingReports().show_isis_neighbors(state, output)

    def _print_lldp_neighbors(self, state, output, **_kwargs):
        if state.is_intermediate_command:
            return
        AristaInterfaceReports().show_lldp_neighbors(state, output, detail=False)

    def _print_lldp_neighbors_detail(self, state, output, **_kwargs):
        AristaInterfaceReports().show_lldp_neighbors(state, output, detail=True)

    def _print_mac_address_table(self, state, output, **_kwargs):
        AristaRoutingReports().show_mac_address_table(state, output)

    def _print_vrf(self, state, output, **_kwargs):
        AristaRoutingReports().show_vrf(state, output)

    def _print_vlan(self, state, output, **_kwargs):
        AristaRoutingReports().show_vlan(state, output)

    def _print_port_channel_summary(self, state, output, **_kwargs):
        AristaInterfaceReports().show_port_channel_summary(state, output)

    def _print_summary(self, state, arguments, output, **_kwargs):
        netinst = arguments.get('summary', 'vrf') if arguments.has_node('summary') else 'default'
        BaseBgpReport().show_bgp_summary(state, output, network_instance=netinst)
        output.print_line("-" * 100)
        output.print_line(f'Try SR Linux command: show network-instance {netinst} protocols bgp neighbor')

    def _print_evpn_summary(self, state, arguments, output, **_kwargs):
        netinst = arguments.get('summary', 'vrf') if arguments.has_node('summary') else 'default'
        EvpnBgpReport().show_bgp_summary(state, output, network_instance=netinst)
        output.print_line("-" * 100)
        output.print_line(f'Try SR Linux command: show network-instance {netinst} protocols bgp neighbor')

    def _print_1(self, state, arguments, output, **_kwargs):
        netinst = arguments.get('auto-discovery', 'vrf')
        esi_input = arguments.get('auto-discovery', 'esi')
        EvpnBgpReport().show_evpn_rt1(state, output, network_instance=netinst, esi_value=esi_input)
        output.print_line("-" * 100)
        output.print_line('Try SR Linux command: show network-instance default protocols bgp routes evpn route-type 1 summary')

    def _print_2(self, state, arguments, output, **_kwargs):
        netinst = arguments.get('mac-ip', 'vrf')
        mac_input = arguments.get('mac-ip', 'mac-address')
        EvpnBgpReport().show_evpn_rt2(state, output, network_instance=netinst, mac_value=mac_input)
        output.print_line("-" * 100)
        output.print_line('Try SR Linux command: show network-instance default protocols bgp routes evpn route-type 2 summary')

    def _print_3(self, state, arguments, output, **_kwargs):
        netinst = arguments.get('imet', 'vrf')
        originr_input = arguments.get('imet', 'origin-router')
        EvpnBgpReport().show_evpn_rt3(state, output, network_instance=netinst, originr_value=originr_input)
        output.print_line("-" * 100)
        output.print_line('Try SR Linux command: show network-instance default protocols bgp routes evpn route-type 3 summary')

    def _print_4(self, state, arguments, output, **_kwargs):
        netinst = arguments.get('ethernet-segment', 'vrf')
        esi4_input = arguments.get('ethernet-segment', 'esi')
        EvpnBgpReport().show_evpn_rt4(state, output, network_instance=netinst, esi4_value=esi4_input)
        output.print_line("-" * 100)
        output.print_line('Try SR Linux command: show network-instance default protocols bgp routes evpn route-type 4 summary')

    def _print_5(self, state, arguments, output, **_kwargs):
        netinst = arguments.get('ip-prefix', 'vrf')
        ip_input = arguments.get('ip-prefix', 'ip-address')
        EvpnBgpReport().show_evpn_rt5(state, output, network_instance=netinst, ip_value=ip_input)
        output.print_line("-" * 100)
        output.print_line('Try SR Linux command: show network-instance default protocols bgp routes evpn route-type 5 summary')

    def _interface_details(self, state, arguments, output, **_kwargs):
        if state.is_intermediate_command:
            return
        InterfaceDetails().print(state, arguments, output, **_kwargs)
        msg = 'Try SR Linux command: show interface {interface_name} detail'
        output.print_line(f'\n{"-" * len(msg)}\n{msg}')

    def _interface_status(self, state, arguments, output, **_kwargs):
        if state.is_intermediate_command:
            return
        InterfaceStatus().print(state, arguments, output)
        msg = 'Try SR Linux command: show interface {interface_name} brief'
        output.print_line(f'\n{"-" * len(msg)}\n{msg}')

    def _arp_entries(self, state, arguments, output, **_kwargs):
        if state.is_intermediate_command:
            return
        ArpDetails().print(state, arguments, output)
        msg = 'Try SR Linux command: show arpnd arp-entries'
        output.print_line(f'\n{"-" * len(msg)}\n{msg}')

    def _print_interfaces_transceiver(self, state, output, **_kwargs):
        if state.is_intermediate_command:
            return
        AristaInterfaceReports().show_interfaces_transceiver(state, output, detail=False)

    def _print_interfaces_transceiver_detail(self, state, output, **_kwargs):
        AristaInterfaceReports().show_interfaces_transceiver(state, output, detail=True)

    def _print_module(self, state, output, **_kwargs):
        AristaSystemReports().show_module(state, output)

    def _print_processes_top_once(self, state, output, **_kwargs):
        AristaSystemReports().show_processes_top_once(state, output)

    def _print_ospf_interface_brief(self, state, output, **_kwargs):
        AristaRoutingReports().show_ip_ospf_interface_brief(state, output)

    def _print_mlag(self, state, output, **_kwargs):
        AristaRoutingReports().show_mlag(state, output)
