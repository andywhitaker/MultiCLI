# Custom CLI Plugins for Cisco NX-OS

MultiCLI allows users to execute familiar Cisco NX-OS commands on Nokia SR Linux switches with matching output and dynamic state learning.

## Supported Commands

### System & Hardware
| Command | Description |
|---|---|
| `show version` | System version, uptime, and hardware details |
| `show hostname` | System hostname |
| `show clock` | System clock and time zone |
| `show inventory` | Hardware inventory and chassis serials |
| `show environment [cooling\|power\|temperature]` | Fan speeds, power supplies, and temperature sensors |
| `show module` | Linecard, control module, and fabric status |
| `show processes cpu` | System and CPU utilization statistics |

### Interfaces & Layer 2
| Command | Description |
|---|---|
| `show interface brief` / `show interfaces brief` | Brief summary of physical, LAG, and subinterfaces |
| `show interface status` | Port status, speed, duplex, and type |
| `show interface description` | Interface descriptions |
| `show interface transceiver [details]` | Optical transceiver diagnostics and DDM |
| `show ip interface brief` | IPv4 address and operational state per interface |
| `show ipv6 interface brief` | IPv6 address and operational state per interface |
| `show port-channel summary` | LAG / Port-channel status and member ports |
| `show mac address-table` | MAC address table with VLAN, type, and age |
| `show mac address-table vlan <id>` | Filter MAC table by VLAN |
| `show mac address-table interface <name>` | Filter MAC table by interface |
| `show mac address-table vni <vni_id>` | Filter MAC table by EVPN VNI |
| `show vlan` | Configured VLANs, status, and member ports |

### Routing, Protocols & EVPN
| Command | Description |
|---|---|
| `show ip route [vrf default]` | IPv4 routing table with next hops and protocols |
| `show vrf` | VRF instances, state, and route distinguishers |
| `show ip arp` | ARP cache resolution table |
| `show ip bgp summary` | BGP neighbor summary, prefixes, and session states |
| `show bfd neighbors` | BFD session states, intervals, and diagnostics |
| `show ip ospf neighbor` | OSPF neighbor adjacencies and states |
| `show ip ospf interface brief` | OSPF enabled interfaces, areas, and costs |
| `show lldp neighbors [detail]` | LLDP discovery neighbors and port information |
| `show nve vni` | NVE VXLAN VNI mappings and states |
| `show nve peers` | NVE VTEP tunnel peers |
| `show vpc` | Virtual Port Channel / Multi-homing status |

## Testing

Deploy the containerlab topology and log in to a switch configured with the Cisco NX-OS persona (or use `cnxuser/cnxuser`):

```bash
docker exec -it leaf2 sr_cli
```

Or switch any node on-the-fly using the helper script:
```bash
./switch-multicli.sh cisco leaf1
```
