#!/usr/bin/python
###########################################################################
# Description: MultiCLI Plugin for Juniper JUNOS Commands
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
    '/home/juser/cli',
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
        os.path.exists(os.path.join(path, 'routing')) or
        os.path.exists(os.path.join(path, 'interface')) or
        os.path.exists(os.path.join(path, 'eth_switch'))
    ):
        import_base = path
        break

if import_base is None:
    raise ImportError("Could not find a valid CLI plugin base directory")

for subdir in ["system", "routing", "eth_switch", "interface"]:
    sub_path = os.path.join(import_base, subdir)
    if os.path.exists(sub_path) and sub_path not in sys.path:
        sys.path.insert(0, sub_path)

from junos_system_reports import JunosSystemReports
from junos_routing_reports import JunosRoutingReports
from ethernet_switching_table_report import EthernetSwitchingReport
from show_interfaces import JperInterfaceSummary, JperInterfaceBrief, JperInterfaceTerse

from srlinux.mgmt.cli.lazy_loader_utils import wait_for_show_reports_load
from srlinux.mgmt.cli.cli_mode import CliMode
import os

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
    # If no default_persona file is set, check if multiple vendor plugins are present
    plugins_dir = '/etc/opt/srlinux/cli/plugins'
    if os.path.exists(plugins_dir):
        installed_plugins = [f for f in os.listdir(plugins_dir) if f.startswith('main_') and f.endswith('.py')]
        if len(installed_plugins) == 1 and f'main_{persona_name.split("-")[0]}.py' in installed_plugins[0]:
            return True
    return False

class Plugin(CliPlugin):

    def _get_child(self, parent, name):
        if hasattr(parent, 'get_command_or_none'):
            return parent.get_command_or_none(name)
        elif hasattr(parent, 'root'):
            return parent.root.get_command_or_none(name)
        return None

    def _add_or_override(self, parent, syntax, callback=None, schema=None, update_location=False):
        node = self._get_child(parent, syntax.name)
        if node:
            if callback:
                node.set_callback(callback)
            return node
        kwargs = {'update_location': update_location}
        if callback is not None:
            kwargs['callback'] = callback
        if schema is not None:
            kwargs['schema'] = schema
        return parent.add_command(syntax, **kwargs)

    def _register_all_commands(self, target):
        # 1. System Commands: show version, show system uptime, show chassis hardware
        self._add_or_override(target, Syntax('version', help='Show system version in Juniper JUNOS format'), callback=self._print_version, update_location=False)

        sys_cmd = self._add_or_override(target, Syntax('system', help='Show system information in Juniper format'), update_location=False)
        self._add_or_override(sys_cmd, Syntax('uptime', help='Show system uptime in Juniper format'), callback=self._print_system_uptime, update_location=False)
        proc_cmd = self._add_or_override(sys_cmd, Syntax('processes', help='Show system processes in Juniper format'), callback=self._print_system_processes, update_location=False)
        self._add_or_override(proc_cmd, Syntax('summary', help='Show system processes summary'), callback=self._print_system_processes_summary, update_location=False)
        self._add_or_override(proc_cmd, Syntax('brief', help='Show system processes brief'), callback=self._print_system_processes, update_location=False)
        self._add_or_override(proc_cmd, Syntax('extensive', help='Show system processes extensive'), callback=self._print_system_processes, update_location=False)

        chassis_cmd = self._add_or_override(target, Syntax('chassis', help='Show chassis information in Juniper format'), update_location=False)
        self._add_or_override(chassis_cmd, Syntax('hardware', help='Show chassis hardware in Juniper format'), callback=self._print_chassis_hardware, update_location=False)

        # 2. Interfaces: show interfaces, show interfaces brief, show interfaces terse
        intfs = self._add_or_override(
            target,
            JperInterfaceSummary.get_syntax(),
            callback=self._interface_summary,
            schema=JperInterfaceSummary.get_data_schema(),
            update_location=False
        )
        self._add_or_override(
            intfs,
            JperInterfaceBrief.get_syntax(),
            callback=self._interface_brief,
            schema=JperInterfaceBrief.get_data_schema(),
            update_location=False
        )
        self._add_or_override(
            intfs,
            JperInterfaceTerse.get_syntax(),
            callback=self._interface_terse,
            schema=JperInterfaceTerse.get_data_schema(),
            update_location=False
        )

        # 3. ARP: show arp, show arp no-resolve
        arp_cmd = self._add_or_override(target, Syntax('arp', help='Show ARP table in Juniper format'), callback=self._print_arp, update_location=False)
        self._add_or_override(arp_cmd, Syntax('no-resolve', help='Show ARP table without resolving DNS'), callback=self._print_arp, update_location=False)

        # 4. LLDP: show lldp neighbors
        lldp_node = self._add_or_override(target, Syntax('lldp', help='Show LLDP information'), update_location=False)
        self._add_or_override(lldp_node, Syntax('neighbors', help='Show LLDP neighbors in Juniper format'), callback=self._print_lldp_neighbors, update_location=False)

        # 5. VLANs: show vlans
        self._add_or_override(target, Syntax('vlans', help='Show VLANs in Juniper format'), callback=self._print_vlans, update_location=False)

        # 6. LACP: show lacp interfaces
        lacp_node = self._add_or_override(target, Syntax('lacp', help='Show LACP information'), update_location=False)
        self._add_or_override(lacp_node, Syntax('interfaces', help='Show LACP aggregated interfaces in Juniper format'), callback=self._print_lacp_interfaces, update_location=False)

        # 7. Ethernet-Switching: show ethernet-switching table
        eth_switch = self._add_or_override(target, Syntax('ethernet-switching', help='Show ethernet switching information'), update_location=False)
        eth_switch_table = self._add_or_override(
            eth_switch,
            Syntax('table', help='Show media access control table'),
            callback=self._show_ethernet_switching_table,
            schema=EthernetSwitchingReport().get_schema_instance(),
            update_location=False
        )
        self._add_or_override(
            eth_switch_table,
            Syntax('instance', help='Display information for a specified network-instance')
            .add_unnamed_argument('name', suggestions=KeyCompleter('/network-instance[name=*]')),
            callback=self._show_ethernet_switching_table,
            update_location=False,
            schema=EthernetSwitchingReport().get_schema_instance()
        )
        self._add_or_override(
            eth_switch_table,
            Syntax('vlan', help='Display MAC address learned on a specified VLAN')
            .add_unnamed_argument('value', suggestions=MultipleKeyCompleters(keycompleters=[KeyCompleter(path="/interface[name=*]/subinterface[index=*]/vlan/encap/single-tagged-range/low-vlan-id[range-low-vlan-id=*]"), KeyCompleter(path="/interface[name=*]/subinterface[index=*]/vlan/encap/single-tagged/vlan-id:")])),
            callback=self._show_ethernet_switching_table,
            update_location=False,
            schema=EthernetSwitchingReport().get_schema_instance()
        )
        self._add_or_override(
            eth_switch_table,
            Syntax('interface', help='Display MAC table for a specified interface')
            .add_unnamed_argument('name', suggestions=MultipleKeyCompleters(keycompleters=[KeyCompleter(path="/interface[name=*]"), KeyCompleter(path="/interface[name=*]/subinterface[index=*]/name:")])),
            callback=self._show_ethernet_switching_table,
            update_location=False,
            schema=EthernetSwitchingReport().get_schema_instance()
        )

        # 8. Route: show route / show route summary
        route_cmd = self._add_or_override(target, Syntax('route', help='Show routing table'), callback=self._print_route, update_location=False)
        self._add_or_override(route_cmd, Syntax('summary', help='Show route summary in Juniper format'), callback=self._print_route_summary, update_location=False)

        # 9. BGP Summary: show bgp summary
        bgp_cmd = self._add_or_override(target, Syntax('bgp', help='Show BGP information'), update_location=False)
        self._add_or_override(bgp_cmd, Syntax('summary', help='Show BGP summary in Juniper format'), callback=self._print_bgp_summary, update_location=False)

        # 10. OSPF Neighbor: show ospf neighbor
        ospf_cmd = self._add_or_override(target, Syntax('ospf', help='Show OSPF information'), update_location=False)
        self._add_or_override(ospf_cmd, Syntax('neighbor', help='Show OSPF neighbor in Juniper format'), callback=self._print_ospf_neighbor, update_location=False)

        # 11. IS-IS Adjacency: show isis adjacency
        isis_cmd = self._add_or_override(target, Syntax('isis', help='Show IS-IS information'), update_location=False)
        self._add_or_override(isis_cmd, Syntax('adjacency', help='Show IS-IS adjacency in Juniper format'), callback=self._print_isis_adjacency, update_location=False)

    def load(self, cli, **_kwargs):
        self._cli = cli
        # 1. Root global command 'junos' for interactive submode and one-liners:
        # e.g., 'junos show version' or entering 'junos' mode
        junos_node = cli.add_global_command(
            Syntax('junos', help='Juniper JUNOS operational mode and commands'),
            update_location=_enter_submode
        )
        junos_show = self._add_or_override(
            junos_node,
            Syntax('show', help='Juniper JUNOS show reports'),
            update_location=False
        )
        self._register_all_commands(junos_show)

    def on_start(self, state):
        if not should_register_show_mode('juniper'):
            return
        # 2. Register to show_mode for persona compatibility (e.g. juser)
        wait_for_show_reports_load(state)
        self._register_all_commands(state.command_tree.show_mode)

    # Callbacks
    def _print_version(self, state, output, **_kwargs):
        JunosSystemReports().show_version(state, output)

    def _print_system_uptime(self, state, output, **_kwargs):
        JunosSystemReports().show_system_uptime(state, output)

    def _print_chassis_hardware(self, state, output, **_kwargs):
        JunosSystemReports().show_chassis_hardware(state, output)

    def _print_system_processes(self, state, output, **_kwargs):
        if not state.is_last_command:
            return
        JunosSystemReports().show_system_processes(state, output, summary=False)

    def _print_system_processes_summary(self, state, output, **_kwargs):
        JunosSystemReports().show_system_processes(state, output, summary=True)

    def _interface_summary(self, state, arguments, output, **_kwargs):
        if not state.is_last_command:
            return
        JperInterfaceSummary().print(state, arguments, output, **_kwargs)

    def _interface_brief(self, state, arguments, output, **_kwargs):
        if not state.is_last_command:
            return
        JperInterfaceBrief().print(state, arguments, output, **_kwargs)

    def _interface_terse(self, state, arguments, output, **_kwargs):
        if not state.is_last_command:
            return
        JperInterfaceTerse().print(state, arguments, output, **_kwargs)

    def _print_arp(self, state, output, **_kwargs):
        if not state.is_last_command:
            return
        JunosRoutingReports().show_arp_no_resolve(state, output)

    def _print_lldp_neighbors(self, state, output, **_kwargs):
        JunosRoutingReports().show_lldp_neighbors(state, output)

    def _print_vlans(self, state, output, **_kwargs):
        JunosRoutingReports().show_vlans(state, output)

    def _print_lacp_interfaces(self, state, output, **_kwargs):
        JunosRoutingReports().show_lacp_interfaces(state, output)

    def _show_ethernet_switching_table(self, state, arguments, output, **_kwargs):
        if not state.is_last_command:
            return
        EthernetSwitchingReport()._show_table_instance(state, output, arguments, **_kwargs)

    def _print_route(self, state, output, **_kwargs):
        if not state.is_last_command:
            return
        JunosRoutingReports().show_route(state, output)

    def _print_route_summary(self, state, output, **_kwargs):
        JunosRoutingReports().show_route_summary(state, output)

    def _print_bgp_summary(self, state, output, **_kwargs):
        JunosRoutingReports().show_bgp_summary(state, output)

    def _print_ospf_neighbor(self, state, output, **_kwargs):
        JunosRoutingReports().show_ospf_neighbor(state, output)

    def _print_isis_adjacency(self, state, output, **_kwargs):
        JunosRoutingReports().show_isis_adjacency(state, output)
