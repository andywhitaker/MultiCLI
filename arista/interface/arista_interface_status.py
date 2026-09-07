"""
Arista eos Interface Status
Author: Mohammad Zaman
Email: mohammad.zaman@nokia.com

This code is a plugin for SR Linux CLI that provides detailed information about physical network interfaces in Arista format,
        Arista command: show interface status
        SRLinux command: show interface  brief
        Current usage on SRLinux: show eos interface status

        This plugin will be updated to exact Arista CLI in 25.3.2 and 24.10.4
"""

from srlinux.data import ColumnFormatter, Data, Borders, ColumnFormatter, Alignment
from srlinux.location import build_path
from srlinux.schema import FixedSchemaRoot
from srlinux.syntax import Syntax


try:
    from arista_interface_reports import format_arista_intf
except ImportError:
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
        return name


class InterfaceStatus(object):
    def get_syntax_status(self):
        result = Syntax('status', help='Show arista interface status for interfaces')
        return result

    def get_data_schema(self):
        root = FixedSchemaRoot()
        root.add_child(
            'IfBrief',
            key='Port',
            fields=['Name', 'Status', 'vlan', 'Duplex', 'Speed', 'Type'],
        )
        return root

    def print(self, state, arguments, output, **_kwargs):
        serve_data = self._stream_data(state, arguments)
        result = Data(arguments.schema)
        self._set_formatters(result)
        with output.stream_data(result):
            self._populate_data(result, serve_data)

    def _stream_data(self, state, arguments):
        intf_name = '*'
        try:
            if hasattr(arguments, 'has_node'):
                if arguments.has_node('interface') and arguments.has_argument('name'):
                    intf_name = arguments.get('interface', 'name') or '*'
                elif arguments.has_node('interfaces') and arguments.has_argument('name'):
                    intf_name = arguments.get('interfaces', 'name') or '*'
        except Exception:
            intf_name = '*'
        path = build_path('/interface[name={name}]', name=intf_name)
        return state.server_data_store.stream_data(path, recursive=False, include_container_children=True)

    def _populate_data(self, data, serve_data):
        data.synchronizer.flush_fields(data)
        for interface in serve_data.interface.items():
            disp_name = format_arista_intf(interface.name, short=False)
            child = data.ifbrief.create(disp_name)
            child.name = getattr(interface, 'description', '') or '--'
            child.status = "notconnected"
            if getattr(interface, 'oper_state', '') == "up":
                child.status = "connected"                
            child.vlan = "routed" if getattr(interface, 'oper_state', '') == "up" else "--"
            if getattr(interface, 'vlan_tagging', False):
                child.vlan = "trunk"
            child.duplex = "full"
            child.speed = "--"
            if hasattr(interface, 'ethernet') and interface.ethernet.exists():
                try:
                    eth_node = interface.ethernet.get()
                    if hasattr(eth_node, 'duplex_mode'):
                        d = getattr(eth_node, 'duplex_mode', None)
                        if d:
                            child.duplex = str(d).lower()
                except Exception:
                    pass
                try:
                    eth_node = interface.ethernet.get()
                    if hasattr(eth_node, 'port_speed') and eth_node.port_speed:
                        child.speed = str(eth_node.port_speed)
                except Exception:
                    pass

            child.type = "--"
            if hasattr(interface, 'transceiver') and interface.transceiver.exists():
                try:
                    xcvr_node = interface.transceiver.get()
                    if hasattr(xcvr_node, 'ethernet_pmd') and xcvr_node.ethernet_pmd:
                        child.type = str(xcvr_node.ethernet_pmd)
                    elif hasattr(xcvr_node, 'form_factor') and xcvr_node.form_factor:
                        child.type = str(xcvr_node.form_factor)
                except Exception:
                    pass
            child.synchronizer.flush_fields(child)
        data.synchronizer.flush_children(data.ifbrief)

    def _set_formatters(self, interface_data):
        # data = interface_data
        formatter = ColumnFormatter(
            borders=Borders.Nothing,
            horizontal_alignment={
                'Port': Alignment.Left,
                'Name': Alignment.Left,
                'Status': Alignment.Right,
                'vlan': Alignment.Center,
                'Duplex': Alignment.Center,
                'Speed': Alignment.Center,
                'Type': Alignment.Left
            },
            widths={
                'Port': 14,
                'Name': 10,
                'Status': 14,
                'vlan': 10,
                'Duplex': 10,
                'Speed': 10,
                'Type': 10
            }

        )
        interface_data.set_formatter('/IfBrief', formatter)