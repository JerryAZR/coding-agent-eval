#!/usr/bin/env bash
# Configure Podman/Docker registry mirrors for Docker Hub using CN mirrors.
# Run with sudo if needed for /etc/containers/.
set -euo pipefail

CONFIG_DIR="/etc/containers/registries.conf.d"
CONFIG_FILE="$CONFIG_DIR/docker-hub-cn.conf"

echo "Creating Podman registry mirror config for Docker Hub..."
mkdir -p "$CONFIG_DIR"

cat > "$CONFIG_FILE" <<'EOF'
# CN mirrors for Docker Hub (docker.io)
# Mirrors are tried in order; the first one that responds is used.
# If none of the mirrors have the image, the primary docker.io is tried last.

[[registry]]
prefix = "docker.io"
location = "docker.io"

[[registry.mirror]]
location = "docker.m.daocloud.io"

[[registry.mirror]]
location = "docker.1panel.live"

[[registry.mirror]]
location = "dockerhub.icu"

[[registry.mirror]]
location = "docker.mirrors.sjtug.sjtu.edu.cn"
EOF

echo "Wrote $CONFIG_FILE"
echo ""
echo "Mirrors configured:"
grep -E '^location' "$CONFIG_FILE" | sed 's/location = /  - /'
echo ""
echo "Restart Podman machine (if any) or restart the podman service to pick up changes."
echo "Then build with:  podman build --target cae-worker-pi -t cae-worker-pi -f images/Dockerfile ."
