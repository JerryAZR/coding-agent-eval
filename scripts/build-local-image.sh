#!/bin/bash
# Build a minimal CAE base image from host's Python 3.11 (no network required).
set -euo pipefail

PYTHON_BIN="/usr/bin/python3.11"
IMAGE_TAG="${1:-cae-worker-base}"

echo "Creating container from scratch..."
CTR=$(buildah from scratch)
MNT=$(buildah mount "$CTR")

# Copy Python binary
echo "Copying Python binary..."
mkdir -p "$MNT/usr/bin"
cp "$PYTHON_BIN" "$MNT/usr/bin/python"

# Copy shared libraries needed by Python
echo "Copying shared libraries..."
ldd "$PYTHON_BIN" | awk '{print $3}' | grep -v '^(' | grep -v '^$' | while read -r lib; do
    if [ -f "$lib" ]; then
        dir=$(dirname "$lib")
        mkdir -p "$MNT$dir"
        cp -L "$lib" "$MNT$lib"
    fi
done

# Also copy ld-linux if referenced
ld_linux=$(ldd "$PYTHON_BIN" | grep 'ld-linux' | awk '{print $1}')
if [ -n "$ld_linux" ] && [ -f "$ld_linux" ]; then
    dir=$(dirname "$ld_linux")
    mkdir -p "$MNT$dir"
    cp -L "$ld_linux" "$MNT$ld_linux"
fi

# Copy Python standard library
echo "Copying Python standard library..."
PYTHON_LIB="/usr/lib/python3.11"
if [ -d "$PYTHON_LIB" ]; then
    mkdir -p "$MNT$PYTHON_LIB"
    cp -r "$PYTHON_LIB"/* "$MNT$PYTHON_LIB/"
fi

# Copy any .so files in the stdlib (e.g., _ctypes, _ssl, etc.)
if [ -d "$PYTHON_LIB/lib-dynload" ]; then
    for so in "$PYTHON_LIB/lib-dynload"/*.so; do
        if [ -f "$so" ]; then
            ldd "$so" 2>/dev/null | awk '{print $3}' | grep -v '^(' | grep -v '^$' | while read -r lib; do
                if [ -f "$lib" ]; then
                    dir=$(dirname "$lib")
                    mkdir -p "$MNT$dir"
                    cp -L "$lib" "$MNT$lib"
                fi
            done
        fi
    done
fi

# We need /bin/sh for exec in ContainerRuntime (it uses shell=False Popen,
# but podman run defaults to /bin/sh -c if no entrypoint is set).
# Actually no - our command is a list, so it runs directly. But let's be safe.
# The real problem is some stdlib modules need additional libs.

buildah unmount "$CTR"
buildah commit "$CTR" "$IMAGE_TAG"
buildah rm "$CTR"

echo "Built $IMAGE_TAG successfully."

# Also tag as tester image if requested
if [ "$IMAGE_TAG" = "cae-worker-base" ]; then
    buildah tag "$IMAGE_TAG" "cae-tester-base"
    echo "Tagged as cae-tester-base too."
fi
