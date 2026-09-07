#!/usr/bin/env python3
"""
validate_multicli.py
Automated validation harness for all MultiCLI commands across
Arista EOS (leaf1), Cisco NX-OS (leaf2), and Juniper JUNOS (leaf3).
"""

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
            "show bgp evpn summary",
        ],
        "negative_assertions": [
            ("show mlag", "state: Active", "show mlag should not output hardcoded 'state: Active' when no MLAG is configured"),
            ("show port-channel summary", "LACP(a)", "show port-channel summary should not hardcode LACP(a) when no LAG is configured"),
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
            "show mac address-table",
            "show mac address-table vlan 1",
            "show mac address-table interface ethernet-1/1",
            "show mac address-table vni 1",
            "show vrf",
            "show vlan",
            "show bfd neighbors",
            "show ip ospf neighbor",
            "show ip ospf interface brief",
            "show nve vni",
            "show nve peers",
            "show vpc",
        ],
        "negative_assertions": [
            ("show vpc", "peer-link is up", "show vpc should not output hardcoded 'peer-link is up' when no VPC/ES is configured"),
            ("show nve peers", "state: Up", "show nve peers should not output hardcoded 'state: Up' when no NVE peer is present"),
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
            "show route summary",
            "show bgp summary",
            "show ospf neighbor",
            "show isis adjacency",
        ],
        "negative_assertions": [
            ("show system uptime", "Time Source: NTP CLOCK", "show system uptime should dynamically verify NTP state rather than hardcoding NTP CLOCK"),
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

def run_command(node, cmd):
    full_cmd = ["docker", "exec", node, "sr_cli", cmd]
    t0 = time.time()
    res = subprocess.run(full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    dt = time.time() - t0
    return res.returncode, res.stdout, res.stderr, dt

def validate(args):
    total_passed = 0
    total_failed = 0
    failures = []

    print("=" * 80)
    print("MultiCLI Comprehensive Automated Validation Test Suite")
    print("=" * 80)

    for suite_name, suite in TEST_SUITES.items():
        node = getattr(args, suite["arg_key"], suite["default_node"])
        commands = suite["commands"]
        neg_assertions = dict(((c, p), msg) for c, p, msg in suite.get("negative_assertions", []))
        print(f"\n--- Running {suite_name} on container '{node}' ({len(commands)} commands) ---")

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
                if cmd == neg_cmd and bad_pattern in stdout:
                    errors.append(f"Assertion failed: {failure_msg} (found '{bad_pattern}')")

            if errors:
                total_failed += 1
                status = "FAIL"
                failures.append({
                    "suite": suite_name,
                    "node": node,
                    "command": cmd,
                    "errors": errors,
                    "stdout": stdout,
                    "stderr": stderr
                })
                print(f"  [{idx:2d}/{len(commands):2d}] {cmd:<44} -> {status} ({dt:.2f}s) - {'; '.join(errors)}")
            else:
                total_passed += 1
                status = "PASS"
                print(f"  [{idx:2d}/{len(commands):2d}] {cmd:<44} -> {status} ({dt:.2f}s)")

    print("\n" + "=" * 80)
    print(f"Test Summary: Total={total_passed + total_failed} | Passed={total_passed} | Failed={total_failed}")
    print("=" * 80)

    if failures:
        print(f"\nFAILED COMMANDS DETAILS ({len(failures)} failures):")
        for f in failures:
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
    cli_args = parser.parse_args()

    success = validate(cli_args)
    sys.exit(0 if success else 1)
