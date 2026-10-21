#!/usr/bin/env python3
"""
validate_multicli.py
Automated validation harness for all MultiCLI commands across
Arista EOS (leaf1-1), Cisco NX-OS (leaf1-2), Juniper JUNOS (leaf2-1), and Nokia SR OS (leaf2-2).
"""

import os
import re
import subprocess
import sys
import time

TEST_SUITES = {
    "Arista EOS": {
        "arg_key": "arista_node",
        "default_node": "leaf1-1",
        "commands": [
            "show version",
            "show hostname",
            "show clock",
            "show inventory",
            "show environment",
            "show environment cooling",
            "show environment power",
            "show environment temperature",
            "show ip interface brief",
            "show interfaces description",
            "show interfaces transceiver",
            "show interfaces transceiver detail",
            "show module",
            "show processes top once",
            "show lldp neighbors",
            "show lldp neighbors detail",
            "show ip arp",
            "show port-channel summary",
            "show ip route",
            "show ip route vrf default",
            "show vrf",
            "show vlan",
            "show mac address-table",
            "show ip ospf neighbor",
            "show ip ospf interface brief",
            "show isis neighbors",
            "show mlag",
            "show ip bgp summary",
            "show ip bgp vrf default summary",
            "show bgp evpn summary",
            "show interfaces status",
            "show eos interface ethernet-1/1",
            "eos show version",
            "eos show hostname",
            "eos show ip route",
            "eos show interfaces",
            "eos show interfaces ethernet-1/1",
            "eos show interfaces status",
        ],
        "submode_tests": [
            ("eos", ["show hostname", "show version"], "Nokia 7220 IXR-D2L"),
            ("eos", ["show interfaces ethernet-1/1"], "ethernet-1/1 is up"),
            ("eos", ["show interfaces", "show interfaces status"], "Ethernet1/1"),
            ("nxos", ["show hostname", "show version"], "Nokia SR Linux Software"),
            ("junos", ["show version"], "Hostname:"),
            ("sros", ["show version"], "SRLinux-"),
        ],
        "negative_assertions": [
            ("show environment cooling", "System Temperature", "show environment cooling should not trigger intermediate show environment all"),
            ("show environment power", "System Temperature", "show environment power should not trigger intermediate show environment all"),
            ("show lldp neighbors detail", "Last table change time", "show lldp neighbors detail should not trigger intermediate show lldp neighbors summary"),
            ("show lldp neighbors", "0:01:00 ago", "show lldp neighbors should not output hardcoded fake timestamp '0:01:00 ago'"),
            ("show ip route", "S       10.1.10.0/24", "Local/connected subnet should be classified as C or L, not S"),
            ("show vlan", "--    mac-vrf-1", "show vlan should dynamically derive VLAN tag rather than '--'"),
            ("show vlan", "Vlan1", "show vlan should not convert IRB interface to Vlan1"),
            ("show mac address-table", "Vlan--", "show mac address-table should not output 'Vlan--'"),
            ("show mac address-table", "Vlan1", "show mac address-table should not convert IRB interface to Vlan1"),
            ("show eos interface ethernet-1/1", "packets/sec", "show eos interface detail should not output unsupported packets/sec metric"),
            ("show interfaces status", "with framing overhead", "show interfaces status should not output interface detail"),
            ("show interfaces description", "with framing overhead", "show interfaces description should not output interface detail"),
            ("show interfaces transceiver", "with framing overhead", "show interfaces transceiver should not output interface detail"),
            ("eos show interfaces status", "with framing overhead", "eos show interfaces status should not output interface detail"),
            ("show ip route", "ipv4 route", "show ip route must not recommend invalid ipv4 route command"),
            ("show eos interface ethernet-1/1", "{interface_name}", "show eos interface detail must not contain unrendered {interface_name} placeholder"),
            ("show mac address-table", "<instance>", "show mac address-table must not contain <instance> placeholder"),
        ],
        "positive_assertions": [
            ("show mac address-table", "Try SR Linux command: show network-instance bridge-table mac-table all", "show mac address-table must recommend valid SRL command"),
            ("show ip route", "Gateway of last resort", "show ip route must contain Gateway of last resort header"),
            ("show ip route", "Try SR Linux command: show network-instance default route-table ipv4-unicast summary", "show ip route must recommend valid SRL route-table command"),
            ("show vlan", "Try SR Linux command: show network-instance summary", "show vlan must recommend valid SRL network-instance summary command"),
            ("show ip arp", "Age (min)", "show ip arp must contain Age (min) column"),
            ("show interfaces status", "Ethernet1/1", "show interfaces status must format interfaces in Arista style EthernetX/Y"),
            ("show ip bgp vrf default summary", "BGP summary information for VRF default", "show ip bgp vrf default summary must output VRF BGP summary"),
            ("show vlan", "1     mac-vrf-1", "show vlan must dynamically resolve VLAN 1 for mac-vrf-1"),
            ("show vlan", "irb0.0", "show vlan must preserve irb0.0 interface name"),
            ("show mac address-table", "1       0000.5e00.0101", "show mac address-table must dynamically resolve VLAN 1 for IRB MAC"),
            ("show mac address-table", "irb0.0", "show mac address-table must format IRB port as irb0.0"),
            ("show processes top once", "re:\\d+\\s+root\\s+", "show processes top once must list real system processes"),
            ("show ip ospf neighbor", "10.10.10.10", "show ip ospf neighbor must display spine neighbor"),
            ("show ip ospf interface brief", "192.168.10.2/31", "show ip ospf interface brief must display active OSPF interface IP/mask"),
            ("show isis neighbors", "0100.1001.0010", "show isis neighbors must display spine IS-IS adjacency"),
            ("show mlag", "state               : Active", "show mlag must show Active state for operational Ethernet Segment"),
            ("show mlag", "peer-address        : 2.2.2.2", "show mlag must resolve ES peer VTEP address"),
            ("show port-channel summary", "Po1(U)", "show port-channel summary must report Po1(U) for active LAG"),
            ("show eos interface ethernet-1/1", "with framing overhead", "show eos interface detail should output input/output rate with framing overhead"),
            ("eos show version", "Nokia 7220 IXR-D2L", "eos show version must output Arista-formatted version"),
            ("eos show hostname", "leaf1-1", "eos show hostname must output hostname"),
            ("eos show ip route", "Gateway of last resort", "eos show ip route must contain Gateway of last resort header"),
            ("eos show interfaces", "ethernet-1/1 is up", "eos show interfaces must output interface status and statistics"),
            ("eos show interfaces ethernet-1/1", "ethernet-1/1 is up", "eos show interfaces ethernet-1/1 must output interface detail"),
        ]
    },
    "Cisco NX-OS": {
        "arg_key": "cisco_node",
        "default_node": "leaf1-2",
        "commands": [
            "show version",
            "show hostname",
            "show clock",
            "show inventory",
            "show environment",
            "show environment cooling",
            "show environment power",
            "show environment temperature",
            "show module",
            "show processes cpu",
            "show interface brief",
            "show interface status",
            "show interface description",
            "show interface transceiver",
            "show interface transceiver details",
            "show ipv6 interface brief",
            "show port-channel summary",
            "show ip interface brief",
            "show lldp neighbors",
            "show lldp neighbors detail",
            "show ip arp",
            "show ip route",
            "show ip route vrf default",
            "show ip bgp summary",
            "show ip bgp vrf default summary",
            "show mac address-table",
            "show mac address-table vlan 1",
            "show mac address-table vlan 10",
            "show mac address-table interface ethernet-1/2",
            "show mac address-table vni 1",
            "show mac address-table vni 100",
            "show vrf",
            "show vlan",
            "show bfd neighbors",
            "show ip ospf neighbor",
            "show ip ospf interface brief",
            "show nve vni",
            "show nve peers",
            "show vpc",
            "nxos show version",
            "nxos show hostname",
            "nxos show ip route",
            "nxos show interface",
            "nxos show interface ethernet-1/2",
            "nxos show interface brief",
            "nxos show lldp neighbors",
            "nxos show lldp neighbors detail",
            "show interface",
            "show interface ethernet-1/2",
        ],
        "submode_tests": [
            ("nxos", ["show hostname", "show version"], "Nokia SR Linux Software"),
            ("nxos", ["show interface brief", "show interface ethernet-1/2"], "Ethernet1/2 is up"),
            ("nxos", ["show ip route"], "Gateway of last resort"),
            ("eos", ["show hostname", "show version"], "Nokia 7220 IXR-D2L"),
            ("junos", ["show version"], "Hostname:"),
            ("sros", ["show version"], "SRLinux-"),
        ],
        "negative_assertions": [
            ("show ip route", "ethernet-1/2.0", "show ip route should format interface as Eth1/2 rather than ethernet-1/2.0"),
            ("show mac address-table vlan 1", "irb0.2", "show mac address-table vlan 1 should not leak non-matching VLAN 2 entries"),
            ("show mac address-table vlan 10", "irb0.0", "show mac address-table vlan 10 should not return non-matching entries"),
            ("show vlan", "--    mac-vrf-1", "show vlan should dynamically derive VLAN tag rather than '--'"),
            ("show vlan", "Vlan0.", "show vlan should not output synthetic 'Vlan0.' interface names"),
            ("show vlan", "Vlan1", "show vlan should not convert IRB interface to Vlan1"),
            ("show interface brief", "admin state is up, Dedicated Interface", "show interface brief should not output full interface detail"),
            ("show interface status", "admin state is up, Dedicated Interface", "show interface status should not output full interface detail"),
            ("show interface description", "admin state is up, Dedicated Interface", "show interface description should not output full interface detail"),
            ("show interface transceiver", "admin state is up, Dedicated Interface", "show interface transceiver should not output full interface detail"),
            ("nxos show interface brief", "admin state is up, Dedicated Interface", "nxos show interface brief should not output full interface detail"),
            ("show ip route", "ipv4 route", "show ip route must not recommend invalid ipv4 route command"),
            ("show nve vni", "Try SR Linux command: show tunnel-interface\n", "show nve vni must not recommend incomplete show tunnel-interface command"),
            ("show nve peers", "Try SR Linux command: show tunnel-interface vxlan-interface bridge-table\n", "show nve peers must not recommend incomplete bridge-table command"),
            ("show ip ospf neighbor", "<instance>", "show ip ospf neighbor must not contain <instance> placeholder"),
            ("show mac address-table", "<instance>", "show mac address-table must not contain <instance> placeholder"),
            ("show mac address-table", "ethernet-x/y.z", "show mac address-table must not contain placeholder interface"),
            ("show interface ethernet-1/2", "packets/sec", "show interface ethernet-1/2 must not output synthetic packets/sec"),
            ("show lldp neighbors", "Total entries displayed: 0", "show lldp neighbors must not return 0 entries when spine neighbor is active"),
            ("show lldp neighbors detail", "Total entries displayed: 0", "show lldp neighbors detail must not return 0 entries when spine neighbor is active"),
            ("nxos show lldp neighbors", "Total entries displayed: 0", "nxos show lldp neighbors must not return 0 entries when spine neighbor is active"),
            ("show environment", "No temperature sensor data available.", "show environment must resolve control processor temperature sensor data"),
            ("show environment temperature", "No temperature sensor data available.", "show environment temperature must resolve control processor temperature sensor data"),
            ("show nve peers", "No NVE peers discovered.", "show nve peers must resolve active VXLAN peers"),
        ],
        "positive_assertions": [
            ("show lldp neighbors", "spine", "show lldp neighbors must list spine neighbor"),
            ("show lldp neighbors", "Total entries displayed: 1", "show lldp neighbors must display total entries count"),
            ("show lldp neighbors detail", "System Name: spine", "show lldp neighbors detail must display System Name: spine"),
            ("show lldp neighbors detail", "Enabled Capabilities: R", "show lldp neighbors detail must resolve Router capability R"),
            ("nxos show lldp neighbors", "spine", "nxos show lldp neighbors must list spine neighbor"),
            ("nxos show lldp neighbors detail", "System Name: spine", "nxos show lldp neighbors detail must display System Name: spine"),
            ("show environment", "Control Processor", "show environment must display Control Processor temperature entry"),
            ("show environment temperature", "Control Processor", "show environment temperature must display Control Processor temperature entry"),
            ("show nve peers", "3.3.3.3", "show nve peers must display active peer VTEP 3.3.3.3"),
            ("show nve peers", "4.4.4.4", "show nve peers must display active peer VTEP 4.4.4.4"),
            ("show ip ospf neighbor", "Try SR Linux command: show network-instance default protocols ospf neighbor", "show ip ospf neighbor must recommend default instance"),
            ("show ip ospf neighbor", "10.10.10.10", "show ip ospf neighbor must display spine OSPF neighbor"),
            ("show ip ospf interface brief", "Eth1/2", "show ip ospf interface brief must display Eth1/2"),
            ("show bfd neighbors", "192.168.10.5", "show bfd neighbors must display active BFD neighbor"),
            ("show bfd neighbors", "Eth1/2", "show bfd neighbors must resolve interface Eth1/2"),
            ("show mac address-table", "show network-instance bridge-table mac-table all", "show mac address-table must recommend valid SRL command"),
            ("show processes cpu", "CPU utilization for five seconds:", "show processes cpu must contain CPU utilization summary"),
            ("show processes cpu", "re:Invoked\\s+uSecs", "show processes cpu must include Invoked and uSecs columns"),
            ("show processes cpu", "re:\\d+\\s+\\d+\\s+\\d+\\s+", "show processes cpu must list real system processes"),
            ("show ip arp", "MAC Address", "show ip arp must contain MAC Address header"),
            ("show ip route", "Try SR Linux command: show network-instance default route-table ipv4-unicast summary", "show ip route must recommend valid SRL route-table command"),
            ("show vlan", "Try SR Linux command: show network-instance summary", "show vlan must recommend valid SRL network-instance summary command"),
            ("show nve vni", "Try SR Linux command: show network-instance * vxlan-interface", "show nve vni must recommend valid SRL vxlan-interface command"),
            ("show nve peers", "Try SR Linux command: show tunnel-interface vxlan-interface bridge-table unicast-destinations destination", "show nve peers must recommend valid SRL unicast destinations command"),
            ("show vpc", "peer-link is up", "show vpc must show active ES peer-link on leaf1-2"),
            ("show ip route", "re:via \\d+\\.\\d+\\.\\d+\\.\\d+", "show ip route must dynamically resolve next-hop IP"),
            ("show ip route", "re:Eth\\d+/\\d+", "show ip route must dynamically resolve outgoing Cisco-formatted interface"),
            ("show ip bgp vrf default summary", "BGP summary information for VRF default", "show ip bgp vrf default summary must output VRF BGP summary"),
            ("show vlan", "1     mac-vrf-1", "show vlan must dynamically resolve VLAN 1 for mac-vrf-1"),
            ("show vlan", "irb0.0", "show vlan must preserve irb0.0 interface name"),
            ("show mac address-table", "1   00:00:5E:00:01:01", "show mac address-table must show dynamic VLAN 1 for mac-vrf-1 MAC"),
            ("show mac address-table vlan 1", "irb0.0(R)", "show mac address-table vlan 1 must return matching VLAN 1 entries"),
            ("show interface", "Ethernet1/2 is up", "show interface must output interface detail"),
            ("show interface ethernet-1/2", "Ethernet1/2 is up", "show interface ethernet-1/2 must output interface detail"),
            ("nxos show version", "Nokia SR Linux Software", "nxos show version must output Cisco-formatted version"),
            ("nxos show hostname", "leaf1-2", "nxos show hostname must output hostname"),
            ("nxos show ip route", "Gateway of last resort", "nxos show ip route must contain Gateway of last resort header"),
            ("nxos show interface", "Ethernet1/2 is up", "nxos show interface must output interface detail"),
            ("nxos show interface ethernet-1/2", "Ethernet1/2 is up", "nxos show interface ethernet-1/2 must output interface detail"),
            ("nxos show interface brief", "Eth1/1", "nxos show interface brief must output Ethernet interfaces"),
        ]
    },
    "Juniper JUNOS": {
        "arg_key": "juniper_node",
        "default_node": "leaf2-1",
        "commands": [
            "show version",
            "show system uptime",
            "show system processes",
            "show system processes summary",
            "show system processes brief",
            "show system processes extensive",
            "show chassis hardware",
            "show interfaces",
            "show interfaces brief",
            "show interfaces terse",
            "show arp",
            "show arp no-resolve",
            "show lldp neighbors",
            "show vlans",
            "show lacp interfaces",
            "show ethernet-switching table",
            "show ethernet-switching table vlan 1",
            "show ethernet-switching table instance default",
            "show ethernet-switching table interface ethernet-1/1",
            "show route",
            "show route summary",
            "show bgp summary",
            "show ospf neighbor",
            "show isis adjacency",
            "junos show version",
            "junos show route",
            "junos show interfaces",
        ],
        "submode_tests": [
            ("junos", ["show version", "show route"], "inet.0:"),
            ("junos", ["show interfaces"], "Physical interface:"),
            ("eos", ["show hostname", "show version"], "Nokia 7220 IXR-D2L"),
            ("nxos", ["show hostname", "show version"], "Nokia SR Linux Software"),
            ("sros", ["show version"], "SRLinux-"),
        ],
        "negative_assertions": [
            ("show system uptime", "Time Source: NTP CLOCK", "show system uptime should dynamically verify NTP state rather than hardcoding NTP CLOCK"),
            ("show vlans", "mac-vrf-1             0", "show vlans should not output tag 0 for mac-vrf-1 when IRB tag is 1"),
            ("show ethernet-switching table vlan 1", "irb0.2", "show ethernet-switching table vlan 1 should not leak VLAN 2 entries"),
            ("show system processes summary", "PID USERNAME", "show system processes summary should not output full process table"),
            ("show route summary", "via 10.", "show route summary should not output individual next-hops"),
            ("show route", "ipv4 route", "show route must not recommend invalid ipv4 route command"),
            ("show route summary", "ipv4 route", "show route summary must not recommend invalid ipv4 route command"),
            ("show ospf neighbor", "<instance>", "show ospf neighbor must not contain <instance> placeholder"),
            ("show isis adjacency", "<instance>", "show isis adjacency must not contain <instance> placeholder"),
            ("show ethernet-switching table", "<instance>", "show ethernet-switching table must not contain <instance> placeholder"),
        ],
        "positive_assertions": [
            ("show ethernet-switching table", "show network-instance bridge-table mac-table all", "show ethernet-switching table must recommend valid SRL command"),
            ("show ospf neighbor", "Try SR Linux command: show network-instance default protocols ospf neighbor", "show ospf neighbor must recommend default instance"),
            ("show ospf neighbor", "10.10.10.10", "show ospf neighbor must display spine OSPF neighbor"),
            ("show isis adjacency", "Try SR Linux command: show network-instance default protocols isis adjacency", "show isis adjacency must recommend default instance"),
            ("show isis adjacency", "spine", "show isis adjacency must display spine IS-IS adjacency"),
            ("show route", "re:inet\\.0: \\d+ destinations", "show route must contain destinations and routes header"),
            ("show route", "Try SR Linux command: show network-instance default route-table ipv4-unicast summary", "show route must recommend valid SRL route-table ipv4-unicast summary command"),
            ("show route summary", "Try SR Linux command: show network-instance default route-table summary", "show route summary must recommend valid SRL route-table summary command"),
            ("show vlans", "Try SR Linux command: show network-instance summary", "show vlans must recommend valid SRL network-instance summary command"),
            ("show route", "re:et-\\d+/\\d+/\\d+\\.\\d+", "show route must contain Juniper formatted interfaces"),
            ("show system processes", "re:THR\\s+PRI", "show system processes must include THR column"),
            ("show system processes", "re:\\d+\\s+root\\s+", "show system processes must list real system processes"),
            ("show vlans", "mac-vrf-1             1", "show vlans must dynamically derive tag 1 for mac-vrf-1"),
            ("show ethernet-switching table vlan 1", "irb0.0(R)", "show ethernet-switching table vlan 1 must return VLAN 1 entries"),
            ("junos show version", "Hostname:", "junos show version must output Juniper-formatted version"),
            ("junos show route", "inet.0:", "junos show route must output Juniper-formatted route table"),
        ]
    },
    "Nokia SROS": {
        "arg_key": "nokia_node",
        "default_node": "leaf2-2",
        "commands": [
            "show version",
            "show system information",
            "show chassis",
            "show port",
            "show port 1/1/1",
            "show port description",
            "show lag",
            "show lag 1",
            "show system lldp neighbor",
            "show router route-table",
            "show router default route-table",
            "show router ip-vrf-1 route-table",
            "show router interface",
            "show router arp",
            "show router bgp summary",
            "show router ospf neighbor",
            "show router isis adjacency",
            "show service service-using",
            "show service fdb mac",
            "show service id mac-vrf-1 vxlan",
            "show service id mac-vrf-1 vxlan destinations",
            "show service id mac-vrf-1 fdb mac",
            "sros show version",
            "sros show router route-table",
            "sros show port",
            "sros show chassis",
            "sros show system information",
            "sros show service fdb mac",
        ],
        "submode_tests": [
            ("sros", ["show"], "sros"),
            ("sros", ["show version"], "SRLinux-"),
            ("sros", ["show version", "show router route-table"], "Route Table"),
            ("sros", ["show port", "show chassis"], "Chassis Information"),
            ("eos", ["show version"], "Nokia 7220 IXR-D2L"),
            ("nxos", ["show version"], "Nokia SR Linux Software"),
            ("junos", ["show version"], "Hostname:"),
        ],
        "negative_assertions": [
            ("show port", "with framing overhead", "show port should not trigger standard SRL show interface output"),
            ("show router route-table", "Gateway of last resort", "show router route-table should not output Cisco/Arista header"),
            ("show version", "Software image:", "show version should not output Juniper style version header"),
            ("show chassis", "Cannot create node", "show chassis should not raise plugin load errors"),
            ("show version", "TiMOS", "show version should not output TiMOS - must accurately report SR Linux"),
            ("show version", "panos", "show version should not output synthetic SROS panos build path"),
            ("show system information", "2026-09-02T20:32:38.586Z", "show system information must not output hardcoded boot timestamp"),
            ("show system information", "0 days, 00:00:00.00", "show system information must not report zero uptime"),
            ("show router arp", "03h59m50s", "show router arp must not contain hardcoded 03h59m50s expiry"),
            ("show router bgp summary", "Total BGP Paths         : 52", "show router bgp summary must dynamically query total paths rather than hardcoding 52"),
            ("show lag 1", "\n2        ", "show lag 1 must filter out lag 2"),
            ("show service fdb mac", "No. of Entries in FDB: 0", "show service fdb mac must not return 0 entries when EVPN/IRB MACs exist"),
            ("show service id mac-vrf-1 fdb mac", "No. of Entries in FDB: 0", "show service id mac-vrf-1 fdb mac must not return 0 entries"),
            ("sros show service fdb mac", "No. of Entries in FDB: 0", "sros show service fdb mac must not return 0 entries"),
        ],
        "positive_assertions": [
            ("show version", "SRLinux-", "show version must output authentic SRLinux banner in SROS format"),
            ("show version", "7220 IXR-D2L", "show version must output actual chassis model"),
            ("show version", "Try SR Linux command: show version", "show version must recommend SR Linux command"),
            ("show system information", "System Up Time", "show system information must output system uptime"),
            ("show system information", "Try SR Linux command: info from state system information", "show system information must recommend SRL command"),
            ("show chassis", "Chassis Information", "show chassis must display chassis information"),
            ("show chassis", "Try SR Linux command: show platform chassis", "show chassis must recommend SRL chassis command"),
            ("show port", "Ports on Slot 1", "show port must display port table"),
            ("show port", "Try SR Linux command: show interface brief", "show port must recommend SRL interface brief"),
            ("show port description", "Port Descriptions on Slot 1", "show port description must display port descriptions"),
            ("show lag", "Lag Data", "show lag must display lag data"),
            ("show lag 1", "Lag Data", "show lag 1 must display lag data"),
            ("show system lldp neighbor", "LLDP Remote System Information", "show system lldp neighbor must display lldp info"),
            ("show router route-table", "Route Table (Router: default)", "show router route-table must display default route table"),
            ("show router route-table", "Try SR Linux command: show network-instance default route-table ipv4-unicast summary", "show router route-table must recommend SRL route-table command"),
            ("show router interface", "Interface Table (Router: default)", "show router interface must display interface table"),
            ("show router arp", "ARP Table (Router: default)", "show router arp must display ARP table"),
            ("show router bgp summary", "BGP Summary", "show router bgp summary must display BGP summary table"),
            ("show router ospf neighbor", "10.10.10.10", "show router ospf neighbor must display spine OSPF neighbor"),
            ("show router isis adjacency", "spine", "show router isis adjacency must display spine IS-IS adjacency"),
            ("show service service-using", "Services [Customer: All]", "show service service-using must display service table"),
            ("show service service-using", "NA", "show service service-using must display NA for CustomerID"),
            ("show service id mac-vrf-1 vxlan", "Egress VTEP, VNI", "show service id mac-vrf-1 vxlan must display VXLAN destinations"),
            ("show service id mac-vrf-1 vxlan destinations", "Egress VTEP, VNI", "show service id mac-vrf-1 vxlan destinations must display VXLAN destinations"),
            ("show service id mac-vrf-1 vxlan destinations", "Try SR Linux command:", "show service id vxlan destinations must include SR Linux command hint"),
            ("show service fdb mac", "00:00:5E:00:01:01", "show service fdb mac must list IRB anycast MAC entry"),
            ("show service fdb mac", "irb-interface", "show service fdb mac must resolve destination leaf for IRB MAC"),
            ("show service id mac-vrf-1 fdb mac", "00:00:5E:00:01:01", "show service id mac-vrf-1 fdb mac must list IRB anycast MAC entry"),
            ("show service id mac-vrf-1 fdb mac", "Try SR Linux command:", "show service id fdb mac must include SR Linux command hint"),
            ("sros show service fdb mac", "00:00:5E:00:01:01", "sros show service fdb mac must list IRB anycast MAC entry"),
        ],
    }
}

ERROR_PATTERNS = [
    "Traceback (most recent call last)",
    "AssertionError",
    "Cannot create node",
    "DataError",
    "PluginError",
    "syntax error",
    "Unknown command",
    "unrecognized argument",
    "CLI command failed",
]

import concurrent.futures
import os
import re
import subprocess
import sys
import threading
import time

print_lock = threading.Lock()

def run_command(node, cmd):
    full_cmd = ["docker", "exec", node, "sr_cli", cmd]
    t0 = time.time()
    res = subprocess.run(full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    dt = time.time() - t0
    return res.returncode, res.stdout, res.stderr, dt

def run_suite(suite_name, suite, args, parallel=True):
    node = getattr(args, suite["arg_key"], suite["default_node"])
    commands = suite["commands"]
    neg_assertions = dict(((c, p), msg) for c, p, msg in suite.get("negative_assertions", []))
    pos_assertions = dict(((c, p), msg) for c, p, msg in suite.get("positive_assertions", []))

    with print_lock:
        print(f"\n--- Running {suite_name} on container '{node}' ({len(commands)} commands) ---")

    passed = 0
    failed = 0
    failures = []

    for idx, cmd in enumerate(commands, 1):
        rc, stdout, stderr, dt = run_command(node, cmd)

        # Check error patterns
        errors = []
        if rc != 0:
            errors.append(f"Non-zero exit code: {rc}")
        for pat in ERROR_PATTERNS:
            if pat in stdout or pat in stderr:
                errors.append(f"Found error pattern '{pat}'")

        # Check that output is not completely empty
        if not stdout.strip() and not stderr.strip():
            errors.append("Output is completely empty")

        # Negative assertions: ensure no hardcoded mock data is present
        for (neg_cmd, bad_pattern), failure_msg in neg_assertions.items():
            if cmd == neg_cmd:
                matched = bool(re.search(bad_pattern[3:], stdout)) if bad_pattern.startswith("re:") else (bad_pattern in stdout)
                if matched:
                    errors.append(f"Assertion failed: {failure_msg} (found '{bad_pattern}')")

        # Positive assertions: ensure expected dynamic content is present
        for (pos_cmd, req_pattern), failure_msg in pos_assertions.items():
            if cmd == pos_cmd:
                matched = bool(re.search(req_pattern[3:], stdout)) if req_pattern.startswith("re:") else (req_pattern in stdout)
                if not matched:
                    errors.append(f"Assertion failed: {failure_msg} (missing '{req_pattern}')")

        prefix = f"[{node}] " if parallel else ""
        with print_lock:
            if errors:
                failed += 1
                status = "FAIL"
                failures.append({
                    "suite": suite_name,
                    "node": node,
                    "command": cmd,
                    "errors": errors,
                    "stdout": stdout,
                    "stderr": stderr
                })
                print(f"  {prefix}[{idx:2d}/{len(commands):2d}] {cmd:<44} -> {status} ({dt:.2f}s) - {'; '.join(errors)}")
            else:
                passed += 1
                status = "PASS"
                print(f"  {prefix}[{idx:2d}/{len(commands):2d}] {cmd:<44} -> {status} ({dt:.2f}s)")

    # Submode interactive tests
    submode_tests = suite.get("submode_tests", [])
    for s_idx, (submode, subcmds, expected) in enumerate(submode_tests, 1):
        cmds = [subcmds] if isinstance(subcmds, str) else list(subcmds)
        test_display = f"{submode} -> {' ; '.join(cmds)}"
        full_cmd = ["docker", "exec", "-i", node, "sr_cli"]
        input_str = f"{submode}\n" + "\n".join(cmds) + "\npwc\nexit\n"
        t0 = time.time()
        res = subprocess.run(full_cmd, input=input_str, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        dt = time.time() - t0
        errors = []
        if res.returncode != 0:
            errors.append(f"Non-zero exit code: {res.returncode}")
        for pat in ERROR_PATTERNS:
            if pat in res.stdout or pat in res.stderr:
                errors.append(f"Found error pattern '{pat}'")
        if expected not in res.stdout:
            errors.append(f"Expected pattern '{expected}' missing from submode output")
        if submode not in [line.strip() for line in res.stdout.splitlines()]:
            errors.append(f"Submode '{submode}' was not retained as present working context (pwc check failed)")

        prefix = f"[{node}] " if parallel else ""
        with print_lock:
            if errors:
                failed += 1
                status = "FAIL"
                failures.append({
                    "suite": suite_name,
                    "node": node,
                    "command": f"submode: {test_display}",
                    "errors": errors,
                    "stdout": res.stdout,
                    "stderr": res.stderr
                })
                print(f"  {prefix}[submode] {test_display:<39} -> {status} ({dt:.2f}s) - {'; '.join(errors)}")
            else:
                passed += 1
                status = "PASS"
                print(f"  {prefix}[submode] {test_display:<39} -> {status} ({dt:.2f}s)")

    return passed, failed, failures

def validate_recommended_srl_commands(target_nodes="leaf1-1", parallel=True):
    """
    Validate that all recommended SR Linux commands suggested in the output
    footers of MultiCLI show commands are syntactically valid and executable
    on native Nokia SR Linux switches.
    """
    if isinstance(target_nodes, str):
        target_nodes = [target_nodes]

    recommended_commands = [
        "show interface brief",
        "show interface",
        "show interface detail",
        "show interface ethernet-1/1 brief",
        "show interface ethernet-1/1 detail",
        "show system lldp neighbor",
        "show arpnd arp-entries",
        "show lag",
        "show network-instance default protocols bgp neighbor",
        "show network-instance default protocols bgp summary",
        "show network-instance default protocols bgp routes evpn route-type 1 summary",
        "show network-instance default protocols bgp routes evpn route-type 2 summary",
        "show network-instance default protocols bgp routes evpn route-type 3 summary",
        "show network-instance default protocols bgp routes evpn route-type 4 summary",
        "show network-instance default protocols bgp routes evpn route-type 5 summary",
        "show network-instance default route-table ipv4-unicast summary",
        "show network-instance default route-table summary",
        "show network-instance summary",
        "show network-instance bridge-table mac-table all",
        "show network-instance default protocols ospf neighbor",
        "show network-instance default protocols isis adjacency",
        "show network-instance default protocols ospf interface",
        "show system network-instance ethernet-segments",
        "show version",
        "info from state system name",
        "info from state system clock",
        "show platform",
        "show platform environment",
        "show platform chassis",
        "info from state system information",
        "info from state bfd",
        "show network-instance * vxlan-interface",
        "show tunnel-interface vxlan-interface bridge-table unicast-destinations destination",
    ]

    def _validate_node(target_node):
        node_passed = 0
        node_failed = 0
        node_failures = []
        with print_lock:
            print(f"\n--- Validating {len(recommended_commands)} Recommended SR Linux Commands on '{target_node}' ---")
        for idx, cmd in enumerate(recommended_commands, 1):
            rc, stdout, stderr, dt = run_command(target_node, cmd)
            out = stdout + stderr
            errors = []
            if rc != 0:
                errors.append(f"Non-zero exit code: {rc}")
            if "usage: show" in out:
                errors.append("Command printed 'usage: show' (incomplete token)")
            if "Parsing error" in out:
                errors.append("Parsing error in SR Linux syntax")
            if "Unknown command" in out:
                errors.append("Unknown command in SR Linux CLI")
            # Some protocol tables (like IS-IS when unconfigured) legitimately return empty output with exit code 0
            if not stdout.strip() and not stderr.strip() and "isis" not in cmd:
                errors.append("Output is completely empty")

            with print_lock:
                if errors:
                    node_failed += 1
                    node_failures.append({
                        "suite": "Recommended SRL Commands",
                        "node": target_node,
                        "command": cmd,
                        "errors": errors,
                        "stdout": stdout,
                        "stderr": stderr
                    })
                    print(f"  [{target_node}] [{idx:2d}/{len(recommended_commands):2d}] {cmd:<60} -> FAIL ({dt:.2f}s) - {'; '.join(errors)}")
                else:
                    node_passed += 1
                    print(f"  [{target_node}] [{idx:2d}/{len(recommended_commands):2d}] {cmd:<60} -> PASS ({dt:.2f}s)")
        return node_passed, node_failed, node_failures

    total_passed = 0
    total_failed = 0
    failures = []

    if parallel and len(target_nodes) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(target_nodes)) as executor:
            future_to_node = {executor.submit(_validate_node, node): node for node in target_nodes}
            for fut in concurrent.futures.as_completed(future_to_node):
                p, f, fails = fut.result()
                total_passed += p
                total_failed += f
                failures.extend(fails)
    else:
        for node in target_nodes:
            p, f, fails = _validate_node(node)
            total_passed += p
            total_failed += f
            failures.extend(fails)

    return total_passed, total_failed, failures

def validate_user_personas(target_nodes="leaf1-1", parallel=True):
    """
    Validate per-user CLI personas (auser, cnxuser, juser, nokuser) when both
    /etc/opt/srlinux/cli/plugins and ~/cli/plugins are loaded simultaneously.
    """
    if isinstance(target_nodes, str):
        target_nodes = [target_nodes]

    persona_tests = [
        ("auser", "show version", ["Nokia 7220 IXR-D2L", "Try SR Linux command: show version"], ["Software image version: N/A"]),
        ("cnxuser", "show lldp neighbors", ["spine", "Total entries displayed: 1"], ["Total entries displayed: 0"]),
        ("juser", "show bgp summary", ["inet.0", "Try SR Linux command: show network-instance default protocols bgp neighbor"], []),
        ("nokuser", "show router bgp summary", ["BGP Admin State", "Try SR Linux command: show network-instance default protocols bgp summary"], []),
        ("nokuser", "show service fdb mac", ["00:00:5E:00:01:01", "irb-interface"], ["No. of Entries in FDB: 0"]),
    ]

    def _validate_node_personas(target_node):
        node_passed = 0
        node_failed = 0
        node_failures = []
        with print_lock:
            print(f"\n--- Validating {len(persona_tests)} Per-User CLI Persona Commands on '{target_node}' ---")
        for idx, (user, cmd, pos_pats, neg_pats) in enumerate(persona_tests, 1):
            full_cmd = ["docker", "exec", target_node, "su", "-", user, "-c", cmd]
            t0 = time.time()
            res = subprocess.run(full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            dt = time.time() - t0
            out = res.stdout + res.stderr
            errors = []
            if res.returncode != 0:
                errors.append(f"Non-zero exit code: {res.returncode}")
            for pat in ERROR_PATTERNS:
                if pat in out:
                    errors.append(f"Found error pattern '{pat}'")
            for req in pos_pats:
                if req not in res.stdout:
                    errors.append(f"Missing expected output '{req}'")
            for bad in neg_pats:
                if bad in res.stdout:
                    errors.append(f"Found unexpected output '{bad}'")

            display_cmd = f"su - {user} -c \"{cmd}\""
            with print_lock:
                if errors:
                    node_failed += 1
                    node_failures.append({
                        "suite": "Per-User CLI Personas",
                        "node": target_node,
                        "command": display_cmd,
                        "errors": errors,
                        "stdout": res.stdout,
                        "stderr": res.stderr
                    })
                    print(f"  [{target_node}] [{idx:2d}/{len(persona_tests):2d}] {display_cmd:<60} -> FAIL ({dt:.2f}s) - {'; '.join(errors)}")
                else:
                    node_passed += 1
                    print(f"  [{target_node}] [{idx:2d}/{len(persona_tests):2d}] {display_cmd:<60} -> PASS ({dt:.2f}s)")
        return node_passed, node_failed, node_failures

    total_passed = 0
    total_failed = 0
    failures = []

    if parallel and len(target_nodes) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(target_nodes)) as executor:
            future_to_node = {executor.submit(_validate_node_personas, node): node for node in target_nodes}
            for fut in concurrent.futures.as_completed(future_to_node):
                p, f, fails = fut.result()
                total_passed += p
                total_failed += f
                failures.extend(fails)
    else:
        for node in target_nodes:
            p, f, fails = _validate_node_personas(node)
            total_passed += p
            total_failed += f
            failures.extend(fails)

    return total_passed, total_failed, failures

def validate(args):
    t_start = time.time()
    total_passed = 0
    total_failed = 0
    all_failures = []

    print("=" * 80)
    print("MultiCLI Comprehensive Automated Validation Test Suite")
    print("=" * 80)

    if getattr(args, 'install', False):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        switch_script = os.path.join(script_dir, "..", "switch-multicli.sh")
        print("\n==> Installing MultiCLI personas to target nodes...")
        install_tasks = [("leaf1-1", "arista_node", "arista"),
                         ("leaf1-2", "cisco_node", "cisco"),
                         ("leaf2-1", "juniper_node", "juniper"),
                         ("leaf2-2", "nokia_node", "nokia")]
        if not getattr(args, 'sequential', False):
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futs = [executor.submit(subprocess.run, [switch_script, "all", getattr(args, key, def_node), "--default", persona], check=True)
                        for def_node, key, persona in install_tasks]
                for f in futs:
                    f.result()
        else:
            for def_node, key, persona in install_tasks:
                subprocess.run([switch_script, "all", getattr(args, key, def_node), "--default", persona], check=True)
        time.sleep(1)

    suites_to_run = list(TEST_SUITES.items())
    if getattr(args, 'sequential', False):
        for s_name, s_data in suites_to_run:
            p, f, fails = run_suite(s_name, s_data, args, parallel=False)
            total_passed += p
            total_failed += f
            all_failures.extend(fails)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(suites_to_run)) as executor:
            future_to_suite = {
                executor.submit(run_suite, s_name, s_data, args, parallel=True): s_name
                for s_name, s_data in suites_to_run
            }
            for fut in concurrent.futures.as_completed(future_to_suite):
                p, f, fails = fut.result()
                total_passed += p
                total_failed += f
                all_failures.extend(fails)

    # Validate per-user CLI personas across all target nodes
    target_nodes = list(dict.fromkeys([args.arista_node, args.cisco_node, args.juniper_node, args.nokia_node]))
    p_usr, f_usr, fails_usr = validate_user_personas(target_nodes, parallel=not getattr(args, 'sequential', False))
    total_passed += p_usr
    total_failed += f_usr
    all_failures.extend(fails_usr)

    # Validate all recommended SR Linux commands
    p_srl, f_srl, fails_srl = validate_recommended_srl_commands(target_nodes, parallel=not getattr(args, 'sequential', False))
    total_passed += p_srl
    total_failed += f_srl
    all_failures.extend(fails_srl)

    elapsed_total = time.time() - t_start
    print("\n" + "=" * 80)
    print(f"Test Summary: Total={total_passed + total_failed} | Passed={total_passed} | Failed={total_failed} (Finished in {elapsed_total:.2f}s)")
    print("=" * 80)

    if all_failures:
        print(f"\nFAILED COMMANDS DETAILS ({len(all_failures)} failures):")
        for f in all_failures:
            print("-" * 60)
            print(f"Suite:   {f['suite']} (Node: {f['node']})")
            print(f"Command: {f['command']}")
            print(f"Errors:  {f['errors']}")
            if f['stderr']:
                print(f"STDERR:\n{f['stderr']}")
            if f['stdout']:
                print(f"STDOUT:\n{f['stdout']}")
        return False
    else:
        print("\nALL COMMANDS PASSED VALIDATION WITHOUT ERRORS!")
        return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MultiCLI Automated Test Validation Suite")
    parser.add_argument("--arista-node", default="leaf1-1", help="Target node running Arista EOS persona (default: leaf1-1)")
    parser.add_argument("--cisco-node", default="leaf1-2", help="Target node running Cisco NX-OS persona (default: leaf1-2)")
    parser.add_argument("--juniper-node", default="leaf2-1", help="Target node running Juniper JUNOS persona (default: leaf2-1)")
    parser.add_argument("--nokia-node", default="leaf2-2", help="Target node running Nokia SR OS persona (default: leaf2-2)")
    parser.add_argument("--install", action="store_true", help="Automatically configure each target node with switch-multicli.sh before validation")
    parser.add_argument("--sequential", action="store_true", help="Run node test suites sequentially instead of in parallel")
    cli_args = parser.parse_args()

    success = validate(cli_args)
    sys.exit(0 if success else 1)
