# Custom CLI Plugins for Nokia SR OS

The following CLI plugins are available in this repo:

| Command | Description / Contributor |
|---|---|
| `show version` | Nokia SR OS formatted software version and chassis info |
| `show system information` | System name, uptime, active slot, SSH/SNMP status, and clock |
| `show chassis` | Chassis hardware, serial number, fan trays, and power supplies |
| `show port [<id>]` | Port status, link state, MTU, LAG membership, and encapsulation |
| `show port description` | Port descriptions per slot |
| `show lag` | LAG operational state, threshold, and active member count |
| `show system lldp neighbor` | LLDP remote system neighbor information |
| `show router [<netinst>] route-table` | IPv4 route table with next-hops, protocols, and metrics |
| `show router [<netinst>] interface` | Router interface table with IPv4/IPv6 addresses and states |
| `show router [<netinst>] arp` | Router ARP table with dynamic/static type and expiry |
| `show router [<netinst>] bgp summary` | BGP summary and neighbor statistics ([giancarlo3g](https://github.com/giancarlo3g)) |
| `show router [<netinst>] ospf neighbor` | OSPFv2 neighbor adjacencies and states |
| `show router [<netinst>] isis adjacency` | IS-IS adjacencies, levels, and hold timers |
| `show service service-using` | Configured VPLS (`mac-vrf`) and VPRN (`ip-vrf`) services |
| `show service fdb mac` | Forwarding database MAC table across all services |
| `show service id <id> fdb mac` | Forwarding database MAC table for a specific service |
| `show service id <id> evpn-mpls` | EVPN-MPLS destinations ([zenodhaene](https://github.com/zenodhaene)) |
| `show service id <id> vxlan destinations` | EVPN-VxLAN destinations ([zenodhaene](https://github.com/zenodhaene)) |

## Testing

Deploy the EVPN lab. Login to any leaf or spine node using `nokuser/nokuser` and try any of the above commands.

## Nokia SROS scripts

### `evpn_report.py`

This script introduces a custom command that allows the user to visualize the EVPN endpoints for both single-homed and multi-homed (ethernet segment) destinations. This is useful for figuring out where an EVPN-enabled service is configured.

The command works for EVPN services with both VxLAN and MPLS transport tunnels. It requires the `service_report.py` script to also be copied to the `plugins` folder.

### Command syntax (EVPN-VxLAN services)

```
/show service id evpn-vxlan vxlan destinations
```

Where `evpn-vxlan` is an EVPN-enabled service with VxLAN transport tunnels.

<details>
    <summary>Example execution</summary>

    ```
    --{ + running }--[  ]--
    A:admin@leaf-3# /show service id evpn-vxlan vxlan destinations

    ===============================================================================
    Egress VTEP, VNI (Instance 1)
    ===============================================================================
    VTEP Address                                        Egress VNI Oper  Mcast Num
                                                                State       MACs
    -------------------------------------------------------------------------------
    10.0.0.3                                            100        Up    BUM   N/A
    10.0.0.4                                            100        Up    BUM   N/A
    -------------------------------------------------------------------------------
    Number of Egress VTEP, VNI : 2
    -------------------------------------------------------------------------------
    ===============================================================================

    ===============================================================================
    Egress VTEP, VNI (Instance 2)
    ===============================================================================
    VTEP Address                                        Egress VNI Oper  Mcast Num
                                                                State       MACs
    -------------------------------------------------------------------------------
    No Matching Entries
    ===============================================================================

    ===============================================================================
    BGP EVPN-VXLAN Ethernet Segment Dest (Instance 1)
    ===============================================================================
    Eth SegId                               Num. Macs       Last Update
    -------------------------------------------------------------------------------
    00:00:00:00:C0:FF:EE:00:00:01           100             2025-04-02 08:23:37
    -------------------------------------------------------------------------------
    Number of entries: 1
    -------------------------------------------------------------------------------
    ===============================================================================

    ===============================================================================
    BGP EVPN-VXLAN Ethernet Segment Dest (Instance 2)
    ===============================================================================
    Eth SegId                               Num. Macs       Last Update
    -------------------------------------------------------------------------------
    No Matching Entries
    ===============================================================================
    ```

</details>

### Command syntax (EVPN-MPLS services)

```
/show service id srmpls-evpn-vpls evpn-mpls
```

Where `srmpls-evpn-vpls` is an EVPN-enabled service with SR-MPLS transport tunnels.


<details>
    <summary>Example execution</summary>

    ```
    --{ + running }--[  ]--
    A:CE-SXR-1# / show service id srmpls-evpn-vpls evpn-mpls

    ===============================================================================
    BGP EVPN-MPLS Dest (Instance 1)
    ===============================================================================
    TEP Address                     Transpor:Tnl      Egr Label  Oper  Mcast  Num
                                                                State        MACs
    -------------------------------------------------------------------------------
    10.0.0.4                        sr-isis:20004     103        Up    bum    N/A
    10.0.1.3                        sr-isis:20103     524287     Up    bum    N/A
    10.0.1.3                        sr-isis:20103     524287     Up    None   10
    10.0.1.4                        sr-isis:20104     524287     Up    bum    N/A
    10.0.1.4                        sr-isis:20104     524287     Up    None   10
    -------------------------------------------------------------------------------
    Number of entries: 5
    -------------------------------------------------------------------------------
    ===============================================================================

    ===============================================================================
    BGP EVPN-MPLS Dest (Instance 2)
    ===============================================================================
    TEP Address                     Transpor:Tnl      Egr Label  Oper  Mcast  Num
                                                                State        MACs
    -------------------------------------------------------------------------------
    No Matching Entries
    ===============================================================================

    ===============================================================================
    BGP EVPN-MPLS Ethernet Segment Dest (Instance 1)
    ===============================================================================
    Eth SegId                       Num. Macs               Last Update
    -------------------------------------------------------------------------------
    00:00:00:BE:EF:00:00:00:00:03   10                      2025-04-02 08:48:34
    -------------------------------------------------------------------------------
    Number of entries: 1
    -------------------------------------------------------------------------------
    ===============================================================================

    ===============================================================================
    BGP EVPN-MPLS Ethernet Segment Dest (Instance 2)
    ===============================================================================
    Eth SegId                       Num. Macs               Last Update
    -------------------------------------------------------------------------------
    No Matching Entries
    ===============================================================================
    ```
</details>
