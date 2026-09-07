"""
CLI Plugin for SR Linux for Cisco-style IP Interface Command
Provides alternate command syntax for interface information
Author: Alperen Akpinar
Email: alperen.akpinar@nokia.com
"""
import sys
import os
import re
from srlinux.location import build_path
from srlinux.data import ColumnFormatter, Data, Borders, Alignment, Border
from srlinux.schema import FixedSchemaRoot

# Add interface directory to sys.path if not present
interface_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'interface'))
if interface_dir not in sys.path:
    sys.path.insert(0, interface_dir)

try:
    from cisco_interface_reports import format_cisco_intf, cisco_intf_sort_key
except ImportError:
    def format_cisco_intf(name, short=True):
        if not name:
            return "-"
        name = str(name).strip()
        if name.startswith('ethernet-'):
            num = name.split('-', 1)[1]
            return f"Eth{num}" if short else f"Ethernet{num}"
        elif name.startswith('mgmt'):
            return name
        elif name.startswith('system0'):
            return "Lo0" if short else "Loopback0"
        elif name.startswith('lo'):
            num = name[2:]
            return f"Lo{num}" if short else f"Loopback{num}"
        elif name.startswith('lag'):
            num = name.split('lag', 1)[1]
            return f"Po{num}" if short else f"Port-channel{num}"
        elif name.startswith('irb'):
            return name
        elif name.startswith('vlan'):
            num = re.split(r'vlan', name)[-1]
            return f"Vlan{num}"
        return name

    def cisco_intf_sort_key(name):
        if not name:
            return (99, [0], "")
        lower = str(name).lower()
        type_priority = 5
        if lower.startswith(('eth', 'ethernet')):
            type_priority = 0
        elif lower.startswith(('lo', 'loopback')):
            type_priority = 1
        elif lower.startswith('mgmt'):
            type_priority = 2
        elif lower.startswith(('po', 'port-channel')):
            type_priority = 3
        elif lower.startswith(('vlan', 'irb')):
            type_priority = 4
        digits = [int(p) for p in re.findall(r'\d+', lower)]
        return (type_priority, digits or [0], lower)

class IpInterfaceReport:
    def _get_schema(self):
        root = FixedSchemaRoot()
        interfaces = root.add_child(
            'interfaces',
            fields=['header']
        )
        interfaces.add_child(
            'interface',  # This must be lowercase
            key='Interface',  # This is what shows up in output
            fields=[
                'IP-Address',
                'Interface-Status', 
                'Protocol-Status',
                'VRF'
            ]
        )
        return root

    def _fetch_state(self, state):
        # Get interface data with recursive=True to get all nested data including IP addresses
        interface_path = build_path('/interface[name=*]')
        self.interface_data = state.server_data_store.get_data(interface_path, recursive=True)
        
        # Get network-instance interface mapping
        ni_path = build_path('/network-instance[name=*]/interface[name=*]')
        self.ni_data = state.server_data_store.get_data(ni_path, recursive=True)
    
    def _get_interface_vrf(self, interface_name):
        # Normalize interface name for matching
        normalized_name = interface_name.replace('Ethernet', 'ethernet-')
        
        # If no network instance data, return empty string
        if not hasattr(self.ni_data, 'network_instance'):
            return ""
        
        # Iterate through network instances
        for ni in self.ni_data.network_instance.items():
            # Check if this network instance has interfaces
            if hasattr(ni, 'interface'):
                for intf in ni.interface.items():
                    # Compare normalized interface names, including subinterface
                    if intf.name == normalized_name or intf.name.startswith(normalized_name + '.'):
                        return ni.name
        
        # If no VRF found
        return ""

    def _format_interface_name(self, base_name, subindex=None):
        if base_name.startswith('ethernet-'):
            name = f"Ethernet{base_name[9:]}"
        elif base_name.startswith('lo'):
            name = f"Loopback{base_name[2:]}"
        elif base_name.startswith('vlan'):
            name = f"Vlan{base_name[4:]}"
        else:
            name = base_name

        if subindex is not None and subindex != 0:
            return f"{name}.{subindex}"
        return name

    def _set_formatters(self, data):
        formatter = ColumnFormatter(
            borders=Borders.Nothing,
            horizontal_alignment={
                'Interface': Alignment.Left,
                'IP-Address': Alignment.Left,
                'Interface-Status': Alignment.Left,
                'Protocol-Status': Alignment.Left,
                'VRF': Alignment.Center
            },
            widths={
                'Interface': 16,         # Fixed width for Interface
                'IP-Address': 15,        # Enough for IPs like 192.168.100.1/24
                'Interface-Status': 16,  # Wide enough for 'admin down' text
                'Protocol-Status': 16,   # Wide enough for 'up' or 'down'
                'VRF': 15                # Adjust as needed
            }
        )
    
        # Apply borders correctly
        bordered_formatter = Border(
            formatter, 
            position=Border.Above | Border.Below,  # Add borders above and below
            character='-'  # Border character
        )
    
        data.set_formatter('/interfaces/interface', bordered_formatter)
    
    def _populate_data(self, result, state):
        result.synchronizer.flush_fields(result)
        data = result.interfaces.create()
        data.header = ""
        self._fetch_state(state)
        processed_interfaces = set()  # Change to a set for faster lookup
        
        # Process all interfaces
        for interface in self.interface_data.interface.items():
            base_name = interface.name
            
            if hasattr(interface, 'subinterface'):
                for subif in interface.subinterface.items():
                    intf_name = self._format_interface_name(base_name, subif.index)
                    
                    # Use set to check and prevent duplicates
                    if intf_name in processed_interfaces:
                        continue
                    processed_interfaces.add(intf_name)
                    
                    # Change this block to prevent multiple data_child creation
                    try:
                        data_child = data.interface.create(intf_name)
                    except Exception as e:
                        # If interface already exists, skip
                        continue
                    
                    # Rest of the code remains the same
                    ip_address = "unassigned"
                    if hasattr(subif, 'ipv4'):
                        ipv4 = subif.ipv4.get()
                        try:
                            for addr in ipv4.address.items():
                                full_prefix = getattr(addr, 'ip_prefix', 'unassigned')
                                ip_address = full_prefix.split('/')[0] if full_prefix != 'unassigned' else full_prefix
                                break
                        except Exception:
                            pass
                    
                    # Get states
                    admin_state = getattr(subif, 'admin_state', 'disable')
                    oper_state = getattr(subif, 'oper_state', 'down')
                    
                    if admin_state == "enable":
                        if oper_state == "up":
                            intf_status = "up"
                            proto_status = "up"
                        else:
                            intf_status = "up"
                            proto_status = "down"
                    else:
                        intf_status = "admin down"
                        proto_status = "down"
                    
                    data_child.ip_address = ip_address
                    data_child.interface_status = intf_status
                    data_child.protocol_status = proto_status
                    data_child.vrf = self._get_interface_vrf(intf_name)
                    data_child.synchronizer.flush_fields(data_child)
            
            # Handle unconfigured interfaces
            if base_name not in processed_interfaces:
                intf_name = self._format_interface_name(base_name)
                
                # Check if interface already exists to prevent duplicate
                if intf_name not in processed_interfaces:
                    processed_interfaces.add(intf_name)
                    
                    data_child = data.interface.create(intf_name)
                    data_child.ip_address = "unassigned"
                    data_child.interface_status = "admin down"
                    data_child.protocol_status = "down"
                    data_child.vrf = ""
                    data_child.synchronizer.flush_fields(data_child)
        
        result.synchronizer.flush_children(result.interfaces)
        return result

    def show_interfaces_brief(self, state, output):
        """Main function to display interface brief"""
        result = Data(self._get_schema())
        self._set_formatters(result)
        with output.stream_data(result):
            self._populate_data(result, state)

    def show_ip_interface_brief(self, state, output, vrf='default'):
        """Display Cisco NX-OS style 'show ip interface brief'."""
        self._fetch_state(state)
        # Determine VRF ID
        vrf_id = 1
        if vrf != 'default':
            try:
                ni_list = list(self.ni_data.network_instance.items())
                for idx, ni in enumerate(ni_list, 1):
                    if getattr(ni, 'name', '') == vrf:
                        vrf_id = idx
                        break
            except Exception:
                vrf_id = 1

        lines = [
            f'IP Interface Status for VRF "{vrf}"({vrf_id})',
            f"{'Interface':<20} {'IP Address':<15} {'Interface Status'}"
        ]

        entries = []
        for interface in self.interface_data.interface.items():
            base_name = interface.name
            if hasattr(interface, 'subinterface'):
                for subif in interface.subinterface.items():
                    sub_idx = subif.index
                    intf_name = self._format_interface_name(base_name, sub_idx)
                    intf_vrf = self._get_interface_vrf(intf_name) or "default"
                    if intf_vrf != vrf:
                        continue

                    ip_address = ""
                    if hasattr(subif, 'ipv4') and subif.ipv4.exists():
                        try:
                            for addr in subif.ipv4.get().address.items():
                                pfx = getattr(addr, 'ip_prefix', '')
                                if pfx:
                                    ip_address = pfx.split('/')[0]
                                    break
                        except Exception:
                            pass

                    if not ip_address:
                        continue

                    admin = getattr(subif, 'admin_state', 'disable')
                    oper = getattr(subif, 'oper_state', 'down')
                    proto_str = "proto-up" if oper == "up" else "proto-down"
                    link_str = "link-up" if oper == "up" else "link-down"
                    admin_str = "admin-up" if admin == "enable" else "admin-down"
                    status_str = f"{proto_str}/{link_str}/{admin_str}"

                    # Short interface name like Eth1/1, Lo0, mgmt0, Vlan1
                    short_name = format_cisco_intf(intf_name, short=True)

                    entries.append({
                        'name': short_name,
                        'ip': ip_address,
                        'status': status_str
                    })

        entries.sort(key=lambda e: cisco_intf_sort_key(e['name']))
        for e in entries:
            lines.append(f"{e['name']:<20} {e['ip']:<15} {e['status']}")

        output.print_line("\n".join(lines))
        output.print_line("\n----------------------------------------------------------------------------------------------------")
        output.print_line("Try SR Linux command: show interface brief")