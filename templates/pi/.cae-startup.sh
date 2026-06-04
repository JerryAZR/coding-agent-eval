#!/usr/bin/env bash
set -euo pipefail

# Install the pi coding agent if it is not already available.
# This runs inside the worker container (or locally when using local mode).
# For faster cold starts, bake pi into a custom image layer instead:
#
#   FROM cae-worker-base
#   RUN curl -fsSL https://pi.dev/install.sh | sh
#
# Then pass --worker-image <your-image> to cae run.

if ! command -v pi >/dev/null 2>&1; then
    echo "Installing pi coding agent..." >&2
    curl -fsSL https://pi.dev/install.sh | sh
fi

echo "pi version: $(pi --version 2>/dev/null || echo 'unknown')" >&2
