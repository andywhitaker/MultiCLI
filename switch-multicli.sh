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

if [ -z "$TARGET_NOS" ]; then
    echo "Usage: $0 <arista|cisco|juniper> [node_name (default: leaf1)]"
    echo ""
    echo "Examples:"
    echo "  $0 arista leaf1      # Sets leaf1 to Arista EOS"
    echo "  $0 cisco leaf1       # Sets leaf1 to Cisco NX-OS"
    echo "  $0 juniper leaf1     # Sets leaf1 to Juniper JUNOS"
    exit 1
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

case "$TARGET_NOS" in
    arista|eos)
        SOURCE_DIR="$SCRIPT_DIR/arista"
        NOS_NAME="Arista EOS"
        ;;
    cisco|cisco-nx|nxos)
        SOURCE_DIR="$SCRIPT_DIR/cisco-nx"
        NOS_NAME="Cisco NX-OS"
        ;;
    juniper|junos)
        SOURCE_DIR="$SCRIPT_DIR/juniper"
        NOS_NAME="Juniper JUNOS"
        ;;
    *)
        echo "Error: Unknown NOS '$TARGET_NOS'. Choose 'arista', 'cisco', or 'juniper'."
        exit 1
        ;;
esac

echo "==> Configuring node '$TARGET_NODE' with $NOS_NAME persona..."

if [ "$USE_DOCKER_CP" = true ]; then
    # Clean in container (selective removal of multicli components)
    docker exec "$TARGET_NODE" bash -c 'rm -rf /etc/opt/srlinux/cli/plugins/* /etc/opt/srlinux/cli/{system,routing,interface,ip,mac,eth_switch,bgp,README.md} 2>/dev/null || true; mkdir -p /etc/opt/srlinux/cli/plugins'
    # Copy files into container
    docker cp "$SOURCE_DIR"/. "$TARGET_NODE":/etc/opt/srlinux/cli/
    echo "==> Successfully installed $NOS_NAME to $TARGET_NODE via docker cp."
else
    # Clean existing plugin subdirs in target node config/cli
    mkdir -p "$TARGET_CLI_DIR"/plugins
    rm -rf "$TARGET_CLI_DIR"/plugins/* "$TARGET_CLI_DIR"/system "$TARGET_CLI_DIR"/routing "$TARGET_CLI_DIR"/interface "$TARGET_CLI_DIR"/ip "$TARGET_CLI_DIR"/mac "$TARGET_CLI_DIR"/eth_switch "$TARGET_CLI_DIR"/bgp "$TARGET_CLI_DIR"/README.md 2>/dev/null || true
    mkdir -p "$TARGET_CLI_DIR"/plugins

    # Copy vendor suite
    cp -r "$SOURCE_DIR"/* "$TARGET_CLI_DIR"/
    echo "==> Successfully installed $NOS_NAME to $TARGET_NODE ($TARGET_CLI_DIR)."
fi

echo "==> Test now with: docker exec -it $TARGET_NODE sr_cli"
