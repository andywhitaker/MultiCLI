# Custom CLI Plugins for Arista EOS

MultiCLI allows users to execute familiar Arista EOS commands on Nokia SR Linux switches with matching output and dynamic state learning.

## Supported Commands

### System & Hardware
| Command | Description |
|---|---|
| `show version` | Arista EOS software version, uptime, memory, and model info |
| `show hostname` | System FQDN and hostname |
| `show clock` | System clock and timezone |
| `show inventory` | System inventory and hardware serials |
| `show environment [cooling\|power\|temperature]` | Fan speeds, power supplies, and temperature sensors |
| `show module` | Linecard, supervisor, and fabric module status |
| `show processes top once` | Process table and memory/swap statistics |

### Interfaces & Layer 2
| Command | Description |
|---|---|
| `show ip interface brief` | IPv4 address and operational status per interface |
| `show interfaces description` / `show interface description` | Interface descriptions and line protocol status |
| `show interfaces transceiver [detail]` / `show interface transceiver [detail]` | Optical transceiver diagnostics and DDM |
| `show port-channel summary` | LAG / Port-channel summary with protocol and member ports |
| `show mac address-table` | MAC address table with VLAN, type, and interface |
| `show vlan` | Configured VLANs, status, and member ports |
| `show mlag` | MLAG operational status, peer link, and multi-homing ES |

### Routing & Protocols
| Command | Description |
|---|---|
| `show ip route [vrf default]` | Routing table with protocol codes and next-hops |
| `show vrf` | VRF routing instances, protocols, and interfaces |
| `show ip arp` | ARP cache resolution table |
| `show ip bgp summary` | BGP IPv4 unicast neighbor summary |
| `show bgp evpn summary` | BGP EVPN neighbor summary |
| `show bgp evpn route-type [auto-discovery\|mac-ip\|imet\|ethernet-segment\|ip-prefix]` | BGP EVPN route-type specific outputs |
| `show ip ospf neighbor` | OSPF neighbor adjacencies and states |
| `show ip ospf interface brief` | OSPF interface state, cost, and area |
| `show isis neighbors` | IS-IS neighbor adjacencies and hold times |
| `show lldp neighbors [detail]` | LLDP discovery neighbors and details |

## Testing

Deploy the containerlab topology and log in to a switch configured with the Arista EOS persona (or use `auser/auser`):

```bash
docker exec -it leaf1 sr_cli
```

Or switch any node on-the-fly using the helper script:
```bash
./switch-multicli.sh arista leaf1
```

## Custom CLI Plugin scripts

This folder contains custom CLI python scripts for EOS commands.

The scripts are arranged in this format. The main_arista.py checks the imports in the shown path below

```
/home/auser/cli
├── bgp
│   └── bgp_evpn_report.py            # Handles BGP EVPN Route Type and summary reports
│
├── interface
│   ├── arista_arp_details.py         # Parses and formats ARP entries
│   ├── arista_interface_detail.py    # Displays detailed interface info (Arista style)
│   ├── arista_interface_reports.py   # Interface brief, transceiver, description, LLDP, LAG
│   └── arista_interface_status.py    # Displays brief interface status (Arista style)
│
├── ip
│   └── arista_ip_bgp_report.py       # Generates standard BGP summary reports
│
├── plugins
│   └── main_arista.py                # Loads Arista-style CLI plugins
│
├── routing
│   └── arista_routing_reports.py     # IP route, VRF, VLAN, MAC, OSPF, IS-IS, MLAG
│
└── system
    └── arista_system_reports.py      # Version, hostname, clock, inventory, environment
```

### Verification commands:

**Interface Status**:
```
show eos interface status
```

**Interface Details**:
```
show eos interface {interface_name}
```
*OR, to list all interfaces*

```
show eos interface
```

**ARP Details**:
```
show eos arp
```
OR, to provide optional arguments,

```
show eos arp interface {interface_name}
```

