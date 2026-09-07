#!/usr/bin/python
###########################################################################
# Description: MultiCLI Plugin for Cisco NX-OS Commands
# Copyright (c) 2025-2026 Nokia
###########################################################################

import srlinux.schema.schema_syntax_builder
from srlinux.mgmt.cli import CliPlugin, KeyCompleter, RequiredPlugin, MultipleKeyCompleters
from srlinux.syntax import Syntax
from srlinux.location import build_path
import sys
import os

potential_paths = [
    '/etc/opt/srlinux/cli',
    os.path.expanduser('~/cli'),
    '/home/cnxuser/cli',
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

for subdir in ["ip", "mac", "interface", "system", "routing"]:
    sub_path = os.path.join(import_base, subdir)
    if os.path.exists(sub_path) and sub_path not in sys.path:
        sys.path.insert(0, sub_path)

from cisco_system_reports import CiscoSystemReports
from cisco_interface_reports import CiscoInterfaceReports
from cisco_lldp_reports import CiscoLldpReports
from cisco_routing_reports import CiscoRoutingReports
from ip_route_report import IpRouteReport
from ip_interface_report import IpInterfaceReport
from ip_bgp_report import IpBgpReport
from mac_address_table_report import MacAddressTableReport

class Plugin(CliPlugin):

    def get_required_plugins(self):
        return [
            RequiredPlugin('version', module='srlinux'),
        ]

    def _add_or_override(self, parent, syntax, callback=None, schema=None, update_location=False):
        if hasattr(parent, 'get_command_or_none'):
            node = parent.get_command_or_none(syntax.name)
        elif hasattr(parent, 'root'):
            node = parent.root.get_command_or_none(syntax.name)
        else:
            node = None

        if node:
            if callback:
                node.set_callback(callback)
            return node
        kwargs = {}
        if callback is not None:
            kwargs['callback'] = callback
        if schema is not None:
            kwargs['schema'] = schema
        if update_location:
            kwargs['update_location'] = update_location
        return parent.add_command(syntax, **kwargs)

    def load(self, cli, **_kwargs):
        # 1. System Commands: version, hostname, clock, inventory, environment
        self._add_or_override(cli.show_mode, Syntax('version', help='Show system version in Cisco NX-OS format'), callback=self._print_version)
        self._add_or_override(cli.show_mode, Syntax('hostname', help='Show system hostname'), callback=self._print_hostname)
        self._add_or_override(cli.show_mode, Syntax('clock', help='Show system clock in Cisco NX-OS format'), callback=self._print_clock)
        self._add_or_override(cli.show_mode, Syntax('inventory', help='Show system hardware inventory in Cisco NX-OS format'), callback=self._print_inventory)

        env_cmd = self._add_or_override(cli.show_mode, Syntax('environment', help='Show environment status in Cisco NX-OS format'), callback=self._print_environment_all)
        self._add_or_override(env_cmd, Syntax('cooling', help='Show cooling status'), callback=self._print_environment_cooling)
        self._add_or_override(env_cmd, Syntax('power', help='Show power supply status'), callback=self._print_environment_power)
        self._add_or_override(env_cmd, Syntax('temperature', help='Show temperature status'), callback=self._print_environment_temp)

        self._add_or_override(cli.show_mode, Syntax('module', help='Show module information in Cisco NX-OS format'), callback=self._print_module)
        proc_node = self._add_or_override(cli.show_mode, Syntax('processes', help='Show process information in Cisco NX-OS format'))
        self._add_or_override(proc_node, Syntax('cpu', help='Show process CPU utilization'), callback=self._print_processes_cpu)

        # 2. Interface Commands: show interface brief, status, description, transceiver
        intf_node = self._add_or_override(cli.show_mode, Syntax('interface', help='Interface information'))
        self._add_or_override(intf_node, Syntax('brief', help='Interface brief in Cisco NX-OS format'), callback=self._print_interface_brief)
        self._add_or_override(intf_node, Syntax('status', help='Interface status in Cisco NX-OS format'), callback=self._print_interface_status)
        self._add_or_override(intf_node, Syntax('description', help='Interface description in Cisco NX-OS format'), callback=self._print_interface_description)
        xcvr = self._add_or_override(intf_node, Syntax('transceiver', help='Transceiver details in Cisco NX-OS format'), callback=self._print_interface_transceiver)
        self._add_or_override(xcvr, Syntax('details', help='Transceiver details'), callback=self._print_interface_transceiver_details)
        self._add_or_override(xcvr, Syntax('detail', help='Transceiver details'), callback=self._print_interface_transceiver_details)

        # Also support plural 'interfaces'
        intfs_node = self._add_or_override(cli.show_mode, Syntax('interfaces', help='Interface information'))
        self._add_or_override(intfs_node, Syntax('brief', help='Interface brief in Cisco NX-OS format'), callback=self._print_interface_brief)
        self._add_or_override(intfs_node, Syntax('status', help='Interface status in Cisco NX-OS format'), callback=self._print_interface_status)
        self._add_or_override(intfs_node, Syntax('description', help='Interface description in Cisco NX-OS format'), callback=self._print_interface_description)
        xcvrs = self._add_or_override(intfs_node, Syntax('transceiver', help='Transceiver details in Cisco NX-OS format'), callback=self._print_interface_transceiver)
        self._add_or_override(xcvrs, Syntax('details', help='Transceiver details'), callback=self._print_interface_transceiver_details)
        self._add_or_override(xcvrs, Syntax('detail', help='Transceiver details'), callback=self._print_interface_transceiver_details)

        # IPv6 Commands: show ipv6 interface brief
        ipv6_node = self._add_or_override(cli.show_mode, Syntax('ipv6', help='IPv6 protocol information'))
        ipv6_intf = self._add_or_override(ipv6_node, Syntax('interface', help='IPv6 interface information'))
        self._add_or_override(ipv6_intf, Syntax('brief', help='IPv6 interface brief in Cisco NX-OS format'), callback=self._print_ipv6_interface_brief)

        # Port-Channel Commands
        pc_node = self._add_or_override(cli.show_mode, Syntax('port-channel', help='Port-Channel information'))
        self._add_or_override(pc_node, Syntax('summary', help='Port-Channel summary in Cisco NX-OS format'), callback=self._print_port_channel_summary)

        # 3. LLDP Commands: show lldp neighbors, show lldp neighbor
        lldp_node = self._add_or_override(cli.show_mode, Syntax('lldp', help='LLDP information'))
        lldp_neigh = self._add_or_override(lldp_node, Syntax('neighbors', help='LLDP neighbors in Cisco NX-OS format'), callback=self._print_lldp_neighbors)
        self._add_or_override(lldp_neigh, Syntax('detail', help='LLDP neighbors detail in Cisco NX-OS format'), callback=self._print_lldp_neighbors_detail)
        # Singular alias
        lldp_single = self._add_or_override(lldp_node, Syntax('neighbor', help='LLDP neighbors in Cisco NX-OS format'), callback=self._print_lldp_neighbors)
        self._add_or_override(lldp_single, Syntax('detail', help='LLDP neighbors detail in Cisco NX-OS format'), callback=self._print_lldp_neighbors_detail)

        # 4. IP Commands: show ip route, show ip interface brief, show ip bgp, show ip arp, show ip ospf
        ip_node = self._add_or_override(cli.show_mode, Syntax('ip', help='IP protocol information'))

        ip_route = self._add_or_override(ip_node, Syntax('route', help='IP route information'), callback=self._print_ip_route)
        ip_route.add_command(
            Syntax('vrf').add_unnamed_argument('vrf_name', suggestions=KeyCompleter('/network-instance[name=*]')),
            callback=self._print_ip_route_vrf,
            update_location=False
        )

        ip_intf = self._add_or_override(ip_node, Syntax('interface', help='IP interface information'))
        self._add_or_override(ip_intf, Syntax('brief', help='IP interface status in Cisco NX-OS format'), callback=self._print_ip_interface_brief)

        ip_bgp = self._add_or_override(ip_node, Syntax('bgp', help='IP BGP information'))
        self._add_or_override(ip_bgp, Syntax('summary', help='BGP summary information'), callback=self._print_ip_bgp_summary)

        ip_bgp_vrf = self._add_or_override(ip_bgp, Syntax('vrf').add_unnamed_argument('vrf_name', suggestions=KeyCompleter('/network-instance[name=*]')))
        self._add_or_override(ip_bgp_vrf, Syntax('summary', help='BGP summary for VRF'), callback=self._print_ip_bgp_vrf_summary)

        self._add_or_override(ip_node, Syntax('arp', help='IP ARP table in Cisco NX-OS format'), callback=self._print_ip_arp)

        ip_ospf = self._add_or_override(ip_node, Syntax('ospf', help='IP OSPF information'))
        self._add_or_override(ip_ospf, Syntax('neighbor', help='OSPF neighbors in Cisco NX-OS format'), callback=self._print_ospf_neighbor)
        ospf_intf = self._add_or_override(ip_ospf, Syntax('interface', help='OSPF interface information'))
        self._add_or_override(ospf_intf, Syntax('brief', help='OSPF interface brief in Cisco NX-OS format'), callback=self._print_ip_ospf_interface_brief)

        # 5. MAC Address Table
        mac_node = self._add_or_override(cli.show_mode, Syntax('mac', help='Show MAC commands'))
        mac_address_table = self._add_or_override(
            mac_node,
            Syntax('address-table', help='Show MAC Address Table in Cisco NX-OS format'),
            callback=self._print_mac_address_table,
            schema=MacAddressTableReport().get_schema_instance()
        )
        mac_address_table.add_command(
            Syntax('instance', help='Display information for a specified network-instance')
            .add_unnamed_argument('name', suggestions=KeyCompleter('/network-instance[name=*]')),
            callback=self._print_mac_address_table,
            update_location=False,
            schema=MacAddressTableReport().get_schema_instance()
        )
        mac_address_table.add_command(
            Syntax('vlan', help='Display MAC address learned on a specified VLAN')
            .add_unnamed_argument('value', suggestions=MultipleKeyCompleters(keycompleters=[KeyCompleter(path="/interface[name=*]/subinterface[index=*]/vlan/encap/single-tagged-range/low-vlan-id[range-low-vlan-id=*]"), KeyCompleter(path="/interface[name=*]/subinterface[index=*]/vlan/encap/single-tagged/vlan-id:")])),
            callback=self._print_mac_address_table,
            update_location=False,
            schema=MacAddressTableReport().get_schema_instance()
        )
        mac_address_table.add_command(
            Syntax('interface', help='Display MAC table for a specified interface')
            .add_unnamed_argument('name', suggestions=MultipleKeyCompleters(keycompleters=[KeyCompleter(path="/interface[name=*]"), KeyCompleter(path="/interface[name=*]/subinterface[index=*]/name:")])),
            callback=self._print_mac_address_table,
            update_location=False,
            schema=MacAddressTableReport().get_schema_instance()
        )
        mac_address_table.add_command(
            Syntax('vni', help='Display MAC table for a specified vni')
            .add_unnamed_argument('value', suggestions=KeyCompleter(path="/tunnel-interface[name=*]/vxlan-interface[index=*]/ingress/vni:")),
            callback=self._print_mac_address_table,
            update_location=False,
            schema=MacAddressTableReport().get_schema_instance()
        )

        # 6. Routing / Network Instance: vrf, vlan, bfd, nve, vpc
        self._add_or_override(cli.show_mode, Syntax('vrf', help='VRF information in Cisco NX-OS format'), callback=self._print_vrf)
        self._add_or_override(cli.show_mode, Syntax('vlan', help='VLAN information in Cisco NX-OS format'), callback=self._print_vlan)

        bfd_node = self._add_or_override(cli.show_mode, Syntax('bfd', help='BFD information'))
        self._add_or_override(bfd_node, Syntax('neighbors', help='BFD neighbors in Cisco NX-OS format'), callback=self._print_bfd_neighbors)

        nve_node = self._add_or_override(cli.show_mode, Syntax('nve', help='NVE information in Cisco NX-OS format'))
        self._add_or_override(nve_node, Syntax('vni', help='NVE VNI status in Cisco NX-OS format'), callback=self._print_nve_vni)
        self._add_or_override(nve_node, Syntax('peers', help='NVE peers in Cisco NX-OS format'), callback=self._print_nve_peers)

        self._add_or_override(cli.show_mode, Syntax('vpc', help='vPC information in Cisco NX-OS format'), callback=self._print_vpc)

    # Callbacks
    def _print_version(self, state, output, **_kwargs):
        CiscoSystemReports().show_version(state, output)

    def _print_hostname(self, state, output, **_kwargs):
        CiscoSystemReports().show_hostname(state, output)

    def _print_clock(self, state, output, **_kwargs):
        CiscoSystemReports().show_clock(state, output)

    def _print_inventory(self, state, output, **_kwargs):
        CiscoSystemReports().show_inventory(state, output)

    def _print_environment_all(self, state, output, **_kwargs):
        if state.is_intermediate_command:
            return
        CiscoSystemReports().show_environment(state, output, 'all')

    def _print_environment_cooling(self, state, output, **_kwargs):
        CiscoSystemReports().show_environment(state, output, 'cooling')

    def _print_environment_power(self, state, output, **_kwargs):
        CiscoSystemReports().show_environment(state, output, 'power')

    def _print_environment_temp(self, state, output, **_kwargs):
        CiscoSystemReports().show_environment(state, output, 'temperature')

    def _print_interface_brief(self, state, output, **_kwargs):
        CiscoInterfaceReports().show_interface_brief(state, output)

    def _print_interface_status(self, state, output, **_kwargs):
        CiscoInterfaceReports().show_interface_status(state, output)

    def _print_interface_description(self, state, output, **_kwargs):
        CiscoInterfaceReports().show_interface_description(state, output)

    def _print_port_channel_summary(self, state, output, **_kwargs):
        CiscoInterfaceReports().show_port_channel_summary(state, output)

    def _print_lldp_neighbors(self, state, output, **_kwargs):
        if state.is_intermediate_command:
            return
        CiscoLldpReports().show_lldp_neighbors(state, output, detail=False)

    def _print_lldp_neighbors_detail(self, state, output, **_kwargs):
        CiscoLldpReports().show_lldp_neighbors(state, output, detail=True)

    def _print_ip_route(self, state, output, **_kwargs):
        if state.is_intermediate_command:
            return
        IpRouteReport()._show_routes(state, output, network_instance='default')
        output.print_line('\nTry SR Linux command: show network-instance default route-table')

    def _print_ip_route_vrf(self, state, arguments, output, **_kwargs):
        vrf_name = arguments.get('vrf_name') or 'default'
        IpRouteReport()._show_routes(state, output, network_instance=vrf_name)
        output.print_line(f'\nTry SR Linux command: show network-instance {vrf_name} route-table')

    def _print_ip_interface_brief(self, state, output, **_kwargs):
        IpInterfaceReport().show_ip_interface_brief(state, output, vrf='default')

    def _print_ip_bgp_summary(self, state, output, **_kwargs):
        IpBgpReport().show_bgp_summary(state, output, network_instance='default')
        output.print_line('\nTry SR Linux command: show network-instance default protocols bgp neighbor')

    def _print_ip_bgp_vrf_summary(self, state, arguments, output, **_kwargs):
        vrf_name = arguments.get('vrf_name') or 'default'
        IpBgpReport().show_bgp_summary(state, output, network_instance=vrf_name)
        output.print_line(f'\nTry SR Linux command: show network-instance {vrf_name} protocols bgp neighbor')

    def _print_ip_arp(self, state, output, **_kwargs):
        CiscoRoutingReports().show_ip_arp(state, output)

    def _print_ospf_neighbor(self, state, output, **_kwargs):
        CiscoRoutingReports().show_ip_ospf_neighbor(state, output)

    def _print_mac_address_table(self, state, arguments, output, **kwargs):
        if state.is_intermediate_command:
            return
        MacAddressTableReport()._show_table_instance(state, output, arguments, **kwargs)

    def _print_vrf(self, state, output, **_kwargs):
        CiscoRoutingReports().show_vrf(state, output)

    def _print_vlan(self, state, output, **_kwargs):
        CiscoRoutingReports().show_vlan(state, output)

    def _print_bfd_neighbors(self, state, output, **_kwargs):
        CiscoRoutingReports().show_bfd_neighbors(state, output)

    def _print_module(self, state, output, **_kwargs):
        CiscoSystemReports().show_module(state, output)

    def _print_processes_cpu(self, state, output, **_kwargs):
        CiscoSystemReports().show_processes_cpu(state, output)

    def _print_interface_transceiver(self, state, output, **_kwargs):
        if state.is_intermediate_command:
            return
        CiscoInterfaceReports().show_interface_transceiver(state, output, details=False)

    def _print_interface_transceiver_details(self, state, output, **_kwargs):
        CiscoInterfaceReports().show_interface_transceiver(state, output, details=True)

    def _print_ipv6_interface_brief(self, state, output, **_kwargs):
        CiscoInterfaceReports().show_ipv6_interface_brief(state, output)

    def _print_ip_ospf_interface_brief(self, state, output, **_kwargs):
        CiscoRoutingReports().show_ip_ospf_interface_brief(state, output)

    def _print_nve_vni(self, state, output, **_kwargs):
        CiscoRoutingReports().show_nve_vni(state, output)

    def _print_nve_peers(self, state, output, **_kwargs):
        CiscoRoutingReports().show_nve_peers(state, output)

    def _print_vpc(self, state, output, **_kwargs):
        CiscoRoutingReports().show_vpc(state, output)
