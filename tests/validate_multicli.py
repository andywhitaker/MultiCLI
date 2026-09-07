#!/usr/bin/env python3
"""
validate_multicli.py
Automated validation harness for all MultiCLI commands across
Arista EOS (leaf1), Cisco NX-OS (leaf2), and Juniper JUNOS (leaf3).
"""

import os
import re
import subprocess
import sys
import time

TEST_SUITES = {
    "Arista EOS": {
        "arg_key": "arista_node",
        "default_node": "leaf1",
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
            "show interface description",
            "show interfaces transceiver",
            "show interfaces transceiver detail",
            "show interface transceiver",
            "show interface transceiver detail",
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
            "show interface status",
            "show interfaces status",
            "show eos interface ethernet-1/1",
            "eos show version",
            "eos show hostname",
            "eos show ip route",
            "eos show interface",
            "eos show interface ethernet-1/1",
            "eos show interfaces",
            "eos show interfaces status",
        ],
        "submode_tests": [
            ("eos", ["show hostname", "show version"], "Nokia 7220 IXR-D2L"),
            ("eos", ["show interface", "show interface ethernet-1/1"], "ethernet-1/1 is up"),
            ("eos", ["show interfaces", "show interfaces status"], "Ethernet1/1"),
            ("nxos", ["show hostname", "show version"], "Nokia SR Linux Software"),
            ("junos", ["show version"], "Hostname:"),
        ],
        "negative_assertions": [
            ("show mlag", "state: Active", "show mlag should not output hardcoded 'state: Active' when no MLAG is configured"),
            ("show mlag", "local-interface     : Po1", "show mlag should not output synthetic 'Po1' when no interface is bound"),
            ("show port-channel summary", "LACP(a)", "show port-channel summary should not hardcode LACP(a) when no LAG is configured"),
            ("show environment cooling", "System Temperature", "show environment cooling should not trigger intermediate show environment all"),
            ("show environment power", "System Temperature", "show environment power should not trigger intermediate show environment all"),
            ("show lldp neighbors detail", "Last table change time", "show lldp neighbors detail should not trigger intermediate show lldp neighbors summary"),
            ("show lldp neighbors", "0:01:00 ago", "show lldp neighbors should not output hardcoded fake timestamp '0:01:00 ago'"),
            ("show ip route", "S       10.1.10.0/24", "Local/connected subnet should be classified as C or L, not S"),
            ("show vlan", "--    app", "show vlan should dynamically derive VLAN tag rather than '--'"),
            ("show vlan", "Vlan1", "show vlan should not convert IRB interface to Vlan1"),
            ("show mac address-table", "Vlan--", "show mac address-table should not output 'Vlan--'"),
            ("show mac address-table", "Vlan1", "show mac address-table should not convert IRB interface to Vlan1"),
            ("show eos interface ethernet-1/1", "packets/sec", "show eos interface detail should not output unsupported packets/sec metric"),
            ("show interfaces status", "with framing overhead", "show interfaces status should not output interface detail"),
            ("show interfaces description", "with framing overhead", "show interfaces description should not output interface detail"),
            ("show interfaces transceiver", "with framing overhead", "show interfaces transceiver should not output interface detail"),
            ("eos show interfaces status", "with framing overhead", "eos show interfaces status should not output interface detail"),
            ("show ip route", "route-table", "show ip route must not recommend invalid route-table command"),
        ],
        "positive_assertions": [
            ("show ip route", "Gateway of last resort", "show ip route must contain Gateway of last resort header"),
            ("show ip route", "Try SR Linux command: show network-instance default ipv4 route", "show ip route must recommend valid SRL ipv4 route command"),
            ("show vlan", "Try SR Linux command: show network-instance summary", "show vlan must recommend valid SRL network-instance summary command"),
            ("show ip arp", "Age (min)", "show ip arp must contain Age (min) column"),
            ("show interfaces status", "Ethernet1/1", "show interfaces status must format interfaces in Arista style EthernetX/Y"),
            ("show ip bgp vrf default summary", "BGP summary information for VRF default", "show ip bgp vrf default summary must output VRF BGP summary"),
            ("show vlan", "1     app", "show vlan must dynamically resolve VLAN 1 for app"),
            ("show vlan", "irb0.1", "show vlan must preserve irb0.1 interface name"),
            ("show mac address-table", "1       0000.5e00.0101", "show mac address-table must dynamically resolve VLAN 1 for IRB MAC"),
            ("show mac address-table", "irb0.1", "show mac address-table must format IRB port as irb0.1"),
            ("show eos interface ethernet-1/1", "with framing overhead", "show eos interface detail should output input/output rate with framing overhead"),
            ("eos show version", "Nokia 7220 IXR-D2L", "eos show version must output Arista-formatted version"),
            ("eos show hostname", "leaf1", "eos show hostname must output hostname"),
            ("eos show ip route", "Gateway of last resort", "eos show ip route must contain Gateway of last resort header"),
            ("eos show interface", "ethernet-1/1 is up", "eos show interface must output interface status and statistics"),
            ("eos show interface ethernet-1/1", "ethernet-1/1 is up", "eos show interface ethernet-1/1 must output interface detail"),
        ]
    },
    "Cisco NX-OS": {
        "arg_key": "cisco_node",
        "default_node": "leaf2",
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
            "show interfaces brief",
            "show interface status",
            "show interface description",
            "show interface transceiver",
            "show interface transceiver details",
            "show interfaces transceiver",
            "show interfaces transceiver details",
            "show ipv6 interface brief",
            "show port-channel summary",
            "show ip interface brief",
            "show lldp neighbors",
            "show lldp neighbor",
            "show lldp neighbors detail",
            "show ip arp",
            "show ip route",
            "show ip route vrf default",
            "show ip bgp summary",
            "show ip bgp vrf default summary",
            "show mac address-table",
            "show mac address-table vlan 1",
            "show mac address-table vlan 10",
            "show mac address-table interface ethernet-1/1",
            "show mac address-table vni 1",
            "show mac address-table vni 10010",
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
            "nxos show interface ethernet-1/1",
            "nxos show interfaces",
            "nxos show interface brief",
            "show interface",
            "show interface ethernet-1/1",
            "show interfaces",
        ],
        "submode_tests": [
            ("nxos", ["show hostname", "show version"], "Nokia SR Linux Software"),
            ("nxos", ["show interface brief", "show interface ethernet-1/1"], "Ethernet1/1 is up"),
            ("nxos", ["show ip route"], "Gateway of last resort"),
            ("eos", ["show hostname", "show version"], "Nokia 7220 IXR-D2L"),
            ("junos", ["show version"], "Hostname:"),
        ],
        "negative_assertions": [
            ("show vpc", "peer-link is up", "show vpc should not output hardcoded 'peer-link is up' when no VPC/ES is configured"),
            ("show vpc", "Po1", "show vpc should not output synthetic 'Po1' when no interface is bound"),
            ("show nve peers", "state: Up", "show nve peers should not output hardcoded 'state: Up' when no NVE peer is present"),
            ("show ip route", "ethernet-1/1.0", "show ip route should format interface as Eth1/1 rather than ethernet-1/1.0"),
            ("show mac address-table vlan 1", "irb0.2", "show mac address-table vlan 1 should not leak non-matching VLAN 2 entries (irb0.2)"),
            ("show mac address-table vlan 10", "irb0.1", "show mac address-table vlan 10 should not return non-matching entries"),
            ("show vlan", "--    app", "show vlan should dynamically derive VLAN tag rather than '--'"),
            ("show vlan", "Vlan0.", "show vlan should not output synthetic 'Vlan0.' interface names"),
            ("show vlan", "Vlan1", "show vlan should not convert IRB interface to Vlan1"),
            ("show interface brief", "admin state is up, Dedicated Interface", "show interface brief should not output full interface detail"),
            ("show interface status", "admin state is up, Dedicated Interface", "show interface status should not output full interface detail"),
            ("show interface description", "admin state is up, Dedicated Interface", "show interface description should not output full interface detail"),
            ("show interface transceiver", "admin state is up, Dedicated Interface", "show interface transceiver should not output full interface detail"),
            ("nxos show interface brief", "admin state is up, Dedicated Interface", "nxos show interface brief should not output full interface detail"),
            ("show ip route", "route-table", "show ip route must not recommend invalid route-table command"),
            ("show nve vni", "Try SR Linux command: show tunnel-interface\n", "show nve vni must not recommend incomplete show tunnel-interface command"),
            ("show nve peers", "Try SR Linux command: show tunnel-interface vxlan-interface bridge-table\n", "show nve peers must not recommend incomplete bridge-table command"),
        ],
        "positive_assertions": [
            ("show processes cpu", "CPU utilization for five seconds:", "show processes cpu must contain CPU utilization summary"),
            ("show processes cpu", "re:Invoked\\s+uSecs", "show processes cpu must include Invoked and uSecs columns"),
            ("show ip arp", "MAC Address", "show ip arp must contain MAC Address header"),
            ("show ip route", "Try SR Linux command: show network-instance default ipv4 route", "show ip route must recommend valid SRL ipv4 route command"),
            ("show vlan", "Try SR Linux command: show network-instance summary", "show vlan must recommend valid SRL network-instance summary command"),
            ("show nve vni", "Try SR Linux command: show tunnel-interface vxlan-interface brief", "show nve vni must recommend valid SRL vxlan brief command"),
            ("show nve peers", "Try SR Linux command: show tunnel-interface vxlan-interface bridge-table unicast-destinations destination", "show nve peers must recommend valid SRL unicast destinations command"),
            ("show ip route", "re:via \\d+\\.\\d+\\.\\d+\\.\\d+", "show ip route must dynamically resolve next-hop IP"),
            ("show ip route", "re:Eth\\d+/\\d+", "show ip route must dynamically resolve outgoing Cisco-formatted interface"),
            ("show ip bgp vrf default summary", "BGP summary information for VRF default", "show ip bgp vrf default summary must output VRF BGP summary"),
            ("show vlan", "1     app", "show vlan must dynamically resolve VLAN 1 for app"),
            ("show vlan", "irb0.1", "show vlan must preserve irb0.1 interface name"),
            ("show mac address-table", "1   00:00:5E:00:01:01", "show mac address-table must show dynamic VLAN 1 for app MAC"),
            ("show mac address-table vlan 1", "irb0.1(R)", "show mac address-table vlan 1 must return matching VLAN 1 entries"),
            ("show interface", "Ethernet1/1 is up", "show interface must output interface detail"),
            ("show interface ethernet-1/1", "Ethernet1/1 is up", "show interface ethernet-1/1 must output interface detail"),
            ("nxos show version", "Nokia SR Linux Software", "nxos show version must output Cisco-formatted version"),
            ("nxos show hostname", "leaf2", "nxos show hostname must output hostname"),
            ("nxos show ip route", "Gateway of last resort", "nxos show ip route must contain Gateway of last resort header"),
            ("nxos show interface", "Ethernet1/1 is up", "nxos show interface must output interface detail"),
            ("nxos show interface ethernet-1/1", "Ethernet1/1 is up", "nxos show interface ethernet-1/1 must output interface detail"),
            ("nxos show interface brief", "Eth1/1", "nxos show interface brief must output Ethernet interfaces"),
        ]
    },
    "Juniper JUNOS": {
        "arg_key": "juniper_node",
        "default_node": "leaf3",
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
        ],
        "negative_assertions": [
            ("show system uptime", "Time Source: NTP CLOCK", "show system uptime should dynamically verify NTP state rather than hardcoding NTP CLOCK"),
            ("show vlans", "app                   0", "show vlans should not output tag 0 for app when IRB tag is 1"),
            ("show ethernet-switching table vlan 1", "irb0.2", "show ethernet-switching table vlan 1 should not leak VLAN 2 entries"),
            ("show system processes summary", "PID USERNAME", "show system processes summary should not output full process table"),
            ("show route summary", "via 10.", "show route summary should not output individual next-hops"),
            ("show route", "route-table", "show route must not recommend invalid route-table command"),
            ("show route summary", "route-table", "show route summary must not recommend invalid route-table command"),
        ],
        "positive_assertions": [
            ("show route", "re:inet\\.0: \\d+ destinations", "show route must contain destinations and routes header"),
            ("show route", "Try SR Linux command: show network-instance default ipv4 route", "show route must recommend valid SRL ipv4 route command"),
            ("show route summary", "Try SR Linux command: show network-instance default ipv4 route summary", "show route summary must recommend valid SRL ipv4 route summary command"),
            ("show vlans", "Try SR Linux command: show network-instance summary", "show vlans must recommend valid SRL network-instance summary command"),
            ("show route", "re:et-\\d+/\\d+/\\d+\\.\\d+", "show route must contain Juniper formatted interfaces"),
            ("show system processes", "re:THR\\s+PRI", "show system processes must include THR column"),
            ("show vlans", "app                   1", "show vlans must dynamically derive tag 1 for app"),
            ("show ethernet-switching table vlan 1", "irb0.1(R)", "show ethernet-switching table vlan 1 must return VLAN 1 entries"),
            ("junos show version", "Hostname:", "junos show version must output Juniper-formatted version"),
            ("junos show route", "inet.0:", "junos show route must output Juniper-formatted route table"),
        ]
    }
}

ERROR_PATTERNS = [
    "Traceback (most recent call last)",
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

def validate_recommended_srl_commands(target_node="leaf1"):
    """
    Validate that all recommended SR Linux commands suggested in the output
    footers of MultiCLI show commands are syntactically valid and executable
    on native Nokia SR Linux switches.
    """
    recommended_commands = [
        "show interface brief",
        "show interface",
        "show interface detail",
        "show system lldp neighbor",
        "show arpnd arp-entries",
        "show lag",
        "show network-instance default protocols bgp neighbor",
        "show network-instance default protocols bgp routes evpn route-type 1 summary",
        "show network-instance default protocols bgp routes evpn route-type 2 summary",
        "show network-instance default protocols bgp routes evpn route-type 3 summary",
        "show network-instance default protocols bgp routes evpn route-type 4 summary",
        "show network-instance default protocols bgp routes evpn route-type 5 summary",
        "show network-instance default ipv4 route",
        "show network-instance default ipv4 route summary",
        "show network-instance summary",
        "show network-instance app bridge-table mac-table all",
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
        "show tunnel-interface vxlan-interface brief",
        "show tunnel-interface vxlan-interface bridge-table unicast-destinations destination",
    ]

    print(f"\n--- Validating {len(recommended_commands)} Recommended SR Linux Commands on '{target_node}' ---")
    passed = 0
    failed = 0
    failures = []

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

        if errors:
            failed += 1
            failures.append({
                "suite": "Recommended SRL Commands",
                "node": target_node,
                "command": cmd,
                "errors": errors,
                "stdout": stdout,
                "stderr": stderr
            })
            print(f"  [{target_node}] [{idx:2d}/{len(recommended_commands):2d}] {cmd:<60} -> FAIL ({dt:.2f}s) - {'; '.join(errors)}")
        else:
            passed += 1
            print(f"  [{target_node}] [{idx:2d}/{len(recommended_commands):2d}] {cmd:<60} -> PASS ({dt:.2f}s)")

    return passed, failed, failures

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
        install_tasks = [("leaf1", "arista_node", "arista"),
                         ("leaf2", "cisco_node", "cisco"),
                         ("leaf3", "juniper_node", "juniper")]
        if not getattr(args, 'sequential', False):
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
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

    # Validate all recommended SR Linux commands
    p_srl, f_srl, fails_srl = validate_recommended_srl_commands(args.arista_node)
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
    parser.add_argument("--arista-node", default="leaf1", help="Target node running Arista EOS persona (default: leaf1)")
    parser.add_argument("--cisco-node", default="leaf2", help="Target node running Cisco NX-OS persona (default: leaf2)")
    parser.add_argument("--juniper-node", default="leaf3", help="Target node running Juniper JUNOS persona (default: leaf3)")
    parser.add_argument("--install", action="store_true", help="Automatically configure each target node with switch-multicli.sh before validation")
    parser.add_argument("--sequential", action="store_true", help="Run node test suites sequentially instead of in parallel")
    cli_args = parser.parse_args()

    success = validate(cli_args)
    sys.exit(0 if success else 1)
