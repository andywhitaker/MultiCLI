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

# Validate target node name
if [[ ! "$TARGET_NODE" =~ ^[a-zA-Z0-9_.-]+$ ]]; then
    echo "Error: Invalid target node name '$TARGET_NODE'"
    exit 1
fi

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
        *leaf4*) DEFAULT_PERSONA="nokia" ;;
        *) DEFAULT_PERSONA="arista" ;;
    esac
fi

# Validate default persona
case "$DEFAULT_PERSONA" in
    arista|cisco|juniper|nokia|none|all)
        ;;
    *)
        echo "Error: Invalid default persona '$DEFAULT_PERSONA'. Must be arista, cisco, juniper, nokia, none, or all."
        exit 1
        ;;
esac

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
    docker exec "$TARGET_NODE" python3 -c '
import os, json, shutil
cli_dir = "/etc/opt/srlinux/cli"
manifest_path = os.path.join(cli_dir, ".multicli_manifest.json")
legacy_files = {
    "plugins/main_arista.py", "plugins/main_cisco.py", "plugins/main_juniper.py", "plugins/main_nokia.py",
    "plugins/ip_reports.py", "plugins/mac_reports.py", "plugins/Cisco_nxos_lldp_neighbor",
    "plugins/ethernet_switching_reports.py", "plugins/show_interfaces.py", "plugins/sros_bgp_report.py",
    "plugins/service_report.py", "plugins/sros_router_report.py", "default_persona", "README.md"
}
legacy_dirs = ["system", "routing", "interface", "ip", "mac", "eth_switch", "bgp", "evpn", "service"]

to_remove = set(legacy_files)
dirs_to_clean = set(legacy_dirs)
if os.path.exists(manifest_path):
    try:
        with open(manifest_path) as f:
            m = json.load(f)
            to_remove.update(m.get("installed_files", []))
            dirs_to_clean.update(m.get("installed_dirs", []))
    except Exception:
        pass

for rel in to_remove:
    fp = os.path.join(cli_dir, rel)
    if os.path.isfile(fp):
        try: os.remove(fp)
        except Exception: pass

for d in sorted(dirs_to_clean - {"plugins", "."}, key=len, reverse=True):
    dp = os.path.join(cli_dir, d)
    if os.path.isdir(dp):
        try: os.rmdir(dp)
        except OSError: pass

if os.path.exists(manifest_path):
    try: os.remove(manifest_path)
    except Exception: pass
' 2>/dev/null || true
    docker exec "$TARGET_NODE" bash -c 'find /etc/opt/srlinux/cli/plugins -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true; mkdir -p /etc/opt/srlinux/cli/plugins'

    for v in "${VENDORS[@]}"; do
        docker cp "$SCRIPT_DIR/$v"/. "$TARGET_NODE":/etc/opt/srlinux/cli/
    done
    docker exec "$TARGET_NODE" sh -c 'printf "%s\n" "$1" > /etc/opt/srlinux/cli/default_persona' _ "$DEFAULT_PERSONA"

    # Generate .multicli_manifest.json dynamically from installed vendors
    docker exec -i "$TARGET_NODE" python3 - "$DEFAULT_PERSONA" << 'PYEOF'
import os, json, sys
cli_dir = '/etc/opt/srlinux/cli'
default_persona = sys.argv[1] if len(sys.argv) > 1 else 'none'
files = []
dirs = []
for root, d_list, f_list in os.walk(cli_dir):
    for d in d_list:
        if d != '__pycache__':
            rel_d = os.path.relpath(os.path.join(root, d), cli_dir)
            if rel_d != 'plugins':
                dirs.append(rel_d)
    for f in f_list:
        if not f.endswith('.pyc') and f != '.multicli_manifest.json':
            rel_f = os.path.relpath(os.path.join(root, f), cli_dir)
            # Only track MultiCLI files, never user files
            if not rel_f.startswith('plugins/') or any(rel_f == f'plugins/{p}' for p in ['main_arista.py','main_cisco.py','main_juniper.py','main_nokia.py','show_interfaces.py','ip_reports.py','mac_reports.py','Cisco_nxos_lldp_neighbor','ethernet_switching_reports.py','sros_bgp_report.py','service_report.py','sros_router_report.py']):
                files.append(rel_f)

manifest = {
    'version': '0.2.0',
    'installed_persona': default_persona,
    'installed_files': sorted(set(files)),
    'installed_dirs': sorted(set(dirs))
}
with open(os.path.join(cli_dir, '.multicli_manifest.json'), 'w') as fp:
    json.dump(manifest, fp, indent=2)
PYEOF
    echo "==> Successfully installed [${VENDORS[*]}] to $TARGET_NODE via docker cp."
else
    mkdir -p "$TARGET_CLI_DIR"/plugins
    python3 - "$TARGET_CLI_DIR" << 'PYEOF' 2>/dev/null || true
import os, json, sys
cli_dir = sys.argv[1]
manifest_path = os.path.join(cli_dir, '.multicli_manifest.json')
legacy_files = {
    'plugins/main_arista.py', 'plugins/main_cisco.py', 'plugins/main_juniper.py', 'plugins/main_nokia.py',
    'plugins/ip_reports.py', 'plugins/mac_reports.py', 'plugins/Cisco_nxos_lldp_neighbor',
    'plugins/ethernet_switching_reports.py', 'plugins/show_interfaces.py', 'plugins/sros_bgp_report.py',
    'plugins/service_report.py', 'plugins/sros_router_report.py', 'default_persona', 'README.md'
}
legacy_dirs = ['system', 'routing', 'interface', 'ip', 'mac', 'eth_switch', 'bgp', 'evpn', 'service']
to_remove = set(legacy_files)
dirs_to_clean = set(legacy_dirs)
if os.path.exists(manifest_path):
    try:
        with open(manifest_path) as f:
            m = json.load(f)
            to_remove.update(m.get('installed_files', []))
            dirs_to_clean.update(m.get('installed_dirs', []))
    except Exception: pass

for rel in to_remove:
    fp = os.path.join(cli_dir, rel)
    if os.path.isfile(fp):
        try: os.remove(fp)
        except Exception: pass

for d in sorted(dirs_to_clean - {'plugins', '.'}, key=len, reverse=True):
    dp = os.path.join(cli_dir, d)
    if os.path.isdir(dp):
        try: os.rmdir(dp)
        except OSError: pass

if os.path.exists(manifest_path):
    try: os.remove(manifest_path)
    except Exception: pass
PYEOF
    find "$TARGET_CLI_DIR"/plugins -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    mkdir -p "$TARGET_CLI_DIR"/plugins
    for v in "${VENDORS[@]}"; do
        cp -r "$SCRIPT_DIR/$v"/* "$TARGET_CLI_DIR"/
    done
    printf "%s\n" "$DEFAULT_PERSONA" > "$TARGET_CLI_DIR"/default_persona
    python3 - "$TARGET_CLI_DIR" "$DEFAULT_PERSONA" << 'PYEOF'
import os, json, sys
cli_dir = sys.argv[1]
default_persona = sys.argv[2] if len(sys.argv) > 2 else 'none'
files = []
dirs = []
for root, d_list, f_list in os.walk(cli_dir):
    for d in d_list:
        if d != '__pycache__':
            rel_d = os.path.relpath(os.path.join(root, d), cli_dir)
            if rel_d != 'plugins': dirs.append(rel_d)
    for f in f_list:
        if not f.endswith('.pyc') and f != '.multicli_manifest.json':
            rel_f = os.path.relpath(os.path.join(root, f), cli_dir)
            if not rel_f.startswith('plugins/') or any(rel_f == f'plugins/{p}' for p in ['main_arista.py','main_cisco.py','main_juniper.py','main_nokia.py','show_interfaces.py','ip_reports.py','mac_reports.py','Cisco_nxos_lldp_neighbor','ethernet_switching_reports.py','sros_bgp_report.py','service_report.py','sros_router_report.py']):
                files.append(rel_f)

manifest = {
    'version': '0.2.0',
    'installed_persona': default_persona,
    'installed_files': sorted(set(files)),
    'installed_dirs': sorted(set(dirs))
}
with open(os.path.join(cli_dir, '.multicli_manifest.json'), 'w') as fp:
    json.dump(manifest, fp, indent=2)
PYEOF
    echo "==> Successfully installed [${VENDORS[*]}] to $TARGET_NODE ($TARGET_CLI_DIR)."
fi

echo "==> Test now with: docker exec -it $TARGET_NODE sr_cli"
