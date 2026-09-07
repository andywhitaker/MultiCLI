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
try:
    from cisco_ip_bgp_report import IpBgpReport
except ImportError:
    from ip_bgp_report import IpBgpReport
from mac_address_table_report import MacAddressTableReport

from srlinux.mgmt.cli.lazy_loader_utils import wait_for_show_reports_load
from srlinux.mgmt.cli.cli_mode import CliMode
from srlinux.mgmt.cli.cli_state import CliState
from srlinux.schema.data_store import DataStore

_active_data_store_override = None

_orig_is_intermediate = getattr(CliState, '_orig_multicli_is_intermediate', None)
if _orig_is_intermediate is None:
    _orig_is_intermediate = CliState.is_intermediate_command.fget
    CliState._orig_multicli_is_intermediate = _orig_is_intermediate

    def _multicli_is_intermediate(self):
        first_cmd = self.first_regular_command_name
        if first_cmd in ['eos', 'nxos', 'junos']:
            return not self.is_last_command
        return _orig_is_intermediate(self)

    CliState.is_intermediate_command = property(_multicli_is_intermediate)

_orig_server_data_store = getattr(CliState, '_orig_multicli_server_data_store', None)
if _orig_server_data_store is None:
    _orig_server_data_store = CliState.server_data_store.fget
    CliState._orig_multicli_server_data_store = _orig_server_data_store

    def _multicli_server_data_store(self):
        global _active_data_store_override
        if _active_data_store_override is not None:
            return _active_data_store_override
        return _orig_server_data_store(self)

    CliState.server_data_store = property(_multicli_server_data_store)

def _enter_submode(state, arguments):
    if state.is_last_command:
        state.location = arguments

def should_register_show_mode(persona_name):
    config_file = '/etc/opt/srlinux/cli/default_persona'
    if os.path.exists(config_file):
        try:
            with open(config_file) as f:
                pref = f.read().strip().lower()
                if pref == 'none':
                    return False
                if pref in [persona_name, persona_name.replace('-', ''), 'all']:
                    return True
                return False
        except Exception:
            pass
    return True

class Plugin(CliPlugin):

    def _get_child(self, parent, name):
        if hasattr(parent, 'get_command_or_none'):
            return parent.get_command_or_none(name)
        elif hasattr(parent, 'root'):
            return parent.root.get_command_or_none(name)
        return None

    def _wrap_callback(self, callback):
        if not callback:
            return None
        def wrapped(state, *args, **kwargs):
            if state.is_intermediate_command:
                return
            global _active_data_store_override
            _active_data_store_override = state.server.get_data_store(DataStore.State)
            try:
                return callback(state, *args, **kwargs)
            finally:
                _active_data_store_override = None
        return wrapped

    def _add_or_override(self, parent, syntax, callback=None, schema=None, update_location=False):
        node = self._get_child(parent, syntax.name)
        if node:
            if callback:
                node.set_callback(self._wrap_callback(callback))
            return node
        kwargs = {'update_location': update_location}
        if callback is not None:
            kwargs['callback'] = self._wrap_callback(callback)
        if schema is not None:
            kwargs['schema'] = schema
        return parent.add_command(syntax, **kwargs)

    def _register_all_commands(self, target):
        # 1. System Commands: version, hostname, clock, inventory, environment
        self._add_or_override(target, Syntax('version', help='Show system version in Cisco NX-OS format'), callback=self._print_version, update_location=False)
        self._add_or_override(target, Syntax('hostname', help='Show system hostname'), callback=self._print_hostname, update_location=False)
        self._add_or_override(target, Syntax('clock', help='Show system clock in Cisco NX-OS format'), callback=self._print_clock, update_location=False)
        self._add_or_override(target, Syntax('inventory', help='Show system hardware inventory in Cisco NX-OS format'), callback=self._print_inventory, update_location=False)

        env_cmd = self._add_or_override(target, Syntax('environment', help='Show environment status in Cisco NX-OS format'), callback=self._print_environment_all, update_location=False)
        self._add_or_override(env_cmd, Syntax('cooling', help='Show cooling status'), callback=self._print_environment_cooling, update_location=False)
        self._add_or_override(env_cmd, Syntax('power', help='Show power supply status'), callback=self._print_environment_power, update_location=False)
        self._add_or_override(env_cmd, Syntax('temperature', help='Show temperature status'), callback=self._print_environment_temp, update_location=False)

        self._add_or_override(target, Syntax('module', help='Show module information in Cisco NX-OS format'), callback=self._print_module, update_location=False)
        proc_node = self._add_or_override(target, Syntax('processes', help='Show process information in Cisco NX-OS format'), update_location=False)
        self._add_or_override(proc_node, Syntax('cpu', help='Show process CPU utilization'), callback=self._print_processes_cpu, update_location=False)

        # 2. Interface Commands: show interface [name], brief, status, description, transceiver
        intf_syntax = Syntax('interface', help='Interface status and information')
        intf_syntax.add_unnamed_argument(
            'name',
            default='*',
            suggestions=MultipleKeyCompleters(keycompleters=[KeyCompleter(path="/interface[name=*]")])
        )
        intf_node = self._add_or_override(target, intf_syntax, callback=self._print_interface_detail, update_location=False)
        self._add_or_override(intf_node, Syntax('brief', help='Interface brief in Cisco NX-OS format'), callback=self._print_interface_brief, update_location=False)
        self._add_or_override(intf_node, Syntax('status', help='Interface status in Cisco NX-OS format'), callback=self._print_interface_status, update_location=False)
        self._add_or_override(intf_node, Syntax('description', help='Interface description in Cisco NX-OS format'), callback=self._print_interface_description, update_location=False)
        xcvr = self._add_or_override(intf_node, Syntax('transceiver', help='Transceiver details in Cisco NX-OS format'), callback=self._print_interface_transceiver, update_location=False)
        self._add_or_override(xcvr, Syntax('details', help='Transceiver details'), callback=self._print_interface_transceiver_details, update_location=False)
        self._add_or_override(xcvr, Syntax('detail', help='Transceiver details'), callback=self._print_interface_transceiver_details, update_location=False)

        # Also support plural 'interfaces'
        intfs_syntax = Syntax('interfaces', help='Interface status and information')
        intfs_syntax.add_unnamed_argument(
            'name',
            default='*',
            suggestions=MultipleKeyCompleters(keycompleters=[KeyCompleter(path="/interface[name=*]")])
        )
        intfs_node = self._add_or_override(target, intfs_syntax, callback=self._print_interface_detail, update_location=False)
        self._add_or_override(intfs_node, Syntax('brief', help='Interface brief in Cisco NX-OS format'), callback=self._print_interface_brief, update_location=False)
        self._add_or_override(intfs_node, Syntax('status', help='Interface status in Cisco NX-OS format'), callback=self._print_interface_status, update_location=False)
        self._add_or_override(intfs_node, Syntax('description', help='Interface description in Cisco NX-OS format'), callback=self._print_interface_description, update_location=False)
        xcvrs = self._add_or_override(intfs_node, Syntax('transceiver', help='Transceiver details in Cisco NX-OS format'), callback=self._print_interface_transceiver, update_location=False)
        self._add_or_override(xcvrs, Syntax('details', help='Transceiver details'), callback=self._print_interface_transceiver_details, update_location=False)
        self._add_or_override(xcvrs, Syntax('detail', help='Transceiver details'), callback=self._print_interface_transceiver_details, update_location=False)

        # IPv6 Commands: show ipv6 interface brief
        ipv6_node = self._add_or_override(target, Syntax('ipv6', help='IPv6 protocol information'), update_location=False)
        ipv6_intf = self._add_or_override(ipv6_node, Syntax('interface', help='IPv6 interface information'), update_location=False)
        self._add_or_override(ipv6_intf, Syntax('brief', help='IPv6 interface brief in Cisco NX-OS format'), callback=self._print_ipv6_interface_brief, update_location=False)

        # Port-Channel Commands
        pc_node = self._add_or_override(target, Syntax('port-channel', help='Port-Channel information'), update_location=False)
        self._add_or_override(pc_node, Syntax('summary', help='Port-Channel summary in Cisco NX-OS format'), callback=self._print_port_channel_summary, update_location=False)

        # 3. LLDP Commands: show lldp neighbors, show lldp neighbor
        lldp_node = self._add_or_override(target, Syntax('lldp', help='LLDP information'), update_location=False)
        lldp_neigh = self._add_or_override(lldp_node, Syntax('neighbors', help='LLDP neighbors in Cisco NX-OS format'), callback=self._print_lldp_neighbors, update_location=False)
        self._add_or_override(lldp_neigh, Syntax('detail', help='LLDP neighbors detail in Cisco NX-OS format'), callback=self._print_lldp_neighbors_detail, update_location=False)
        # Singular alias
        lldp_single = self._add_or_override(lldp_node, Syntax('neighbor', help='LLDP neighbors in Cisco NX-OS format'), callback=self._print_lldp_neighbors, update_location=False)
        self._add_or_override(lldp_single, Syntax('detail', help='LLDP neighbors detail in Cisco NX-OS format'), callback=self._print_lldp_neighbors_detail, update_location=False)

        # 4. IP Commands: show ip route, show ip interface brief, show ip bgp, show ip arp, show ip ospf
        ip_node = self._add_or_override(target, Syntax('ip', help='IP protocol information'), update_location=False)

        ip_route = self._add_or_override(ip_node, Syntax('route', help='IP route information'), callback=self._print_ip_route, update_location=False)
        self._add_or_override(
            ip_route,
            Syntax('vrf').add_unnamed_argument('vrf_name', suggestions=KeyCompleter('/network-instance[name=*]')),
            callback=self._print_ip_route_vrf,
            update_location=False
        )

        ip_intf = self._add_or_override(ip_node, Syntax('interface', help='IP interface information'), update_location=False)
        self._add_or_override(ip_intf, Syntax('brief', help='IP interface status in Cisco NX-OS format'), callback=self._print_ip_interface_brief, update_location=False)

        ip_bgp = self._add_or_override(ip_node, Syntax('bgp', help='IP BGP information'), update_location=False)
        self._add_or_override(ip_bgp, Syntax('summary', help='BGP summary information'), callback=self._print_ip_bgp_summary, update_location=False)

        ip_bgp_vrf = self._add_or_override(ip_bgp, Syntax('vrf').add_unnamed_argument('vrf_name', suggestions=KeyCompleter('/network-instance[name=*]')), update_location=False)
        self._add_or_override(ip_bgp_vrf, Syntax('summary', help='BGP summary for VRF'), callback=self._print_ip_bgp_vrf_summary, update_location=False)

        self._add_or_override(ip_node, Syntax('arp', help='IP ARP table in Cisco NX-OS format'), callback=self._print_ip_arp, update_location=False)

        ip_ospf = self._add_or_override(ip_node, Syntax('ospf', help='IP OSPF information'), update_location=False)
        self._add_or_override(ip_ospf, Syntax('neighbor', help='OSPF neighbors in Cisco NX-OS format'), callback=self._print_ospf_neighbor, update_location=False)
        ospf_intf = self._add_or_override(ip_ospf, Syntax('interface', help='OSPF interface information'), update_location=False)
        self._add_or_override(ospf_intf, Syntax('brief', help='OSPF interface brief in Cisco NX-OS format'), callback=self._print_ip_ospf_interface_brief, update_location=False)

        # 5. MAC Address Table
        mac_node = self._add_or_override(target, Syntax('mac', help='Show MAC commands'), update_location=False)
        mac_address_table = self._add_or_override(
            mac_node,
            Syntax('address-table', help='Show MAC Address Table in Cisco NX-OS format'),
            callback=self._print_mac_address_table,
            schema=MacAddressTableReport().get_schema_instance(),
            update_location=False
        )
        self._add_or_override(
            mac_address_table,
            Syntax('instance', help='Display information for a specified network-instance')
            .add_unnamed_argument('name', suggestions=KeyCompleter('/network-instance[name=*]')),
            callback=self._print_mac_address_table,
            update_location=False,
            schema=MacAddressTableReport().get_schema_instance()
        )
        self._add_or_override(
            mac_address_table,
            Syntax('vlan', help='Display MAC address learned on a specified VLAN')
            .add_unnamed_argument('value', suggestions=MultipleKeyCompleters(keycompleters=[KeyCompleter(path="/interface[name=*]/subinterface[index=*]/vlan/encap/single-tagged-range/low-vlan-id[range-low-vlan-id=*]"), KeyCompleter(path="/interface[name=*]/subinterface[index=*]/vlan/encap/single-tagged/vlan-id:")])),
            callback=self._print_mac_address_table,
            update_location=False,
            schema=MacAddressTableReport().get_schema_instance()
        )
        self._add_or_override(
            mac_address_table,
            Syntax('interface', help='Display MAC table for a specified interface')
            .add_unnamed_argument('name', suggestions=MultipleKeyCompleters(keycompleters=[KeyCompleter(path="/interface[name=*]"), KeyCompleter(path="/interface[name=*]/subinterface[index=*]/name:")])),
            callback=self._print_mac_address_table,
            update_location=False,
            schema=MacAddressTableReport().get_schema_instance()
        )
        self._add_or_override(
            mac_address_table,
            Syntax('vni', help='Display MAC table for a specified vni')
            .add_unnamed_argument('value', suggestions=KeyCompleter(path="/tunnel-interface[name=*]/vxlan-interface[index=*]/ingress/vni:")),
            callback=self._print_mac_address_table,
            update_location=False,
            schema=MacAddressTableReport().get_schema_instance()
        )

        # 6. Routing / Network Instance: vrf, vlan, bfd, nve, vpc
        self._add_or_override(target, Syntax('vrf', help='VRF information in Cisco NX-OS format'), callback=self._print_vrf, update_location=False)
        self._add_or_override(target, Syntax('vlan', help='VLAN information in Cisco NX-OS format'), callback=self._print_vlan, update_location=False)

        bfd_node = self._add_or_override(target, Syntax('bfd', help='BFD information'), update_location=False)
        self._add_or_override(bfd_node, Syntax('neighbors', help='BFD neighbors in Cisco NX-OS format'), callback=self._print_bfd_neighbors, update_location=False)

        nve_node = self._add_or_override(target, Syntax('nve', help='NVE information in Cisco NX-OS format'), update_location=False)
        self._add_or_override(nve_node, Syntax('vni', help='NVE VNI status in Cisco NX-OS format'), callback=self._print_nve_vni, update_location=False)
        self._add_or_override(nve_node, Syntax('peers', help='NVE peers in Cisco NX-OS format'), callback=self._print_nve_peers, update_location=False)

        self._add_or_override(target, Syntax('vpc', help='vPC information in Cisco NX-OS format'), callback=self._print_vpc, update_location=False)

    def load(self, cli, **_kwargs):
        self._cli = cli
        # 1. Root global command 'nxos' for interactive submode and one-liners:
        # e.g., 'nxos show version' or entering 'nxos' mode
        nxos_node = cli.add_global_command(
            Syntax('nxos', help='Cisco NX-OS operational mode and commands'),
            update_location=_enter_submode
        )
        nx_show = self._add_or_override(
            nxos_node,
            Syntax('show', help='Cisco NX-OS show reports'),
            update_location=False
        )
        self._register_all_commands(nx_show)

    def on_start(self, state):
        if not should_register_show_mode('cisco'):
            return
        # 2. Register to show_mode for persona compatibility (e.g. cnxuser)
        wait_for_show_reports_load(state)
        self._register_all_commands(state.command_tree.show_mode)

    # Callbacks
    def _print_interface_detail(self, state, output, arguments=None, **_kwargs):
        if state.is_intermediate_command:
            return
        CiscoInterfaceReports().show_interface_detail(state, output, arguments=arguments)

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
        output.print_line('\nTry SR Linux command: show network-instance default ipv4 route')

    def _print_ip_route_vrf(self, state, arguments, output, **_kwargs):
        vrf_name = arguments.get('vrf_name') or 'default'
        IpRouteReport()._show_routes(state, output, network_instance=vrf_name)
        output.print_line(f'\nTry SR Linux command: show network-instance {vrf_name} ipv4 route')

    def _print_ip_interface_brief(self, state, output, **_kwargs):
        IpInterfaceReport().show_ip_interface_brief(state, output, vrf='default')

    def _print_ip_bgp_summary(self, state, output, **_kwargs):
        IpBgpReport().show_bgp_summary(state, output, network_instance='default')
        output.print_line('\nTry SR Linux command: show network-instance default protocols bgp neighbor')

    def _print_ip_bgp_vrf_summary(self, state, arguments, output, **_kwargs):
        vrf_name = arguments.get('vrf', 'vrf_name') if arguments.has_node('vrf') else 'default'
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
