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

CLAB_DIR="/home/awhitaker/clab/srl-evpn-irb/clab-srl-evpn-irb/${TARGET_NODE}/config/cli"

if [ ! -d "$CLAB_DIR" ]; then
    echo "Error: Target node directory does not exist: $CLAB_DIR"
    exit 1
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

# Clean existing plugin subdirs in target node config/cli
rm -rf "$CLAB_DIR"/plugins/* "$CLAB_DIR"/system "$CLAB_DIR"/routing "$CLAB_DIR"/interface "$CLAB_DIR"/ip "$CLAB_DIR"/mac "$CLAB_DIR"/eth_switch "$CLAB_DIR"/bgp "$CLAB_DIR"/README.md 2>/dev/null || true
mkdir -p "$CLAB_DIR"/plugins

# Copy vendor suite
cp -r "$SOURCE_DIR"/* "$CLAB_DIR"/

echo "==> Successfully installed $NOS_NAME to $TARGET_NODE ($CLAB_DIR)."
echo "==> Test now with: docker exec -it $TARGET_NODE sr_cli"
