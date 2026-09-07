#!/usr/bin/python
###########################################################################
# Description: MultiCLI Plugin for Arista EOS Commands
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
    try:
        from arista_ip_bgp_report import IpBgpReport as BaseBgpReport
    except ImportError:
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

from srlinux.mgmt.cli.lazy_loader_utils import wait_for_show_reports_load
from srlinux.mgmt.cli.cli_mode import CliMode
from srlinux.mgmt.cli.cli_state import CliState
from srlinux.schema.data_store import DataStore
import os

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
        self._add_or_override(
            target,
            Syntax('version', help='Show system version in Arista EOS format'),
            callback=self._print_version,
            update_location=False
        )

        self._add_or_override(
            target,
            Syntax('hostname', help='Show system hostname'),
            callback=self._print_hostname,
            update_location=False
        )

        self._add_or_override(
            target,
            Syntax('clock', help='Show system clock in Arista EOS format'),
            callback=self._print_clock,
            update_location=False
        )

        self._add_or_override(
            target,
            Syntax('inventory', help='Show system hardware inventory'),
            callback=self._print_inventory,
            update_location=False
        )

        env_cmd = self._add_or_override(
            target,
            Syntax('environment', help='Show environment status'),
            callback=self._print_environment_all,
            update_location=False
        )
        self._add_or_override(
            env_cmd,
            Syntax('cooling', help='Show cooling status'),
            callback=self._print_environment_cooling,
            update_location=False
        )
        self._add_or_override(
            env_cmd,
            Syntax('power', help='Show power supply status'),
            callback=self._print_environment_power,
            update_location=False
        )
        self._add_or_override(
            env_cmd,
            Syntax('temperature', help='Show temperature status'),
            callback=self._print_environment_temp,
            update_location=False
        )

        self._add_or_override(
            target,
            Syntax('module', help='Show module information in Arista EOS format'),
            callback=self._print_module,
            update_location=False
        )

        proc_cmd = self._add_or_override(
            target,
            Syntax('processes', help='Show process information in Arista EOS format'),
            update_location=False
        )
        proc_top = self._add_or_override(
            proc_cmd,
            Syntax('top', help='Show top processes'),
            update_location=False
        )
        self._add_or_override(
            proc_top,
            Syntax('once', help='Show top processes once'),
            callback=self._print_processes_top_once,
            update_location=False
        )

        self._add_or_override(
            target,
            Syntax('mlag', help='Show MLAG information in Arista EOS format'),
            callback=self._print_mlag,
            update_location=False
        )

        # 2. IP Commands: show ip bgp, show ip route, show ip interface brief, show ip arp, show ip ospf
        ip = self._add_or_override(
            target,
            Syntax('ip', help='display ip protocol information'),
            update_location=False
        )

        bgp = self._add_or_override(
            ip,
            Syntax('bgp', help='show bgp information'),
            update_location=False
        )
        self._add_or_override(
            bgp,
            Syntax('summary')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]')),
            callback=self._print_summary,
            update_location=False
        )
        bgp_vrf = self._add_or_override(
            bgp,
            Syntax('vrf').add_unnamed_argument('vrf_name', suggestions=KeyCompleter('/network-instance[name=*]')),
            update_location=False
        )
        self._add_or_override(
            bgp_vrf,
            Syntax('summary', help='BGP summary for VRF'),
            callback=self._print_vrf_bgp_summary,
            update_location=False
        )

        # IP Route
        ip_route = self._add_or_override(
            ip,
            Syntax('route', help='IP routing table'),
            callback=self._print_ip_route,
            update_location=False
        )
        self._add_or_override(
            ip_route,
            Syntax('vrf').add_unnamed_argument('vrf_name', suggestions=KeyCompleter('/network-instance[name=*]')),
            callback=self._print_vrf_route,
            update_location=False
        )

        # IP Interface Brief
        ip_intf = self._add_or_override(
            ip,
            Syntax('interface', help='IP interface information'),
            update_location=False
        )
        self._add_or_override(
            ip_intf,
            Syntax('brief', help='IP interface brief'),
            callback=self._print_ip_interface_brief,
            update_location=False
        )

        # IP ARP
        self._add_or_override(
            ip,
            Syntax('arp', help='IP ARP table'),
            callback=self._print_ip_arp,
            update_location=False
        )

        # IP OSPF
        ip_ospf = self._add_or_override(
            ip,
            Syntax('ospf', help='IP OSPF information'),
            update_location=False
        )
        self._add_or_override(
            ip_ospf,
            Syntax('neighbor', help='OSPF neighbors'),
            callback=self._print_ospf_neighbor,
            update_location=False
        )
        ospf_intf = self._add_or_override(
            ip_ospf,
            Syntax('interface', help='OSPF interface information'),
            update_location=False
        )
        self._add_or_override(
            ospf_intf,
            Syntax('brief', help='OSPF interface brief'),
            callback=self._print_ospf_interface_brief,
            update_location=False
        )

        # 3. EVPN Commands
        bgp_root = self._add_or_override(
            target,
            Syntax('bgp', help='display bgp information'),
            update_location=False
        )

        evpn = self._add_or_override(
            bgp_root,
            Syntax('evpn', help='show EVPN information'),
            update_location=False
        )
        self._add_or_override(
            evpn,
            Syntax('summary')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]')),
            callback=self._print_evpn_summary,
            update_location=False
        )
        route_type = self._add_or_override(
            evpn,
            Syntax('route-type', help='specify the EVPN route type'),
            update_location=False
        )
        self._add_or_override(
            route_type,
            Syntax('auto-discovery')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]'))
            .add_named_argument('esi', default='*', help='ESI value'),
            callback=self._print_1,
            update_location=False
        )
        self._add_or_override(
            route_type,
            Syntax('mac-ip')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]'))
            .add_named_argument('mac-address', default='*', help='MAC address'),
            callback=self._print_2,
            update_location=False
        )
        self._add_or_override(
            route_type,
            Syntax('imet')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]'))
            .add_named_argument('origin-router', default='*', help='Originating router IPv4 or IPv6 address'),
            callback=self._print_3,
            update_location=False
        )
        self._add_or_override(
            route_type,
            Syntax('ethernet-segment')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]'))
            .add_named_argument('esi', default='*', help='ESI value'),
            callback=self._print_4,
            update_location=False
        )
        self._add_or_override(
            route_type,
            Syntax('ip-prefix')
            .add_named_argument('vrf', default='default', help='network instance name', suggestions=KeyCompleter('/network-instance[name=*]'))
            .add_named_argument('ip-address', default='*', help='IPv4 or IPv6 address prefix'),
            callback=self._print_5,
            update_location=False
        )

        # 4. Interfaces Commands: show interfaces status, description, detail
        intfs_syntax = Syntax('interfaces', help='Interface status and information')
        intfs_syntax.add_unnamed_argument(
            'name', default='*', suggestions=MultipleKeyCompleters(keycompleters=[KeyCompleter(path="/interface[name=*]")])
        )
        intfs = self._add_or_override(
            target,
            intfs_syntax,
            callback=self._interface_details,
            update_location=False
        )
        self._add_or_override(
            intfs,
            InterfaceStatus().get_syntax_status(),
            update_location=False,
            callback=self._interface_status,
            schema=InterfaceStatus().get_data_schema()
        )
        self._add_or_override(
            intfs,
            Syntax('description', help='Interface descriptions'),
            callback=self._print_interfaces_description,
            update_location=False
        )
        intfs_xcvr = self._add_or_override(
            intfs,
            Syntax('transceiver', help='Transceiver and DDM status in Arista EOS format'),
            callback=self._print_interfaces_transceiver,
            update_location=False
        )
        self._add_or_override(
            intfs_xcvr,
            Syntax('detail', help='Transceiver detail'),
            callback=self._print_interfaces_transceiver_detail,
            update_location=False
        )

        # Also support on 'interface' singular
        intf_singular = self._add_or_override(
            target,
            InterfaceDetails().get_syntax_details(),
            callback=self._interface_details,
            update_location=False
        )
        self._add_or_override(
            intf_singular,
            InterfaceStatus().get_syntax_status(),
            update_location=False,
            callback=self._interface_status,
            schema=InterfaceStatus().get_data_schema()
        )
        self._add_or_override(
            intf_singular,
            Syntax('description', help='Interface descriptions'),
            callback=self._print_interfaces_description,
            update_location=False
        )
        s_xcvr = self._add_or_override(
            intf_singular,
            Syntax('transceiver', help='Transceiver and DDM status in Arista EOS format'),
            callback=self._print_interfaces_transceiver,
            update_location=False
        )
        self._add_or_override(
            s_xcvr,
            Syntax('detail', help='Transceiver detail'),
            callback=self._print_interfaces_transceiver_detail,
            update_location=False
        )

        # 5. LLDP Commands
        lldp_node = self._add_or_override(
            target,
            Syntax('lldp', help='LLDP information'),
            update_location=False
        )
        lldp_neigh = self._add_or_override(
            lldp_node,
            Syntax('neighbors', help='LLDP neighbors in Arista format'),
            callback=self._print_lldp_neighbors,
            update_location=False
        )
        self._add_or_override(
            lldp_neigh,
            Syntax('detail', help='LLDP neighbors detail'),
            callback=self._print_lldp_neighbors_detail,
            update_location=False
        )
        lldp_single = self._add_or_override(
            lldp_node,
            Syntax('neighbor', help='LLDP neighbors in Arista format'),
            callback=self._print_lldp_neighbors,
            update_location=False
        )
        self._add_or_override(
            lldp_single,
            Syntax('detail', help='LLDP neighbors detail'),
            callback=self._print_lldp_neighbors_detail,
            update_location=False
        )

        # 6. MAC Table Commands
        mac_node = self._add_or_override(
            target,
            Syntax('mac', help='MAC information'),
            update_location=False
        )
        self._add_or_override(
            mac_node,
            Syntax('address-table', help='MAC address table'),
            callback=self._print_mac_address_table,
            update_location=False
        )

        # 7. VRF & VLAN Commands
        self._add_or_override(
            target,
            Syntax('vrf', help='VRF information in Arista format'),
            callback=self._print_vrf,
            update_location=False
        )
        self._add_or_override(
            target,
            Syntax('vlan', help='VLAN information in Arista format'),
            callback=self._print_vlan,
            update_location=False
        )

        # 8. Port-Channel Commands
        pc_node = self._add_or_override(
            target,
            Syntax('port-channel', help='Port-Channel information'),
            update_location=False
        )
        self._add_or_override(
            pc_node,
            Syntax('summary', help='Port-Channel summary in Arista format'),
            callback=self._print_port_channel_summary,
            update_location=False
        )

        # 9. IS-IS Commands
        isis_node = self._add_or_override(
            target,
            Syntax('isis', help='IS-IS information'),
            update_location=False
        )
        self._add_or_override(
            isis_node,
            Syntax('neighbors', help='IS-IS neighbors in Arista format'),
            callback=self._print_isis_neighbors,
            update_location=False
        )

    def load(self, cli, **_kwargs):
        self._cli = cli
        # 1. Root global command 'eos' for interactive submode and one-liners:
        # e.g., 'eos show version' or entering 'eos' mode
        eos_node = cli.add_global_command(
            Syntax('eos', help='Arista EOS operational mode and commands'),
            update_location=_enter_submode
        )
        eos_show = self._add_or_override(
            eos_node,
            Syntax('show', help='Arista EOS show reports'),
            update_location=False
        )
        self._register_all_commands(eos_show)

        # Also support arp on eos_show
        self._add_or_override(
            eos_show,
            ArpDetails()._get_syntax_arp(),
            update_location=False,
            callback=self._arp_entries,
            schema=ArpDetails()._get_arp_schema(True)
        )

    def on_start(self, state):
        if not should_register_show_mode('arista'):
            return
        # 2. Register to show_mode for persona compatibility (e.g. auser)
        wait_for_show_reports_load(state)
        self._register_all_commands(state.command_tree.show_mode)

        # 3. Legacy 'show eos ...' container preserved for compatibility
        eos_legacy = self._add_or_override(state.command_tree.show_mode, Syntax('eos', help='Show Arista EOS reports'), update_location=False)
        eos_interfaces = self._add_or_override(
            eos_legacy,
            InterfaceDetails().get_syntax_details(),
            update_location=False,
            callback=self._interface_details
        )
        self._add_or_override(
            eos_interfaces,
            InterfaceStatus().get_syntax_status(),
            update_location=False,
            callback=self._interface_status,
            schema=InterfaceStatus().get_data_schema()
        )
        self._add_or_override(
            eos_legacy,
            ArpDetails()._get_syntax_arp(),
            update_location=False,
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

    def _print_vrf_bgp_summary(self, state, arguments, output, **_kwargs):
        netinst = arguments.get('vrf', 'vrf_name') if arguments.has_node('vrf') else 'default'
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
