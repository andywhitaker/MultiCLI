#!/bin/bash
###############################################################################
# build-deb.sh
# MultiCLI NDK Agent Debian Package Builder
# Builds .deb packages for specified architecture or all supported architectures.
# Usage: ./build-deb.sh [amd64|arm64|x86_64|all]
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_ARCH="${1:-all}"
VERSION="${VERSION:-1.0.0}"

if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "Error: dpkg-deb is required to build Debian packages."
    exit 1
fi

ARCH_LIST=()
case "$TARGET_ARCH" in
    all)
        ARCH_LIST=("amd64" "arm64" "x86_64")
        ;;
    amd64|arm64|x86_64)
        ARCH_LIST=("$TARGET_ARCH")
        ;;
    *)
        echo "Usage: $0 [amd64|arm64|x86_64|all (default: all)]"
        exit 1
        ;;
esac

for ARCH in "${ARCH_LIST[@]}"; do
    echo "==> Building srl-multicli_${ARCH}.deb (v${VERSION})..."
    BUILD_ROOT="$(mktemp -d "/tmp/multicli-build-${ARCH}-XXXXXX")"

    # Copy source tree
    cp -r "$SCRIPT_DIR/src/." "$BUILD_ROOT/"

    # Set permissions
    find "$BUILD_ROOT" -type d -exec chmod 755 {} +
    find "$BUILD_ROOT/etc" "$BUILD_ROOT/tmp" -type f -exec chmod 644 {} +
    chmod 755 "$BUILD_ROOT/DEBIAN/postinst"
    chmod 755 "$BUILD_ROOT/etc/opt/srlinux/appmgr/multicli/multicli.py"
    chmod 755 "$BUILD_ROOT/etc/opt/srlinux/appmgr/multicli/multicli.sh"
    chmod 755 "$BUILD_ROOT/etc/opt/srlinux/appmgr/multicli/multicli_version.sh"

    # Update Architecture in control file (Debian uses amd64 for x86_64)
    CONTROL_ARCH="$ARCH"
    if [ "$CONTROL_ARCH" = "x86_64" ]; then
        CONTROL_ARCH="amd64"
    fi
    sed -i "s/^Architecture: .*/Architecture: ${CONTROL_ARCH}/" "$BUILD_ROOT/DEBIAN/control"
    sed -i "s/^Version: .*/Version: ${VERSION}/" "$BUILD_ROOT/DEBIAN/control"

    # Generate md5sums for all package files excluding DEBIAN
    (
        cd "$BUILD_ROOT"
        find etc tmp -type f -exec md5sum {} + > "$BUILD_ROOT/DEBIAN/md5sums"
    )

    # Build Debian package
    OUTPUT_DEB="$SCRIPT_DIR/srl-multicli_${ARCH}.deb"
    dpkg-deb --build --root-owner-group "$BUILD_ROOT" "$OUTPUT_DEB" >/dev/null

    echo "==> Generated: $OUTPUT_DEB ($(ls -lh "$OUTPUT_DEB" | awk '{print $5}'))"
    rm -rf "$BUILD_ROOT"
done

echo "==> Build complete for [${ARCH_LIST[*]}]."
