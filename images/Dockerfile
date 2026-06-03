# CAE base images for container mode
#
# Build:
#   podman build --target cae-worker-base -t cae-worker-base .
#   podman build --target cae-tester-base -t cae-tester-base .
#   podman build --target cae-worker-pi   -t cae-worker-pi   .
#
# Or use scripts/build-images.sh

ARG PYTHON_VERSION=3.11
ARG DEBIAN_VERSION=bookworm

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-${DEBIAN_VERSION}-slim AS cae-base

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /cae

# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------
FROM cae-base AS cae-worker-base
LABEL role=worker
ENTRYPOINT ["python", "-m", "cae.worker"]

# ---------------------------------------------------------------------------
# Tester
# ---------------------------------------------------------------------------
FROM cae-base AS cae-tester-base
LABEL role=tester
ENTRYPOINT ["python", "-m", "cae.tester"]

# ---------------------------------------------------------------------------
# Standalone (bake framework in — no bind-mount needed for src/)
# ---------------------------------------------------------------------------
FROM cae-worker-base AS cae-worker-standalone
COPY src/ /cae/src/
ENV PYTHONPATH=/cae/src

FROM cae-tester-base AS cae-tester-standalone
COPY src/ /cae/src/
ENV PYTHONPATH=/cae/src

# ---------------------------------------------------------------------------
# Layered pi worker (Node.js + pi pre-installed)
# ---------------------------------------------------------------------------
FROM cae-worker-base AS cae-worker-pi
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @earendil-works/pi-coding-agent
# `pi` is now in PATH

# ---------------------------------------------------------------------------
# Usage notes
# ---------------------------------------------------------------------------
# Development (bind-mount CAE source):
#   podman run --rm --userns=keep-id \
#     -v /host/run:/run:Z -v /host/src:/cae/src:Z -e PYTHONPATH=/cae/src \
#     cae-worker-base --volume /run --agent-mode echo
#
# Production (standalone image):
#   podman run --rm --userns=keep-id -v /host/run:/run:Z \
#     cae-worker-standalone --volume /run --agent-mode echo
#
# --userns=keep-id  → rootless UID mapping (host user = container root)
# -d is NOT used     → host process mirrors subprocess.Popen semantics
# :Z on volumes      → SELinux label relabeling
# --net=none         → tester only (no network during evaluation)
#
# For full docs see docs/container-mode.md
# vim: set ft=dockerfile :
