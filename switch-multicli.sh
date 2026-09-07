#!/bin/bash
###############################################################################
# switch-multicli.sh
# Quickly switch the active MultiCLI NOS persona on a target SR Linux node.
# Usage: ./switch-multicli.sh <arista|cisco|juniper> [node_name]
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_NOS="${1:-}"
TARGET_NODE="${2:-leaf1}"
DEFAULT_PERSONA=""

# Parse optional --default flag
shift 2 2>/dev/null || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --default|-d)
            DEFAULT_PERSONA="${2:-}"
            shift 2 2>/dev/null || shift 1
            ;;
        *)
            shift 1
            ;;
    esac
done

if [ -z "$TARGET_NOS" ]; then
    echo "Usage: $0 <all|arista|cisco|juniper|nokia|comma-separated> [node_name (default: leaf1)] [--default <arista|cisco|juniper|nokia|none>]"
    echo ""
    echo "Examples:"
    echo "  $0 all leaf1                 # Installs all submodes on leaf1 with default persona (arista)"
    echo "  $0 all leaf2                 # Installs all submodes on leaf2 with default persona (cisco)"
    echo "  $0 all leaf3                 # Installs all submodes on leaf3 with default persona (juniper)"
    echo "  $0 arista leaf1              # Installs only Arista EOS on leaf1"
    echo "  $0 cisco leaf2               # Installs only Cisco NX-OS on leaf2"
    echo "  $0 juniper leaf3             # Installs only Juniper JUNOS on leaf3"
    echo "  $0 nokia leaf1               # Installs only Nokia SR OS on leaf1"
    echo "  $0 eos,nxos leaf1            # Installs Arista EOS and Cisco NX-OS on leaf1"
    exit 1
fi

# Infer default persona if not explicitly passed
if [ -z "$DEFAULT_PERSONA" ]; then
    case "$TARGET_NODE" in
        *leaf1*) DEFAULT_PERSONA="arista" ;;
        *leaf2*) DEFAULT_PERSONA="cisco" ;;
        *leaf3*) DEFAULT_PERSONA="juniper" ;;
        *) DEFAULT_PERSONA="arista" ;;
    esac
fi

# Determine target directory or docker mode
TARGET_CLI_DIR=""
USE_DOCKER_CP=false

# 1. Try resolving host mount path via docker inspect
if command -v docker >/dev/null 2>&1; then
    INSPECTED_DIR="$(docker inspect "$TARGET_NODE" --format '{{range .Mounts}}{{if eq .Destination "/etc/opt/srlinux"}}{{.Source}}/cli{{else if eq .Destination "/etc/opt/srlinux/cli"}}{{.Source}}{{end}}{{end}}' 2>/dev/null || true)"
    if [ -n "$INSPECTED_DIR" ] && [ -d "$(dirname "$INSPECTED_DIR")" ]; then
        TARGET_CLI_DIR="$INSPECTED_DIR"
    fi
fi

# 2. Check CLAB_DIR environment variable if provided
if [ -z "$TARGET_CLI_DIR" ] && [ -n "${CLAB_DIR:-}" ]; then
    if [ -d "$CLAB_DIR/${TARGET_NODE}/config/cli" ]; then
        TARGET_CLI_DIR="$CLAB_DIR/${TARGET_NODE}/config/cli"
    elif [ -d "$CLAB_DIR" ]; then
        TARGET_CLI_DIR="$CLAB_DIR"
    fi
fi

# 3. Search for clab lab directories relative to current or home directory
if [ -z "$TARGET_CLI_DIR" ]; then
    MATCH="$(find . -maxdepth 4 -type d -path "*/${TARGET_NODE}/config/cli" 2>/dev/null | head -n 1 || true)"
    if [ -n "$MATCH" ] && [ -d "$MATCH" ]; then
        TARGET_CLI_DIR="$MATCH"
    fi
fi

# 4. If directory not found on host, check if target container is running
if [ -z "$TARGET_CLI_DIR" ]; then
    if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -qw "$TARGET_NODE"; then
        USE_DOCKER_CP=true
    else
        echo "Error: Could not locate configuration directory for '$TARGET_NODE' and container is not running."
        echo "Please specify CLAB_DIR environment variable or run the containerlab topology."
        exit 1
    fi
fi

# Parse target NOS list
VENDORS=()
IFS=',' read -ra ADDR <<< "$TARGET_NOS"
for part in "${ADDR[@]}"; do
    case "$part" in
        all|multicli)
            VENDORS=("arista" "cisco-nx" "juniper" "nokia")
            break
            ;;
        arista|eos)
            VENDORS+=("arista")
            ;;
        cisco|cisco-nx|nxos)
            VENDORS+=("cisco-nx")
            ;;
        juniper|junos)
            VENDORS+=("juniper")
            ;;
        nokia|sros)
            VENDORS+=("nokia")
            ;;
        *)
            echo "Error: Unknown NOS '$part'. Choose 'all', 'arista', 'cisco', 'juniper', or 'nokia'."
            exit 1
            ;;
    esac
done

echo "==> Configuring node '$TARGET_NODE' with MultiCLI [${VENDORS[*]}] (default persona: $DEFAULT_PERSONA)..."

if [ "$USE_DOCKER_CP" = true ]; then
    docker exec "$TARGET_NODE" bash -c 'rm -rf /etc/opt/srlinux/cli/plugins/{main_{arista,cisco,juniper}.py,ip_reports.py,mac_reports.py,Cisco_nxos_lldp_neighbor,ethernet_switching_reports.py,show_interfaces.py,sros_bgp_report.py,service_report.py,sros_router_report.py} /etc/opt/srlinux/cli/{system,routing,interface,ip,mac,eth_switch,bgp,evpn,README.md} 2>/dev/null || true; find /etc/opt/srlinux/cli -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true; mkdir -p /etc/opt/srlinux/cli/plugins'
    for v in "${VENDORS[@]}"; do
        docker cp "$SCRIPT_DIR/$v"/. "$TARGET_NODE":/etc/opt/srlinux/cli/
    done
    docker exec "$TARGET_NODE" bash -c "echo '$DEFAULT_PERSONA' > /etc/opt/srlinux/cli/default_persona"
    echo "==> Successfully installed [${VENDORS[*]}] to $TARGET_NODE via docker cp."
else
    mkdir -p "$TARGET_CLI_DIR"/plugins
    rm -rf "$TARGET_CLI_DIR"/plugins/{main_{arista,cisco,juniper}.py,ip_reports.py,mac_reports.py,Cisco_nxos_lldp_neighbor,ethernet_switching_reports.py,show_interfaces.py,sros_bgp_report.py,service_report.py,sros_router_report.py} "$TARGET_CLI_DIR"/{system,routing,interface,ip,mac,eth_switch,bgp,evpn,README.md} 2>/dev/null || true
    find "$TARGET_CLI_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    mkdir -p "$TARGET_CLI_DIR"/plugins
    for v in "${VENDORS[@]}"; do
        cp -r "$SCRIPT_DIR/$v"/* "$TARGET_CLI_DIR"/
    done
    echo "$DEFAULT_PERSONA" > "$TARGET_CLI_DIR"/default_persona
    echo "==> Successfully installed [${VENDORS[*]}] to $TARGET_NODE ($TARGET_CLI_DIR)."
fi

echo "==> Test now with: docker exec -it $TARGET_NODE sr_cli"
