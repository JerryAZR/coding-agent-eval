#!/usr/bin/env bash
set -euo pipefail

# Build CAE container images for Podman/Docker.
# Usage: ./scripts/build-images.sh [engine] [targets...]
#   engine: podman (default) or docker
#   targets: space-separated list of image targets (default: all base images)
#
# Examples:
#   ./scripts/build-images.sh                    # build all base images with podman
#   ./scripts/build-images.sh docker             # use docker instead of podman
#   ./scripts/build-images.sh podman cae-worker-pi  # build only pi worker

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

ENGINE="${1:-podman}"
shift || true

TARGETS=("${@:-cae-worker-base cae-tester-base cae-worker-standalone cae-tester-standalone cae-worker-fat cae-tester-fat}")

if ! command -v "$ENGINE" >/dev/null 2>&1; then
    echo "Error: $ENGINE not found. Install Podman or Docker first." >&2
    exit 1
fi

for target in ${TARGETS[@]}; do
    echo "Building ${target}..."
    "$ENGINE" build \
        --target "$target" \
        -t "$target" \
        -f images/Dockerfile \
        .
done

echo "Done. Built images:"
"$ENGINE" images --format '{{.Repository}}:{{.Tag}}' | grep '^cae-' || true
